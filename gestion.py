from bson import ObjectId
import streamlit as st
import pandas as pd
from pymongo import MongoClient
import os
from utils import highlight_rows

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
        edited_df = st.data_editor(df, num_rows="dynamic")  # Édition interactive

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