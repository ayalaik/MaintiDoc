
import argparse
import json
import time
import re
import unicodedata
from datetime import datetime, timezone
from itertools import product
from statistics import median

from llama_index.core import QueryBundle, Settings, VectorStoreIndex, PromptTemplate
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.postgres import PGVectorStore
from pydantic import PrivateAttr


class OllamaEmbeddingChronometre(OllamaEmbedding):
    """Mesure l'embedding demandé par le retriever, avec le même appel Ollama."""

    _durees_questions: list[float] = PrivateAttr(default_factory=list)

    def get_query_embedding(self, query: str) -> list[float]:
        debut = time.perf_counter()
        vecteur = super().get_query_embedding(query)
        self._durees_questions.append(time.perf_counter() - debut)
        return vecteur

    def mesurer_recherche(self, retriever, requete):
        premier_appel = len(self._durees_questions)
        debut = time.perf_counter()
        resultats = retriever.retrieve(requete)
        duree = time.perf_counter() - debut
        appels = self._durees_questions[premier_appel:]
        duree_embeddings = sum(appels)
        return resultats, {
            "total_secondes": round(duree, 6),
            "appels_embedding": len(appels),
            "embedding_secondes": round(duree_embeddings, 6),
            "recuperation_hors_embedding_secondes": round(duree - duree_embeddings, 6),
        }

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

modele_embedding = OllamaEmbeddingChronometre(
    model_name="nomic-embed-text"
)
Settings.embed_model = modele_embedding

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

def interroger_rag(question, partager_embedding=False):

    debut = time.perf_counter()

    requete = question
    profil_embedding_partage = None
    if partager_embedding:
        debut_embedding = time.perf_counter()
        vecteur = modele_embedding.get_query_embedding(question)
        profil_embedding_partage = {
            "appels_embedding": 1,
            "embedding_secondes": round(time.perf_counter() - debut_embedding, 6),
        }
        requete = QueryBundle(query_str=question, embedding=vecteur)

    textes, profil_textes = modele_embedding.mesurer_recherche(retriever_textes, requete)
    tableaux, profil_tableaux = modele_embedding.mesurer_recherche(retriever_tableaux, requete)

    debut_contexte = time.perf_counter()
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

    debut_generation = time.perf_counter()
    duree_contexte = debut_generation - debut_contexte
    reponse = Settings.llm.complete(prompt_final)
    duree_generation = time.perf_counter() - debut_generation

    sources = [
        r.node.metadata.get("fichier", "inconnu")
        for r in resultats
    ]

    duree = time.perf_counter() - debut
    profil = {
        "recherche_texte": profil_textes,
        "recherche_tableaux": profil_tableaux,
        "preparation_contexte_secondes": round(duree_contexte, 6),
        "generation_secondes": round(duree_generation, 6),
        "taille_prompt_caracteres": len(prompt_final),
    }
    if profil_embedding_partage is not None:
        profil["embedding_partage"] = profil_embedding_partage
    if reponse.raw is not None:
        champs_ollama = {
            "total_nanosecondes": "total_duration",
            "chargement_nanosecondes": "load_duration",
            "traitement_prompt_nanosecondes": "prompt_eval_duration",
            "generation_jetons_nanosecondes": "eval_duration",
            "jetons_prompt": "prompt_eval_count",
            "jetons_generes": "eval_count",
        }
        metriques_ollama = {
            nom: valeur
            for nom, champ in champs_ollama.items()
            if (valeur := reponse.raw.get(champ)) is not None
        }
        if metriques_ollama:
            profil["ollama"] = metriques_ollama

    return reponse.text, sources, round(duree, 6), profil

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

analyseur = argparse.ArgumentParser(description="Mesure la latence du RAG multimodal.")
analyseur.add_argument(
    "--repetitions",
    type=int,
    default=1,
    help="Nombre de passages complets sur le jeu de questions (défaut : 1).",
)
analyseur.add_argument(
    "--fenetre-contexte",
    type=int,
    help="Fenêtre de contexte Ollama en jetons (défaut : valeur du modèle).",
)
analyseur.add_argument(
    "--embedding-partage",
    action="store_true",
    help="Réutilise le même embedding pour les recherches texte et tableaux.",
)
arguments = analyseur.parse_args()
if arguments.repetitions < 1:
    analyseur.error("--repetitions doit être supérieur ou égal à 1")
