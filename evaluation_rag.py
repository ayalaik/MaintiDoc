
import json
import time
import re
import unicodedata

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
# 2. CONNEXION AUX INDEX VECTORIELS
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

index_textes = VectorStoreIndex.from_vector_store(store_textes)
index_tableaux = VectorStoreIndex.from_vector_store(store_tableaux)

retriever_textes = index_textes.as_retriever(
    similarity_top_k=TOP_K
)

retriever_tableaux = index_tableaux.as_retriever(
    similarity_top_k=TOP_K
)

# ==========================================
# 3. PROMPT DU RAG
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
# 4. FONCTION DE RECHERCHE RAG
# ==========================================

def interroger_rag(question):

    debut = time.perf_counter()

    textes = retriever_textes.retrieve(question)
    tableaux = retriever_tableaux.retrieve(question)

    for r in textes:
        r.node.metadata["type_source"] = "Texte"

    for r in tableaux:
        r.node.metadata["type_source"] = "Tableau"

    resultats = []
    ids_vus = set()

    for r in textes + tableaux:
        if r.node.node_id not in ids_vus:
            ids_vus.add(r.node.node_id)
            resultats.append(r)

    resultats.sort(
        key=lambda r: r.score if r.score is not None else 0,
        reverse=True
    )

    resultats = resultats[:MAX_RESULTATS]

    contexte = "\n\n".join(
        f"Type : {r.node.metadata.get('type_source', 'Inconnu')}\n"
        f"Document : {r.node.metadata.get('fichier', 'inconnu')}\n"
        f"Page : {r.node.metadata.get('page', '?')}\n"
        f"Contenu : {r.node.text}"
        for r in resultats
    )

    prompt_final = PROMPT.format(
        context_str=contexte,
        query_str=question
    )

    reponse = Settings.llm.complete(prompt_final).text

    sources = [
        r.node.metadata.get("fichier", "inconnu")
        for r in resultats
    ]

    duree = round(time.perf_counter() - debut, 2)

    return reponse, sources, duree

# ==========================================
# 5. NORMALISATION DES REPONSES
# ==========================================

def normaliser(texte):

    texte = unicodedata.normalize("NFKC", texte.lower())

    texte = texte.replace("heure(s)", "h")
    texte = texte.replace("heures", "h")
    texte = texte.replace("heure", "h")
    texte = texte.replace("mètres cubes", "m3")

    texte = re.sub(r"\s+", "", texte)

    return texte


def verifier_reponse(reponse, attendue, type_question):

    reponse_norm = normaliser(reponse)
    attendue_norm = normaliser(attendue)

    if type_question == "absence_information":
        expressions = [
            "je ne trouve pas cette information",
            "information introuvable",
            "information non disponible",
            "n'est pas indiquée",
            "n'est pas précisée"
        ]

        return any(
            normaliser(expression) in reponse_norm
            for expression in expressions
        )

    return attendue_norm in reponse_norm

# ==========================================
# 6. CHARGEMENT DU GROUND TRUTH
# ==========================================

with open(
    "questions_evaluation.json",
    "r",
    encoding="utf-8"
) as fichier:
    questions = json.load(fichier)

resultats_evaluation = []

print("=" * 55)
print("       EVALUATION DU RAG MAINTIDOC")
print("=" * 55)

# ==========================================
# 7. EXECUTION DES TESTS
# ==========================================

for test in questions:

    print(f"\nTest {test['id']} : {test['question']}")

    reponse, sources, duree = interroger_rag(
        test["question"]
    )

    correcte = verifier_reponse(
        reponse,
        test["reponse_attendue"],
        test["type"]
    )

    document_attendu = test["document_attendu"]

    source_correcte = (
        document_attendu in sources
        if document_attendu is not None
        else None
    )

    print(f"Réponse attendue : {test['reponse_attendue']}")
    print(f"Réponse générée : {reponse}")
    print(f"Réponse correcte : {'OUI' if correcte else 'NON'}")

    if source_correcte is not None:
        print(f"Source retrouvée : {'OUI' if source_correcte else 'NON'}")
    else:
        print("Source retrouvée : Non applicable")

    print(f"Temps de réponse : {duree} secondes")

    resultats_evaluation.append({
        "id": test["id"],
        "question": test["question"],
        "type": test["type"],
        "reponse_attendue": test["reponse_attendue"],
        "reponse_generee": reponse,
        "reponse_correcte": correcte,
        "document_attendu": document_attendu,
        "source_correcte": source_correcte,
        "sources": sources,
        "temps_reponse": duree
    })

# ==========================================
# 8. CALCUL DES METRIQUES
# ==========================================

total = len(resultats_evaluation)

if total == 0:
    raise ValueError("Le fichier d'évaluation est vide.")

bonnes_reponses = sum(
    r["reponse_correcte"]
    for r in resultats_evaluation
)

accuracy = bonnes_reponses / total * 100

tests_sources = [
    r for r in resultats_evaluation
    if r["source_correcte"] is not None
]

hit_rate = (
    sum(r["source_correcte"] for r in tests_sources)
    / len(tests_sources) * 100
    if tests_sources else 0
)

temps_moyen = sum(
    r["temps_reponse"]
    for r in resultats_evaluation
) / total

print("\n" + "=" * 55)
print("              BILAN GLOBAL")
print("=" * 55)

print(f"Nombre de tests : {total}")
print(f"Réponses correctes : {bonnes_reponses}/{total}")
print(f"Accuracy estimée : {accuracy:.2f}%")
print(f"Hit Rate@4 : {hit_rate:.2f}%")
print(f"Temps moyen : {temps_moyen:.2f} secondes")

# ==========================================
# 9. SAUVEGARDE DES RESULTATS
# ==========================================

rapport = {
    "metriques": {
        "nombre_tests": total,
        "reponses_correctes": bonnes_reponses,
        "accuracy": round(accuracy, 2),
        "hit_rate_at_4": round(hit_rate, 2),
        "temps_moyen_secondes": round(temps_moyen, 2)
    },
    "resultats": resultats_evaluation
}

with open(
    "resultats_evaluation.json",
    "w",
    encoding="utf-8"
) as fichier:
    json.dump(
        rapport,
        fichier,
        ensure_ascii=False,
        indent=4
    )

print("\nRésultats sauvegardés dans resultats_evaluation.json")
