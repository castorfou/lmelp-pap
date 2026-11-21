"""La maturité des enregistrements : vérification des URL d'intégral et règles
de passage d'un niveau à l'autre (glossaire, *maturité d'un enregistrement*).

Le réseau est simulé par une session factice, Mongo par mongomock.
"""

from datetime import UTC, datetime
from typing import Any

import mongomock
import pytest
import requests

from lmelp_pap.maturite import (
    NIVEAUX,
    Depot,
    Enregistrement,
    Verification,
    appliquer,
    classer,
    integraux,
    maturite_emission,
    verifier,
)


HIER = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
AUJOURDHUI = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
URL = "https://media.radiofrance-podcast.net/podcast09/a.m4a"


class Reponse:
    """Une réponse HTTP minimale, comme celles de ``requests``."""

    def __init__(self, statut: int, type_: str = "audio/mp4"):
        self.status_code = statut
        self.headers = {"Content-Type": type_}


def ok() -> Verification:
    return Verification(AUJOURDHUI, "ok", "200")


def net() -> Verification:
    return Verification(AUJOURDHUI, "net", "404")


def passager() -> Verification:
    return Verification(AUJOURDHUI, "passager", "timeout")


def enregistrement(niveau: str) -> Enregistrement:
    return Enregistrement(
        url=URL,
        emission_id="2008-03-02",
        source="radiofrance",
        niveau=niveau,
        entrees={niveau: HIER},
        verification=Verification(HIER, "ok", "200"),
    )


# --- classer : le verdict d'une vérification -------------------------------


@pytest.mark.parametrize(
    ("reponse", "resultat"),
    [
        (Reponse(200, "audio/mp4"), "ok"),
        (Reponse(200, "audio/mpeg"), "ok"),
        (Reponse(200, "text/html; charset=utf-8"), "net"),
        (Reponse(404), "net"),
        (Reponse(410), "net"),
        (Reponse(500), "passager"),
        (Reponse(503), "passager"),
        (Reponse(429), "passager"),
        (Reponse(403), "passager"),
        (requests.Timeout("trop long"), "passager"),
        (requests.ConnectionError("hors ligne"), "passager"),
    ],
)
def test_classer(reponse: Any, resultat: str) -> None:
    verification = classer(reponse, AUJOURDHUI)
    assert verification.resultat == resultat
    assert verification.date == AUJOURDHUI
    assert verification.detail


# --- appliquer : les passages d'un niveau à l'autre ------------------------


@pytest.mark.parametrize(
    ("avant", "verification", "apres"),
    [
        (None, ok(), "telechargeable"),
        (None, net(), "localise"),
        (None, passager(), "localise"),
        ("localise", ok(), "telechargeable"),
        ("localise", net(), "localise"),
        ("localise", passager(), "localise"),
        ("telechargeable", ok(), "telechargeable"),
        ("telechargeable", net(), "localise"),
        ("telechargeable", passager(), "telechargeable"),
        ("rapatrie", net(), "rapatrie"),
        ("qualifie", net(), "qualifie"),
        ("valide", net(), "valide"),
        ("rapatrie", ok(), "rapatrie"),
    ],
)
def test_appliquer(avant: str | None, verification: Verification, apres: str) -> None:
    existant = enregistrement(avant) if avant else None
    resultat = appliquer(existant, verification, URL, "2008-03-02")
    assert resultat.niveau == apres
    assert resultat.verification == verification


def test_un_nouvel_enregistrement_est_date_du_jour() -> None:
    resultat = appliquer(None, ok(), URL, "2008-03-02")
    assert resultat.entrees == {"telechargeable": AUJOURDHUI}
    assert resultat.source == "radiofrance"
    assert resultat.emission_id == "2008-03-02"


def test_rester_au_meme_niveau_garde_la_date_d_entree() -> None:
    resultat = appliquer(enregistrement("telechargeable"), ok(), URL, "2008-03-02")
    assert resultat.entrees["telechargeable"] == HIER


def test_une_url_morte_redescend_a_localise_date_du_jour() -> None:
    resultat = appliquer(enregistrement("telechargeable"), net(), URL, "2008-03-02")
    assert resultat.entrees["localise"] == AUJOURDHUI
    assert resultat.entrees["telechargeable"] == HIER


