"""L'outil ``lmelp-pap arbitrer``, au seam de son API HTTP.

Le serveur est démarré sur un port libre, avec un cache rempli par les fixtures
et un dossier de sortie temporaire ; il reconstruit la liste sans réseau.
"""

import csv
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap.arbitrer import creer_serveur
from tests.test_commande import _cache_rempli


@pytest.fixture(autouse=True)
def _sans_base_lmelp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)


@pytest.fixture
def sortie(tmp_path: Path) -> Path:
    return tmp_path / "sortie"


@pytest.fixture
def url(tmp_path: Path, sortie: Path) -> Iterator[str]:
    """L'adresse du serveur, démarré sur un port libre."""
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    # Une notice INA du 28 septembre 2014 : l'émission a aussi sa fiche
    # radiofrance.fr, et l'arbitrage doit s'attacher à la notice.
    with (cache / "ina" / "notices.csv").open("a", encoding="utf-8") as f:
        f.write(
            "2014-09-28,Livres,Le masque et la plume,FIT,20:00:00,00:55:00,"
            '"Débat,Magazine",https://catalogue.ina.fr/doc/TV-RADIO/'
            "PH_PHD99999999/livres,oui\n"
        )
    serveur = creer_serveur(cache, sortie, port=0)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
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


def _ids(donnees: dict[str, Any]) -> list[str]:
    return [e["id"] for e in donnees["emissions"]]


def _lignes(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_un_arbitrage_de_theme_est_ecrit_et_sort_l_emission_de_la_liste(
    url: str, sortie: Path
) -> None:
    assert "1967-01-01" in _ids(_get(f"{url}/api/donnees"))  # thème inconnu

    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "1967-01-01",
            "sorte": "thème",
            "themes": ["théâtre"],
            "justification": "écouté l'enregistrement",
        },
    )

    assert "1967-01-01" not in _ids(donnees)
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert arbitrage["source"] == "wayback_podcast"
    assert arbitrage["source_id"] == "ITEMA_23820437"
    assert arbitrage["sorte"] == "thème"
    assert arbitrage["valeur"] == "théâtre"
    assert arbitrage["justification"] == "écouté l'enregistrement"
    assert arbitrage["date"]
    assert "1967-01-01" not in {e["id"] for e in _lignes(sortie / "emissions.csv")}


def test_annuler_l_arbitrage_remet_l_emission_dans_la_liste(
    url: str, sortie: Path
) -> None:
    _post(
        f"{url}/api/arbitrages",
        {"emission_id": "1967-01-01", "sorte": "thème", "themes": ["théâtre"]},
    )

    donnees = _post(
        f"{url}/api/annulations",
        {"source": "wayback_podcast", "source_id": "ITEMA_23820437"},
    )

    assert "1967-01-01" in _ids(donnees)
    assert donnees["arbitrages"] == []
    assert _lignes(sortie / "arbitrages.csv") == []


def test_l_arbitrage_s_attache_a_la_notice_ina_plutot_qu_a_la_fiche(
    url: str, sortie: Path
) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "2014-09-28",
            "sorte": "thème",
            "themes": ["livres", "cinéma"],
            "justification": "titre explicite",
        },
    )

    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert (arbitrage["source"], arbitrage["source_id"]) == ("ina", "PH_PHD99999999")
    assert arbitrage["valeur"] == "cinéma;livres"
    [emission] = [e for e in donnees["emissions"] if e["id"] == "2014-09-28"]
    assert emission["themes"] == ["cinéma", "livres"]  # mixte : reste dans la liste
    assert emission["arbitrage"] == {
        "sorte": "thème",
        "justification": "titre explicite",
    }
    [publie] = donnees["arbitrages"]
    assert publie["attestation"]["date"] == "2014-09-28"


def test_une_emission_mixte_arbitree_s_annule_depuis_l_emission(
    url: str, sortie: Path
) -> None:
    _post(
        f"{url}/api/arbitrages",
        {"emission_id": "2014-09-28", "sorte": "thème", "themes": ["livres", "cinéma"]},
    )

    donnees = _post(f"{url}/api/annulations", {"emission_id": "2014-09-28"})

    [emission] = [e for e in donnees["emissions"] if e["id"] == "2014-09-28"]
    assert emission["arbitrage"] is None
    assert _lignes(sortie / "arbitrages.csv") == []


