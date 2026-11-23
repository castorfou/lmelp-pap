"""La collecte des sources déclenchée depuis l'appli, au seam de son API HTTP.

La collecte réseau de radiofrance est remplacée par une copie des fiches des
fixtures : le test voit le cache se remplir, puis la liste se reconstruire.
"""

import json
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap import collecte
from lmelp_pap.arbitrer import creer_serveur
from tests.test_commande import FIXTURES, _cache_rempli


@pytest.fixture(autouse=True)
def _sans_base_lmelp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    """Un cache rempli, sauf radiofrance : jamais collectée."""
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    shutil.rmtree(cache / "radiofrance")
    return cache


@pytest.fixture
def feu() -> threading.Event:
    """Ouvert, la fausse collecte radiofrance finit ; fermé, elle attend."""
    feu = threading.Event()
    feu.set()
    return feu


@pytest.fixture(autouse=True)
def _radiofrance_sans_reseau(
    monkeypatch: pytest.MonkeyPatch, feu: threading.Event
) -> None:
    """La collecte radiofrance copie les fiches des fixtures, après avoir
    signalé sa progression, et attend le feu."""

    def collecter(dossier: Path, progres: Any = None) -> None:
        if progres:
            progres("radiofrance : page 1")
        assert feu.wait(10)
        fiches = dossier / "fiches"
        fiches.mkdir(parents=True, exist_ok=True)
        for fiche in (FIXTURES / "radiofrance").glob("*.html"):
            if not fiche.name.startswith("liste-"):
                shutil.copy(fiche, fiches / fiche.name)

    lire = collecte.SOURCES["radiofrance"][1]
    monkeypatch.setitem(collecte.SOURCES, "radiofrance", (collecter, lire))


@pytest.fixture
def url(cache: Path, tmp_path: Path) -> Iterator[str]:
    serveur = creer_serveur(cache, tmp_path / "sortie", port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{serveur.server_address[1]}"
    serveur.shutdown()
    serveur.server_close()


def _get(url: str) -> Any:
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def _post(url: str, corps: dict[str, Any]) -> Any:
    requete = urllib.request.Request(
        url,
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requete) as r:
        return json.load(r)


def _attendre_fin(url: str) -> dict[str, Any]:
    for _ in range(200):
        etat: dict[str, Any] = _get(f"{url}/api/collectes")
        if not etat["en_cours"]:
            return etat
        time.sleep(0.05)
    raise AssertionError("la collecte ne finit pas")


def _sources(donnees: dict[str, Any], emission_id: str) -> set[str]:
    emission = next(e for e in donnees["emissions"] if e["id"] == emission_id)
    return {a["source"] for a in emission["attestations"]}


def test_collecter_radiofrance_remplit_le_cache_et_reconstruit_la_liste(
    url: str, cache: Path, feu: threading.Event
) -> None:
    avant = _get(f"{url}/api/donnees")
    assert "1958-12-04" not in [e["id"] for e in avant["emissions"]]
    feu.clear()

    lancee = _post(f"{url}/api/collectes", {"source": "radiofrance"})

    # la réponse part pendant que la collecte tourne : la page n'attend pas
    assert lancee["en_cours"] is True
    assert lancee["sources"] == ["radiofrance"]
    assert _get(f"{url}/health") == {"status": "ok"}
    feu.set()
    fin = _attendre_fin(url)
    assert fin["bilan"]["emissions"] > len(avant["emissions"])
    assert (cache / "radiofrance" / "collecte_terminee").exists()
    apres = _get(f"{url}/api/donnees")
    assert "radiofrance" in _sources(apres, "1958-12-04")  # extrait Aragon
    assert (cache.parent / "sortie" / "emissions.csv").read_text().count("1958-12-04")


def test_une_deuxieme_collecte_pendant_la_premiere_est_refusee_avec_un_message(
    url: str, feu: threading.Event
) -> None:
    feu.clear()
    _post(f"{url}/api/collectes", {"source": "radiofrance"})

    with pytest.raises(urllib.error.HTTPError) as refus:
        _post(f"{url}/api/collectes", {"source": "toutes", "refresh": True})

    assert refus.value.code == 409
    message = json.load(refus.value)["erreur"]
    assert "déjà en cours" in message
    assert "radiofrance" in message
    feu.set()
    assert _attendre_fin(url)["sources"] == ["radiofrance"]


def test_la_progression_de_la_source_se_lit_pendant_la_collecte(
    url: str, feu: threading.Event
) -> None:
    feu.clear()
    _post(f"{url}/api/collectes", {"source": "radiofrance"})

    for _ in range(100):
        etat = _get(f"{url}/api/collectes")
        if etat["progression"]:
            break
        time.sleep(0.05)
    assert etat["en_cours_sur"] == "radiofrance"
    assert etat["progression"] == "radiofrance : page 1"
    feu.set()
    _attendre_fin(url)


def test_une_source_inconnue_est_refusee(url: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as refus:
        _post(f"{url}/api/collectes", {"source": "gallica"})

    assert refus.value.code == 400
    assert "source inconnue" in json.load(refus.value)["erreur"]


def test_toutes_collecte_chaque_source_et_saute_celles_deja_completes(
    url: str,
) -> None:
    _post(f"{url}/api/collectes", {"source": "toutes"})

    fin = _attendre_fin(url)
    assert fin["sources"] == sorted(collecte.SOURCES)
    assert fin["bilan"]["sources"]["radiofrance"] == "collectee"
    assert fin["bilan"]["sources"]["ina"] == "deja_complete"
    assert fin["bilan"]["sources"]["lmelp"] == "sautee"  # sans MONGO_URI


def test_la_re_collecte_reprend_une_source_deja_complete(url: str, cache: Path) -> None:
    (cache / "radiofrance" / "fiches").mkdir(parents=True)
    (cache / "radiofrance" / "collecte_terminee").touch()

    _post(f"{url}/api/collectes", {"source": "radiofrance", "refresh": True})

    fin = _attendre_fin(url)
    assert fin["refresh"] is True
    assert fin["bilan"]["sources"] == {"radiofrance": "collectee"}


def test_la_collecte_laisse_ses_lignes_dans_les_logs(
    url: str, feu: threading.Event, capsys: pytest.CaptureFixture[str]
) -> None:
    feu.clear()
    _post(f"{url}/api/collectes", {"source": "radiofrance"})
    with pytest.raises(urllib.error.HTTPError):
        _post(f"{url}/api/collectes", {"source": "ina"})
    feu.set()
    _attendre_fin(url)

    lignes = capsys.readouterr().err.splitlines()
    horodatee = r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d INFO    arbitrer : "
    attendues = [
        r"collecte demandée : radiofrance$",
        r"collecte radiofrance : début$",
        r"collecte ina refusée : une collecte est déjà en cours \(radiofrance\)",
        r"collecte radiofrance : collectée en \d+ s$",
        r"collecte terminée en \d+ s : \d+ émissions \(avant \d+\), \d+ attest",
    ]
    for motif in attendues:
        assert any(re.search(horodatee + motif, ligne) for ligne in lignes), motif
