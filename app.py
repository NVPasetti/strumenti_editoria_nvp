import streamlit as st
import pandas as pd
import os
import datetime
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

# --- FUNZIONI DATABASE AMAZON (WISHLIST) ---
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
            pass

def aggiorna_nota_db(item_id, nota_testo):
    if supabase:
        try:
            supabase.table("wishlist").update({"nota": nota_testo}).eq("asin", item_id).execute()
        except Exception:
            pass

def rimuovi_preferito_db(item_id):
    if supabase:
        try:
            supabase.table("wishlist").delete().eq("asin", item_id).execute()
        except Exception:
            pass

def svuota_salvati_db():
    st.session_state.libri_salvati.clear()
    if supabase:
        try:
            supabase.table("wishlist").delete().neq("asin", "dummy_value").execute()
        except Exception:
            pass

# --- FUNZIONI DATABASE IBS (REMINDERS 30 GIORNI) ---
def carica_reminders_db():
    if supabase:
        try:
            risposta = supabase.table("reminders").select("*").execute()
            reminders_dict = {}
            for r in risposta.data:
                # Controllo rigoroso se l'autore è NULL (None) nel database
                autore_db = r.get("autore")
                if not autore_db or str(autore_db).strip().lower() == "none":
                    autore_db = "N/D"
                
                reminders_dict[r["id"]] = {
                    "titolo": r["titolo"], 
                    "autore": autore_db, 
                    "data_scadenza": r["data_scadenza"]
                }
            return reminders_dict
        except Exception:
            return {}
    return {}

def aggiungi_reminder_db(id_link, titolo, autore, data_scadenza):
    if supabase:
        try:
            supabase.table("reminders").insert({
                "id": id_link, 
                "titolo": titolo, 
                "autore": autore,
                "data_scadenza": data_scadenza
            }).execute()
        except Exception as e:
            st.toast("⚠️ Assicurati di aver aggiornato la tabella 'reminders' su Supabase!")

def rimuovi_reminder_db(id_link):
    if supabase:
        try:
            supabase.table("reminders").delete().eq("id", id_link).execute()
        except Exception:
            pass

# --- INIZIALIZZAZIONE MEMORIA GLOBALE ---
if 'libri_salvati' not in st.session_state:
    st.session_state.libri_salvati = carica_preferiti_db()

if 'reminders' not in st.session_state:
    st.session_state.reminders = carica_reminders_db()

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
    except Exception: return None

@st.cache_data(ttl=3600)
def load_estero_data(file_name):
    """Carica i dati dai file CSV del mercato internazionale"""
    if not os.path.exists(file_name): return None
    try:
        df = pd.read_csv(file_name)
        df['Titolo'] = df['Titolo'].fillna("Senza Titolo")
        df['Autore'] = df['Autore'].fillna("N/D")
        df['Editore'] = df['Editore'].fillna("N/D")
        
        # Gestione booleani sicura per la colonna 'Nuovo'
        if 'Nuovo' not in df.columns:
            df['Nuovo'] = False
        else:
            df['Nuovo'] = df['Nuovo'].astype(bool)
            
        # Gestione fallback per la categoria
        if 'Categoria' not in df.columns:
            df['Categoria'] = 'Novità'
            
        return df
    except Exception: return None

# --- FUNZIONE HELPER: GENERATORE GRIGLIA AMAZON ---
def mostra_griglia_libri(df_da_mostrare, limite_key, tab_id):
    totale_libri = len(df_da_mostrare)
    if totale_libri == 0:
        st.info("Nessun libro trovato in questa sezione con i filtri attuali.")
        return

    df_mostrato = df_da_mostrare.iloc[:st.session_state[limite_key]]
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
                            st.button("❤️" if is_saved else "🤍", key=f"amz_{asin}_{tab_id}", on_click=toggle_salvataggio, args=(asin,), type="tertiary")
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
                                    nuova_nota = st.text_area("Appunti:", value=nota_attuale, key=f"txt_{asin}_{tab_id}", height=120)
                                    if st.button("Salva", key=f"btn_nota_{asin}_{tab_id}", type="primary", use_container_width=True):
                                        st.session_state.libri_salvati[asin] = nuova_nota
                                        aggiorna_nota_db(asin, nuova_nota)
                                        st.toast("✅ Nota salvata!")
                                        st.rerun()

                        st.link_button("Vedi su Amazon", f"https://www.amazon.it/dp/{asin}" if pd.notna(asin) else "#", type="primary", use_container_width=True)

    if st.session_state[limite_key] < totale_libri:
        st.markdown("---")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("⬇️ Carica altri libri", use_container_width=True, key=f"btn_load_{tab_id}"):
                st.session_state[limite_key] += 150
                st.rerun()

