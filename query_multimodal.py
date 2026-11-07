
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core import PromptTemplate
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.postgres import PGVectorStore

# Configuration
DB = dict(
    host="localhost",
    port=5432,
    database="maintidoc",
    user="maintidoc",
    password="motdepasse"
)

EMBED_DIM = 768
TOP_K = 3

Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text"
)

Settings.llm = Ollama(
    model="llama3.2:3b",
    request_timeout=300.0,
    temperature=0.1
)

# Connexion aux deux tables
store_textes = PGVectorStore.from_params(
    **DB,
    table_name="chunks",
    embed_dim=EMBED_DIM
)

store_tableaux = PGVectorStore.from_params(
    **DB,
    table_name="tableaux",
    embed_dim=EMBED_DIM
)

index_textes = VectorStoreIndex.from_vector_store(
    store_textes
)

index_tableaux = VectorStoreIndex.from_vector_store(
    store_tableaux
)

retriever_textes = index_textes.as_retriever(
    similarity_top_k=TOP_K
)

retriever_tableaux = index_tableaux.as_retriever(
    similarity_top_k=TOP_K
)

PROMPT = PromptTemplate(
    "Tu es MaintiDoc, un assistant de maintenance industrielle.\n"
    "Réponds en français uniquement à partir des documents fournis.\n"
    "Utilise les informations techniques et les tableaux.\n"
    "Si la réponse n'est pas dans les documents, dis : "
    "'Je ne trouve pas cette information dans les documents.'\n\n"
    "Contexte :\n{context_str}\n\n"
    "Question : {query_str}\n"
    "Réponse :"
)

print("MaintiDoc multimodal prêt !")

while True:
    question = input("\nQuestion > ").strip()

    if question.lower() in {"q", "quit", "exit"}:
        break

    if not question:
        continue

    # Recherche dans les textes et les tableaux
    resultats_textes = retriever_textes.retrieve(question)
    resultats_tableaux = retriever_tableaux.retrieve(question)

    # Fusion et suppression des doublons
    resultats = []
    ids_vus = set()

    for resultat in resultats_textes + resultats_tableaux:
        identifiant = resultat.node.node_id
        if identifiant not in ids_vus:
            ids_vus.add(identifiant)
            resultats.append(resultat)

    # Construction du contexte
    contexte = "\n\n".join(
        f"Document : {r.node.metadata.get('fichier', 'inconnu')}\n"
        f"Page : {r.node.metadata.get('page', '?')}\n"
        f"Contenu : {r.node.text}"
        for r in resultats
    )

    # Génération de la réponse
    prompt_final = PROMPT.format(
        context_str=contexte,
        query_str=question
    )

    reponse = Settings.llm.complete(prompt_final)

    print("\nRéponse :")
    print(reponse.text)

    print("\nSources :")
    for r in resultats:
        m = r.node.metadata
        print(
            f"- {m.get('famille', '?')} / "
            f"{m.get('fichier', '?')} "
            f"(page {m.get('page', '?')}) "
            f"- score {r.score:.2f}"
            if r.score is not None
            else f"- {m.get('fichier', '?')}"
        )
