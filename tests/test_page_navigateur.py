"""La page de la liste des émissions, ouverte dans un navigateur (Chromium).

Ces tests chargent la page générée par ``construire_page`` et l'utilisent comme
un lecteur : couleurs calculées, frise, filtres. Le mode arbitrage est servi
par une fausse API (``page.route``), sans lancer le serveur.
"""

import csv
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright import sync_api

from lmelp_pap.page import construire_page, donnees_page


ADRESSE = "http://pap.test/"

# Cinq émissions sur deux années : deux au thème livres, trois au thème inconnu.
EMISSIONS = [
    ("2015-01-04", "livres", "Le dernier Modiano", "lmelp;radiofrance", True),
    ("2015-01-11", "", "", "wayback_podcast", True),
    ("2015-01-18", "", "Littérature", "ina", False),
    ("2016-01-03", "livres", "Marguerite Duras", "ina", False),
    ("2016-01-10", "", "", "ina", False),
]


def _ecrire(chemin: Path, champs: list[str], lignes: list[dict[str, str]]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, champs)
        w.writeheader()
        w.writerows(lignes)


@pytest.fixture
def dossier(tmp_path: Path) -> Path:
    """Les CSV d'une petite liste d'émissions."""
    vide = dict.fromkeys(
        ["description", "animateur", "chaine", "heure", "duree", "arbitrage"], ""
    )
    _ecrire(
        tmp_path / "emissions.csv",
        ["id", "date", "themes", "titre", *vide, "justification_arbitrage"],
        [
            {"id": i, "date": i, "themes": t, "titre": ti, **vide}
            for i, t, ti, _, _ in EMISSIONS
        ],
    )
    _ecrire(
        tmp_path / "attestations.csv",
        ["emission_id", "source", "source_id", "date", "themes", "titre", "url"],
        [
            {"emission_id": i, "source": s, "source_id": f"{s}-{i}", "date": i}
            for i, _, _, sources, _ in EMISSIONS
            for s in sources.split(";")
        ],
    )
    _ecrire(
        tmp_path / "enregistrements.csv",
        ["emission_id", "url", "type", "sources", "duree"],
        [
            {"emission_id": i, "url": f"https://audio.test/{i}.mp3", "type": "intégral"}
            for i, _, _, _, enreg in EMISSIONS
            if enreg
        ],
    )
    _ecrire(
        tmp_path / "doutes.csv",
        COLONNES_DOUTES,
        [],
    )
    return tmp_path


COLONNES_DOUTES = [
    "type",
    "emission_id",
    "dans_la_liste",
    "source",
    "source_id",
    "detail",
    "a_ecouter",
]