# ==========================================
# SIDEBAR: NAVIGAZIONE PRINCIPALE
# ==========================================
st.sidebar.header("Strumenti")
piattaforma = st.sidebar.radio("Scegli servizio:", [
    "🆕 Novità saggistica (30 giorni)", 
    "🔍 Scouting Amazon",
    "🌍 Mercato Internazionale"
])
st.sidebar.markdown("---")

# ==========================================
# SEZIONE 1: NOVITÀ SAGGISTICA (IBS)
# ==========================================
if piattaforma == "🆕 Novità saggistica (30 giorni)":
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
        solo_nuovi = st.sidebar.checkbox("🆕 Mostra solo le nuove uscite")
        search_query = st.sidebar.text_input("🔍 Cerca libro o autore", help="Cerca in entrambe le liste")

        st.sidebar.subheader("Filtra Selezionati")
        editori_disponibili = sorted(df_vip['Editore'].unique())
        sel_editore = st.sidebar.multiselect("Seleziona Editore", editori_disponibili)

        st.sidebar.subheader("Ordina Selezionati")
        sort_mode = st.sidebar.selectbox(
            "Criterio di ordinamento:",
            ["Titolo (A-Z)", "Titolo (Z-A)", "Editore (A-Z)", "Editore (Z-A)"]
        )

        # --- WIDGET LATERALE: GESTIONE PROMEMORIA ---
        st.sidebar.markdown("---")
        num_reminders = len(st.session_state.reminders)
        
        with st.sidebar.expander(f"⏰ Libri in monitoraggio ({num_reminders})"):
            if num_reminders == 0:
                st.caption("Nessun libro in monitoraggio.")
            else:
                oggi = datetime.date.today()
                sorted_rems = sorted(st.session_state.reminders.items(), key=lambda x: x[1]['data_scadenza'])
                
                for r_id, r_data in sorted_rems:
                    try:
                        scadenza = datetime.date.fromisoformat(r_data["data_scadenza"])
                        giorni_rimasti = (scadenza - oggi).days
                    except:
                        giorni_rimasti = 99
                        scadenza = oggi
                        
                    if giorni_rimasti <= 0:
                        status = "🔴 Scaduto!"
                    elif giorni_rimasti <= 7:
                        status = f"🟠 -{giorni_rimasti} gg"
                    else:
                        status = f"🟢 -{giorni_rimasti} gg"
                        
                    st.markdown(f"**{r_data['titolo']}**<br><span style='font-size:0.85em; color:gray;'>di {r_data['autore']}</span>", unsafe_allow_html=True)
                    st.caption(f"{status} (Scadenza: {scadenza.strftime('%d/%m/%Y')})")
                    
                    if st.button("🗑️ Rimuovi", key=f"del_rem_{hash(r_id)}", use_container_width=True):
                        del st.session_state.reminders[r_id]
                        rimuovi_reminder_db(r_id)
                        st.rerun()
                    st.markdown("---")

        # --- APPLICAZIONE FILTRI ---
        if solo_nuovi:
            df_vip = df_vip[df_vip['Nuovo'] == True]
            df_altri = df_altri[df_altri['Nuovo'] == True]

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

        with tab1:
            if df_vip.empty:
                st.info("Nessun libro trovato con i filtri attuali.")
            for index, row in df_vip.iterrows():
                with st.container():
                    c1, c2 = st.columns([1, 5])
                    with c1:
                        url = row['Copertina']
                        if pd.notna(url) and str(url).startswith('http'):
                            st.image(str(url), width=120)
                        else:
                            st.text("🖼️ No Img")
                    with c2:
                        c2_testo, c2_btn = st.columns([4, 1])
                        with c2_testo:
                            badge = "🆕 " if row['Nuovo'] else ""
                            st.subheader(f"{badge}{row['Titolo']}")
                        
                        with c2_btn:
                            link = row.get('Link')
                            autore_libro = str(row.get('Autore', 'N/D'))
                            is_reminded = link in st.session_state.reminders
                            
                            btn_label = "✅ Seguito" if is_reminded else "🕒 Monitora"
                            btn_type = "primary" if is_reminded else "secondary"
                            
                            if st.button(btn_label, key=f"rem_vip_{index}", use_container_width=True, help="Ricordami di controllare le vendite tra 30 giorni"):
                                if is_reminded:
                                    del st.session_state.reminders[link]
                                    rimuovi_reminder_db(link)
                                else:
                                    if 'Data_Aggiunta' in row and pd.notna(row['Data_Aggiunta']):
                                        try:
                                            data_base = datetime.date.fromisoformat(str(row['Data_Aggiunta']))
                                        except:
                                            data_base = datetime.date.today()
                                    else:
                                        data_base = datetime.date.today()
                                        
                                    scadenza = (data_base + datetime.timedelta(days=30)).isoformat()
                                    st.session_state.reminders[link] = {
                                        "titolo": row['Titolo'], 
                                        "autore": autore_libro,
                                        "data_scadenza": scadenza
                                    }
                                    aggiungi_reminder_db(link, row['Titolo'], autore_libro, scadenza)
                                st.rerun()

                        st.markdown(f"**{autore_libro}** | *{row.get('Editore', 'N/D')}* ({row.get('Anno', '')})")
                        desc = str(row.get('Descrizione', ''))
                        if len(desc) > 10 and desc.lower() != "nan":
                            with st.expander("📖 Leggi sinossi"):
                                st.write(desc)
                        if pd.notna(link) and str(link).startswith('http'):
                            st.markdown(f"[➡️ Vedi su IBS]({link})")
                    st.divider()

        with tab2:
            st.caption("Libri di altri editori (lista standard).")
            if df_altri.empty:
                st.info("Nessun libro in questa categoria.")
            for index, row in df_altri.iterrows():
                with st.container():
                    c_img, c_info, c_btn2 = st.columns([0.5, 4, 1])
                    with c_img:
                        url = row['Copertina']
                        if pd.notna(url) and str(url).startswith('http'):
                            st.image(str(url), width=60)
                    with c_info:
                        badge = "🆕 " if row['Nuovo'] else ""
                        autore_libro = str(row.get('Autore', 'N/D'))
                        st.markdown(f"{badge}**{row['Titolo']}**")
                        st.markdown(f"{autore_libro} - *{row.get('Editore', 'N/D')}*")
                        link = row.get('Link')
                        if pd.notna(link) and str(link).startswith('http'):
                            st.markdown(f"[Link]({link})")
                    
                    with c_btn2:
                        is_reminded2 = link in st.session_state.reminders
                        btn_label2 = "✅ Seguito" if is_reminded2 else "🕒 Monitora"
                        btn_type2 = "primary" if is_reminded2 else "secondary"
                        if st.button(btn_label2, key=f"rem_altri_{index}", use_container_width=True):
                            if is_reminded2:
                                del st.session_state.reminders[link]
                                rimuovi_reminder_db(link)
                            else:
                                if 'Data_Aggiunta' in row and pd.notna(row['Data_Aggiunta']):
                                    try:
                                        data_base = datetime.date.fromisoformat(str(row['Data_Aggiunta']))
                                    except:
                                        data_base = datetime.date.today()
                                else:
                                    data_base = datetime.date.today()
                                    
                                scadenza = (data_base + datetime.timedelta(days=30)).isoformat()
                                st.session_state.reminders[link] = {
                                    "titolo": row['Titolo'], 
                                    "autore": autore_libro,
                                    "data_scadenza": scadenza
                                }
                                aggiungi_reminder_db(link, row['Titolo'], autore_libro, scadenza)
                        st.rerun()
                    st.markdown("---")

