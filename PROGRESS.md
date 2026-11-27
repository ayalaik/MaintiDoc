# Avancement de MaintiDoc

## Migration V1 du 27 novembre 2026

La V1 utilise BGE-M3 via Ollama, Qdrant et LangChain dans l’ingestion, le terminal et la démo FastAPI/Streamlit. Les sources conservent la famille, le fichier et la page. Les résultats de performance ci-dessous concernent le prototype historique.

Qdrant a été démarré via Docker Compose et l’indexation réelle des six PDF a publié 8 passages de texte et 6 tableaux sous l’alias `maintidoc_bge_m3`.

Vérification locale via FastAPI sur les quatre questions de référence. Les trois réponses chiffrées contenaient 30 kW, 200 m³/h et 4 000 h, avec le fichier attendu et sa page 1 parmi les sources. La question sur la date de fabrication a produit une abstention, puis la formulation attendue a été vérifiée après normalisation. La recherche limitée au texte a également été testée.

## Étapes réalisées

Les six PDF de test ont désormais un identifiant, une version interne `demo-1` et un groupe de démonstration dans [l’inventaire](corpus/metadata.csv). La collection active Qdrant a été reconstruite et ses 14 points contrôlés. Un filtre Qdrant sur chaque groupe retrouve les trois PDF correspondants, soit sept points par groupe.

La démonstration locale relie [Streamlit](interface.py) à [FastAPI](api.py). FastAPI authentifie les comptes `demo_pompes` et `demo_moteurs`, filtre les passages Qdrant avant la génération et vérifie les droits lors de l’ouverture directe des PDF. Les commandes et les variables des mots de passe figurent dans le [README](README.md#10-exécution-et-tests). Les six PDF constituent le corpus du test initial demandé par le professeur.

Les deux profils ont été validés manuellement depuis Streamlit le 27 novembre 2026. Sur la même question, le profil moteurs a reçu 30 kW avec la page 1 de la fiche ME-30 parmi les sources. Le profil pompes a reçu une abstention et uniquement des sources du groupe pompes. Les essais FastAPI ont également vérifié le filtrage des passages avant génération et les statuts 200, 403 et 401 lors de l’ouverture directe du PDF. Le [rapport L1.6](RAPPORT_TESTS_L1_6.md) rassemble les résultats et les deux captures.

La [note de cadrage V1](NOTE_CADRAGE_V1.md) formalise le livrable L1.1 et décrit la nouvelle pile.

| Jalon | Trace dans le dépôt |
| --- | --- |
| Pipeline local, extraction multimodale, embeddings et PGVector | `ad2645c1` |
| Ingestion, extraction et scripts de requête | `898cb253` |
| Mise à jour intermédiaire | `2746a1b0` |
| Première évaluation du RAG | `c4b224a8`, [questions_evaluation.json](questions_evaluation.json) et [resultats_evaluation.json](resultats_evaluation.json) |
| Revue de cohérence | La fusion texte + tableaux est implémentée. Le README présente encore la fusion comme en cours et l’évaluation comme une piste. La revue de latence a été faite en lecture seule. |

## Référence de performance enregistrée

| Cas | Référence | Durée |
| --- | --- | ---: |
| Puissance nominale du ME-30 | 30 kW | 171,28 s |
| Débit maximal du PC-200 | 200 m³/h | 52,63 s |
| Regraissage des roulements du ME-30 | 4 000 h | 41,04 s |
| Date exacte de fabrication du PC-200 | Abstention | 42,90 s |

Le rapport indique **76,96 s en moyenne** et une médiane de **47,77 s** calculée sur les quatre durées publiées. Le script a accepté **4 réponses sur 4** et retrouvé **3 documents attendus sur 3** parmi les quatre premiers résultats. Le cas d’abstention est exclu du calcul de ce taux. Les contrôles reposent sur la présence d’une chaîne normalisée ou d’une formule d’abstention et sur le nom de fichier retrouvé. La fidélité de chaque affirmation à sa page source reste à contrôler. [evaluation_rag.py](evaluation_rag.py) · [resultats_evaluation.json](resultats_evaluation.json)

## Diagnostic actuel

- `evaluation_rag.py` mesure une durée totale par question avec `time.perf_counter()`. Les coûts respectifs des embeddings, de PGVector, de la construction du contexte et de la génération restent inconnus.
- La première question est nettement plus lente. Le chargement à froid des modèles ou les premières connexions peuvent y contribuer. Le rapport contient un seul passage de quatre questions différentes et ne permet pas d’isoler ces effets.
- `query_multimodal.py` et `evaluation_rag.py` passent la même chaîne à deux retrievers successifs. Dans la version locale inspectée de LlamaIndex, chaque appel construit son propre `QueryBundle` et calcule le vecteur s’il est absent. Partager un vecteur pré-calculé entre les deux recherches peut éviter un appel d’embedding. Le gain reste à quantifier.

## Plan de profilage du prototype historique

1. Instrumenter `evaluation_rag.py` pour distinguer l’embedding, les deux recherches PGVector, la fusion et le contexte, puis la génération. Quand les métriques Ollama sont disponibles, relever le chargement du modèle, le traitement du prompt et la génération des jetons. Préserver le rapport historique lors des nouveaux essais.
2. Rejouer à plusieurs reprises les mêmes questions à froid et à chaud. Consigner les conditions, les durées par étape et la médiane de bout en bout. Suivre en parallèle l’exactitude, les sources, les unités et l’abstention.
3. Après cette mesure de référence, tester le calcul d’un seul embedding par question pour les deux recherches. Comparer avec les mêmes questions, index, paramètres de récupération et prompt. Déterminer à partir des résultats s’il faut agir ensuite sur le chargement d’Ollama, la taille du contexte ou la génération.

L’instrumentation et l’essai d’embedding partagé figurent dans le commit `09db4f41` et les rapports `resultats_profilage_*.json`. Une nouvelle référence de latence reste à établir sur la V1.
