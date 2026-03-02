import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Radar Editoriale", layout="wide")

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

# --- FUNZIONI DATABASE ---
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
        df['Autore'] = df['Autore'].fillna("N/D")
        df['Descrizione'] = df['Descrizione'].fillna("Nessuna descrizione disponibile.")
        df = df.drop_duplicates(subset=['Link'])
        return df
    except Exception: return None

# ==========================================
# SIDEBAR: NAVIGAZIONE PRINCIPALE E SALVATI
# ==========================================
st.sidebar.title("📚 Radar Editoriale")
piattaforma = st.sidebar.radio("Scegli la Piattaforma:", ["🟠 Amazon (Bestseller)", "🔴 IBS (Novità Editori)"])

st.sidebar.markdown("---")
num_salvati = len(st.session_state.libri_salvati)
st.sidebar.metric(label="❤️ Wishlist Globale", value=f"{num_salvati} libri")

if num_salvati > 0:
    st.sidebar.button("🗑️ Svuota Salvati", on_click=svuota_salvati_db, type="secondary", use_container_width=True)
st.sidebar.markdown("---")

# ==========================================
# SEZIONE 1: AMAZON BESTSELLER
# ==========================================
if piattaforma == "🟠 Amazon (Bestseller)":
    st.title("I più venduti - Amazon")
    st.caption("Esplora i libri più popolari, salvali e aggiungi le tue note.")

    if 'limite_libri_amz' not in st.session_state: st.session_state.limite_libri_amz = 150
    if 'filtro_cat_amz' not in st.session_state: st.session_state.filtro_cat_amz = "Tutte"
    if 'filtro_rec_amz' not in st.session_state: st.session_state.filtro_rec_amz = 60
    if 'filtro_ord_amz' not in st.session_state: st.session_state.filtro_ord_amz = "Decrescente (Più recensioni)"
    if 'filtro_salvati_amz' not in st.session_state: st.session_state.filtro_salvati_amz = False

    df_amz = load_amazon_data("amazon_libri_multicat.csv")

    if df_amz is None:
        st.warning("⚠️ Dati Amazon non ancora disponibili.")
    else:
        st.sidebar.header("Filtri Amazon")
        categorie_amz = ["Tutte"] + sorted(df_amz['Categoria'].unique().tolist())
        sel_cat_amz = st.sidebar.selectbox("Reparto:", categorie_amz)
        
        max_recensioni = int(df_amz['Recensioni'].max()) if not df_amz.empty else 1000
        min_rec_amz = st.sidebar.slider("Filtra per popolarità (min. recensioni):", 0, max_recensioni, value=60, step=50)
        
        ord_amz = st.sidebar.radio("Ordina per recensioni:", ["Decrescente (Più recensioni)", "Crescente (Meno recensioni)"])
        is_ascending_amz = True if ord_amz == "Crescente (Meno recensioni)" else False
        
        mostra_salvati_amz = st.sidebar.checkbox("Visualizza solo i Salvati (Amazon)")

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

