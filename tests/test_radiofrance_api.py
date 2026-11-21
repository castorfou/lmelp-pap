"""La lecture d'une diffusion dans l'Open API Radio France, sans réseau.

Une session factice répond aux requêtes GraphQL ; rien n'atteint l'API.
"""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import requests

from lmelp_pap.radiofrance_api import (
    ApiRadioFranceError,
    Diffusion,
    LecteurDiffusions,
    Personnalite,
    jeton,
    lire_diffusion,
)


# Les pages connues de pap sont sous www.radiofrance.fr ; l'API rend les
# mêmes chemins sous www.franceinter.fr.
MASQUE = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume"
MASQUE_API = "https://www.franceinter.fr/franceinter/podcasts/le-masque-et-la-plume"
AUTRE_API = "https://www.franceinter.fr/franceinter/podcasts/le-7-9"
PAGE = f"{MASQUE}/aliene-7557327"
PAGE_API = f"{MASQUE_API}/aliene-7557327"
JOUR = date(2024, 3, 24)


class ReponseGraphQL:
    def __init__(self, statut: int, corps: Any):
        self.status_code = statut
        self._corps = corps

    def json(self) -> Any:
        return self._corps


class SessionApi:
    """Rend, requête après requête, les réponses données (ou les lève)."""

    def __init__(self, *reponses: Any):
        self.reponses = list(reponses)
        self.demandes: list[dict[str, Any]] = []

    def post(self, url: str, **options: Any) -> Any:
        self.demandes.append({"url": url, **options})
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def _noeud(
    url: str, show: str = MASQUE_API, personnalites: list[Any] | None = None
) -> dict[str, Any]:
    return {
        "id": url.rsplit("-", 1)[-1],
        "title": "Aliène",
        "standFirst": "Le résumé de la diffusion.",
        "url": url,
        "published_date": "1711306800",
        "show": {"id": "6eac4a84", "url": show},
        "personalitiesConnection": {"edges": personnalites or []},
    }


def _personne(nom: str, relation: str, info: str | None = None) -> dict[str, Any]:
    return {"relation": relation, "info": info, "node": {"id": nom, "name": nom}}


def _page(*noeuds: dict[str, Any]) -> ReponseGraphQL:
    edges = [{"cursor": f"c{i}", "node": n} for i, n in enumerate(noeuds)]
    return ReponseGraphQL(200, {"data": {"diffusions": {"edges": edges}}})


def test_trouve_la_diffusion_par_l_url_de_sa_page() -> None:
    autre = _noeud(f"{AUTRE_API}/x-1", f"{AUTRE_API}/")
    voulue = _noeud(
        PAGE_API,
        personnalites=[
            _personne("Jérôme Garcin", "staff", "Producteur"),
            _personne("Arnaud Viviant", "producer"),
            _personne("Une Autrice", "guest"),
            _personne("roman", "tag"),
        ],
    )
    session = SessionApi(_page(autre, voulue))

    diffusion = lire_diffusion(JOUR, [PAGE], "cle", session)

    assert diffusion == Diffusion(
        titre="Aliène",
        resume="Le résumé de la diffusion.",
        url=PAGE_API,
        animateurs=(Personnalite("Arnaud Viviant", None),),
        equipe=(Personnalite("Jérôme Garcin", "Producteur"),),
        invites=(Personnalite("Une Autrice", None),),
    )


def test_la_requete_porte_la_cle_et_le_jour_a_l_heure_de_paris() -> None:
    session = SessionApi(_page(_noeud(PAGE_API)))

    lire_diffusion(JOUR, [PAGE], "cle", session)

    demande = session.demandes[0]
    assert demande["url"] == "https://openapi.radiofrance.fr/v1/graphql"
    assert demande["headers"]["x-token"] == "cle"
    debut = int(datetime(2024, 3, 24, tzinfo=ZoneInfo("Europe/Paris")).timestamp())
    variables = demande["json"]["variables"]
    assert variables["start"] == debut
    assert variables["end"] == debut + 86399
    assert "diffusions(" in demande["json"]["query"]
    assert demande["timeout"]


def test_sans_page_connue_prend_la_diffusion_du_masque_du_jour() -> None:
    autre = _noeud(f"{AUTRE_API}/x-1", f"{AUTRE_API}/")
    session = SessionApi(_page(autre, _noeud(f"{MASQUE_API}/autre-2")))

    diffusion = lire_diffusion(JOUR, [], "cle", session)

    assert diffusion is not None
    assert diffusion.url == f"{MASQUE_API}/autre-2"


