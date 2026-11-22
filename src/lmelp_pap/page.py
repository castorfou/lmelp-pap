"""Page HTML autonome de la liste des émissions, générée à partir de ses CSV.

La page embarque les données en JSON (``<script id="donnees">``) et le
JavaScript qui les affiche : elle s'ouvre hors ligne, sans serveur.
"""

import base64
import csv
import json
from collections import defaultdict
from importlib.resources import files
from pathlib import Path
from typing import Any

from lmelp_pap.arbitrages import THEMES
from lmelp_pap.liste import HOMMAGE


def construire_page(dossier: Path, arbitrage: bool = False) -> str:
    """Le HTML complet de la page, à partir des CSV de ``dossier``.

    En mode ``arbitrage``, la page porte en plus les contrôles de l'outil
    ``lmelp-pap arbitrer`` ; elle ne fonctionne alors que servie par lui.
    """
    # Le favicon voyage dans la page (data URI) : elle s'ouvre sans serveur.
    favicon = base64.b64encode(icone("favicon-32x32.png")).decode()
    gabarit = (
        _ressource("page.html")
        .replace("__FAVICON__", favicon)
        .replace(
            "__ARBITRAGE__",
            _ressource("arbitrage.html")
            .replace("__THEMES__", json.dumps(THEMES, ensure_ascii=False))
            .replace("__HOMMAGE__", json.dumps(HOMMAGE, ensure_ascii=False))
            if arbitrage
            else "",
        )
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
    doutes = _par_emission(
        dossier / "doutes.csv", ("type", "detail", "a_ecouter", "source", "source_id")
    )
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
            "doutes": [
                {
                    "type": d["type"],
                    "detail": d["detail"],
                    "a_ecouter": d["a_ecouter"] == "oui",
                    # l'attestation sur laquelle porte le doute, s'il y en a une
                    "source": d["source"],
                    "source_id": d["source_id"],
                }
                for d in doutes[e["id"]]
            ],
            "arbitrage": (
                {"sorte": e["arbitrage"], "justification": e["justification_arbitrage"]}
                if e["arbitrage"]
                else None
            ),
        }
        for e in _lire(dossier / "emissions.csv")
    ]


def icone(nom: str) -> bytes:
    """Une icône livrée avec le paquet (``lmelp_pap/icones/``, produites par
    ``scripts/generer_favicon.py``)."""
    return files("lmelp_pap").joinpath("icones", nom).read_bytes()


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
