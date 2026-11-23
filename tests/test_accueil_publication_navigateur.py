"""Le bouton « Publier » de l'accueil, dans un vrai navigateur (Playwright),
avec l'API de publication simulée."""

from typing import Any

import pytest


pytest.importorskip("playwright.sync_api")

from tests.test_accueil_navigateur import _ouvrir, navigateur  # noqa: F401


def _publier(
    nav: Any, apercu: dict[str, Any], resultat: dict[str, Any]
) -> tuple[Any, list[str]]:
    """L'accueil avec ``/api/publication`` simulée ; rend la page et les
    méthodes reçues."""
    recues: list[str] = []

    def publication(requete: Any) -> dict[str, Any]:
        recues.append(requete.method)
        return apercu if requete.method == "GET" else resultat

    page = _ouvrir(nav, api={"/api/publication": publication})
    return page, recues


def test_publier_montre_le_resume_puis_publie_apres_confirmation(
    navigateur: Any,  # noqa: F811
) -> None:
    page, recues = _publier(
        navigateur,
        {"a_publier": True, "resume": "2 arbitrages ajoutés"},
        {"statut": "publiee", "commit": "abc1234", "resume": "2 arbitrages"},
    )

    page.get_by_role("button", name="Publier", exact=True).click()
    boite = page.locator("#boite")
    boite.get_by_text("2 arbitrages ajoutés").wait_for()
    assert recues == ["GET"]
    boite.get_by_role("button", name="Publier sur GitHub").click()

    page.locator("#toast", has_text="abc1234").wait_for()
    assert recues == ["GET", "POST"]


def test_publier_sans_changement_ne_publie_pas(
    navigateur: Any,  # noqa: F811
) -> None:
    page, recues = _publier(
        navigateur, {"a_publier": False, "resume": "aucun changement"}, {}
    )

    page.get_by_role("button", name="Publier", exact=True).click()

    page.locator("#toast", has_text="Rien à publier").wait_for()
    assert recues == ["GET"]


def test_une_publication_refusee_montre_pourquoi(
    navigateur: Any,  # noqa: F811
) -> None:
    page, _ = _publier(
        navigateur,
        {"a_publier": True, "resume": "1 arbitrage ajouté"},
        {"statut": "refusee", "detail": "conflit au rebase sur main : arbitrages.csv"},
    )

    page.get_by_role("button", name="Publier", exact=True).click()
    page.locator("#boite").get_by_role("button", name="Publier sur GitHub").click()

    page.locator("#boite", has_text="conflit au rebase").wait_for()
