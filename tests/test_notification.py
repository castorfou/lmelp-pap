"""Les notifications ntfy de l'appli (``lmelp_pap.notification``)."""

import json
import urllib.error
import urllib.request

import pytest

from lmelp_pap.notification import notifier
from tests.test_logs import messages


class Envoi:
    """Un faux ``urlopen`` : garde les requêtes, ou lève ``erreur``."""

    def __init__(self, erreur: Exception | None = None):
        self.requetes: list[urllib.request.Request] = []
        self.erreur = erreur

    def __call__(self, requete: urllib.request.Request, timeout: float) -> object:
        self.requetes.append(requete)
        if self.erreur:
            raise self.erreur
        return object()


def test_sans_topic_aucune_notification_et_une_ligne_de_log(
    capfd: pytest.CaptureFixture[str],
) -> None:
    envoi = Envoi()

    assert notifier("liste publiée", "ok", env={}, envoyer=envoi) is False

    assert envoi.requetes == []
    assert any(
        "NTFY_TOPIC" in m for m in messages(capfd.readouterr().err, "notification")
    )


def test_publie_le_json_ntfy_avec_le_titre_prefixe_pap(
    capfd: pytest.CaptureFixture[str],
) -> None:
    envoi = Envoi()
    env = {"NTFY_TOPIC": "lmelp", "NTFY_TOKEN": "tk_1"}

    ok = notifier(
        "liste publiée",
        "3 arbitrages",
        priorite=4,
        tags=["books"],
        env=env,
        envoyer=envoi,
    )

    assert ok is True
    (requete,) = envoi.requetes
    assert requete.full_url == "https://ntfy.sh"
    assert requete.get_header("Authorization") == "Bearer tk_1"
    assert json.loads(requete.data) == {  # type: ignore[arg-type]
        "topic": "lmelp",
        "title": "pap - liste publiée",
        "message": "3 arbitrages",
        "priority": 4,
        "tags": ["books"],
    }
    assert "notification ntfy envoyée : pap - liste publiée" in messages(
        capfd.readouterr().err, "notification"
    )


def test_le_serveur_ntfy_se_configure() -> None:
    envoi = Envoi()
    env = {"NTFY_TOPIC": "lmelp", "NTFY_SERVER_URL": "http://ntfy.local:8080/"}

    notifier("t", "m", env=env, envoyer=envoi)

    assert envoi.requetes[0].full_url == "http://ntfy.local:8080"


def test_une_erreur_reseau_ne_leve_pas_et_laisse_un_avertissement(
    capfd: pytest.CaptureFixture[str],
) -> None:
    envoi = Envoi(urllib.error.URLError("hors ligne"))

    assert notifier("t", "m", env={"NTFY_TOPIC": "x"}, envoyer=envoi) is False

    assert any(
        "non envoyée" in m and "hors ligne" in m
        for m in messages(capfd.readouterr().err, "notification")
    )
