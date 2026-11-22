"""Les logs de l'appli : des lignes horodatées sur la sortie d'erreur, que
``docker logs`` montre."""

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import mongomock
import pytest

from lmelp_pap import cli, logs
from lmelp_pap.arbitrer import creer_serveur
from lmelp_pap.maturite import Depot
from tests.test_commande import _cache_rempli


LIGNE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (\w+) +(\S+) : (.*)$")


def lignes(sortie: str) -> list[tuple[str, str, str]]:
    """Les lignes de log (niveau, module, message) d'une sortie capturée."""
    return [
        (m[1], m[2], m[3]) for ligne in sortie.splitlines() if (m := LIGNE.match(ligne))
    ]


def messages(sortie: str, module: str) -> list[str]:
    """Les messages d'un module dans une sortie capturée."""
    return [m for _, mod, m in lignes(sortie) if mod == module]


def test_une_ligne_porte_horodatage_niveau_module_et_message(
    capfd: pytest.CaptureFixture[str],
) -> None:
    logs.configurer()
    logging.getLogger("lmelp_pap.arbitrer").warning("Mongo injoignable")

    assert ("WARNING", "arbitrer", "Mongo injoignable") in lignes(
        capfd.readouterr().err
    )


def test_configurer_deux_fois_ne_double_pas_les_lignes(
    capfd: pytest.CaptureFixture[str],
) -> None:
    logs.configurer()
    logs.configurer()
    logging.getLogger("lmelp_pap.cli").info("une fois")

    assert lignes(capfd.readouterr().err).count(("INFO", "cli", "une fois")) == 1


# --- au seam du serveur -------------------------------------------------------


@pytest.fixture
def serveur(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Un serveur sans Mongo sur un port libre ; ``serveur.url`` son adresse."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    serveur: Any = creer_serveur(cache, tmp_path / "sortie", port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    serveur.url = f"http://127.0.0.1:{serveur.server_address[1]}"
    yield serveur
    serveur.shutdown()
    serveur.server_close()


def _requete(url: str, corps: object = None) -> int:
    """Le statut de la réponse à un GET, ou à un POST de ``corps`` en JSON."""
    donnees = None if corps is None else json.dumps(corps).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=donnees)) as r:
            r.read()
            return int(r.status)
    except urllib.error.HTTPError as e:
        return e.code


def _logs(capfd: pytest.CaptureFixture[str]) -> str:
    time.sleep(0.1)  # le fil du serveur finit sa ligne
    return capfd.readouterr().err


def test_une_requete_http_est_journalisee(
    serveur: Any, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    _requete(f"{serveur.url}/liste")
    _requete(f"{serveur.url}/inexistant")

    http = messages(_logs(capfd), "http")
    assert any(m.startswith("GET /liste 200") for m in http)
    assert any(m.startswith("GET /inexistant 404") for m in http)


def test_la_sante_et_les_sondages_ne_sont_pas_journalises(
    serveur: Any, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    _requete(f"{serveur.url}/health")
    _requete(f"{serveur.url}/api/verifications")
    _requete(f"{serveur.url}/api/rapatriements")

    assert messages(_logs(capfd), "http") == []


def test_une_exception_dans_une_requete_est_journalisee_avec_sa_trace(
    serveur: Any, capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def panne() -> None:
        raise RuntimeError("serveur Mongo injoignable")

    monkeypatch.setattr(serveur.atelier, "donnees", panne)
    capfd.readouterr()

    statut = _requete(f"{serveur.url}/api/donnees")

    sortie = _logs(capfd)
    assert statut == 500
    assert any(
        niveau == "ERROR" and "GET /api/donnees" in m for niveau, _, m in lignes(sortie)
    )
    assert "RuntimeError: serveur Mongo injoignable" in sortie


# --- au seam de la commande : le démarrage ----------------------------------


def _demarrer_la_commande(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    depot: Depot | None = None,
) -> list[str]:
    """Lance ``lmelp-pap arbitrer`` sans servir (le serveur s'arrête aussitôt)
    et rend les messages de démarrage."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.setattr(cli, "depot_depuis_env", lambda: depot)

    def arret(_serveur: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", arret)
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    capfd.readouterr()
    code = cli.main(
        [
            "arbitrer",
            "--cache",
            str(cache),
            "--sortie",
            str(tmp_path / "sortie"),
            "--hote",
            "0.0.0.0",
            "--port",
            "0",
            "--sans-navigateur",
        ]
    )
    assert code == 0
    return messages(capfd.readouterr().err, "cli")


def test_le_demarrage_dit_version_adresse_liste_mongo_et_dossiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    journal = "\n".join(_demarrer_la_commande(tmp_path, monkeypatch, capfd))

    assert re.search(r"lmelp-pap \d+\.\d+\.\d+ : écoute sur 0\.0\.0\.0:\d+", journal)
    assert re.search(r"liste : \d+ émissions", journal)
    assert "Mongo : absent (MONGO_URI non défini)" in journal
    assert f"cache {tmp_path / 'cache'}" in journal
    assert f"audios lmelp {Path('data/raw/audios-lmelp')}" in journal
    assert "Ctrl+C" not in journal
    assert "Arbitrage de la liste" not in journal


def test_le_demarrage_dit_mongo_connecte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    depot = Depot(mongomock.MongoClient()["masque_et_la_plume"])

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd, depot)

    assert "Mongo : connecté (base masque_et_la_plume)" in journal


def test_le_demarrage_dit_mongo_injoignable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    depot = Depot(mongomock.MongoClient()["masque_et_la_plume"])

    def injoignable(*_args: object, **_options: object) -> None:
        raise RuntimeError("nas923:27018: timed out")

    monkeypatch.setattr(depot.base.client.admin, "command", injoignable)

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd, depot)

    assert any(
        m.startswith("Mongo : injoignable (base masque_et_la_plume) : ")
        for m in journal
    )


def test_le_demarrage_donne_l_url_publique_si_elle_est_fournie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PAP_URL_PUBLIQUE", "http://nas923:8085/")

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd)

    assert "page publique : http://nas923:8085/" in journal


# --- au seam du serveur : les actions ---------------------------------------


def test_un_arbitrage_et_son_annulation_sont_journalises(
    serveur: Any, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    arbitrage = {
        "emission_id": "1967-01-01",
        "sorte": "thème",
        "themes": ["théâtre"],
        "justification": "écouté",
    }
    _requete(f"{serveur.url}/api/arbitrages", arbitrage)
    # l'émission sort de la liste : l'annulation vise son attestation
    annulation = {"source": "wayback_podcast", "source_id": "ITEMA_23820437"}
    _requete(f"{serveur.url}/api/annulations", annulation)

    journal = messages(_logs(capfd), "arbitrer")
    assert "arbitrage thème 1967-01-01 : théâtre (« écouté »)" in journal
    assert "annulation wayback_podcast:ITEMA_23820437 : 1 arbitrage retiré" in journal


def test_une_demande_refusee_est_journalisee(
    serveur: Any, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()
    statut = _requete(
        f"{serveur.url}/api/arbitrages", {"emission_id": "1967-01-01", "sorte": "?"}
    )

    assert statut == 400
    assert any(
        m.startswith("POST /api/arbitrages refusée (400) : sorte invalide")
        for m in messages(_logs(capfd), "http")
    )
