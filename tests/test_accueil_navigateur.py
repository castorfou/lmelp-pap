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
    navigateur: Any,
    donnees: dict[str, Any] | None = None,
    sombre: bool = False,
    api: dict[str, Any] | None = None,
) -> Any:
    """L'accueil servi hors ligne. ``api`` : des routes de plus, chemin →
    fonction qui reçoit la requête et rend la réponse JSON ; ``/api/donnees``
    peut y être remplacé."""
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
        elif api and (chemin := "/" + url.split("/", 3)[-1]) in api:
            reponse = api[chemin](route.request)
            route.fulfill(body=json.dumps(reponse), content_type="application/json")
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
    page.locator('.compteur[data-etat="localise"]').click()
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


def test_la_page_telechargeable_propose_telecharger(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="telechargeable"]').click()
    entetes = [t.rstrip(" ▲▼") for t in page.locator("th").all_inner_texts()]
    assert entetes[-1] == "Action"
    lignes = page.locator("tbody tr")
    assert lignes.first.get_by_role("button", name="Télécharger").count() == 1
    assert lignes.first.locator("input[type=checkbox]").count() == 1
    assert page.get_by_role("button", name="Télécharger : sélection (0)").count() == 1
    total = _comptes(_donnees())["telechargeable"]
    assert page.get_by_role("button", name=f"Télécharger : tout ({total})").count()


def test_telecharger_envoie_les_emissions_et_notifie(navigateur: Any) -> None:
    donnees = _donnees()
    envoyees: list[Any] = []
    apres = json.loads(json.dumps(donnees))
    rapatriee = next(e for e in apres["emissions"] if e["maturite"] == "telechargeable")
    rapatriee["maturite"] = "rapatrie"
    lectures = {"n": 0}

    def donnees_api(requete: Any) -> Any:
        lectures["n"] += 1
        return donnees if lectures["n"] == 1 else apres

    def rapatriements(requete: Any) -> Any:
        if requete.method == "POST":
            envoyees.append(json.loads(requete.post_data))
            return {
                "en_cours": True,
                "faites": 0,
                "total": 1,
                "bilan": None,
                "en_cours_sur": None,
                "erreurs": [],
            }
        return {
            "en_cours": False,
            "faites": 1,
            "total": 1,
            "en_cours_sur": None,
            "bilan": {"rapatries": 1, "deja_la": 0, "echecs": 0},
            "erreurs": [],
        }

    page = _ouvrir(
        navigateur,
        api={"/api/donnees": donnees_api, "/api/rapatriements": rapatriements},
    )
    page.locator('.compteur[data-etat="telechargeable"]').click()
    ligne = page.locator(f'tbody tr[data-id="{rapatriee["id"]}"]')
    ligne.get_by_role("button", name="Télécharger").click()

    page.locator("#toast", has_text="1 rapatrié").wait_for()
    assert envoyees == [{"emissions": [rapatriee["id"]]}]
    assert "rapatrié 1→2" in page.locator("#toast").inner_text()
    assert page.locator(f'tbody tr[data-id="{rapatriee["id"]}"]').count() == 0


def test_telecharger_la_selection(navigateur: Any) -> None:
    envoyees: list[Any] = []

    def rapatriements(requete: Any) -> Any:
        if requete.method == "POST":
            envoyees.append(json.loads(requete.post_data))
        return {
            "en_cours": False,
            "faites": 2,
            "total": 2,
            "en_cours_sur": None,
            "bilan": {"rapatries": 2, "deja_la": 0, "echecs": 0},
            "erreurs": [],
        }

    page = _ouvrir(navigateur, api={"/api/rapatriements": rapatriements})
    page.locator('.compteur[data-etat="telechargeable"]').click()
    cases = page.locator("tbody input[type=checkbox]")
    cases.nth(0).check()
    cases.nth(1).check()
    page.get_by_role("button", name="Télécharger : sélection (2)").click()
    page.locator("#toast", has_text="2 rapatriés").wait_for()
    assert page.get_by_role("button", name="Télécharger : sélection (0)").count()
    assert page.locator("tbody input[type=checkbox]:checked").count() == 0
    assert len(envoyees[0]["emissions"]) == 2


EN_COURS = {
    "en_cours": True,
    "faites": 3,
    "total": 12,
    "en_cours_sur": "2008-03-02",
    "octets": 210_000_000,
    "fichier_octets": 35_000_000,
    "fichier_total": 70_000_000,
    "debut": "2026-11-21T09:00:00+01:00",
    "arrete": False,
    "bilan": None,
    "erreurs": [],
}
FINI_AVEC_ECHEC = {
    **EN_COURS,
    "en_cours": False,
    "faites": 12,
    "en_cours_sur": None,
    "bilan": {"rapatries": 11, "deja_la": 0, "echecs": 1},
    "erreurs": [{"emission": "1980-02-24", "detail": "Read timed out."}],
}


