"""L'outil ``lmelp-pap arbitrer``, au seam de son API HTTP.

Le serveur est démarré sur un port libre, avec un cache rempli par les fixtures
et un dossier de sortie temporaire ; il reconstruit la liste sans réseau.
"""

import csv
import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap.arbitrer import Atelier, creer_serveur
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
        # L'émission du samedi 1er août 2020 : l'INA la donne aussi le
        # dimanche et le lundi, d'où un désaccord de date.
        for jour in ("01", "02", "03"):
            f.write(
                f"2020-08-{jour},Le masque et la plume,Le masque et la plume,"
                "France Inter,20:00:00,00:55:00,Débat,"
                f"https://catalogue.ina.fr/doc/TV-RADIO/PH_RD202008{jour}/masque,"
                "oui\n"
            )
        # Mars 2015 : la notice sans thème du mardi 3 est rapprochée de
        # l'émission livres du 1er, mais rapprochable aussi de celle, cinéma,
        # du 5 : un rapprochement ambigu.
        for jour, titre, litterature in (
            ("01", "Livres", "oui"),
            ("03", "Le masque et la plume", "non"),
            ("05", "Cinéma", "non"),
        ):
            f.write(
                f"2015-03-{jour},{titre},Le masque et la plume,France Inter,"
                "20:00:00,00:55:00,Débat,"
                f"https://catalogue.ina.fr/doc/TV-RADIO/PH_RD201503{jour}/masque,"
                f"{litterature}\n"
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


def test_un_arbitrage_hommage_sort_l_emission_de_la_liste(
    url: str, sortie: Path
) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {"emission_id": "1967-01-01", "sorte": "thème", "themes": ["hommage"]},
    )

    assert "1967-01-01" not in _ids(donnees)
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert (arbitrage["sorte"], arbitrage["valeur"]) == ("thème", "hommage")
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


def test_la_route_health_repond_sans_construire_la_page(url: str) -> None:
    assert _get(f"{url}/health") == {"status": "ok"}


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


def test_existe_leve_l_attestation_fragile_et_s_annule_depuis_l_emission(
    url: str, sortie: Path
) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "1967-01-01",
            "sorte": "existence",
            "valeur": "existe",
            "justification": "titre explicite",
        },
    )

    [emission] = [e for e in donnees["emissions"] if e["id"] == "1967-01-01"]
    assert [d["type"] for d in emission["doutes"]] == ["thème inconnu"]
    assert emission["arbitrage_existence"] == {"justification": "titre explicite"}
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert (arbitrage["sorte"], arbitrage["valeur"]) == ("existence", "existe")

    donnees = _post(f"{url}/api/annulations", {"emission_id": "1967-01-01"})

    [emission] = [e for e in donnees["emissions"] if e["id"] == "1967-01-01"]
    assert emission["arbitrage_existence"] is None
    assert "attestation fragile" in {d["type"] for d in emission["doutes"]}


