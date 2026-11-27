# Contexte du projet MaintiDoc

## Objectif et périmètre

MaintiDoc est un prototype local d’assistant documentaire pour la maintenance industrielle. Il aide les techniciens et responsables à retrouver des caractéristiques, procédures, périodicités et pistes de diagnostic dans des PDF, puis à consulter les sources d’une réponse en français.

Le corpus de démonstration contient six PDF. `famille_A` couvre la pompe centrifuge PC-200 et `famille_B` le moteur ME-30. Chaque famille comprend une fiche technique, un manuel de maintenance et un guide de dépannage. Le README rapporte 8 passages et 6 tableaux indexés lors de tests antérieurs. Ces volumes décrivent le jeu de démonstration.

## Parcours V1

[index_qdrant.py](index_qdrant.py) extrait les PDF avec PyMuPDF et indexe le texte et les tableaux dans Qdrant avec BGE-M3 via Ollama. [query_multimodal.py](query_multimodal.py) relie la recherche vectorielle à la génération locale avec LangChain. FastAPI et Streamlit utilisent cette chaîne. Voir [les commandes de la V1](README.md#10-exécution-et-tests).

## Architecture du prototype historique

| Étape | Implémentation |
| --- | --- |
| Indexation du texte | `ingestion.py` lit les PDF avec `PyMuPDFReader`, nettoie les pages, puis utilise `SentenceSplitter` avec une taille de 512 et un recouvrement de 50. Les passages sont stockés dans `data_chunks`. |
| Extraction multimodale | `extraction_multimodale.py` utilise PyMuPDF pour le texte, les tableaux et les images intégrées. Il produit `extractions/extractions.json`, avec notamment `tableaux` et `tableaux_texte`. Le README rapporte l’absence d’images intégrées dans les PDF testés. |
| Indexation des tableaux | `indexation_tableaux.py` lit le champ `tableaux`, assemble les en-têtes et les valeurs en texte structuré, puis indexe le résultat dans `data_tableaux`. |
| Embeddings et stockage | LlamaIndex utilise `nomic-embed-text` via Ollama. Les vecteurs ont 768 dimensions. `docker-compose.yml` fournit PostgreSQL 16 avec PGVector sur le port local 5432. |
| Recherche textuelle | `query.py` interroge `data_chunks` avec un moteur de requête LlamaIndex et récupère jusqu’à quatre passages. |
| Recherche texte + tableaux | `query_multimodal.py` récupère jusqu’à trois résultats par table, marque leur type, déduplique par identifiant de nœud, trie par score et retient jusqu’à quatre passages au total. |
| Génération et provenance | La voie multimodale utilise `llama3.2:3b` via Ollama, avec une température de 0,1 et un délai maximal de requête de 300 s. Le prompt demande une réponse en français fondée sur le contexte et une abstention si l’information manque. Le terminal affiche les sources avec type, famille, fichier, page et score. |
| Évaluation | `evaluation_rag.py` reproduit la logique multimodale dans son propre code, lit `questions_evaluation.json`, chronomètre la requête et écrit `resultats_evaluation.json`. |

À ce stade, « multimodal » désigne la combinaison du texte et des tableaux convertis en texte pour répondre. L’interprétation de schémas, l’OCR des PDF numérisés et les modèles de vision restent des pistes.

## Environnement et points d’entrée historiques

- Le prototype a été développé sous Windows avec PowerShell et Python 3.11. L’environnement local `.venv311` contient les intégrations utilisées lors de la revue.
- PostgreSQL/PGVector s’exécute via Docker Compose et Ollama sur le poste. Les deux modèles doivent être disponibles localement.
- Les commandes terminal `query_multimodal.py` et `query.py` utilisent désormais Qdrant.
- `diagnostic.py`, `test_extraction_texte.py`, `test_tableaux_corriges.py` et `test_rag_tableaux.py` servent aux contrôles du prototype.
- `requirements.txt` ne déclare pas explicitement PyMuPDF ni les intégrations LlamaIndex pour Ollama et PGVector. La reproductibilité d’une installation neuve reste à vérifier. Les scripts contiennent des identifiants de démonstration en dur.

## Évolutions envisagées

La feuille de route prévoit une interface web et une API, l’import et le versionnement des documents, les équipements et interventions, le diagnostic assisté, les rôles et droits d’accès, puis un déploiement reproductible. Les choix de frameworks et d’hébergement restent ouverts. Les réponses doivent rester traçables aux documents techniques.

## Sources de cette passation

Ce document reconstruit le contexte à partir de l’échange accessible, de l’historique Git local, du [README.md](README.md), des scripts et du rapport d’évaluation. Les anciennes conversations ChatGPT hors du fil accessible ne sont pas couvertes. Voir [PROGRESS.md](PROGRESS.md) pour les résultats mesurés et la reprise.
