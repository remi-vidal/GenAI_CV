import logging
import os
import streamlit as st
import google.generativeai as genai
import PyPDF2 as pdf
import pandas as pd
import extract_msg

from dotenv import load_dotenv

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
    model = genai.GenerativeModel("gemini-1.5-flash")
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

                if attachment.longFilename == None:
                    logging.error("attachement name is None")
                    raise ValueError("attachement name is None")


                _, extension = os.path.splitext(attachment.longFilename)

                if extension != ".pdf":
                    logging.error(f"Unsupported extension {extension}")
                    raise Exception(f"Extension {attachment.longFilename} not PDF")
                else:
                    attachment.save(customFilename=attachment.longFilename)

                    # Move the file to the correct folder
                    saved_path = os.path.join(os.getcwd(), attachment.longFilename)  # Chemin où le fichier a été sauvegardé
                    final_path = os.path.join(cvs_folder, attachment.longFilename)   # Chemin final

                    # If the file already exists, remove it
                    if os.path.exists(final_path):
                        logging.info(f"Replacing existing file: {final_path}")
                        os.remove(final_path)


                    os.rename(saved_path, final_path)

        else:
            logging.error(f"There is no attachement")
            raise Exception(f"There is no attachement")


    except Exception as e:
        logging.error(f"Error when getting resume")
        raise Exception(f"Error when getting resume")


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
    text = text.replace("\n", " ").strip()
    return text


# Prompt Template
input_prompt = """ 
Retrouve l'email, l'année de diplomation et les compétences clés dans le CV ci-dessous.

Pour l'année, merci de fournir une réponse avec seulement les 4 chiffres de l'année, sans aucun autre caractère.

CV: {text}

Je veux une réponse en un seul string ayant la structure suivante :
{{"Mail": "exemple@email.com", "Année de diplomation": "YYYY", "Compétences": "compétence1, compétence2, ..."}}

Merci de respecter la structure demandée ! Ne rajoute pas "json" devant.
"""

## streamlit app
st.title("ATS")

submit = st.button("Submit")

if submit:
    mails_folder = "data/mails"
    cvs_folder = "data/CVs"
    all_responses = []

    # Process all .msg files in the mails folder
    for filename in os.listdir(mails_folder):
        print(filename)
        if filename.endswith(".msg"):
            msg_path = os.path.join(mails_folder, filename)
            msg = extract_msg.Message(msg_path)
            getResume(msg, cvs_folder)

    # Process all PDF files in the CVs folder
    for filename in os.listdir(cvs_folder):
        if filename.endswith(".pdf"):
            file_path = os.path.join(cvs_folder, filename)
            text = extract_text_from_pdf(file_path)
            formatted_prompt = input_prompt.format(text=text)
            response = get_gemini_response(formatted_prompt)
            response_data = eval(response)  # Assuming the response is a string representation of a dictionary
            all_responses.append(response_data)

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
