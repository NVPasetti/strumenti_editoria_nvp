import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Strumenti Editoriali", layout="wide", page_icon="📚")

# --- CONNESSIONE A SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Errore di connessione a Supabase: {e}")
    supabase = None

# --- FUNZIONI DATABASE (Solo per Amazon) ---
def carica_preferiti_db():
    if supabase:
        try:
            risposta = supabase.table("wishlist").select("asin, nota").execute()
            return {r["asin"]: (r.get("nota") or "") for r in risposta.data}
        except Exception:
            try:
                risposta = supabase.table("wishlist").select("asin").execute()
                return {r["asin"]: "" for r in risposta.data}
            except Exception:
                return {}
    return {}

def salva_preferito_db(item_id):
    if supabase:
        try:
            supabase.table("wishlist").insert({"asin": item_id, "nota": ""}).execute()
        except Exception:
            try:
                supabase.table("wishlist").insert({"asin": item_id}).execute()
            except Exception as e:
                st.toast(f"⚠️ Errore salvataggio nel DB: {e}")

def aggiorna_nota_db(item_id, nota_testo):
    if supabase:
        try:
            supabase.table("wishlist").update({"nota": nota_testo}).eq("asin", item_id).execute()
        except Exception as e:
            st.toast("⚠️ Errore aggiornamento nota DB")

def rimuovi_preferito_db(item_id):
    if supabase:
        try:
            supabase.table("wishlist").delete().eq("asin", item_id).execute()
        except Exception as e:
            st.toast(f"⚠️ Errore rimozione dal DB: {e}")

def svuota_salvati_db():
    st.session_state.libri_salvati.clear()
    if supabase:
        try:
            supabase.table("wishlist").delete().neq("asin", "dummy_value").execute()
        except Exception as e:
            st.error(f"Errore nello svuotamento: {e}")

# --- INIZIALIZZAZIONE MEMORIA GLOBALE ---
if 'libri_salvati' not in st.session_state:
    st.session_state.libri_salvati = carica_preferiti_db()

def toggle_salvataggio(item_id):
    if item_id in st.session_state.libri_salvati:
        del st.session_state.libri_salvati[item_id]
        rimuovi_preferito_db(item_id)
    else:
        st.session_state.libri_salvati[item_id] = ""
        salva_preferito_db(item_id)

# --- FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data(ttl=3600)
def load_amazon_data(file_name):
    if not os.path.exists(file_name): return None
    try:
        df = pd.read_csv(file_name)
        df['Titolo'] = df['Titolo'].fillna("Senza Titolo")
        df['Autore'] = df['Autore'].fillna("N/D")
        df = df.drop_duplicates(subset=['ASIN'])
        df = df.drop_duplicates(subset=['Titolo'])
        return df
    except Exception: return None

@st.cache_data(ttl=3600)
def load_ibs_data(file_name):
    if not os.path.exists(file_name): return None
    try:
        df = pd.read_csv(file_name)
        df['Titolo'] = df['Titolo'].fillna("Senza Titolo")
        df['Editore'] = df['Editore'].fillna("N/D")
        if 'Nuovo' not in df.columns:
            df['Nuovo'] = False
        else:
            df['Nuovo'] = df['Nuovo'].astype(bool)
        return df
    except Exception as e: 
        st.error(f"Errore lettura CSV IBS: {e}")
        return None

# ==========================================
# SIDEBAR: NAVIGAZIONE PRINCIPALE
# ==========================================
st.sidebar.header("🛠️ Strumenti")
piattaforma = st.sidebar.radio("Scegli servizio:", ["🔴 Novità saggistica (30 giorni)", "🟠 Scouting Amazon"])
st.sidebar.markdown("---")

