import logging
import os
from hmac import compare_digest
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field

from index_qdrant import lire_metadonnees
from query_multimodal import poser_question


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


@app.post("/questions", response_model=Reponse)
def questionner(demande: Question, groupe: Groupe, response: Response):
    try:
        documents = [
            fiche["document_id"]
            for fiche in lire_metadonnees(CORPUS).values()
            if groupe in fiche["groupes_autorises"]
        ]
        reponse, sources = poser_question(
            demande.question, groupe=groupe, documents_autorises=documents,
        )
    except Exception:
        logger.error("Échec de la recherche ou de la génération du RAG.")
        raise HTTPException(
            status_code=503,
            detail="Le moteur documentaire est indisponible. Vérifie Qdrant, l’index et Ollama.",
        ) from None
    response.headers["Cache-Control"] = "no-store"
    return Reponse(reponse=reponse, sources=sources)


@app.get("/documents/{document_id}", response_class=FileResponse)
def consulter_document(document_id: str, groupe: Groupe):
    for relatif, fiche in lire_metadonnees(CORPUS).items():
        if fiche["document_id"] != document_id:
            continue
        if groupe not in fiche["groupes_autorises"]:
            raise HTTPException(status_code=403, detail="Accès refusé à ce document.")
        chemin = (CORPUS / relatif).resolve()
        if chemin.is_relative_to(CORPUS.resolve()) and chemin.suffix.lower() == ".pdf" and chemin.is_file():
            return FileResponse(chemin, media_type="application/pdf", headers={"Cache-Control": "no-store"})
        break
    raise HTTPException(status_code=404, detail="Document introuvable.")
