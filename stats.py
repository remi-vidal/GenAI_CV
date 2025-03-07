import streamlit as st
import pandas as pd
from config import collection

def stats_page():
    st.title("Statistiques")

    # Récupérer les données (en supposant que "Date" est au format Date)
    data = list(collection.find({}, {"_id": 0, "Job": 1, "Date": 1}))

    # Transformer en DataFrame Pandas
    df = pd.DataFrame(data)

    # Vérifier la colonne date et la convertir
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        # Ajouter les dimensions temporelles
        df["Année"] = df["Date"].dt.year
        df["Mois"] = df["Date"].dt.strftime("%Y-%m")  # Ex: 2024-03
        df["Jour"] = df["Date"].dt.strftime("%Y-%m-%d")  # Ex: 2024-03-06

        # Affichage des stats
        st.subheader("💼 Candidatures par Job Description")

        # No filter by default 
        df_filtered = df.copy()

        # Filtrage : Job + Groupe temporel + Période
        col1, col2, col3 = st.columns(3)  # Ajustement des largeurs
        with col1:
            unique_jobs = ["Tous"] + sorted(df["Job"].dropna().unique())
            selected_job = st.selectbox("Filtrer par Job Desc :", unique_jobs)

        with col2:
            time_dimension = st.selectbox("Grouper par :", ["Ne pas grouper (nombre total)", "Année", "Mois", "Jour"], index=0)

        with col3:
            date_fourchette = st.date_input("📅 Période de candidature", value=[], format="DD/MM/YYYY")

        # Appliquer le filtre par Job
        if selected_job != "Tous":
            df_filtered = df[df["Job"] == selected_job]

        # Appliquer le filtre temporel si une période est sélectionnée
        if len(date_fourchette) == 2:
            start_date, end_date = date_fourchette
            end_date = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            df_filtered = df_filtered[(df_filtered["Date"] >= pd.Timestamp(start_date)) & (df_filtered["Date"] <= end_date)]

        # Application du groupby selon la dimension temporelle
        if time_dimension == "Ne pas grouper (nombre total)":
            count_by_job = df_filtered["Job"].value_counts().reset_index()
            count_by_job.columns = ["Job", "Nombre de candidatures"]
        else:
            count_by_job = df_filtered.groupby(["Job", time_dimension]).size().reset_index(name="Nombre de candidatures")

        st.dataframe(count_by_job, hide_index=True)

        # Graphiques après filtrage
        count_by_year = df_filtered.groupby("Année").size().reset_index(name="Nombre de candidatures")
        count_by_month = df_filtered.groupby("Mois").size().reset_index(name="Nombre de candidatures")
        count_by_day = df_filtered.groupby("Jour").size().reset_index(name="Nombre de candidatures")

        st.subheader("📅 Candidatures totales par année")
        st.bar_chart(count_by_year.set_index("Année"))

        st.subheader("📆 Candidatures totales par mois")
        st.line_chart(count_by_month.set_index("Mois"))

        st.subheader("📆 Candidatures totales par jour")
        st.area_chart(count_by_day.set_index("Jour"))

    else:
        st.warning("Aucune donnée disponible.")
