import sys
import time
import re
import os
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
import json
import urllib.request
import urllib.error

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

BASE_URL = "https://www.davidemaggio.it/programmi-tv"
CSV_FILENAME = "ospiti_tv.csv"

# --- CONFIGURAZIONE DINAMICA GEMINI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY") 
ACTIVE_MODEL = None

if GEMINI_KEY:
    print("✅ Chiave Gemini rilevata! Interrogo il server per trovare i modelli disponibili...")
    try:
        url_models = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        req = urllib.request.Request(url_models, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            models_data = json.loads(response.read().decode())
            available_models = [m['name'] for m in models_data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            preferiti = [
                'models/gemini-3.1-flash-lite', 
                'models/gemini-2.0-flash', 
                'models/gemini-1.5-flash',
                'models/gemini-1.5-flash-latest',
                'models/gemini-1.5-flash-8b',
                'models/gemini-pro'
            ]
            
            for pref in preferiti:
                if pref in available_models:
                    ACTIVE_MODEL = pref
                    break
            
            if not ACTIVE_MODEL:
                if 'models/gemini-3.1-flash-lite' not in available_models:
                    ACTIVE_MODEL = 'models/gemini-3.1-flash-lite'
                elif available_models:
                    ACTIVE_MODEL = available_models[0]
                
        if ACTIVE_MODEL:
            print(f"✅ Modello selezionato: {ACTIVE_MODEL}")
        else:
            print("❌ Nessun modello compatibile trovato per questa API key.")
            
    except Exception as e:
        print(f"⚠️ Impossibile verificare i modelli dal server ({e}). Forzo il 3.1 Flash Lite.")
        ACTIVE_MODEL = "models/gemini-3.1-flash-lite"
else:
    print("❌ ATTENZIONE: Chiave Gemini (GEMINI_API_KEY) NON TROVATA!")

def estrai_ospiti_ai(titolo, descrizione, is_retry=False):
    """Chiede a Gemini di estrarre ESCLUSIVAMENTE gli ospiti invitati."""
    if not GEMINI_KEY or not ACTIVE_MODEL:
        return "N/D"
    
    prompt = f"""Leggi questo articolo su un programma TV. Il tuo unico compito è estrarre ESCLUSIVAMENTE i nomi degli OSPITI INVITATI in studio o in collegamento.
    REGOLE RIGIDE:
    1. NON includere i conduttori fissi del programma.
    2. NON includere persone di cui si parlerà nella puntata ma che non saranno fisicamente presenti come ospiti.
    3. NON includere registi, autori o personaggi secondari non invitati come ospiti.
    4. Restituisci SOLO l'elenco dei nomi e cognomi degli ospiti separati da virgola. Non aggiungere altre parole.
    5. Se nell'articolo non c'è nessun ospite annunciato secondo queste regole, scrivi esattamente 'N/D'.
    
    Titolo: {titolo}
    Testo: {descrizione}"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{ACTIVE_MODEL}:generateContent?key={GEMINI_KEY}"
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    
    try:
        time.sleep(5) 
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            try:
                res = result['candidates'][0]['content']['parts'][0]['text'].strip()
                res = re.sub(r'^(?:sono|saranno|c\'è|ci sarà|ci sono|ospiti:)\s+', '', res, flags=re.IGNORECASE).strip()
                res = res.strip("*-.\n\t ")
                return res.capitalize() if res else "N/D"
            except (KeyError, IndexError):
                return "N/D"
                
    except urllib.error.HTTPError as e:
        if e.code == 429 and not is_retry:
            print(f"⏳ Limite di velocità raggiunto (429) su '{titolo[:20]}'. Aspetto 30 secondi e riprovo...")
            time.sleep(30)
            return estrai_ospiti_ai(titolo, descrizione, is_retry=True)
            
        return "N/D"
    except Exception as e:
        return "N/D"

def get_stealth_session():
    session = requests.Session(impersonate="chrome120")
    session.headers.update({"Accept-Language": "it-IT,it;q=0.9", "Referer": "https://www.google.it/"})
    return session

def get_date_from_article(session, url):
    try:
        time.sleep(0.5)
        res = session.get(url)
        if res.status_code == 200:
            inner_soup = BeautifulSoup(res.text, 'html.parser')
            date_tag = inner_soup.find('p', class_='font-open text-[0.75rem] font-semibold leading-none text-gray-200')
            if date_tag:
                return date_tag.get_text(strip=True).split('-')[0].strip()
    except: pass
    return "N/D"

# --- NUOVA FUNZIONE: OTTO E MEZZO ---
def scrape_otto_e_mezzo(session):
    print("\n📺 Controllo ultima puntata di Otto e Mezzo...")
    url_base = "https://www.la7.it/otto-e-mezzo/rivedila7"
    try:
        res = session.get(url_base)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        marker_ultima = soup.find('div', class_=re.compile(r'scritta_ultima'))
        if not marker_ultima: return None
            
        card = marker_ultima.find_parent('div', class_=re.compile(r'holder-bg'))
        a_tag = marker_ultima.find_parent('a')
        
        link_puntata = "N/D"
        data_puntata = "N/D"
        
        if a_tag and a_tag.get('href'):
            link_puntata = a_tag.get('href')
            if not link_puntata.startswith('http'): link_puntata = "https://www.la7.it" + link_puntata
            match_data = re.search(r'(\d{2}-\d{2}-\d{4})', link_puntata)
            if match_data: data_puntata = match_data.group(1).replace('-', '/')
                
        immagine = "N/D"
        if card and card.get('data-background-image'):
            img_raw = card.get('data-background-image')
            immagine = ("https:" + img_raw) if img_raw.startswith('//') else img_raw
            
        ospiti = "N/D"
        occhiello = card.find('div', class_=re.compile(r'occhiello')) if card else None
        if occhiello:
            testo_raw = occhiello.get_text(strip=True)
            ospiti = re.sub(r'(?i)^Ospiti(?: di Lilli Gruber)?\s*:\s*', '', testo_raw).strip()
            
        return {
            "Data": data_puntata,
            "Titolo": "Otto e Mezzo",
            "Descrizione_Completa": "", 
            "Ospiti": ospiti,
            "Immagine": immagine,
            "Link": link_puntata
        }
    except Exception as e:
        print(f"❌ Errore Otto e Mezzo: {e}")
        return None


def scrape_ospiti_tv():
    print("📺 Avvio scraper Palinsesto TV (La7 + DavideMaggio)...")
    session = get_stealth_session()
    
    df_old = pd.DataFrame()
    link_visti = set()
    
    if os.path.exists(CSV_FILENAME):
        try:
            if os.path.getsize(CSV_FILENAME) > 0:
                df_old = pd.read_csv(CSV_FILENAME)
                if not df_old.empty and 'Link' in df_old.columns:
                    link_visti = set(df_old['Link'].tolist())
            else:
                print("⚠️ Attenzione: Il file CSV esiste ma è a 0 byte. Lo ignoro e riparto da zero.")
        except Exception as e:
            print(f"⚠️ Impossibile leggere il file vecchio ({e}). Riparto da zero.")
            df_old = pd.DataFrame()

    nuovi_dati = []
    
    # --- 1. ESECUZIONE OTTO E MEZZO ---
    otto_data = scrape_otto_e_mezzo(session)
    if otto_data and otto_data["Link"] not in link_visti:
        nuovi_dati.append(otto_data)
        link_visti.add(otto_data["Link"])
        print("✅ Otto e Mezzo aggiunto alle novità.")
    elif otto_data:
        print("🛑 L'ultima puntata di Otto e Mezzo è già presente nel database.")

    # --- 2. ESECUZIONE DAVIDEMAGGIO ---
    stop_scraping = False
    page = 1

    while not stop_scraping:
        url = f"{BASE_URL}/page/{page}" if page > 1 else BASE_URL
        print(f"\n📄 Analizzo pagina {page} di DavideMaggio...")
        
        try:
            response = session.get(url)
            if response.status_code != 200: break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tendenza = soup.find(id='ora-in-tendenza')
            if tendenza: tendenza.decompose()
            paginazione = soup.find('ul', class_=re.compile(r'page-numbers'))
            if paginazione:
                for tag_sotto in paginazione.find_all_next(['h2', 'h3', 'h4', 'div', 'p']):
                    tag_sotto.decompose()

            titoli_tags = soup.find_all(['h2', 'h3', 'h4'], class_=re.compile(r'font-(?:extra)?bold'))
            if not titoli_tags: break

            for tag in titoli_tags:
                a_tag = tag.find('a')
                if not a_tag: continue
                link = a_tag['href']
                
                if "/videogallery/" in link.lower(): continue
                
                if link in link_visti:
                    print("🛑 Trovata notizia già presente nel database. Mi fermo qui.")
                    stop_scraping = True
                    break
                
                link_visti.add(link)
                titolo = a_tag.get_text(strip=True)
                print(f"✨ Estrazione AI per: {titolo[:40]}...")

                img_url = "N/D"
                tutti_link_uguali = soup.find_all('a', href=link)
                for a_img in tutti_link_uguali:
                    img_tag = a_img.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or "N/D"
                        if img_url != "N/D": break

                desc_div = tag.find_next('div', class_=re.compile(r'text-gray-100'))
                descrizione = desc_div.get_text(separator=' ', strip=True) if desc_div and desc_div.find_previous(['h2', 'h3', 'h4']) == tag else "N/D"

                meta_p = tag.find_next('p', class_=re.compile(r'text-\[#A0A0A0\]'))
                data = "N/D"
                if meta_p and meta_p.find_previous(['h2', 'h3', 'h4']) == tag:
                    spans = meta_p.find_all('span')
                    if len(spans) >= 2: data = spans[1].get_text(strip=True)

                if data == "N/D":
                    data = get_date_from_article(session, link)

                ospiti_ai = estrai_ospiti_ai(titolo, descrizione)

                nuovi_dati.append({
                    "Data": data,
                    "Titolo": titolo,
                    "Descrizione_Completa": descrizione,
                    "Ospiti": ospiti_ai,
                    "Immagine": img_url,
                    "Link": link
                })
            
            if stop_scraping: break
            page += 1
            if page > 5: break
            
        except Exception as e:
            print(f"❌ Errore durante l'analisi: {e}")
            break

    if nuovi_dati:
        df_new = pd.DataFrame(nuovi_dati)
        df_final = pd.concat([df_new, df_old], ignore_index=True).drop_duplicates(subset=['Link'])
        df_final.to_csv(CSV_FILENAME, index=False, encoding='utf-8')
        print(f"✅ Database aggiornato: +{len(df_new)} nuove notizie inserite.")
    else:
        print("☕ Nessuna nuova notizia da aggiungere. Il file CSV è già aggiornato.")

if __name__ == "__main__":
    scrape_ospiti_tv()
