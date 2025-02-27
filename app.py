import streamlit as st
import os
from upload import upload_page
from gestion import gestion_page


# from dotenv import load_dotenv
# load_dotenv()  ## load all our environment variables
# PASSWORD = os.getenv("PASSWORD")

PASSWORD = st.secrets["PASSWORD"]

st.set_page_config(layout="wide")  # Wide mode by default

# Inject custom CSS to set the width of the sidebar
st.markdown(
    """
    <style>
        section[data-testid="stSidebar"] {
            width: 189px !important;
            min-width: 50px;
            max-width: 250px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

def login():
    st.title("🔐 Connexion")
    password_input = st.text_input("Mot de passe :", type="password")

    if st.button("Se connecter"):
        if password_input == PASSWORD:
            st.success("✅ Accès autorisé !")
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Upload"  # Page par défaut après connexion


if not st.session_state["authenticated"]:
    login()
else:
    # Barre latérale avec boutons de navigation
    if st.sidebar.button("📩 Importation"):
        st.session_state["current_page"] = "Upload"
    if st.sidebar.button("🗂️ Candidatures"):
        st.session_state["current_page"] = "Applications"
    
    # Affichage de la page sélectionnée
    if st.session_state["current_page"] == "Upload":
        upload_page()
    elif st.session_state["current_page"] == "Applications":
        gestion_page()