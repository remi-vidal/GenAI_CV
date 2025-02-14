import imaplib
import email
import os
from getpass import getpass

# Configuration de la boîte mail
IMAP_SERVER = "outlook.office365.com"
IMAP_PORT = 993
EMAIL_ACCOUNT = "rvidal@aubay.com"
EMAIL_PASSWORD = getpass()

# Dossier local pour sauvegarder les emails
SAVE_FOLDER = r"C:\Users\rvidal\GenAI_CV\data\mails"
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

# Connexion au serveur IMAP
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)

# Sélection du dossier (Inbox, Sent, etc.)
mail.select("LinkedIn")

# Récupération des emails
status, email_ids = mail.search(None, "ALL")  # "ALL" pour tous les emails

if status == "OK":
    email_ids = email_ids[0].split()
    for i, e_id in enumerate(email_ids):
        # Récupération de l'email brut
        status, data = mail.fetch(e_id, "(RFC822)")
        if status == "OK":
            raw_email = data[0][1]

            # Convertir en format email
            msg = email.message_from_bytes(raw_email)
            subject = msg.get("Subject", "Sans Sujet").replace(":", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "")
            filename = f"{i}_{subject}.eml"
            save_path = os.path.join(SAVE_FOLDER, filename)

            # Sauvegarder l'email au format .eml
            with open(save_path, "wb") as f:
                f.write(raw_email)

            print(f"Email enregistré : {filename}")

# Déconnexion
mail.logout()
