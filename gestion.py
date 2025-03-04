from bson import ObjectId
import streamlit as st
import pandas as pd
from pymongo import MongoClient
import os
from utils import generate_download_link

from dotenv import load_dotenv
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["staging"]
collection = db["data_test"]


# MONGO_URI = st.secrets["MONGO_URI"]
# client = MongoClient(MONGO_URI)
# db = client["ats_database"]
# collection = db["candidatures"]


def get_applications():
    """
    Retrieve applications from the mongodb database and return them as a pandas DataFrame.
    """
    app_list = list(collection.find({}))
    if app_list:
        df = pd.DataFrame(app_list)
        df["Téléphone"] = df["Téléphone"].apply(lambda x: str(x) if pd.notna(x) else "")
        # Put "_id" column at the end
        cols = [col for col in df.columns if col != "_id"] + ["_id"]
        return df[cols]
    return pd.DataFrame()


def gestion_page():

    st.title("Candidatures")

    # # ⚡ Recharger la base MongoDB à chaque rechargement
    # if "df" not in st.session_state:
    st.session_state.df = get_applications()

    df = st.session_state.df  # Utilisation du cache local

    if not df.empty:
        # FILTERS DEFINITION
        col1, col2, col3 = st.columns(3)

        STATUT_MAPPING = {
            0: "🟡 Non traité",
            -1: "❌ Refus",
            1: "📨 Formulaire envoyé",
            2: "🛠️ En cours de qualif.",
            3: "✅ Go process"
        }
        statut_options = ["Tous"] + list(STATUT_MAPPING.values())

        with col1:
            statut_filter = st.selectbox("📌 Statut", statut_options)

        with col2:
            date_selection = st.date_input("📅 Période de candidature", value=[], format="DD/MM/YYYY")

        with col3:
            job_filter = st.selectbox("💼 Job", ["Tous"] + df["Job"].dropna().unique().tolist())

        col4, col5 = st.columns(2)

        with col4:
            freelance_filter = st.selectbox("👨‍💻 Freelance", ["Tous"] + df["Freelance"].dropna().unique().tolist())

        with col5:
            df["Expérience"] = df["Expérience"].fillna(-1)  # Remplace NaN par -1
            experience_min, experience_max = st.slider(
                "📊 Expérience",
                float(df["Expérience"].min()),
                float(df["Expérience"].max()),
                (float(df["Expérience"].min()), float(df["Expérience"].max()))
            )

        # APPLICATION DES FILTRES

        if statut_filter != "Tous":
            statut_numeric = {v: k for k, v in STATUT_MAPPING.items()}[statut_filter]
            df = df[df["Statut"] == statut_numeric]

        # Vérifier si l'utilisateur a sélectionné une période avant d'appliquer le filtre
        if len(date_selection) == 2:
            start_date, end_date = date_selection
            # Convertir en Timestamp fixe l'heure à minuit :pour end_date, il est nécessaire 
            # de rajouter 1 jour et soustraire 1 seconde pour inclure toute la journée
            start_date = pd.Timestamp(start_date)
            end_date = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

            df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]


        if job_filter != "Tous":
            df = df[df["Job"] == job_filter]

        # Fourchette expérience
        df = df[(df["Expérience"] >= experience_min) & (df["Expérience"] <= experience_max)]
        df["Expérience"] = df["Expérience"].replace(-1, float("nan"))  # Remettre NaN

        if freelance_filter != "Tous":
            df = df[df["Freelance"] == freelance_filter]

        # Sélecteur de colonnes pour le tri
        sort_columns = st.multiselect("↕️ Trier par :", df.columns, placeholder="Sélectionnez une ou plusieurs colonnes")

        # Définir l'ordre de tri pour chaque colonne sélectionnée
        sort_orders = [st.checkbox(f"Ordre croissant pour {col}", value=True) for col in sort_columns]

        # Appliquer le tri selon l'ordre sélectionné
        if sort_columns:
            df = df.sort_values(by=sort_columns, ascending=sort_orders)

        df = df.reset_index(drop=True)  # Évite la colonne d'index après filtrage

        df["CV"] = df["_id"].apply(lambda oid: generate_download_link(collection.find_one({"_id": oid}).get("CV")))


        # Création de colonnes pour afficher la DataFrame et les liens CV côte à côte
        col_cv, col_df = st.columns([1, 30])  # Ajuste les proportions selon tes préférences

        with col_cv:
            st.markdown('<div style="height: 44px;"></div>', unsafe_allow_html=True)  # Ajoute un espace blanc
            # Utilisation de st.markdown() pour rendre les liens cliquables
            for i, row in df.iterrows():
                st.markdown(
            f'<div style="margin-bottom: 9.2px;">{row["CV"]}</div>', 
            unsafe_allow_html=True
        )

        # Transformation des statuts en affichage lisible avec emojis
        df["Statut"] = df["Statut"].map(STATUT_MAPPING)

        # Options du menu déroulant (clé = affichage, valeur = stockage en base)
        statut_options = {v: k for k, v in STATUT_MAPPING.items()}

        with col_df:
        
            edited_df = st.data_editor(
                df.drop(columns=["CV"]),
                column_config={
                    "CV": st.column_config.TextColumn("CV", help="Cliquez pour télécharger"),
                    "Date": st.column_config.DatetimeColumn(
                        "Date", format="D MMM YYYY", step=60
                    ),
                    "Statut": st.column_config.SelectboxColumn(
                        "Statut",
                        options=list(statut_options.keys()),
                        required=True,
                        pinned=True,
                    ),
                },
                height=2000,
                # hide_index=True,
                num_rows="dynamic",
            )  # Édition interactive

        # Convertir les statuts affichés (emoji) en valeurs numériques avant enregistrement
        edited_df["Statut"] = edited_df["Statut"].map(statut_options)

        # Sauvegarde des ID avant édition
        original_ids = set(df["_id"].astype(str))

        # Convertir _id en string pour comparaison
        edited_df["_id"] = edited_df["_id"].astype(str)
        remaining_ids = set(edited_df["_id"])

        # Détection des suppressions
        deleted_ids = original_ids - remaining_ids  # Différence entre avant/après

        # Vérification des modifications
        if not edited_df.reset_index(drop=True).astype(str).equals(df.reset_index(drop=True).astype(str)) or deleted_ids:
            if st.button("💾 Enregistrer les modifications"):
                # Suppression des documents supprimés
                for deleted_id in deleted_ids:
                    collection.delete_one({"_id": ObjectId(deleted_id)})

                # Mise à jour des documents modifiés
                for _, row in edited_df.iterrows():
                    obj_id = ObjectId(row["_id"])  # Convertir en ObjectId
                    new_data = row.drop("_id").to_dict()  # Retirer l'ID
                    collection.update_one({"_id": obj_id}, {"$set": new_data})

                # 🔄 Recharger immédiatement les données mises à jour
                st.session_state.df = get_applications()

                # ✅ Redessiner Streamlit sans recharger toute la page
                st.rerun()
    else:
        st.write("Aucun candidat trouvé.")
