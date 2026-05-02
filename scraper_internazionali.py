import sys
import time
import re
import random
import os
import subprocess
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

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

# --- CONFIGURAZIONE DRIVER STEALTH (CON FIX VERSIONE DINAMICA) ---
def get_driver():
    options = uc.ChromeOptions()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Trova dinamicamente la versione di Chrome installata
    versione_chrome = None
    try:
        processo = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
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
# 🗽 0. NEW YORK TIMES (BESTSELLERS)
# ==========================================
def get_nyt_bestsellers(driver):
    print("\n--- 🗽 AVVIO NEW YORK TIMES BEST SELLERS ---")
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
            driver.get(url)
            time.sleep(4)
            for i in range(1, 4):
                driver.execute_script(f"window.scrollTo(0, {i * 400});")
                time.sleep(0.5)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
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
# 🐧 1. PENGUIN RANDOM HOUSE
# ==========================================
def get_penguin_releases(driver):
    print("\n--- 🐧 AVVIO PENGUIN RANDOM HOUSE (5 Pagine) ---")
    urls_da_visitare = []
    
    for page in range(1, 6):
        url = f"https://www.penguinrandomhouse.com/books/new-releases-nonfiction/?page={page}"
        print(f"🔍 Scansione Vetrina Penguin Pagina {page}...")
        driver.get(url)
        time.sleep(4)
        for i in range(1, 4):
            driver.execute_script(f"window.scrollTo(0, {i * 400});")
            time.sleep(0.5)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        for l in soup.find_all('a', href=re.compile(r'/books/\d+/')):
            href = l['href']
            full_url = href if href.startswith('http') else "https://www.penguinrandomhouse.com" + href
            if full_url not in urls_da_visitare: urls_da_visitare.append(full_url)
                
    print(f"✅ Trovati {len(urls_da_visitare)} titoli su Penguin. Inizio estrazione...")
    
    risultati = []
    for link in urls_da_visitare:
        try:
            driver.get(link)
            time.sleep(random.uniform(2.0, 3.5))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
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
# 📚 2. HARPERCOLLINS
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
            
            titolo_principale = soup.find('h1', class_='product-title')
            sottotitolo = soup.find('h3')
            if titolo_principale: dettagli["Titolo"] = titolo_principale.get_text(strip=True) + (". " + sottotitolo.get_text(strip=True) if sottotitolo else "")
                
            author_p = soup.find('p', class_='authorsParse')
            if author_p:
                testo_pulito = re.sub(r'(?i)^by\s*', '', author_p.get_text(strip=True)).strip()
                dettagli["Autore"] = testo_pulito[:-1].strip() if testo_pulito.endswith(',') else testo_pulito
                
            img_tag = soup.find('img', id='selected-img')
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src') or ""
                dettagli["Copertina"] = ("https:" + src) if src.startswith('//') else src
                
            desc_div = soup.find('div', id='hc-product-description')
            if desc_div:
                for btn in desc_div.find_all(['button', 'a']): btn.decompose()
                dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
                
            risultati.append(dettagli)
        except: continue
    return risultati

# ==========================================
# 🌳 3. SIMON & SCHUSTER
# ==========================================
def get_simon_releases(driver):
    print("\n--- 🌳 AVVIO SIMON & SCHUSTER ---")
    driver.get("https://www.simonandschuster.com/p/new-releases#non-fiction")
    time.sleep(5)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    libri_trovati = []
    for div in soup.find_all('div', class_=re.compile(r'column.*is-4')):
        a_tag = div.find('a')
        if a_tag and a_tag.get('href'):
            full_url = a_tag.get('href') if a_tag.get('href').startswith('http') else "https://www.simonandschuster.com" + a_tag.get('href')
            img = a_tag.find('img')
            copertina = (img.get('data-src') or img.get('src')) if img else "N/D"
            title_div = div.find('div', class_=re.compile(r'book-title'))
            titolo = title_div.get_text(strip=True) if title_div else "N/D"
            libri_trovati.append({"Link": full_url, "Titolo": titolo, "Copertina": copertina})
            
    print(f"✅ Trovati {len(libri_trovati)} titoli su Simon & Schuster. Inizio estrazione...")
    
    risultati = []
    for libro in libri_trovati:
        try:
            driver.get(libro['Link'])
            time.sleep(random.uniform(2.5, 4.0))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            dettagli = {"Editore": "Simon & Schuster", "Titolo": libro['Titolo'], "Autore": "N/D", "Descrizione": "N/D", "Copertina": libro['Copertina'], "Link": libro['Link'], "Categoria": "Novità"}
            
            author_tag = soup.find(class_=re.compile(r'author|contributor', re.I))
            if author_tag: dettagli["Autore"] = re.sub(r'(?i)^by\s*', '', author_tag.get_text(strip=True))
                
            desc_box = soup.find(class_=re.compile(r'description|about|summary|content', re.I))
            if desc_box:
                for btn in desc_box.find_all(['button', 'a']): btn.decompose()
                dettagli["Descrizione"] = desc_box.get_text(separator=' ', strip=True)
                
            risultati.append(dettagli)
        except: continue
    return risultati

# ==========================================
# Ⓜ️ 4. MACMILLAN
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
                dettagli["Autore"] = author_p.get_text(strip=True)

            desc_div = soup.find('div', class_=re.compile(r'book-about__body'))
            if desc_div:
                for btn in desc_div.find_all(['button', 'a']): btn.decompose()
                dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
                
            risultati.append(dettagli)
        except: continue
    return risultati

# ==========================================
# 🏰 5. HACHETTE
# ==========================================
def get_hachette_releases(driver):
    print("\n--- 🏰 AVVIO HACHETTE ---")
    driver.get("https://www.hachettebookgroup.com/genre-category/nonfiction/")
    time.sleep(5)
    
    try:
        driver.execute_script("let btn = document.querySelector('button[id^=\"carousel-\"]'); if(btn) btn.click();")
        time.sleep(1.5)
    except: pass

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    urls_visti = set()
    for l in soup.find_all('a', href=re.compile(r'/titles/')):
        full_url = l['href'] if l['href'].startswith('http') else "https://www.hachettebookgroup.com" + l['href']
        urls_visti.add(full_url)
        
    print(f"✅ Trovati {len(urls_visti)} titoli su Hachette. Inizio estrazione...")
    
    risultati = []
    for link in urls_visti:
        try:
            driver.get(link)
            time.sleep(random.uniform(2.5, 4.0))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
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


# ==========================================
# 🚀 FUNZIONE MAIN (MODALITÀ PULITA E SOVRASCRITTURA)
# ==========================================
def main():
    print(f"🚀 Avvio Scraper Internazionale (Modalità Clean & Overwrite)...")
    driver = get_driver()
    tutti_i_dati = []
    
    try:
        tutti_i_dati.extend(get_nyt_bestsellers(driver))
        tutti_i_dati.extend(get_penguin_releases(driver))
        tutti_i_dati.extend(get_harper_releases(driver))
        tutti_i_dati.extend(get_simon_releases(driver))
        tutti_i_dati.extend(get_macmillan_releases(driver))
        tutti_i_dati.extend(get_hachette_releases(driver))
        
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
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
