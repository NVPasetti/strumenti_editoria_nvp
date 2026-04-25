import sys
import time
import re
import os
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

BASE_URL = "https://www.davidemaggio.it/programmi-tv"
CSV_FILENAME = "ospiti_tv.csv"

def get_stealth_session():
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.it/"
    })
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

def scrape_ospiti_tv():
    print("📺 Avvio scraper incrementale DavideMaggio.it...")
    session = get_stealth_session()
    
    # Carichiamo i dati esistenti per non duplicarli e sapere quando fermarci
    if os.path.exists(CSV_FILENAME):
        df_old = pd.read_csv(CSV_FILENAME)
        link_visti = set(df_old['Link'].tolist())
    else:
        df_old = pd.DataFrame()
        link_visti = set()

    nuovi_risultati = []
    stop_scraping = False
    page = 1

    while not stop_scraping:
        url = f"{BASE_URL}/page/{page}" if page > 1 else BASE_URL
        print(f"📄 Analizzo pagina {page}...")
        
        try:
            response = session.get(url)
            if response.status_code != 200: break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Pulizia footer e tendenze per ogni pagina
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
                
                # CHIAVE DI ARRESTO: se il link è già presente, ci fermiamo
                if link in link_visti:
                    print("🛑 Trovata notizia già presente. Mi fermo.")
                    stop_scraping = True
                    break
                
                titolo = a_tag.get_text(strip=True)
                
                # Estrazione Immagine
                img_url = "N/D"
                img_tag = soup.find('a', href=link).find('img') if soup.find('a', href=link) else None
                if img_tag: img_url = img_tag.get('src') or img_tag.get('data-src') or "N/D"

                # Descrizione
                desc_div = tag.find_next('div', class_=re.compile(r'text-gray-100'))
                descrizione = desc_div.get_text(separator=' ', strip=True) if desc_div and desc_div.find_previous(['h2', 'h3', 'h4']) == tag else "N/D"

                # Data e Autore
                meta_p = tag.find_next('p', class_=re.compile(r'text-\[#A0A0A0\]'))
                autore, data = "N/D", "N/D"
                if meta_p and meta_p.find_previous(['h2', 'h3', 'h4']) == tag:
                    spans = meta_p.find_all('span')
                    if len(spans) >= 1: autore = spans[0].get_text(strip=True).replace("di ", "")
                    if len(spans) >= 2: data = spans[1].get_text(strip=True)

                if data == "N/D":
                    data = get_date_from_article(session, link)

                nuovi_risultati.append({
                    "Data": data, "Titolo": titolo, "Descrizione": descrizione,
                    "Autore": autore, "Immagine": img_url, "Link": link
                })
            
            if stop_scraping: break
            page += 1
            if page > 10: break # Limite di sicurezza
            
        except Exception as e:
            print(f"❌ Errore: {e}")
            break

    # Uniamo i nuovi dati a quelli vecchi
    if nuovi_risultati:
        df_new = pd.DataFrame(nuovi_risultati)
        df_final = pd.concat([df_new, df_old], ignore_index=True).drop_duplicates(subset=['Link'])
        df_final.to_csv(CSV_FILENAME, index=False, encoding='utf-8')
        print(f"✅ Database aggiornato: +{len(df_new)} notizie.")
    else:
        print("☕ Nulla di nuovo da aggiungere.")

if __name__ == "__main__":
    scrape_ospiti_tv()
