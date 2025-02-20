import logging
import os
import time
import streamlit as st
import google.generativeai as genai
import pandas as pd
import extract_msg

from dotenv import load_dotenv
from utils import anonymize_cv, extract_text_from_pdf

load_dotenv()  ## load all our environment variables

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_response(input):
    """
    Generates a response using the Gemini generative model.

    Args:
        input (str): The input string to generate a response for.

    Returns:
        str: The generated response text.
    """
    # model = genai.GenerativeModel("gemini-1.5-flash")
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(input)
    return response.text


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
                saved_path = os.path.join(os.getcwd(), attachment.longFilename)  # Chemin où le fichier a été sauvegardé
                final_path = os.path.join(cvs_folder, attachment.longFilename)   # Chemin final

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


# Prompt Template
input_prompt = """
Tu joues le rôle d'un recruteur data qui doit extraire des informations clés d'un CV.
Un(e) candidat(e) a envoyé son CV par mail.
Retrouve l'année de diplomation et les 3 compétences techniques clés dans le CV ci-dessous.

CV: {text}

Je veux une réponse en un seul string ayant la structure suivante :
{{"Année de diplomation": "YYYY", "Compétences": "compétence1, compétence2, compétence3"}}
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
    msg_files = [f for f in os.listdir(mails_folder) if f.endswith(".msg")][:5]
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
                    "email": "N/A",
                    "nom": " ".join(noms_from_email),
                    "année": "N/A",
                    "compétences": "N/A"
                }
            ) 
            else:  # If a file has been successfully saved
                text_cv = extract_text_from_pdf(final_path)

                # Anonymization
                text_anonymise, extracted_email = anonymize_cv(text_cv, [name for name in noms_from_email if len(name) > 2])

                if text_anonymise == "":
                    all_responses.append(
                        {
                            "email": "N/A",
                            "nom": " ".join(noms_from_email),
                            "année": "N/A",
                            "compétences": "N/A",
                        }
                    )

                # print("Texte anonymisé :", text_anonymise)
                # print("Email extrait :", extracted_email)

                else:
                    # Si le CV a du contenu, on le fournit au LLM
                    formatted_prompt = input_prompt.format(text=text_anonymise)
                    response = get_gemini_response(formatted_prompt)
                    print("Réponse : ", response)
                    try : 
                        response_data = eval(response)  # Assuming the response is a string representation of a dictionary
                    except:
                        continue
                    all_responses.append(
                        {
                            "email": extracted_email,
                            "nom": " ".join(noms_from_email),
                            "année": response_data["Année de diplomation"],
                            "compétences": response_data["Compétences"],
                        }
                    )  # On retourne le texte anonymisé + l'email et le nom extraits

            # Update progress
            processed_mails += 1
            progress_bar.progress(processed_mails / total_mails)
            progress_text.text(f"Processed {processed_mails} of {total_mails} mails")

        if i + batch_size < total_mails:
            st.text("Pause de 1 minute pour respecter la limite d'API...")
            time.sleep(60)

    # Create a DataFrame
    df = pd.DataFrame(all_responses)
    # Save the DataFrame to a CSV file
    csv_file = "output.csv"
    df.to_csv(csv_file, index=False)

    # Provide a download link for the CSV file
    st.download_button(
        label="Download CSV",
        data=open(csv_file, "rb").read(),
        file_name=csv_file,
        mime="text/csv"
    )
