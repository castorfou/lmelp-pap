"""Lecture du fichier ``arbitrages.csv``, versionné à côté de la liste.

Colonnes : ``source``, ``source_id`` (l'attestation arbitrée), ``sorte``
(``thème`` ou ``existence``), ``valeur`` (les thèmes séparés par ``;``, ou
``n'existe pas``), ``justification`` (facultative) et ``date`` de la décision
(ISO 8601, jour ou jour et heure).
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Literal

from lmelp_pap.liste import Arbitrage


INEXISTANTE = "n'existe pas"
THEMES = (
    "livres",
    "cinéma",
    "théâtre",
    "opéra",
    "télévision",
    "musique",
    "variétés",
)
COLONNES = ["source", "source_id", "sorte", "valeur", "justification", "date"]


def lire_arbitrages(chemin: Path) -> list[Arbitrage]:
    """Les arbitrages du fichier, dans son ordre ; aucun s'il n'existe pas."""
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        return [_arbitrage(ligne, n) for n, ligne in enumerate(csv.DictReader(f), 2)]


def _arbitrage(ligne: dict[str, str], numero: int) -> Arbitrage:
    """L'arbitrage d'une ligne du fichier ; ``ValueError`` si elle est invalide."""
    sorte, valeur = ligne["sorte"].strip(), ligne["valeur"].strip()
    themes = frozenset(t.strip() for t in valeur.split(";") if t.strip())
    if sorte == "thème" and themes:
        sorte_lue: Literal["thème", "existence"] = "thème"
    elif sorte == "existence" and valeur == INEXISTANTE:
        sorte_lue, themes = "existence", frozenset()
    else:
        raise ValueError(
            f"arbitrages.csv, ligne {numero} : sorte « {sorte} » et valeur "
            f"« {valeur} » invalides (attendu : thème et des thèmes séparés par "
            f"« ; », ou existence et « {INEXISTANTE} »)"
        )
    return Arbitrage(
        source=ligne["source"].strip(),
        source_id=ligne["source_id"].strip(),
        sorte=sorte_lue,
        themes=themes,
        justification=(ligne.get("justification") or "").strip(),
        date=datetime.fromisoformat(ligne["date"].strip()),
    )


def ecrire_arbitrages(chemin: Path, arbitrages: list[Arbitrage]) -> None:
    """Réécrit le fichier avec ces arbitrages, dans cet ordre."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, lineterminator="\n")
        ecrivain.writeheader()
        ecrivain.writerows(
            {
                "source": a.source,
                "source_id": a.source_id,
                "sorte": a.sorte,
                "valeur": valeur(a),
                "justification": a.justification,
                "date": _date(a.date),
            }
            for a in arbitrages
        )


def valeur(arbitrage: Arbitrage) -> str:
    """La colonne ``valeur`` : les thèmes séparés par ``;``, ou ``n'existe pas``."""
    if arbitrage.sorte == "existence":
        return INEXISTANTE
    return ";".join(sorted(arbitrage.themes))


def _date(moment: datetime) -> str:
    """Le jour seul à minuit (saisie à la main), sinon le jour et l'heure."""
    if moment.time() == datetime.min.time():
        return moment.date().isoformat()
    return moment.isoformat(timespec="seconds")
