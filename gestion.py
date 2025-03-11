from bson import ObjectId
import streamlit as st
import pandas as pd
from config import collection
from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_pdf_viewer import pdf_viewer

@st.dialog("Fiche candidat")
def open_fiche_candidat(candidate_id):
    """Load and diaplay Resume from MongoDB"""
    candidate = collection.find_one({"_id": ObjectId(candidate_id)}, {"CV": 1, "Nom": 1, "Job": 1})

    if candidate:
        col1, col2 = st.columns([2, 1])  # Width : 2/3 for PDF, 1/3 for the side text
        with col1:
            if "CV" in candidate and candidate["CV"]:
                pdf_viewer(candidate["CV"], width="100%")
            else:
                st.warning("Aucun CV disponible pour ce candidat.")
        with col2:
            st.subheader("Ici on pourrait afficher et éditer des infos sur le candidat")
            st.write("On pourrait également naviguer entre les fiches avec des flèches")
            st.write("Vue candidat 360 directement ici ? avec la liste des candidatures")

            st.write(f"**Nom :** {candidate["Nom"]}")
            st.write(f"**Job :** {candidate["Job"]}")
            # TODO : display other informations

    else:
        st.error("Impossible de récupérer le CV.")

# @st.cache_data(ttl=60)
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
        app_list = list(
            collection.find(query, projection)
            .collation({"locale": "fr", "strength": 1})
            .sort(sort_criteria)
            .skip(skip)
            .limit(limit)
        )
    else:
        app_list = list(
            collection.find(query, projection)
            .collation({"locale": "fr", "strength": 1})
            .skip(skip)
            .limit(limit)
        )

    if app_list:
        df = pd.DataFrame(app_list)
        df["Téléphone"] = df["Téléphone"].apply(lambda x: str(x) if pd.notna(x) else "")
        df["_id"] = df["_id"].apply(str)  # Convert ObjectId to string
        cols = [col for col in df.columns if col != "_id"] + ["_id"]
        return df[cols]
    return pd.DataFrame()


