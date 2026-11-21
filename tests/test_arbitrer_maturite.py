"""La maturité des enregistrements dans l'appli, au seam de son API HTTP.

Le serveur tourne sur un port libre avec un dépôt mongomock et une session
HTTP factice : la vérification des URL n'atteint jamais le réseau.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import mongomock
import pytest

from lmelp_pap.arbitrer import creer_serveur
from lmelp_pap.maturite import Depot
from tests.test_commande import _cache_rempli
from tests.test_maturite import Reponse, Session


INTEGRAL_2014 = (
    "https://media.radiofrance-podcast.net/podcast09/"
    "14007-28.09.2014-ITEMA_20674220-2014F4007S0271-27.m4a"
)
INTEGRAL_2017 = (
    "https://media.radiofrance-podcast.net/podcast09/"
    "14007-01.01.2017-ITEMA_21183424-0.mp3"
)
INTEGRAL_2024 = (
    "https://media.radiofrance-podcast.net/podcast09/"
    "20904-11.02.2024-ITEMA_23644545-2024F4007S0042-27.m4a"
)


@pytest.fixture(autouse=True)
def _sans_base_lmelp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)


@pytest.fixture
def depot() -> Depot:
    return Depot(mongomock.MongoClient()["masque_et_la_plume"])


def _demarrer(tmp_path: Path, **options: Any) -> Iterator[str]:
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    serveur = creer_serveur(cache, tmp_path / "sortie", port=0, **options)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{serveur.server_address[1]}"
    serveur.shutdown()
    serveur.server_close()


@pytest.fixture
def url(tmp_path: Path, depot: Depot) -> Iterator[str]:
    session = Session(
        {
            INTEGRAL_2014: Reponse(200, "audio/mp4"),
            INTEGRAL_2017: Reponse(404),
            INTEGRAL_2024: Reponse(200, "audio/mp4"),
        }
    )
    yield from _demarrer(tmp_path, depot=depot, session=session)


@pytest.fixture
def url_sans_mongo(tmp_path: Path) -> Iterator[str]:
    yield from _demarrer(tmp_path)


def _get(url: str) -> Any:
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def _post(url: str) -> Any:
    requete = urllib.request.Request(url, data=b"{}", method="POST")
    with urllib.request.urlopen(requete) as r:
        return json.load(r)


def _attendre_fin(url: str) -> dict[str, Any]:
    for _ in range(100):
        etat: dict[str, Any] = _get(f"{url}/api/verifications")
        if not etat["en_cours"]:
            return etat
        time.sleep(0.05)
    raise AssertionError("la vérification ne finit pas")


def _maturites(donnees: dict[str, Any]) -> dict[str, str | None]:
    return {e["id"]: e["maturite"] for e in donnees["emissions"]}


def test_avant_toute_verification_aucune_emission_n_a_de_maturite(url: str) -> None:
    donnees = _get(f"{url}/api/donnees")
    assert donnees["maturite_active"] is True
    assert set(_maturites(donnees).values()) == {None}


def test_verifier_les_urls_rend_les_integraux_telechargeables(
    url: str, depot: Depot
) -> None:
    etat = _post(f"{url}/api/verifications")
    assert etat["total"] == 3

    fin = _attendre_fin(url)

    assert fin["faites"] == 3
    assert fin["bilan"] == {"ok": 2, "net": 1, "passager": 0}
    maturites = _maturites(_get(f"{url}/api/donnees"))
    assert maturites["2014-09-28"] == "telechargeable"
    assert maturites["2024-02-11"] == "telechargeable"
    assert maturites["2017-01-01"] == "localise"
    assert maturites["1967-01-01"] is None  # extraits seulement
    assert len(depot.tous()) == 3


def test_avant_une_premiere_verification_l_etat_est_au_repos(url: str) -> None:
    assert _get(f"{url}/api/verifications") == {
        "en_cours": False,
        "faites": 0,
        "total": 0,
        "bilan": None,
    }


def test_sans_mongo_la_maturite_est_absente(url_sans_mongo: str) -> None:
    donnees = _get(f"{url_sans_mongo}/api/donnees")
    assert "maturite_active" not in donnees
    assert all("maturite" not in e for e in donnees["emissions"])
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post(f"{url_sans_mongo}/api/verifications")
    assert erreur.value.code == 503
