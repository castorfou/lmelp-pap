"""L'accueil de l'appli pap dans un vrai navigateur (Playwright).

La page est servie hors ligne avec des données simulées pour ``/api/donnees`` :
des émissions de 1955 à 2026, réparties entre les états.
"""

import json
from collections import Counter
from collections.abc import Iterator
from importlib.resources import files
from typing import Any

import pytest


sync_api = pytest.importorskip("playwright.sync_api")

ADRESSE = "http://pap.test/"
ETATS = [
    "sans",
    "localise",
    "telechargeable",
    "rapatrie",
    "qualifie",
    "valide",
    "lmelp",
]


def _emission(jour: str, etat: str, depuis: str | None = None) -> dict[str, Any]:
    return {
        "id": jour,
        "date": jour,
        "titre": f"Émission du {jour}",
        "themes": ["livres"],
        "animateur": "",
        "attestations": [{"source": "lmelp" if etat == "lmelp" else "ina"}],
        "maturite": None if etat in ("sans", "lmelp") else etat,
        "maturite_depuis": depuis,
    }


def _donnees() -> dict[str, Any]:
    """Quatre émissions par an de 1955 à 2026 ; en 1987, une par état
    localisé, téléchargeable, sans enregistrement et rapatrié."""
    emissions = []
    for annee in range(1955, 2027):
        if annee == 1987:
            etats = ["localise", "telechargeable", "sans", "rapatrie"]
        elif annee < 1994:
            etats = ["localise"] * 3 + ["sans"]
        elif annee < 2006:
            etats = ["sans"] * 4
        elif annee < 2014:
            etats = ["telechargeable", "telechargeable", "qualifie", "valide"]
        else:
            etats = ["lmelp"] * 4
        for i, etat in enumerate(etats):
            jour = f"{annee}-{3 * i + 1:02d}-0{i + 1}"
            depuis = None if etat in ("sans", "lmelp") else f"2026-11-{10 + i}"
            emissions.append(_emission(jour, etat, depuis))
    return {"emissions": emissions, "arbitrages": [], "maturite_active": True}


def _comptes(donnees: dict[str, Any], annee: int | None = None) -> Counter[str]:
    comptes: Counter[str] = Counter()
    for e in donnees["emissions"]:
        if annee and not e["date"].startswith(str(annee)):
            continue
        lmelp = e["attestations"][0]["source"] == "lmelp"
        comptes["lmelp" if lmelp else e["maturite"] or "sans"] += 1
    return comptes


@pytest.fixture(scope="module")
def navigateur() -> Iterator[Any]:
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except sync_api.Error as err:
            pytest.skip(f"Chromium indisponible : {err}")
        yield nav
        nav.close()


def _ouvrir(
    navigateur: Any, donnees: dict[str, Any] | None = None, sombre: bool = False
) -> Any:
    page = navigateur.new_page(
        viewport={"width": 1280, "height": 1000},
        color_scheme="dark" if sombre else "light",
    )
    html = files("lmelp_pap").joinpath("accueil.html").read_text(encoding="utf-8")
    corps = json.dumps(donnees or _donnees())

    def router(route: Any) -> None:
        url = route.request.url
        if url.split("#")[0] == ADRESSE:
            route.fulfill(body=html, content_type="text/html; charset=utf-8")
        elif url.endswith("/api/donnees"):
            route.fulfill(body=corps, content_type="application/json")
        else:
            route.abort()

    page.route("**/*", router)
    page.goto(ADRESSE)
    page.locator(".compteur").first.wait_for()
    return page


def _compteurs(page: Any) -> dict[str, int]:
    return {
        c.get_attribute("data-etat"): int(c.locator(".n").inner_text())
        for c in page.locator(".compteur").all()
    }


def _survoler_annee(page: Any, annee: int) -> None:
    page.locator(f'#histo rect.zone[data-annee="{annee}"]').hover()


