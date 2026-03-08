import sys
import time
import os
import pandas as pd
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
NUM_PAGINE_PER_CATEGORIA = 100  # <--- MODIFICATO DA 300 A 100 PER VELOCIZZARE
MIN_RECENSIONI_VECCHI = 60      # Soglia per i libri meno recenti
MIN_RECENSIONI_NUOVI = 35       # Soglia ridotta per le uscite post-Luglio 2025
OUTPUT_FILE = "amazon_libri_multicat.csv"

# --- DEFINIZIONE CATEGORIE (URL PULITI) ---
CATEGORIES = [
    {"name": "Politica", "rh": "n%3A411663031%2Cn%3A508811031"},
    {"name": "Società e scienze sociali", "rh": "n%3A411663031%2Cn%3A508879031"},
    {"name": "Storia", "rh": "n%3A411663031%2Cn%3A508796031"},
    {"name": "Diari, biografie, memorie", "rh": "n%3A411663031%2Cn%3A508714031"},
    {"name": "Arte, cinema e fotografia", "rh": "n%3A411663031%2Cn%3A508758031"},
    {"name": "Scienze, tecnologia, medicina", "rh": "n%3A411663031%2Cn%3A508867031"},
    {"name": "Religione e spiritualità", "rh": "n%3A508745031"}
]

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def check_captcha(driver):
    if "inserisci i caratteri" in driver.page_source.lower() or driver.find_elements(By.ID, 'captchacharacters'):
        print("\n" + "!"*50)
        print("⚠️  AMAZON CAPTCHA RILEVATO!  ⚠️")
        print("Vai sul browser, risolvilo e poi premi INVIO qui.")
        print("!"*50 + "\n")
        input("Premi INVIO dopo aver risolto...")
        driver.refresh()
        time.sleep(3)
        return True
    return False

def clean_reviews_count(text):
    if not text: return 0
    clean = re.sub(r'[^\d]', '', text)
    return int(clean) if clean else 0

def is_multiple_author(author_text):
    if not author_text: return True 
    text = author_text.lower()
    if ',' in text: return True
    if re.search(r'\b(?:e|and|et)\b', text): return True
    return False

def extract_date(text):
    if not text: return ""
    match = re.search(r'(\d{1,2}\s+[a-zA-Z]{3}\.?\s+\d{4})', text)
    return match.group(1) if match else ""

def is_recente_dopo_luglio_2025(date_text):
    """
    Analizza la data (es: '15 ott 2025' o '5 giu. 2026') 
    e restituisce True se è successiva a Luglio 2025.
    """
    if not date_text: return False
    
    mesi = {
        'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
        'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12
    }
    
    match = re.search(r'(\d{1,2})\s+([a-z]{3})\.?\s+(\d{4})', date_text.lower())
    if match:
        month_str = match.group(2)
        year = int(match.group(3))
        month = mesi.get(month_str, 0)
        
        if year > 2025:
            return True
        if year == 2025 and month > 7:
            return True
            
    return False

def append_to_csv(data_list, filename):
    if not data_list: return
    df = pd.DataFrame(data_list)
    file_exists = os.path.isfile(filename)
    df.to_csv(filename, mode='a', header=not file_exists, index=False, encoding='utf-8')

def sort_final_csv(filename):
    if os.path.exists(filename):
        print(f"\n--- Riordino finale del file CSV: {filename} ---")
        df = pd.read_csv(filename)
        df = df.sort_values(by=['Categoria', 'Recensioni'], ascending=[True, False])
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"✅ File CSV ordinato e completato correttamente: {len(df)} righe totali.")

def estrai_dati_libro(card, cat_name, visti_asin):
    asin = card.get('data-asin')
    if not asin or asin in visti_asin: 
        return None
    
    # Titolo
    title_tag = card.find('h2')
    title = title_tag.get_text(strip=True) if title_tag else "N/D"
    
    # Autore
    author = "N/D"
    author_rows = card.find_all('div', class_='a-row')
    for row in author_rows:
        row_text = row.get_text(" ", strip=True)
        match = re.match(r'^(?:di\s*:?|Di\s*:?)\s*(.+)', row_text)
        if match:
            raw_auth = match.group(1).split('|')[0].split('(')[0]
            author = raw_auth.strip()
            break
            
    if author == "N/D" or is_multiple_author(author): 
        return None

    # Recensioni
    reviews_count = 0
    review_tag = card.find(lambda tag: tag.name == 'a' and tag.has_attr('aria-label') and ('valutazioni' in tag['aria-label'] or 'voti' in tag['aria-label']))
    
    if review_tag:
        reviews_count = clean_reviews_count(review_tag['aria-label'].split()[0])
    else:
        review_span = card.find('span', class_='s-underline-text')
        if review_span:
            reviews_count = clean_reviews_count(review_span.get_text())

    # Data
    full_card_text = card.get_text(" ", strip=True)
    date_found = extract_date(full_card_text)

    # --- LOGICA DEL DOPPIO BINARIO ---
    if reviews_count >= MIN_RECENSIONI_VECCHI:
        pass 
    elif MIN_RECENSIONI_NUOVI <= reviews_count < MIN_RECENSIONI_VECCHI:
        if not is_recente_dopo_luglio_2025(date_found):
            return None 
    else:
        return None 

    # Immagine
    img_tag = card.find('img', class_='s-image')
    img_url = img_tag['src'] if img_tag else ""

    return {
        'ASIN': asin,
        'Copertina': img_url,
        'Titolo': title,
        'Autore': author,
        'Data': date_found,
        'Recensioni': reviews_count,
        'Categoria': cat_name
    }

def get_amazon_data(driver, filename):
    visti_asin = set()

    for cat in CATEGORIES:
        print(f"\n\n{'='*20} SCANSIONE: {cat['name'].upper()} {'='*20}")
        
        for page in range(1, NUM_PAGINE_PER_CATEGORIA + 1):
            page_books = []
            
            url = f"https://www.amazon.it/s?i=stripbooks&rh={cat['rh']}&s=popularity-rank&dc&page={page}"

            print(f"\n{cat['name']} - Pagina {page}/{NUM_PAGINE_PER_CATEGORIA}...")
            driver.get(url)
            
            check_captcha(driver)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except:
                print("❌ Nessun risultato trovato o pagina non caricata (Probabile fine catalogo).")
                if page > 5: break
                continue
                
            time.sleep(random.uniform(1.0, 2.0))
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(0.5)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            results = soup.find_all('div', {'data-component-type': 's-search-result'})
            print(f"  -> {len(results)} elementi trovati. Elaborazione...")

            count_ok = 0
            for card in results:
                book_data = estrai_dati_libro(card, cat['name'], visti_asin)
                
                if book_data:
                    visti_asin.add(book_data['ASIN'])
                    page_books.append(book_data)
                    count_ok += 1
            
            append_to_csv(page_books, filename)
            print(f"  -> {count_ok} libri idonei aggiunti al CSV.")

def main():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        
    driver = setup_driver()
    try:
        get_amazon_data(driver, OUTPUT_FILE)
        sort_final_csv(OUTPUT_FILE)
    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrotto manualmente. I dati scaricati finora sono salvi nel CSV.")
        sort_final_csv(OUTPUT_FILE)
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
