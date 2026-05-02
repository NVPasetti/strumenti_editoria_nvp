import sys
import time
import re
import random
import os
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# --- IMPORT ANTI-BOT ---
# curl_cffi simula il fingerprint TLS di Chrome
from curl_cffi import requests

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

URL_NOUVEAUTES = "https://www.decitre.fr/livres/arts-societe-sciences-humaines/nouveautes.html?sort=%7B%22field%22%3A%22publication%22%2C%22direction%22%3A%22desc%22%7D&dctr_web_availability=01"
URL_BESTSELLERS = "https://www.decitre.fr/livres/arts-societe-sciences-humaines/meilleures-ventes.html"
PAGINE_BESTSELLERS = 3
CSV_FILENAME = "dati_decitre_scraper.csv"

# ==========================================
# 🛡️ CONFIGURAZIONE SESSIONE STEALTH
# ==========================================
def get_stealth_session():
    """
    Crea una sessione curl_cffi che emula perfettamente l'impronta TLS
    di un browser Chrome recente, utile per bypassare DataDome/Cloudflare.
    """
    # impersonate="chrome120" (o versioni successive) è la magia di questa libreria
    session = requests.Session(impersonate="chrome120")
    
    # Aggiungiamo headers realistici
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.fr/",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    })
    return session

def controlla_blocco(html):
    testo = html.lower()
    if "just a moment" in testo or "datadome" in testo or "verify you are human" in testo:
        print("\n⚠️ Attenzione: DataDome/Cloudflare ha intercettato la richiesta HTTP.")
        return True
    return False

# ==========================================
# 📖 ESTRAZIONE VETRINA (TROVA I LINK)
# ==========================================
def parse_list_page(session, url):
    time.sleep(random.uniform(2.0, 4.0))
    try:
        response = session.get(url, timeout=15)
        if controlla_blocco(response.text):
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        books = []
        visti_href = set()
        
        for a_tag in soup.find_all('a', class_=re.compile(r'product-card-infos__details__texts__link')):
            href = a_tag.get('href')
            if not href or href in visti_href: continue
            
            if href.startswith('//'): href = "https:" + href
            elif not href.startswith('http'): href = "https://www.decitre.fr" + (href if href.startswith('/') else '/' + href)
            href = href.split('#')[0] 
            
            h3_tag = a_tag.find('h3', class_=re.compile(r'product-card-infos__details__texts__link__title'))
            title = h3_tag.get_text(strip=True) if h3_tag else a_tag.get_text(strip=True)
            if len(title) < 3: continue
                    
            img_url = ""
            parent_card = a_tag.find_parent(class_=re.compile(r'product-card'))
            if parent_card:
                img_tag = parent_card.find('img')
                if img_tag:
                    img_url = img_tag.get('src') or img_tag.get('data-src') or ""
                    if img_url and img_url.startswith('//'): img_url = "https:" + img_url
                        
            books.append({'Copertina': img_url, 'Titolo': title, 'Link': href})
            visti_href.add(href)
                
        return books
    except Exception as e:
        print(f"Errore caricamento lista: {e}")
        return []

