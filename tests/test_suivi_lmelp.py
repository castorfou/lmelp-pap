"""La source lmelp suivie dans Mongo par le fil de planification horaire.

La base partagée avec lmelp est simulée par mongomock : collections
``episodes`` et ``emissions`` (lecture seule), comme la collecte les lit.
"""

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import mongomock
import pymongo.errors
import pytest

from lmelp_pap import collecte, logs
from lmelp_pap.arbitrer import Atelier
from lmelp_pap.maturite import Depot
from tests.test_commande import _cache_rempli
from tests.test_logs import lignes


PAGES = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"


def _verifier(base: Any, page: str, date: datetime, titre: str = "Livres") -> None:
    """Une émission vérifiée dans lmelp : un épisode et son émission."""
    episode = base.episodes.insert_one(
        {
            "titre": titre,
            "date": date,
            "episode_page_url": PAGES + page,
            "audio_rel_filename": f"{page}.m4a",
        }
    ).inserted_id
    base.emissions.insert_one({"episode_id": episode})


@pytest.fixture
def base() -> Any:
    base: Any = mongomock.MongoClient()["masque_et_la_plume"]
    _verifier(base, "livres-du-01-novembre-2026", datetime(2026, 11, 1, 9, 12))
    return base


@pytest.fixture
def cache(tmp_path: Path, base: Any) -> Path:
    """Un cache rempli, dont lmelp copié de la base."""
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    collecte.ecrire_lmelp(cache / "lmelp", collecte.lire_base_lmelp(base))
    (cache / "lmelp" / collecte.TERMINEE).touch()
    return cache


@pytest.fixture
def atelier(cache: Path, base: Any, tmp_path: Path) -> Atelier:
    return Atelier(cache, tmp_path / "sortie", depot=Depot(base))


@pytest.fixture
def sortie(capfd: pytest.CaptureFixture[str]) -> Any:
    """Les messages d'``arbitrer`` écrits dans les logs, niveau compris."""
    logs.configurer(logging.DEBUG)
    yield lambda: [
        (niveau, message)
        for niveau, module, message in lignes(capfd.readouterr().err)
        if module == "arbitrer"
    ]
    logs.configurer(logging.INFO)
    logging.getLogger(logs.RACINE).setLevel(logging.INFO)


def _emissions_json(cache: Path) -> list[dict[str, str]]:
    donnees: list[dict[str, str]] = json.loads(
        (cache / "lmelp" / "emissions.json").read_text(encoding="utf-8")
    )
    return donnees


def test_la_lecture_de_la_base_donne_les_emissions_verifiees_non_masquees(
    base: Any,
) -> None:
    masque = base.episodes.insert_one(
        {
            "titre": "Masqué",
            "date": datetime(2026, 11, 8),
            "episode_page_url": PAGES + "masque",
            "masked": True,
        }
    ).inserted_id
    base.emissions.insert_one({"episode_id": masque})
    base.episodes.insert_one(  # pas vérifié : aucune émission ne le désigne
        {"titre": "Brut", "date": datetime(2026, 11, 15), "episode_page_url": "x"}
    )

    assert collecte.lire_base_lmelp(base) == [
        {
            "page": PAGES + "livres-du-01-novembre-2026",
            "titre": "Livres",
            "publication": "2026-11-01T09:12:00+00:00",
            "fichier": "livres-du-01-novembre-2026.m4a",
        }
    ]


def test_un_tour_sans_changement_ne_reecrit_rien_et_laisse_au_plus_une_ligne_debug(
    atelier: Atelier, cache: Path, tmp_path: Path, sortie: Any
) -> None:
    sortie()
    fichiers = [
        cache / "lmelp" / "emissions.json",
        tmp_path / "sortie" / "emissions.csv",
    ]
    avant = [f.stat().st_mtime_ns for f in fichiers]

    atelier.suivre_lmelp()

    assert [f.stat().st_mtime_ns for f in fichiers] == avant
    ecrites = sortie()
    assert len(ecrites) <= 1
    assert all(niveau == "DEBUG" for niveau, _ in ecrites)


def test_une_emission_verifiee_dans_lmelp_entre_dans_la_liste_au_tour_suivant(
    atelier: Atelier, base: Any, cache: Path, sortie: Any
) -> None:
    avant = atelier.nombre_emissions()
    _verifier(base, "livres-du-08-novembre-2026", datetime(2026, 11, 8, 9))

    atelier.suivre_lmelp()

    assert atelier.nombre_emissions() == avant + 1
    assert "2026-11-08" in {e["id"] for e in atelier.donnees()["emissions"]}
    assert [e["page"] for e in _emissions_json(cache)][-1].endswith("08-novembre-2026")
    assert (
        "INFO",
        (
            "source lmelp : 1 émission vérifiée ajoutée, 0 retirée, 0 modifiée ; "
            f"liste {avant} → {avant + 1} émissions"
        ),
    ) in sortie()


def test_une_emission_retiree_de_lmelp_quitte_le_cache_au_tour_suivant(
    atelier: Atelier, base: Any, cache: Path, sortie: Any
) -> None:
    base.emissions.delete_many({})
    avant = atelier.nombre_emissions()

    atelier.suivre_lmelp()

    assert _emissions_json(cache) == []
    assert (
        "INFO",
        (
            "source lmelp : 0 émission vérifiée ajoutée, 1 retirée, 0 modifiée ; "
            f"liste {avant} → {atelier.nombre_emissions()} émissions"
        ),
    ) in sortie()


