import sys
import time
import pandas as pd
import re
import random
import os
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

URL_NOUVEAUTES = "https://www.decitre.fr/livres/arts-societe-sciences-humaines/nouveautes.html?sort=%7B%22field%22%3A%22publication%22%2C%22direction%22%3A%22desc%22%7D&dctr_web_availability=01"
URL_BESTSELLERS = "https://www.decitre.fr/livres/arts-societe-sciences-humaines/meilleures-ventes.html"
PAGINE_BESTSELLERS = 3
CSV_FILENAME = "dati_decitre_scraper.csv"

def get_stealth_session():
    """Crea una sessione che simula perfettamente l'impronta di Chrome 120 per ingannare DataDome"""
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.fr/"
    })
    return session

def controlla_blocco(html):
    testo = html.lower()
    if "just a moment" in testo or "datadome" in testo or "verify you are human" in testo:
        print("\n⚠️ Attenzione: DataDome ha intercettato la richiesta. IP momentaneamente flaggato.")
        return True
    return False

def get_single_book_details(session, book_url):
    dettagli = {"Publisher": "N/D", "Descrizione": "N/D", "Autore": "N/D"}
    if not book_url: return dettagli
    
    try:
        time.sleep(random.uniform(2.0, 4.0))
        response = session.get(book_url)
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
                dettagli["Publisher"] = re.sub(r'(?i)éditeurs?|editeurs?|\:', '', valore).strip()
                break

        # 3. ESTRAZIONE AUTORE
        for tag in soup.find_all(class_=re.compile(r'author', re.I)):
            autore_testo = tag.get_text(strip=True)
            if 2 < len(autore_testo) < 100 and "Centre de" not in autore_testo and "cookies" not in autore_testo.lower():
                dettagli["Autore"] = re.sub(r'^(De\s+|Par\s+)', '', autore_testo, flags=re.IGNORECASE)
                break

        return dettagli
    except Exception as e:
        print(f"  [Errore estrazione dettagli: {e}]")
        return dettagli

def parse_list_page(session, url):
    time.sleep(random.uniform(3.0, 5.0))
    response = session.get(url)
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
    print("=== START DECITRE SCRAPER (STEALTH REQUESTS MODE) ===")
    
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

    session = get_stealth_session()
    
    pagine_da_visitare = [{"nome": "Novità", "url": URL_NOUVEAUTES}]
    for p in range(1, PAGINE_BESTSELLERS + 1):
        pagine_da_visitare.append({"nome": f"Bestseller (Pag. {p})", "url": URL_BESTSELLERS if p == 1 else f"{URL_BESTSELLERS}?p={p}"})
        
    try:
        nuovi_estratti_totali = 0
        for pagina_target in pagine_da_visitare:
            print(f"\n--- 📖 LETTURA VETRINA: {pagina_target['nome'].upper()} ---")
            libri_nella_pagina = parse_list_page(session, pagina_target['url'])
            
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
                print(f"  [{idx}/{len(libri_nella_pagina)}] 🆕 Sfoglio: {book['Titolo'][:30]}...")
                
                dettagli = get_single_book_details(session, book['Link'])
                if dettagli["Autore"] != "N/D": book['Autore'] = dettagli["Autore"]
                    
                book['Editore'], book['Descrizione'], book['Data_Aggiunta'], book['Nuovo'], book['Categoria'] = dettagli['Publisher'], dettagli['Descrizione'], oggi_str, True, pagina_target['nome']
                
                all_books_dict[uid_provvisorio] = book
                old_data.add(uid_provvisorio) 
                salva_dati(all_books_dict)
                
            print(f"💾 Elaborazione {pagina_target['nome']} completata. {nuovi_nella_pagina} aggiunti.")

    except Exception as e:
        print(f"\nErrore inaspettato: {e}")
        
    print(f"\n🎉 OPERAZIONE CONCLUSA. {nuovi_estratti_totali} NUOVI libri aggiunti oggi!")

if __name__ == "__main__":
    main()
