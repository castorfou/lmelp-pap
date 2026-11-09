"""Collecte des sources dans un cache local, puis lecture du cache en attestations.

Chaque source a son dossier ``<cache>/<source>/``. Une collecte terminée y
laisse le fichier ``collecte_terminee`` : la source n'est alors plus
re-collectée, sauf demande explicite (``refresh``). La lecture ne touche
jamais au réseau.
"""

import csv
import json
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import find_dotenv, load_dotenv

from lmelp_pap.liste import Attestation
from lmelp_pap.sources import (
    anciennes_listes,
    ina,
    lmelp,
    radiofrance,
    wayback_podcast,
)


TERMINEE = "collecte_terminee"
_ENTETES = {"User-Agent": "lmelp-pap (https://github.com/castorfou/lmelp-pap)"}
_DELAI = 1.0
_DELAI_WAYBACK = 4.0  # la Wayback Machine refuse les connexions au-delà
_CDX = "https://web.archive.org/cdx/search/cdx"
_RADIOFRANCE = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume"


# --- Lecture du cache --------------------------------------------------------


def lire_radiofrance(dossier: Path) -> list[Attestation]:
    fiches = sorted((dossier / "fiches").glob("*.html"))
    lues = (radiofrance.lire_fiche(f.read_text(encoding="utf-8")) for f in fiches)
    return [a for a in lues if a is not None]


def lire_wayback_podcast(dossier: Path) -> list[Attestation]:
    return wayback_podcast.lire_cdx((dossier / "cdx_podcast.txt").read_text("utf-8"))


def lire_ina(dossier: Path) -> list[Attestation]:
    with (dossier / "notices.csv").open(encoding="utf-8", newline="") as f:
        return ina.lire_notices(csv.DictReader(f))


def lire_anciennes_listes(dossier: Path) -> list[Attestation]:
    """Une attestation par date et par thème : les listes se recoupent."""
    uniques: dict[tuple[object, frozenset[str]], Attestation] = {}
    for f in sorted(dossier.glob("*.html")):
        for a in anciennes_listes.lire_liste(f.read_text(encoding="utf-8")):
            uniques.setdefault((a.date, a.themes), a)
    return list(uniques.values())


def lire_lmelp(dossier: Path) -> list[Attestation]:
    """Les émissions vérifiées copiées de la base Mongo par la collecte."""
    emissions = json.loads((dossier / "emissions.json").read_text(encoding="utf-8"))
    return lmelp.lire_emissions(emissions)


# --- Collecte (réseau) -------------------------------------------------------


class SourceIndisponibleError(Exception):
    """La source ne peut pas être collectée ici (accès absent) : on la saute."""


def _get(
    adresse: str, params: dict[str, str] | None = None, essais: int = 6
) -> requests.Response:
    """GET avec relances : la Wayback Machine renvoie souvent 503 ou 504."""
    for essai in range(essais):
        try:
            reponse = requests.get(adresse, params=params, headers=_ENTETES, timeout=60)
            if reponse.status_code < 500:
                return reponse
        except requests.RequestException:
            if essai == essais - 1:
                raise
        time.sleep(10 * 2**essai)  # 10 s, 20 s, 40 s… : laisser passer la limite
    reponse.raise_for_status()
    return reponse


def collecter_radiofrance(dossier: Path) -> None:
    fiches = dossier / "fiches"
    fiches.mkdir(parents=True, exist_ok=True)
    vues: set[str] = set()
    page = 1
    while True:
        liste = _get(_RADIOFRANCE, {"p": str(page)})
        urls = radiofrance.lire_page_liste(liste.content.decode("utf-8"))
        # Au-delà de la dernière page, le site renvoie une liste vide ou
        # redirige vers la page 1 : une page sans URL nouvelle marque la fin.
        if not set(urls) - vues:
            break
        vues.update(urls)
        for url in urls:
            fichier = fiches / f"{url.rstrip('/').rsplit('/', 1)[-1]}.html"
            if not fichier.exists():
                # Le site n'annonce pas d'encodage : décoder l'UTF-8 soi-même.
                fichier.write_text(_get(url).content.decode("utf-8"), "utf-8")
                time.sleep(_DELAI)
        page += 1
        time.sleep(_DELAI)


def collecter_wayback_podcast(dossier: Path) -> None:
    reponse = _get(
        _CDX,
        {
            "url": "media.radiofrance-podcast.net/podcast09/14007-",
            "matchType": "prefix",
            "fl": "original,statuscode",
            "collapse": "urlkey",
        },
    )
    reponse.raise_for_status()
    (dossier / "cdx_podcast.txt").write_text(reponse.text, encoding="utf-8")


def collecter_ina(dossier: Path) -> None:
    from lmelp_pap.sources.ina_catalogue import scrape_ina_catalogue_raw

    def sans_rang(urls: pd.Series) -> pd.Series:
        return urls.str.split("?").str[0]  # ?rang= varie d'une recherche à l'autre

    toutes = scrape_ina_catalogue_raw(facette=False)
    litterature = set(sans_rang(scrape_ina_catalogue_raw(facette=True)["url_ina"]))
    toutes["facette_litterature"] = (
        sans_rang(toutes["url_ina"]).isin(litterature).map({True: "oui", False: "non"})
    )
    toutes.drop(columns=["source"]).to_csv(dossier / "notices.csv", index=False)


