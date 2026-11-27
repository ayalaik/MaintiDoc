"""Construit et publie l'index documentaire de la V1."""

import csv
from pathlib import Path
from uuid import uuid4

import pymupdf
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models

from extraction_multimodale import extraire_tableaux, tableau_vers_texte
from rag_v1 import COLLECTION, EMBEDDING_DIM, QDRANT_URL, ouvrir_index


def lire_metadonnees(corpus: Path) -> dict:
    inventaire = corpus / "metadata.csv"
    fiches = {}
    identifiants = set()
    with inventaire.open(encoding="utf-8-sig", newline="") as fichier:
        lignes = csv.DictReader(fichier)
        champs = {"chemin", "document_id", "version", "groupes_autorises"}
        if set(lignes.fieldnames or []) != champs:
            raise ValueError(f"Colonnes invalides dans {inventaire}.")

        for numero, ligne in enumerate(lignes, start=2):
            chemin = (ligne["chemin"] or "").strip()
            identifiant = (ligne["document_id"] or "").strip()
            version = (ligne["version"] or "").strip()
            groupes = [g.strip() for g in (ligne["groupes_autorises"] or "").split(";")]
            if None in ligne or not (chemin and identifiant and version and all(groupes)):
                raise ValueError(f"Métadonnées incomplètes dans {inventaire}, ligne {numero}.")
            if chemin in fiches or identifiant in identifiants:
                raise ValueError(f"Chemin ou identifiant en double dans {inventaire}, ligne {numero}.")
            fiches[chemin] = {
                "document_id": identifiant,
                "version": version,
                "groupes_autorises": list(dict.fromkeys(groupes)),
            }
            identifiants.add(identifiant)
    return fiches


def lire_corpus(corpus: Path) -> list[Document]:
    fichiers = sorted(corpus.rglob("*.pdf"))
    chemins = {p.relative_to(corpus).as_posix() for p in fichiers}
    fiches = lire_metadonnees(corpus)
    manquants = chemins - fiches.keys()
    inconnus = fiches.keys() - chemins
    if manquants or inconnus:
        raise ValueError(
            f"Inventaire incohérent. PDF sans fiche : {sorted(manquants)}. "
            f"Fiches sans PDF : {sorted(inconnus)}."
        )

    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    documents = []
    for chemin in fichiers:
        fiche = fiches[chemin.relative_to(corpus).as_posix()]
        with pymupdf.open(chemin) as pdf:
            for numero, page in enumerate(pdf, start=1):
                metadata = {
                    **fiche,
                    "famille": chemin.parent.name,
                    "fichier": chemin.name,
                    "page": numero,
                }
                for passage in splitter.split_text(page.get_text("text", sort=True)):
                    documents.append(Document(
                        page_content=passage,
                        metadata={**metadata, "type_source": "Texte"},
                    ))
                for tableau in extraire_tableaux(page):
                    if any(any(ligne) for ligne in tableau):
                        documents.append(Document(
                            page_content=tableau_vers_texte(tableau),
                            metadata={**metadata, "type_source": "Tableau"},
                        ))
    return documents


def indexer(client: QdrantClient, corpus: Path) -> int:
    documents = lire_corpus(corpus)
    if not documents:
        raise ValueError("Le corpus ne contient aucun passage ni tableau indexable.")

    collection = f"{COLLECTION}_{uuid4().hex}"
    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
    )
    ouvrir_index(client, collection).add_documents(documents, batch_size=16)

    # L'alias public bascule une fois que toute la collection est indexée.
    operations = [
        models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=COLLECTION)),
        models.CreateAliasOperation(create_alias=models.CreateAlias(
            collection_name=collection,
            alias_name=COLLECTION,
        )),
    ]
    client.update_collection_aliases(change_aliases_operations=operations)
    return len(documents)


if __name__ == "__main__":
    client = QdrantClient(url=QDRANT_URL, timeout=30)
    try:
        nombre = indexer(client, Path("corpus"))
        print(f"{nombre} passages et tableaux publiés dans {COLLECTION}.")
    finally:
        client.close()