def test_un_titre_corrige_dans_lmelp_compte_comme_une_modification(
    atelier: Atelier, base: Any, cache: Path, sortie: Any
) -> None:
    base.episodes.update_many({}, {"$set": {"titre_corrige": "Livres, corrigé"}})

    atelier.suivre_lmelp()

    assert [e["titre"] for e in _emissions_json(cache)] == ["Livres, corrigé"]
    assert any(
        niveau == "INFO"
        and "0 émission vérifiée ajoutée, 0 retirée, 1 modifiée" in message
        for niveau, message in sortie()
    )


def test_un_tour_pendant_une_collecte_passe_son_tour_sans_la_perturber(
    atelier: Atelier, base: Any, cache: Path, sortie: Any, monkeypatch: Any
) -> None:
    feu = threading.Event()

    def collecter(dossier: Path, progres: Any = None) -> None:
        assert feu.wait(10)

    lire = collecte.SOURCES["ina"][1]
    monkeypatch.setitem(collecte.SOURCES, "ina", (collecter, lire))
    _verifier(base, "livres-du-08-novembre-2026", datetime(2026, 11, 8, 9))
    avant = _emissions_json(cache)
    atelier.lancer_collecte({"source": "ina", "refresh": True})

    assert atelier.suivre_lmelp() == "sautee"

    assert _emissions_json(cache) == avant
    assert ("INFO", "source lmelp : tour sauté (collecte en cours)") in sortie()
    feu.set()
    for _ in range(200):
        if not atelier.etat_collecte()["en_cours"]:
            break
        threading.Event().wait(0.05)
    assert atelier.etat_collecte()["bilan"]["sources"] == {"ina": "collectee"}


def test_sans_mongo_le_tour_passe_et_le_cache_reste(
    cache: Path, tmp_path: Path, sortie: Any
) -> None:
    atelier = Atelier(cache, tmp_path / "sortie")
    avant = atelier.nombre_emissions()

    assert atelier.suivre_lmelp() == "sautee"

    assert atelier.nombre_emissions() == avant
    assert ("INFO", "source lmelp : tour sauté (MONGO_URI absent)") in sortie()


class _BaseInjoignable:
    """Une base dont le serveur ne répond pas."""

    def __getattr__(self, nom: str) -> Any:
        raise pymongo.errors.ServerSelectionTimeoutError("nas923:27017: timed out")

    def __getitem__(self, nom: str) -> Any:
        return self.__getattr__(nom)


def test_mongo_injoignable_le_tour_passe_et_l_appli_garde_le_cache_precedent(
    atelier: Atelier, cache: Path, sortie: Any
) -> None:
    avant = (_emissions_json(cache), atelier.nombre_emissions())
    atelier.depot = Depot.__new__(Depot)
    atelier.depot.base = _BaseInjoignable()

    assert atelier.suivre_lmelp() == "sautee"

    assert (_emissions_json(cache), atelier.nombre_emissions()) == avant
    assert (
        "WARNING",
        "source lmelp : tour sauté (Mongo injoignable : nas923:27017: timed out)",
    ) in sortie()


def test_un_premier_tour_remplit_un_cache_lmelp_jamais_collecte(
    base: Any, cache: Path, tmp_path: Path
) -> None:
    shutil.rmtree(cache / "lmelp")
    atelier = Atelier(cache, tmp_path / "sortie", depot=Depot(base))
    avant = atelier.nombre_emissions()

    assert atelier.suivre_lmelp() == "mise_a_jour"

    assert (cache / "lmelp" / collecte.TERMINEE).exists()
    assert atelier.nombre_emissions() == avant + 1


def test_le_bouton_lmelp_relit_la_base_meme_sans_re_collecter(
    atelier: Atelier, monkeypatch: Any
) -> None:
    relues: list[Path] = []
    lire = collecte.SOURCES["lmelp"][1]
    monkeypatch.setitem(
        collecte.SOURCES, "lmelp", (lambda d, p=None: relues.append(d), lire)
    )

    atelier.lancer_collecte({"source": "lmelp"})
    for _ in range(200):
        if not atelier.etat_collecte()["en_cours"]:
            break
        threading.Event().wait(0.05)

    assert atelier.etat_collecte()["bilan"]["sources"] == {"lmelp": "collectee"}
    assert len(relues) == 1


def test_une_reconstruction_en_echec_rend_au_cache_son_etat_precedent(
    atelier: Atelier, base: Any, cache: Path, monkeypatch: Any
) -> None:
    avant = _emissions_json(cache)
    _verifier(base, "livres-du-08-novembre-2026", datetime(2026, 11, 8, 9))

    def en_echec() -> None:
        raise pymongo.errors.AutoReconnect("connexion perdue")

    monkeypatch.setattr(atelier, "recharger_cache", en_echec)
    with pytest.raises(pymongo.errors.AutoReconnect):
        atelier.suivre_lmelp()

    assert _emissions_json(cache) == avant
    monkeypatch.undo()
    assert atelier.suivre_lmelp() == "mise_a_jour"  # le tour suivant reprend
