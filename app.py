import logging
import os
import re
import io
import json
import time
import streamlit as st
import shutil
import google.generativeai as genai
import google.api_core.exceptions
import pandas as pd
import extract_msg
from google.generativeai.types import GenerationConfig
from utils import getResume, anonymize_cv, extract_text_from_pdf


# from dotenv import load_dotenv
# load_dotenv()  ## load all our environment variables
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)


def get_gemini_response(input_text, max_retries=5, base_wait=30):
    """
    Génère une réponse en gérant les erreurs de quota (429).
    
    Args:
        input_text (str): Texte d'entrée pour le modèle.
        max_retries (int): Nombre maximum de tentatives avant d'abandonner.
        base_wait (int): Temps d'attente initial (en secondes) avant le premier retry.
    
    Returns:
        dict: La réponse du modèle sous forme de JSON.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                input_text,
                generation_config=GenerationConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)  # Retourne la réponse si tout va bien

        except google.api_core.exceptions.ResourceExhausted:
            wait_time = base_wait * (2 ** attempt)  # Exponentiel : 30s, 60s, 120s, 240s...
            st.warning(f"Quota dépassé. Tentative {attempt + 1}/{max_retries}. Réessai dans {wait_time} secondes...")
            time.sleep(wait_time)
            st.empty()

        except Exception as e:
            st.error(f"Erreur inattendue : {e}")
            return {"Année de diplomation": "N/A", "Compétences": "N/A"}  # Valeurs par défaut en cas d'erreur fatale
    
    st.error("Échec après plusieurs tentatives. Veuillez réessayer plus tard.")
    return {"Année de diplomation": "N/A", "Compétences": "N/A"}  # Valeurs par défaut si toutes les tentatives échouent


# Prompt Template
input_prompt = """
Tu joues le rôle d'un recruteur data qui doit extraire des informations clés d'un CV.
Un(e) candidat(e) a envoyé son CV par mail.

Retrouve l'année de diplomation et les 5 compétences techniques data clés dans le CV ci-dessous.

Pour l'année, fais attention car parfois une formation est spécifiée avec les dates de début et de fin.
Par exemple : 09/2022 - 06/2024 ou bien 2021 à 2022. Dans ces cas-là, il faut aller chercher l'année de fin, c'est-à-dire
respectivement 2024 et 2022.

CV: {text}

Je veux une réponse en un seul string ayant la structure suivante :
{{"Année de diplomation": "YYYY", "Compétences": "compétence1, compétence2, compétence3, compétence4, compétence5"}}
"""

## Streamlit app
st.set_page_config(layout="wide")  # Wide mode by default
st.title("ATS")

# Upload files via drag-and-drop
uploaded_files = st.file_uploader(
    "Glissez-Déposez vos fichiers .msg ici", 
    type=["msg"], 
    accept_multiple_files=True
)

if uploaded_files:

    cvs_folder = "CVs"
    all_responses = []
    batch_size = 15  # Nombre max de requêtes par minute

    # Get the list of all .msg files
    total_mails = len(uploaded_files)
    processed_mails = 0

    # Initialize progress bar
    progress_bar = st.progress(0)
    progress_text = st.empty()
    pause_text = st.empty()

    # Batch processing .msg files

    for i in range(0, total_mails, batch_size):
        batch_files = uploaded_files[i:i + batch_size]

        for file in batch_files:
            filename = file.name
            print(f"Processing: {filename}")

            # Extraire le job depuis le nom de l'email
            match = re.search(r'application_ (.*?) from', filename)
            job_name = match.group(1) if match else "Inconnu"

            # Extract names from the email
            email_name = filename.split("from")[1].split(".msg")[0] if "from" in filename else "Inconnu"
            noms_from_email = email_name.split()
            print("Noms de l'email :", noms_from_email)

            # Lecture du fichier .msg directement depuis l'upload
            msg_bytes = file.read()
            msg = extract_msg.Message(io.BytesIO(msg_bytes))

            # Resume extraction
            final_path = getResume(msg, cvs_folder)

            if not final_path : #Notamment si c'est un word
                logging.error(f"Skipping email {filename}, no valid CV found.")
                response_data = {"Année de diplomation": "N/A", "Compétences": "N/A"}

                all_responses.append(
                    {
                        "Job": job_name,
                        "Mail": "N/A",
                        "Nom": " ".join(noms_from_email),
                        "Diplôme": "N/A",
                        "Compétences Tech": "N/A",
                    }
                )
            else:  # If a file has been successfully saved
                text_cv = extract_text_from_pdf(final_path)

                # Anonymization
                text_anonymise, extracted_email = anonymize_cv(text_cv, [name for name in noms_from_email if len(name) > 2])

                if text_anonymise == "":
                    all_responses.append(
                        {
                            "Job": job_name,
                            "Mail": "N/A",
                            "Nom": " ".join(noms_from_email),
                            "Diplôme": "N/A",
                            "Compétences Tech": "N/A",
                        }
                    )

                # print("Texte anonymisé :", text_anonymise)
                # print("Email extrait :", extracted_email)

                else:
                    # Si le CV a du contenu, on le fournit au LLM
                    formatted_prompt = input_prompt.format(text=text_anonymise)
                    response = get_gemini_response(formatted_prompt)
                    print("Réponse : ", response)

                    all_responses.append(
                        {   
                            "Job": job_name,
                            "Mail": extracted_email,
                            "Nom": " ".join(noms_from_email),
                            "Diplôme": response["Année de diplomation"],
                            "Compétences Tech": response["Compétences"],
                        }
                    )  # On retourne le texte anonymisé + l'email et le nom extraits

            # Update progress
            processed_mails += 1
            progress_bar.progress(processed_mails / total_mails)
            progress_text.text(f"{processed_mails} mails traités sur {total_mails}")

        if i + batch_size < total_mails:
            pause_text.text("Pause de 1 minute pour respecter le quota de l'API...")
            time.sleep(60)
            pause_text.empty()  # Clear the pause message after the pause

    # Create a DataFrame
    df = pd.DataFrame(all_responses)
    df = df.sort_values(by="Job").reset_index(drop=True)
    # Display the DataFrame as a table
    st.dataframe(df)


    if os.path.exists(cvs_folder):
        shutil.rmtree(cvs_folder)  # Remove folder and its content
        os.makedirs(cvs_folder)  # Recreate folder if another script needs it