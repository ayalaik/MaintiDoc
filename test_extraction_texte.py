
from pathlib import Path
import pymupdf

pdf_path = Path(
    "corpus/famille_B/fiche_technique_moteur_ME-30.pdf"
)

if not pdf_path.exists():
    raise SystemExit(f"PDF introuvable : {pdf_path}")

with pymupdf.open(pdf_path) as doc:
    page = doc[0]

    print("\n===== TEXTE NORMAL =====")
    print(page.get_text("text"))

    print("\n===== TEXTE AVEC TRI =====")
    print(page.get_text("text", sort=True))

    print("\n===== TABLEAU EXTRAIT =====")
    for table in page.find_tables().tables:
        for ligne in table.extract():
            print(ligne)