@pytest.mark.parametrize(
    "corps",
    [
        {"emission_id": "1900-01-01", "sorte": "existence"},
        {"emission_id": "1967-01-01", "sorte": "thème", "themes": []},
        {"emission_id": "1967-01-01", "sorte": "thème", "themes": ["peinture"]},
        {
            "emission_id": "1967-01-01",
            "sorte": "thème",
            "themes": ["hommage", "livres"],
        },
        {"emission_id": "1967-01-01", "sorte": "autre"},
        {"emission_id": "1967-01-01", "sorte": "existence", "valeur": "peut-être"},
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


def test_la_liste_servie_porte_les_controles_d_arbitrage(url: str) -> None:
    with urllib.request.urlopen(f"{url}/liste") as r:
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


# --- Arbitrage de date ------------------------------------------------------------


def _emission(donnees: dict[str, Any], emission_id: str) -> Any:
    emissions: list[dict[str, Any]] = donnees["emissions"]
    [emission] = [e for e in emissions if e["id"] == emission_id]
    return emission


def test_les_dates_candidates_d_un_doute_de_date_ont_leur_jour_et_leurs_sources(
    url: str,
) -> None:
    emission = _emission(_get(f"{url}/api/donnees"), "2020-08-01")

    assert "désaccord de date" in [d["type"] for d in emission["doutes"]]
    assert emission["dates_candidates"] == [
        {
            "date": "2020-08-01",
            "jour": "samedi",
            "sources": ["ina"],
            "habituel": False,
            "actuelle": True,
        },
        {
            "date": "2020-08-02",
            "jour": "dimanche",
            "sources": ["ina"],
            "habituel": True,
            "actuelle": False,
        },
        {
            "date": "2020-08-03",
            "jour": "lundi",
            "sources": ["ina"],
            "habituel": False,
            "actuelle": False,
        },
    ]


def test_une_emission_sans_doute_de_date_n_a_pas_de_dates_candidates(
    url: str,
) -> None:
    assert _emission(_get(f"{url}/api/donnees"), "2014-09-28")["dates_candidates"] == []


def test_un_arbitrage_de_date_retient_la_date_et_survit_a_une_reconstruction(
    url: str, tmp_path: Path, sortie: Path
) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "2020-08-01",
            "sorte": "date",
            "date": "2020-08-02",
            "justification": "jour habituel",
        },
    )

    assert "2020-08-01" not in _ids(donnees)
    emission = _emission(donnees, "2020-08-02")
    assert emission["doutes"] == []
    assert emission["arbitrage_date"] == {
        "date": "2020-08-02",
        "justification": "jour habituel",
    }
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert (arbitrage["source"], arbitrage["sorte"], arbitrage["valeur"]) == (
        "ina",
        "date",
        "2020-08-02",
    )

    reconstruite = Atelier(tmp_path / "cache", sortie).donnees()

    assert "2020-08-02" in _ids(reconstruite)
    assert "2020-08-01" not in _ids(reconstruite)


def test_un_arbitrage_de_date_s_annule_depuis_l_emission(
    url: str, sortie: Path
) -> None:
    _post(
        f"{url}/api/arbitrages",
        {"emission_id": "2020-08-01", "sorte": "date", "date": "2020-08-02"},
    )

    donnees = _post(f"{url}/api/annulations", {"emission_id": "2020-08-02"})

    assert _emission(donnees, "2020-08-01")["arbitrage_date"] is None


@pytest.mark.parametrize(
    "corps",
    [
        # une date qu'aucune source ne donne
        {"emission_id": "2020-08-01", "sorte": "date", "date": "2020-08-09"},
        {"emission_id": "2020-08-01", "sorte": "date", "date": "1er août"},
        {"emission_id": "2020-08-01", "sorte": "date"},
        # une émission sans doute de date
        {"emission_id": "2014-09-28", "sorte": "date", "date": "2014-09-28"},
    ],
)
def test_un_arbitrage_de_date_invalide_est_refuse_sans_rien_ecrire(
    url: str, sortie: Path, corps: dict[str, Any]
) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post(f"{url}/api/arbitrages", corps)

    assert erreur.value.code == 400
    assert not (sortie / "arbitrages.csv").exists()


def test_une_date_arbitree_se_change_sans_annuler_l_arbitrage_de_theme(
    url: str, sortie: Path
) -> None:
    _post(
        f"{url}/api/arbitrages",
        {"emission_id": "2020-08-01", "sorte": "date", "date": "2020-08-02"},
    )
    _post(
        f"{url}/api/arbitrages",
        {"emission_id": "2020-08-02", "sorte": "thème", "themes": ["livres"]},
    )
    candidates = _emission(_get(f"{url}/api/donnees"), "2020-08-02")["dates_candidates"]
    assert [(c["date"], c["actuelle"]) for c in candidates] == [
        ("2020-08-01", False),
        ("2020-08-02", True),
        ("2020-08-03", False),
    ]

    donnees = _post(
        f"{url}/api/arbitrages",
        {"emission_id": "2020-08-02", "sorte": "date", "date": "2020-08-01"},
    )

    emission = _emission(donnees, "2020-08-01")
    assert emission["arbitrage_date"]["date"] == "2020-08-01"
    assert emission["arbitrage"]["sorte"] == "thème"


# --- Arbitrage de rapprochement --------------------------------------------------


def _attestations(donnees: dict[str, Any], emission_id: str) -> list[str]:
    return [a["titre"] for a in _emission(donnees, emission_id)["attestations"]]


