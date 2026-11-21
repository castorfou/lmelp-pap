"""Le client de l'Open API Radio France : la diffusion d'une émission, lue à
la demande (écoute, mise à disposition).

L'API (GraphQL, en-tête ``x-token``) n'a pas de requête par identifiant de
diffusion : on lit les diffusions de France Inter du jour de l'émission (heure
de Paris) et on retient celle dont l'URL a le chemin d'une page radiofrance.fr
connue de l'émission, sinon la première du Masque et la Plume. Les URL rendues
par l'API sont sous ``www.franceinter.fr``, les pages connues de pap sous
``www.radiofrance.fr`` : seuls les chemins sont comparés.

Les CGU de l'API (art. 5.3) interdisent de stocker ses données : rien n'en
est écrit sur disque, en base ni dans les logs. Pour ménager le quota (1 000
requêtes par jour), ``LecteurDiffusions`` garde au plus une heure, dans la
mémoire du processus seulement, la diffusion lue pour une émission ; l'écoute
et la mise à disposition le partagent. Les erreurs ne disent que leur nature
(statut HTTP, exception), jamais le contenu reçu.
"""

import os
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests


POINT = "https://openapi.radiofrance.fr/v1/graphql"
# Le chemin des pages du Masque : l'API les rend sous www.franceinter.fr,
# pap les connaît sous www.radiofrance.fr ; on compare donc les chemins.
MASQUE = "/franceinter/podcasts/le-masque-et-la-plume"
# Les diffusions lues par requête, et le nombre de pages au plus pour un jour.
PAR_PAGE = 100
PAGES_MAX = 3
DELAI = 15  # secondes
PARIS = ZoneInfo("Europe/Paris")
# La durée de vie d'une diffusion dans le cache en mémoire, en secondes.
CACHE = 3600.0
# La variable d'environnement de la clé de l'API.
CLE = "RADIOFRANCE_API_TOKEN"

# Les relations de ``personalitiesConnection`` : ``producer`` (l'animateur),
# ``staff`` (l'équipe : critiques…), ``guest`` (les invités) ; ``tag``
# (personnalité citée) n'est pas retenu.
ANIMATEURS = ("producer",)
EQUIPE = ("staff",)
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


def jeton() -> str | None:
    """La clé de l'API (``RADIOFRANCE_API_TOKEN``), ou ``None``."""
    return os.environ.get(CLE) or None


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
    animateurs: tuple[Personnalite, ...]
    equipe: tuple[Personnalite, ...]
    invites: tuple[Personnalite, ...]


class LecteurDiffusions:
    """Lit la diffusion d'une émission, gardée ``duree`` secondes dans la
    mémoire du processus (jamais ailleurs) ; une erreur n'est pas gardée."""

    def __init__(
        self,
        session: Any = None,
        *,
        duree: float = CACHE,
        horloge: Callable[[], float] = time.monotonic,
    ):
        self._session = session
        self._duree = duree
        self._horloge = horloge
        self._memoire: dict[str, tuple[float, Diffusion | None]] = {}
        self._verrou = threading.Lock()

    def lire(
        self, cle: str, jour: date, pages: Iterable[str], jeton: str
    ) -> tuple[Diffusion | None, bool]:
        """La diffusion du Masque du ``jour`` pour l'émission ``cle`` (voir
        ``lire_diffusion``), et vrai si elle vient du cache."""
        with self._verrou:
            maintenant = self._horloge()
            self._memoire = {
                c: v
                for c, v in self._memoire.items()
                if maintenant - v[0] < self._duree
            }
            if cle in self._memoire:
                return self._memoire[cle][1], True
        diffusion = lire_diffusion(jour, pages, jeton, self._session)
        with self._verrou:
            self._memoire[cle] = (self._horloge(), diffusion)
        return diffusion, False


def lire_diffusion(
    jour: date, pages: Iterable[str], jeton: str, session: Any = None
) -> Diffusion | None:
    """La diffusion du Masque du ``jour`` (celle d'une des ``pages``
    radiofrance.fr de l'émission, de préférence), ou ``None`` ;
    ``ApiRadioFranceError`` si l'API échoue."""
    http: Any = session or requests.Session()
    connues = {_chemin(p) for p in pages}
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
            if _chemin(noeud.get("url")) in connues:
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
            headers={"x-token": jeton, "Content-Type": "application/json"},
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


def _chemin(url: str | None) -> str:
    """Le chemin d'une URL, sans domaine ni « / » final."""
    return urlsplit(url or "").path.rstrip("/")


def _du_masque(noeud: dict[str, Any]) -> bool:
    """La diffusion appartient au Masque et la Plume (quel que soit le
    domaine de ses URL)."""
    show = _chemin((noeud.get("show") or {}).get("url"))
    return show == MASQUE or _chemin(noeud.get("url")).startswith(MASQUE + "/")


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
        animateurs=parmi(ANIMATEURS),
        equipe=parmi(EQUIPE),
        invites=parmi(INVITES),
    )
