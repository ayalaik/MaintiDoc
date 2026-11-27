import logging
import os
import re
from hmac import compare_digest
from pathlib import Path
from typing import Annotated, Literal

import pymupdf
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field

from index_qdrant import lire_metadonnees
from query_multimodal import ABSTENTION, poser_question


app = FastAPI(title="MaintiDoc")
logger = logging.getLogger(__name__)
authentification = HTTPBasic()
CORPUS = Path(__file__).resolve().parent / "corpus"
MOTS_DE_PASSE = {
    "demo_pompes": "MAINTIDOC_DEMO_POMPES_PASSWORD",
    "demo_moteurs": "MAINTIDOC_DEMO_MOTEURS_PASSWORD",
}


def groupe_connecte(identifiants: Annotated[HTTPBasicCredentials, Depends(authentification)]) -> str:
    secrets = {groupe: os.getenv(variable) for groupe, variable in MOTS_DE_PASSE.items()}
    if not all(secrets.values()) or len(set(secrets.values())) != len(secrets):
        raise HTTPException(status_code=503, detail="Configure deux mots de passe de démonstration distincts.")

    attendu = secrets.get(identifiants.username)
    if attendu is None or not compare_digest(identifiants.password.encode("utf-8"), attendu.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="Identifiants de démonstration invalides.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return identifiants.username


Groupe = Annotated[str, Depends(groupe_connecte)]


class Question(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    document_id: str
    type_source: str
    famille: str
    fichier: str
    page: int | str
    score: float | None


class Reponse(BaseModel):
    reponse: str
    sources: list[Source]


def normaliser_reference(texte: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", texte.casefold()))


@app.post("/questions", response_model=Reponse)
def questionner(demande: Question, groupe: Groupe, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        inventaire = lire_metadonnees(CORPUS)
        question_normalisee = f" {normaliser_reference(demande.question)} "
        documents = []
        documents_cibles = []
        for chemin, fiche in inventaire.items():
            identifiant = fiche["document_id"]
            if groupe in fiche["groupes_autorises"]:
                documents.append(identifiant)
            references = [identifiant, Path(chemin).stem, *fiche["alias"]]
            if any(
                reference and f" {reference} " in question_normalisee
                for reference in map(normaliser_reference, references)
            ):
                documents_cibles.append(identifiant)

        if documents_cibles:
            if any(identifiant not in documents for identifiant in documents_cibles):
                return Reponse(reponse=ABSTENTION, sources=[])
            documents = documents_cibles
        reponse, sources = poser_question(
            demande.question, groupe=groupe, documents_autorises=documents,
        )
    except Exception:
        logger.error("Échec de la recherche ou de la génération du RAG.")
        raise HTTPException(
            status_code=503,
            detail="Le moteur documentaire est indisponible. Vérifie Qdrant, l’index et Ollama.",
        ) from None
    return Reponse(reponse=reponse, sources=sources)


def chemin_document_autorise(document_id: str, groupe: str) -> Path:
    for relatif, fiche in lire_metadonnees(CORPUS).items():
        if fiche["document_id"] != document_id:
            continue
        if groupe not in fiche["groupes_autorises"]:
            raise HTTPException(status_code=403, detail="Accès refusé à ce document.")
        chemin = (CORPUS / relatif).resolve()
        if chemin.is_relative_to(CORPUS.resolve()) and chemin.suffix.lower() == ".pdf" and chemin.is_file():
            return chemin
        break
    raise HTTPException(status_code=404, detail="Document introuvable.")


@app.get("/documents/{document_id}", response_class=FileResponse)
def consulter_document(document_id: str, groupe: Groupe):
    chemin = chemin_document_autorise(document_id, groupe)
    return FileResponse(chemin, media_type="application/pdf", headers={"Cache-Control": "no-store"})


@app.get("/documents/{document_id}/pages/{page}", responses={200: {"content": {"image/png": {}}}}, response_class=Response)
def apercu_page(document_id: str, page: int, groupe: Groupe, mode: Literal["page", "figure"] = "page"):
    chemin = chemin_document_autorise(document_id, groupe)
    try:
        with pymupdf.open(chemin) as document:
            if not 1 <= page <= len(document):
                raise HTTPException(status_code=404, detail="Page introuvable.")
            source = document[page - 1]
            zone = source.rect
            if mode == "figure":
                images = [
                    (pymupdf.Rect(image["bbox"]) * source.rotation_matrix) & source.rect
                    for image in source.get_image_info()
                ]
                figures = [image for image in images if image.width >= 60 and image.height >= 60]
                if not figures:
                    raise HTTPException(status_code=404, detail="Aucune figure intégrée sur cette page.")
                zone = max(figures, key=lambda image: image.get_area())
            echelle = min(3 if mode == "figure" else 2, 1600 / max(zone.width, zone.height))
            png = source.get_pixmap(matrix=pymupdf.Matrix(echelle, echelle), clip=zone).tobytes("png")
    except (RuntimeError, ValueError):
        raise HTTPException(status_code=422, detail="Impossible de convertir cette page en image.") from None
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})