# ==========================================
# SEZIONE 2: SCOUTING AMAZON
# ==========================================
elif piattaforma == "🔍 Scouting Amazon":
    st.title("I più recensiti - Amazon")
    st.caption("Esplora i libri più popolari, salvali e aggiungi le tue note.")

    num_salvati = len(st.session_state.libri_salvati)
    st.sidebar.metric(label="❤️ Appunti & Salvati", value=f"{num_salvati} libri")
    
    mostra_salvati_amz = st.sidebar.checkbox("Visualizza solo i Salvati")
    
    if num_salvati > 0:
        with st.sidebar.popover("🗑️ Svuota Salvati", use_container_width=True):
            st.markdown("⚠️ **Sei sicuro?**")
            st.caption("Questa azione eliminerà tutti i libri salvati e i tuoi appunti in modo definitivo.")
            if st.button("Sì, svuota tutto", type="primary", use_container_width=True):
                svuota_salvati_db()
                st.rerun()

    st.sidebar.markdown("---")

    if 'limite_libri_amz_top' not in st.session_state: st.session_state.limite_libri_amz_top = 150
    if 'limite_libri_amz_pot' not in st.session_state: st.session_state.limite_libri_amz_pot = 150
    if 'filtro_cat_amz' not in st.session_state: st.session_state.filtro_cat_amz = "Tutte"
    if 'filtro_rec_amz' not in st.session_state: st.session_state.filtro_rec_amz = 35 
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
        min_rec_amz = st.sidebar.slider("Filtra per popolarità (min. recensioni):", 0, max_recensioni, value=35, step=10)
        
        ord_amz = st.sidebar.radio("Ordina per recensioni:", ["Decrescente (Più recensioni)", "Crescente (Meno recensioni)"])
        is_ascending_amz = True if ord_amz == "Crescente (Meno recensioni)" else False

        if (sel_cat_amz != st.session_state.filtro_cat_amz or min_rec_amz != st.session_state.filtro_rec_amz or 
            ord_amz != st.session_state.filtro_ord_amz or mostra_salvati_amz != st.session_state.filtro_salvati_amz):
            st.session_state.limite_libri_amz_top = 150
            st.session_state.limite_libri_amz_pot = 150
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

        df_top = df_filtrato[df_filtrato['Recensioni'] >= 60]
        df_potenziale = df_filtrato[df_filtrato['Recensioni'] < 60]

        tab_top, tab_potenziale = st.tabs([f"🌟 Più recensioni ({len(df_top)})", f"🚀 Libri con potenziale ({len(df_potenziale)})"])

        with tab_top:
            mostra_griglia_libri(df_top, 'limite_libri_amz_top', 'top')

        with tab_potenziale:
            st.caption("Libri recenti con un numero di recensioni tra 35 e 59.")
            mostra_griglia_libri(df_potenziale, 'limite_libri_amz_pot', 'pot')