def test_un_rapprochement_ambigu_a_son_attestation_et_ses_rivales(url: str) -> None:
    emission = _emission(_get(f"{url}/api/donnees"), "2015-03-01")

    assert {
        "type": "rapprochement ambigu",
        "detail": "rapprochable aussi de 2015-03-05",
        "a_ecouter": False,
        "source": "ina",
        "source_id": "PH_RD20150303",
    } in emission["doutes"]
    assert emission["rapprochements"] == [
        {"source": "ina", "source_id": "PH_RD20150303", "rivales": ["2015-03-05"]}
    ]


def test_garder_ici_leve_le_doute_sans_rien_changer_d_autre(
    url: str, sortie: Path
) -> None:
    avant = _get(f"{url}/api/donnees")

    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "2015-03-01",
            "sorte": "rapprochement",
            "source": "ina",
            "source_id": "PH_RD20150303",
            "vers": None,
        },
    )

    emission = _emission(donnees, "2015-03-01")
    assert "rapprochement ambigu" not in [d["type"] for d in emission["doutes"]]
    assert emission["rapprochements"] == []
    assert _ids(donnees) == _ids(avant)
    assert _attestations(donnees, "2015-03-01") == _attestations(avant, "2015-03-01")
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    assert (
        arbitrage["source"],
        arbitrage["source_id"],
        arbitrage["sorte"],
        arbitrage["valeur"],
    ) == ("ina", "PH_RD20150303", "rapprochement", "garder ici")


def test_deplacer_vers_envoie_l_attestation_sur_l_emission_rivale(
    url: str, tmp_path: Path, sortie: Path
) -> None:
    donnees = _post(
        f"{url}/api/arbitrages",
        {
            "emission_id": "2015-03-01",
            "sorte": "rapprochement",
            "source": "ina",
            "source_id": "PH_RD20150303",
            "vers": "2015-03-05",
        },
    )

    # l'émission cible, cinéma, est hors de la liste
    assert _attestations(donnees, "2015-03-01") == ["Livres"]
    assert "rapprochement ambigu" not in [
        d["type"] for d in _emission(donnees, "2015-03-01")["doutes"]
    ]
    [arbitrage] = _lignes(sortie / "arbitrages.csv")
    # la cible est désignée par une de ses attestations, pas par son identifiant
    assert (arbitrage["sorte"], arbitrage["valeur"]) == (
        "rapprochement",
        "ina:PH_RD20150305",
    )

    reconstruite = Atelier(tmp_path / "cache", sortie).donnees()

    assert _attestations(reconstruite, "2015-03-01") == ["Livres"]


@pytest.mark.parametrize(
    "corps",
    [
        # une émission qui n'est pas rivale
        {"source_id": "PH_RD20150303", "vers": "2014-09-28"},
        # une attestation sans rapprochement ambigu
        {"source_id": "PH_RD20150301", "vers": None},
        {"source_id": "PH_RD20150399", "vers": None},
    ],
)
def test_un_arbitrage_de_rapprochement_invalide_est_refuse_sans_rien_ecrire(
    url: str, sortie: Path, corps: dict[str, Any]
) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post(
            f"{url}/api/arbitrages",
            {"emission_id": "2015-03-01", "sorte": "rapprochement", "source": "ina"}
            | corps,
        )

    assert erreur.value.code == 400
    assert not (sortie / "arbitrages.csv").exists()


def test_le_serveur_sert_le_favicon_ico(url: str) -> None:
    with urllib.request.urlopen(f"{url}/favicon.ico") as r:
        assert r.headers["Content-Type"] == "image/x-icon"
        corps = r.read()

    # en-tête d'un fichier ICO : réservé 0, type 1 (icône)
    assert corps[:4] == b"\x00\x00\x01\x00"


def test_le_serveur_sert_une_icone_demandee_avec_une_query_string(url: str) -> None:
    # un navigateur ou un lien peut forcer le rechargement : ``?v=2``
    with urllib.request.urlopen(f"{url}/favicon.ico?v=2") as r:
        assert r.headers["Content-Type"] == "image/x-icon"
        assert r.read()[:4] == b"\x00\x00\x01\x00"


def test_l_accueil_declare_des_icones_que_le_serveur_sert(url: str) -> None:
    with urllib.request.urlopen(f"{url}/") as r:
        accueil = r.read().decode()

    liens = re.findall(
        r'<link rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', accueil
    )
    assert "/favicon.ico" in liens
    assert "/apple-touch-icon.png" in liens
    for lien in liens:
        with urllib.request.urlopen(f"{url}{lien}") as r:
            assert r.headers["Content-Type"].startswith("image/")
