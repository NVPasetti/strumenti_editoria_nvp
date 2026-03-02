import sys
import time
import pandas as pd
import re
import random
import requests
import io
import os  # Fondamentale per controllare se il file esiste
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- FIX ENCODING PER WINDOWS ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# --- CONFIGURAZIONE ---
SAFETY_LIMIT = 50 

URLS = [
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Storia+e+archeologia",
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Società%2c+politica+e+comunicazione",
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Scienze%2c+geografia%2c+ambiente",
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Salute%2c+famiglia+e+benessere+personale",
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Religione+e+spiritualità",
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Psicologia",
    "https://www.ibs.it/libri/ultima-settimana?useAsn=True&filterDepartment=Biografie"
]

EDITORI_TARGET = [
    "Adelphi", "Bollati Boringhieri", "Carabba", "Carocci", "Castelvecchi", 
    "DeriveApprodi", "Donzelli", "Einaudi", "Feltrinelli", "Garzanti", 
    "Giunti", "Gribaudo", "Hoepli", "Il Mulino", "Laterza", 
    "Libreria Editrice Vaticana", "Longanesi", "Marsilio", "Mimesis", 
    "Minimum Fax", "Mondadori", "Mondadori Electa", "Mondadori università", 
    "Morcelliana", "Newton Compton", "Passigli", "Piemme", "Ponte alle Grazie", 
    "Raffaello Cortina", "Rizzoli", "Ronzani", "Rubettino", "Rusconi libri", 
    "San Paolo Edizioni", "Silvio Berlusconi Editore", "Solferino", 
    "Sonzogno", "Sperling & Kupfer", "UTET", "Vallardi", "Vita e Pensiero"
]

def setup_driver():
    """Configurazione Driver 'Blindata' per GitHub Actions"""
    chrome_options = Options()
    
    # --- PARAMETRI CRITICI PER GITHUB ACTIONS ---
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox") 
    chrome_options.add_argument("--disable-dev-shm-usage") 
    chrome_options.add_argument("--disable-gpu") 
    chrome_options.add_argument("--window-size=1920,1080")
    
    # --- MASCHERAMENTO BOT ---
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    chrome_options.add_argument("--log-level=3") 
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_single_book_description(driver, book_url):
    if not book_url: return "N/D"
    try:
        driver.get(book_url)
        try:
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        except:
            return "Errore caricamento pagina"
        
        time.sleep(random.uniform(1.0, 2.0))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        body_container = soup.find('div', class_='cc-em-content-body')
        if body_container:
            text_div = body_container.find('div', class_=lambda x: x and 'cc-content-text' in x)
            if text_div:
                html_content = text_div.decode_contents()
                if '<br' in html_content:
                    parts = re.split(r'<br\s*/?>', html_content)
                    raw_text = parts[-1] 
                    return BeautifulSoup(raw_text, 'html.parser').get_text(separator=' ', strip=True)
                else:
                    return text_div.get_text(separator=' ', strip=True)

        desc_box = soup.find('div', id='description')
        if desc_box:
            text_div = desc_box.find('div', class_=lambda x: x and 'cc-content-text' in x)
            if text_div:
                return text_div.get_text(separator=' ', strip=True)

        return "" 
    except Exception as e:
        return ""

def parse_list_page(driver, url):
    print(f"\n--- Analisi URL... ---")
    driver.get(url)
    try:
        try:
            accept_btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            accept_btn.click()
        except: pass

        try:
            WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.CLASS_NAME, "cc-product-list-item")))
        except:
            return []

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(0.5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        cards = soup.find_all('div', class_='cc-product-list-item')
        
        books = []
        for card in cards:
            try:
                title_tag = card.find('a', class_='title') or card.find('a', href=True)
                title = title_tag.get_text(strip=True) if title_tag else "N/D"
                if len(title) < 2: continue 
                link = "https://www.ibs.it" + title_tag['href'] if title_tag and title_tag.has_attr('href') else ""
                
                img_url = ""
                img_col = card.find('div', class_='cc-col-img')
                if img_col:
                    img_tag = img_col.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ""

                author = "N/D"
                auth_tag = card.find(class_='cc-author')
                if auth_tag:
                    raw_auth = auth_tag.get_text(strip=True)
                    author = re.sub(r'^di\s*', '', raw_auth, flags=re.IGNORECASE)

                publisher, year = "N/D", "N/D"
                pub_tag = card.find(class_='cc-publisher')
                if pub_tag:
                    pub_text = pub_tag.get_text(strip=True)
                    match_year = re.search(r'(\d{4})$', pub_text)
                    if match_year:
                        year = match_year.group(1)
                        publisher = pub_text[:match_year.start()].strip().rstrip(',').strip()
                    else:
                        publisher = pub_text.rstrip(',').strip()

                is_target = any(t.lower() in publisher.lower() for t in EDITORI_TARGET)
                categoria_app = "Editori Selezionati" if is_target else "Altri Editori"

                books.append({
                    'Copertina': img_url,
                    'Titolo': title,
                    'Autore': author,
                    'Editore': publisher,
                    'Anno': year,
                    'Link': link,
                    'id_univoco': (title + author).lower(),
                    'Descrizione': '',
                    'Da_Scaricare': is_target, 
                    'Categoria_App': categoria_app
                })
            except: continue
        return books
    except Exception as e:
        print(f"Errore parsing pagina: {e}")
        return []

def save_excel_with_images(df, filename):
    # FILTRO: Salviamo in Excel (che è pesante) SOLO i libri principali
    df_excel = df[df['Categoria_App'] == 'Editori Selezionati'].copy()
    
    print(f"\n--- Generazione Excel ({len(df_excel)} libri selezionati) ---")
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Libri')
        workbook = writer.book
        worksheet = writer.sheets['Libri']
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 35)
        worksheet.set_column('C:E', 15)
        worksheet.set_column('F:F', 50)
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        worksheet.set_column('B:G', None, wrap_format)

        for idx, row in df_excel.iterrows():
            img_url = row['Copertina']
            row_num = idx + 1
            worksheet.set_row(row_num, 80)
            if img_url and str(img_url).startswith('http'):
                try:
                    image_data = requests.get(img_url, timeout=5).content
                    image_stream = io.BytesIO(image_data)
                    worksheet.insert_image(row_num, 0, img_url, {'image_data': image_stream, 'x_scale': 0.5, 'y_scale': 0.5, 'object_position': 1})
                except: pass
    print(f"✅ Excel salvato (Solo Top Editori).")

