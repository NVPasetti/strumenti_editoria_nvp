import sys
import time
import pandas as pd
import re
import random
import os
from datetime import datetime
from bs4 import BeautifulSoup
import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# --- CONFIGURAZIONE SCRAPERAPI ---
# La chiave verrà pescata in automatico dai "Secrets" di GitHub
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

URL_NOVITA = "https://www.booksamillion.com/nonfiction2?cat=nonfiction2&oxid=1182&oxname=newarrivalsmod2&oxpage=newarrivals&oxpos=module2&oxdate=03012017"
URL_BESTSELLER = "https://www.booksamillion.com/features?cat=bestnonfiction&oxid=1173&oxname=bestsellersmod2&oxpage=bestsellers&oxpos=module3&oxdate=020121"
CSV_FILENAME = "dati_bam_scraper.csv"

def get_con_scraperapi(target_url):
    """Inoltra la richiesta ai server di ScraperAPI"""
    payload = {
        'api_key': SCRAPERAPI_KEY,
        'url': target_url,
        'render': 'true' 
    }
    
    for tentativo in range(2):
        try:
            response = requests.get('http://api.scraperapi.com/', params=payload, timeout=60)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 401:
                print("❌ ERRORE: API Key non valida o crediti esauriti!")
                return None
            else:
                print(f"⚠️ Errore ScraperAPI {response.status_code}. Riprovo...")
                time.sleep(3)
        except Exception as e:
            print(f"⚠️ Errore di connessione: {e}")
            time.sleep(3)
            
    return None

def get_single_book_details(book_url):
    """Estrae Sinossi, Publisher e Autore tramite ScraperAPI"""
    dettagli = {"Publisher": "N/D", "Descrizione": "N/D", "Autore": "N/D"}
    if not book_url: return dettagli
    
    try:
        html = get_con_scraperapi(book_url)
        if not html: return dettagli
        
        soup = BeautifulSoup(html, 'html.parser')
        
        anno_body = soup.find(id='annoBody')
        if anno_body:
            dettagli["Descrizione"] = anno_body.get_text(separator=' ', strip=True)
        else:
            desc_div = soup.find('div', class_=re.compile(r'description|synopsis', re.I))
            if desc_div:
                dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)

        details_section = soup.find(id='details-section')
        if details_section:
            for li in details_section.find_all('li'):
                testo_li = li.get_text(strip=True)
                if "Publisher:" in testo_li:
                    dettagli["Publisher"] = testo_li.replace("Publisher:", "").strip()
                    break

        author_tag = soup.find(class_=re.compile(r'author', re.I))
        if author_tag:
            autore_testo = author_tag.get_text(strip=True)
            dettagli["Autore"] = re.sub(r'^by\s*', '', autore_testo, flags=re.IGNORECASE)

        return dettagli
    except Exception as e:
        print(f"  [Errore estrazione dettagli: {e}]")
        return dettagli

def parse_list_page(url):
    """Estrae i link dei libri dalla vetrina usando ScraperAPI"""
    html = get_con_scraperapi(url)
    if not html:
        return None
        
    soup = BeautifulSoup(html, 'html.parser')
    
    if "Access Denied" in html or "Are you a human?" in html:
        print("❌ ALLARME: Books-A-Million ha bloccato il proxy di ScraperAPI. Serve attivare 'premium=true'.")
        return None

    books = []
    links_trovati = soup.find_all('a', href=re.compile(r'/p/'))
    visti_href = set()
    
    for a_tag in links_trovati:
        href = a_tag.get('href')
        if not href or href in visti_href: continue
        
        if href.startswith('//'):
            href = "https:" + href
        elif not href.startswith('http'):
            href = "https://www.booksamillion.com" + (href if href.startswith('/') else '/' + href)
            
        href = href.split('#')[0] 
        
        title = a_tag.get('title') or a_tag.get_text(strip=True)
        if len(title) < 3: 
            parent = a_tag.find_parent('div', class_=re.compile(r'item|product'))
            if parent:
                title_tag = parent.find(class_=re.compile(r'title|name'))
                if title_tag:
                    title = title_tag.get_text(strip=True)
        
        if len(title) < 3: continue
                
        img_url = ""
        img_tag = a_tag.find('img')
        if not img_tag:
            parent = a_tag.find_parent('div', class_=re.compile(r'item|product'))
            if parent:
                img_tag = parent.find('img')
        
        if img_tag:
            img_url = img_tag.get('src') or img_tag.get('data-original') or ""
            if img_url and img_url.startswith('//'):
                img_url = "https:" + img_url
                    
        uid = href
            
        books.append({
            'Copertina': img_url,
            'Titolo': title,
            'Autore': 'N/D', 
            'Link': href,
            'id_univoco': uid 
        })
        visti_href.add(href)
            
    return books

