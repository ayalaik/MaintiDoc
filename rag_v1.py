"""Configuration commune de l'indexation et du RAG V1."""

import os

from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

COLLECTION = "maintidoc_bge_m3"
EMBEDDING_MODEL = "bge-m3:567m"
EMBEDDING_DIM = 1024
OLLAMA_URL = os.getenv("MAINTIDOC_OLLAMA_URL", "http://127.0.0.1:11434")
QDRANT_URL = os.getenv("MAINTIDOC_QDRANT_URL", "http://127.0.0.1:6333")


def ouvrir_index(client: QdrantClient, collection: str = COLLECTION) -> QdrantVectorStore:
    return QdrantVectorStore(
        client=client,
        collection_name=collection,
        embedding=OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_URL,
            client_kwargs={"timeout": 300.0},
        ),
        # La taille et la distance sont fixées lors de la création de l'index.
        validate_collection_config=False,
    )
