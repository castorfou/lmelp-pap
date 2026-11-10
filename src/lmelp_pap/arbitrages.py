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


def ajouter_arbitrage(chemin: Path, arbitrage: Arbitrage) -> None:
    """Ajoute l'arbitrage en fin de fichier, sans toucher aux lignes existantes."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not chemin.exists() or not chemin.read_text(encoding="utf-8").strip()
    if not nouveau and not chemin.read_bytes().endswith(b"\n"):
        with chemin.open("a", encoding="utf-8") as f:
            f.write("\n")
    with chemin.open("w" if nouveau else "a", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, lineterminator="\n")
        if nouveau:
            ecrivain.writeheader()
        ecrivain.writerow(
            {
                "source": arbitrage.source,
                "source_id": arbitrage.source_id,
                "sorte": arbitrage.sorte,
                "valeur": valeur(arbitrage),
                "justification": arbitrage.justification,
                "date": _date(arbitrage.date),
            }
        )


def retirer_arbitrages(chemin: Path, cles: set[tuple[str, str]]) -> int:
    """Retire les lignes des attestations ``cles``, sans réécrire les autres.

    Rend le nombre de lignes retirées.
    """
    if not chemin.exists():
        return 0
    entete, *lignes = chemin.read_text(encoding="utf-8").splitlines(keepends=True)
    gardees = [
        ligne
        for ligne in lignes
        if not (
            (champs := next(csv.DictReader([entete, ligne]), None))
            and (champs["source"].strip(), champs["source_id"].strip()) in cles
        )
    ]
    if len(gardees) < len(lignes):
        chemin.write_text(entete + "".join(gardees), encoding="utf-8")
    return len(lignes) - len(gardees)


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