# ==========================================
# SEZIONE 1: NOVITÀ SAGGISTICA (IBS) - STILE CLASSICO
# ==========================================
if piattaforma == "🔴 Novità saggistica (30 giorni)":
    st.title("📚 Novità Saggistica")

    file_name = "dati_per_app.csv"
    df_ibs = load_ibs_data(file_name)

    if df_ibs is None:
        st.error(f"⚠️ File '{file_name}' non trovato! Attendi il primo aggiornamento automatico.")
    else:
        # --- NOTIFICA NUOVI ARRIVI ---
        nuovi_libri = df_ibs[df_ibs['Nuovo'] == True]
        num_nuovi = len(nuovi_libri)

        if num_nuovi > 0:
            st.success(f"🔔 **Aggiornamento:** Ci sono **{num_nuovi}** nuovi libri rispetto all'ultimo controllo!")
            with st.expander(f"👀 Vedi la lista dei {num_nuovi} nuovi arrivi"):
                for _, row in nuovi_libri.iterrows():
                    st.markdown(f"🆕 **{row['Titolo']}** - {row['Autore']} ({row['Editore']})")

        # --- SEPARAZIONE DATI ---
        df_vip = df_ibs[df_ibs['Categoria_App'] == 'Editori Selezionati'].copy()
        df_altri = df_ibs[df_ibs['Categoria_App'] != 'Editori Selezionati'].copy()

        # --- SIDEBAR: FILTRI E ORDINAMENTO ---
        # 1. BARRA DI RICERCA
        search_query = st.sidebar.text_input("🔍 Cerca libro o autore", help="Cerca in entrambe le liste")

        # 2. FILTRO EDITORE (Solo VIP)
        st.sidebar.subheader("Filtra Selezionati")
        editori_disponibili = sorted(df_vip['Editore'].unique())
        sel_editore = st.sidebar.multiselect("Seleziona Editore", editori_disponibili)

        # 3. ORDINAMENTO (Solo VIP)
        st.sidebar.subheader("Ordina Selezionati")
        sort_mode = st.sidebar.selectbox(
            "Criterio di ordinamento:",
            ["Titolo (A-Z)", "Titolo (Z-A)", "Editore (A-Z)", "Editore (Z-A)"]
        )

        # --- APPLICAZIONE FILTRI ---
        if search_query:
            if not df_vip.empty:
                mask_vip = df_vip.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                df_vip = df_vip[mask_vip]
            if not df_altri.empty:
                mask_altri = df_altri.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
                df_altri = df_altri[mask_altri]

        if sel_editore:
            df_vip = df_vip[df_vip['Editore'].isin(sel_editore)]

        if not df_vip.empty:
            if sort_mode == "Titolo (A-Z)":
                df_vip = df_vip.sort_values(by='Titolo', ascending=True)
            elif sort_mode == "Titolo (Z-A)":
                df_vip = df_vip.sort_values(by='Titolo', ascending=False)
            elif sort_mode == "Editore (A-Z)":
                df_vip = df_vip.sort_values(by='Editore', ascending=True)
            elif sort_mode == "Editore (Z-A)":
                df_vip = df_vip.sort_values(by='Editore', ascending=False)

        # --- INTERFACCIA A TAB ---
        tab1, tab2 = st.tabs([f"⭐ Editori Selezionati ({len(df_vip)})", f"📂 Altri Editori ({len(df_altri)})"])

        # === TAB 1: EDITORI SELEZIONATI ===
        with tab1:
            if df_vip.empty:
                st.info("Nessun libro trovato con i filtri attuali.")
            
            for _, row in df_vip.iterrows():
                with st.container():
                    c1, c2 = st.columns([1, 5])
                    
                    with c1:
                        url = row['Copertina']
                        if pd.notna(url) and str(url).startswith('http'):
                            st.image(str(url), width=120)
                        else:
                            st.text("🖼️ No Img")
                    
                    with c2:
                        badge = "🆕 " if row['Nuovo'] else ""
                        st.subheader(f"{badge}{row['Titolo']}")
                        
                        st.markdown(f"**{row.get('Autore', 'N/D')}** | *{row.get('Editore', 'N/D')}* ({row.get('Anno', '')})")
                        
                        desc = str(row.get('Descrizione', ''))
                        if len(desc) > 10 and desc.lower() != "nan":
                            with st.expander("📖 Leggi sinossi"):
                                st.write(desc)
                        
                        link = row.get('Link')
                        if pd.notna(link) and str(link).startswith('http'):
                            st.markdown(f"[➡️ Vedi su IBS]({link})")
                    
                    st.divider()

        # === TAB 2: ALTRI EDITORI ===
        with tab2:
            st.caption("Libri di altri editori (lista standard).")
            
            if df_altri.empty:
                st.info("Nessun libro in questa categoria.")

            for _, row in df_altri.iterrows():
                with st.container():
                    c_img, c_info = st.columns([0.5, 5])
                    
                    with c_img:
                        url = row['Copertina']
                        if pd.notna(url) and str(url).startswith('http'):
                            st.image(str(url), width=60)
                    
                    with c_info:
                        badge = "🆕 " if row['Nuovo'] else ""
                        st.markdown(f"{badge}**{row['Titolo']}**")
                        st.markdown(f"{row.get('Autore', 'N/D')} - *{row.get('Editore', 'N/D')}*")
                        
                        link = row.get('Link')
                        if pd.notna(link) and str(link).startswith('http'):
                            st.markdown(f"[Link]({link})")
                    
                    st.markdown("---")

