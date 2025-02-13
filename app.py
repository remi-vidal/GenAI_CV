import os
import streamlit as st
import google.generativeai as genai
import PyPDF2 as pdf
import pandas as pd  # Import pandas

from dotenv import load_dotenv

load_dotenv()  ## load all our environment variables

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_repsonse(input):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(input)
    return response.text


def extract_text_from_pdf(file):
    
    reader = pdf.PdfReader(file)

    text = ""
    
    for _, page in enumerate(reader.pages):
        text += str(page.extract_text())
    
    # Nettoyer le texte
    text = text.replace("\n", " ").strip()

    return text


# Prompt Template

input_prompt = """ 
Retrouve l'email, l'année de diplomation et les compétences clés dans le CV ci-dessous.

Pour l'année, merci de fournir une réponse avec seulement les 4 chiffres de l'année, sans aucun autre caractère.

CV: {text}

Je veux une réponse en un seul string ayant la structure suivante :
{{"Mail":"","Année de diplomation":"", "Compétences":""}}
"""

## streamlit app
st.title("ATS")
uploaded_file = st.file_uploader(
    "Upload Your Resume", type="pdf", help="Please upload the pdf"
)

submit = st.button("Submit")

if submit:
    if uploaded_file is not None:
        text = extract_text_from_pdf(uploaded_file)

        formatted_prompt = input_prompt.format(text=text)
        print(formatted_prompt)
        response = get_gemini_repsonse(formatted_prompt)
        
        # Parse the response to extract email and graduation year
        response_data = eval(response)  # Assuming the response is a string representation of a dictionary
        
        # Create a DataFrame
        df = pd.DataFrame([response_data])
        
        # Save the DataFrame to an Excel file
        excel_file = "output.xlsx"
        df.to_excel(excel_file, index=False)
        
        # Provide a download link for the Excel file
        st.download_button(
            label="Download Excel",
            data=open(excel_file, "rb").read(),
            file_name=excel_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
