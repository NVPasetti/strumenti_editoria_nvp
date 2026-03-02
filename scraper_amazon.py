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
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
NUM_PAGINE_PER_CATEGORIA = 300  # 300 pagine per ogni categoria
MIN_RECENSIONI = 60             # Soglia minima recensioni
OUTPUT_FILE = "amazon_libri_multicat.csv" # Nome del file di salvataggio

# --- DEFINIZIONE CATEGORIE ---
CATEGORIES = [
    {
        "name": "Politica",
        "start": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508811031&s=popularity-rank&dc&ds=v1%3A1uqCcTb8AV8Dc6x3H5oH0R5Cf0u0jaxVcXbZT3KTUBE&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1770971381&rnid=411663031&unfiltered=1&ref=sr_nr_n_22",
        "template": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508811031&s=popularity-rank&dc&page={page}&xpid=jPcvm0uprEBiA&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1770971462&rnid=411663031&unfiltered=1&ref=sr_pg_{page}"
    },
    {
        "name": "Società e scienze sociali",
        "start": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508879031&s=popularity-rank&dc&ds=v1%3AR47I6AG9ih1tg0l9wu3JvStxNrxtYTuBhWVTFa0u2Ns&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1770971381&rnid=411663031&unfiltered=1&ref=sr_nr_n_27",
        "template": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508879031&s=popularity-rank&dc&page={page}&xpid=w8fDm946QJ2kf&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1770971700&rnid=411663031&unfiltered=1&ref=sr_pg_{page}"
    },
    {
        "name": "Storia",
        "start": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508796031&s=popularity-rank&dc&ds=v1%3AJOuHaw3exr5T9B7CMs43On%2BKh5n5aB42XV1mVuWeXtI&Adv-Srch-Books-Submit.x=43&Adv-Srch-Books-Submit.y=13&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1770971808&rnid=411663031&unfiltered=1&ref=sr_nr_n_29",
        "template": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508796031&s=popularity-rank&dc&page={page}&xpid=Vb0JMqPaAY_2z&Adv-Srch-Books-Submit.x=43&Adv-Srch-Books-Submit.y=13&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1770971834&rnid=411663031&unfiltered=1&ref=sr_pg_{page}"
    },
    {
        "name": "Diari, biografie, memorie",
        "start": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508714031&s=popularity-rank&dc&ds=v1%3AmWhtywfD%2BcnTHWC0bM2cOPEJ%2FahBmVcN9GQgjl7IGOc&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1771967445&rnid=411663031&unfiltered=1&xpid=jPcvm0uprEBiA&ref=sr_nr_n_3",
        "template": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508714031&s=popularity-rank&dc&page={page}&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1771967662&rnid=411663031&unfiltered=1&xpid=jPcvm0uprEBiA&ref=sr_pg_{page}"
    },
    {
        "name": "Arte, cinema e fotografia",
        "start": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508758031&s=popularity-rank&dc&ds=v1%3At7vY0geCA1tYPIQYJMVpI4k2SjEn3qbMn25rXC%2BKwKU&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1771967928&rnid=411663031&unfiltered=1&xpid=jPcvm0uprEBiA&ref=sr_nr_n_2",
        "template": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508758031&s=popularity-rank&dc&page={page}&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1771967935&rnid=411663031&unfiltered=1&xpid=jPcvm0uprEBiA&ref=sr_pg_{page}"
    },
    {
        "name": "Scienze, tecnologia, medicina",
        "start": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508867031&s=popularity-rank&dc&ds=v1%3AwvIAIIaZwTaMGS2TzKeLz%2Bwgw07rYBJpZRyEJ1ecEWU&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1771968054&rnid=411663031&unfiltered=1&xpid=jPcvm0uprEBiA&ref=sr_nr_n_25",
        "template": "https://www.amazon.it/s?i=stripbooks&rh=n%3A411663031%2Cn%3A508867031&s=popularity-rank&dc&page={page}&Adv-Srch-Books-Submit.x=30&Adv-Srch-Books-Submit.y=4&__mk_it_IT=%C3%85M%C3%85Z%C3%95%C3%91&page_nav_name=Libri+in+italiano&qid=1771968084&rnid=411663031&unfiltered=1&xpid=jPcvm0uprEBiA&ref=sr_pg_{page}"
    }
]

# --- FIX ENCODING ---
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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

def check_captcha(driver, soup):
    if soup.find('input', id='captchacharacters') or "inserisci i caratteri" in soup.get_text().lower():
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
    try:
        return int(clean)
    except:
        return 0

def is_multiple_author(author_text):
    if not author_text: return True 
    text = author_text.lower()
    if ',' in text: return True
    if ' e ' in text: return True
    if ' et ' in text or ' and ' in text: return True
    return False

