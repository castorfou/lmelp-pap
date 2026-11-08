"""Lecture des notices du catalogue INA (catalogue.ina.fr).

La collecte (Playwright, voir ``ina_catalogue``) produit une ligne par notice
de la collection « Le masque et la plume », avec la colonne
``facette_litterature`` à ``oui`` pour les notices que l'INA classe en
Littérature.
"""

import re
from collections.abc import Iterable
from datetime import date

from lmelp_pap.liste import Attestation


SOURCE = "ina"

_MOTS_CLES = {
    "livres": r"littér|livre|roman|lire|édition|librairie|poète|goncourt",
    "théâtre": r"th[ée][âa]tre",
    "cinéma": r"cinéma|film",
    "opéra": r"opéra",
}


def lire_notices(lignes: Iterable[dict[str, str]]) -> list[Attestation]:
    """Une attestation par notice datée ; les notices sans date sont ignorées."""
    attestations = []
    for ligne in lignes:
        if not ligne.get("date_diffusion"):
            continue
        url = ligne["url_ina"].split("?", 1)[0]
        attestations.append(
            Attestation(
                source=SOURCE,
                source_id=_identifiant(url),
                date=date.fromisoformat(ligne["date_diffusion"]),
                themes=_themes(ligne),
                titre=ligne.get("titre") or None,
                chaine=ligne.get("chaine") or None,
                heure=_horaire(ligne.get("heure")),
                duree=_horaire(ligne.get("duree")),
                url=url,
            )
        )
    return attestations


def _identifiant(url: str) -> str:
    """``…/doc/TV-RADIO/PH_PHD88021484/titre`` → ``PH_PHD88021484``."""
    return url.rstrip("/").split("/")[-2]


def _themes(ligne: dict[str, str]) -> frozenset[str]:
    titre = (ligne.get("titre") or "").lower()
    themes = {t for t, motif in _MOTS_CLES.items() if re.search(motif, titre)}
    if ligne.get("facette_litterature") == "oui":
        themes.add("livres")
    return frozenset(themes)


def _horaire(valeur: str | None) -> str | None:
    """Garde ``HH:MM:SS`` ; les valeurs mal formées de l'INA donnent None."""
    if valeur and re.fullmatch(r"\d{2}:\d{2}:\d{2}", valeur):
        return valeur
    return None