def test_les_compteurs_comptent_les_emissions_par_etat(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    attendus = _comptes(_donnees())
    assert _compteurs(page) == {e: attendus[e] for e in ETATS}


def test_aucun_role_n_apparait(navigateur: Any) -> None:
    texte = _ouvrir(navigateur).locator("body").inner_text()
    assert "Archéologue" not in texte
    assert "Exploitant" not in texte


def test_la_frise_defile_seule_sous_les_compteurs(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    frise = page.locator("#frise")
    assert frise.evaluate("f => f.scrollHeight > f.clientHeight")
    assert page.evaluate(
        "document.scrollingElement.scrollHeight"
        " <= document.scrollingElement.clientHeight + 1"
    )
    bas_compteurs = page.locator(".compteurs").bounding_box()
    haut_frise = frise.bounding_box()
    assert haut_frise["y"] >= bas_compteurs["y"] + bas_compteurs["height"] - 1
    assert haut_frise["y"] + haut_frise["height"] <= 1000


def test_survoler_une_annee_y_place_la_frise(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    _survoler_annee(page, 1987)
    premiere = page.locator("#frise").evaluate(
        "f => [...f.querySelectorAll('.annee')]"
        ".find(b => b.offsetTop >= f.scrollTop - 1).dataset.annee"
    )
    assert premiere == "1987"
    assert "1987" in page.locator("#lecture").inner_text()


def test_cliquer_une_annee_filtre_tout(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('#histo rect.zone[data-annee="1987"]').click()

    attendus = _comptes(_donnees(), 1987)
    assert _compteurs(page) == {e: attendus[e] for e in ETATS}
    assert page.locator("#frise .annee").count() == 1

    page.locator("#effacer-annee").click()
    assert page.locator("#frise .annee").count() == 2026 - 1955 + 1


def test_un_compteur_ouvre_la_page_de_son_etat_filtree_par_annee(
    navigateur: Any,
) -> None:
    page = _ouvrir(navigateur)
    page.locator('#histo rect.zone[data-annee="1987"]').click()
    page.locator('.compteur[data-etat="localise"]').click()

    assert "localisé" in page.locator("h2").first.inner_text()
    assert page.locator("tbody tr").count() == 1
    assert "etat=localise" in page.url


def test_les_colonnes_d_une_page_d_etat_se_trient(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="localise"]').click()
    entetes = page.locator("th.triable")
    noms = [t.rstrip(" ▲▼") for t in entetes.all_inner_texts()]
    assert noms == ["Date", "Titre", "Thèmes", "Sources", "Depuis"]

    def colonne(i: int) -> list[Any]:
        textes = page.locator(f"tbody tr td:nth-child({i + 1})").all_inner_texts()
        # l'ancienneté (« 11 j ») se compare en nombre de jours
        return [int(t.split()[0]) if t.endswith(" j") else t.lower() for t in textes]

    for i, nom in enumerate(noms):
        entetes.nth(i).click()
        premier_sens = colonne(i)
        assert premier_sens in (sorted(premier_sens), sorted(premier_sens)[::-1])
        entetes.nth(i).click()
        assert colonne(i) == premier_sens[::-1] or len(set(premier_sens)) == 1, nom
        assert entetes.nth(i).inner_text()[-1] in "▲▼"


def test_la_page_dans_lmelp_n_a_ni_sources_ni_anciennete(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="lmelp"]').click()
    entetes = [t.rstrip(" ▲▼") for t in page.locator("th").all_inner_texts()]
    assert entetes == ["Date", "Titre", "Thèmes"]


def test_sans_action_pas_de_colonne_action(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="telechargeable"]').click()
    entetes = [t.rstrip(" ▲▼") for t in page.locator("th").all_inner_texts()]
    assert "Action" not in entetes


def test_le_retour_a_l_accueil(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="localise"]').click()
    page.get_by_role("button", name="← Accueil").click()
    assert page.locator("#frise").count() == 1


def test_en_sombre_le_fond_est_sombre_et_les_etats_gardent_leur_couleur(
    navigateur: Any,
) -> None:
    clair = _ouvrir(navigateur)
    sombre = _ouvrir(navigateur, sombre=True)
    fond = sombre.evaluate("getComputedStyle(document.body).backgroundColor")
    assert sum(int(c) for c in fond[4:-1].split(",")[:3]) < 200

    def couleur(page: Any) -> str:
        return str(
            page.locator('.compteur[data-etat="localise"]').evaluate(
                "c => getComputedStyle(c).borderTopColor"
            )
        )

    assert couleur(sombre) == couleur(clair)
