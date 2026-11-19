"""Lecture des notices du catalogue INA (catalogue.ina.fr).

La collecte (Playwright, voir ``ina_catalogue``) produit une ligne par notice
de la collection « Le masque et la plume », avec la colonne
``facette_litterature`` à ``oui`` pour les notices que l'INA classe en
Littérature.
"""

import html
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Literal

from lmelp_pap.liste import Attestation


SOURCE = "ina"

_MOTS_CLES = {
    "livres": r"littér|livre|roman|lire|édition|librairie|poète|goncourt",
    "théâtre": r"th[ée][âa]tre|critiques dramatiques",
    "cinéma": r"cinéma|film",
    "opéra": r"opéra",
    "télévision": r"télévision",
    "musique": r"musique",
    "variétés": r"variétés",
}


# Les champs d'une fiche détaillée qui classent l'émission : descripteurs,
# chapeau, résumé producteur (« Cinéma », « LITTERAIRE »). Le résumé
# documentaire, texte libre où une émission cinéma cite le roman adapté à
# l'écran, ne sert qu'à défaut.
_CHAMPS_DE_CLASSEMENT = ("DE", "CHAP", "RESPROD")
_RESUME_DOCUMENTAIRE = "RES"


def lire_notices(
    lignes: Iterable[dict[str, str]], fiches: Mapping[str, str] | None = None
) -> list[Attestation]:
    """Une attestation par notice datée ; les notices sans date sont ignorées.

    ``fiches`` associe à l'identifiant d'une notice le HTML de sa fiche
    détaillée, quand elle est en cache : ses descripteurs, son chapeau et ses
    résumés donnent des thèmes que le titre seul ne donne pas.
    """
    attestations = []
    for ligne in lignes:
        if not ligne.get("date_diffusion"):
            continue
        url = ligne["url_ina"].split("?", 1)[0]
        source_id = identifiant(url)
        fiche = (fiches or {}).get(source_id)
        attestations.append(
            Attestation(
                source=SOURCE,
                source_id=source_id,
                date=date.fromisoformat(ligne["date_diffusion"]),
                themes=_themes(ligne, fiche),
                nature_date=_nature_date(fiche),
                titre=ligne.get("titre") or None,
                chaine=ligne.get("chaine") or None,
                heure=_horaire(ligne.get("heure")),
                duree=_horaire(ligne.get("duree")),
                url=url,
            )
        )
    return attestations


def identifiant(url: str) -> str:
    """``…/doc/TV-RADIO/PH_PHD88021484/titre`` → ``PH_PHD88021484``."""
    return url.rstrip("/").split("/")[-2]


def _themes(ligne: dict[str, str], fiche: str | None = None) -> frozenset[str]:
    """Les thèmes lus dans le titre de la notice et dans les champs de
    classement de sa fiche détaillée, à défaut dans son résumé documentaire ;
    la facette littérature ajoute les livres."""
    textes = [ligne.get("titre") or ""]
    if fiche is not None:
        textes += [_champ(fiche, code) or "" for code in _CHAMPS_DE_CLASSEMENT]
    themes = _mots_cles(" ".join(textes))
    if not themes and fiche is not None:
        themes = _mots_cles(_champ(fiche, _RESUME_DOCUMENTAIRE) or "")
    if ligne.get("facette_litterature") == "oui":
        themes |= {"livres"}
    return frozenset(themes)


def _mots_cles(texte: str) -> set[str]:
    """Les thèmes dont un mot-clé figure dans le texte, accents et casse ignorés."""
    texte = _sans_accents(texte.lower())
    return {
        t for t, motif in _MOTS_CLES.items() if re.search(_sans_accents(motif), texte)
    }


def _nature_date(fiche: str | None) -> Literal["première diffusion", "rediffusion"]:
    """Une notice dont le statut n'est pas « Première diffusion » (« Multidiffusé »)
    est une rediffusion : elle atteste l'émission sans dater sa première diffusion.
    Sans fiche, la notice date l'émission."""
    if fiche is None:
        return "première diffusion"
    statut = _champ(fiche, "STADIF")
    if statut is None or statut == "Première diffusion":
        return "première diffusion"
    return "rediffusion"


def _sans_accents(texte: str) -> str:
    """« LITTÉRAIRE », « LITTERAIRE » et « littéraire » se lisent pareil."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _champ(fiche: str, code: str) -> str | None:
    """Le texte d'un champ de la fiche détaillée (``<td id="DE">``), sans balises."""
    m = re.search(rf'<td id="{code}"[^>]*>(.*?)</td>', fiche, re.DOTALL)
    if m is None:
        return None
    return html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip() or None


def _horaire(valeur: str | None) -> str | None:
    """Garde ``HH:MM:SS`` ; les valeurs mal formées de l'INA donnent None."""
    if valeur and re.fullmatch(r"\d{2}:\d{2}:\d{2}", valeur):
        return valeur
    return None