def test_la_page_connue_l_emporte_sur_une_autre_diffusion_du_masque() -> None:
    # le même jour, un extrait (podcast d'un livre) précède l'émission entière
    extrait = _noeud(f"{MASQUE_API}/le-fondateur-1")
    session = SessionApi(_page(extrait, _noeud(PAGE_API)))

    diffusion = lire_diffusion(JOUR, [PAGE], "cle", session)

    assert diffusion is not None and diffusion.url == PAGE_API


def test_aucune_diffusion_du_masque_ce_jour_la() -> None:
    autre = _noeud(f"{AUTRE_API}/x-1", f"{AUTRE_API}/")
    session = SessionApi(_page(autre))

    assert lire_diffusion(JOUR, [PAGE], "cle", session) is None


def test_une_page_pleine_fait_lire_la_suivante() -> None:
    pleine = [_noeud(f"{AUTRE_API}/y-{i}", f"{AUTRE_API}/") for i in range(100)]
    session = SessionApi(_page(*pleine), _page(_noeud(PAGE_API)))

    diffusion = lire_diffusion(JOUR, [PAGE], "cle", session)

    assert diffusion is not None and diffusion.url == PAGE_API
    assert session.demandes[1]["json"]["variables"]["after"] == "c99"


@pytest.mark.parametrize(
    ("reponse", "detail"),
    [
        (ReponseGraphQL(403, {"message": "Unauthorized"}), "HTTP 403"),
        (ReponseGraphQL(400, {"errors": [{"message": "x"}]}), "HTTP 400"),
        (ReponseGraphQL(200, {"errors": [{"message": "x"}], "data": None}), "GraphQL"),
        (requests.Timeout("trop long"), "Timeout"),
        (requests.ConnectionError("hors ligne"), "ConnectionError"),
    ],
)
def test_une_erreur_de_l_api_ne_rapporte_que_sa_nature(
    reponse: Any, detail: str
) -> None:
    with pytest.raises(ApiRadioFranceError) as erreur:
        lire_diffusion(JOUR, [PAGE], "cle", SessionApi(reponse))
    assert detail in str(erreur.value)
    assert "Unauthorized" not in str(erreur.value)


class Horloge:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_le_lecteur_garde_la_diffusion_en_memoire_une_heure() -> None:
    horloge = Horloge()
    session = SessionApi(_page(_noeud(PAGE_API)), _page(_noeud(PAGE_API)))
    lecteur = LecteurDiffusions(session, horloge=horloge)

    premiere = lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")
    horloge.t += 3599
    seconde = lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")
    horloge.t += 2
    troisieme = lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")

    assert premiere.diffusion == seconde.diffusion
    assert premiere.diffusion is not None
    assert (premiere.cache, seconde.cache, troisieme.cache) == (False, True, False)
    assert len(session.demandes) == 2


def test_le_lecteur_ne_garde_pas_une_erreur() -> None:
    session = SessionApi(ReponseGraphQL(500, {}), _page(_noeud(PAGE_API)))
    lecteur = LecteurDiffusions(session)

    with pytest.raises(ApiRadioFranceError):
        lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")
    lecture = lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")

    assert lecture.diffusion is not None and lecture.cache is False


def test_la_cle_se_lit_dans_l_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADIOFRANCE_API_TOKEN", "cle")
    assert jeton() == "cle"
    monkeypatch.setenv("RADIOFRANCE_API_TOKEN", "")
    assert jeton() is None


class Jour:
    def __init__(self) -> None:
        self.jour = date(2026, 11, 21)

    def __call__(self) -> date:
        return self.jour


def test_le_lecteur_compte_les_requetes_du_jour() -> None:
    pleine = [_noeud(f"{AUTRE_API}/y-{i}", f"{AUTRE_API}/") for i in range(100)]
    session = SessionApi(
        _page(*pleine),
        _page(_noeud(PAGE_API)),
        ReponseGraphQL(403, {}),
        _page(_noeud(PAGE_API)),
    )
    jour = Jour()
    lecteur = LecteurDiffusions(session, aujourdhui=jour)

    deux_pages = lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")
    du_cache = lecteur.lire("2024-03-24", JOUR, [PAGE], "cle")
    with pytest.raises(ApiRadioFranceError) as erreur:
        lecteur.lire("2024-03-31", JOUR, [PAGE], "cle")
    jour.jour = date(2026, 11, 22)  # minuit, heure de Paris : on repart de zéro
    lendemain = lecteur.lire("2024-04-07", JOUR, [PAGE], "cle")

    assert (deux_pages.requetes, deux_pages.du_jour) == (2, 2)
    assert (du_cache.requetes, du_cache.du_jour) == (0, 2)
    assert (erreur.value.requetes, erreur.value.du_jour) == (1, 3)
    assert (lendemain.requetes, lendemain.du_jour) == (1, 1)
