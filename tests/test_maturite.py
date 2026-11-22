"""La maturité des enregistrements : vérification des URL d'intégral et règles
de passage d'un niveau à l'autre (glossaire, *maturité d'un enregistrement*).

Le réseau est simulé par une session factice, Mongo par mongomock.
"""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import mongomock
import pytest
import requests

from lmelp_pap.maturite import (
    NIVEAUX,
    Depot,
    Enregistrement,
    Qualification,
    QualificationError,
    RapatriementError,
    RapatriementInterrompuError,
    Verification,
    appliquer,
    classer,
    ecrire_qualifications,
    integraux,
    maturite_emission,
    meilleur,
    qualifier,
    rapatrier,
    retenu,
    verification_due,
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


def test_un_echec_passager_de_verification_est_journalise(
    depot: Depot, capfd: pytest.CaptureFixture[str]
) -> None:
    session = Session(
        {URL: Reponse(404), "https://c.m4a": requests.ConnectionError("hors ligne")}
    )

    verifier(
        [(URL, "2008-03-02"), ("https://c.m4a", "2010-05-09")],
        depot,
        session,
        maintenant=AUJOURDHUI,
    )

    logs = capfd.readouterr().err
    assert (
        "WARNING maturite : vérification 2010-05-09 https://c.m4a : ConnectionError"
        in logs
    )
    assert "2008-03-02" not in logs  # une URL morte n'est pas un échec réseau


def test_verifier_deux_fois_ne_duplique_rien(depot: Depot) -> None:
    session = Session({URL: Reponse(200)})
    verifier([(URL, "2008-03-02")], depot, session, maintenant=HIER)
    verifier([(URL, "2008-03-02")], depot, session, maintenant=AUJOURDHUI)
    (seul,) = depot.tous()
    assert seul.entrees == {"telechargeable": HIER}
    assert seul.verification is not None
    assert seul.verification.date == AUJOURDHUI


def test_meilleur_rend_l_enregistrement_le_plus_avance() -> None:
    assert meilleur([]) is None
    rapatrie = enregistrement("rapatrie")
    assert meilleur([enregistrement("localise"), rapatrie]) == rapatrie


# --- rapatrier : télécharger l'intégral sur le NAS --------------------------

M4A = "https://media.radiofrance-podcast.net/podcast09/14007-02.03.2008-27.m4a"
MP3 = "https://media.radiofrance-podcast.net/podcast09/14007-02.03.2008-22.mp3"
SON = b"ID3" + bytes(range(256)) * 40
EMPREINTE = hashlib.sha256(SON).hexdigest()


def telechargeable(url: str = M4A) -> Enregistrement:
    return replace(enregistrement("telechargeable"), url=url)


class Flux:
    """Une réponse ``GET`` en flux : des morceaux, puis éventuellement une
    coupure."""

    def __init__(
        self, statut: int = 200, coupure: bool = False, longueur: int | None = None
    ):
        self.status_code = statut
        self.coupure = coupure
        self.headers = {"Content-Length": str(longueur)} if longueur else {}

    def iter_content(self, chunk_size: int = 1) -> Any:
        yield SON[:1000]
        if self.coupure:
            raise requests.ConnectionError("coupure")
        yield SON[1000:]

    def close(self) -> None:
        pass


class SessionFlux:
    def __init__(self, reponse: Flux | None = None):
        self.reponse = reponse or Flux()
        self.demandes: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **options: Any) -> Flux:
        self.demandes.append((url, options))
        return self.reponse


def test_retenu_prefere_le_m4a() -> None:
    assert retenu([telechargeable(MP3), telechargeable(M4A)]) == telechargeable(M4A)
    assert retenu([telechargeable(MP3)]) == telechargeable(MP3)
    assert retenu([]) is None
    assert retenu([enregistrement("localise")]) is None