# ==========================================
# 🔍 ESTRAZIONE DETTAGLI SINGOLO LIBRO
# ==========================================
def get_single_book_details(session, book_url):
    dettagli = {"Editore": "N/D", "Descrizione": "N/D", "Autore": "N/D"}
    if not book_url: return dettagli
    
    try:
        time.sleep(random.uniform(1.5, 3.5))
        response = session.get(book_url, timeout=15)
        
        if controlla_blocco(response.text):
            return dettagli
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. ESTRAZIONE SINOSSI
        resume_title = soup.find(lambda tag: tag.name in ['h3', 'div'] and 'résumé' in tag.get_text(strip=True).lower())
        if resume_title:
            desc_content = resume_title.find_next_sibling('div')
            if desc_content: dettagli["Descrizione"] = desc_content.get_text(separator=' ', strip=True)
        else:
            desc_div = soup.find('div', id='description') or soup.find(class_=re.compile(r'description'))
            if desc_div: dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)

        # 2. ESTRAZIONE EDITORE 
        for tag in soup.find_all(['li', 'div', 'tr']):
            testo = tag.get_text(strip=True).lower()
            if "éditeur" in testo or "editeur" in testo:
                valore = tag.get_text(separator=' ', strip=True)
                dettagli["Editore"] = re.sub(r'(?i)éditeurs?|editeurs?|\:', '', valore).strip()
                break

        # 3. ESTRAZIONE AUTORE
        for tag in soup.find_all(class_=re.compile(r'author', re.I)):
            autore_testo = tag.get_text(strip=True)
            if 2 < len(autore_testo) < 100 and "centre de" not in autore_testo.lower() and "cookies" not in autore_testo.lower():
                dettagli["Autore"] = re.sub(r'^(De\s+|Par\s+)', '', autore_testo, flags=re.IGNORECASE)
                break

        return dettagli
    except Exception as e:
        print(f"  [Errore estrazione dettagli: {e}]")
        return dettagli

# ==========================================
# 🚀 MAIN (MODALITÀ PULITA)
# ==========================================
def main():
    print("=== START DECITRE SCRAPER (CURL_CFFI STEALTH MODE) ===")
    
    oggi_str = datetime.now().date().isoformat()
    tutti_i_dati = []
    
    session = get_stealth_session()
    
    pagine_da_visitare = [{"nome": "Novità", "url": URL_NOUVEAUTES}]
    for p in range(1, PAGINE_BESTSELLERS + 1):
        pagine_da_visitare.append({
            "nome": "Bestseller" if p == 1 else f"Bestseller (Pag. {p})", 
            "url": URL_BESTSELLERS if p == 1 else f"{URL_BESTSELLERS}?p={p}"
        })
        
    try:
        for pagina_target in pagine_da_visitare:
            print(f"\n--- 📖 LETTURA VETRINA: {pagina_target['nome'].upper()} ---")
            libri_nella_pagina = parse_list_page(session, pagina_target['url'])
            
            if not libri_nella_pagina:
                print(f"Nessun libro trovato in {pagina_target['nome']}.")
                continue
                
            print(f"✅ Trovati {len(libri_nella_pagina)} libri. Inizio estrazione...")
            
            for idx, book in enumerate(libri_nella_pagina, 1):
                print(f"  [{idx}/{len(libri_nella_pagina)}] 🔍 Sfoglio: {book['Titolo'][:30]}...")
                
                dettagli = get_single_book_details(session, book['Link'])
                
                book['Autore'] = dettagli['Autore']
                book['Editore'] = dettagli['Editore']
                book['Descrizione'] = dettagli['Descrizione']
                book['Categoria'] = "Novità" if "Novità" in pagina_target['nome'] else "Bestseller"
                book['Data_Aggiunta'] = oggi_str
                
                tutti_i_dati.append(book)
                
    except Exception as e:
        print(f"\n⚠️ Errore inaspettato globale: {e}")
        
    # --- SALVATAGGIO STATELESS (SOVRASCRITTURA) ---
    if tutti_i_dati:
        df = pd.DataFrame(tutti_i_dati)
        
        cols = ['Categoria', 'Data_Aggiunta', 'Editore', 'Copertina', 'Titolo', 'Autore', 'Descrizione', 'Link']
        esistenti = [c for c in cols if c in df.columns]
        df = df[esistenti]
        
        df.to_csv(CSV_FILENAME, index=False)
        print(f"\n🎉 OPERAZIONE CONCLUSA. {len(df)} libri elaborati! File '{CSV_FILENAME}' sovrascritto.")
    else:
        print("\n⚠️ Nessun dato raccolto. Il CSV non è stato creato/sovrascritto.")

if __name__ == "__main__":
    main()
