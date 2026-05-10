import sys
import ssl
import time
import re
import random
import os
import subprocess
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests

# --- FIX SSL PER MAC ---
ssl._create_default_https_context = ssl._create_unverified_context

# --- IMPORT ANTI-BOT ---
import undetected_chromedriver as uc
from selenium_stealth import stealth

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CSV_FILENAME = "dati_internazionali.csv"

# --- FUNZIONE HELPER CURL_CFFI (SITI VELOCI) ---
def get_soup(url):
    # impersonate="chrome120" aggira i blocchi imitando perfettamente il traffico di Chrome
    response = requests.get(url, impersonate="chrome120", timeout=15)
    return BeautifulSoup(response.text, 'html.parser')

# --- CONFIGURAZIONE DRIVER STEALTH (SITI COMPLESSI) ---
def get_driver():
    options = uc.ChromeOptions()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    versione_chrome = None
    try:
        if sys.platform == 'darwin': # Se il sistema è un Mac
            comando = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version']
        else: # Se è Linux/Windows
            comando = ['google-chrome', '--version']
            
        processo = subprocess.run(comando, capture_output=True, text=True)
        versione_completa = processo.stdout.strip()
        versione_chrome = int(versione_completa.split()[2].split('.')[0])
        print(f"🔧 Versione Chrome rilevata sul sistema: {versione_chrome}")
    except Exception as e:
        print(f"⚠️ Impossibile determinare la versione di Chrome: {e}")
        versione_chrome = 147 # Fallback
        
    driver = uc.Chrome(options=options, version_main=versione_chrome)

    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    return driver

# ==========================================
# 🗽 0. NEW YORK TIMES (CURL_CFFI)
# ==========================================
def get_nyt_bestsellers():
    print("\n--- 🗽 AVVIO NEW YORK TIMES BEST SELLERS (Veloce) ---")
    urls_nyt = [
        ("Hardcover", "https://www.nytimes.com/books/best-sellers/hardcover-nonfiction/"),
        ("Print & E-Book", "https://www.nytimes.com/books/best-sellers/combined-print-and-e-book-nonfiction/"),
        ("Advice & Misc", "https://www.nytimes.com/books/best-sellers/advice-how-to-and-miscellaneous/")
    ]
    
    risultati = []
    titoli_visti = set()

    for nome_cat, url in urls_nyt:
        print(f"🔍 Scansione NYT: {nome_cat}...")
        try:
            soup = get_soup(url)
            titoli_tags = soup.find_all('h3', itemprop='name')

            for h3 in titoli_tags:
                titolo = h3.get_text(strip=True).title()
                if len(titolo) < 2 or titolo.lower() in titoli_visti:
                    continue
                
                titoli_visti.add(titolo.lower())
                container = h3.find_parent('article') or h3.find_parent('li') or h3.parent.parent
                
                autore, copertina, descrizione, editore = "N/D", "N/D", "N/D", "New York Times Bestseller"
                
                if container:
                    a_tag = container.find(itemprop='author')
                    if a_tag: autore = re.sub(r'(?i)^by\s*', '', a_tag.get_text(strip=True))
                    
                    img_tag = container.find('img', itemprop='image')
                    if img_tag: copertina = img_tag.get('src') or "N/D"
                        
                    desc_tag = container.find(itemprop='description')
                    if desc_tag: descrizione = desc_tag.get_text(strip=True)
                        
                    ed_tag = container.find(itemprop='publisher')
                    if ed_tag: editore = ed_tag.get_text(strip=True)

                risultati.append({"Editore": editore, "Titolo": titolo, "Autore": autore, "Descrizione": descrizione, "Copertina": copertina, "Link": url, "Categoria": "Bestseller"})
                
        except Exception as e:
            print(f"⚠️ Errore su {nome_cat}: {e}")
            
    print(f"✅ Trovati {len(risultati)} bestseller unici sul New York Times.")
    return risultati

