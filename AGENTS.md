# Travailler sur MaintiDoc avec Codex

## Prise en main

1. Lire [README.md](README.md) pour la vision produit et les commandes, [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) pour l’architecture et [PROGRESS.md](PROGRESS.md) pour reprendre au bon point.
2. Consulter `git status --short` et les scripts concernés. Préserver les modifications locales de l’utilisateur.
3. Continuer le prototype existant. En cas d’écart entre le README et le code, indiquer ce qui a été vérifié et ce qui reste à confirmer.

## Collaboration

- Travailler étape par étape et expliquer en français ce qui change, pourquoi et comment le résultat est vérifié.
- Commencer par une analyse en lecture seule pour une nouvelle étape. Obtenir l’accord de l’utilisateur avant de modifier des fichiers, sauf si sa demande autorise explicitement les modifications concernées.
- Limiter les changements au périmètre convenu. Réutiliser les points d’entrée existants et signaler toute hypothèse importante.
- À la fin d’une étape autorisée, indiquer les fichiers modifiés, les vérifications effectuées et la suite proposée. Consigner les résultats dans `PROGRESS.md` lorsque la mise à jour du suivi fait partie du périmètre.

## Précautions propres au dépôt

- Préserver les métadonnées `famille`, `fichier` et `page` ainsi que l’abstention quand le contexte ne permet pas de répondre. Vérifier les unités et les références lors d’un changement du RAG.
- `ingestion.py` a `RESET_TABLE = True` et supprime `data_chunks`. Vérifier ce réglage et obtenir l’accord avant toute réindexation destructive.
- `extraction_multimodale.py` écrit dans `extractions/`. `evaluation_rag.py` réécrit `resultats_evaluation.json`. Préserver le rapport historique avant une nouvelle campagne de mesures.
- Ne pas recopier les identifiants de connexion dans les documents ou les comptes rendus. Protéger les PDF et extractions internes avant tout partage.

## Priorité actuelle

Mesurer la latence du pipeline texte + tableaux avant de l’optimiser. La première intervention envisagée est une instrumentation de `evaluation_rag.py`, sous réserve d’accord. [PROGRESS.md](PROGRESS.md)