def extract_date(text):
    if not text: return ""
    match = re.search(r'(\d{1,2}\s+[a-zA-Z]{3}\.?\s+\d{4})', text)
    if match:
        return match.group(1)
    return ""

def append_to_csv(data_list, filename):
    """Salva i dati della singola pagina accodandoli al CSV esistente."""
    if not data_list: return
    df = pd.DataFrame(data_list)
    
    # Se il file non esiste, aggiunge l'header; altrimenti accoda solo i dati
    file_exists = os.path.isfile(filename)
    df.to_csv(filename, mode='a', header=not file_exists, index=False, encoding='utf-8')

def sort_final_csv(filename):
    """Alla fine dello scraping, legge il CSV, lo ordina e lo sovrascrive."""
    if os.path.exists(filename):
        print(f"\n--- Riordino finale del file CSV: {filename} ---")
        df = pd.read_csv(filename)
        df = df.sort_values(by=['Categoria', 'Recensioni'], ascending=[True, False])
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"✅ File CSV ordinato e completato correttamente: {len(df)} righe totali.")

def get_amazon_data(driver, filename):
    visti_asin = set()

    for cat in CATEGORIES:
        print(f"\n\n{'='*20} SCANSIONE: {cat['name'].upper()} {'='*20}")
        
        for page in range(1, NUM_PAGINE_PER_CATEGORIA + 1):
            page_books = [] # Accumulatore per la singola pagina
            
            if page == 1:
                url = cat['start']
            else:
                url = cat['template'].format(page=page)

            print(f"\n{cat['name']} - Pagina {page}/{NUM_PAGINE_PER_CATEGORIA}...")
            driver.get(url)
            
            time.sleep(random.uniform(2.0, 4.0))
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            if check_captcha(driver, soup):
                soup = BeautifulSoup(driver.page_source, 'html.parser')

            results = soup.find_all('div', {'data-component-type': 's-search-result'})
            
            if not results:
                print("❌ Nessun risultato trovato in questa pagina.")
                if page > 5: 
                    print("Probabile fine catalogo per questa categoria.")
                    break
                continue
                
            print(f"  -> {len(results)} elementi trovati. Elaborazione...")

            count_ok = 0
            for card in results:
                try:
                    asin = card.get('data-asin')
                    if not asin or asin in visti_asin: continue
                    
                    title_tag = card.find('h2')
                    title = title_tag.get_text(strip=True) if title_tag else "N/D"
                    
                    author = "N/D"
                    author_rows = card.find_all('div', class_='a-row')
                    for row in author_rows:
                        row_text = row.get_text(" ", strip=True)
                        if re.match(r'^di\s+', row_text, re.IGNORECASE):
                            raw_auth = re.sub(r'^di\s+', '', row_text, flags=re.IGNORECASE)
                            raw_auth = raw_auth.split('|')[0].split('(')[0]
                            author = raw_auth.strip()
                            break
                    
                    if author == "N/D": continue
                    if is_multiple_author(author): continue

                    full_card_text = card.get_text(" ", strip=True)
                    date_found = extract_date(full_card_text)

                    reviews_count = 0
                    review_tag = card.find(lambda tag: tag.name == 'a' and tag.has_attr('aria-label') and ('valutazioni' in tag['aria-label'] or 'voti' in tag['aria-label']))
                    
                    if review_tag:
                        label_text = review_tag['aria-label']
                        reviews_count = clean_reviews_count(label_text.split()[0])
                    else:
                        review_span = card.find('span', class_='s-underline-text')
                        if review_span:
                            reviews_count = clean_reviews_count(review_span.get_text())

                    if reviews_count < MIN_RECENSIONI: continue

                    img_tag = card.find('img', class_='s-image')
                    img_url = img_tag['src'] if img_tag else ""

                    visti_asin.add(asin)
                    page_books.append({
                        'ASIN': asin,
                        'Copertina': img_url,
                        'Titolo': title,
                        'Autore': author,
                        'Data': date_found,
                        'Recensioni': reviews_count,
                        'Categoria': cat['name'] 
                    })
                    count_ok += 1

                except Exception:
                    continue
            
            # Salva i libri trovati in questa pagina direttamente nel CSV
            append_to_csv(page_books, filename)
            print(f"  -> {count_ok} nuovi libri aggiunti e salvati nel CSV.")

def main():
    # Rimuove il file precedente per evitare di mischiare i dati se fai ripartire da zero
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        
    driver = setup_driver()
    try:
        get_amazon_data(driver, OUTPUT_FILE)
        # Se tutto finisce senza errori, applica l'ordinamento finale
        sort_final_csv(OUTPUT_FILE)
    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrotto manualmente. I dati scaricati finora sono salvi nel CSV.")
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
        print("I dati processati fino a questo momento sono al sicuro nel CSV.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