# ==========================================
# 🐧 1. PENGUIN RANDOM HOUSE (CURL_CFFI)
# ==========================================
def get_penguin_releases():
    print("\n--- 🐧 AVVIO PENGUIN RANDOM HOUSE (Veloce) ---")
    urls_da_visitare = []
    
    for page in range(1, 6):
        url = f"https://www.penguinrandomhouse.com/books/new-releases-nonfiction/?page={page}"
        print(f"🔍 Scansione Vetrina Penguin Pagina {page}...")
        try:
            soup = get_soup(url)
            for l in soup.find_all('a', href=re.compile(r'/books/\d+/')):
                href = l['href']
                full_url = href if href.startswith('http') else "https://www.penguinrandomhouse.com" + href
                if full_url not in urls_da_visitare: urls_da_visitare.append(full_url)
        except Exception as e:
            print(f"⚠️ Errore pagina Penguin: {e}")
                
    print(f"✅ Trovati {len(urls_da_visitare)} titoli su Penguin. Inizio estrazione...")
    
    risultati = []
    for link in urls_da_visitare:
        try:
            time.sleep(random.uniform(0.5, 1.5)) # Piccola pausa per non intasare il server
            soup = get_soup(link)
            dettagli = {"Editore": "Penguin Random House", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": "N/D", "Link": link, "Categoria": "Novità"}
            
            h1 = soup.find('h1')
            if h1: dettagli["Titolo"] = h1.get_text(strip=True)
                
            h2 = soup.find('h2')
            if h2: dettagli["Autore"] = re.sub(r'(?i)^by\s*', '', h2.get_text(strip=True)).strip()
                
            desc_div = soup.find('div', id='book-description-copy') or soup.find(class_=re.compile(r'book-description', re.I))
            if desc_div:
                for btn in desc_div.find_all(['button', 'a']): btn.decompose()
                dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
                
            img_tag = soup.find('img', id='coverFormat') or soup.find('img', class_=re.compile(r'responsive_img|img-responsive', re.I))
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src') or ""
                if src: dettagli["Copertina"] = src if src.startswith('http') else "https:" + src
                
            risultati.append(dettagli)
        except: continue
    return risultati

# ==========================================
# 📚 2. HARPERCOLLINS (SELENIUM - Invariato)
# ==========================================
def get_harper_releases(driver):
    print("\n--- 📚 AVVIO HARPERCOLLINS ---")
    url = "https://www.harpercollins.com/collections/new-in-nonfiction?sortBy=HCUSproducts_meta.hc-defined.publishdtimestamp_desc"
    driver.get(url)
    time.sleep(6) 
    driver.execute_script("window.scrollTo(0, 500);")
    time.sleep(2)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    urls_pagina = []
    
    for img in soup.find_all('img', class_='ais-hit-picture--img'):
        parent_a = img.find_parent('a')
        if parent_a and parent_a.get('href'):
            full_url = parent_a.get('href') if parent_a.get('href').startswith('http') else "https://www.harpercollins.com" + parent_a.get('href')
            if full_url not in urls_pagina: urls_pagina.append(full_url)
                
    print(f"✅ Trovati {len(urls_pagina)} titoli su HarperCollins. Inizio estrazione...")
    
    risultati = []
    for link in urls_pagina:
        try:
            driver.get(link)
            time.sleep(random.uniform(2.5, 4.0)) 
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            dettagli = {"Editore": "HarperCollins", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": "N/D", "Link": link, "Categoria": "Novità"}
            
            # 1. COPERTINA E TITOLO
            img_tag = soup.find('img', id='selected-img')
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src') or ""
                if src:
                    dettagli["Copertina"] = ("https:" + src) if src.startswith('//') else src
                
                alt_text = img_tag.get('alt')
                if alt_text:
                    dettagli["Titolo"] = alt_text.split(' by ')[0].strip()
                
            # 2. AUTORE 
            author_p = soup.find('p', class_='authorsParse')
            if author_p:
                autore_grezzo = author_p.get_text(strip=True)
                dettagli["Autore"] = re.sub(r'(?i)^By\s+', '', autore_grezzo).strip(', ')
                
            # 3. DESCRIZIONE
            desc_div = soup.find('div', id='hc-product-description')
            if desc_div:
                for btn in desc_div.find_all(['button', 'a']): btn.decompose()
                dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
                
            risultati.append(dettagli)
        except Exception as e: 
            print(f"  [Errore estrazione HarperCollins su {link}: {e}]")
            continue
            
    return risultati

# ==========================================
# 🌳 3. SIMON & SCHUSTER (CURL_CFFI)
# ==========================================
def get_simon_releases():
    print("\n--- 🌳 AVVIO SIMON & SCHUSTER (Veloce) ---")
    try:
        soup = get_soup("https://www.simonandschuster.com/p/new-releases#non-fiction")
        libri_trovati = []
        
        for div in soup.find_all('div', class_=re.compile(r'column.*is-4')):
            a_tag = div.find('a')
            if a_tag and a_tag.get('href'):
                full_url = a_tag.get('href') if a_tag.get('href').startswith('http') else "https://www.simonandschuster.com" + a_tag.get('href')
                img = a_tag.find('img')
                copertina = (img.get('data-src') or img.get('src')) if img else "N/D"
                libri_trovati.append({"Link": full_url, "Copertina": copertina})
                
        print(f"✅ Trovati {len(libri_trovati)} titoli su Simon & Schuster. Inizio estrazione...")
        
        risultati = []
        for libro in libri_trovati:
            try:
                time.sleep(random.uniform(0.5, 1.5))
                soup = get_soup(libro['Link'])
                dettagli = {"Editore": "Simon & Schuster", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": libro['Copertina'], "Link": libro['Link'], "Categoria": "Novità"}
                
                # 1. TITOLO
                h1_title = soup.find('h1', class_=re.compile(r'book-title'))
                if h1_title:
                    dettagli["Titolo"] = h1_title.get_text(strip=True)
                    
                # 2. AUTORE 
                author_div = soup.find(lambda tag: tag.name in ['div', 'span', 'p'] and 'is-size-5' in tag.get('class', []) and 'By' in tag.get_text())
                if author_div:
                    dettagli["Autore"] = re.sub(r'(?i)^By\s+', '', author_div.get_text(strip=True)).strip()
                else:
                    author_link = soup.find('a', href=re.compile(r'/authors/'))
                    if author_link:
                        dettagli["Autore"] = author_link.get_text(strip=True)
                    
                # 3. DESCRIZIONE
                desc_div = soup.find('div', class_='content')
                if desc_div:
                    for btn in desc_div.find_all(['button', 'a']): btn.decompose()
                    dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
                    
                risultati.append(dettagli)
            except Exception as e:
                print(f"  [Errore estrazione Simon & Schuster su {libro['Link']}: {e}]")
                continue
                
        return risultati
    except Exception as e:
        print(f"⚠️ Errore su vetrina Simon & Schuster: {e}")
        return []

# ==========================================
# Ⓜ️ 4. MACMILLAN (SELENIUM - Invariato)
# ==========================================
def get_macmillan_releases(driver):
    print("\n--- Ⓜ️ AVVIO MACMILLAN ---")
    driver.get("https://us.macmillan.com/search?dFR%5Bcollections.list.name%5D%5B0%5D=New%20Releases&dFR%5BhierarchicalCategories.lvl0%5D%5B0%5D=Nonfiction&searchType=products")
    time.sleep(6) 
    driver.execute_script("window.scrollTo(0, 500);")
    time.sleep(2)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    libri_trovati = []
    urls_visti = set()
    
    for img in soup.find_all('img', class_=re.compile(r'img__el')):
        parent_a = img.find_parent('a')
        if parent_a and parent_a.get('href'):
            href = parent_a.get('href')
            if "search" in href or "author" in href: continue
            full_url = href if href.startswith('http') else "https://us.macmillan.com" + href
            if full_url not in urls_visti:
                urls_visti.add(full_url)
                src = img.get('src') or img.get('data-src') or ""
                libri_trovati.append({"Link": full_url, "Copertina": src})
                
    print(f"✅ Trovati {len(libri_trovati)} titoli su Macmillan. Inizio estrazione...")
    
    risultati = []
    for libro in libri_trovati:
        try:
            driver.get(libro['Link'])
            time.sleep(random.uniform(2.5, 4.0))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            dettagli = {"Editore": "Macmillan", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": libro['Copertina'], "Link": libro['Link'], "Categoria": "Novità"}
            
            h1 = soup.find('h1', class_=re.compile(r'section-title__heading'))
            h2 = soup.find('h2', class_=re.compile(r'section-title__sub-title'))
            if h1: dettagli["Titolo"] = h1.get_text(strip=True) + (". " + h2.get_text(strip=True) if h2 else "")
                
            author_p = soup.find('p', class_=re.compile(r'section-title__content'))
            if author_p:
                span_label = author_p.find('span', class_=re.compile(r'section-title__label'))
                if span_label: span_label.decompose()
                
                autore_grezzo = author_p.get_text(strip=True)
                dettagli["Autore"] = re.sub(r'(?i)^(contributors?\s+by\s+|by\s+)', '', autore_grezzo).strip()

            desc_div = soup.find('div', class_=re.compile(r'book-about__body'))
            if desc_div:
                for btn in desc_div.find_all(['button', 'a']): btn.decompose()
                dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
                
            risultati.append(dettagli)
        except Exception as e:
            print(f"  [Errore estrazione Macmillan su {libro['Link']}: {e}]")
            continue
            
    return risultati

# ==========================================
# 🏰 5. HACHETTE (CURL_CFFI)
# ==========================================
def get_hachette_releases():
    print("\n--- 🏰 AVVIO HACHETTE (Veloce) ---")
    try:
        soup = get_soup("https://www.hachettebookgroup.com/genre-category/nonfiction/")
        
        urls_visti = set()
        for l in soup.find_all('a', href=re.compile(r'/titles/')):
            full_url = l['href'] if l['href'].startswith('http') else "https://www.hachettebookgroup.com" + l['href']
            urls_visti.add(full_url)
            
        print(f"✅ Trovati {len(urls_visti)} titoli su Hachette. Inizio estrazione...")
        
        risultati = []
        for link in urls_visti:
            try:
                time.sleep(random.uniform(0.5, 1.5))
                soup = get_soup(link)
                dettagli = {"Editore": "Hachette", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": "N/D", "Link": link, "Categoria": "Novità"}
                
                h1 = soup.find('h1')
                if h1: dettagli["Titolo"] = h1.get_text(strip=True)
                    
                author_tag = soup.find(class_=re.compile(r'author|contributor', re.I))
                if author_tag:
                    parti = re.split(r'(?i)by\s+', author_tag.get_text(strip=True))
                    dettagli["Autore"] = parti[-1].strip() if len(parti) > 1 else author_tag.get_text(strip=True)
                    
                desc_box = soup.find(id=re.compile(r'description|about', re.I)) or soup.find(class_=re.compile(r'description|about|summary', re.I))
                if desc_box:
                    for btn in desc_box.find_all(['button', 'a']): btn.decompose()
                    dettagli["Descrizione"] = desc_box.get_text(separator=' ', strip=True)
                    
                img_tag = soup.find('img', class_=re.compile(r'cover|product|book', re.I))
                if img_tag: dettagli["Copertina"] = img_tag.get('data-src') or img_tag.get('src') or ""
                    
                risultati.append(dettagli)
            except: continue
        return risultati
    except Exception as e:
        print(f"⚠️ Errore su vetrina Hachette: {e}")
        return []

# ==========================================
# 🚀 FUNZIONE MAIN (MODALITÀ IBRIDA E SOVRASCRITTURA)
# ==========================================
def main():
    print(f"🚀 Avvio Scraper Internazionale Ibrido (Clean & Overwrite)...")
    tutti_i_dati = []
    
    try:
        # FASE 1: SITI VELOCI (Nessun browser caricato in memoria)
        tutti_i_dati.extend(get_nyt_bestsellers())
        tutti_i_dati.extend(get_penguin_releases())
        tutti_i_dati.extend(get_simon_releases())
        tutti_i_dati.extend(get_hachette_releases())
        
        # FASE 2: SITI JS (Apre il browser in background)
        print("\n⚙️ Inizializzazione Chrome invisibile per i siti complessi...")
        driver = get_driver()
        try:
            tutti_i_dati.extend(get_harper_releases(driver))
            tutti_i_dati.extend(get_macmillan_releases(driver))
        finally:
            driver.quit() # Assicurati che si chiuda alla fine
        
        # FASE 3: SALVATAGGIO DATI
        if tutti_i_dati:
            df = pd.DataFrame(tutti_i_dati)
            
            oggi_str = datetime.now().date().isoformat()
            df['Data_Aggiunta'] = oggi_str
            
            cols = ['Categoria', 'Data_Aggiunta', 'Editore', 'Copertina', 'Titolo', 'Autore', 'Descrizione', 'Link']
            esistenti = [c for c in cols if c in df.columns]
            df = df[esistenti]
            
            # Eliminazione fisica prima della sovrascrittura
            if os.path.exists(CSV_FILENAME):
                os.remove(CSV_FILENAME)
                print(f"🗑️ Vecchio file '{CSV_FILENAME}' cancellato dal disco.")
                
            df.to_csv(CSV_FILENAME, index=False)
            print(f"✅ Scraping concluso! Trovati in totale {len(df)} libri. File sovrascritto: {CSV_FILENAME}")
        else:
            print("⚠️ Nessun dato estratto. Il file CSV non è stato creato/aggiornato.")
            
    except Exception as e:
        print(f"⚠️ Errore critico globale: {e}")

if __name__ == "__main__":
    main()
