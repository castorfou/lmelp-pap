"""Lecture des pages podcast du Masque et la Plume sur radiofrance.fr.

Les fiches d'émission portent leurs données dans du JSON-LD schema.org
(``RadioEpisode``, ``NewsArticle``) et leurs étiquettes dans
``<meta property="article:tag">``.
"""

import html as html_lib
import json
import re
from dataclasses import replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from lmelp_pap.liste import Attestation, Enregistrement
from lmelp_pap.sources.audio_radiofrance import lire_nom_fichier


SOURCE = "radiofrance"
_PARIS = ZoneInfo("Europe/Paris")
_THEMES = {"livres": "livres", "cinéma": "cinéma", "cinema": "cinéma",
           "théâtre": "théâtre", "theatre": "théâtre"}  # fmt: skip


def lire_fiche(page: str) -> Attestation | None:
    """Lit une fiche d'émission et renvoie ce qu'elle atteste.

    Une page qui n'est pas une fiche d'émission (une page de série, par
    exemple) n'atteste rien.
    """
    graphe = _json_ld(page)
    if "RadioEpisode" not in graphe:
        return None
    episode = graphe["RadioEpisode"]
    article = graphe.get("NewsArticle", {})
    url: str = episode["url"]
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    audio = episode.get("mainEntity") or {}

    titre = _texte(article.get("headline") or episode.get("name"))
    duree = _duree(audio.get("duration"))
    enregistrements = _enregistrements(audio.get("contentUrl"), duree)
    extrait = _est_un_extrait(duree, enregistrements)
    return Attestation(
        source=SOURCE,
        source_id=slug,
        date=_date_paris(episode["dateCreated"]),
        themes=_themes(slug, titre, _etiquettes(page)),
        titre=titre,
        description=_texte(article.get("description")),
        duree=duree,
        animateur=", ".join(p["name"] for p in episode.get("director", [])) or None,
        url=url,
        enregistrements=tuple(
            replace(e, type="extrait") if extrait else e for e in enregistrements
        ),
        extrait=extrait,
    )


def _json_ld(page: str) -> dict[str, dict[str, Any]]:
    """Les objets JSON-LD de la page, indexés par type."""
    objets: dict[str, dict[str, Any]] = {}
    for bloc in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', page, re.DOTALL
    ):
        donnees = json.loads(bloc)
        for objet in donnees.get("@graph", [donnees]):
            objets.setdefault(objet.get("@type", ""), objet)
    return objets


def _texte(valeur: str | None) -> str | None:
    """Texte nettoyé : espaces insécables normalisées, vide ou « . » → None."""
    if valeur is None:
        return None
    texte = re.sub(r"[\u00a0\u202f\s]+", " ", valeur).strip()
    return texte if texte.strip(" .") else None


def _etiquettes(page: str) -> list[str]:
    """Les étiquettes de la fiche (``<meta property="article:tag">``)."""
    m = re.search(r'<meta property="article:tag" content="([^"]*)"', page)
    return html_lib.unescape(m.group(1)).split(",") if m else []


def _themes(slug: str, titre: str | None, etiquettes: list[str]) -> frozenset[str]:
    """Thèmes lus dans les étiquettes, le début de l'URL et le titre exact.

    Le titre compte aussi précédé du nom de l'émission (« Le masque et la
    plume cinéma »).
    """
    titre = re.sub(r"^le masque et la plume\s*", "", (titre or "").lower())
    candidats = [*etiquettes, slug.split("-", 1)[0], titre]
    return frozenset(
        _THEMES[c.strip().lower()] for c in candidats if c.strip().lower() in _THEMES
    )


def _date_paris(horodatage: str) -> Any:
    """Le jour, à l'heure de Paris, d'un horodatage ISO 8601."""
    instant = datetime.fromisoformat(horodatage)
    return instant.astimezone(_PARIS).date()


def _duree(iso: str | None) -> str | None:
    """Convertit une durée ISO 8601 (``P0Y0M0DT0H30M15S``) en ``HH:MM:SS``."""
    if not iso:
        return None
    m = re.search(r"T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if m is None:
        return None
    h, mn, s = (int(x or 0) for x in m.groups())
    return f"{h:02d}:{mn:02d}:{s:02d}"


# Une émission entière dure de 40 min à 1 h, une fiche par livre ou par film
# moins de 20 min : rien entre les deux sur radiofrance.fr. Seuil à 25 min.
_DUREE_MIN_ENTIERE = "00:25:00"


def _est_un_extrait(
    duree: str | None, enregistrements: tuple[Enregistrement, ...]
) -> bool:
    """Une fiche courte, ou une archive (lettre ``E`` du fichier audio)."""
    courte = duree is not None and duree < _DUREE_MIN_ENTIERE
    return courte or any(e.type == "extrait" for e in enregistrements)


def _enregistrements(url: str | None, duree: str | None) -> tuple[Enregistrement, ...]:
    """Le fichier audio de la fiche, typé d'après son nom (intégral ou extrait),
    avec la durée que la fiche donne."""
    if not url:
        return ()
    fichier = lire_nom_fichier(url)
    return (
        Enregistrement(
            url=url, type=fichier.type if fichier else "intégral", duree=duree
        ),
    )


def lire_page_liste(page: str) -> list[str]:
    """Les URL des fiches d'émission listées sur une page podcast (``?p=N``)."""
    liste = _json_ld(page).get("ItemList", {})
    return [element["url"] for element in liste.get("itemListElement", [])]
