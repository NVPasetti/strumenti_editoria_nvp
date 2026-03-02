import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Scouting Amazon", layout="wide")

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

def salva_preferito_db(asin):
    if supabase:
        try:
            supabase.table("wishlist").insert({"asin": asin, "nota": ""}).execute()
        except Exception:
            try:
                supabase.table("wishlist").insert({"asin": asin}).execute()
            except Exception as e:
                st.toast(f"⚠️ Errore salvataggio nel DB: {e}")

def aggiorna_nota_db(asin, nota_testo):
    if supabase:
        try:
            supabase.table("wishlist").update({"nota": nota_testo}).eq("asin", asin).execute()
        except Exception as e:
            st.toast("⚠️ Errore: assicurati di aver aggiunto la colonna 'nota' su Supabase!")

def rimuovi_preferito_db(asin):
    if supabase:
        try:
            supabase.table("wishlist").delete().eq("asin", asin).execute()
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

if 'limite_libri' not in st.session_state: st.session_state.limite_libri = 150
if 'filtro_cat' not in st.session_state: st.session_state.filtro_cat = "Tutte"
if 'filtro_rec' not in st.session_state: st.session_state.filtro_rec = 60
if 'filtro_ord' not in st.session_state: st.session_state.filtro_ord = "Decrescente (Più recensioni)"
if 'filtro_salvati' not in st.session_state: st.session_state.filtro_salvati = False

def toggle_salvataggio(asin):
    if asin in st.session_state.libri_salvati:
        del st.session_state.libri_salvati[asin]
        rimuovi_preferito_db(asin)
    else:
        st.session_state.libri_salvati[asin] = ""
        salva_preferito_db(asin)

# --- FUNZIONE DI CARICAMENTO DATI ---
@st.cache_data(ttl=3600)
def load_amazon_data(file_name):
    if not os.path.exists(file_name):
        return None
    try:
        df = pd.read_csv(file_name)
        df['Titolo'] = df['Titolo'].fillna("Senza Titolo")
        df['Autore'] = df['Autore'].fillna("N/D")
        
        df = df.drop_duplicates(subset=['ASIN'])
        df = df.drop_duplicates(subset=['Titolo'])
        
        return df
    except Exception:
        return None

# --- INTESTAZIONE SHOP ---
st.title("I più venduti - Amazon")
st.caption("Esplora i libri con più recensioni, aggiungili ai Salvati e scrivi i tuoi appunti personali.")

file_amazon = "amazon_libri_multicat.csv"
df_amz = load_amazon_data(file_amazon)

if df_amz is None:
    st.warning("⚠️ Dati Amazon non ancora disponibili. Attendi che lo scraper generi il file CSV.")
