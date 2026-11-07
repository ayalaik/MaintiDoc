
from pathlib import Path
 
import psycopg2
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.readers.file import PyMuPDFReader
from llama_index.vector_stores.postgres import PGVectorStore
 
# ---------- Configuration ----------
CORPUS_DIR = "corpus"
DB = dict(host="localhost", port=5432, database="maintidoc",
          user="maintidoc", password="motdepasse")
TABLE_NAME = "chunks"          # LlamaIndex crée la table "data_chunks"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768                # dimension de nomic-embed-text
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
RESET_TABLE = True             # True = repart d'une table vide à chaque lancement
MAX_CHUNKS = 3000              # garde-fou : on s'arrête si le corpus est suspect
 
# ---------- Modèles ----------
Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL)
Settings.node_parser = SentenceSplitter(chunk_size=CHUNK_SIZE,
                                        chunk_overlap=CHUNK_OVERLAP)
 
# ---------- 1. Lecture des PDF, page par page ----------
reader = PyMuPDFReader()
documents = []
 
for pdf in sorted(Path(CORPUS_DIR).rglob("*.pdf")):
    try:
        pages = reader.load_data(file_path=pdf)
    except Exception as e:
        print(f"[ERREUR] {pdf.name} illisible : {e}")
        continue
 
    gardees = 0
    for numero, page in enumerate(pages, start=1):
        # Nettoyage : suppression des caractères NUL (refusés par PostgreSQL)
        texte = page.get_content().replace("\x00", "").strip()
 
        # On ignore les pages vides ou absurdement longues (texte corrompu)
        if not (20 < len(texte) < 20000):
            continue
 
        # Nouveau document avec métadonnées minimales
        documents.append(Document(
            text=texte,
            metadata={
                "famille": pdf.parent.name,
                "fichier": pdf.name,
                "page": numero,
            },
        ))
        gardees += 1
 
    print(f"{pdf.parent.name}/{pdf.name} : {gardees}/{len(pages)} pages gardées")
 
if not documents:
    raise SystemExit("Aucun document exploitable dans 'corpus/'. Vérifie tes PDF.")
 
print(f"\n{len(documents)} pages au total")
 
# ---------- 2. Contrôle du nombre de chunks AVANT les embeddings ----------
nodes = Settings.node_parser.get_nodes_from_documents(documents)
print(f"{len(nodes)} chunks à indexer")
 
if len(nodes) > MAX_CHUNKS:
    raise SystemExit(
        f"{len(nodes)} chunks, c'est trop (max {MAX_CHUNKS}). "
        "Un PDF est probablement corrompu : arrêt avant le calcul des embeddings."
    )
 
# ---------- 3. Table propre (optionnel) ----------
if RESET_TABLE:
    conn = psycopg2.connect(host=DB["host"], port=DB["port"], dbname=DB["database"],
                            user=DB["user"], password=DB["password"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS data_{TABLE_NAME};")
    conn.close()
    print("Table réinitialisée")
 
# ---------- 4. Connexion à PGVector ----------
vector_store = PGVectorStore.from_params(
    **DB,
    table_name=TABLE_NAME,
    embed_dim=EMBED_DIM,
)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
 
# ---------- 5. Indexation : embeddings + stockage ----------
index = VectorStoreIndex(
    nodes,
    storage_context=storage_context,
    show_progress=True,
)
 
print("Ingestion terminée")
 