"""La maturité des enregistrements dans l'appli, au seam de son API HTTP.

Le serveur tourne sur un port libre avec un dépôt mongomock et une session
HTTP factice : la vérification des URL n'atteint jamais le réseau.
"""

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import mongomock
import pytest

from lmelp_pap.arbitrer import creer_serveur
from lmelp_pap.maturite import Depot
from tests.test_commande import _cache_rempli
from tests.test_maturite import SON, Flux, Reponse, Session
from tests.test_radiofrance_api import MASQUE_API


class SessionComplete(Session):
    """HEAD factices pour la vérification, GET en flux pour le rapatriement ;
    ``attente`` retient le téléchargement tant qu'il n'est pas levé."""

    def __init__(self, reponses: dict[str, Any]):
        super().__init__(reponses)
        self.attente = threading.Event()
        self.attente.set()

        self.statut = 200

    def get(self, url: str, **options: Any) -> Flux:
        self.attente.wait(5)
        return Flux(self.statut, longueur=len(SON))


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
    monkeypatch.delenv("RADIOFRANCE_API_TOKEN", raising=False)


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


REPONSES = {
    INTEGRAL_2014: Reponse(200, "audio/mp4"),
    INTEGRAL_2017: Reponse(404),
    INTEGRAL_2024: Reponse(200, "audio/mp4"),
}


@pytest.fixture
def url(tmp_path: Path, depot: Depot) -> Iterator[str]:
    session = SessionComplete(REPONSES)
    for adresse in _demarrer(
        tmp_path,
        depot=depot,
        session=session,
        audios=tmp_path / "audios",
        audios_lmelp=tmp_path / "audios-lmelp",
    ):
        SESSIONS[adresse] = session
        yield adresse


# La session factice de chaque serveur démarré, par adresse.
SESSIONS: dict[str, SessionComplete] = {}


def _session_du_serveur(url: str) -> SessionComplete:
    return SESSIONS[url]


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


def _attendre_bilan(url: str) -> dict[str, Any]:
    """Attend une vérification finie, même lancée par le fil de planification
    (qui peut ne pas avoir encore démarré)."""
    for _ in range(100):
        etat: dict[str, Any] = _get(f"{url}/api/verifications")
        if not etat["en_cours"] and etat["bilan"] is not None:
            return etat
        time.sleep(0.05)
    raise AssertionError("aucune vérification finie")


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
        "derniere": None,
        "prochaine": None,
    }


def test_sans_mongo_la_maturite_est_absente(url_sans_mongo: str) -> None:
    donnees = _get(f"{url_sans_mongo}/api/donnees")
    assert "maturite_active" not in donnees
    assert all("maturite" not in e for e in donnees["emissions"])
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post(f"{url_sans_mongo}/api/verifications")
    assert erreur.value.code == 503


def _texte(url: str) -> str:
    with urllib.request.urlopen(url) as r:
        return str(r.read().decode())


def test_l_accueil_est_sur_la_racine_et_la_liste_sur_liste(url: str) -> None:
    assert 'id="accueil"' in _texte(f"{url}/")
    assert 'id="lignes"' in _texte(f"{url}/liste")


def test_sans_mongo_l_accueil_repond_aussi(url_sans_mongo: str) -> None:
    assert 'id="accueil"' in _texte(f"{url_sans_mongo}/")


def test_chaque_emission_porte_la_date_d_entree_dans_sa_maturite(url: str) -> None:
    _post(f"{url}/api/verifications")
    _attendre_fin(url)
    emissions = {e["id"]: e for e in _get(f"{url}/api/donnees")["emissions"]}
    aujourd_hui = datetime.now(UTC).date().isoformat()
    assert emissions["2014-09-28"]["maturite_depuis"].startswith(aujourd_hui)
    assert emissions["1967-01-01"]["maturite_depuis"] is None


def _post_json(url: str, corps: dict[str, Any]) -> Any:
    requete = urllib.request.Request(
        url,
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requete) as r:
        return json.load(r)


def _attendre_rapatriements(url: str) -> dict[str, Any]:
    for _ in range(100):
        etat: dict[str, Any] = _get(f"{url}/api/rapatriements")
        if not etat["en_cours"]:
            return etat
        time.sleep(0.05)
    raise AssertionError("le rapatriement ne finit pas")


def _verifier(url: str) -> None:
    _post(f"{url}/api/verifications")
    _attendre_fin(url)


