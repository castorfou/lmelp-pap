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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import mongomock
import pytest

from lmelp_pap.arbitrer import creer_serveur
from lmelp_pap.maturite import Depot
from tests.test_commande import _cache_rempli
from tests.test_maturite import SON, Flux, Reponse, Session


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
    session = SessionComplete(
        {
            INTEGRAL_2014: Reponse(200, "audio/mp4"),
            INTEGRAL_2017: Reponse(404),
            INTEGRAL_2024: Reponse(200, "audio/mp4"),
        }
    )
    for adresse in _demarrer(
        tmp_path, depot=depot, session=session, audios=tmp_path / "audios"
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
    assert "2 ok, 1 mortes, 0 échecs passagers" in logs


def test_une_verification_manuelle_est_tracee(
    url: str, capfd: pytest.CaptureFixture[str]
) -> None:
    _post(f"{url}/api/verifications")
    _attendre_fin(url)
    time.sleep(0.1)
    logs = capfd.readouterr().err
    assert "vérification manuelle (complète) : 3 URL" in logs
    assert "vérification terminée" in logs
