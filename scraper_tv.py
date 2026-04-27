import sys
import time
import re
import os
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
import google.generativeai as genai

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

BASE_URL = "https://www.davidemaggio.it/programmi-tv"
CSV_FILENAME = "ospiti_tv.csv"

# --- CONFIGURAZIONE GEMINI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY") 
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def estrai_ospiti_ai(titolo, descrizione):
    """Chiede a Gemini di estrarre SOLO i nomi degli ospiti"""
    if not model:
        return "N/D"
    
    prompt = f"""Analizza questo testo di un programma TV ed estrai SOLO i nomi propri delle persone (ospiti, conduttori o protagonisti).
    Restituisci solo l'elenco dei nomi separati da virgola. Non scrivere frasi intere.
    Se non trovi nomi di persone, scrivi esattamente 'N/D'.
    Titolo: {titolo}
    Testo: {descrizione}"""
    
    try:
        time.sleep(1.5) # Pausa per non superare il limite di richieste gratuite
        response = model.generate_content(prompt)
        res = response.text.strip()
        # Pulizia per rimuovere "Ci sono", "Saranno ospiti" etc se Gemini li ha messi per sbaglio
        res = re.sub(r'^(?:sono|saranno|c\'è|ci sarà|ci sono|ospiti:)\s+', '', res, flags=re.IGNORECASE).strip()
        return res.capitalize() if res else "N/D"
    except Exception:
        return "N/D"

def get_stealth_session():
    session = requests.Session(impersonate="chrome120")
    session.headers.update({"Accept-Language": "it-IT,it;q=0.9", "Referer": "https://www.google.it/"})
    return session

def get_date_from_article(session, url):
    """Recupera la data mancante dall'interno dell'articolo tagliando l'orario"""
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

def scrape_ospiti_tv():
    print("📺 Avvio scraper incrementale DavideMaggio.it con AI...")
    session = get_stealth_session()
    
    # --- FIX: GESTIONE FILE VUOTI (EmptyDataError) ---
    df_old = pd.DataFrame()
    link_visti = set()
    
    if os.path.exists(CSV_FILENAME) and os.path.getsize(CSV_FILENAME) > 0:
        try:
            df_old = pd.read_csv(CSV_FILENAME)
            if 'Link' in df_old.columns:
                link_visti = set(df_old['Link'].tolist())
        except pd.errors.EmptyDataError:
            print("⚠️ File CSV vuoto trovato, lo ricreo da zero.")
            pass
    # --------------------------------------------------

    nuovi_dati = []
    stop_scraping = False
    page = 1

    while not stop_scraping:
        url = f"{BASE_URL}/page/{page}" if page > 1 else BASE_URL
        print(f"\n📄 Analizzo pagina {page}...")
        
        try:
            response = session.get(url)
            if response.status_code != 200: break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # --- PULIZIA HTML ---
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
                
                # SE IL LINK ESISTE GIA', FERMA LO SCRAPER!
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

                # Chiamata a Gemini per gli ospiti
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
            if page > 10: break # Massimo 10 pagine per sicurezza
            
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
