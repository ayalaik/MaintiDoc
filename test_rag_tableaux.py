
from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

# Configuration
DB = dict(
    host="localhost",
    port=5432,
    database="maintidoc",
    user="maintidoc",
    password="motdepasse"
)

# Même modèle utilisé pendant l'indexation
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text"
)

# Connexion à la table des tableaux
vector_store = PGVectorStore.from_params(
    **DB,
    table_name="tableaux",
    embed_dim=768
)

index = VectorStoreIndex.from_vector_store(
    vector_store
)

# Recherche vectorielle
retriever = index.as_retriever(
    similarity_top_k=3
)

question = "Quelle est la puissance nominale du moteur ME-30 ?"

resultats = retriever.retrieve(question)

print("\nQUESTION :", question)

for i, resultat in enumerate(resultats, start=1):
    print(f"\n--- RESULTAT {i} ---")
    print("Score :", resultat.score)
    print("Document :", resultat.node.metadata.get("fichier"))
    print("Page :", resultat.node.metadata.get("page"))
    print("Contenu :")
    print(resultat.node.text)