def test_n_existe_pas_retire_l_emission_et_ses_doutes(url: str, sortie: Path) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {"emission_id": "2013-06-30", "sorte": "existence"},
    )

    assert "2013-06-30" not in _ids(donnees)
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert (arbitrage["sorte"], arbitrage["valeur"]) == ("existence", "n'existe pas")
    assert "2013-06-30" not in {
        d["emission_id"] for d in _lignes(sortie / "doutes.csv")
    }


@pytest.mark.parametrize(
    "corps",
    [
        {"emission_id": "1900-01-01", "sorte": "existence"},
        {"emission_id": "1967-01-01", "sorte": "thème", "themes": []},
        {"emission_id": "1967-01-01", "sorte": "thème", "themes": ["peinture"]},
        {"emission_id": "1967-01-01", "sorte": "autre"},
    ],
)
def test_une_demande_invalide_est_refusee_sans_rien_ecrire(
    url: str, sortie: Path, corps: dict[str, Any]
) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post(f"{url}/api/arbitrages", corps)

    assert erreur.value.code == 400
    assert json.load(erreur.value)["erreur"]
    assert not (sortie / "arbitrages.csv").exists()


def test_la_page_servie_porte_les_controles_d_arbitrage(url: str) -> None:
    with urllib.request.urlopen(url) as r:
        page = r.read().decode()

    assert 'id="arbitrage"' in page
    assert "/api/arbitrages" in page


def test_les_lignes_ecrites_a_la_main_restent_intactes(url: str, sortie: Path) -> None:
    a_la_main = (
        "source,source_id,sorte,valeur,justification,date\n"
        "ina,PH_INCONNUE,thème,théâtre;livres,à la main,2026-11-10\n"
    )
    (sortie / "arbitrages.csv").write_text(a_la_main, encoding="utf-8")

    _post(f"{url}/api/arbitrages", {"emission_id": "2013-06-30", "sorte": "existence"})
    texte = (sortie / "arbitrages.csv").read_text(encoding="utf-8")
    assert texte.startswith(a_la_main)
    assert len(texte.splitlines()) == 3

    _post(
        f"{url}/api/annulations",
        {"source": "wayback_podcast", "source_id": "ITEMA_20496304"},
    )
    assert (sortie / "arbitrages.csv").read_text(encoding="utf-8") == a_la_main


def test_a_ecouter_renvoie_l_emission_puis_un_arbitrage_de_theme_le_remplace(
    url: str, sortie: Path
) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {"emission_id": "1967-01-01", "sorte": "écoute"},
    )

    [emission] = [e for e in donnees["emissions"] if e["id"] == "1967-01-01"]
    assert emission["arbitrage"]["sorte"] == "écoute"
    assert {d["a_ecouter"] for d in emission["doutes"]} == {True}
    [renvoi] = _lignes(sortie / "arbitrages.csv")
    assert (renvoi["source_id"], renvoi["sorte"], renvoi["valeur"]) == (
        "ITEMA_23820437",
        "écoute",
        "à écouter",
    )

    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "1967-01-01",
            "sorte": "thème",
            "themes": ["livres"],
            "justification": "écouté l'enregistrement",
        },
    )

    [emission] = [e for e in donnees["emissions"] if e["id"] == "1967-01-01"]
    assert emission["arbitrage"]["sorte"] == "thème"
    assert [(d["type"], d["a_ecouter"]) for d in emission["doutes"]] == [
        ("attestation fragile", False)
    ]


def test_a_ecouter_est_refuse_pour_une_emission_sans_doute(
    url: str, sortie: Path
) -> None:
    donnees = _get(f"{url}/api/donnees")
    sans_doute = next(e["id"] for e in donnees["emissions"] if not e["doutes"])

    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post(f"{url}/api/arbitrages", {"emission_id": sans_doute, "sorte": "écoute"})

    assert erreur.value.code == 400
    assert not (sortie / "arbitrages.csv").exists()
