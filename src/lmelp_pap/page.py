"""Page HTML autonome de la liste des émissions, générée à partir de ses CSV.

La page embarque les données en JSON (``<script id="donnees">``) et le
JavaScript qui les affiche : elle s'ouvre hors ligne, sans serveur.
"""

import csv
import json
from collections import defaultdict
from importlib.resources import files
from pathlib import Path
from typing import Any

from lmelp_pap.arbitrages import THEMES


def construire_page(dossier: Path, arbitrage: bool = False) -> str:
    """Le HTML complet de la page, à partir des CSV de ``dossier``.

    En mode ``arbitrage``, la page porte en plus les contrôles de l'outil
    ``lmelp-pap arbitrer`` ; elle ne fonctionne alors que servie par lui.
    """
    gabarit = _ressource("page.html").replace(
        "__ARBITRAGE__",
        _ressource("arbitrage.html").replace(
            "__THEMES__", json.dumps(THEMES, ensure_ascii=False)
        )
        if arbitrage
        else "",
    )
    # « </ » fermerait le bloc <script> : « <\/ » est le même JSON.
    donnees = json.dumps(donnees_page(dossier), ensure_ascii=False)
    return gabarit.replace("__DONNEES__", donnees.replace("</", "<\\/"))


def donnees_page(dossier: Path) -> list[dict[str, Any]]:
    """Les émissions de la liste, telles que la page les affiche."""
    attestations = _par_emission(
        dossier / "attestations.csv", ("source", "date", "titre", "url")
    )
    enregistrements = _par_emission(
        dossier / "enregistrements.csv", ("url", "type", "duree")
    )
    doutes = _par_emission(dossier / "doutes.csv", ("type", "detail"))
    return [
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
            "arbitrage": (
                {"sorte": e["arbitrage"], "justification": e["justification_arbitrage"]}
                if e["arbitrage"]
                else None
            ),
        }
        for e in _lire(dossier / "emissions.csv")
    ]


def _ressource(nom: str) -> str:
    """Un fichier livré avec le paquet (gabarit de la page, mode arbitrage)."""
    return files("lmelp_pap").joinpath(nom).read_text(encoding="utf-8")


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