def salva_dati(dizionario_libri):
    df = pd.DataFrame(list(dizionario_libri.values()))
    if not df.empty:
        if 'id_univoco' in df.columns:
            df_final = df.drop(columns=['id_univoco'])
        else:
            df_final = df.copy()
        
        cols = ['Nuovo', 'Categoria', 'Data_Aggiunta', 'Copertina', 'Titolo', 'Autore', 'Editore', 'Descrizione', 'Link']
        esistenti = [c for c in cols if c in df_final.columns]
        rimanenti = [c for c in df_final.columns if c not in esistenti]
        df_final = df_final[esistenti + rimanenti]
        
        df_final.to_csv(CSV_FILENAME, index=False)
        return len(df_final)
    return 0

def main():
    if not SCRAPERAPI_KEY:
        print("❌ ATTENZIONE: Chiave ScraperAPI non trovata nelle variabili d'ambiente!")
        return

    print("=== START BAM! SCRAPER (GITHUB AUTOMATION MODE) ===")
    
    all_books_dict = {}
    old_data = set() 
    oggi_str = datetime.now().date().isoformat()
    
    if os.path.exists(CSV_FILENAME):
        try:
            print(f"📚 Lettura archivio storico ({CSV_FILENAME})...")
            df_old = pd.read_csv(CSV_FILENAME)
            
            if 'Link' in df_old.columns:
                df_old['temp_id'] = df_old['Link']
            else:
                df_old['temp_id'] = (df_old['Titolo'].fillna('') + df_old['Autore'].fillna('')).str.lower().str.strip()
                
            if 'Data_Aggiunta' not in df_old.columns:
                df_old['Data_Aggiunta'] = oggi_str
            if 'Nuovo' not in df_old.columns:
                df_old['Nuovo'] = False
            if 'Categoria' not in df_old.columns:
                df_old['Categoria'] = 'N/D'
            
            for _, row in df_old.iterrows():
                uid = row['temp_id']
                book_dict = row.drop(labels=['temp_id']).to_dict()
                book_dict['Nuovo'] = False 
                
                all_books_dict[uid] = book_dict
                old_data.add(uid)
                    
            print(f"✅ Trovati {len(old_data)} libri salvati in archivio.")
        except Exception as e:
            print(f"⚠️ Impossibile leggere il vecchio CSV: {e}")
    else:
        print("🌱 Nessun archivio trovato. Verrà creato un nuovo database BAM oggi.")

    pagine_da_visitare = [
        {"nome": "Novità", "url": URL_NOVITA},
        {"nome": "Bestseller", "url": URL_BESTSELLER}
    ]
    
    try:
        nuovi_estratti_totali = 0
        
        for pagina_target in pagine_da_visitare:
            print(f"\n--- 📖 LETTURA VETRINA: {pagina_target['nome'].upper()} ---")
            
            libri_nella_pagina = parse_list_page(pagina_target['url'])
            
            if libri_nella_pagina is None:
                print(f"🚨 Errore fatale sulla pagina {pagina_target['nome']}.")
                continue
                
            if not libri_nella_pagina:
                print(f"Nessun libro valido trovato in {pagina_target['nome']}.")
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
                
                time.sleep(random.uniform(1.0, 2.0))
                print(f"  [{idx}/{len(libri_nella_pagina)}] 🆕 Sfoglio: {book['Titolo'][:30]}...")
                
                dettagli = get_single_book_details(book['Link'])
                
                if dettagli["Autore"] != "N/D":
                    book['Autore'] = dettagli["Autore"]
                    
                book['Editore'] = dettagli['Publisher']
                book['Descrizione'] = dettagli['Descrizione']
                book['Data_Aggiunta'] = oggi_str
                book['Nuovo'] = True
                book['Categoria'] = pagina_target['nome'] 
                
                all_books_dict[uid_provvisorio] = book
                old_data.add(uid_provvisorio) 
                
                salva_dati(all_books_dict)

            print(f"💾 Elaborazione vetrina completata. {nuovi_nella_pagina} nuovi libri analizzati da {pagina_target['nome']}.")

    except KeyboardInterrupt:
        print("\nInterrotto manualmente dall'utente.")

    if all_books_dict:
        print(f"\n🎉 OPERAZIONE CONCLUSA. {nuovi_estratti_totali} NUOVI libri aggiunti oggi!")
        print(f"📂 CSV Finale pronto: {CSV_FILENAME}")

if __name__ == "__main__":
    main()
