"""Le thème clair/sombre de l'accueil et de la liste, dans Chromium.

Les deux pages sont servies hors ligne sur la même origine (``/`` et
``/liste``) : un choix fait sur l'une se retrouve sur l'autre, comme dans
l'appli. Sans choix, chaque page suit le thème du système.
"""

import json
import re
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap.page import construire_page


sync_api = pytest.importorskip("playwright.sync_api")

ORIGINE = "http://pap.test"
FIXTURES = Path(__file__).parent / "fixtures" / "liste"
CLAIR = (246, 245, 241)  # --fond de l'accueil en clair
SOMBRE = (20, 23, 28)  # --fond de l'accueil en sombre

# localStorage qui refuse tout accès, comme un navigateur sans stockage.
SANS_STOCKAGE = """
Object.defineProperty(window, "localStorage", {
  get() { throw new DOMException("refusé", "SecurityError"); }
});
"""


@pytest.fixture(scope="module")
def navigateur() -> Iterator[Any]:
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except sync_api.Error as err:
            pytest.skip(f"Chromium indisponible : {err}")
        yield nav
        nav.close()


@pytest.fixture(scope="module")
def pages() -> dict[str, str]:
    """Le HTML servi pour chaque chemin."""
    return {
        "/": files("lmelp_pap").joinpath("accueil.html").read_text(encoding="utf-8"),
        "/liste": construire_page(FIXTURES),
    }


def _contexte(navigateur: Any, pages: dict[str, str], sombre: bool = False) -> Any:
    contexte = navigateur.new_context(color_scheme="dark" if sombre else "light")
    donnees = {"emissions": [], "arbitrages": [], "maturite_active": False}

    def router(route: Any) -> None:
        chemin = "/" + route.request.url.split("/", 3)[-1].split("?")[0].split("#")[0]
        if chemin in pages:
            route.fulfill(body=pages[chemin], content_type="text/html; charset=utf-8")
        elif chemin == "/api/donnees":
            route.fulfill(body=json.dumps(donnees), content_type="application/json")
        else:
            route.abort()

    contexte.route("**/*", router)
    return contexte


def _ouvrir(contexte: Any, chemin: str) -> Any:
    page = contexte.new_page()
    erreurs: list[str] = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.erreurs = erreurs
    page.goto(ORIGINE + chemin)
    page.locator("#interrupteur-theme").wait_for()
    return page


def _fond(page: Any) -> tuple[int, ...]:
    couleur = page.evaluate("getComputedStyle(document.body).backgroundColor")
    return tuple(int(c) for c in re.findall(r"\d+", couleur)[:3])


def _sombre(page: Any) -> bool:
    return sum(_fond(page)) < 3 * 128


def _theme(page: Any) -> str | None:
    theme: str | None = page.evaluate("document.documentElement.dataset.theme ?? null")
    return theme


def _memorise(page: Any) -> str | None:
    valeur: str | None = page.evaluate("localStorage.getItem('pap.theme')")
    return valeur


@pytest.mark.parametrize("chemin", ["/", "/liste"])
def test_sans_choix_la_page_suit_le_systeme_meme_quand_il_change(
    navigateur: Any, pages: dict[str, str], chemin: str
) -> None:
    contexte = _contexte(navigateur, pages)
    page = _ouvrir(contexte, chemin)

    assert _theme(page) is None
    assert not _sombre(page)
    page.emulate_media(color_scheme="dark")
    assert _sombre(page)
    page.emulate_media(color_scheme="light")
    assert not _sombre(page)
    contexte.close()


@pytest.mark.parametrize("chemin", ["/", "/liste"])
def test_l_interrupteur_passe_de_auto_a_clair_a_sombre_puis_auto(
    navigateur: Any, pages: dict[str, str], chemin: str
) -> None:
    contexte = _contexte(navigateur, pages, sombre=True)
    page = _ouvrir(contexte, chemin)
    bouton = page.locator("#interrupteur-theme")

    vus = []
    for _ in range(4):
        vus.append((_theme(page), _memorise(page), _sombre(page), bouton.inner_text()))
        assert "Thème" in (bouton.get_attribute("title") or "")
        bouton.click()

    assert vus == [
        (None, None, True, "◐"),
        ("light", "light", False, "☀"),
        ("dark", "dark", True, "☾"),
        (None, None, True, "◐"),
    ]
    assert page.erreurs == []
    contexte.close()


def test_le_title_de_l_interrupteur_dit_l_etat_et_la_suite(
    navigateur: Any, pages: dict[str, str]
) -> None:
    contexte = _contexte(navigateur, pages)
    page = _ouvrir(contexte, "/")
    bouton = page.locator("#interrupteur-theme")

    titres = []
    for _ in range(3):
        titres.append(bouton.get_attribute("title"))
        assert bouton.get_attribute("aria-label") == titres[-1]
        bouton.click()

    assert titres == [
        "Thème automatique (suit le système). Cliquer pour passer en clair.",
        "Thème clair. Cliquer pour passer en sombre.",
        "Thème sombre. Cliquer pour passer en automatique.",
    ]
    contexte.close()