def test_rapatrier_une_emission_la_telecharge_et_la_passe_a_rapatrie(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _verifier(url)
    etat = _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    assert etat["total"] == 1

    fin = _attendre_rapatriements(url)

    assert fin["bilan"] == {"rapatries": 1, "deja_la": 0, "echecs": 0}
    fichier = tmp_path / "audios" / "2014" / INTEGRAL_2014.rsplit("/", 1)[1]
    assert fichier.read_bytes() == SON
    assert _maturites(_get(f"{url}/api/donnees"))["2014-09-28"] == "rapatrie"
    (rapatrie,) = [e for e in depot.tous() if e.niveau == "rapatrie"]
    assert rapatrie.fichier == f"2014/{fichier.name}"


def test_rapatrier_une_emission_sans_integral_telechargeable_est_refuse(
    url: str,
) -> None:
    _verifier(url)
    demandes: list[dict[str, Any]] = [
        {"emissions": ["1967-01-01"]},
        {"emissions": []},
        {},
    ]
    for corps in demandes:
        with pytest.raises(urllib.error.HTTPError) as erreur:
            _post_json(f"{url}/api/rapatriements", corps)
        assert erreur.value.code == 400


def test_un_seul_rapatriement_a_la_fois(url: str) -> None:
    _verifier(url)
    # retient le téléchargement en cours
    session = _session_du_serveur(url)
    session.attente.clear()
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post_json(f"{url}/api/rapatriements", {"emissions": ["2024-02-11"]})
    assert erreur.value.code == 409
    session.attente.set()
    _attendre_rapatriements(url)


def test_sans_mongo_pas_de_rapatriement(url_sans_mongo: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post_json(f"{url_sans_mongo}/api/rapatriements", {"emissions": ["x"]})
    assert erreur.value.code == 503


def test_l_avancement_donne_les_octets_recus(url: str) -> None:
    _verifier(url)
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    fin = _attendre_rapatriements(url)
    assert fin["octets"] == len(SON)
    assert fin["rapatriees"] == ["2014-09-28"]
    assert fin["fichier_octets"] == len(SON)
    assert fin["fichier_total"] == len(SON)
    assert fin["debut"]
    assert fin["arrete"] is False


def test_arreter_un_lot(url: str, tmp_path: Path) -> None:
    _verifier(url)
    session = _session_du_serveur(url)
    session.attente.clear()
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28", "2024-02-11"]})
    _post_json(f"{url}/api/rapatriements/arret", {})
    session.attente.set()

    fin = _attendre_rapatriements(url)

    assert fin["arrete"] is True
    assert fin["bilan"]["rapatries"] == 0
    assert [p for p in (tmp_path / "audios").rglob("*") if p.is_file()] == []
    assert _maturites(_get(f"{url}/api/donnees"))["2014-09-28"] == "telechargeable"


def test_un_echec_reste_visible_sur_l_emission(url: str) -> None:
    _verifier(url)
    _session_du_serveur(url).statut = 404
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    fin = _attendre_rapatriements(url)
    assert fin["bilan"]["echecs"] == 1
    emissions = {e["id"]: e for e in _get(f"{url}/api/donnees")["emissions"]}
    echec = emissions["2014-09-28"]["echec_rapatriement"]
    assert "404" in echec["detail"]
    assert echec["date"]
    assert emissions["2024-02-11"]["echec_rapatriement"] is None


# --- vérification automatique -----------------------------------------------


@pytest.fixture
def serveur_planifie(tmp_path: Path, depot: Depot) -> Iterator[Any]:
    """Un serveur avec la planification, et son atelier."""
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    session = SessionComplete(
        {
            INTEGRAL_2014: Reponse(200, "audio/mp4"),
            INTEGRAL_2017: Reponse(404),
            INTEGRAL_2024: Reponse(200, "audio/mp4"),
        }
    )
    serveur: Any = creer_serveur(
        cache,
        tmp_path / "sortie",
        port=0,
        depot=depot,
        session=session,
        audios=tmp_path / "audios",
        planification=True,
    )
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    serveur.url = f"http://127.0.0.1:{serveur.server_address[1]}"
    yield serveur
    serveur.shutdown()
    serveur.server_close()


def test_sur_une_base_vide_la_verification_part_seule(serveur_planifie: Any) -> None:
    fin = _attendre_bilan(serveur_planifie.url)
    assert fin["bilan"] == {"ok": 2, "net": 1, "passager": 0}
    maturites = _maturites(_get(f"{serveur_planifie.url}/api/donnees"))
    assert maturites["2014-09-28"] == "telechargeable"
    assert maturites["2017-01-01"] == "localise"
    assert fin["derniere"]
    assert fin["prochaine"] > fin["derniere"]


def test_planifier_deux_fois_ne_relance_rien(serveur_planifie: Any) -> None:
    _attendre_bilan(serveur_planifie.url)
    assert serveur_planifie.atelier.planifier() is None


def test_une_verification_perimee_repart(serveur_planifie: Any, depot: Depot) -> None:
    _attendre_bilan(serveur_planifie.url)
    depot.noter_verification(datetime.now(UTC) - timedelta(days=8))
    assert serveur_planifie.atelier.planifier() == "complete"
    fin = _attendre_bilan(serveur_planifie.url)
    assert fin["faites"] == 3
    derniere = datetime.fromisoformat(fin["derniere"])
    assert datetime.now(UTC) - derniere < timedelta(minutes=1)


def test_une_url_nouvelle_est_verifiee_seule(
    serveur_planifie: Any, tmp_path: Path, depot: Depot
) -> None:
    _attendre_bilan(serveur_planifie.url)
    avant = depot.derniere_verification()
    nouvelle = "https://media.radiofrance-podcast.net/podcast09/nouvelle.m4a"
    with (tmp_path / "sortie" / "enregistrements.csv").open("a") as f:
        f.write(f"2014-09-28,{nouvelle},intégral,radiofrance,00:55:00\n")
    serveur_planifie.atelier._session.reponses[nouvelle] = Reponse(200, "audio/mp4")

    assert serveur_planifie.atelier.planifier() == "nouvelles"
    fin = _attendre_bilan(serveur_planifie.url)

    assert fin["faites"] == 1
    assert depot.derniere_verification() == avant
    assert nouvelle in {e.url for e in depot.tous()}


def test_sans_planification_rien_ne_part(url: str) -> None:
    time.sleep(0.3)
    assert _get(f"{url}/api/verifications")["bilan"] is None


def test_la_verification_automatique_laisse_une_trace_dans_les_logs(
    serveur_planifie: Any, depot: Depot, capfd: pytest.CaptureFixture[str]
) -> None:
    _attendre_bilan(serveur_planifie.url)
    il_y_a_8_jours = datetime.now(UTC) - timedelta(days=8)
    depot.noter_verification(il_y_a_8_jours)
    capfd.readouterr()  # oublie le démarrage

    serveur_planifie.atelier.planifier()
    _attendre_bilan(serveur_planifie.url)
    time.sleep(0.1)

    logs = capfd.readouterr().err
    date = il_y_a_8_jours.astimezone().strftime("%d/%m/%Y")
    assert f"vérification automatique (complète : dernière le {date} à " in logs
    assert ") : 3 URL" in logs
    assert "vérification terminée" in logs
    assert "2 ok, 1 morte, 0 échec passager" in logs


def test_une_verification_manuelle_est_tracee(
    url: str, capfd: pytest.CaptureFixture[str]
) -> None:
    _post(f"{url}/api/verifications")
    _attendre_fin(url)
    time.sleep(0.1)
    logs = capfd.readouterr().err
    assert "vérification manuelle (complète) : 3 URL" in logs
    assert "vérification terminée" in logs


def test_le_rapatriement_laisse_une_trace_dans_les_logs(
    url: str, capfd: pytest.CaptureFixture[str]
) -> None:
    _verifier(url)
    capfd.readouterr()
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    _attendre_rapatriements(url)
    time.sleep(0.1)
    logs = capfd.readouterr().err
    assert "rapatriement : 1 émission demandée" in logs
    assert f"rapatrié 2014-09-28 : 2014/{INTEGRAL_2014.rsplit('/', 1)[1]}" in logs
    assert "rapatriement terminé en" in logs
    assert "1 rapatrié, 0 déjà là, 0 échec" in logs


def test_un_echec_de_rapatriement_est_trace(
    url: str, capfd: pytest.CaptureFixture[str]
) -> None:
    _verifier(url)
    _session_du_serveur(url).statut = 404
    capfd.readouterr()
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    _attendre_rapatriements(url)
    time.sleep(0.1)
    logs = capfd.readouterr().err
    assert "échec 2014-09-28 : " in logs
    assert "HTTP 404" in logs
    assert "0 rapatrié, 0 déjà là, 1 échec" in logs


# --- écouter et qualifier un enregistrement rapatrié ------------------------

FICHIER_2014 = f"2014/{INTEGRAL_2014.rsplit('/', 1)[1]}"


def _rapatrier_2014(url: str) -> None:
    _verifier(url)
    _post_json(f"{url}/api/rapatriements", {"emissions": ["2014-09-28"]})
    _attendre_rapatriements(url)


def _emissions(donnees: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in donnees["emissions"]}


def test_une_emission_rapatriee_donne_son_fichier_a_ecouter(url: str) -> None:
    _rapatrier_2014(url)
    emissions = _emissions(_get(f"{url}/api/donnees"))
    assert emissions["2014-09-28"]["fichier_audio"] == FICHIER_2014
    assert emissions["2014-09-28"]["ecart"] is None
    assert emissions["2024-02-11"]["fichier_audio"] is None


def test_une_qualification_favorable_rend_l_emission_qualifiee(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _rapatrier_2014(url)
    avant = _emissions(_get(f"{url}/api/donnees"))["2014-09-28"]

    donnees = _post_json(
        f"{url}/api/qualifications",
        {"emission_id": "2014-09-28", "verdict": "favorable"},
    )

    emission = _emissions(donnees)["2014-09-28"]
    assert emission["maturite"] == "qualifie"
    assert emission["themes"] == avant["themes"]
    assert emission["fichier_audio"] == FICHIER_2014
    (qualification,) = depot.qualifications()
    assert qualification.verdict == "favorable"
    assert qualification.enregistrement == INTEGRAL_2014
    csv = (tmp_path / "sortie" / "qualifications.csv").read_text(encoding="utf-8")
    assert f"2014-09-28,{INTEGRAL_2014},favorable,," in csv


def test_un_ecart_laisse_l_emission_rapatriee_et_marquee(
    url: str, depot: Depot
) -> None:
    _rapatrier_2014(url)

    donnees = _post_json(
        f"{url}/api/qualifications",
        {"emission_id": "2014-09-28", "verdict": "ecarte", "motif": "pas la bonne"},
    )

    emission = _emissions(donnees)["2014-09-28"]
    assert emission["maturite"] == "rapatrie"
    assert emission["ecart"]["motif"] == "pas la bonne"
    assert emission["ecart"]["date"]
    assert [q.verdict for q in depot.qualifications()] == ["ecarte"]


def test_une_qualification_invalide_est_refusee(url: str) -> None:
    _rapatrier_2014(url)
    demandes: list[dict[str, Any]] = [
        {"emission_id": "2014-09-28", "verdict": "ecarte", "motif": " "},
        {"emission_id": "2014-09-28", "verdict": "bof"},
        {"emission_id": "2024-02-11", "verdict": "favorable"},  # téléchargeable
        {"emission_id": "inconnue", "verdict": "favorable"},
        {},
    ]
    for corps in demandes:
        with pytest.raises(urllib.error.HTTPError) as erreur:
            _post_json(f"{url}/api/qualifications", corps)
        assert erreur.value.code == 400, corps


def test_sans_mongo_pas_de_qualification(url_sans_mongo: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post_json(
            f"{url_sans_mongo}/api/qualifications",
            {"emission_id": "2014-09-28", "verdict": "favorable"},
        )
    assert erreur.value.code == 503


def test_les_qualifications_sont_tracees(
    url: str, capfd: pytest.CaptureFixture[str]
) -> None:
    _rapatrier_2014(url)
    capfd.readouterr()
    _post_json(
        f"{url}/api/qualifications",
        {"emission_id": "2014-09-28", "verdict": "ecarte", "motif": "coupé"},
    )
    _post_json(
        f"{url}/api/qualifications",
        {"emission_id": "2014-09-28", "verdict": "favorable"},
    )
    with pytest.raises(urllib.error.HTTPError):
        _post_json(
            f"{url}/api/qualifications",
            {"emission_id": "2024-02-11", "verdict": "favorable"},
        )
    logs = capfd.readouterr().err
    assert f"écarté 2014-09-28 ({FICHIER_2014}) : « coupé »" in logs
    assert f"qualifié 2014-09-28 ({FICHIER_2014}) : favorable" in logs
    assert "qualification refusée 2024-02-11 : " in logs


def _lire(url: str, **entetes: str) -> tuple[int, dict[str, str], bytes]:
    requete = urllib.request.Request(url, headers=entetes)
    with urllib.request.urlopen(requete) as r:
        return r.status, dict(r.headers), r.read()


def test_l_audio_rapatrie_s_ecoute(url: str) -> None:
    _rapatrier_2014(url)
    statut, entetes, corps = _lire(f"{url}/audios/{FICHIER_2014}")
    assert statut == 200
    assert corps == SON
    assert entetes["Content-Type"] == "audio/mp4"
    assert entetes["Accept-Ranges"] == "bytes"
    assert entetes["Content-Length"] == str(len(SON))


@pytest.mark.parametrize(
    ("plage", "debut", "fin"),
    [("bytes=10-19", 10, 19), ("bytes=100-", 100, None), ("bytes=-5", None, None)],
)
def test_l_audio_se_lit_par_plage_pour_le_saut(
    url: str, plage: str, debut: int | None, fin: int | None
) -> None:
    _rapatrier_2014(url)
    statut, entetes, corps = _lire(f"{url}/audios/{FICHIER_2014}", Range=plage)
    n = len(SON)
    a = n - 5 if debut is None else debut
    b = n - 1 if fin is None else fin
    assert statut == 206
    assert corps == SON[a : b + 1]
    assert entetes["Content-Range"] == f"bytes {a}-{b}/{n}"
    assert entetes["Content-Length"] == str(b - a + 1)


def test_une_plage_hors_du_fichier_est_refusee(url: str) -> None:
    _rapatrier_2014(url)
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _lire(f"{url}/audios/{FICHIER_2014}", Range=f"bytes={len(SON)}-")
    assert erreur.value.code == 416
    assert erreur.value.headers["Content-Range"] == f"bytes */{len(SON)}"


@pytest.mark.parametrize(
    "chemin",
    [
        "2014/absent.m4a",
        "../sortie/emissions.csv",
        "%2e%2e/sortie/emissions.csv",
        "2014/..%2f..%2fsortie/emissions.csv",
        "",
    ],
)
def test_rien_ne_se_lit_hors_du_dossier_audio(url: str, chemin: str) -> None:
    _rapatrier_2014(url)
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _lire(f"{url}/audios/{chemin}")
    assert erreur.value.code == 404


# --- mettre à disposition de lmelp ------------------------------------------


def _qualifier_2014(url: str) -> None:
    _rapatrier_2014(url)
    _post_json(
        f"{url}/api/qualifications",
        {"emission_id": "2014-09-28", "verdict": "favorable"},
    )


def _remettre(url: str, *ids: str) -> Any:
    return _post_json(f"{url}/api/remises", {"emissions": list(ids)})


def test_mettre_a_disposition_copie_ecrit_la_fiche_et_rend_valide(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _qualifier_2014(url)

    donnees = _remettre(url, "2014-09-28")

    assert (tmp_path / "audios-lmelp" / FICHIER_2014).read_bytes() == SON
    assert (tmp_path / "audios" / FICHIER_2014).exists()
    emission = _emissions(donnees)["2014-09-28"]
    assert emission["maturite"] == "valide"
    assert emission["dans_lmelp"] is False
    assert donnees["remise"] == {
        "mises": [{"emission": "2014-09-28", "fichier": FICHIER_2014}],
        "refus": [],
    }
    (fiche,) = depot.base["pap_remises"].find()
    assert fiche["_id"] == INTEGRAL_2014
    assert fiche["audio_rel_filename"] == FICHIER_2014
    assert fiche["titre"] == "Le Masque et la Plume du 28 septembre 2014"
    assert fiche["episode_page_url"].endswith("les-livres-a-lire-2989961")
    assert "par : Jérôme Garcin" in fiche["description"]
    (enregistrement,) = [e for e in depot.tous() if e.url == INTEGRAL_2014]
    assert enregistrement.niveau == "valide"


def test_une_collision_est_refusee_avec_un_message_sans_toucher_aux_fichiers(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _qualifier_2014(url)
    cible = tmp_path / "audios-lmelp" / FICHIER_2014
    cible.parent.mkdir(parents=True)
    cible.write_bytes(b"celui de lmelp")

    donnees = _remettre(url, "2014-09-28")

    assert cible.read_bytes() == b"celui de lmelp"
    assert [p.name for p in cible.parent.iterdir()] == [cible.name]
    (refus,) = donnees["remise"]["refus"]
    assert refus["emission"] == "2014-09-28"
    assert "existe déjà" in refus["detail"]
    assert _emissions(donnees)["2014-09-28"]["maturite"] == "qualifie"
    assert list(depot.base["pap_remises"].find()) == []


def test_seule_une_emission_qualifiee_se_met_a_disposition(url: str) -> None:
    _rapatrier_2014(url)

    donnees = _remettre(url, "2014-09-28", "inconnue")

    assert [r["emission"] for r in donnees["remise"]["refus"]] == [
        "2014-09-28",
        "inconnue",
    ]
    assert _emissions(donnees)["2014-09-28"]["maturite"] == "rapatrie"


def test_une_demande_sans_emissions_est_invalide(url: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _post_json(f"{url}/api/remises", {})
    assert erreur.value.code == 400


def test_sans_mongo_pas_de_mise_a_disposition(url_sans_mongo: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _remettre(url_sans_mongo, "2014-09-28")
    assert erreur.value.code == 503


def test_un_episode_lmelp_de_meme_fichier_fait_entrer_l_emission_dans_lmelp(
    url: str, depot: Depot
) -> None:
    _qualifier_2014(url)
    _remettre(url, "2014-09-28")
    assert _emissions(_get(f"{url}/api/donnees"))["2014-09-28"]["dans_lmelp"] is False

    depot.base["episodes"].insert_one(
        {"titre": "Le Masque", "audio_rel_filename": FICHIER_2014}
    )

    emissions = _emissions(_get(f"{url}/api/donnees"))
    assert emissions["2014-09-28"]["dans_lmelp"] is True
    assert emissions["2024-02-11"]["dans_lmelp"] is False


def test_une_emission_deja_dans_lmelp_n_est_pas_remise(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _qualifier_2014(url)
    # un autre enregistrement de l'émission est déjà valide et entré dans lmelp
    depot.base["pap_enregistrements"].insert_one(
        {
            "_id": "fonds-prive:2014-09-28",
            "emission_id": "2014-09-28",
            "source": "passionne",
            "niveau": "valide",
            "entrees": {},
            "fichier": "2014/2014-09-28-passionne.mp3",
        }
    )
    depot.base["episodes"].insert_one(
        {"audio_rel_filename": "2014/2014-09-28-passionne.mp3"}
    )

    donnees = _remettre(url, "2014-09-28")

    (refus,) = donnees["remise"]["refus"]
    assert "déjà dans lmelp" in refus["detail"]
    assert not (tmp_path / "audios-lmelp" / FICHIER_2014).exists()


def test_les_mises_a_disposition_sont_tracees(
    url: str, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    _qualifier_2014(url)
    capfd.readouterr()

    _remettre(url, "2014-09-28", "2024-02-11")

    logs = capfd.readouterr().err
    court = hashlib.sha256(SON).hexdigest()[:12]
    assert (
        f"mis à disposition 2014-09-28 : {tmp_path / 'audios' / FICHIER_2014} → "
        f"{tmp_path / 'audios-lmelp' / FICHIER_2014} (sha256 {court})"
    ) in logs
    assert "mise à disposition refusée 2024-02-11 (niveau telechargeable) : " in logs
    assert "mise à disposition : 1 mise à disposition, 1 refus" in logs


def test_une_collision_est_tracee(
    url: str, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    _qualifier_2014(url)
    cible = tmp_path / "audios-lmelp" / FICHIER_2014
    cible.parent.mkdir(parents=True)
    cible.write_bytes(b"x")
    capfd.readouterr()

    _remettre(url, "2014-09-28")

    logs = capfd.readouterr().err
    assert "mise à disposition refusée 2014-09-28 (niveau qualifie) : " in logs
    assert "existe déjà" in logs


def test_une_remise_interrompue_apres_la_copie_se_termine_et_est_tracee(
    url: str, tmp_path: Path, depot: Depot, capfd: pytest.CaptureFixture[str]
) -> None:
    _qualifier_2014(url)
    # une panne a suivi la copie : le fichier est chez lmelp, rien d'autre
    cible = tmp_path / "audios-lmelp" / FICHIER_2014
    cible.parent.mkdir(parents=True)
    cible.write_bytes(SON)
    capfd.readouterr()

    donnees = _remettre(url, "2014-09-28")

    assert donnees["remise"]["refus"] == []
    assert _emissions(donnees)["2014-09-28"]["maturite"] == "valide"
    (fiche,) = depot.base["pap_remises"].find()
    assert fiche["audio_rel_filename"] == FICHIER_2014
    logs = capfd.readouterr().err
    assert "mis à disposition 2014-09-28 : " in logs
    assert "reprise : fichier déjà copié, même sha256" in logs


class SessionAvecApi(SessionComplete):
    """La session factice, avec une API Radio France qui connaît le
    28/09/2014."""

    def __init__(self, reponses: dict[str, Any]):
        super().__init__(reponses)
        self.api: list[dict[str, Any]] = []
        self.statut_api = 200

    def post(self, adresse: str, **options: Any) -> Any:
        self.api.append(options)
        noeud = {
            "url": f"{MASQUE_API}/x-1",
            "show": {"url": MASQUE_API},
            "published_date": str(
                int(datetime(2014, 9, 28, 10, tzinfo=UTC).timestamp())
            ),
            "standFirst": "Chapô de l'API.",
            "personalitiesConnection": {
                "edges": [{"relation": "guest", "node": {"name": "Arnaud Viviant"}}]
            },
        }
        donnees = {"data": {"diffusions": {"edges": [{"cursor": "a", "node": noeud}]}}}

        statut = self.statut_api

        class R:
            status_code = statut

            def json(self) -> Any:
                return donnees

        return R()


def test_avec_un_jeton_l_api_radio_france_complete_la_description(
    tmp_path: Path, depot: Depot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RADIOFRANCE_API_TOKEN", "jeton-secret")
    session = SessionAvecApi(REPONSES)
    for adresse in _demarrer(
        tmp_path,
        depot=depot,
        session=session,
        audios=tmp_path / "audios",
        audios_lmelp=tmp_path / "audios-lmelp",
    ):
        _qualifier_2014(adresse)
        _remettre(adresse, "2014-09-28")

    (fiche,) = depot.base["pap_remises"].find()
    assert "invités : Arnaud Viviant" in fiche["description"]
    assert fiche["sources_description"]["invites"] == "api_radiofrance"
    assert session.api[0]["headers"]["x-token"] == "jeton-secret"
    assert "jeton-secret" not in str(fiche)


def test_sans_jeton_l_api_n_est_pas_lue(
    tmp_path: Path, depot: Depot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RADIOFRANCE_API_TOKEN", raising=False)
    session = SessionAvecApi(REPONSES)
    for adresse in _demarrer(
        tmp_path,
        depot=depot,
        session=session,
        audios=tmp_path / "audios",
        audios_lmelp=tmp_path / "audios-lmelp",
    ):
        _qualifier_2014(adresse)
        donnees = _remettre(adresse, "2014-09-28")

    assert session.api == []
    assert _emissions(donnees)["2014-09-28"]["maturite"] == "valide"


def test_une_api_en_erreur_ne_bloque_pas_la_mise_a_disposition(
    tmp_path: Path,
    depot: Depot,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RADIOFRANCE_API_TOKEN", "jeton-secret")
    session = SessionAvecApi(REPONSES)
    session.statut_api = 403
    for adresse in _demarrer(
        tmp_path,
        depot=depot,
        session=session,
        audios=tmp_path / "audios",
        audios_lmelp=tmp_path / "audios-lmelp",
    ):
        _qualifier_2014(adresse)
        capfd.readouterr()
        donnees = _remettre(adresse, "2014-09-28")

    assert _emissions(donnees)["2014-09-28"]["maturite"] == "valide"
    (fiche,) = depot.base["pap_remises"].find()
    assert "api_radiofrance" not in fiche["sources_description"].values()
    logs = capfd.readouterr().err
    assert (
        "api radiofrance 2014-09-28 (mise à disposition) : erreur HTTP 403, "
        "1 requête (1/1000 aujourd'hui), 0 s"
    ) in logs


def test_l_ecoute_puis_la_remise_ne_lisent_l_api_qu_une_fois(
    tmp_path: Path,
    depot: Depot,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RADIOFRANCE_API_TOKEN", "jeton-secret")
    session = SessionAvecApi(REPONSES)
    for adresse in _demarrer(
        tmp_path,
        depot=depot,
        session=session,
        audios=tmp_path / "audios",
        audios_lmelp=tmp_path / "audios-lmelp",
    ):
        _qualifier_2014(adresse)
        capfd.readouterr()
        ecoute = _get(f"{adresse}/api/radiofrance/2014-09-28")
        _remettre(adresse, "2014-09-28")

    assert ecoute["statut"] == "trouvee"
    assert len(session.api) == 1
    (fiche,) = depot.base["pap_remises"].find()
    assert "invités : Arnaud Viviant" in fiche["description"]
    logs = capfd.readouterr().err
    # un seul compteur du jour pour l'écoute et la mise à disposition
    assert (
        "api radiofrance 2014-09-28 : trouvée, 1 requête (1/1000 aujourd'hui), 0 s"
    ) in logs
    assert (
        "api radiofrance 2014-09-28 (mise à disposition) : trouvée (cache), "
        "0 requête (1/1000 aujourd'hui)"
    ) in logs
    assert "Arnaud Viviant" not in logs


# --- annuler une mise à disposition ------------------------------------------


def _annuler_remise(url: str, emission_id: str) -> Any:
    return _post_json(f"{url}/api/remises/annulation", {"emission": emission_id})


def test_annuler_une_mise_a_disposition_ramene_a_qualifie(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _qualifier_2014(url)
    _remettre(url, "2014-09-28")

    donnees = _annuler_remise(url, "2014-09-28")

    assert _emissions(donnees)["2014-09-28"]["maturite"] == "qualifie"
    assert list(depot.base["pap_remises"].find()) == []
    (enregistrement,) = [e for e in depot.tous() if e.url == INTEGRAL_2014]
    assert enregistrement.niveau == "qualifie"
    assert "valide" not in enregistrement.entrees
    assert not (tmp_path / "audios-lmelp" / FICHIER_2014).exists()
    assert (tmp_path / "audios" / FICHIER_2014).read_bytes() == SON
    # et elle se remet à disposition comme la première fois
    again = _remettre(url, "2014-09-28")
    assert _emissions(again)["2014-09-28"]["maturite"] == "valide"


def test_annuler_garde_un_fichier_lmelp_d_une_autre_empreinte(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _qualifier_2014(url)
    _remettre(url, "2014-09-28")
    copie = tmp_path / "audios-lmelp" / FICHIER_2014
    copie.write_bytes(b"remplace chez lmelp")

    donnees = _annuler_remise(url, "2014-09-28")

    assert _emissions(donnees)["2014-09-28"]["maturite"] == "qualifie"
    assert copie.read_bytes() == b"remplace chez lmelp"


def test_seule_une_emission_valide_hors_lmelp_s_annule(
    url: str, tmp_path: Path, depot: Depot
) -> None:
    _qualifier_2014(url)
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _annuler_remise(url, "2014-09-28")
    assert erreur.value.code == 400

    _remettre(url, "2014-09-28")
    depot.base["episodes"].insert_one({"audio_rel_filename": FICHIER_2014})
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _annuler_remise(url, "2014-09-28")
    assert erreur.value.code == 400
    assert depot.base["pap_remises"].count_documents({}) == 1
    assert (tmp_path / "audios-lmelp" / FICHIER_2014).exists()


def test_l_annulation_est_tracee(
    url: str, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    _qualifier_2014(url)
    _remettre(url, "2014-09-28")
    capfd.readouterr()

    _annuler_remise(url, "2014-09-28")

    logs = capfd.readouterr().err
    assert (
        "mise à disposition annulée 2014-09-28 : fiche pap_remises retirée, "
        f"copie retirée {tmp_path / 'audios-lmelp' / FICHIER_2014}, "
        "retour à qualifié"
    ) in logs


# --- la fiche d'une mise à disposition --------------------------------------


def test_la_fiche_d_une_mise_a_disposition_se_lit(url: str) -> None:
    _rapatrier_2014(url)
    with pytest.raises(urllib.error.HTTPError) as erreur:
        _get(f"{url}/api/remises/2014-09-28")
    assert erreur.value.code == 404

    _post_json(
        f"{url}/api/qualifications",
        {"emission_id": "2014-09-28", "verdict": "favorable"},
    )
    apercu = _get(f"{url}/api/remises/2014-09-28")
    assert apercu["apercu"] is True
    assert apercu["date_remise"] is None
    assert apercu["audio_rel_filename"] == FICHIER_2014

    _remettre(url, "2014-09-28")
    fiche = _get(f"{url}/api/remises/2014-09-28")
    assert fiche["apercu"] is False
    assert {k: v for k, v in fiche.items() if k not in ("apercu", "date_remise")} == {
        k: v for k, v in apercu.items() if k not in ("apercu", "date_remise")
    }

    assert fiche["titre"] == "Le Masque et la Plume du 28 septembre 2014"
    assert fiche["audio_rel_filename"] == FICHIER_2014
    assert "par : Jérôme Garcin" in fiche["description"]
    assert fiche["date"].startswith("2014-09-28")
    assert "_id" not in fiche
