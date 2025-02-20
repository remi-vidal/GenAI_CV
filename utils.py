
import re
import PyPDF2 as pdf

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


def remove_accents(text):
    """
    Transforme les caractères accentués en leur équivalent sans accent.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')



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

# Exemple d'utilisation
text_cv = """jean marie dupont
07 86 12 34 56remi4567@holala.com
e0753681353 blabla
la 40 13 rue des Lavandières 13200 Arles"""

noms_from_email = ["Jean", "Dupont", "marie"]

text_anonymise, extracted_email = anonymize_cv(text_cv, noms_from_email)

print("Texte anonymisé :", text_anonymise)
print("Email extrait :", extracted_email)


# print(extract_text_from_pdf("data/CVs/CV SBE.pdf"))