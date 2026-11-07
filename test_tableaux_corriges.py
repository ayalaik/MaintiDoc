
from pathlib import Path
import pymupdf

PDF = Path("corpus/famille_B/fiche_technique_moteur_ME-30.pdf")

if not PDF.exists():
    raise SystemExit(f"Fichier introuvable : {PDF}")

with pymupdf.open(PDF) as doc:
    page = doc[0]
    tables = page.find_tables()

    for numero, table in enumerate(tables.tables, start=1):
        print(f"\n===== TABLEAU {numero} =====")

        # Chaque ligne contient les cellules détectées
        for row in table.rows:
            valeurs = []

            for cell in row.cells:
                if cell is None:
                    valeurs.append("")
                    continue

                # Extraire directement le texte de la zone
                # de la cellule avec les espaces préservés
                texte = page.get_text(
                    "text",
                    clip=pymupdf.Rect(cell),
                    sort=True
                ).strip()

                texte = " ".join(texte.split())
                valeurs.append(texte)

            print(" | ".join(valeurs))