# ==========================================
# SEZIONE 2: IBS NOVITÀ
# ==========================================
elif piattaforma == "🔴 IBS (Novità Editori)":
    st.title("Novità Editoriali - IBS")
    st.caption("Filtra le ultime uscite per scoprire le chicche degli Editori Target.")

    if 'limite_libri_ibs' not in st.session_state: st.session_state.limite_libri_ibs = 150
    if 'filtro_cat_ibs' not in st.session_state: st.session_state.filtro_cat_ibs = "Tutti"
    if 'filtro_nuovi_ibs' not in st.session_state: st.session_state.filtro_nuovi_ibs = False
    if 'filtro_salvati_ibs' not in st.session_state: st.session_state.filtro_salvati_ibs = False

    df_ibs = load_ibs_data("dati_per_app.csv")

    if df_ibs is None:
        st.warning("⚠️ Dati IBS non ancora disponibili.")
    else:
        st.sidebar.header("Filtri IBS")
        categorie_ibs = ["Tutti"] + sorted(df_ibs['Categoria_App'].unique().tolist())
        sel_cat_ibs = st.sidebar.selectbox("Filtra per Tipologia Editore:", categorie_ibs)
        
        solo_nuovi_ibs = st.sidebar.checkbox("🔥 Mostra solo le ultime uscite assolute")
        mostra_salvati_ibs = st.sidebar.checkbox("Visualizza solo i Salvati (IBS)")

        if (sel_cat_ibs != st.session_state.filtro_cat_ibs or solo_nuovi_ibs != st.session_state.filtro_nuovi_ibs or 
            mostra_salvati_ibs != st.session_state.filtro_salvati_ibs):
            st.session_state.limite_libri_ibs = 150
            st.session_state.filtro_cat_ibs = sel_cat_ibs
            st.session_state.filtro_nuovi_ibs = solo_nuovi_ibs
            st.session_state.filtro_salvati_ibs = mostra_salvati_ibs

        df_filtrato = df_ibs.copy()
        
        if mostra_salvati_ibs:
            df_filtrato = df_filtrato[df_filtrato['Link'].isin(st.session_state.libri_salvati.keys())]
        else:
            if sel_cat_ibs != "Tutti":
                df_filtrato = df_filtrato[df_filtrato['Categoria_App'] == sel_cat_ibs]
            if solo_nuovi_ibs and 'Nuovo' in df_filtrato.columns:
                df_filtrato = df_filtrato[df_filtrato['Nuovo'] == True]

        totale_libri = len(df_filtrato)
        st.markdown(f"**{totale_libri}** risultati trovati")
        st.markdown("---")

        df_mostrato = df_filtrato.iloc[:st.session_state.limite_libri_ibs]
        lista_libri = list(df_mostrato.iterrows())
        
        for i in range(0, len(lista_libri), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(lista_libri):
                    index, row = lista_libri[i + j]
                    link_univoco = row.get('Link', '')
                    is_saved = link_univoco in st.session_state.libri_salvati
                    
                    with cols[j]:
                        with st.container(border=True):
                            c_titolo, c_cuore = st.columns([5, 1])
                            with c_cuore:
                                st.button("❤️" if is_saved else "🤍", key=f"ibs_{index}", on_click=toggle_salvataggio, args=(link_univoco,), type="tertiary")
                            with c_titolo:
                                badge_nuovo = " <span style='color: #ff4b4b; font-size: 0.8em;'>🔥 NUOVO</span>" if row.get('Nuovo') == True else ""
                                st.markdown(f"<div style='height: 55px; padding-top: 4px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-weight: bold; font-size: 1.05em; text-align: left;'>{row['Titolo']}{badge_nuovo}</div>", unsafe_allow_html=True)
                            
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
                                    <span style='font-size: 0.9em;'>Editore: <b>{row.get('Editore', 'N/D')}</b> ({row.get('Anno', 'N/D')})</span><br>
                                    <span style='font-size: 0.8em; color: gray;'>Tipo: {row.get('Categoria_App', 'N/D')}</span>
                                </div>
                                """, unsafe_allow_html=True)

                            with c_note:
                                if is_saved:
                                    st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
                                    nota_attuale = st.session_state.libri_salvati.get(link_univoco, "").strip()
                                    icona_nota = "📒" if nota_attuale else "📝"
                                    with st.popover(icona_nota, help="Gestisci nota"):
                                        nuova_nota = st.text_area("Appunti:", value=nota_attuale, key=f"txt_{index}", height=120)
                                        if st.button("Salva", key=f"btn_nota_ibs_{index}", type="primary", use_container_width=True):
                                            st.session_state.libri_salvati[link_univoco] = nuova_nota
                                            aggiorna_nota_db(link_univoco, nuova_nota)
                                            st.toast("✅ Nota salvata!")
                                            st.rerun()
                            
                            desc = row.get('Descrizione', '')
                            if pd.notna(desc) and len(str(desc).strip()) > 0:
                                with st.expander("Trama / Descrizione"):
                                    st.write(desc)
                            
                            st.link_button("Vedi su IBS", link_univoco if pd.notna(link_univoco) else "#", type="primary", use_container_width=True)

        if st.session_state.limite_libri_ibs < totale_libri:
            st.markdown("---")
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                if st.button("⬇️ Carica altri libri", use_container_width=True, key="btn_load_ibs"):
                    st.session_state.limite_libri_ibs += 150
                    st.rerun()
