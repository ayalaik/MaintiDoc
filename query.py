"""
MaintiDoc - Poser une question au RAG (recherche dans PGVector + réponse Ollama)
Usage : python query.py
"""
from llama_index.core import PromptTemplate, Settings, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.postgres import PGVectorStore

# ---------- Configuration (identique à ingestion.py) ----------
DB = dict(host="localhost", port=5432, database="maintidoc",
          user="maintidoc", password="motdepasse")
TABLE_NAME = "chunks"
EMBED_DIM = 768
TOP_K = 4  # nombre de chunks donnés au LLM

Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
Settings.llm = Ollama(model="llama3.2:3b", request_timeout=300.0, temperature=0.1)

# ---------- Connexion à la base existante ----------
vector_store = PGVectorStore.from_params(**DB, table_name=TABLE_NAME, embed_dim=EMBED_DIM)
index = VectorStoreIndex.from_vector_store(vector_store)

# ---------- Prompt : réponse uniquement à partir des documents ----------
PROMPT = PromptTemplate(
    "Tu es MaintiDoc, un assistant de maintenance industrielle.\n"
    "Réponds en français, uniquement à partir du contexte ci-dessous.\n"
    "Si l'information n'y est pas, réponds : \"Je ne trouve pas cette information "
    "dans les documents.\"\n\n"
    "Contexte :\n{context_str}\n\n"
    "Question : {query_str}\n"
    "Réponse :"
)

query_engine = index.as_query_engine(similarity_top_k=TOP_K, text_qa_template=PROMPT)

# ---------- Boucle de questions ----------
print("MaintiDoc prêt. Pose une question (ou 'q' pour quitter).")
while True:
    question = input("\nQuestion > ").strip()
    if question.lower() in {"q", "quit", "exit", ""}:
        break

    reponse = query_engine.query(question)
    print("\nRéponse :", reponse)

    print("\nSources :")
    for src in reponse.source_nodes:
        m = src.node.metadata
        print(f" - {m.get('famille')} / {m.get('fichier')} (page {m.get('page')})"
              f" - score {src.score:.2f}")