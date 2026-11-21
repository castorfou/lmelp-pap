"""La diffusion d'une émission dans l'Open API Radio France, lue à la demande.

L'API (GraphQL, en-tête ``X-Token``) n'a pas de requête par identifiant de
diffusion : on lit les diffusions de France Inter du jour de l'émission (heure
de Paris) et on retient celle dont l'URL est une page radiofrance.fr connue de
l'émission, sinon la première du Masque et la Plume.

Les CGU de l'API (art. 5.3) interdisent de stocker ou de mettre en cache ses
données : ce module ne garde rien, ni sur disque ni en mémoire, et ses erreurs
ne disent que leur nature (statut HTTP, exception), jamais le contenu reçu.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests


POINT = "https://openapi.radiofrance.fr/v1/graphql"
MASQUE = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume"
# Les diffusions lues par requête, et le nombre de pages au plus pour un jour.
PAR_PAGE = 100
PAGES_MAX = 3
DELAI = 15  # secondes
PARIS = ZoneInfo("Europe/Paris")

# Les relations de ``personalitiesConnection`` : l'équipe (animateur et
# critiques) et les invités ; ``tag`` (personnalité citée) n'est pas retenu.
EQUIPE = ("staff", "producer")
INVITES = ("guest",)

REQUETE = """query ($start: Int, $end: Int, $first: Int, $after: String) {
  diffusions(station: FRANCEINTER, start: $start, end: $end,
             first: $first, after: $after) {
    edges {
      cursor
      node {
        id title standFirst url published_date
        show { id url }
        personalitiesConnection { edges { relation info node { id name } } }
      }
    }
  }
}"""


class ApiRadioFranceError(RuntimeError):
    """L'API n'a pas répondu, ou en erreur ; le message n'en dit que la nature."""


@dataclass(frozen=True)
class Personnalite:
    """Une personne citée par la diffusion, avec son rôle s'il est donné."""

    nom: str
    role: str | None


@dataclass(frozen=True)
class Diffusion:
    """Ce que l'API dit d'une diffusion du Masque."""

    titre: str | None
    resume: str | None
    url: str | None
    equipe: tuple[Personnalite, ...]
    invites: tuple[Personnalite, ...]


def lire_diffusion(
    jour: date, pages: Iterable[str], jeton: str, session: Any = None
) -> Diffusion | None:
    """La diffusion du Masque du ``jour`` (celle d'une des ``pages``
    radiofrance.fr de l'émission, de préférence), ou ``None`` ;
    ``ApiRadioFranceError`` si l'API échoue."""
    http: Any = session or requests.Session()
    connues = set(pages)
    debut = int(datetime(jour.year, jour.month, jour.day, tzinfo=PARIS).timestamp())
    variables: dict[str, Any] = {
        "start": debut,
        "end": debut + 86399,
        "first": PAR_PAGE,
        "after": None,
    }
    du_masque: dict[str, Any] | None = None
    for _ in range(PAGES_MAX):
        edges = _diffusions(http, jeton, variables)
        for edge in edges:
            noeud = edge.get("node") or {}
            if noeud.get("url") in connues:
                return _diffusion(noeud)
            if du_masque is None and _du_masque(noeud):
                du_masque = noeud
        if len(edges) < PAR_PAGE:
            break
        variables["after"] = edges[-1].get("cursor")
    return _diffusion(du_masque) if du_masque else None


def _diffusions(http: Any, jeton: str, variables: dict[str, Any]) -> list[Any]:
    """Une page de diffusions du jour."""
    try:
        reponse = http.post(
            POINT,
            json={"query": REQUETE, "variables": dict(variables)},
            headers={"X-Token": jeton, "Content-Type": "application/json"},
            timeout=DELAI,
        )
    except requests.RequestException as erreur:
        raise ApiRadioFranceError(type(erreur).__name__) from None
    if reponse.status_code != 200:
        raise ApiRadioFranceError(f"HTTP {reponse.status_code}")
    try:
        corps = reponse.json()
    except ValueError:
        raise ApiRadioFranceError("réponse illisible") from None
    connexion = (corps.get("data") or {}).get("diffusions")
    if corps.get("errors") or connexion is None:
        raise ApiRadioFranceError("erreur GraphQL")
    return list(connexion.get("edges") or [])


def _du_masque(noeud: dict[str, Any]) -> bool:
    """La diffusion appartient au Masque et la Plume."""
    show = (noeud.get("show") or {}).get("url") or ""
    return show.rstrip("/") == MASQUE or (noeud.get("url") or "").startswith(
        MASQUE + "/"
    )


def _diffusion(noeud: dict[str, Any]) -> Diffusion:
    personnes = (noeud.get("personalitiesConnection") or {}).get("edges") or []

    def parmi(relations: tuple[str, ...]) -> tuple[Personnalite, ...]:
        return tuple(
            Personnalite(str((p.get("node") or {}).get("name") or ""), p.get("info"))
            for p in personnes
            if p.get("relation") in relations and (p.get("node") or {}).get("name")
        )

    return Diffusion(
        titre=noeud.get("title"),
        resume=noeud.get("standFirst"),
        url=noeud.get("url"),
        equipe=parmi(EQUIPE),
        invites=parmi(INVITES),
    )