def test_rapatrier_ecrit_le_fichier_par_annee_et_passe_a_rapatrie(
    tmp_path: Any,
) -> None:
    session = SessionFlux()
    resultat = rapatrier(telechargeable(), tmp_path, session, AUJOURDHUI)

    fichier = tmp_path / "2008" / "14007-02.03.2008-27.m4a"
    assert fichier.read_bytes() == SON
    assert resultat.niveau == "rapatrie"
    assert resultat.entrees["rapatrie"] == AUJOURDHUI
    assert resultat.entrees["telechargeable"] == HIER
    assert resultat.fichier == "2008/14007-02.03.2008-27.m4a"
    assert resultat.sha256 == EMPREINTE
    assert resultat.taille == len(SON)
    assert not list(tmp_path.rglob("*.part"))
    url, options = session.demandes[0]
    assert url == M4A
    assert options["stream"] is True
    assert "lmelp-pap" in options["headers"]["User-Agent"]


def test_un_fichier_deja_la_avec_la_bonne_empreinte_n_est_pas_retelecharge(
    tmp_path: Any,
) -> None:
    (tmp_path / "2008").mkdir()
    (tmp_path / "2008" / "14007-02.03.2008-27.m4a").write_bytes(SON)
    deja = replace(
        telechargeable(), fichier="2008/14007-02.03.2008-27.m4a", sha256=EMPREINTE
    )
    session = SessionFlux()
    resultat = rapatrier(deja, tmp_path, session, AUJOURDHUI)
    assert session.demandes == []
    assert resultat.niveau == "rapatrie"


def test_un_fichier_a_la_mauvaise_empreinte_est_retelecharge(tmp_path: Any) -> None:
    (tmp_path / "2008").mkdir()
    (tmp_path / "2008" / "14007-02.03.2008-27.m4a").write_bytes(b"abime")
    deja = replace(
        telechargeable(), fichier="2008/14007-02.03.2008-27.m4a", sha256=EMPREINTE
    )
    session = SessionFlux()
    rapatrier(deja, tmp_path, session, AUJOURDHUI)
    assert len(session.demandes) == 1
    assert (tmp_path / "2008" / "14007-02.03.2008-27.m4a").read_bytes() == SON


def test_une_coupure_ne_laisse_aucun_fichier(tmp_path: Any) -> None:
    with pytest.raises(requests.ConnectionError):
        rapatrier(
            telechargeable(),
            tmp_path,
            SessionFlux(Flux(coupure=True)),
            AUJOURDHUI,
            attendre=_sans_pause,
        )
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_une_url_qui_ne_repond_pas_200_echoue_sans_fichier(tmp_path: Any) -> None:
    with pytest.raises(RapatriementError, match="404"):
        rapatrier(telechargeable(), tmp_path, SessionFlux(Flux(404)), AUJOURDHUI)
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_seul_un_telechargeable_se_rapatrie(tmp_path: Any) -> None:
    with pytest.raises(RapatriementError, match="localise"):
        rapatrier(enregistrement("localise"), tmp_path, SessionFlux(), AUJOURDHUI)


def test_le_depot_garde_fichier_empreinte_et_taille(depot: Depot) -> None:
    rapatrie = replace(
        enregistrement("rapatrie"), fichier="2008/a.m4a", sha256="ab", taille=3
    )
    depot.enregistrer(rapatrie)
    assert depot.tous() == [rapatrie]


# --- second tour : tentatives, progression, arrêt, échec mémorisé ------------


class SessionSuite:
    """Une réponse (ou une exception à lever) par appel, dans l'ordre."""

    def __init__(self, *reponses: Any):
        self.reponses = list(reponses)
        self.appels = 0

    def get(self, url: str, **options: Any) -> Any:
        self.appels += 1
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def _sans_pause(_: float) -> None:
    pass


