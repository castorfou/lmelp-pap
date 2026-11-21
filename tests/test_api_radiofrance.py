"""La lecture d'une diffusion dans l'Open API Radio France, sans réseau.

Une session factice répond aux requêtes GraphQL ; rien n'atteint l'API.
"""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import requests

from lmelp_pap.api_radiofrance import (
    ApiRadioFranceError,
    Diffusion,
    Personnalite,
    lire_diffusion,
)


MASQUE = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume"
PAGE = f"{MASQUE}/aliene-7557327"
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
    url: str, show: str = MASQUE, personnalites: list[Any] | None = None
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
    autre = _noeud("https://www.radiofrance.fr/franceinter/podcasts/le-7-9/x-1", "")
    voulue = _noeud(
        PAGE,
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
        url=PAGE,
        equipe=(
            Personnalite("Jérôme Garcin", "Producteur"),
            Personnalite("Arnaud Viviant", None),
        ),
        invites=(Personnalite("Une Autrice", None),),
    )


def test_la_requete_porte_la_cle_et_le_jour_a_l_heure_de_paris() -> None:
    session = SessionApi(_page(_noeud(PAGE)))

    lire_diffusion(JOUR, [PAGE], "cle", session)

    demande = session.demandes[0]
    assert demande["url"] == "https://openapi.radiofrance.fr/v1/graphql"
    assert demande["headers"]["X-Token"] == "cle"
    debut = int(datetime(2024, 3, 24, tzinfo=ZoneInfo("Europe/Paris")).timestamp())
    variables = demande["json"]["variables"]
    assert variables["start"] == debut
    assert variables["end"] == debut + 86399
    assert "diffusions(" in demande["json"]["query"]
    assert demande["timeout"]


def test_sans_page_connue_prend_la_diffusion_du_masque_du_jour() -> None:
    autre = _noeud("https://www.radiofrance.fr/franceinter/podcasts/le-7-9/x-1", "")
    session = SessionApi(_page(autre, _noeud(f"{MASQUE}/autre-2")))

    diffusion = lire_diffusion(JOUR, [], "cle", session)

    assert diffusion is not None
    assert diffusion.url == f"{MASQUE}/autre-2"


def test_aucune_diffusion_du_masque_ce_jour_la() -> None:
    autre = _noeud("https://www.radiofrance.fr/franceinter/podcasts/le-7-9/x-1", "")
    session = SessionApi(_page(autre))

    assert lire_diffusion(JOUR, [PAGE], "cle", session) is None


def test_une_page_pleine_fait_lire_la_suivante() -> None:
    pleine = [
        _noeud(f"https://www.radiofrance.fr/franceinter/podcasts/x/y-{i}", "")
        for i in range(100)
    ]
    session = SessionApi(_page(*pleine), _page(_noeud(PAGE)))

    diffusion = lire_diffusion(JOUR, [PAGE], "cle", session)

    assert diffusion is not None and diffusion.url == PAGE
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
