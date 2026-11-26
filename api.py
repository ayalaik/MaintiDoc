import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from query_multimodal import poser_question


app = FastAPI(title="MaintiDoc")
logger = logging.getLogger(__name__)


class Question(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    type_source: str
    famille: str
    fichier: str
    page: int | str
    score: float | None


class Reponse(BaseModel):
    reponse: str
    sources: list[Source]


@app.post("/questions", response_model=Reponse)
def questionner(demande: Question):
    try:
        reponse, sources = poser_question(demande.question)
    except Exception:
        logger.error("Échec de la recherche ou de la génération du RAG.")
        raise HTTPException(
            status_code=503,
            detail="Le moteur documentaire est indisponible. Vérifie PostgreSQL et Ollama.",
        ) from None
    return Reponse(reponse=reponse, sources=sources)