else:
    # ==========================================
    # SIDEBAR: FILTRI E SALVATI
    # ==========================================
    st.sidebar.header("Menu")
    
    categorie_disponibili = ["Tutte"] + sorted(df_amz['Categoria'].unique().tolist())
    sel_cat_amz = st.sidebar.selectbox("Reparto:", categorie_disponibili)
    
    max_recensioni = int(df_amz['Recensioni'].max()) if not df_amz.empty else 1000
    min_recensioni_filtro = st.sidebar.slider(
        "Filtra per popolarità (min. recensioni):", 
        min_value=0, max_value=max_recensioni, value=60, step=50
    )
    
    ordinamento = st.sidebar.radio(
        "Ordina per recensioni:",
        options=["Decrescente (Più recensioni)", "Crescente (Meno recensioni)"]
    )
    is_ascending = True if ordinamento == "Crescente (Meno recensioni)" else False

    st.sidebar.markdown("---")
    
    num_salvati = len(st.session_state.libri_salvati)
    st.sidebar.metric(label="❤️ Salvati", value=f"{num_salvati} libri")
    
    mostra_solo_salvati = st.sidebar.checkbox("Visualizza solo i Salvati")
    
    if num_salvati > 0:
        st.sidebar.button("🗑️ Svuota Salvati", on_click=svuota_salvati_db, type="secondary")

    # ==========================================
    # CONTROLLO CAMBIO FILTRI
    # ==========================================
    if (sel_cat_amz != st.session_state.filtro_cat or 
        min_recensioni_filtro != st.session_state.filtro_rec or 
        ordinamento != st.session_state.filtro_ord or
        mostra_solo_salvati != st.session_state.filtro_salvati):
        
        st.session_state.limite_libri = 150
        st.session_state.filtro_cat = sel_cat_amz
        st.session_state.filtro_rec = min_recensioni_filtro
        st.session_state.filtro_ord = ordinamento
        st.session_state.filtro_salvati = mostra_solo_salvati

    # ==========================================
    # ELABORAZIONE DATI (FILTRI)
    # ==========================================
    df_filtrato = df_amz.copy()
    
    if mostra_solo_salvati:
        df_filtrato = df_filtrato[df_filtrato['ASIN'].isin(st.session_state.libri_salvati.keys())]
    else:
        if sel_cat_amz != "Tutte":
            df_filtrato = df_filtrato[df_filtrato['Categoria'] == sel_cat_amz]
        df_filtrato = df_filtrato[df_filtrato['Recensioni'] >= min_recensioni_filtro]
        
    df_filtrato = df_filtrato.sort_values(by='Recensioni', ascending=is_ascending)

    totale_libri = len(df_filtrato)
    st.markdown(f"**{totale_libri}** risultati trovati")
    st.markdown("---")

    df_mostrato = df_filtrato.iloc[:st.session_state.limite_libri]

    # ==========================================
    # RENDERING A GRIGLIA ALLINEATA
    # ==========================================
    lista_libri = list(df_mostrato.iterrows())
    
    for i in range(0, len(lista_libri), 3):
        cols = st.columns(3)
        
        for j in range(3):
            if i + j < len(lista_libri):
                index, row_data = lista_libri[i + j]
                asin = row_data.get('ASIN', '')
                
                is_saved = asin in st.session_state.libri_salvati
                
                with cols[j]:
                    with st.container(border=True):
                        
                        # 1. RIGA TITOLO E CUORE
                        c_titolo, c_cuore = st.columns([5, 1])
                        with c_cuore:
                            st.button(
                                "❤️" if is_saved else "🤍", 
                                key=f"btn_{asin}", 
                                on_click=toggle_salvataggio, 
                                args=(asin,),
                                help="Aggiungi o rimuovi dai Salvati",
                                type="tertiary"
                            )
                        with c_titolo:
                            titolo_html = f"""
                            <div style='height: 55px; padding-top: 4px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-weight: bold; font-size: 1.05em; text-align: left;'>
                                {row_data['Titolo']}
                            </div>
                            """
                            st.markdown(titolo_html, unsafe_allow_html=True)
                        
                        # 2. IMMAGINE
                        url = row_data['Copertina']
                        if pd.notna(url) and str(url).startswith('http'):
                            img_html = f"""
                            <div style='height: 450px; display: flex; justify-content: center; align-items: center; margin-bottom: 15px;'>
                                <img src='{url}' style='width: 100%; height: 100%; object-fit: contain;'>
                            </div>
                            """
                        else:
                            img_html = f"<div style='height: 450px; display: flex; justify-content: center; align-items: center; margin-bottom: 15px; background-color: #f8f9fa; border-radius: 5px;'>🖼️ <i>Nessuna Immagine</i></div>"
                        
                        st.markdown(img_html, unsafe_allow_html=True)
                        
                        # 3. INFO E METADATI + ICONA NOTE
                        c_info, c_note = st.columns([5, 1])
                        
                        with c_info:
                            autore_intero = str(row_data.get('Autore', 'N/D'))
                            autore_corto = autore_intero[:35] + "..." if len(autore_intero) > 35 else autore_intero
                            
                            info_html = f"""
                            <div style='height: 80px; line-height: 1.4; text-align: left;'>
                                <span style='font-size: 0.85em; color: gray;'>Di: <b>{autore_corto}</b></span><br>
                                <span style='font-size: 0.9em;'>⭐⭐⭐⭐⭐ ({int(row_data['Recensioni'])})</span><br>
                                <span style='font-size: 0.8em; color: gray;'>Reparto: {row_data.get('Categoria', 'N/D')}</span>
                            </div>
                            """
                            st.markdown(info_html, unsafe_allow_html=True)

                        with c_note:
                            if is_saved:
                                st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
                                
                                # Logica icona e testo dinamici
                                nota_attuale = st.session_state.libri_salvati.get(asin, "").strip()
                                icona_nota = "📒" if nota_attuale else "📝"
                                testo_aiuto = "Leggi/Modifica nota" if nota_attuale else "Aggiungi una nota personale"
                                
                                with st.popover(icona_nota, help=testo_aiuto):
                                    nuova_nota = st.text_area("I tuoi appunti per questo libro:", value=nota_attuale, key=f"txt_{asin}", height=120)
                                    
                                    if st.button("Salva Nota", key=f"btn_nota_{asin}", type="primary", use_container_width=True):
                                        st.session_state.libri_salvati[asin] = nuova_nota
                                        aggiorna_nota_db(asin, nuova_nota)
                                        st.toast("✅ Nota salvata con successo!")
                                        st.rerun() # Ricarica istantaneamente l'icona

                        # 4. PULSANTE AMAZON
                        amz_link = f"https://www.amazon.it/dp/{asin}" if pd.notna(asin) else "#"
                        st.link_button("Vedi su Amazon", amz_link, type="primary", use_container_width=True)

    # ==========================================
    # PULSANTE "CARICA ALTRI" IN FONDO
    # ==========================================
    if st.session_state.limite_libri < totale_libri:
        st.markdown("---")
        col_vuota1, col_bottone, col_vuota2 = st.columns([1, 2, 1])
        with col_bottone:
            if st.button("⬇️ Carica altri libri", use_container_width=True):
                st.session_state.limite_libri += 150
                st.rerun()
                            
