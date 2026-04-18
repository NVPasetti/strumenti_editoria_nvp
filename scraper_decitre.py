import sys
import time
import pandas as pd
import re
import random
import os
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

URL_NOUVEAUTES = "https://www.decitre.fr/livres/arts-societe-sciences-humaines/nouveautes.html?sort=%7B%22field%22%3A%22publication%22%2C%22direction%22%3A%22desc%22%7D&dctr_web_availability=01"
URL_BESTSELLERS = "https://www.decitre.fr/livres/arts-societe-sciences-humaines/meilleures-ventes.html"
PAGINE_BESTSELLERS = 3
CSV_FILENAME = "dati_decitre_scraper.csv"

# --- CONFIGURAZIONE DRIVER STEALTH ---
def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Rimuove il flag webdriver
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''Object.defineProperty(navigator, 'webdriver', { get: () => undefined })'''
    })
    return driver

def gestisci_sicurezza(driver):
    """Controlla difese antibot e attende"""
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    testo_pagina = soup.text.lower()
    
    if "just a moment" in testo_pagina or "cloudflare" in testo_pagina or "verify you are human" in testo_pagina or "datadome" in testo_pagina:
        print("\n🛑 [SISTEMA DI SICUREZZA RILEVATO] Tento di attendere la risoluzione automatica.")
        
        for _ in range(5):
            time.sleep(3)
            html_check = driver.page_source
            testo_check = BeautifulSoup(html_check, 'html.parser').text.lower()
            if "just a moment" not in testo_check and "verify you are human" not in testo_check and "datadome" not in testo_check:
                print("✅ [VIA LIBERA] Blocco superato in automatico!")
                time.sleep(8) 
                return driver.page_source
    return html

def get_single_book_details(driver, book_url):
    dettagli = {"Publisher": "N/D", "Descrizione": "N/D", "Autore": "N/D"}
    if not book_url: return dettagli
    
    try:
        driver.get(book_url)
        time.sleep(random.uniform(3.0, 5.0))
        gestisci_sicurezza(driver)
        
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(1.0)
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(1.0)

        driver.execute_script("""
            let btnEditore = document.querySelector('div.product-summary-caracteristics button');
            if (btnEditore) btnEditore.click();
        """)
        
        driver.execute_script("""
            let bottoni = document.querySelectorAll('button');
            bottoni.forEach(b => {
                if(b.textContent.toLowerCase().includes('voir plus') || b.textContent.toLowerCase().includes('lire la suite')) {
                    b.click();
                }
            });
        """)
        
        time.sleep(1.5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        resume_title = soup.find(lambda tag: tag.name in ['h3', 'div'] and 'résumé' in tag.get_text(strip=True).lower())
        if resume_title:
            desc_content = resume_title.find_next_sibling('div')
            if desc_content: dettagli["Descrizione"] = desc_content.get_text(separator=' ', strip=True)
        else:
            desc_div = soup.find('div', id='description') or soup.find(class_=re.compile(r'description'))
            if desc_div: dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)

        for tag in soup.find_all(['li', 'div', 'tr']):
            testo = tag.get_text(strip=True).lower()
            if "éditeur" in testo or "editeur" in testo:
                valore = tag.get_text(separator=' ', strip=True)
                dettagli["Publisher"] = re.sub(r'(?i)éditeurs?|editeurs?|\:', '', valore).strip()
                break

        for tag in soup.find_all(class_=re.compile(r'author', re.I)):
            autore_testo = tag.get_text(strip=True)
            if 2 < len(autore_testo) < 100 and "Centre de" not in autore_testo and "cookies" not in autore_testo.lower():
                dettagli["Autore"] = re.sub(r'^(De\s+|Par\s+)', '', autore_testo, flags=re.IGNORECASE)
                break

        return dettagli
    except Exception as e:
        print(f"  [Errore estrazione dettagli: {e}]")
        return dettagli

def parse_list_page(driver, url):
    driver.get(url)
    time.sleep(random.uniform(4.0, 6.0)) 
    gestisci_sicurezza(driver)
    
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight/3);")
        time.sleep(1.5)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
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
                    
        books.append({'Copertina': img_url, 'Titolo': title, 'Autore': 'N/D', 'Link': href, 'id_univoco': href})
        visti_href.add(href)
            
    return books

def salva_dati(dizionario_libri):
    df = pd.DataFrame(list(dizionario_libri.values()))
    if not df.empty:
        df_final = df.drop(columns=['id_univoco']) if 'id_univoco' in df.columns else df.copy()
        cols = ['Nuovo', 'Categoria', 'Data_Aggiunta', 'Copertina', 'Titolo', 'Autore', 'Editore', 'Descrizione', 'Link']
        esistenti = [c for c in cols if c in df_final.columns]
        rimanenti = [c for c in df_final.columns if c not in esistenti]
        df_final = df_final[esistenti + rimanenti]
        df_final.to_csv(CSV_FILENAME, index=False)
        return len(df_final)
    return 0

def main():
    print("=== START DECITRE SCRAPER (SELENIUM GITHUB MODE) ===")
    
    all_books_dict = {}
    old_data = set() 
    oggi_str = datetime.now().date().isoformat()
    
    if os.path.exists(CSV_FILENAME):
        try:
            print(f"📚 Lettura archivio storico ({CSV_FILENAME})...")
            df_old = pd.read_csv(CSV_FILENAME)
            df_old['temp_id'] = df_old['Link'] if 'Link' in df_old.columns else (df_old['Titolo'].fillna('') + df_old['Autore'].fillna('')).str.lower().str.strip()
                
            if 'Data_Aggiunta' not in df_old.columns: df_old['Data_Aggiunta'] = oggi_str
            if 'Nuovo' not in df_old.columns: df_old['Nuovo'] = False
            if 'Categoria' not in df_old.columns: df_old['Categoria'] = 'N/D'
            
            for _, row in df_old.iterrows():
                uid = row['temp_id']
                book_dict = row.drop(labels=['temp_id']).to_dict()
                book_dict['Nuovo'] = False 
                all_books_dict[uid] = book_dict
                old_data.add(uid)
                    
            print(f"✅ Trovati {len(old_data)} libri salvati in precedenza.")
        except Exception as e:
            print(f"⚠️ Impossibile leggere il vecchio CSV: {e}")
    else:
        print("🌱 Nessun archivio trovato. Verrà creato un database francese oggi.")

    driver = get_driver()
    
    pagine_da_visitare = [{"nome": "Novità", "url": URL_NOUVEAUTES}]
    for p in range(1, PAGINE_BESTSELLERS + 1):
        pagine_da_visitare.append({"nome": f"Bestseller (Pag. {p})", "url": URL_BESTSELLERS if p == 1 else f"{URL_BESTSELLERS}?p={p}"})
        
    try:
        nuovi_estratti_totali = 0
        for pagina_target in pagine_da_visitare:
            print(f"\n--- 📖 LETTURA VETRINA: {pagina_target['nome'].upper()} ---")
            libri_nella_pagina = parse_list_page(driver, pagina_target['url'])
            
            if not libri_nella_pagina:
                print(f"Nessun libro trovato in {pagina_target['nome']}.")
                continue
                
            print(f"✅ Trovati {len(libri_nella_pagina)} libri. Controllo le novità...")
            nuovi_nella_pagina = 0
            
            for idx, book in enumerate(libri_nella_pagina, 1):
                uid_provvisorio = book['id_univoco']
                if uid_provvisorio in old_data:
                    print(f"  [{idx}/{len(libri_nella_pagina)}] ⏭️ Già in archivio: {book['Titolo'][:30]}...")
                    continue
                
                nuovi_nella_pagina += 1
                nuovi_estratti_totali += 1
                time.sleep(random.uniform(2.0, 4.0))
                print(f"  [{idx}/{len(libri_nella_pagina)}] 🆕 Sfoglio: {book['Titolo'][:30]}...")
                
                dettagli = get_single_book_details(driver, book['Link'])
                if dettagli["Autore"] != "N/D": book['Autore'] = dettagli["Autore"]
                    
                book['Editore'], book['Descrizione'], book['Data_Aggiunta'], book['Nuovo'], book['Categoria'] = dettagli['Publisher'], dettagli['Descrizione'], oggi_str, True, pagina_target['nome']
                
                all_books_dict[uid_provvisorio] = book
                old_data.add(uid_provvisorio) 
                salva_dati(all_books_dict)
                time.sleep(random.uniform(1.0, 2.5))
                
            print(f"💾 Elaborazione {pagina_target['nome']} completata. {nuovi_nella_pagina} aggiunti.")
            time.sleep(random.uniform(5.0, 8.0))

    except Exception as e:
        print(f"\nErrore inaspettato: {e}")
    finally:
        driver.quit()

    print(f"\n🎉 OPERAZIONE CONCLUSA. {nuovi_estratti_totali} NUOVI libri aggiunti oggi!")

if __name__ == "__main__":
    main()
