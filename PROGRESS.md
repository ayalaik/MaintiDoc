# Avancement de MaintiDoc

État de la passation au 26 novembre 2026. Le dernier commit observé est `c4b224a8`.

## Étapes réalisées

La [note de cadrage V1](NOTE_CADRAGE_V1.md) formalise le livrable L1.1. Le maintien de PostgreSQL/PGVector, de `nomic-embed-text` via Ollama et de LlamaIndex pour la V1 a été confirmé le 26 novembre 2026.

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

## Prochaine étape proposée, en attente d’accord

1. Instrumenter `evaluation_rag.py` pour distinguer l’embedding, les deux recherches PGVector, la fusion et le contexte, puis la génération. Quand les métriques Ollama sont disponibles, relever le chargement du modèle, le traitement du prompt et la génération des jetons. Préserver le rapport historique lors des nouveaux essais.
2. Rejouer à plusieurs reprises les mêmes questions à froid et à chaud. Consigner les conditions, les durées par étape et la médiane de bout en bout. Suivre en parallèle l’exactitude, les sources, les unités et l’abstention.
3. Après cette mesure de référence, tester le calcul d’un seul embedding par question pour les deux recherches. Comparer avec les mêmes questions, index, paramètres de récupération et prompt. Déterminer à partir des résultats s’il faut agir ensuite sur le chargement d’Ollama, la taille du contexte ou la génération.

À la passation, l’instrumentation et les optimisations restent à mettre en œuvre. Aucune nouvelle campagne de mesure n’a été lancée.
