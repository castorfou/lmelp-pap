"""Le bouton « Publier » de l'appli : l'atelier exporte les décisions de
Mongo, reconstruit la liste et la publie dans un dépôt nu temporaire (aucun
réseau, jamais le vrai dépôt GitHub)."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import mongomock
import pytest

from lmelp_pap.arbitrages import ArbitragesMongo
from lmelp_pap.arbitrer import Atelier, PublicationIndisponibleError, creer_serveur
from lmelp_pap.liste import Arbitrage
from lmelp_pap.maturite import Depot
from lmelp_pap.publication import Configuration, Publication, PublicationError
from tests.test_commande import _cache_rempli
from tests.test_logs import _demarrer_la_commande, lignes
from tests.test_publication import Notifications, git


@pytest.fixture
def distant(tmp_path: Path) -> Path:
    """Un dépôt nu, ``main`` avec un README."""
    nu = tmp_path / "distant.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(nu))
    poste = tmp_path / "poste"
    git(tmp_path, "clone", str(nu), str(poste))
    git(poste, "config", "user.name", "test")
    git(poste, "config", "user.email", "test@example.org")
    (poste / "README.md").write_text("pap\n")
    git(poste, "add", ".")
    git(poste, "commit", "-m", "init")
    git(poste, "push", "-q", "origin", "main")
    return nu


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    dossier = tmp_path / "cache"
    _cache_rempli(dossier)
    return dossier


@pytest.fixture
def depot() -> Depot:
    return Depot(mongomock.MongoClient(tz_aware=True)["masque_et_la_plume"])


def _publication(distant: Path, tmp_path: Path) -> Publication:
    return Publication(
        Configuration(clone=tmp_path / "depot", distant=str(distant)),
        notifier=Notifications(),
    )


def _arbitrage() -> Arbitrage:
    return Arbitrage(
        source="ina",
        source_id="RD_42",
        sorte="existence",
        themes=frozenset(),
        justification="écouté",
        date=datetime(2026, 11, 22, 9, 0, 0),
    )


def test_publier_exporte_les_arbitrages_de_mongo_et_pousse_la_liste(
    distant: Path, cache: Path, depot: Depot, tmp_path: Path
) -> None:
    sortie = tmp_path / "sortie"
    atelier = Atelier(
        cache, sortie, depot=depot, publication=_publication(distant, tmp_path)
    )
    ArbitragesMongo(depot.base).ajouter(_arbitrage())

    resultat = atelier.publier({})

    assert resultat["statut"] == "publiee"
    publies = git(distant, "ls-tree", "--name-only", "main", "data/processed/")
    assert publies.split() == [
        "data/processed/arbitrages.csv",
        "data/processed/attestations.csv",
        "data/processed/doutes.csv",
        "data/processed/emissions.csv",
        "data/processed/enregistrements.csv",
        "data/processed/qualifications.csv",
    ]
    assert "RD_42" in git(distant, "show", "main:data/processed/arbitrages.csv")
    # le fichier local est aussi l'export de Mongo
    assert "RD_42" in (sortie / "arbitrages.csv").read_text(encoding="utf-8")


def test_l_apercu_de_l_atelier_compte_les_arbitrages_a_publier(
    distant: Path, cache: Path, depot: Depot, tmp_path: Path
) -> None:
    atelier = Atelier(
        cache,
        tmp_path / "sortie",
        depot=depot,
        publication=_publication(distant, tmp_path),
    )
    ArbitragesMongo(depot.base).ajouter(_arbitrage())

    apercu = atelier.apercu_publication()

    assert apercu["a_publier"] is True
    assert apercu["arbitrages"] == {"ajoutes": 1, "retires": 0}
    assert "1 arbitrage ajouté" in apercu["resume"]


LIGNE_ARBITRAGE = "ina,RD_7,existence,n'existe pas,écouté,2026-11-01\n"


def _fichier_d_arbitrages(chemin: Path) -> str:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        "source,source_id,sorte,valeur,justification,date\n" + LIGNE_ARBITRAGE,
        encoding="utf-8",
    )
    return chemin.read_text(encoding="utf-8")


def test_publier_avec_pap_arbitrages_vide_refuse_d_effacer_le_fichier(
    distant: Path,
    cache: Path,
    depot: Depot,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    sortie = tmp_path / "sortie"
    avant = _fichier_d_arbitrages(sortie / "arbitrages.csv")
    notifications = Notifications()
    publication = Publication(
        Configuration(clone=tmp_path / "depot", distant=str(distant)),
        notifier=notifications,
    )
    atelier = Atelier(cache, sortie, depot=depot, publication=publication)
    capfd.readouterr()
    main = git(distant, "rev-parse", "main")

    resultat = atelier.publier({})

    assert resultat["statut"] == "refusee"
    assert "lmelp-pap arbitrages importer" in resultat["detail"]
    assert git(distant, "rev-parse", "main") == main
    assert (sortie / "arbitrages.csv").read_text(encoding="utf-8") == avant
    (alerte,) = notifications.recues
    assert alerte["titre"] == "publication refusée" and alerte["priorite"] == 4
    # ntfy est externe : le chemin des données (sur le NAS) n'y part pas
    assert "arbitrages.csv" in str(alerte["message"])
    assert str(tmp_path) not in str(alerte["message"])
    assert any(
        niveau == "ERROR" and "lmelp-pap arbitrages importer" in m and str(sortie) in m
        for niveau, _, m in lignes(capfd.readouterr().err)
    )
    with pytest.raises(PublicationError, match="lmelp-pap arbitrages importer"):
        atelier.apercu_publication()
    assert (sortie / "arbitrages.csv").read_text(encoding="utf-8") == avant


def test_publier_avec_pap_arbitrages_vide_protege_aussi_ceux_du_clone(
    distant: Path, cache: Path, depot: Depot, tmp_path: Path
) -> None:
    sortie = tmp_path / "sortie"
    atelier = Atelier(
        cache, sortie, depot=depot, publication=_publication(distant, tmp_path)
    )
    ArbitragesMongo(depot.base).ajouter(_arbitrage())
    assert atelier.publier({})["statut"] == "publiee"
    # pap_arbitrages vidé, plus de fichier local : le clone garde ceux publiés
    depot.base["pap_arbitrages"].delete_many({})
    (sortie / "arbitrages.csv").unlink()
    main = git(distant, "rev-parse", "main")

    assert atelier.publier({})["statut"] == "refusee"
    assert git(distant, "rev-parse", "main") == main


def test_publier_avec_pap_arbitrages_vide_et_aucun_arbitrage_ailleurs_publie(
    distant: Path, cache: Path, depot: Depot, tmp_path: Path
) -> None:
    atelier = Atelier(
        cache,
        tmp_path / "sortie",
        depot=depot,
        publication=_publication(distant, tmp_path),
    )

    assert atelier.publier({})["statut"] == "publiee"


def test_le_demarrage_avertit_quand_pap_arbitrages_est_a_importer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    depot: Depot,
) -> None:
    _fichier_d_arbitrages(tmp_path / "sortie" / "arbitrages.csv")

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd, depot=depot)

    (alerte,) = [m for m in journal if "pap_arbitrages est vide" in m]
    assert "1 arbitrage" in alerte and "lmelp-pap arbitrages importer" in alerte


def test_sans_publication_configuree_publier_est_indisponible(
    cache: Path, tmp_path: Path
) -> None:
    atelier = Atelier(cache, tmp_path / "sortie")

    with pytest.raises(PublicationIndisponibleError):
        atelier.publier({})
    with pytest.raises(PublicationIndisponibleError):
        atelier.apercu_publication()


@pytest.fixture
def serveur(
    distant: Path, cache: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    monkeypatch.chdir(tmp_path)
    serveur: Any = creer_serveur(
        cache,
        tmp_path / "sortie",
        port=0,
        publication=_publication(distant, tmp_path),
    )
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    serveur.url = f"http://127.0.0.1:{serveur.server_address[1]}"
    yield serveur
    serveur.shutdown()
    serveur.server_close()


def _json(url: str, corps: object = None) -> tuple[int, Any]:
    donnees = None if corps is None else json.dumps(corps).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=donnees)) as r:
            return int(r.status), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_l_api_donne_l_apercu_puis_publie(serveur: Any, distant: Path) -> None:
    statut, apercu = _json(serveur.url + "/api/publication")
    assert statut == 200
    assert apercu["a_publier"] is True

    statut, publie = _json(serveur.url + "/api/publication", {})
    assert statut == 200
    assert publie["statut"] == "publiee"
    assert publie["commit"] == git(distant, "rev-parse", "main")

    statut, encore = _json(serveur.url + "/api/publication", {})
    assert encore["statut"] == "rien"


def test_le_demarrage_dit_si_la_publication_est_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PAP_DEPOT_GIT", str(tmp_path / "depot"))
    monkeypatch.setenv("GH_TOKEN", "github_pat_secret")
    monkeypatch.setenv("NTFY_TOPIC", "lmelp")

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd)

    (ligne,) = [m for m in journal if m.startswith("publication :")]
    assert "https://github.com/castorfou/lmelp-pap.git (main)" in ligne
    assert f"clone {tmp_path / 'depot'}" in ligne
    assert "GH_TOKEN présent" in ligne and "ntfy lmelp" in ligne
    assert "github_pat_secret" not in "\n".join(journal)


def test_le_demarrage_dit_que_la_publication_est_desactivee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("PAP_DEPOT_GIT", raising=False)

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd)

    assert "publication : désactivée (PAP_DEPOT_GIT non défini)" in journal


def test_l_apercu_de_l_api_refuse_si_pap_arbitrages_est_a_importer(
    distant: Path,
    cache: Path,
    depot: Depot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _fichier_d_arbitrages(tmp_path / "sortie" / "arbitrages.csv")
    serveur: Any = creer_serveur(
        cache,
        tmp_path / "sortie",
        port=0,
        depot=depot,
        publication=_publication(distant, tmp_path),
    )
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{serveur.server_address[1]}/api/publication"
    try:
        statut, reponse = _json(url)
    finally:
        serveur.shutdown()
        serveur.server_close()

    assert statut == 502
    assert "lmelp-pap arbitrages importer" in reponse["erreur"]
    assert any(
        "GET /api/publication refusée (502)" in m
        for _, _, m in lignes(capfd.readouterr().err)
    )


def test_l_api_sans_publication_repond_503(
    cache: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    serveur: Any = creer_serveur(cache, tmp_path / "sortie", port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{serveur.server_address[1]}/api/publication"
    try:
        assert _json(url)[0] == 503
        assert _json(url, {})[0] == 503
    finally:
        serveur.shutdown()
        serveur.server_close()