def test_un_choix_fait_sur_l_accueil_vaut_pour_la_liste_et_survit_au_rechargement(
    navigateur: Any, pages: dict[str, str]
) -> None:
    contexte = _contexte(navigateur, pages)
    accueil = _ouvrir(contexte, "/")
    accueil.locator("#interrupteur-theme").click()  # clair
    accueil.locator("#interrupteur-theme").click()  # sombre

    liste = _ouvrir(contexte, "/liste")
    assert _theme(liste) == "dark"
    assert _sombre(liste)
    assert liste.locator("#interrupteur-theme").inner_text() == "☾"

    accueil.reload()
    accueil.locator("#interrupteur-theme").wait_for()
    assert _theme(accueil) == "dark"
    assert _sombre(accueil)
    contexte.close()


def test_un_choix_fait_sur_une_page_s_applique_a_l_autre_deja_ouverte(
    navigateur: Any, pages: dict[str, str]
) -> None:
    contexte = _contexte(navigateur, pages)
    accueil = _ouvrir(contexte, "/")
    liste = _ouvrir(contexte, "/liste")

    liste.locator("#interrupteur-theme").click()  # clair
    liste.locator("#interrupteur-theme").click()  # sombre

    accueil.wait_for_function("document.documentElement.dataset.theme === 'dark'")
    assert accueil.locator("#interrupteur-theme").inner_text() == "☾"
    contexte.close()


@pytest.mark.parametrize("chemin", ["/", "/liste"])
def test_le_theme_force_est_pose_avant_le_premier_rendu(
    navigateur: Any, pages: dict[str, str], chemin: str
) -> None:
    contexte = _contexte(navigateur, pages)
    contexte.add_init_script("localStorage.setItem('pap.theme', 'dark')")
    # Relevé au premier élément du <body> : avant tout rendu de la page.
    contexte.add_init_script(
        """new MutationObserver((_, obs) => {
             if (document.body) {
               window.themeAuPremierRendu = document.documentElement.dataset.theme;
               obs.disconnect();
             }
           }).observe(document, {childList: true, subtree: true});"""
    )
    page = _ouvrir(contexte, chemin)

    assert page.evaluate("window.themeAuPremierRendu") == "dark"
    contexte.close()


@pytest.mark.parametrize("chemin", ["/", "/liste"])
def test_sans_stockage_la_page_reste_en_auto_et_l_interrupteur_marche(
    navigateur: Any, pages: dict[str, str], chemin: str
) -> None:
    contexte = _contexte(navigateur, pages, sombre=True)
    contexte.add_init_script(SANS_STOCKAGE)
    page = _ouvrir(contexte, chemin)

    assert _theme(page) is None
    assert _sombre(page)
    page.locator("#interrupteur-theme").click()
    assert _theme(page) == "light"
    assert not _sombre(page)
    assert page.erreurs == []
    contexte.close()


def test_une_valeur_memorisee_inconnue_laisse_la_page_en_auto(
    navigateur: Any, pages: dict[str, str]
) -> None:
    contexte = _contexte(navigateur, pages, sombre=True)
    contexte.add_init_script("localStorage.setItem('pap.theme', 'violet')")
    page = _ouvrir(contexte, "/")

    assert _theme(page) is None
    assert page.locator("#interrupteur-theme").inner_text() == "◐"
    contexte.close()


def test_la_page_de_la_liste_ouverte_sans_serveur_a_son_interrupteur(
    navigateur: Any, tmp_path: Path
) -> None:
    fichier = tmp_path / "emissions.html"
    fichier.write_text(construire_page(FIXTURES), encoding="utf-8")
    page = navigateur.new_page(color_scheme="light")
    erreurs: list[str] = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.goto(fichier.as_uri())

    page.locator("#interrupteur-theme").click()
    page.locator("#interrupteur-theme").click()
    assert _theme(page) == "dark"
    assert _sombre(page)
    assert erreurs == []
    page.close()


def _contraste(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    def lum(c: tuple[int, ...]) -> float:
        v = [x / 255 for x in c]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]

    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _rgb(hexa: str) -> tuple[int, ...]:
    hexa = hexa.strip().lstrip("#")
    return tuple(int(hexa[i : i + 2], 16) for i in (0, 2, 4))


def test_en_sombre_les_couleurs_d_etat_de_l_accueil_se_lisent_sur_les_cartes(
    navigateur: Any, pages: dict[str, str]
) -> None:
    contexte = _contexte(navigateur, pages, sombre=True)
    page = _ouvrir(contexte, "/")
    variables = page.evaluate(
        """() => {
             const s = getComputedStyle(document.documentElement);
             return Object.fromEntries(["carte", "fond", "sans", "localise",
               "telechargeable", "rapatrie", "qualifie", "valide", "lmelp"]
               .map(n => [n, s.getPropertyValue("--" + n)]));
           }"""
    )
    carte = _rgb(variables.pop("carte"))
    assert carte != (255, 255, 255)

    faibles = {
        n: round(_contraste(_rgb(v), carte), 2)
        for n, v in variables.items()
        if n != "fond" and _contraste(_rgb(v), carte) < 4.5
    }
    assert faibles == {}
    contexte.close()
