import requests
import streamlit as st


URL_API = "http://127.0.0.1:8000/questions"

st.set_page_config(page_title="MaintiDoc")
st.title("MaintiDoc")

with st.form("question"):
    question = st.text_area("Question de maintenance", max_chars=2000)
    soumise = st.form_submit_button("Rechercher", type="primary")

if soumise:
    if not question.strip():
        st.warning("Saisis une question de maintenance.")
        st.stop()

    try:
        with st.spinner("Recherche dans les manuels et génération de la réponse…"):
            resultat = requests.post(URL_API, json={"question": question}, timeout=(5, 330))
            resultat.raise_for_status()
            donnees = resultat.json()
    except requests.Timeout:
        st.error("Le délai de réponse a été dépassé.")
        st.stop()
    except requests.HTTPError as erreur:
        if erreur.response.status_code == 503:
            st.error("Le moteur documentaire est indisponible. Vérifie PostgreSQL et Ollama.")
        else:
            st.error("L’API a rejeté la demande.")
        st.stop()
    except requests.RequestException:
        st.error("Impossible de recevoir une réponse de l’API MaintiDoc.")
        st.stop()

    st.subheader("Réponse")
    st.text(donnees["reponse"])
    st.subheader("Sources retrouvées")
    if not donnees["sources"]:
        st.info("Aucune source retrouvée.")
    for source in donnees["sources"]:
        st.text(
            f"{source['famille']} / {source['fichier']} — "
            f"page {source['page']} ({source['type_source']})"
        )