def test_un_echec_passager_est_retente(tmp_path: Any) -> None:
    session = SessionSuite(requests.ReadTimeout("lent"), Flux(coupure=True), Flux())
    resultat = rapatrier(
        telechargeable(), tmp_path, session, AUJOURDHUI, attendre=_sans_pause
    )
    assert session.appels == 3
    assert resultat.niveau == "rapatrie"
    assert (tmp_path / "2008" / "14007-02.03.2008-27.m4a").read_bytes() == SON


def test_au_bout_de_trois_essais_l_echec_remonte(tmp_path: Any) -> None:
    session = SessionSuite(*[requests.ReadTimeout("lent")] * 3)
    with pytest.raises(requests.ReadTimeout):
        rapatrier(telechargeable(), tmp_path, session, AUJOURDHUI, attendre=_sans_pause)
    assert session.appels == 3
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_un_statut_http_n_est_pas_retente(tmp_path: Any) -> None:
    session = SessionSuite(Flux(404))
    with pytest.raises(RapatriementError):
        rapatrier(telechargeable(), tmp_path, session, AUJOURDHUI, attendre=_sans_pause)
    assert session.appels == 1


def test_la_progression_suit_les_octets_recus(tmp_path: Any) -> None:
    vus: list[tuple[int, int | None]] = []
    rapatrier(
        telechargeable(),
        tmp_path,
        SessionFlux(Flux(longueur=len(SON))),
        AUJOURDHUI,
        progres=lambda recus, total: vus.append((recus, total)),
    )
    assert vus[-1] == (len(SON), len(SON))
    assert vus[0][0] == 1000


def test_arreter_coupe_le_telechargement_sans_laisser_de_fichier(
    tmp_path: Any,
) -> None:
    with pytest.raises(RapatriementInterrompuError):
        rapatrier(
            telechargeable(), tmp_path, SessionFlux(), AUJOURDHUI, arreter=lambda: True
        )
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_l_echec_d_un_rapatriement_se_memorise(depot: Depot) -> None:
    echoue = replace(telechargeable(), echec=Verification(AUJOURDHUI, "net", "lent"))
    depot.enregistrer(echoue)
    assert depot.tous() == [echoue]


def test_un_rapatriement_reussi_efface_l_echec(tmp_path: Any) -> None:
    echoue = replace(telechargeable(), echec=Verification(AUJOURDHUI, "net", "lent"))
    assert rapatrier(echoue, tmp_path, SessionFlux(), AUJOURDHUI).echec is None


# --- vérification automatique : quand vérifier, et quoi ----------------------

SEMAINE = timedelta(days=7)
LISTE = [(URL, "2008-03-02"), (M4A, "2008-03-02")]


def test_base_vide_verification_complete() -> None:
    assert verification_due(LISTE, set(), None, AUJOURDHUI, SEMAINE) == (
        "complete",
        LISTE,
    )


def test_jamais_verifiee_verification_complete() -> None:
    connues = {URL, M4A}
    assert verification_due(LISTE, connues, None, AUJOURDHUI, SEMAINE)[0] == "complete"


def test_a_jour_rien_a_faire() -> None:
    connues = {URL, M4A}
    assert verification_due(LISTE, connues, HIER, AUJOURDHUI, SEMAINE) == (None, [])


def test_perimee_verification_complete() -> None:
    il_y_a_8_jours = AUJOURDHUI - timedelta(days=8)
    connues = {URL, M4A}
    assert verification_due(LISTE, connues, il_y_a_8_jours, AUJOURDHUI, SEMAINE) == (
        "complete",
        LISTE,
    )


def test_urls_nouvelles_seules() -> None:
    assert verification_due(LISTE, {URL}, HIER, AUJOURDHUI, SEMAINE) == (
        "nouvelles",
        [(M4A, "2008-03-02")],
    )


def test_le_depot_garde_la_date_de_la_derniere_verification(depot: Depot) -> None:
    assert depot.derniere_verification() is None
    depot.noter_verification(HIER)
    depot.noter_verification(AUJOURDHUI)
    assert depot.derniere_verification() == AUJOURDHUI


