import re
import os
import PyPDF2 as pdf
import logging


def getResume(msg, cvs_folder):
    """
    Processes the attachments in the provided message to retrieve a resume.
    Args:
        msg: The message object containing attachments.
        cvs_folder: The folder where the resume should be saved.
    Raises:
        ValueError: If an attachment's name is None.
        Exception: If there are no attachments, or if an attachment's extension is not .pdf,
                   or if there is an error when getting the resume.
    Logs:
        Info: Logs the number of attachments if present.
        Error: Logs errors related to attachment name, unsupported extension,
               absence of attachments, and general errors when getting the resume.
    """

    try:
        # Check for any attachments
        if msg.attachments:
            logging.info("There is %d attachement(s)....", len(msg.attachments))

            for attachment in msg.attachments:

                if attachment.longFilename is None:
                    logging.error("attachement name is None")
                    raise ValueError("attachement name is None")

                _, extension = os.path.splitext(attachment.longFilename)

                if extension != ".pdf":
                    logging.error(f"Unsupported extension {extension}")
                    return None

                # Temporary save
                attachment.save(customFilename=attachment.longFilename)

                # Move the file to the correct folder
                saved_path = os.path.join(
                    os.getcwd(), attachment.longFilename
                )  # Chemin où le fichier a été sauvegardé
                final_path = os.path.join(
                    cvs_folder, attachment.longFilename
                )  # Chemin final

                # If the file already exists, remove it
                if os.path.exists(final_path):
                    logging.info(f"Replacing existing file: {final_path}")
                    os.remove(final_path)

                os.rename(saved_path, final_path)
                return final_path
        else:
            logging.error("No attachment found")
            return None

    except Exception as e:
        logging.error(f"Error when getting resume: {e}")
        raise None


def extract_text_from_pdf(file):
    """
    Extracts text from a PDF file.

    Args:
        file (str): The path to the PDF file.

    Returns:
        str: The extracted text from the PDF, with newlines replaced by spaces and leading/trailing whitespace removed.
    """
    reader = pdf.PdfReader(file)
    text = ""
    for _, page in enumerate(reader.pages):
        text += str(page.extract_text())
    text = text.replace("\x00", "").replace("\n", " ").strip()
    return text

def anonymize_cv(text_cv, noms_from_email):
    # 1. Extraction de l'email avant anonymisation
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_cv)
    extracted_email = email_match.group(0) if email_match else None

    # 2. Suppression du nom et prénom, même s'ils sont collés à d'autres mots
    for nom in sorted(noms_from_email, key=len, reverse=True):  # Trier pour éviter les conflits
        text_cv = re.sub(rf'(?i){re.escape(nom)}', '[ANONYMISÉ]', text_cv)

    # 3. Suppression de l'email (remplacement après extraction)
    text_cv = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', text_cv)

    # 4. Suppression des numéros de téléphone
    # text_cv = re.sub(r'\b(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b', '[TÉL]', text_cv)
    text_cv = re.sub(r'(?<!\d)(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}', '[TÉL]', text_cv)

    # 5. Suppression de l'adresse postale (basique, peut être affiné)
    text_cv = re.sub(r'\d{1,5}\s+\w+(?:\s+\w+)*(?:,\s*\w+(?:\s+\w+)*)?,?\s*\d{5}', '[ADRESSE]', text_cv)

    return text_cv, extracted_email  # On retourne le texte anonymisé + l'email extrait

