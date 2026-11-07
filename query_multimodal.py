
from llama_index.core import Settings, VectorStoreIndex, PromptTemplate
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.postgres import PGVectorStore

# ==========================================
# 1. CONFIGURATION
# ==========================================

DB = dict(
    host="localhost",
    port=5432,
    database="maintidoc",
    user="maintidoc",
    password="motdepasse"
)

EMBED_DIM = 768
TOP_K = 3
MAX_RESULTATS = 4

Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text"
)

Settings.llm = Ollama(
    model="llama3.2:3b",
    request_timeout=300.0,
    temperature=0.1
)

# ==========================================
# 2. CONNEXION AUX BASES VECTORIELLES
# ==========================================

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

# ==========================================
# 3. CONFIGURATION DES RETRIEVERS
# ==========================================

retriever_textes = index_textes.as_retriever(
    similarity_top_k=TOP_K
)

retriever_tableaux = index_tableaux.as_retriever(
    similarity_top_k=TOP_K
)

# ==========================================
# 4. PROMPT DU MODELE
# ==========================================

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

# ==========================================
# 5. BOUCLE PRINCIPALE
# ==========================================

print("MaintiDoc multimodal prêt !")
print("Tape 'q' pour quitter.")

while True:

    question = input("\nQuestion > ").strip()

    if question.lower() in {"q", "quit", "exit"}:
        break

    if not question:
        continue

    # --------------------------------------
    # A. Recherche dans les deux index
    # --------------------------------------

    resultats_textes = retriever_textes.retrieve(question)
    resultats_tableaux = retriever_tableaux.retrieve(question)

    # --------------------------------------
    # B. Identification du type de source
    # --------------------------------------

    for resultat in resultats_textes:
        resultat.node.metadata["type_source"] = "Texte"

    for resultat in resultats_tableaux:
        resultat.node.metadata["type_source"] = "Tableau"

    # --------------------------------------
    # C. Fusion et suppression des doublons
    # --------------------------------------

    resultats = []
    ids_vus = set()

    for resultat in resultats_textes + resultats_tableaux:

        identifiant = resultat.node.node_id

        if identifiant not in ids_vus:
            ids_vus.add(identifiant)
            resultats.append(resultat)

    # --------------------------------------
    # D. Classement par similarité
    # --------------------------------------

    resultats.sort(
        key=lambda r: r.score if r.score is not None else 0,
        reverse=True
    )

    # Garder uniquement les 4 meilleurs résultats
    resultats = resultats[:MAX_RESULTATS]

    # --------------------------------------
    # E. Construction du contexte
    # --------------------------------------

    contexte = "\n\n".join(
        f"Type : {r.node.metadata.get('type_source', 'Inconnu')}\n"
        f"Document : {r.node.metadata.get('fichier', 'inconnu')}\n"
        f"Page : {r.node.metadata.get('page', '?')}\n"
        f"Contenu : {r.node.text}"
        for r in resultats
    )

    # --------------------------------------
    # F. Génération de la réponse
    # --------------------------------------

    prompt_final = PROMPT.format(
        context_str=contexte,
        query_str=question
    )

    reponse = Settings.llm.complete(prompt_final)

    print("\nRéponse :")
    print(reponse.text)

    # --------------------------------------
    # G. Affichage des sources
    # --------------------------------------

    print("\nSources :")

    if not resultats:
        print("Aucune source trouvée.")

    for r in resultats:

        m = r.node.metadata

        type_source = m.get("type_source", "Inconnu")
        famille = m.get("famille", "?")
        fichier = m.get("fichier", "?")
        page = m.get("page", "?")

        score = (
            f"{r.score:.2f}"
            if r.score is not None
            else "N/A"
        )

        print(
            f"- [{type_source}] "
            f"{famille} / {fichier} "
            f"(page {page}) - score {score}"
        )