def test_chaque_nouvel_essai_est_signale(tmp_path: Any) -> None:
    signales: list[tuple[int, str, float]] = []
    rapatrier(
        telechargeable(),
        tmp_path,
        SessionSuite(requests.ReadTimeout("lent"), Flux()),
        AUJOURDHUI,
        attendre=_sans_pause,
        relance=lambda essai, erreur, pause: signales.append(
            (essai, str(erreur), pause)
        ),
    )
    assert signales == [(1, "lent", 5)]


# --- qualification d'un enregistrement rapatrié -----------------------------


def rapatrie() -> Enregistrement:
    return replace(enregistrement("rapatrie"), fichier="2008/a.m4a")


def test_une_qualification_favorable_rend_l_enregistrement_qualifie() -> None:
    qualifie, qualification = qualifier(rapatrie(), "favorable", "", AUJOURDHUI)
    assert qualifie.niveau == "qualifie"
    assert qualifie.entrees == {"rapatrie": HIER, "qualifie": AUJOURDHUI}
    assert qualification == Qualification(
        enregistrement=URL,
        emission_id="2008-03-02",
        verdict="favorable",
        motif="",
        date=AUJOURDHUI,
    )
    assert qualifie.ecart is None


def test_un_enregistrement_ecarte_reste_rapatrie_et_garde_son_motif() -> None:
    ecarte, qualification = qualifier(
        rapatrie(), "ecarte", "  pas la bonne émission ", AUJOURDHUI
    )
    assert ecarte.niveau == "rapatrie"
    assert ecarte.entrees == {"rapatrie": HIER}
    assert qualification.verdict == "ecarte"
    assert qualification.motif == "pas la bonne émission"
    assert ecarte.ecart == qualification


def test_une_qualification_favorable_efface_un_ecart() -> None:
    ecarte, _ = qualifier(rapatrie(), "ecarte", "coupé", HIER)
    qualifie, _ = qualifier(ecarte, "favorable", "", AUJOURDHUI)
    assert qualifie.niveau == "qualifie"
    assert qualifie.ecart is None


@pytest.mark.parametrize(
    ("niveau", "verdict", "motif", "message"),
    [
        ("rapatrie", "ecarte", "  ", "motif"),
        ("rapatrie", "peut-être", "", "verdict"),
        ("telechargeable", "favorable", "", "telechargeable"),
        ("qualifie", "favorable", "", "qualifie"),
    ],
)
def test_une_qualification_impossible_est_refusee(
    niveau: str, verdict: str, motif: str, message: str
) -> None:
    with pytest.raises(QualificationError, match=message):
        qualifier(replace(rapatrie(), niveau=niveau), verdict, motif, AUJOURDHUI)


def test_le_depot_garde_l_ecart_et_les_qualifications(depot: Depot) -> None:
    ecarte, qualification = qualifier(rapatrie(), "ecarte", "coupé", AUJOURDHUI)
    depot.enregistrer(ecarte)
    depot.ajouter_qualification(qualification)
    assert depot.tous() == [ecarte]
    assert depot.qualifications() == [qualification]
    assert depot.base["pap_qualifications"].count_documents({}) == 1


def test_les_qualifications_s_exportent_en_csv(tmp_path: Any) -> None:
    _, favorable = qualifier(rapatrie(), "favorable", "", AUJOURDHUI)
    _, ecart = qualifier(rapatrie(), "ecarte", "coupé, à 40 min", HIER)
    ecrire_qualifications([favorable, ecart], tmp_path)
    assert (tmp_path / "qualifications.csv").read_text(encoding="utf-8") == (
        "emission_id,enregistrement,verdict,motif,date\n"
        f'2008-03-02,{URL},ecarte,"coupé, à 40 min",2026-11-20T09:00:00+00:00\n'
        f"2008-03-02,{URL},favorable,,2026-11-21T09:00:00+00:00\n"
    )