# ==========================================
# SEZIONE 2: SCOUTING AMAZON - STILE GRIGLIA
# ==========================================
elif piattaforma == "🟠 Scouting Amazon":
    st.title("I più venduti - Amazon")
    st.caption("Esplora i libri più popolari, salvali e aggiungi le tue note.")

    # Mostra Wishlist Info solo qui
    num_salvati = len(st.session_state.libri_salvati)
    st.sidebar.metric(label="❤️ Appunti & Salvati", value=f"{num_salvati} libri")
    if num_salvati > 0:
        st.sidebar.button("🗑️ Svuota Salvati", on_click=svuota_salvati_db, type="secondary", use_container_width=True)
    st.sidebar.markdown("---")

    if 'limite_libri_amz' not in st.session_state: st.session_state.limite_libri_amz = 150
    if 'filtro_cat_amz' not in st.session_state: st.session_state.filtro_cat_amz = "Tutte"
    if 'filtro_rec_amz' not in st.session_state: st.session_state.filtro_rec_amz = 60
    if 'filtro_ord_amz' not in st.session_state: st.session_state.filtro_ord_amz = "Decrescente (Più recensioni)"
    if 'filtro_salvati_amz' not in st.session_state: st.session_state.filtro_salvati_amz = False

    df_amz = load_amazon_data("amazon_libri_multicat.csv")

    if df_amz is None:
        st.warning("⚠️ Dati Amazon non ancora disponibili. Attendi che lo scraper generi il file CSV.")
    else:
        st.sidebar.header("Filtri Amazon")
        categorie_amz = ["Tutte"] + sorted(df_amz['Categoria'].unique().tolist())
        sel_cat_amz = st.sidebar.selectbox("Reparto:", categorie_amz)
        
        max_recensioni = int(df_amz['Recensioni'].max()) if not df_amz.empty else 1000
        min_rec_amz = st.sidebar.slider("Filtra per popolarità (min. recensioni):", 0, max_recensioni, value=60, step=50)
        
        ord_amz = st.sidebar.radio("Ordina per recensioni:", ["Decrescente (Più recensioni)", "Crescente (Meno recensioni)"])
        is_ascending_amz = True if ord_amz == "Crescente (Meno recensioni)" else False
        
        mostra_salvati_amz = st.sidebar.checkbox("Visualizza solo i Salvati")

        if (sel_cat_amz != st.session_state.filtro_cat_amz or min_rec_amz != st.session_state.filtro_rec_amz or 
            ord_amz != st.session_state.filtro_ord_amz or mostra_salvati_amz != st.session_state.filtro_salvati_amz):
            st.session_state.limite_libri_amz = 150
            st.session_state.filtro_cat_amz = sel_cat_amz
            st.session_state.filtro_rec_amz = min_rec_amz
            st.session_state.filtro_ord_amz = ord_amz
            st.session_state.filtro_salvati_amz = mostra_salvati_amz

        df_filtrato = df_amz.copy()
        
        if mostra_salvati_amz:
            df_filtrato = df_filtrato[df_filtrato['ASIN'].isin(st.session_state.libri_salvati.keys())]
        else:
            if sel_cat_amz != "Tutte":
                df_filtrato = df_filtrato[df_filtrato['Categoria'] == sel_cat_amz]
            df_filtrato = df_filtrato[df_filtrato['Recensioni'] >= min_rec_amz]
            
        df_filtrato = df_filtrato.sort_values(by='Recensioni', ascending=is_ascending_amz)

        totale_libri = len(df_filtrato)
        st.markdown(f"**{totale_libri}** risultati trovati")
        st.markdown("---")

        df_mostrato = df_filtrato.iloc[:st.session_state.limite_libri_amz]
        lista_libri = list(df_mostrato.iterrows())
        
        for i in range(0, len(lista_libri), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(lista_libri):
                    index, row = lista_libri[i + j]
                    asin = row.get('ASIN', '')
                    is_saved = asin in st.session_state.libri_salvati
                    
                    with cols[j]:
                        with st.container(border=True):
                            c_titolo, c_cuore = st.columns([5, 1])
                            with c_cuore:
                                st.button("❤️" if is_saved else "🤍", key=f"amz_{asin}", on_click=toggle_salvataggio, args=(asin,), type="tertiary")
                            with c_titolo:
                                st.markdown(f"<div style='height: 55px; padding-top: 4px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-weight: bold; font-size: 1.05em; text-align: left;'>{row['Titolo']}</div>", unsafe_allow_html=True)
                            
                            url_img = row['Copertina']
                            if pd.notna(url_img) and str(url_img).startswith('http'):
                                st.markdown(f"<div style='height: 450px; display: flex; justify-content: center; align-items: center; margin-bottom: 15px;'><img src='{url_img}' style='width: 100%; height: 100%; object-fit: contain;'></div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div style='height: 450px; display: flex; justify-content: center; align-items: center; margin-bottom: 15px; background-color: #f8f9fa; border-radius: 5px;'>🖼️ <i>Nessuna Immagine</i></div>", unsafe_allow_html=True)
                            
                            c_info, c_note = st.columns([5, 1])
                            with c_info:
                                autore = str(row.get('Autore', 'N/D'))
                                autore_corto = autore[:35] + "..." if len(autore) > 35 else autore
                                st.markdown(f"""
                                <div style='height: 80px; line-height: 1.4; text-align: left;'>
                                    <span style='font-size: 0.85em; color: gray;'>Di: <b>{autore_corto}</b></span><br>
                                    <span style='font-size: 0.9em;'>⭐⭐⭐⭐⭐ ({int(row['Recensioni'])})</span><br>
                                    <span style='font-size: 0.8em; color: gray;'>Reparto: {row.get('Categoria', 'N/D')}</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            with c_note:
                                if is_saved:
                                    st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
                                    nota_attuale = st.session_state.libri_salvati.get(asin, "").strip()
                                    icona_nota = "📒" if nota_attuale else "📝"
                                    with st.popover(icona_nota, help="Gestisci nota"):
                                        nuova_nota = st.text_area("Appunti:", value=nota_attuale, key=f"txt_{asin}", height=120)
                                        if st.button("Salva", key=f"btn_nota_{asin}", type="primary", use_container_width=True):
                                            st.session_state.libri_salvati[asin] = nuova_nota
                                            aggiorna_nota_db(asin, nuova_nota)
                                            st.toast("✅ Nota salvata!")
                                            st.rerun()

                            st.link_button("Vedi su Amazon", f"https://www.amazon.it/dp/{asin}" if pd.notna(asin) else "#", type="primary", use_container_width=True)

        if st.session_state.limite_libri_amz < totale_libri:
            st.markdown("---")
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                if st.button("⬇️ Carica altri libri", use_container_width=True, key="btn_load_amz"):
                    st.session_state.limite_libri_amz += 150
                    st.rerun()
