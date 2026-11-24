"""Le bandeau commun à l'accueil et à la liste de l'appli, dans Chromium.

Les deux pages ont le même bandeau : « pap », le sous-titre, les onglets
« Accueil » et « Liste et arbitrages » (la page courante marquée) et
l'interrupteur de thème. « Collecte » reste propre à l'accueil ; la page
publiée de la liste n'a pas de bandeau.
"""

import json
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap.page import construire_page, donnees_page


sync_api = pytest.importorskip("playwright.sync_api")

ORIGINE = "http://pap.test"
FIXTURES = Path(__file__).parent / "fixtures" / "liste"


@pytest.fixture(scope="module")
def navigateur() -> Iterator[Any]:
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except sync_api.Error as err:
            pytest.skip(f"Chromium indisponible : {err}")
        yield nav
        nav.close()


@pytest.fixture
def contexte(navigateur: Any) -> Iterator[Any]:
    pages = {
        "/": files("lmelp_pap").joinpath("accueil.html").read_text(encoding="utf-8"),
        "/liste": construire_page(FIXTURES, arbitrage=True),
        "/publiee": construire_page(FIXTURES),
    }
    donnees = {"emissions": donnees_page(FIXTURES), "arbitrages": []}
    contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})

    def router(route: Any) -> None:
        chemin = "/" + route.request.url.split("/", 3)[-1].split("?")[0].split("#")[0]
        if chemin in pages:
            route.fulfill(body=pages[chemin], content_type="text/html; charset=utf-8")
        elif chemin == "/api/donnees":
            route.fulfill(body=json.dumps(donnees), content_type="application/json")
        elif chemin.startswith("/api/"):
            route.fulfill(body="{}", content_type="application/json")
        else:
            route.abort()

    contexte.route("**/*", router)
    yield contexte
    contexte.close()


def _ouvrir(contexte: Any, chemin: str) -> Any:
    page = contexte.new_page()
    erreurs: list[str] = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.erreurs = erreurs
    page.goto(ORIGINE + chemin)
    page.locator("#interrupteur-theme").wait_for()
    return page


def _onglets(page: Any) -> list[tuple[str, str, str | None]]:
    """(texte, href, aria-current) de chaque onglet du bandeau."""
    onglets: list[tuple[str, str, str | None]] = page.eval_on_selector_all(
        "header.app nav a",
        "liens => liens.map(a => [a.textContent, a.getAttribute('href'),"
        " a.getAttribute('aria-current')])",
    )
    return [tuple(o) for o in onglets]  # type: ignore[misc]


def test_l_accueil_et_la_liste_ont_les_memes_onglets_la_page_courante_marquee(
    contexte: Any,
) -> None:
    accueil = _ouvrir(contexte, "/")
    liste = _ouvrir(contexte, "/liste")

    assert _onglets(accueil) == [
        ("Accueil", "/", "page"),
        ("Liste et arbitrages", "/liste", None),
    ]
    assert _onglets(liste) == [
        ("Accueil", "/", None),
        ("Liste et arbitrages", "/liste", "page"),
    ]
    for page in (accueil, liste):
        bandeau = page.locator("header.app")
        assert bandeau.locator(".logo").inner_text() == "pap"
        assert bandeau.locator(".logo").get_attribute("href") == "/"
        assert "Le Masque & la Plume, archivage patrimonial" in bandeau.inner_text()
        assert bandeau.locator("#interrupteur-theme").count() == 1
        dernier = page.evaluate(
            "document.querySelector('header.app').lastElementChild.id"
        )
        assert dernier == "interrupteur-theme"
        assert page.erreurs == []


def test_les_bandeaux_des_deux_pages_ont_la_meme_allure(contexte: Any) -> None:
    styles = []
    for chemin in ("/", "/liste"):
        page = _ouvrir(contexte, chemin)
        styles.append(
            page.evaluate(
                """() => {
                     const b = document.querySelector("header.app");
                     const s = getComputedStyle(b), r = b.getBoundingClientRect();
                     return [s.backgroundColor, s.fontFamily, s.fontSize,
                             Math.round(r.left), Math.round(r.top),
                             Math.round(r.width), Math.round(r.height)];
                   }"""
            )
        )
    assert styles[0] == styles[1]
    # Le bandeau occupe toute la largeur, en haut de la page.
    assert styles[0][3:6] == [0, 0, 1280]


def test_collecte_reste_propre_a_l_accueil(contexte: Any) -> None:
    accueil = _ouvrir(contexte, "/")
    liste = _ouvrir(contexte, "/liste")

    assert accueil.locator("header.app #collecter").count() == 1
    assert liste.locator("#collecter").count() == 0
    assert liste.locator("header.app .actions").count() == 0


def test_collecte_et_publier_sont_des_actions_de_l_accueil_a_part_des_onglets(
    contexte: Any,
) -> None:
    accueil = _ouvrir(contexte, "/")
    actions = accueil.locator("header.app .actions")

    assert actions.get_attribute("aria-label") == "Actions de l'accueil"
    ids = actions.evaluate("g => [...g.children].map(e => e.id)")
    assert ids == ["collecter", "publier"]
    assert accueil.locator("header.app nav button").count() == 0
    # Séparées des onglets par un trait vertical.
    trait = actions.evaluate("g => getComputedStyle(g).borderLeftWidth")
    assert trait == "1px"


def test_les_onglets_menent_d_une_page_a_l_autre(contexte: Any) -> None:
    page = _ouvrir(contexte, "/")

    page.locator("header.app nav").get_by_role(
        "link", name="Liste et arbitrages"
    ).click()
    page.wait_for_url(ORIGINE + "/liste")
    page.locator("header.app nav").get_by_role("link", name="Accueil").click()
    page.wait_for_url(ORIGINE + "/")
    page.locator(".compteur").first.wait_for()


def test_la_liste_n_a_plus_qu_un_lien_vers_l_accueil_celui_du_bandeau(
    contexte: Any,
) -> None:
    liste = _ouvrir(contexte, "/liste")

    assert liste.get_by_role("link", name="← Accueil").count() == 0
    assert liste.locator("#interrupteur-theme").count() == 1


def test_la_page_publiee_n_a_pas_de_bandeau(contexte: Any) -> None:
    publiee = _ouvrir(contexte, "/publiee")

    assert publiee.locator("header.app").count() == 0
    assert publiee.locator("header .tete #interrupteur-theme").count() == 1