def test_remonter_apres_une_descente_repart_de_zero() -> None:
    redescendu = appliquer(enregistrement("telechargeable"), net(), URL, "2008-03-02")
    plus_tard = datetime(2026, 12, 1, tzinfo=UTC)
    remonte = appliquer(
        redescendu, Verification(plus_tard, "ok", "200"), URL, "2008-03-02"
    )
    assert remonte.niveau == "telechargeable"
    assert remonte.entrees["telechargeable"] == plus_tard


def test_un_enregistrement_rapatrie_ne_change_pas_de_dates() -> None:
    resultat = appliquer(enregistrement("rapatrie"), net(), URL, "2008-03-02")
    assert resultat.entrees == {"rapatrie": HIER}


# --- maturité d'une émission ------------------------------------------------


def test_la_maturite_d_une_emission_est_celle_de_son_meilleur_enregistrement() -> None:
    assert maturite_emission([]) is None
    assert (
        maturite_emission([enregistrement("localise"), enregistrement("rapatrie")])
        == "rapatrie"
    )
    assert list(NIVEAUX) == [
        "localise",
        "telechargeable",
        "rapatrie",
        "qualifie",
        "valide",
    ]


# --- dépôt Mongo ------------------------------------------------------------


@pytest.fixture
def depot() -> Depot:
    return Depot(mongomock.MongoClient()["masque_et_la_plume"])


def test_le_depot_ecrit_dans_pap_enregistrements(depot: Depot) -> None:
    depot.enregistrer(enregistrement("telechargeable"))
    depot.enregistrer(enregistrement("rapatrie"))  # même URL : remplace
    assert [e.niveau for e in depot.tous()] == ["rapatrie"]
    document = depot.base.pap_enregistrements.find_one({"_id": URL})
    assert document is not None
    assert document["emission_id"] == "2008-03-02"


def test_le_depot_relit_ce_qu_il_a_ecrit(depot: Depot) -> None:
    depot.enregistrer(enregistrement("telechargeable"))
    (relu,) = depot.tous()
    assert relu == enregistrement("telechargeable")


# --- les intégraux à vérifier ----------------------------------------------


def test_integraux_lit_les_urls_d_integral_de_la_liste(tmp_path: Any) -> None:
    (tmp_path / "enregistrements.csv").write_text(
        "emission_id,url,type,sources,duree\n"
        f"2008-03-02,{URL},intégral,radiofrance,00:55:00\n"
        "2008-03-02,https://x/extrait.mp3,extrait,radiofrance,00:05:00\n",
        encoding="utf-8",
    )
    assert integraux(tmp_path) == [(URL, "2008-03-02")]


# --- verifier : toutes les URL ----------------------------------------------


class Session:
    """Une session HTTP factice : une réponse (ou une exception) par URL."""

    def __init__(self, reponses: dict[str, Any]):
        self.reponses = reponses
        self.demandes: list[tuple[str, dict[str, Any]]] = []

    def head(self, url: str, **options: Any) -> Any:
        self.demandes.append((url, options))
        reponse = self.reponses[url]
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def test_verifier_classe_et_enregistre_chaque_url(depot: Depot) -> None:
    depot.enregistrer(enregistrement("rapatrie"))
    session = Session(
        {
            URL: Reponse(404),
            "https://b.m4a": Reponse(200),
            "https://c.m4a": requests.Timeout("lent"),
        }
    )
    a_verifier = [(URL, "2008-03-02"), ("https://b.m4a", "2009-01-04")]
    a_verifier.append(("https://c.m4a", "2010-05-09"))
    vus: list[int] = []
    bilan = verifier(
        a_verifier, depot, session, maintenant=AUJOURDHUI, progres=vus.append
    )
    niveaux = {e.url: e.niveau for e in depot.tous()}
    assert niveaux == {
        URL: "rapatrie",
        "https://b.m4a": "telechargeable",
        "https://c.m4a": "localise",
    }
    assert bilan == {"ok": 1, "net": 1, "passager": 1}
    assert sorted(vus) == [1, 2, 3]
    _, options = session.demandes[0]
    assert options["allow_redirects"] is True
    assert options["timeout"]
    assert "lmelp-pap" in options["headers"]["User-Agent"]


def test_verifier_deux_fois_ne_duplique_rien(depot: Depot) -> None:
    session = Session({URL: Reponse(200)})
    verifier([(URL, "2008-03-02")], depot, session, maintenant=HIER)
    verifier([(URL, "2008-03-02")], depot, session, maintenant=AUJOURDHUI)
    (seul,) = depot.tous()
    assert seul.entrees == {"telechargeable": HIER}
    assert seul.verification is not None
    assert seul.verification.date == AUJOURDHUI
