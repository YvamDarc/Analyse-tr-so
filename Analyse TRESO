import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Analyse Trésorerie", layout="centered")

st.title("📊 Analyse de la trésorerie à partir d'un fichier Excel")
st.write("Chargez un fichier Excel contenant les colonnes `Date`, `Débit` et `Crédit`.")

# Upload du fichier
uploaded_file = st.file_uploader("Choisissez un fichier Excel", type=["xlsx"])

if uploaded_file:
    try:
        # Lecture et nettoyage
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        
        if not all(col in df.columns for col in ['Date', 'Débit', 'Crédit']):
            st.error("❌ Le fichier doit contenir les colonnes : 'Date', 'Débit', 'Crédit'")
        else:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Débit'] = pd.to_numeric(df['Débit'], errors='coerce').fillna(0)
            df['Crédit'] = pd.to_numeric(df['Crédit'], errors='coerce').fillna(0)
            df = df.dropna(subset=['Date'])

            # Regroupement par jour
            df_journalier = df.groupby('Date', as_index=False).agg({'Débit': 'sum', 'Crédit': 'sum'})
            df_journalier['Solde_journalier'] = (df_journalier['Débit'] - df_journalier['Crédit']).cumsum()

            st.success("✅ Fichier traité avec succès !")
            st.dataframe(df_journalier.head())

            # Histogramme interactif
            st.subheader("📈 Distribution des soldes journaliers")
            bins = st.slider("Nombre de classes (bins)", min_value=5, max_value=100, value=20, step=5)

            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=df_journalier['Solde_journalier'],
                nbinsx=bins,
                marker_color='steelblue',
                opacity=0.85
            ))

            fig.update_layout(
                title="Distribution des soldes journaliers",
                xaxis_title="Montant du solde (€)",
                yaxis_title="Nombre de jours",
                bargap=0.05,
                template="simple_white"
            )

            st.plotly_chart(fig, use_container_width=True)

            # Export possible
            with st.expander("⬇️ Télécharger le fichier enrichi"):
                st.download_button(
                    label="Télécharger en Excel",
                    data=df_journalier.to_excel(index=False, engine='openpyxl'),
                    file_name="journalier_avec_solde.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"Erreur lors du traitement du fichier : {e}")
