"""La maturité des enregistrements intégraux, conservée dans Mongo.

Un enregistrement intégral avance sur le chemin qui le mène à lmelp :
localisé, téléchargeable, rapatrié, qualifié, valide (glossaire,
*maturité d'un enregistrement*). Ce module tient le niveau de chaque
enregistrement dans la collection ``pap_enregistrements`` (un document par
URL) et le fait évoluer selon la vérification de son URL :

- une URL qui répond 200 avec un type audio rend l'enregistrement
  téléchargeable ;
- un échec net (404, 410, 200 non audio) fait redescendre un téléchargeable à
  localisé : Radio France détient toujours le fichier ;
- un échec passager (délai dépassé, erreur réseau, 5xx…) est noté sans
  changer le niveau ;
- à partir de rapatrié, la vérification ne change plus le niveau.

Chaque entrée dans un niveau est datée (``entrees``).
"""

import csv
import os
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import requests
from dotenv import find_dotenv, load_dotenv


NIVEAUX = ("localise", "telechargeable", "rapatrie", "qualifie", "valide")
COLLECTION = "pap_enregistrements"
SOURCE = "radiofrance"
ENTETES = {"User-Agent": "lmelp-pap (https://github.com/castorfou/lmelp-pap)"}
DELAI = 30
CONCURRENCE = 4

Resultat = Literal["ok", "net", "passager"]


@dataclass(frozen=True)
class Verification:
    """Le résultat de la dernière vérification d'une URL."""

    date: datetime
    resultat: Resultat
    detail: str


@dataclass(frozen=True)
class Enregistrement:
    """Un enregistrement intégral, identifié par son URL, et sa maturité."""

    url: str
    emission_id: str
    source: str
    niveau: str
    entrees: dict[str, datetime] = field(default_factory=dict)
    verification: Verification | None = None


def classer(reponse: Any, maintenant: datetime) -> Verification:
    """Le verdict d'une vérification : la réponse à un HEAD, ou l'exception
    levée en la demandant."""
    if isinstance(reponse, Exception):
        return Verification(maintenant, "passager", type(reponse).__name__)
    statut = reponse.status_code
    type_ = reponse.headers.get("Content-Type", "")
    if statut == 200:
        if type_.startswith("audio/"):
            return Verification(maintenant, "ok", f"200 {type_}")
        return Verification(maintenant, "net", f"200 {type_ or 'sans type'}")
    if statut in (404, 410):
        return Verification(maintenant, "net", str(statut))
    return Verification(maintenant, "passager", str(statut))


def appliquer(
    existant: Enregistrement | None,
    verification: Verification,
    url: str,
    emission_id: str,
) -> Enregistrement:
    """L'enregistrement après une vérification de son URL."""
    if existant is None:
        niveau = "telechargeable" if verification.resultat == "ok" else "localise"
        return Enregistrement(
            url=url,
            emission_id=emission_id,
            source=SOURCE,
            niveau=niveau,
            entrees={niveau: verification.date},
            verification=verification,
        )
    niveau = existant.niveau
    if niveau == "localise" and verification.resultat == "ok":
        niveau = "telechargeable"
    elif niveau == "telechargeable" and verification.resultat == "net":
        niveau = "localise"
    entrees = dict(existant.entrees)
    if niveau != existant.niveau:
        entrees[niveau] = verification.date
    return replace(existant, niveau=niveau, entrees=entrees, verification=verification)


def meilleur(enregistrements: Iterable[Enregistrement]) -> Enregistrement | None:
    """L'enregistrement le plus avancé, ou ``None`` sans enregistrement."""
    return max(enregistrements, key=lambda e: NIVEAUX.index(e.niveau), default=None)


def maturite_emission(enregistrements: Iterable[Enregistrement]) -> str | None:
    """La maturité d'une émission : celle de son enregistrement le plus avancé."""
    plus_avance = meilleur(enregistrements)
    return plus_avance.niveau if plus_avance else None


