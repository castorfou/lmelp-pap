"""La diffusion Radio France d'une émission, au seam de l'API HTTP de l'appli.

Le serveur tourne sur un port libre avec une session factice : l'Open API
Radio France n'est jamais appelée.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.test_arbitrer_maturite import _demarrer
from tests.test_radiofrance_api import (
    MASQUE_API,
    ReponseGraphQL,
    SessionApi,
    _noeud,
    _page,
    _personne,
)


PAGE_2024 = f"{MASQUE_API}/le-masque-et-la-plume-du-dimanche-11-fevrier-2024-2491269"


@pytest.fixture(autouse=True)
def _sans_base_lmelp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.delenv("RADIOFRANCE_API_TOKEN", raising=False)


@pytest.fixture
def cle(monkeypatch: pytest.MonkeyPatch) -> None:
    """La clé de l'Open API Radio France, lue dans l'environnement."""
    monkeypatch.setenv("RADIOFRANCE_API_TOKEN", "cle")


def _get(url: str) -> Any:
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def _serveur(tmp_path: Path, **options: Any) -> Iterator[str]:
    yield from _demarrer(tmp_path, **options)


@pytest.mark.usefixtures("cle")
def test_la_diffusion_trouvee_donne_equipe_et_invites_et_le_journal(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    noeud = _noeud(
        PAGE_2024,
        personnalites=[
            _personne("Jérôme Garcin", "staff", "Producteur"),
            _personne("Une Autrice", "guest"),
        ],
    )
    session = SessionApi(_page(noeud))
    for url in _serveur(tmp_path, session=session):
        reponse = _get(f"{url}/api/radiofrance/2024-02-11")

    assert reponse == {
        "emission_id": "2024-02-11",
        "statut": "trouvee",
        "diffusion": {
            "titre": "Aliène",
            "resume": "Le résumé de la diffusion.",
            "url": PAGE_2024,
            "animateurs": [],
            "equipe": [{"nom": "Jérôme Garcin", "role": "Producteur"}],
            "invites": [{"nom": "Une Autrice", "role": None}],
        },
    }
    # la diffusion est cherchée le jour de l'émission
    assert session.demandes[0]["json"]["variables"]["start"] == 1707606000
    logs = capfd.readouterr().err
    assert "api radiofrance 2024-02-11 : trouvée" in logs
    # rien du contenu de la réponse dans les logs
    assert "Garcin" not in logs
    assert "Aliène" not in logs


@pytest.mark.usefixtures("cle")
def test_sans_diffusion_du_masque_ce_jour_la(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    session = SessionApi(_page())
    for url in _serveur(tmp_path, session=session):
        reponse = _get(f"{url}/api/radiofrance/2024-02-11")

    assert reponse["statut"] == "introuvable"
    assert reponse["diffusion"] is None
    assert "api radiofrance 2024-02-11 : introuvable" in capfd.readouterr().err


def test_sans_cle_l_api_n_est_pas_appelee(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    session = SessionApi()
    for url in _serveur(tmp_path, session=session):
        reponse = _get(f"{url}/api/radiofrance/2024-02-11")

    assert reponse["statut"] == "sans_cle"
    assert session.demandes == []
    assert "api radiofrance 2024-02-11 : pas de clé" in capfd.readouterr().err


@pytest.mark.usefixtures("cle")
def test_une_erreur_de_l_api_est_rapportee_et_journalisee(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    session = SessionApi(ReponseGraphQL(403, {"message": "Unauthorized"}))
    for url in _serveur(tmp_path, session=session):
        reponse = _get(f"{url}/api/radiofrance/2024-02-11")

    assert reponse["statut"] == "erreur"
    assert reponse["detail"] == "HTTP 403"
    logs = capfd.readouterr().err
    assert "api radiofrance 2024-02-11 : erreur HTTP 403" in logs
    assert "Unauthorized" not in logs


@pytest.mark.usefixtures("cle")
def test_une_emission_inconnue_repond_404(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    for url in _serveur(tmp_path, session=SessionApi()):
        with pytest.raises(urllib.error.HTTPError) as erreur:
            _get(f"{url}/api/radiofrance/1900-01-01")
    assert erreur.value.code == 404
    assert "api radiofrance 1900-01-01 : émission inconnue" in capfd.readouterr().err
