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
from utils import *

from dotenv import load_dotenv
load_dotenv()  ## load all our environment variables
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# api_key = st.secrets["GOOGLE_API_KEY"]
# genai.configure(api_key=api_key)


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

Retrouve les  éléments suivants dans le CV :
- L'année de diplomation
- La durée totale d'expérience professionnelle cumulée en années
- Les 5 compétences techniques data clés
- Si le candidat est freelance ou non.

Je veux une réponse en un seul string ayant la structure suivante :
{{"Freelance" : "OUI/NON", "Année de diplomation": "YYYY", "Expérience": "X", "Compétences": "compétence1, compétence2, compétence3, compétence4, compétence5"}}

Pour l'année de diplomation, fais attention car parfois une formation est spécifiée avec les dates de début et de fin.
Par exemple : 09/2022 - 06/2024 ou bien 2021 à 2022. Dans ces cas-là, il faut aller chercher l'année de fin, c'est-à-dire
respectivement 2024 et 2022. De plus il peut y avoir plusieurs diplômes, dans ce cas, il faut prendre le plus récent.

Pour la durée d'expérience, merci de ne pas compter les stages ou alternances, seulement les expériences professionnelles.
Par exemple, si le candidat a travaillé 6 mois en stage et 2 ans et demi en CDI, merci de renvoyer 2,5.

CV: {text}
"""


def analysis_page():
    st.title("Analyse des CV")
    
    # Initialisation du stockage des résultats dans session_state
    if "analysis_results" not in st.session_state:
        st.session_state["analysis_results"] = None

    # Upload files via drag-and-drop
    uploaded_files = st.file_uploader(
        "Glissez-déposez vos fichiers .msg ici :", 
        type=["msg"], 
        accept_multiple_files=True
    )

    # # Affichage des résultats si déjà en mémoire
    # if st.session_state["analysis_results"] is not None:
    #     st.dataframe(st.session_state["analysis_results"])

    # Si des fichiers sont importés, réinitialiser la DataFrame stockée
    if uploaded_files:
        st.session_state["analysis_results"] = None

    # Affichage des résultats uniquement s'ils existent et qu'aucun fichier n'est en cours de traitement
    if st.session_state["analysis_results"] is not None and not uploaded_files:
        st.dataframe(st.session_state["analysis_results"])

    if uploaded_files:
        st.session_state["analysis_results"] = None  # Réinitialiser la DataFrame stockée

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

                # Extract the date from the email
                date_envoi = msg.date

                # Extract LinkedIn title and LinkedIn address
                title, address = extract_linkedin_infos(msg)

                # Resume extraction
                final_path = getResume(msg, cvs_folder)

                if not final_path :
                    logging.error(f"Skipping email {filename}, no valid CV found.")

                    all_responses.append(
                        {
                            "Date": date_envoi,
                            "Job": job_name,
                            "Nom": " ".join(noms_from_email),
                            "Titre LinkedIn": title,
                            "Adresse": address,
                            "Mail": "N/A",
                            "Téléphone": "N/A",
                            "Freelance": "N/A",
                            "Diplôme": "N/A",
                            "Expérience": "N/A",
                            "Compétences Tech": "N/A",
                        }
                    )
                else:  # If a file has been successfully saved
                    _, extension = os.path.splitext(final_path)
                    if extension == ".pdf":
                        text_cv = extract_text_from_pdf(final_path)
                    elif extension == ".docx":
                        text_cv = extract_text_from_docx(final_path)

                    # Mail + phone extraction, and anonymization
                    text_anonymise, extracted_email, extracted_phone = anonymize_cv(
                        text_cv, [name for name in noms_from_email if len(name) > 2]
                    )

                    if text_anonymise == "": # If the PDF is an image
                        all_responses.append(
                            {
                                "Date": date_envoi,
                                "Job": job_name,
                                "Nom": " ".join(noms_from_email),
                                "Titre LinkedIn": title,
                                "Adresse": address,
                                "Mail": "N/A",
                                "Téléphone": "N/A",
                                "Freelance": "N/A",
                                "Diplôme": "N/A",
                                "Expérience": "N/A",
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
                                "Date": date_envoi,
                                "Job": job_name,
                                "Nom": " ".join(noms_from_email),
                                "Titre LinkedIn": title,
                                "Adresse": address,
                                "Mail": extracted_email,
                                "Téléphone": extracted_phone,
                                "Freelance": response["Freelance"],
                                "Diplôme": response["Année de diplomation"],
                                "Expérience": response["Expérience"],
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
        df = df.sort_values(by=["Job", "Date"], ascending=[True, True]).reset_index(drop=True)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")  # Reformatage après tri

        # Fonction de mise en forme
        def highlight_rows(row):
            color = ""
            if str(row["Diplôme"]).isdigit() and int(row["Diplôme"]) <= 2020:
                color = "background-color: lightgreen"
            if row["Freelance"] == "OUI":
                color = "background-color: lightblue"
            return [color] * len(row)

        # Appliquer le style
        styled_df = df.style.apply(highlight_rows, axis=1)

        # Afficher dans Streamlit
        st.dataframe(styled_df)

        # Sauvegarde des résultats
        st.session_state["analysis_results"] = styled_df


        if os.path.exists(cvs_folder):
            shutil.rmtree(cvs_folder)  # Remove folder and its content
            os.makedirs(cvs_folder)  # Recreate folder if another script needs it
