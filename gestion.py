from bson import ObjectId
import streamlit as st
import pandas as pd
from config import collection


@st.cache_data(ttl=60)  # Cache pendant 60s
def load_data(skip, limit, filters, sort_columns, sort_orders):
    return get_applications(skip, limit, filters, sort_columns, sort_orders)


def get_applications(skip=0, limit=20, filters=None, sort_columns=None, sort_orders=None):
    """
    Retrieve applications from the MongoDB database with pagination, filters, and sorting.
    """
    query = {}
    if filters:
        query.update(filters)
    
    projection = {"CV": 0}  # Exclure le champ CV

    sort_criteria = []
    if sort_columns and sort_orders:
        sort_criteria = [(col, 1 if asc else -1) for col, asc in zip(sort_columns, sort_orders)]
    
    if sort_criteria:
        app_list = list(collection.find(query, projection).sort(sort_criteria).skip(skip).limit(limit))
    else:
        app_list = list(collection.find(query, projection).skip(skip).limit(limit))
    
    if app_list:
        df = pd.DataFrame(app_list)
        df["Téléphone"] = df["Téléphone"].apply(lambda x: str(x) if pd.notna(x) else "")
        cols = [col for col in df.columns if col != "_id"] + ["_id"]
        return df[cols]
    return pd.DataFrame()


def gestion_page():
    st.title("Candidatures")

    if "page" not in st.session_state:
        st.session_state.page = 0

    page_size = 20
    skip = st.session_state.page * page_size

    STATUT_MAPPING = {
        0: "🟡 Non traité",
        -1: "❌ Refus",
        1: "📨 Formulaire envoyé",
        2: "🛠️ En cours de qualif.",
        3: "✅ Go process"
    }

    col1, col2, col3 = st.columns(3)
    statut_options = ["Tous"] + list(STATUT_MAPPING.values())
    with col1:
        statut_filter = st.selectbox("📌 Statut", statut_options, on_change=lambda: st.session_state.update(page=0))

    with col2:
        date_selection = st.date_input("📅 Période de candidature", value=[], format="DD/MM/YYYY", on_change=lambda: st.session_state.update(page=0))

    with col3:
        job_filter = st.selectbox("💼 Job", ["Tous"] + collection.distinct("Job"), on_change=lambda: st.session_state.update(page=0))

    col4, col5 = st.columns(2)
    with col4:
        freelance_filter = st.selectbox("👨‍💻 Freelance", ["Tous", "OUI", "NON"], index=0, on_change=lambda: st.session_state.update(page=0))

    with col5:
        experience_min, experience_max = st.slider(
            "📊 Expérience (années)",
            min_value=-1,
            max_value=30,
            value=(-1, 30),
            step=1,
            on_change=lambda: st.session_state.update(page=0),
        )

    filters = {}
    if statut_filter != "Tous":
        filters["Statut"] = {v: k for k, v in STATUT_MAPPING.items()}[statut_filter]

    if len(date_selection) == 2:
        start_date, end_date = pd.Timestamp(date_selection[0]), pd.Timestamp(date_selection[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        filters["Date"] = {"$gte": start_date, "$lte": end_date}

    if job_filter != "Tous":
        filters["Job"] = job_filter

    if freelance_filter == "OUI":
        filters["Freelance"] = "OUI"
    elif freelance_filter == "NON":
        filters["Freelance"] = "NON"

    filters["Expérience"] = {"$gte": experience_min, "$lte": experience_max}  # Expérience dans la plage sélectionnée

    sort_columns = st.multiselect("↕️ Trier par :", collection.find_one().keys(), on_change=lambda: st.session_state.update(page=0))
    sort_orders = [st.checkbox(f"Ordre croissant pour {col}", value=True, on_change=lambda: st.session_state.update(page=0)) for col in sort_columns]

    df = load_data(skip, page_size, filters, sort_columns, sort_orders)

    col_pag1, col_pag2, col_pag3, col_pag4, col_pag5, col_pag6 = st.columns([13, 2, 1, 1, 1, 1])  # Ajuste la répartition des colonnes



    with col_pag3:
        if st.button("⏮️"):  # Aller à la première page
            st.session_state.page = 0
            st.rerun()

    with col_pag4:
        if st.button("⬅️") and st.session_state.page > 0:
            st.session_state.page -= 1
            st.rerun()

    
    with col_pag5:
        if st.button("➡️") and len(df) == page_size:
            st.session_state.page += 1
            st.rerun()

    with col_pag6:
        total_docs = collection.count_documents(filters)  # Compte total des documents selon les filtres
        last_page = (total_docs // page_size) if total_docs % page_size == 0 else (total_docs // page_size)
        
        if st.button("⏭️"):  # Aller à la dernière page
            st.session_state.page = last_page
            st.rerun()

    if not df.empty:

        total_docs = collection.count_documents(filters)
        total_pages = (total_docs // page_size) + (1 if total_docs % page_size != 0 else 0)
        current_page = st.session_state.page + 1

        with col_pag2:
            st.write(f"Page {current_page}/{total_pages}")


        df["Statut"] = df["Statut"].map(STATUT_MAPPING)

        edited_df = st.data_editor(
            df,
            column_config={
                "Statut": st.column_config.SelectboxColumn(
                    "Statut", options=list(STATUT_MAPPING.values()), required=True, pinned=True
                ),
                "Date": st.column_config.DatetimeColumn("Date", format="D MMM YYYY", step=60),
            },
            height=772,
            num_rows="dynamic",
        )


        # Convertir les statuts affichés (emoji) en valeurs numériques avant enregistrement
        edited_df["Statut"] = edited_df["Statut"].map({v: k for k, v in STATUT_MAPPING.items()})

        # Sauvegarde des ID avant édition
        original_ids = set(df["_id"].astype(str))

        # Convertir _id en string pour comparaison
        edited_df["_id"] = edited_df["_id"].astype(str)
        remaining_ids = set(edited_df["_id"])

        # Détection des suppressions
        deleted_ids = original_ids - remaining_ids  # Différence entre avant/après

        with col_pag1:
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