def main():
    print("=== START SCRAPER (HEADLESS MODE + NEW ARRIVALS) ===")
    
    # 1. CARICAMENTO VECCHI DATI (Per confronto)
    old_ids = set()
    csv_filename = "dati_per_app.csv"
    
    if os.path.exists(csv_filename):
        try:
            df_old = pd.read_csv(csv_filename)
            # Creiamo un ID univoco anche per i vecchi dati per confrontarli
            if 'Titolo' in df_old.columns and 'Autore' in df_old.columns:
                df_old['temp_id'] = (df_old['Titolo'].fillna('') + df_old['Autore'].fillna('')).str.lower().str.strip()
                old_ids = set(df_old['temp_id'].unique())
            print(f"📚 Trovati {len(old_ids)} libri già presenti nel database.")
        except Exception as e:
            print(f"⚠️ Impossibile leggere il vecchio CSV: {e}")

    driver = setup_driver()
    all_books_dict = {}
    
    try:
        print(f"=== FASE 1: SCANNING LISTE ===")
        for base_url in URLS:
            page_num = 1
            while page_num <= SAFETY_LIMIT:
                target_url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
                print(f"Url: ...{target_url[-40:]}")
                found = parse_list_page(driver, target_url)
                if not found: break
                
                new_books = 0
                for b in found:
                    if b['id_univoco'] not in all_books_dict:
                        # ### LOGICA NUOVI ARRIVI ###
                        b['Nuovo'] = b['id_univoco'] not in old_ids
                        
                        all_books_dict[b['id_univoco']] = b
                        new_books += 1
                
                print(f"   -> {new_books} libri trovati nella pagina.")
                page_num += 1
                time.sleep(0.5)

        books_to_scrape = [b for b in all_books_dict.values() if b['Da_Scaricare']]
        total_scrape = len(books_to_scrape)
        
        print(f"\n=== FASE 2: SCARICO DETTAGLI ({total_scrape} libri VIP) ===")
        counter = 1
        for book in books_to_scrape:
            uid = book['id_univoco']
            print(f"\r[{counter}/{total_scrape}] {book['Titolo'][:30]}...", end="", flush=True)
            desc = get_single_book_description(driver, book['Link'])
            all_books_dict[uid]['Descrizione'] = desc
            counter += 1
            
    finally:
        driver.quit()

    df = pd.DataFrame(list(all_books_dict.values()))
    if not df.empty:
        df_final = df.drop(columns=['id_univoco', 'Da_Scaricare'])
        # Assicuriamoci che la colonna 'Nuovo' sia inclusa e sia boolean
        cols = ['Categoria_App', 'Copertina', 'Titolo', 'Autore', 'Editore', 'Anno', 'Descrizione', 'Link', 'Nuovo']
        existing_cols = [c for c in cols if c in df_final.columns]
        df_final = df_final[existing_cols]
        
        # Salvataggio
        df_final.to_csv(csv_filename, index=False)
        print(f"\n\n✅ CSV AGGIORNATO: {csv_filename}")
        
        if 'Nuovo' in df_final.columns:
            num_new = df_final['Nuovo'].sum()
            print(f"🆕 Nuovi inserimenti rilevati rispetto a ieri: {num_new}")
        
        save_excel_with_images(df_final, "novita_ibs_filtrate.xlsx")
    else:
        print("\n❌ Nessun risultato.")

if __name__ == "__main__":
    main()