class Depot:
    """La collection ``pap_enregistrements`` d'une base Mongo."""

    def __init__(self, base: Any):
        """``base`` : une base pymongo (ou mongomock)."""
        self.base = base
        self._collection = base[COLLECTION]

    def tous(self) -> list[Enregistrement]:
        """Tous les enregistrements connus."""
        return [_depuis_document(d) for d in self._collection.find()]

    def enregistrer(self, enregistrement: Enregistrement) -> None:
        """Écrit (ou remplace) le document de l'enregistrement."""
        document = _en_document(enregistrement)
        self._collection.replace_one({"_id": document["_id"]}, document, upsert=True)


def depot_depuis_env() -> Depot | None:
    """Le dépôt de la base ``MONGO_URI`` / ``MONGO_DB`` (environnement ou
    ``.env``), ou ``None`` sans ``MONGO_URI``."""
    load_dotenv(find_dotenv(usecwd=True))
    uri = os.environ.get("MONGO_URI")
    if not uri:
        return None
    from pymongo import MongoClient

    client: Any = MongoClient(uri, serverSelectionTimeoutMS=10_000, tz_aware=True)
    return Depot(client[os.environ.get("MONGO_DB", "masque_et_la_plume")])


def integraux(dossier: Path) -> list[tuple[str, str]]:
    """Les URL d'intégral de la liste (``enregistrements.csv``), avec leur
    émission."""
    with (dossier / "enregistrements.csv").open(encoding="utf-8", newline="") as f:
        return [
            (ligne["url"], ligne["emission_id"])
            for ligne in csv.DictReader(f)
            if ligne["type"] == "intégral"
        ]


def verifier(
    a_verifier: list[tuple[str, str]],
    depot: Depot,
    session: Any = None,
    maintenant: datetime | None = None,
    progres: Callable[[int], None] | None = None,
) -> dict[str, int]:
    """Vérifie chaque URL (HEAD, concurrence modérée) et met à jour sa
    maturité. Rend le nombre de vérifications par résultat."""
    # une session ``requests``, ou tout objet qui a sa méthode ``head``
    http: Any = session or requests.Session()
    existants = {e.url: e for e in depot.tous()}
    bilan: Counter[str] = Counter()
    faites = 0

    def une(url: str) -> Verification:
        quand = maintenant or datetime.now(UTC)
        try:
            reponse = http.head(
                url, allow_redirects=True, timeout=DELAI, headers=ENTETES
            )
        except requests.RequestException as erreur:
            return classer(erreur, quand)
        return classer(reponse, quand)

    with ThreadPoolExecutor(CONCURRENCE) as pool:
        for (url, emission_id), verification in zip(
            a_verifier, pool.map(une, [u for u, _ in a_verifier])
        ):
            depot.enregistrer(
                appliquer(existants.get(url), verification, url, emission_id)
            )
            bilan[verification.resultat] += 1
            faites += 1
            if progres:
                progres(faites)
    return {r: bilan[r] for r in ("ok", "net", "passager")}


def _en_document(e: Enregistrement) -> dict[str, Any]:
    v = e.verification
    return {
        "_id": e.url,
        "emission_id": e.emission_id,
        "source": e.source,
        "niveau": e.niveau,
        "entrees": e.entrees,
        "verification": (
            {"date": v.date, "resultat": v.resultat, "detail": v.detail} if v else None
        ),
    }


def _aware(d: datetime) -> datetime:
    """Mongo rend des dates naïves en UTC (sans ``tz_aware``) : on les date."""
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _depuis_document(d: dict[str, Any]) -> Enregistrement:
    v = d.get("verification")
    return Enregistrement(
        url=d["_id"],
        emission_id=d["emission_id"],
        source=d["source"],
        niveau=d["niveau"],
        entrees={k: _aware(t) for k, t in d["entrees"].items()},
        verification=(
            Verification(_aware(v["date"]), v["resultat"], v["detail"]) if v else None
        ),
    )