def _renvoyer_a_l_ecoute(dossier: Path) -> None:
    """2015-01-11 renvoyée à l'écoute ; 2015-01-18 a un doute à trancher."""
    with (dossier / "emissions.csv").open(encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    for ligne in lignes:
        if ligne["id"] == "2015-01-11":
            ligne["arbitrage"] = "écoute"
    _ecrire(dossier / "emissions.csv", list(lignes[0]), lignes)
    _ecrire(
        dossier / "doutes.csv",
        COLONNES_DOUTES,
        [
            {
                "type": "thème inconnu",
                "emission_id": i,
                "dans_la_liste": "oui",
                "detail": "aucune source ne donne de thème",
                "a_ecouter": a_ecouter,
            }
            for i, a_ecouter in (("2015-01-11", "oui"), ("2015-01-18", "non"))
        ],
    )


@pytest.fixture(scope="module")
def navigateur() -> Iterator[sync_api.Browser]:
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except sync_api.Error as err:  # Chromium absent : playwright install
            pytest.skip(f"Chromium indisponible : {err}")
        yield nav
        nav.close()


def _ouvrir(
    navigateur: sync_api.Browser,
    html: str,
    sombre: bool = False,
    api: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> sync_api.Page:
    """La page ``html`` ouverte hors ligne.

    ``api`` répond à ``GET /api/donnees``, ``decision`` aux requêtes ``POST``.
    """
    page = navigateur.new_page(color_scheme="dark" if sombre else "light")

    def router(route: sync_api.Route) -> None:
        url = route.request.url
        if url == ADRESSE:
            route.fulfill(body=html, content_type="text/html; charset=utf-8")
        elif api is not None and "/api/" in url:
            post = route.request.method == "POST"
            reponse = decision if post else api
            route.fulfill(body=json.dumps(reponse), content_type="application/json")
        else:
            route.abort()  # polices : la page s'en passe

    page.route("**/*", router)
    page.goto(ADRESSE)
    return page


def _rgb(couleur: str) -> tuple[int, ...]:
    return tuple(int(c) for c in re.findall(r"\d+", couleur)[:3])


def _est_vert(couleur: str) -> bool:
    r, g, b = _rgb(couleur)
    return g > r + 40 and g > b + 20


@pytest.mark.parametrize("sombre", [False, True], ids=["clair", "sombre"])
def test_le_badge_lmelp_est_vert_et_les_autres_sources_grises(
    navigateur: sync_api.Browser, dossier: Path, sombre: bool
) -> None:
    page = _ouvrir(navigateur, construire_page(dossier), sombre)

    badges = page.locator(".ligne").first.locator(".src")
    couleurs = dict(
        badges.evaluate_all(
            "bs => bs.map(b => [b.textContent, getComputedStyle(b).color])"
        )
    )

    assert _est_vert(couleurs["lmelp ✓"])
    assert not _est_vert(couleurs["radiofrance"])
    pied = page.locator("footer .verifiee")
    assert pied.text_content() == "lmelp ✓"
    assert pied.evaluate("e => getComputedStyle(e).color") == couleurs["lmelp ✓"]


def _frise(page: sync_api.Page) -> dict[str, str]:
    """Le libellé de chaque barre de la frise, par année."""
    return dict(
        page.locator(".frise .barre").evaluate_all(
            "gs => gs.map(g => [g.dataset.annee, g.getAttribute('aria-label')])"
        )
    )


def _echelle(page: sync_api.Page) -> list[str]:
    """Les graduations de l'échelle verticale, du bas vers le haut."""
    graduations: list[str] = page.locator(
        "#frise > text[text-anchor=end]"
    ).all_text_contents()
    return graduations


def test_la_frise_compte_les_emissions_filtrees_et_adapte_son_echelle(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    page = _ouvrir(navigateur, construire_page(dossier))
    assert _frise(page)["2015"] == "2015 : 3 émissions"
    assert _echelle(page)[-1] == "3"

    page.select_option("#theme", "inconnu")

    frise = _frise(page)
    assert frise["2015"] == "2015 : 2 émissions"
    assert frise["2016"] == "2016 : 1 émission"
    assert frise["1955"] == "1955 : 0 émission"
    assert _echelle(page)[-1] == "2"
    page.locator('.barre[data-annee="2016"]').hover()
    assert (
        page.locator("#frise-bulle").inner_text() == "2016\n0 livres · 1 thème inconnu"
    )


def test_choisir_une_annee_ne_change_pas_les_barres_des_autres_annees(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    page = _ouvrir(navigateur, construire_page(dossier))
    avant = _frise(page)

    page.locator('.barre[data-annee="2016"]').click()

    assert page.locator("#resultat").inner_text() == "2 émissions en 2016"
    assert _frise(page) == avant
    assert page.locator(".barre.choisie").get_attribute("data-annee") == "2016"


def _filtres_actifs(page: sync_api.Page) -> list[str]:
    return [
        t.replace("\n", " ").strip()
        for t in page.locator("#frise-filtres .filtre").all_inner_texts()
    ]


def test_l_en_tete_de_la_frise_montre_les_filtres_actifs_et_les_retire(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    page = _ouvrir(navigateur, construire_page(dossier))
    defaut = "Émissions par année · cliquez une année pour filtrer"
    assert page.locator(".frise-tete").inner_text().strip() == defaut

    page.locator('.barre[data-annee="2015"]').click()
    page.select_option("#theme", "inconnu")
    page.check("#avec-enregistrement")
    page.select_option("#source", "wayback_podcast")
    page.fill("#q", "Duras")

    assert _filtres_actifs(page) == [
        "Année 2015 ×",
        "Thème : inconnu ×",
        "Source : podcast archivé (Wayback) ×",
        "Avec enregistrement ×",
        "« Duras » ×",
    ]
    page.get_by_role("button", name="Retirer le filtre « Duras »").click()
    page.get_by_role("button", name="Retirer le filtre Thème : inconnu").click()

    assert page.input_value("#q") == ""
    assert page.input_value("#theme") == ""
    assert _filtres_actifs(page) == [
        "Année 2015 ×",
        "Source : podcast archivé (Wayback) ×",
        "Avec enregistrement ×",
    ]
    assert page.locator("#resultat").inner_text() == "1 émission en 2015"
    assert _frise(page)["2015"] == "2015 : 1 émission"

    page.get_by_role("button", name="Tout effacer").click()

    assert page.locator(".frise-tete").inner_text().strip() == defaut
    assert not page.is_checked("#avec-enregistrement")
    assert page.locator("#resultat").inner_text() == "5 émissions"


def test_en_mode_arbitrage_la_frise_reste_filtree_apres_une_decision(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    emissions = donnees_page(dossier)
    sans_inexistante = [e for e in emissions if e["id"] != "2015-01-18"]
    page = _ouvrir(
        navigateur,
        construire_page(dossier, arbitrage=True),
        api={"emissions": emissions, "arbitrages": []},
        decision={"emissions": sans_inexistante, "arbitrages": []},
    )
    page.locator("#arb-nombre", has_text="0").wait_for()

    page.select_option("#theme", "inconnu")
    assert _frise(page)["2015"] == "2015 : 2 émissions"
    page.locator('.ligne[data-id="2015-01-18"]').click()
    page.get_by_role("button", name="N'existe pas").click()
    page.locator("#arb-statut", has_text="sort de la liste").wait_for()

    assert _frise(page)["2015"] == "2015 : 1 émission"
    assert _echelle(page)[-1] == "1"
    assert _filtres_actifs(page) == ["Thème : inconnu ×"]
    assert page.locator("#resultat").inner_text() == "2 émissions"


def _ids_affiches(page: sync_api.Page) -> list[str]:
    return [
        str(i)
        for i in page.locator(".ligne").evaluate_all("ls => ls.map(l => l.dataset.id)")
    ]


def test_les_filtres_a_trancher_et_a_ecouter_separent_les_emissions_renvoyees(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    _renvoyer_a_l_ecoute(dossier)
    page = _ouvrir(navigateur, construire_page(dossier))

    page.select_option("#doute", label="À trancher")
    assert _ids_affiches(page) == ["2015-01-18"]
    assert _filtres_actifs(page) == ["Doute : À trancher ×"]

    page.select_option("#doute", label="À écouter")
    assert _ids_affiches(page) == ["2015-01-11"]

    page.select_option("#doute", label="Au moins un doute")
    assert _ids_affiches(page) == ["2015-01-11", "2015-01-18"]


def test_le_badge_d_une_emission_renvoyee_est_a_ecouter(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    _renvoyer_a_l_ecoute(dossier)
    page = _ouvrir(navigateur, construire_page(dossier))

    badge = page.locator(".ligne .drap")
    assert badge.evaluate_all("bs => bs.map(b => b.closest('.ligne').dataset.id)") == [
        "2015-01-11",
        "2015-01-18",
    ]
    assert badge.all_inner_texts() == ["à écouter", "doute"]


def test_la_page_publiee_n_a_pas_de_bouton_a_ecouter(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    _renvoyer_a_l_ecoute(dossier)
    page = _ouvrir(navigateur, construire_page(dossier))

    page.locator('.ligne[data-id="2015-01-18"]').click()

    assert page.get_by_role("button", name="À écouter", exact=True).count() == 0


def test_en_mode_arbitrage_a_ecouter_renvoie_l_emission(
    navigateur: sync_api.Browser, dossier: Path
) -> None:
    emissions = donnees_page(dossier)
    page = _ouvrir(
        navigateur,
        construire_page(dossier, arbitrage=True),
        api={"emissions": emissions, "arbitrages": []},
        decision={"emissions": emissions, "arbitrages": []},
    )
    page.locator("#arb-nombre", has_text="0").wait_for()
    page.locator('.ligne[data-id="2015-01-18"]').click()

    with page.expect_request("**/api/arbitrages") as requete:
        page.get_by_role("button", name="À écouter", exact=True).click()

    assert requete.value.post_data_json == {
        "emission_id": "2015-01-18",
        "sorte": "écoute",
        "justification": "",
    }
    page.locator("#arb-statut", has_text="renvoyée à l'écoute").wait_for()
