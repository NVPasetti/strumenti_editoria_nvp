import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from supabase import create_client, Client

# 1. Recupero le credenziali segrete da GitHub
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
EMAIL_MITTENTE = os.environ.get("EMAIL_MITTENTE")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DESTINATARIO")

# 2. Connessione a Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Errore connessione Supabase: {e}")
    exit()

# 3. Analisi scadenze
oggi = datetime.now().date()
try:
    risposta = supabase.table("reminders").select("*").execute()
    reminders = risposta.data
except Exception as e:
    print(f"Errore lettura database: {e}")
    exit()

libri_scaduti = []

for r in reminders:
    scadenza = datetime.fromisoformat(r["data_scadenza"]).date()
    if scadenza <= oggi:
        libri_scaduti.append(r)

# 4. Invio Email (se ci sono libri scaduti)
if libri_scaduti:
    print(f"Trovati {len(libri_scaduti)} libri da notificare. Preparazione email...")
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 Radar Editoriale: {len(libri_scaduti)} libri da verificare!"
    msg["From"] = EMAIL_MITTENTE
    msg["To"] = EMAIL_DESTINATARIO

    # Corpo della mail in HTML
    html_body = """
    <h2>⏰ Tempo scaduto per i tuoi monitoraggi!</h2>
    <p>I seguenti libri sono usciti da almeno 30 giorni. È il momento di controllare come stanno andando su Amazon:</p>
    <ul>
    """
    for libro in libri_scaduti:
        # Recupero l'autore (se è un vecchio salvataggio senza autore, metto N/D)
        autore = libro.get('autore', 'N/D')
        
        # Aggiunta dell'autore nel corpo della mail
        html_body += f"""
        <li style="margin-bottom: 10px;">
            <b>{libro['titolo']}</b><br>
            <span style="color: #555555; font-size: 0.9em;">di {autore}</span> - 
            <a href="{libro['id']}">Vedi su IBS</a>
        </li>
        """
    
    html_body += "</ul><p><i>Buon lavoro di scouting!</i></p>"

    part = MIMEText(html_body, "html")
    msg.attach(part)

    try:
        # Configurazione server Gmail
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_MITTENTE, EMAIL_PASSWORD)
        server.sendmail(EMAIL_MITTENTE, EMAIL_DESTINATARIO, msg.as_string())
        server.quit()
        print("✅ Email inviata con successo!")

        # 5. Cancella i libri notificati dal database
        for libro in libri_scaduti:
            supabase.table("reminders").delete().eq("id", libro["id"]).execute()
        print("✅ Database pulito dai reminder scaduti.")

    except Exception as e:
        print(f"❌ Errore durante l'invio dell'email: {e}")
else:
    print("Oggi nessun libro ha raggiunto i 30 giorni. Nessuna email inviata.")
