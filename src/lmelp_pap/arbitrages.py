"""Lecture du fichier ``arbitrages.csv``, versionné à côté de la liste.

Colonnes : ``source``, ``source_id`` (l'attestation arbitrée), ``sorte``
(``thème``, ``existence``, ``date``, ``rapprochement``, ou ``écoute`` pour un
renvoi à l'écoute), ``valeur`` (les thèmes séparés par ``;``, ``existe`` ou
``n'existe pas``, la date retenue au format ISO, ``à écouter``, ou pour un
rapprochement ``garder ici`` ou l'attestation cible ``source:source_id``),
``justification`` (facultative) et ``date`` de la décision (ISO 8601, jour ou
jour et heure).
"""

import csv
from datetime import date, datetime
from pathlib import Path

from lmelp_pap.liste import HOMMAGE, Arbitrage, CleAttestation, Sorte


EXISTANTE = "existe"
INEXISTANTE = "n'existe pas"
A_ECOUTER = "à écouter"
GARDER_ICI = "garder ici"
THEMES = (
    "livres",
    "cinéma",
    "théâtre",
    "opéra",
    "télévision",
    "musique",
    "variétés",
    HOMMAGE,
)
COLONNES = ["source", "source_id", "sorte", "valeur", "justification", "date"]


def erreur_de_themes(themes: frozenset[str]) -> str | None:
    """Pourquoi ces thèmes ne font pas un arbitrage de thème, ou None.

    Il en faut au moins un, parmi ``THEMES`` ; ``hommage`` est seul.
    """
    if not themes or not themes <= set(THEMES):
        return f"thèmes invalides : {sorted(themes)} (attendu : {THEMES})"
    if HOMMAGE in themes and len(themes) > 1:
        return f"le thème {HOMMAGE} ne se cumule avec aucun autre : {sorted(themes)}"
    return None


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
    retenue, cible, existe = None, None, False
    if sorte == "thème" and themes:
        if erreur := erreur_de_themes(themes):
            raise ValueError(f"arbitrages.csv, ligne {numero} : {erreur}")
        sorte_lue: Sorte = "thème"
    elif sorte == "existence" and valeur in (EXISTANTE, INEXISTANTE):
        sorte_lue, themes, existe = "existence", frozenset(), valeur == EXISTANTE
    elif sorte == "écoute" and valeur == A_ECOUTER:
        sorte_lue, themes = "écoute", frozenset()
    elif sorte == "date" and (retenue := lire_date(valeur)):
        sorte_lue, themes = "date", frozenset()
    elif sorte == "rapprochement" and (
        valeur == GARDER_ICI or (cible := _attestation(valeur))
    ):
        sorte_lue, themes = "rapprochement", frozenset()
    else:
        raise ValueError(
            f"arbitrages.csv, ligne {numero} : sorte « {sorte} » et valeur "
            f"« {valeur} » invalides (attendu : thème et des thèmes séparés par "
            f"« ; », existence et « {EXISTANTE} » ou « {INEXISTANTE} », date et une date "
            f"AAAA-MM-JJ, écoute et « {A_ECOUTER} », ou rapprochement et "
            f"« {GARDER_ICI} » ou une attestation source:source_id)"
        )
    return Arbitrage(
        source=ligne["source"].strip(),
        source_id=ligne["source_id"].strip(),
        sorte=sorte_lue,
        themes=themes,
        date_retenue=retenue,
        cible=cible,
        existe=existe,
        justification=(ligne.get("justification") or "").strip(),
        date=datetime.fromisoformat(ligne["date"].strip()),
    )


def _attestation(texte: str) -> CleAttestation | None:
    """Une attestation ``source:source_id``, ou None."""
    source, _, source_id = texte.partition(":")
    return (source, source_id) if source and source_id else None


def lire_date(texte: str) -> date | None:
    """Une date ``AAAA-MM-JJ``, ou None si le texte n'en est pas une."""
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return None


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


def retirer_arbitrages(chemin: Path, cles: set[CleAttestation]) -> int:
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
    """La colonne ``valeur`` : les thèmes séparés par ``;``, ``existe`` ou
    ``n'existe pas``, la date retenue, ``à écouter``, ``garder ici`` ou l'attestation cible."""
    if arbitrage.sorte == "existence":
        return EXISTANTE if arbitrage.existe else INEXISTANTE
    if arbitrage.sorte == "écoute":
        return A_ECOUTER
    if arbitrage.sorte == "date":
        return arbitrage.date_retenue.isoformat() if arbitrage.date_retenue else ""
    if arbitrage.sorte == "rapprochement":
        return ":".join(arbitrage.cible) if arbitrage.cible else GARDER_ICI
    return ";".join(sorted(arbitrage.themes))


def _date(moment: datetime) -> str:
    """Le jour seul à minuit (saisie à la main), sinon le jour et l'heure."""
    if moment.time() == datetime.min.time():
        return moment.date().isoformat()
    return moment.isoformat(timespec="seconds")