def gestion_page():
    """Main function"""
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
        3: "✅ Go process",
    }

    ### FILTER DEFINITION ###

    col1, col2, col3 = st.columns(3)
    with col1:
        statut_filter = st.selectbox(
            "📌 Statut",
            ["Tous"] + list(STATUT_MAPPING.values()),
            on_change=lambda: st.session_state.update(page=0),
        )

    with col2:
        date_selection = st.date_input(
            "📅 Période de candidature",
            value=[],
            format="DD/MM/YYYY",
            on_change=lambda: st.session_state.update(page=0),
        )

    with col3:
        job_filter = st.selectbox(
            "💼 Job",
            ["Tous"] + collection.distinct("Job"),
            on_change=lambda: st.session_state.update(page=0),
        )

    col4, col5 = st.columns(2)
    with col4:
        freelance_filter = st.selectbox(
            "👨‍💻 Freelance",
            ["Tous", "OUI", "NON"],
            index=0,
            on_change=lambda: st.session_state.update(page=0),
        )

    with col5:
        experience_min, experience_max = st.slider(
            "📈 Expérience (années)",
            min_value=-1,
            max_value=30,
            value=(-1, 30),
            step=1,
            on_change=lambda: st.session_state.update(page=0),
        )

    ### FILTER APPLICATION ###

    filters = {}
    if statut_filter != "Tous":
        filters["Statut"] = {v: k for k, v in STATUT_MAPPING.items()}[statut_filter]

    if len(date_selection) == 2:
        # Streamlit date_input returns midnight for both start and end date.
        # We need to include end_date in the filter, that's why we add one day to end date.
        start_date, end_date = pd.Timestamp(date_selection[0]), pd.Timestamp(date_selection[1]) + pd.Timedelta(days=1)
        filters["Date"] = {"$gte": start_date, "$lte": end_date}

    if job_filter != "Tous":
        filters["Job"] = job_filter

    if freelance_filter in ["OUI", "NON"]:
        filters["Freelance"] = freelance_filter

    filters["Expérience"] = {"$gte": experience_min, "$lte": experience_max}

    ### SORT AND TEXTUAL FILTER ###

    col_tri, col_search = st.columns(2)

    with col_tri:
        sort_columns = st.multiselect(
            "↕️ Trier par :",
            collection.find_one().keys(),
            placeholder="Choisir une colonne",
            on_change=lambda: st.session_state.update(page=0),
        )
        sort_orders = [
            st.checkbox(
                f"Ordre croissant pour {col}",
                value=True,
                on_change=lambda: st.session_state.update(page=0),
            )
            for col in sort_columns
        ]

    with col_search:
        col_field, col_query = st.columns([2, 3])
        with col_field:
            searchable_columns = ["Nom", "Titre LinkedIn", "Compétences Tech", "Entreprises", "Adresse"]
            selected_column = st.selectbox("🔍 Rechercher par :", searchable_columns)
        with col_query:
            # Input field
            search_query = st.text_input(
                "Champ de recherche",
                placeholder="Entrez votre recherche...",
                label_visibility="hidden",
            )

    # Apply the filter if the input field is not empty
    if search_query:
        filters[selected_column] = {"$regex": search_query, "$options": "i"}

    ### LOADIND DATA
    df = load_data(skip, page_size, filters, sort_columns, sort_orders)

    ### CORE AND NAVIGATION BUTTONS DEFINITION ###

    col_pag1, col_pag2, col_pag3, col_pag4, col_pag5, col_pag6, col_pag7, col_pag8 = (
        st.columns([4, 4, 4, 2, 1, 1, 1, 1])        # Buttons width
    )

    with col_pag5:      # First page
        if st.button("⏮️"):
            st.session_state.page = 0
            st.rerun()

    with col_pag6:      # Previous page
        if st.button("⬅️") and st.session_state.page > 0:
            st.session_state.page -= 1
            st.rerun()

    with col_pag7:      # Next page
        if st.button("➡️") and len(df) == page_size:
            st.session_state.page += 1
            st.rerun()

    if not df.empty:

        TOTAL_DOCS = collection.count_documents(filters)  # This computation is done only once
        total_pages = (TOTAL_DOCS // page_size) + (1 if TOTAL_DOCS % page_size != 0 else 0)

        with col_pag8:      # Last page
            if st.button("⏭️"):
                st.session_state.page = total_pages - 1
                st.rerun()

        current_page = st.session_state.page + 1

        with col_pag4:      # Pagination
            st.write(f"Page {current_page}/{total_pages}")

        df["Statut"] = df["Statut"].map(STATUT_MAPPING)

        ### AGGRID CONFIGURATION ###

        gb = GridOptionsBuilder.from_dataframe(df)

        # Default settings for all columns
        gb.configure_default_column(editable=True, filterable=True, sortable=True)

        # Specific columns with advanced options
        gb.configure_column(
            "Statut",
            maxWidth=100,
            pinned=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": list(STATUT_MAPPING.values())},
            singleClickEdit=True,  # Enable editting with one click
            suppressKeyboardEvent=True,
            suppressRowClickSelection=True, # Prevents AG Grid from blocking immediate editing
        )

        gb.configure_column(
            "",     # Column for row selection with checkboxes
            maxWidth=50,
            checkboxSelection=True,
            headerCheckboxSelection=True,
            pinned=True,
        )

        gb.configure_column(
            "Date",
            maxWidth=150,
            type=["customDateTimeFormat"],
            custom_format_string="dd MMM yyyy",
        )

        # Other columns
        gb.configure_column("Titre LinkedIn", maxWidth=400)
        gb.configure_column("Freelance", maxWidth=100) 
        gb.configure_column("Téléphone", maxWidth=100) 
        gb.configure_column("Diplôme", maxWidth=100)
        gb.configure_column("Expérience", maxWidth=110, filter=False)
        gb.configure_column("Compétences Tech", minWidth=400) 
        
        # Configure row selection (enable multi-selection without checkboxes)
        gb.configure_selection("multiple", use_checkbox=False)

        # Build and display the grid
        grid_options = gb.build()
        grid_response = AgGrid(df, gridOptions=grid_options, height=650)

        selected_rows = grid_response["selected_rows"]

        if selected_rows is not None and not selected_rows.empty:  # Check if some rows are selected

            with col_pag2:
                if st.button("🗑️ Supprimer"):
                    # Convert _id string to ObjectId
                    selected_ids = [ObjectId(id_str) for id_str in selected_rows["_id"]]

                    # Delete the corresponding documents from the Mongo database
                    if selected_ids:
                        collection.delete_many({"_id": {"$in": selected_ids}})
                        st.success(f"{len(selected_ids)} ligne(s) supprimée(s) ✅")
                        # Reload data after deletion
                        st.rerun()

        if selected_rows is not None and len(selected_rows) == 1:
            with col_pag3:
                if st.button("📄 Voir CV"):
                    candidate_id = selected_rows.iloc[0]["_id"]  # Retrieve ID of the applicant
                    open_fiche_candidat(candidate_id)

        edited_df = grid_response["data"]

        # Inverse mapping to put oringal digits in the database
        edited_df["Statut"] = edited_df["Statut"].map({v: k for k, v in STATUT_MAPPING.items()})
        # Convert _id to string for comparison
        edited_df["_id"] = edited_df["_id"].astype(str)

        with col_pag1:
            # Check for modifications
            if not edited_df.reset_index(drop=True).astype(str).equals(df.reset_index(drop=True).astype(str)):
                if st.button("💾 Enregistrer"):

                    # Update the modified documents
                    for _, row in edited_df.iterrows():
                        obj_id = ObjectId(row["_id"])  # Convertir en ObjectId
                        new_data = row.drop("_id").to_dict()  # Remove the ID

                        # Check and reconvert date fields to datetime
                        if "Date" in new_data:
                            new_data["Date"] = pd.to_datetime(new_data["Date"], errors="coerce")

                        collection.update_one({"_id": obj_id}, {"$set": new_data})

                    # Instant reload with updated data
                    st.session_state.df = get_applications()
                    st.rerun()
    else:
        st.write("Aucun candidat trouvé.")
