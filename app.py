import logging
import os
import json
import time
import streamlit as st
import google.generativeai as genai
import pandas as pd
import extract_msg

from google.generativeai.types import GenerationConfig
from dotenv import load_dotenv
from utils import getResume, anonymize_cv, extract_text_from_pdf

load_dotenv()  ## load all our environment variables

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_response(input_text):
    """
    Generates a response using the Gemini generative model with JSON output.

    Args:
        input_text (str): The input string to generate a response for.

    Returns:
        dict: The generated response as a JSON object.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        input_text,
        generation_config=GenerationConfig(
            response_mime_type="application/json"
        ),
    )
    
    return json.loads(response.text)



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
st.title("ATS")

submit = st.button("Submit")

if submit:
    mails_folder = "data/mails"
    cvs_folder = "data/CVs"
    all_responses = []
    batch_size = 15  # Nombre max de requêtes par minute

    # Get the list of all .msg files
    msg_files = [f for f in os.listdir(mails_folder) if f.endswith(".msg")]
    total_mails = len(msg_files)
    processed_mails = 0

    # Initialize progress bar
    progress_bar = st.progress(0)
    progress_text = st.empty()

    # Batch processing .msg files

    for i in range(0, total_mails, batch_size):
        batch_files = msg_files[i:i + batch_size]
    
        for filename in batch_files:
            print(filename)

            # Extract names from the email
            email_name = filename.split("from")[1].split(".msg")[0]
            noms_from_email = email_name.split()
            print("Noms de l'email :", noms_from_email)

            msg_path = os.path.join(mails_folder, filename)
            msg = extract_msg.Message(msg_path)

            # Resume extraction
            final_path = getResume(msg, cvs_folder)

            if not final_path : #Notamment si c'est un word
                logging.error(f"Skipping email {filename}, no valid CV found.")
                response_data = {"Année de diplomation": "N/A", "Compétences": "N/A"}

                all_responses.append(
                {
                    "Mail": "N/A",
                    "Nom": " ".join(noms_from_email),
                    "Diplôme": "N/A",
                    "Compétences Tech": "N/A"
                }
            ) 
            else:  # If a file has been successfully saved
                text_cv = extract_text_from_pdf(final_path)

                # Anonymization
                text_anonymise, extracted_email = anonymize_cv(text_cv, [name for name in noms_from_email if len(name) > 2])

                if text_anonymise == "":
                    all_responses.append(
                        {
                    "Mail": "N/A",
                    "Nom": " ".join(noms_from_email),
                    "Diplôme": "N/A",
                    "Compétences Tech": "N/A"
                    }
                    )

                # print("Texte anonymisé :", text_anonymise)
                # print("Email extrait :", extracted_email)

                else:
                    # Si le CV a du contenu, on le fournit au LLM
                    formatted_prompt = input_prompt.format(text=text_anonymise)
                    response = get_gemini_response(formatted_prompt)
                    print("Réponse : ", response)
                    
                    # response_data = eval(response)  # Assuming the response is a string representation of a dictionary
                    
                    all_responses.append(
                        {
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
            st.text("Pause de 1 minute pour respecter le quota de l'API...")
            time.sleep(60)

    # Create a DataFrame
    df = pd.DataFrame(all_responses)

    # Display the DataFrame as a table
    st.dataframe(df)