# ==========================================
# SEZIONE 3: MERCATO INTERNAZIONALE
# ==========================================
elif piattaforma == "🌍 Mercato Internazionale":
    st.title("🌍 Scouting Internazionale")
    st.caption("Esplora le novità e i bestseller dai principali mercati esteri.")

    # --- SELETTORE MERCATO ---
    mercato_scelto = st.radio(
        "Seleziona il mercato da analizzare:", 
        ["🇺🇸 USA (Top 5 Editori)", "🇫🇷 Francia (Decitre)"],
        horizontal=True
    )
    
    st.markdown("---")

    # Ora legge il nuovo super-database per gli USA!
    file_estero = "dati_internazionali.csv" if "USA" in mercato_scelto else "dati_decitre_scraper.csv"
    df_estero = load_estero_data(file_estero)

    if df_estero is None:
        st.warning(f"⚠️ Dati per {mercato_scelto} non trovati. Assicurati che lo scraper abbia generato il file '{file_estero}'.")
    else:
        # --- FILTRI SIDEBAR ---
        st.sidebar.header("Filtri Internazionali")
        solo_nuovi_estero = st.sidebar.checkbox("🆕 Mostra solo i nuovi arrivi")
        search_estero = st.sidebar.text_input("🔍 Cerca titolo, autore o editore")
        
        if solo_nuovi_estero:
            df_estero = df_estero[df_estero['Nuovo'] == True]
            
        if search_estero:
            mask = df_estero.astype(str).apply(lambda x: x.str.contains(search_estero, case=False)).any(axis=1)
            df_estero = df_estero[mask]

        df_novita = df_estero[df_estero['Categoria'].str.contains('Novità', case=False, na=False)]
        df_bestseller = df_estero[~df_estero['Categoria'].str.contains('Novità', case=False, na=False)]

        tab_novita, tab_bestseller = st.tabs([f"🆕 Novità ({len(df_novita)})", f"🏆 Bestseller ({len(df_bestseller)})"])

        def renderizza_lista_estera(dataframe):
            if dataframe.empty:
                st.info("Nessun libro da mostrare con i filtri attuali.")
                return
                
            for index, row in dataframe.iterrows():
                with st.container(border=True):
                    # Struttura delle colonne per allineare l'immagine e il blocco principale
                    c_img, c_main = st.columns([1, 6])
                    
                    with c_img:
                        url = row['Copertina']
                        if pd.notna(url) and str(url).startswith('http'):
                            st.image(str(url), use_container_width=True)
                        else:
                            st.markdown("<div style='text-align:center; padding: 20px; background:#f0f2f6; border-radius:5px;'>No Img</div>", unsafe_allow_html=True)
                            
                    with c_main:
                        # Colonna principale divisa tra informazioni e pulsanti
                        c_testo, c_azioni = st.columns([5, 1.5])
                        
                        with c_testo:
                            badge = "🆕 " if row['Nuovo'] else ""
                            st.markdown(f"#### {badge}{row['Titolo']}")
                        
                        with c_azioni:
                            link = row.get('Link')
                            if pd.notna(link) and str(link).startswith('http'):
                                st.link_button("🌐 Apri Sito", link, use_container_width=True)
                                
                        # Autore ed Editore
                        st.markdown(f"**{row['Autore']}** | *{row['Editore']}*")
                        
                        # Sinossi a comparsa (larga quanto il blocco principale c_main)
                        desc = str(row.get('Descrizione', ''))
                        if len(desc) > 15 and desc.lower() != "nan" and desc.lower() != "n/d":
                            with st.expander("📖 Leggi sinossi originale"):
                                st.write(desc)

        with tab_novita:
            renderizza_lista_estera(df_novita)
            
        with tab_bestseller:
            renderizza_lista_estera(df_bestseller)
