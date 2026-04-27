import sys
import time
import re
import os
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
import google.generativeai as genai

# --- CONFIGURAZIONE GEMINI ---
# In locale usa la tua chiave, su GitHub Actions la prenderemo dai Secrets
GEMINI_KEY = os.getenv("GEMINI_API_KEY") 
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def estrai_ospiti_ai(titolo, descrizione):
    """Chiede a Gemini di estrarre solo i nomi dei protagonisti/ospiti"""
    if not model:
        return "AI non configurata"
    
    prompt = f"""
    Analizza questo testo di un programma TV ed estrai SOLO i nomi delle persone (ospiti, conduttori o protagonisti).
    Restituisci solo l'elenco dei nomi separati da virgola. 
    Non aggiungere commenti, non scrivere frasi intere.
    Se non trovi nomi di persone, scrivi 'N/D'.
    
    Titolo: {titolo}
    Testo: {descrizione}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Errore AI"

# --- RESTO DELLO SCRAPER (BASE PRECEDENTE) ---
URL_TARGET = "https://www.davidemaggio.it/programmi-tv"
CSV_FILENAME = "ospiti_tv.csv"

def get_stealth_session():
    session = requests.Session(impersonate="chrome120")
    session.headers.update({"Accept-Language": "it-IT,it;q=0.9", "Referer": "https://www.google.it/"})
    return session

def get_date_from_article(session, url):
    try:
        res = session.get(url)
        if res.status_code == 200:
            inner_soup = BeautifulSoup(res.text, 'html.parser')
            date_tag = inner_soup.find('p', class_='font-open text-[0.75rem] font-semibold leading-none text-gray-200')
            if date_tag:
                return date_tag.get_text(strip=True).split('-')[0].strip()
    except: pass
    return "N/D"

def scrape_ospiti_tv():
    print("📺 Avvio scraper con supporto AI...")
    session = get_stealth_session()
    
    if os.path.exists(CSV_FILENAME):
        df_old = pd.read_csv(CSV_FILENAME)
        link_visti = set(df_old['Link'].tolist())
    else:
        df_old = pd.DataFrame()
        link_visti = set()

    response = session.get(URL_TARGET)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Pulizia footer come concordato
    paginazione = soup.find('ul', class_=re.compile(r'page-numbers'))
    if paginazione:
        for tag_sotto in paginazione.find_all_next(['h2', 'h3', 'h4', 'div', 'p']):
            tag_sotto.decompose()

    nuovi_dati = []
    titoli_tags = soup.find_all(['h2', 'h3', 'h4'], class_=re.compile(r'font-(?:extra)?bold'))

    for tag in titoli_tags:
        a_tag = tag.find('a')
        if not a_tag: continue
        link = a_tag['href']
        if "/videogallery/" in link.lower() or link in link_visti: continue

        titolo = a_tag.get_text(strip=True)
        print(f"✨ Analizzo con AI: {titolo[:40]}...")

        # Immagine
        img_url = "N/D"
        img_tag = soup.find('a', href=link).find('img') if soup.find('a', href=link) else None
        if img_tag: img_url = img_tag.get('src') or img_tag.get('data-src') or "N/D"

        # Descrizione
        desc_div = tag.find_next('div', class_=re.compile(r'text-gray-100'))
        descrizione = desc_div.get_text(separator=' ', strip=True) if desc_div else "N/D"

        # Data
        meta_p = tag.find_next('p', class_=re.compile(r'text-\[#A0A0A0\]'))
        data = "N/D"
        if meta_p and meta_p.find_previous(['h2', 'h3', 'h4']) == tag:
            spans = meta_p.find_all('span')
            if len(spans) >= 2: data = spans[1].get_text(strip=True)
        if data == "N/D": data = get_date_from_article(session, link)

        # 🎯 CHIAMATA A GEMINI
        ospiti_ai = estrai_ospiti_ai(titolo, descrizione)

        nuovi_dati.append({
            "Data": data,
            "Titolo": titolo,
            "Ospiti": ospiti_ai, # Il nuovo campo AI
            "Descrizione_Completa": descrizione,
            "Immagine": img_url,
            "Link": link
        })

    if nuovi_dati:
        df_new = pd.DataFrame(nuovi_dati)
        df_final = pd.concat([df_new, df_old], ignore_index=True).drop_duplicates(subset=['Link'])
        df_final.to_csv(CSV_FILENAME, index=False, encoding='utf-8')
        print(f"✅ Aggiornato con successo ({len(nuovi_dati)} nuovi articoli).")

if __name__ == "__main__":
    scrape_ospiti_tv()