# Listes archivées : préfixe d'URL dans la Wayback Machine, encodage des pages.
_ANCIENNES_LISTES = (
    ("radiofrance.fr/franceinter/em/lemasqueetlaplume/archives.php", "latin-1"),
    ("franceinter.fr/archives-diffusions/319/", "utf-8"),
)


def collecter_anciennes_listes(dossier: Path) -> None:
    for prefixe, encodage in _ANCIENNES_LISTES:
        reponse = _get(
            _CDX,
            {
                "url": prefixe,
                "matchType": "prefix",
                "fl": "timestamp,original",
                "filter": "statuscode:200",
            },
        )
        reponse.raise_for_status()
        captures: dict[str, str] = {}
        for ligne in reponse.text.splitlines():
            horodatage, url = ligne.split(" ", 1)
            cle = re.sub(r"^https?://(www\.)?|:80", "", url)
            captures[cle] = horodatage  # la dernière capture l'emporte
        for cle, horodatage in sorted(captures.items()):
            fichier = dossier / (re.sub(r"[^A-Za-z0-9.-]+", "_", cle) + ".html")
            if fichier.exists():
                continue
            page = _get(f"https://web.archive.org/web/{horodatage}id_/http://{cle}")
            if page.status_code == 200:
                fichier.write_text(page.content.decode(encodage, "replace"), "utf-8")
            time.sleep(_DELAI_WAYBACK)


def collecter_lmelp(dossier: Path) -> None:
    """Les émissions vérifiées de la base Mongo de lmelp, en lecture seule.

    La base n'est accessible que depuis le devcontainer : ``MONGO_URI`` et
    ``MONGO_DB`` viennent de l'environnement ou du fichier ``.env``.
    """
    load_dotenv(find_dotenv(usecwd=True))
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise SourceIndisponibleError("MONGO_URI absent")
    from pymongo import MongoClient

    client: MongoClient[dict[str, Any]] = MongoClient(
        uri, serverSelectionTimeoutMS=10_000
    )
    with client:
        base = client[os.environ.get("MONGO_DB", "masque_et_la_plume")]
        champs = ["titre", "titre_corrige", "date", "episode_page_url"]
        episodes = {
            str(e["_id"]): e
            for e in base.episodes.find({}, [*champs, "audio_rel_filename", "masked"])
        }
        retenus = [episodes.get(str(e["episode_id"])) for e in base.emissions.find()]
    emissions = [
        {
            "page": e["episode_page_url"],
            "titre": e.get("titre_corrige") or e["titre"],
            "publication": e["date"].replace(tzinfo=UTC).isoformat(),
            "fichier": e.get("audio_rel_filename") or "",
        }
        for e in retenus
        if e and not e.get("masked") and e.get("episode_page_url")
    ]
    if len(emissions) < len(retenus):
        print(
            f"lmelp : {len(retenus) - len(emissions)} émissions sans épisode, "
            "masquées ou sans page radiofrance.fr, ignorées",
            file=sys.stderr,
        )
    (dossier / "emissions.json").write_text(
        json.dumps(
            sorted(emissions, key=lambda e: e["publication"]),
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


# --- Registre des sources ----------------------------------------------------

SOURCES: dict[
    str, tuple[Callable[[Path], None], Callable[[Path], list[Attestation]]]
] = {
    "radiofrance": (collecter_radiofrance, lire_radiofrance),
    "wayback_podcast": (collecter_wayback_podcast, lire_wayback_podcast),
    "ina": (collecter_ina, lire_ina),
    "anciennes_listes": (collecter_anciennes_listes, lire_anciennes_listes),
    "lmelp": (collecter_lmelp, lire_lmelp),
}


def collecter(source: str, cache: Path, refresh: bool = False) -> None:
    """Remplit le cache d'une source, sauf si sa collecte est déjà terminée."""
    dossier = cache / source
    if (dossier / TERMINEE).exists() and not refresh:
        return
    dossier.mkdir(parents=True, exist_ok=True)
    etait_terminee = (dossier / TERMINEE).exists()
    (dossier / TERMINEE).unlink(missing_ok=True)
    try:
        SOURCES[source][0](dossier)
    except SourceIndisponibleError as raison:
        # rien n'a été écrit : le cache précédent, s'il y en a un, reste valable
        print(f"{source} : collecte sautée ({raison})", file=sys.stderr)
        if etait_terminee:
            (dossier / TERMINEE).touch()
        return
    (dossier / TERMINEE).touch()


def lire_cache(cache: Path) -> list[Attestation]:
    """Toutes les attestations des sources dont la collecte est terminée."""
    return [
        a
        for source, (_, lire) in SOURCES.items()
        if (cache / source / TERMINEE).exists()
        for a in lire(cache / source)
    ]
