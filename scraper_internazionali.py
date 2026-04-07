import sys
import time
import re
import random
import asyncio
import ssl
import tempfile
import os
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
import nodriver as uc

# --- FIX SSL E ENCODING ---
ssl._create_default_https_context = ssl._create_unverified_context
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

CSV_FILENAME = "dati_big5_scraper.csv"

# ==========================================
# 🐧 1. PENGUIN RANDOM HOUSE
# ==========================================
async def get_penguin_releases(tab):
    print("\n--- 🐧 AVVIO PENGUIN RANDOM HOUSE (5 Pagine) ---")
    urls_da_visitare = []
    
    for page in range(1, 6):
        url = f"https://www.penguinrandomhouse.com/books/new-releases-nonfiction/?page={page}"
        print(f"🔍 Scansione Vetrina Penguin Pagina {page}...")
        await tab.get(url)
        await asyncio.sleep(4)
        await tab.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
        await asyncio.sleep(1)
        
        html = await tab.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        links = soup.find_all('a', href=re.compile(r'/books/\d+/'))
        for l in links:
            href = l['href']
            full_url = href if href.startswith('http') else "https://www.penguinrandomhouse.com" + href
            if full_url not in urls_da_visitare:
                urls_da_visitare.append(full_url)
                
    print(f"✅ Trovati {len(urls_da_visitare)} libri su Penguin. Inizio estrazione...")
    
    risultati = []
    for link in urls_da_visitare:
        print(f"  [Penguin] 📖 {link}")
        await tab.get(link)
        await asyncio.sleep(random.uniform(2.0, 3.5))
        html = await tab.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        dettagli = {"Editore": "Penguin Random House", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": "N/D", "Link": link}
        
        h1 = soup.find('h1')
        if h1: dettagli["Titolo"] = h1.get_text(strip=True)
            
        h2 = soup.find('h2')
        if h2: 
            testo_autore = h2.get_text(strip=True)
            dettagli["Autore"] = re.sub(r'(?i)^by\s*', '', testo_autore).strip()
            
        desc_div = soup.find('div', id='book-description-copy')
        if desc_div:
            for btn in desc_div.find_all(['button', 'a']): btn.decompose()
            dettagli["Descrizione"] = desc_div.get_text(separator=' ', strip=True)
            
        img_tag = soup.find('img', class_=re.compile(r'responsive_img', re.I))
        if img_tag:
            src = img_tag.get('src') or img_tag.get('data-src') or ""
            dettagli["Copertina"] = src if src.startswith('http') else "https:" + src
            
        risultati.append(dettagli)
        
    return risultati

# ==========================================
# 📚 2. HARPERCOLLINS
# ==========================================
async def get_harper_releases(tab):
    print("\n--- 📚 AVVIO HARPERCOLLINS ---")
    url = "https://www.harpercollins.com/collections/new-in-nonfiction?sortBy=HCUSproducts_meta.hc-defined.publishdtimestamp_desc"
    await tab.get(url)
    await asyncio.sleep(6) 
    await tab.evaluate("window.scrollTo(0, 500);")
    await asyncio.sleep(2)
    
    html = await tab.get_content()
    soup = BeautifulSoup(html, 'html.parser')
    
    immagini_libri = soup.find_all('img', class_='ais-hit-picture--img')
    urls_pagina = []
    
    for img in immagini_libri:
        parent_a = img.find_parent('a')
        if parent_a and parent_a.get('href'):
            href = parent_a.get('href')
            full_url = href if href.startswith('http') else "https://www.harpercollins.com" + href
            if full_url not in urls_pagina:
                urls_pagina.append(full_url)
                
    print(f"✅ Trovati {len(urls_pagina)} libri su HarperCollins. Inizio estrazione...")
    
    risultati = []
    for link in urls_pagina:
        print(f"  [Harper] 📖 {link}")
        await tab.get(link)
        await asyncio.sleep(random.uniform(2.5, 4.0)) 
        html = await tab.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        dettagli = {"Editore": "HarperCollins", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": "N/D", "Link": link}
        
        titolo_principale = soup.find('h1', class_='product-title')
        sottotitolo = soup.find('h3')
        if titolo_principale:
            dettagli["Titolo"] = titolo_principale.get_text(strip=True) + (". " + sottotitolo.get_text(strip=True) if sottotitolo else "")
            
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
        
    return risultati

# ==========================================
# 🌳 3. SIMON & SCHUSTER
# ==========================================
async def get_simon_releases(tab):
    print("\n--- 🌳 AVVIO SIMON & SCHUSTER ---")
    url = "https://www.simonandschuster.com/p/new-releases#non-fiction"
    await tab.get(url)
    await asyncio.sleep(5)
    
    html = await tab.get_content()
    soup = BeautifulSoup(html, 'html.parser')
    col_divs = soup.find_all('div', class_=re.compile(r'column.*is-4'))
    
    libri_trovati = []
    for div in col_divs:
        a_tag = div.find('a')
        if a_tag and a_tag.get('href'):
            href = a_tag.get('href')
            full_url = href if href.startswith('http') else "https://www.simonandschuster.com" + href
            
            img = a_tag.find('img')
            copertina = (img.get('data-src') or img.get('src')) if img else "N/D"
            
            title_div = div.find('div', class_=re.compile(r'book-title'))
            titolo = title_div.get_text(strip=True) if title_div else "N/D"
            
            libri_trovati.append({"Link": full_url, "Titolo": titolo, "Copertina": copertina})
            
    print(f"✅ Trovati {len(libri_trovati)} libri su Simon & Schuster. Inizio estrazione...")
    
    risultati = []
    for libro in libri_trovati:
        print(f"  [S&S] 📖 {libro['Link']}")
        await tab.get(libro['Link'])
        await asyncio.sleep(random.uniform(2.5, 4.0))
        html = await tab.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        dettagli = {"Editore": "Simon & Schuster", "Titolo": libro['Titolo'], "Autore": "N/D", "Descrizione": "N/D", "Copertina": libro['Copertina'], "Link": libro['Link']}
        
        author_tag = soup.find(class_=re.compile(r'author|contributor', re.I))
        if author_tag:
            dettagli["Autore"] = re.sub(r'(?i)^by\s*', '', author_tag.get_text(strip=True))
            
        desc_box = soup.find(class_=re.compile(r'description|about|summary|content', re.I))
        if desc_box:
            for btn in desc_box.find_all(['button', 'a']): btn.decompose()
            dettagli["Descrizione"] = desc_box.get_text(separator=' ', strip=True)
            
        risultati.append(dettagli)
        
    return risultati

# ==========================================
# Ⓜ️ 4. MACMILLAN
# ==========================================
async def get_macmillan_releases(tab):
    print("\n--- Ⓜ️ AVVIO MACMILLAN ---")
    url = "https://us.macmillan.com/search?dFR%5Bcollections.list.name%5D%5B0%5D=New%20Releases&dFR%5BhierarchicalCategories.lvl0%5D%5B0%5D=Nonfiction&searchType=products"
    await tab.get(url)
    await asyncio.sleep(6) 
    await tab.evaluate("window.scrollTo(0, 500);")
    await asyncio.sleep(2)
    
    html = await tab.get_content()
    soup = BeautifulSoup(html, 'html.parser')
    
    immagini_libri = soup.find_all('img', class_=re.compile(r'img__el'))
    libri_trovati = []
    urls_visti = set()
    
    for img in immagini_libri:
        parent_a = img.find_parent('a')
        if parent_a and parent_a.get('href'):
            href = parent_a.get('href')
            if "search" in href or "author" in href: continue
                
            full_url = href if href.startswith('http') else "https://us.macmillan.com" + href
            if full_url not in urls_visti:
                urls_visti.add(full_url)
                src = img.get('src') or img.get('data-src') or ""
                libri_trovati.append({"Link": full_url, "Copertina": src})
                
    print(f"✅ Trovati {len(libri_trovati)} libri su Macmillan. Inizio estrazione...")
    
    risultati = []
    for libro in libri_trovati:
        print(f"  [Macmillan] 📖 {libro['Link']}")
        await tab.get(libro['Link'])
        await asyncio.sleep(random.uniform(2.5, 4.0))
        html = await tab.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        dettagli = {"Editore": "Macmillan", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": libro['Copertina'], "Link": libro['Link']}
        
        h1 = soup.find('h1', class_=re.compile(r'section-title__heading'))
        h2 = soup.find('h2', class_=re.compile(r'section-title__sub-title'))
        if h1:
            dettagli["Titolo"] = h1.get_text(strip=True) + (". " + h2.get_text(strip=True) if h2 else "")
            
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
        
    return risultati

# ==========================================
# 🏰 5. HACHETTE
# ==========================================
async def get_hachette_releases(tab):
    print("\n--- 🏰 AVVIO HACHETTE ---")
    url = "https://www.hachettebookgroup.com/genre-category/nonfiction/"
    await tab.get(url)
    await asyncio.sleep(5)
    
    try:
        await tab.evaluate("""
            let btn = document.querySelector('button[id^="carousel-"]');
            if(btn) btn.click();
        """)
        await asyncio.sleep(1.5)
    except:
        pass

    html = await tab.get_content()
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=re.compile(r'/titles/'))
    
    urls_visti = set()
    for l in links:
        href = l['href']
        full_url = href if href.startswith('http') else "https://www.hachettebookgroup.com" + href
        urls_visti.add(full_url)
        
    print(f"✅ Trovati {len(urls_visti)} libri su Hachette. Inizio estrazione...")
    
    risultati = []
    for link in urls_visti:
        print(f"  [Hachette] 📖 {link}")
        await tab.get(link)
        await asyncio.sleep(random.uniform(2.5, 4.0))
        html = await tab.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        dettagli = {"Editore": "Hachette", "Titolo": "N/D", "Autore": "N/D", "Descrizione": "N/D", "Copertina": "N/D", "Link": link}
        
        h1 = soup.find('h1')
        if h1: dettagli["Titolo"] = h1.get_text(strip=True)
            
        author_tag = soup.find(class_=re.compile(r'author|contributor', re.I))
        if author_tag:
            testo_autore = author_tag.get_text(strip=True)
            parti = re.split(r'(?i)by\s+', testo_autore)
            dettagli["Autore"] = parti[-1].strip() if len(parti) > 1 else testo_autore
            
        desc_box = soup.find(id=re.compile(r'description|about', re.I)) or soup.find(class_=re.compile(r'description|about|summary', re.I))
        if desc_box:
            for btn in desc_box.find_all(['button', 'a']): btn.decompose()
            dettagli["Descrizione"] = desc_box.get_text(separator=' ', strip=True)
            
        img_tag = soup.find('img', class_=re.compile(r'cover|product|book', re.I))
        if img_tag:
            dettagli["Copertina"] = img_tag.get('data-src') or img_tag.get('src') or ""
            
        risultati.append(dettagli)
        
    return risultati

# ==========================================
# 💾 SINCRONIZZATORE CSV (Aggiunge i nuovi e rimuove gli spariti)
# ==========================================
def sincronizza_csv_editore(nuovi_dati, nome_editore):
    """
    Sostituisce TUTTI i libri del determinato editore con quelli appena scaricati.
    I vecchi libri che non ci sono più vengono eliminati in automatico.
    Se un libro c'era già, conserva la sua Data_Aggiunta originale.
    """
    if not nuovi_dati:
        print(f"⚠️ Attenzione: Nessun dato trovato per {nome_editore}. Mantengo lo storico invariato per sicurezza.")
        return

    oggi_str = datetime.now().date().isoformat()
    df_nuovi = pd.DataFrame(nuovi_dati)
    df_nuovi['Categoria'] = 'Novità'

    if os.path.exists(CSV_FILENAME):
        df_vecchio = pd.read_csv(CSV_FILENAME)

        # Separiamo gli altri editori da quello che stiamo processando
        df_altri = df_vecchio[df_vecchio['Editore'] != nome_editore]
        df_vecchio_editore = df_vecchio[df_vecchio['Editore'] == nome_editore]

        # Creiamo un dizionario delle date dei libri che già avevamo
        date_storiche = dict(zip(df_vecchio_editore['Link'], df_vecchio_editore['Data_Aggiunta']))

        # Assegnamo le date: se c'era già, riprendi la vecchia. Se non c'è, usa la data di oggi.
        df_nuovi['Data_Aggiunta'] = df_nuovi['Link'].apply(lambda x: date_storiche.get(x, oggi_str))
        # È "Nuovo" solo se non era nel dizionario storico
        df_nuovi['Nuovo'] = df_nuovi['Link'].apply(lambda x: False if x in date_storiche else True)

        # Ricomponiamo il puzzle: altri editori + le novità (i vecchi di questo editore non presenti in df_nuovi vengono cestinati)
        df_completo = pd.concat([df_altri, df_nuovi], ignore_index=True)

    else:
        # Se il CSV non esiste proprio, sono tutti nuovi!
        df_nuovi['Data_Aggiunta'] = oggi_str
        df_nuovi['Nuovo'] = True
        df_completo = df_nuovi

    # Riordiniamo le colonne in modo pulito
    cols = ['Nuovo', 'Categoria', 'Data_Aggiunta', 'Editore', 'Copertina', 'Titolo', 'Autore', 'Descrizione', 'Link']
    esistenti = [c for c in cols if c in df_completo.columns]
    df_completo = df_completo[esistenti]

    df_completo.to_csv(CSV_FILENAME, index=False)
    print(f"🔄 {nome_editore} sincronizzato sul CSV. {len(df_nuovi)} titoli correnti.")


async def main():
    cartella_temporanea = tempfile.mkdtemp()
    print(f"🚀 Creazione browser stealth in corso...")
    
    browser = await uc.start(
        headless=False, 
        no_sandbox=True, 
        user_data_dir=cartella_temporanea,
        browser_args=['--disable-dev-shm-usage', '--disable-gpu']
    )
    tab = browser.main_tab 
    
    try:
        # PENGUIN
        libri_penguin = await get_penguin_releases(tab)
        sincronizza_csv_editore(libri_penguin, "Penguin Random House")
        
        # HARPERCOLLINS
        libri_harper = await get_harper_releases(tab)
        sincronizza_csv_editore(libri_harper, "HarperCollins")
        
        # SIMON & SCHUSTER
        libri_simon = await get_simon_releases(tab)
        sincronizza_csv_editore(libri_simon, "Simon & Schuster")
        
        # MACMILLAN
        libri_macmillan = await get_macmillan_releases(tab)
        sincronizza_csv_editore(libri_macmillan, "Macmillan")
        
        # HACHETTE
        libri_hachette = await get_hachette_releases(tab)
        sincronizza_csv_editore(libri_hachette, "Hachette")
        
    except Exception as e:
        print(f"⚠️ Errore durante l'esecuzione: {e}")
    finally:
        browser.stop()
        
    print("\n" + "="*70)
    print(f"🎉 SINCRONIZZAZIONE COMPIUTA!")
    print("="*70)

if __name__ == "__main__":
    try:
        uc.loop().run_until_complete(main())
    except Exception as e:
        print(f"❌ ERRORE CRITICO: {e}")
    finally:
        input("\nPremi INVIO per chiudere...")
