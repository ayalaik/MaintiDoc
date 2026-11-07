
import json
from pathlib import Path

from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

# Configuration
FICHIER_JSON = Path("extractions/extractions.json")

DB = dict(
    host="localhost",
    port=5432,
    database="maintidoc",
    user="maintidoc",
    password="motdepasse",
)

TABLE_NAME = "tableaux"
EMBED_DIM = 768

# Modèle d'embeddings local
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text"
)

# Lecture des extractions
with open(FICHIER_JSON, "r", encoding="utf-8") as f:
    donnees = json.load(f)

documents = []

for page in donnees:
    tableaux = page.get("tableaux", [])

    for numero, tableau in enumerate(tableaux, start=1):
        if not tableau or len(tableau) < 2:
            continue

        entetes = tableau[0]
        lignes = []

        for valeurs in tableau[1:]:
            champs = []

            for entete, valeur in zip(entetes, valeurs):
                if valeur:
                    champs.append(
                        f"{entete}: {valeur}"
                    )

            if champs:
                lignes.append(" ; ".join(champs))

        if not lignes:
            continue

        texte = (
            f"Document : {page['fichier']}\n"
            f"Page : {page['page']}\n"
            f"Tableau {numero}\n"
            + "\n".join(lignes)
        )

        documents.append(
            Document(
                text=texte,
                metadata={
                    "famille": page["famille"],
                    "fichier": page["fichier"],
                    "page": page["page"],
                    "tableau": numero,
                    "type_contenu": "tableau",
                },
            )
        )

print(f"{len(documents)} tableaux préparés")

if not documents:
    raise SystemExit(
        "Aucun tableau exploitable trouvé."
    )

# Connexion PGVector
vector_store = PGVectorStore.from_params(
    **DB,
    table_name=TABLE_NAME,
    embed_dim=EMBED_DIM,
)

storage_context = StorageContext.from_defaults(
    vector_store=vector_store
)

# Génération et stockage des embeddings
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    show_progress=True,
)

print("Indexation des tableaux terminée !")