if arguments.fenetre_contexte is not None and arguments.fenetre_contexte < 1:
    analyseur.error("--fenetre-contexte doit être supérieure ou égale à 1")

Settings.llm = Ollama(
    model="llama3.2:3b",
    request_timeout=300.0,
    temperature=0.1,
    context_window=arguments.fenetre_contexte or -1,
)

with open(
    "questions_evaluation.json",
    "r",
    encoding="utf-8"
) as fichier:
    questions = json.load(fichier)

resultats_evaluation = []
debut_campagne = datetime.now(timezone.utc)

print("=" * 55)
print("       EVALUATION DU RAG MAINTIDOC")
print("=" * 55)

# ==========================================
# 7. EXECUTION DES TESTS
# ==========================================

for passage, test in product(range(1, arguments.repetitions + 1), questions):

    print(f"\nPassage {passage}, test {test['id']} : {test['question']}")

    reponse, sources, duree, profil = interroger_rag(
        test["question"], partager_embedding=arguments.embedding_partage
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

    print(f"Temps de réponse : {duree:.2f} secondes")
    if "embedding_partage" in profil:
        duree_embedding = profil["embedding_partage"]["embedding_secondes"]
        print(f"Embedding partagé : {duree_embedding:.3f} s")
    for type_source in ("texte", "tableaux"):
        recherche = profil[f"recherche_{type_source}"]
        print(
            f"Recherche {type_source} : {recherche['total_secondes']:.3f} s "
            f"(embedding : {recherche['embedding_secondes']:.3f} s, "
            f"reste : {recherche['recuperation_hors_embedding_secondes']:.3f} s)"
        )
    print(f"Préparation du contexte : {profil['preparation_contexte_secondes']:.3f} s")
    print(f"Génération : {profil['generation_secondes']:.3f} s")

    resultats_evaluation.append({
        "passage": passage,
        "id": test["id"],
        "question": test["question"],
        "type": test["type"],
        "reponse_attendue": test["reponse_attendue"],
        "reponse_generee": reponse,
        "reponse_correcte": correcte,
        "document_attendu": document_attendu,
        "source_correcte": source_correcte,
        "sources": sources,
        "temps_reponse": duree,
        "profil": profil,
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

temps_reponse = [r["temps_reponse"] for r in resultats_evaluation]
temps_moyen = sum(temps_reponse) / total
temps_median = median(temps_reponse)

print("\n" + "=" * 55)
print("              BILAN GLOBAL")
print("=" * 55)

print(f"Nombre de tests : {total}")
print(f"Réponses correctes : {bonnes_reponses}/{total}")
print(f"Accuracy estimée : {accuracy:.2f}%")
print(f"Hit Rate@4 : {hit_rate:.2f}%")
print(f"Temps moyen : {temps_moyen:.2f} secondes")
print(f"Temps médian : {temps_median:.2f} secondes")

# ==========================================
# 9. SAUVEGARDE DES RESULTATS
# ==========================================

rapport = {
    "debut_utc": debut_campagne.isoformat(),
    "repetitions": arguments.repetitions,
    "fenetre_contexte_jetons": Settings.llm.get_context_window(),
    "embedding_partage": arguments.embedding_partage,
    "metriques": {
        "nombre_tests": total,
        "reponses_correctes": bonnes_reponses,
        "accuracy": round(accuracy, 2),
        "hit_rate_at_4": round(hit_rate, 2),
        "temps_moyen_secondes": round(temps_moyen, 2),
        "temps_median_secondes": round(temps_median, 2),
    },
    "resultats": resultats_evaluation
}

fichier_rapport = f"resultats_profilage_{debut_campagne:%Y%m%dT%H%M%S%fZ}.json"
with open(fichier_rapport, "x", encoding="utf-8") as fichier:
    json.dump(
        rapport,
        fichier,
        ensure_ascii=False,
        indent=4
    )

print(f"\nRésultats sauvegardés dans {fichier_rapport}")
