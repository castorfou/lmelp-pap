"""Page HTML autonome de la liste des émissions, générée à partir de ses CSV.

La page embarque les données en JSON (``<script id="donnees">``) et le
JavaScript qui les affiche : elle s'ouvre hors ligne, sans serveur.
"""

import csv
import json
from collections import defaultdict
from importlib.resources import files
from pathlib import Path


def construire_page(dossier: Path) -> str:
    """Le HTML complet de la page, à partir des CSV de ``dossier``."""
    attestations = _par_emission(
        dossier / "attestations.csv", ("source", "date", "titre", "url")
    )
    enregistrements = _par_emission(dossier / "enregistrements.csv", ("url", "type"))
    doutes = _par_emission(dossier / "doutes.csv", ("type", "detail"))
    emissions = [
        {
            "id": e["id"],
            "date": e["date"],
            "themes": e["themes"].split(";") if e["themes"] else [],
            "titre": e["titre"],
            "description": e["description"],
            "animateur": e["animateur"],
            "chaine": e["chaine"],
            "duree": e["duree"],
            "attestations": attestations[e["id"]],
            "enregistrements": enregistrements[e["id"]],
            "doutes": doutes[e["id"]],
        }
        for e in _lire(dossier / "emissions.csv")
    ]
    gabarit = files("lmelp_pap").joinpath("page.html").read_text(encoding="utf-8")
    # « </ » fermerait le bloc <script> : « <\/ » est le même JSON.
    donnees = json.dumps(emissions, ensure_ascii=False).replace("</", "<\\/")
    return gabarit.replace("__DONNEES__", donnees)


def _par_emission(
    chemin: Path, champs: tuple[str, ...]
) -> defaultdict[str, list[dict[str, str]]]:
    """Les lignes d'un CSV lié, regroupées par ``emission_id``."""
    groupes: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for ligne in _lire(chemin):
        groupes[ligne["emission_id"]].append({c: ligne[c] for c in champs})
    return groupes


def _lire(chemin: Path) -> list[dict[str, str]]:
    """Les lignes d'un CSV de la liste, colonne par colonne."""
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