def test_un_lot_en_cours_s_affiche_dans_un_bandeau_sur_toutes_les_pages(
    navigateur: Any,
) -> None:
    arrets: list[str] = []

    def arret(requete: Any) -> Any:
        arrets.append(requete.method)
        return {**EN_COURS, "arrete": True}

    page = _ouvrir(
        navigateur,
        api={
            "/api/rapatriements": lambda r: EN_COURS,
            "/api/rapatriements/arret": arret,
        },
    )
    bandeau = page.locator("#bandeau")
    bandeau.wait_for()
    texte = bandeau.inner_text()
    assert "3 / 12" in texte
    assert "2008-03-02" in texte
    assert "50 %" in texte
    assert "210 Mo" in texte

    page.locator('.compteur[data-etat="localise"]').click()
    assert page.locator("#bandeau").is_visible()

    page.get_by_role("button", name="Arrêter").click()
    page.locator("#bandeau", has_text="arrêt demandé").wait_for()
    assert arrets == ["POST"]


def test_un_lot_fini_garde_ses_erreurs_jusqu_a_fermeture(navigateur: Any) -> None:
    page = _ouvrir(navigateur, api={"/api/rapatriements": lambda r: FINI_AVEC_ECHEC})
    bandeau = page.locator("#bandeau")
    bandeau.wait_for()
    texte = bandeau.inner_text()
    assert "11 rapatriés" in texte
    assert "1980-02-24" in texte
    assert "Read timed out." in texte

    page.get_by_role("button", name="Fermer").click()
    assert page.locator("#bandeau").count() == 0
    page.reload()
    page.locator(".compteur").first.wait_for()
    page.wait_for_timeout(300)
    assert page.locator("#bandeau").count() == 0


def test_l_echec_d_une_emission_s_affiche_sur_sa_ligne(navigateur: Any) -> None:
    donnees = _donnees()
    cible = next(e for e in donnees["emissions"] if e["maturite"] == "telechargeable")
    cible["echec_rapatriement"] = {
        "date": "2026-11-21T09:23:00+01:00",
        "detail": "Read timed out.",
    }
    page = _ouvrir(navigateur, donnees)
    page.locator('.compteur[data-etat="telechargeable"]').click()
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    assert "échec" in ligne.inner_text()
    assert "Read timed out." in ligne.inner_text()


def test_pendant_un_lot_la_selection_est_videe(navigateur: Any) -> None:
    page = _ouvrir(navigateur, api={"/api/rapatriements": lambda r: EN_COURS})
    page.locator('.compteur[data-etat="telechargeable"]').click()
    page.locator("tbody input[type=checkbox]").nth(0).check()
    page.get_by_role("button", name="Télécharger : sélection (1)").click()
    page.get_by_role("button", name="Télécharger : sélection (0)").wait_for(
        timeout=3000
    )
    assert page.locator("tbody input[type=checkbox]:checked").count() == 0


def test_le_suivi_flotte_en_haut_a_droite_sans_decaler_la_page(
    navigateur: Any,
) -> None:
    sans = _ouvrir(navigateur)
    haut_sans = sans.locator(".compteurs").bounding_box()["y"]
    page = _ouvrir(navigateur, api={"/api/rapatriements": lambda r: EN_COURS})
    panneau = page.locator("#bandeau")
    panneau.wait_for()

    assert panneau.evaluate("b => getComputedStyle(b).position") == "fixed"
    boite = panneau.bounding_box()
    assert boite["x"] + boite["width"] >= 1280 - 40
    assert boite["width"] <= 420
    assert boite["y"] < 120
    assert page.locator(".compteurs").bounding_box()["y"] == haut_sans

    page.get_by_role("button", name="Replier").click()
    assert "50 %" not in panneau.inner_text()
    assert "3 / 12" in panneau.inner_text()
    page.get_by_role("button", name="Déplier").click()
    assert "50 %" in panneau.inner_text()


def test_pap_en_haut_a_gauche_ramene_a_l_accueil(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('#histo rect.zone[data-annee="1987"]').click()
    page.locator('.compteur[data-etat="localise"]').click()
    page.get_by_role("link", name="pap").click()
    page.locator("#frise").wait_for()
    assert page.locator("#frise .annee").count() == 2026 - 1955 + 1
    assert "etat=" not in page.url
