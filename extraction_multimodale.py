
from pathlib import Path
import json
import pymupdf

# ==========================================
# 1. CONFIGURATION
# ==========================================

CORPUS_DIR = Path("corpus")
OUTPUT_DIR = Path("extractions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

resultats = []


# ==========================================
# 2. EXTRACTION CORRIGEE DES TABLEAUX
# ==========================================

def extraire_tableaux(page):
    tableaux = []

    try:
        tables = page.find_tables()

        for table in tables.tables:
            lignes = []

            for row in table.rows:
                cellules = []

                for cell in row.cells:

                    if cell is None:
                        cellules.append("")
                        continue

                    # Extraction dans la zone de la cellule
                    texte_cellule = page.get_text(
                        "text",
                        clip=pymupdf.Rect(cell),
                        sort=True
                    )

                    # Nettoyage des espaces
                    texte_cellule = " ".join(
                        texte_cellule.split()
                    )

                    cellules.append(texte_cellule)

                lignes.append(cellules)

            tableaux.append(lignes)

    except Exception as erreur:
        print(f"Erreur extraction tableau : {erreur}")

    return tableaux


# ==========================================
# 3. CONVERSION DES TABLEAUX EN TEXTE
# ==========================================

def tableau_vers_texte(tableau):
    lignes_texte = []

    for ligne in tableau:
        cellules = [
            str(cellule).strip()
            for cellule in ligne
        ]

        lignes_texte.append(" | ".join(cellules))

    return "\n".join(lignes_texte)


# ==========================================
# 4. PARCOURS DES PDF
# ==========================================

for pdf_path in sorted(CORPUS_DIR.rglob("*.pdf")):

    print(f"\nAnalyse : {pdf_path.name}")

    with pymupdf.open(pdf_path) as document:

        for numero_page, page in enumerate(
            document, start=1
        ):

            # --------------------------
            # A. EXTRACTION DU TEXTE
            # --------------------------

            texte = page.get_text(
                "text",
                sort=True
            )

            # --------------------------
            # B. EXTRACTION DES IMAGES
            # --------------------------

            images = []

            dossier_images = (
                OUTPUT_DIR
                / pdf_path.parent.name
                / pdf_path.stem
            )

            dossier_images.mkdir(
                parents=True,
                exist_ok=True
            )

            for index, image_info in enumerate(
                page.get_images(full=True),
                start=1
            ):

                xref = image_info[0]

                image_data = document.extract_image(
                    xref
                )

                extension = image_data["ext"]

                nom_image = (
                    f"{pdf_path.stem}_"
                    f"p{numero_page}_"
                    f"img{index}.{extension}"
                )

                chemin_image = (
                    dossier_images / nom_image
                )

                chemin_image.write_bytes(
                    image_data["image"]
                )

                images.append(
                    str(chemin_image)
                )

            # --------------------------
            # C. EXTRACTION DES TABLEAUX
            # --------------------------

            tableaux = extraire_tableaux(page)

            tableaux_texte = [
                tableau_vers_texte(tableau)
                for tableau in tableaux
            ]

            # --------------------------
            # D. METADONNEES
            # --------------------------

            resultats.append({

                "famille": pdf_path.parent.name,

                "fichier": pdf_path.name,

                "page": numero_page,

                "texte": texte,

                "images": images,

                "tableaux": tableaux,

                "tableaux_texte": tableaux_texte

            })

            print(
                f"Page {numero_page} : "
                f"{len(images)} images, "
                f"{len(tableaux)} tableaux"
            )


# ==========================================
# 5. SAUVEGARDE JSON
# ==========================================

fichier_sortie = (
    OUTPUT_DIR / "extractions.json"
)

with open(
    fichier_sortie,
    "w",
    encoding="utf-8"
) as fichier:

    json.dump(
        resultats,
        fichier,
        ensure_ascii=False,
        indent=2
    )

print("\nExtraction terminée !")

print(
    f"Résultats enregistrés dans : "
    f"{fichier_sortie}"
)
