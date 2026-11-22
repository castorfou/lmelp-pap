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


# Rendu par une route de ``api`` : la requête reste en suspens, la route
# est gardée dans ``SUSPENDUES`` pour que le test y réponde plus tard.
EN_ATTENTE = object()
SUSPENDUES: list[Any] = []


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
            if reponse is EN_ATTENTE:
                SUSPENDUES.append(route)
            else:
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
    assert noms == ["Date", "Titre", "Sources", "Depuis"]

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
    assert entetes == ["Date", "Titre"]


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
    "rapatriees": ["2008-03-02", "2008-03-09"],
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


def _avec_rapatrie() -> tuple[dict[str, Any], dict[str, Any]]:
    """Les données simulées, l'émission rapatriée portant son fichier."""
    donnees = _donnees()
    cible = next(e for e in donnees["emissions"] if e["maturite"] == "rapatrie")
    cible["fichier_audio"] = "1987/14007-04.10.1987 a.m4a"
    cible["ecart"] = None
    return donnees, cible


def _qualifier(navigateur: Any, reponse: Any) -> tuple[Any, dict[str, Any], list[Any]]:
    """L'accueil sur la page rapatrié, le lecteur de l'émission ouvert ;
    ``reponse(emission)`` change l'émission dans les données renvoyées."""
    donnees, cible = _avec_rapatrie()
    envoyees: list[Any] = []

    def qualifications(requete: Any) -> Any:
        envoyees.append(json.loads(requete.post_data))
        apres = json.loads(json.dumps(donnees))
        reponse(next(e for e in apres["emissions"] if e["id"] == cible["id"]))
        return apres

    page = _ouvrir(navigateur, donnees, api={"/api/qualifications": qualifications})
    page.locator('.compteur[data-etat="rapatrie"]').click()
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Écouter et qualifier").click()
    return page, cible, envoyees


def test_la_page_rapatrie_propose_ecouter_et_qualifier_sans_lot(
    navigateur: Any,
) -> None:
    donnees, _ = _avec_rapatrie()
    page = _ouvrir(navigateur, donnees)
    page.locator('.compteur[data-etat="rapatrie"]').click()
    entetes = [t.rstrip(" ▲▼") for t in page.locator("th").all_inner_texts()]
    assert entetes[-1] == "Action"
    assert page.get_by_role("button", name="Écouter et qualifier").count() == 1
    assert page.locator("tbody input[type=checkbox]").count() == 0
    assert page.locator(".lot").count() == 0


def test_ecouter_ouvre_un_lecteur_sur_le_fichier_rapatrie(navigateur: Any) -> None:
    page, _, _ = _qualifier(navigateur, lambda e: None)
    lecteur = page.locator("audio")
    lecteur.wait_for(state="attached")
    assert lecteur.get_attribute("src") == "/audios/1987/14007-04.10.1987%20a.m4a"
    assert lecteur.get_attribute("controls") is not None
    assert page.get_by_role("button", name="+30 s").count() == 1
    assert page.get_by_role("button", name="−30 s").count() == 1
    assert page.get_by_role("button", name="Écarter").is_disabled()


def test_favorable_qualifie_l_emission_et_notifie(navigateur: Any) -> None:
    def favorable(e: dict[str, Any]) -> None:
        e["maturite"] = "qualifie"

    page, cible, envoyees = _qualifier(navigateur, favorable)
    page.get_by_role("button", name="Favorable").click()

    page.locator("#toast", has_text="qualifié").wait_for()
    assert envoyees == [{"emission_id": cible["id"], "verdict": "favorable"}]
    toast = page.locator("#toast").inner_text()
    assert "rapatrié 1→0" in toast
    qualifies = _comptes(_donnees())["qualifie"]
    assert f"qualifié {qualifies}→{qualifies + 1}" in toast
    assert page.locator(f'tbody tr[data-id="{cible["id"]}"]').count() == 0


def test_ecarter_demande_un_motif_et_l_affiche_sur_la_ligne(navigateur: Any) -> None:
    def ecarte(e: dict[str, Any]) -> None:
        e["ecart"] = {"date": "2026-11-21T10:00:00+01:00", "motif": "pas la bonne"}

    page, cible, envoyees = _qualifier(navigateur, ecarte)
    page.get_by_label("Motif de l'écart").fill("pas la bonne")
    page.get_by_role("button", name="Écarter").click()

    page.locator("#toast", has_text="écarté").wait_for()
    assert envoyees == [
        {"emission_id": cible["id"], "verdict": "ecarte", "motif": "pas la bonne"}
    ]
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    assert "écarté : pas la bonne" in ligne.inner_text()


def test_survoler_les_rapatries_liste_leurs_dates(navigateur: Any) -> None:
    page = _ouvrir(navigateur, api={"/api/rapatriements": lambda r: FINI_AVEC_ECHEC})
    rapatries = page.locator("#bandeau .rapatriees")
    rapatries.wait_for()
    assert "11 rapatriés" in rapatries.inner_text()
    detail = rapatries.get_attribute("title")
    assert "2008-03-02" in detail
    assert "2008-03-09" in detail


# --- Écoute : page radiofrance.fr et diffusion de l'Open API ---------------

PAGE_RF = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/x-1"


def _ecouter(
    navigateur: Any, radiofrance: Any, page_rf: bool = True
) -> tuple[Any, list[str]]:
    """Le lecteur ouvert sur l'émission rapatriée ; ``radiofrance`` : la
    réponse de ``GET /api/radiofrance/<id>``."""
    donnees, cible = _avec_rapatrie()
    if page_rf:
        cible["attestations"].append(
            {"source": "radiofrance", "url": PAGE_RF, "titre": "Une fiche"}
        )
    appels: list[str] = []

    def api(requete: Any) -> Any:
        appels.append(requete.url)
        return radiofrance

    page = _ouvrir(navigateur, donnees, api={f"/api/radiofrance/{cible['id']}": api})
    page.locator('.compteur[data-etat="rapatrie"]').click()
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Écouter et qualifier").click()
    page.locator("tr.ecoute").wait_for()
    return page, appels


TROUVEE = {
    "statut": "trouvee",
    "diffusion": {
        "titre": "Les livres de la semaine",
        "resume": "Un résumé.",
        "url": PAGE_RF,
        "animateurs": [{"nom": "Rebecca Manzoni", "role": None}],
        "equipe": [
            {"nom": "Jérôme Garcin", "role": "Producteur"},
            {"nom": "Arnaud Viviant", "role": None},
        ],
        "invites": [{"nom": "Une Autrice", "role": None}],
    },
}


def test_l_ecoute_ouvre_la_page_radiofrance_dans_un_nouvel_onglet(
    navigateur: Any,
) -> None:
    page, _ = _ecouter(navigateur, TROUVEE)
    lien = page.locator("tr.ecoute").get_by_role("link", name="page radiofrance.fr")
    assert lien.get_attribute("href") == PAGE_RF
    assert lien.get_attribute("target") == "_blank"
    assert "noopener" in (lien.get_attribute("rel") or "")


def test_sans_page_radiofrance_pas_de_lien(navigateur: Any) -> None:
    page, _ = _ecouter(navigateur, TROUVEE, page_rf=False)
    page.locator("tr.ecoute .radiofrance", has_text="Jérôme Garcin").wait_for()
    assert page.locator("tr.ecoute a").count() == 0


def test_l_ecoute_montre_l_equipe_et_les_invites_de_l_api(navigateur: Any) -> None:
    page, appels = _ecouter(navigateur, TROUVEE)
    bloc = page.locator("tr.ecoute .radiofrance")
    bloc.get_by_text("Jérôme Garcin", exact=False).wait_for()
    texte = bloc.inner_text()
    assert "Présentation : Rebecca Manzoni" in texte
    assert "Équipe : Jérôme Garcin (Producteur), Arnaud Viviant" in texte
    assert "Arnaud Viviant" in texte
    assert "Une Autrice" in texte
    assert "Les livres de la semaine" in texte
    assert "Open API Radio France" in texte
    assert len(appels) == 1


@pytest.mark.parametrize(
    ("reponse", "message"),
    [
        ({"statut": "sans_cle", "diffusion": None}, "pas de clé"),
        ({"statut": "introuvable", "diffusion": None}, "aucune diffusion"),
        ({"statut": "erreur", "detail": "HTTP 403", "diffusion": None}, "HTTP 403"),
    ],
)
def test_sans_donnees_de_l_api_un_message_et_l_ecoute_reste_possible(
    navigateur: Any, reponse: dict[str, Any], message: str
) -> None:
    page, _ = _ecouter(navigateur, reponse)
    page.locator("tr.ecoute .radiofrance", has_text=message).wait_for()
    assert page.locator("tr.ecoute audio").count() == 1
    assert page.get_by_role("button", name="Favorable").is_enabled()


# --- mettre à disposition de lmelp ------------------------------------------


def _remettre(navigateur: Any, reponse: Any) -> tuple[Any, dict[str, Any], list[Any]]:
    """L'accueil sur la page qualifié ; ``reponse(donnees, cible)`` rend la
    réponse de ``POST /api/remises``. Les confirmations se font dans la
    boîte de la page (voir ``_confirmer``)."""
    donnees = _donnees()
    cible = next(e for e in donnees["emissions"] if e["maturite"] == "qualifie")
    envoyees: list[Any] = []

    def remises(requete: Any) -> Any:
        envoyees.append(json.loads(requete.post_data))
        apres = json.loads(json.dumps(donnees))
        return reponse(
            apres, next(e for e in apres["emissions"] if e["id"] == cible["id"])
        )

    page = _ouvrir(navigateur, donnees, api={"/api/remises": remises})
    page.locator('.compteur[data-etat="qualifie"]').click()
    return page, cible, envoyees


def _confirmer(page: Any, accepter: bool = True) -> None:
    """Répond à la boîte de confirmation de la page (jamais une boîte native
    du navigateur)."""
    boite = page.get_by_role("dialog")
    boite.wait_for()
    nom = "Mettre à disposition" if accepter else "Annuler"
    boite.get_by_role("button", name=nom, exact=True).click()


def _mise(apres: dict[str, Any], e: dict[str, Any]) -> dict[str, Any]:
    e["maturite"] = "valide"
    e["dans_lmelp"] = False
    return {
        **apres,
        "remise": {"mises": [{"emission": e["id"], "fichier": "x.m4a"}], "refus": []},
    }


def test_la_page_qualifie_propose_la_mise_a_disposition_par_ligne_et_en_lot(
    navigateur: Any,
) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="qualifie"]').click()
    lignes = page.locator("tbody tr")
    nom = "Mettre à disposition de lmelp"
    assert lignes.first.get_by_role("button", name=nom).count() == 1
    assert lignes.first.locator("input[type=checkbox]").count() == 1
    total = _comptes(_donnees())["qualifie"]
    assert page.get_by_role("button", name=f"{nom} : tout ({total})").count() == 1


def test_mettre_a_disposition_confirme_envoie_et_notifie(navigateur: Any) -> None:
    page, cible, envoyees = _remettre(navigateur, _mise)
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Mettre à disposition de lmelp").click()
    _confirmer(page)

    page.locator("#toast", has_text="mis à disposition").wait_for()
    assert envoyees == [{"emissions": [cible["id"]]}]
    comptes = _comptes(_donnees())
    toast = page.locator("#toast").inner_text()
    assert f"qualifié {comptes['qualifie']}→{comptes['qualifie'] - 1}" in toast
    assert "valide" in toast
    assert page.locator(f'tbody tr[data-id="{cible["id"]}"]').count() == 0


def test_sans_confirmation_rien_n_est_envoye(navigateur: Any) -> None:
    page, cible, envoyees = _remettre(navigateur, _mise)
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Mettre à disposition de lmelp").click()
    _confirmer(page, accepter=False)
    page.wait_for_timeout(200)
    assert page.get_by_role("dialog").count() == 0
    assert envoyees == []
    assert ligne.count() == 1


def test_la_confirmation_est_une_boite_de_la_page(navigateur: Any) -> None:
    natives: list[Any] = []
    page, cible, _ = _remettre(navigateur, _mise)

    def native(d: Any) -> None:
        natives.append(d)
        d.dismiss()

    page.on("dialog", native)
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Mettre à disposition de lmelp").click()
    boite = page.get_by_role("dialog")
    boite.wait_for()
    assert natives == []
    assert cible["id"] in boite.inner_text()
    assert "dossier audio de lmelp" in boite.inner_text()


def test_la_mise_a_disposition_en_cours_reste_affichee(navigateur: Any) -> None:
    page, cible, _ = _remettre(navigateur, lambda apres, e: EN_ATTENTE)
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Mettre à disposition de lmelp").click()
    _confirmer(page)

    boite = page.get_by_role("dialog")
    boite.get_by_text("en cours").wait_for()
    assert boite.get_by_role("button").count() == 0
    route = SUSPENDUES.pop()
    apres = _donnees()
    e = next(x for x in apres["emissions"] if x["id"] == cible["id"])
    route.fulfill(body=json.dumps(_mise(apres, e)), content_type="application/json")
    page.locator("#toast", has_text="mis à disposition").wait_for()
    assert page.get_by_role("dialog").count() == 0


def test_une_collision_s_affiche_visiblement(navigateur: Any) -> None:
    detail = "1987/a.m4a existe déjà dans le dossier de lmelp"

    def collision(apres: dict[str, Any], e: dict[str, Any]) -> dict[str, Any]:
        return {
            **apres,
            "remise": {"mises": [], "refus": [{"emission": e["id"], "detail": detail}]},
        }

    page, cible, _ = _remettre(navigateur, collision)
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.get_by_role("button", name="Mettre à disposition de lmelp").click()
    _confirmer(page)

    alerte = page.locator(".refus")
    alerte.wait_for()
    assert cible["id"] in alerte.inner_text()
    assert detail in alerte.inner_text()
    assert "1 refus" in page.locator("#toast").inner_text()
    page.get_by_role("button", name="Fermer les refus").click()
    assert page.locator(".refus").count() == 0


def test_une_emission_valide_entree_dans_lmelp_compte_dans_lmelp(
    navigateur: Any,
) -> None:
    donnees = _donnees()
    entree = next(e for e in donnees["emissions"] if e["maturite"] == "valide")
    entree["dans_lmelp"] = True
    page = _ouvrir(navigateur, donnees)
    comptes = _comptes(_donnees())
    assert _compteurs(page)["valide"] == comptes["valide"] - 1
    assert _compteurs(page)["lmelp"] == comptes["lmelp"] + 1


def test_la_page_rapatrie_s_ouvre_de_la_plus_recente_a_la_plus_ancienne(
    navigateur: Any,
) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="rapatrie"]').click()
    dates = page.locator("tbody tr td:nth-child(1)").all_inner_texts()
    dates = [d for d in dates if d[:4].isdigit()]
    assert dates == sorted(dates, reverse=True)
    assert page.locator("th.triable", has_text="Date").inner_text().endswith("▼")


def test_le_tri_choisi_sur_une_page_est_garde(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="localise"]').click()
    titre = page.locator("th.triable", has_text="Titre")
    titre.click()
    titre.click()  # titre décroissant
    assert page.locator("th.triable", has_text="Titre").inner_text().endswith("▼")

    page.get_by_role("button", name="← Accueil").click()
    page.locator('.compteur[data-etat="localise"]').click()
    assert page.locator("th.triable", has_text="Titre").inner_text().endswith("▼")

    page.reload()
    page.locator("tbody tr").first.wait_for()
    assert page.locator("th.triable", has_text="Titre").inner_text().endswith("▼")

    # une autre page garde son propre tri
    page.get_by_role("button", name="← Accueil").click()
    page.locator('.compteur[data-etat="rapatrie"]').click()
    assert page.locator("th.triable", has_text="Date").inner_text().endswith("▼")


# --- annuler une mise à disposition (page valide) ----------------------------


def test_une_mise_a_disposition_s_annule_depuis_la_page_valide(
    navigateur: Any,
) -> None:
    donnees = _donnees()
    cible = next(e for e in donnees["emissions"] if e["maturite"] == "valide")
    envoyees: list[Any] = []

    def annulation(requete: Any) -> Any:
        envoyees.append(json.loads(requete.post_data))
        apres = json.loads(json.dumps(donnees))
        next(e for e in apres["emissions"] if e["id"] == cible["id"])["maturite"] = (
            "qualifie"
        )
        return apres

    page = _ouvrir(navigateur, donnees, api={"/api/remises/annulation": annulation})
    page.locator('.compteur[data-etat="valide"]').click()
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    bouton = ligne.get_by_role("button", name="Annuler", exact=True)
    assert "discret" in (bouton.get_attribute("class") or "")
    bouton.click()
    boite = page.get_by_role("dialog")
    boite.wait_for()
    assert "qualifié" in boite.inner_text()
    boite.get_by_role("button", name="Annuler la mise à disposition").click()

    page.locator("#toast", has_text="annulée").wait_for()
    assert envoyees == [{"emission": cible["id"]}]
    assert page.locator(f'tbody tr[data-id="{cible["id"]}"]').count() == 0
    assert page.locator(".lot").count() == 0


def test_la_page_valide_montre_depuis_combien_de_jours_lmelp_attend(
    navigateur: Any,
) -> None:
    page = _ouvrir(navigateur)
    page.locator('.compteur[data-etat="valide"]').click()
    colonnes = [t.rstrip(" ▲▼") for t in page.locator("th").all_inner_texts()]
    i = colonnes.index("Depuis")
    cellule = page.locator("tbody tr").first.locator("td").nth(i)
    assert cellule.inner_text().endswith(" j")


def test_aucune_page_d_etat_n_a_de_colonne_themes(navigateur: Any) -> None:
    page = _ouvrir(navigateur)
    for etat in ("telechargeable", "qualifie", "valide", "lmelp"):
        page.locator(f'.compteur[data-etat="{etat}"]').click()
        entetes = [t.rstrip(" ▲▼") for t in page.locator("th").all_inner_texts()]
        assert "Thèmes" not in entetes, etat
        page.get_by_role("button", name="← Accueil").click()


def test_une_emission_qui_n_est_pas_que_livres_le_dit_a_cote_du_titre(
    navigateur: Any,
) -> None:
    donnees = _donnees()
    mixte, autre = [e for e in donnees["emissions"] if e["maturite"] == "qualifie"][:2]
    mixte["themes"] = ["cinéma", "livres"]
    page = _ouvrir(navigateur, donnees)
    page.locator('.compteur[data-etat="qualifie"]').click()
    ligne = page.locator(f'tbody tr[data-id="{mixte["id"]}"]')
    assert "cinéma, livres" in ligne.inner_text()
    seul_livres = page.locator(f'tbody tr[data-id="{autre["id"]}"]')
    assert "livres" not in seul_livres.inner_text()


def test_cliquer_une_emission_qualifiee_deplie_l_apercu_de_sa_fiche(
    navigateur: Any,
) -> None:
    donnees = _donnees()
    cible = next(e for e in donnees["emissions"] if e["maturite"] == "qualifie")
    apercu = {
        "emission_id": cible["id"],
        "titre": "Le Masque et la Plume du 4 janvier 2009",
        "date": "2009-01-04T00:00:00+00:00",
        "type": "livres",
        "duree": 3287,
        "description": "durée : 00:54:47 - Le Masque et la Plume",
        "sources_description": {},
        "episode_page_url": None,
        "url": None,
        "audio_rel_filename": "2009/x.m4a",
        "sha256": "abc",
        "date_remise": None,
        "apercu": True,
    }
    page = _ouvrir(
        navigateur, donnees, api={f"/api/remises/{cible['id']}": lambda r: apercu}
    )
    page.locator('.compteur[data-etat="qualifie"]').click()
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.locator("td").nth(1).click()

    detail = page.locator("tr.fiche")
    detail.get_by_text("Aperçu").wait_for()
    assert "2009/x.m4a" in detail.inner_text()
    # la case à cocher ne replie rien
    ligne.locator("input[type=checkbox]").click()
    assert page.locator("tr.fiche").count() == 1


def test_cliquer_une_emission_valide_deplie_sa_fiche(navigateur: Any) -> None:
    donnees = _donnees()
    cible = next(e for e in donnees["emissions"] if e["maturite"] == "valide")
    fiche = {
        "emission_id": cible["id"],
        "titre": "Le Masque et la Plume du 4 janvier 2015",
        "date": "2015-01-04T00:00:00+00:00",
        "type": "livres",
        "duree": 3287,
        "description": "durée : 00:54:47 - Le Masque et la Plume - par : Jérôme Garcin",
        "sources_description": {"duree": "fichier"},
        "episode_page_url": "https://www.radiofrance.fr/x",
        "url": "https://media.radiofrance-podcast.net/x.m4a",
        "audio_rel_filename": "2015/x.m4a",
        "sha256": "5e06ea3830e3",
        "date_remise": "2026-11-22T09:58:03+00:00",
    }
    page = _ouvrir(
        navigateur, donnees, api={f"/api/remises/{cible['id']}": lambda r: fiche}
    )
    page.locator('.compteur[data-etat="valide"]').click()
    ligne = page.locator(f'tbody tr[data-id="{cible["id"]}"]')
    ligne.locator("td").first.click()

    detail = page.locator("tr.fiche")
    detail.get_by_text("par : Jérôme Garcin").wait_for()
    texte = detail.inner_text()
    for attendu in (fiche["titre"], "2015/x.m4a", "00:54:47", "livres"):
        assert attendu in texte
    ligne.locator("td").first.click()
    assert page.locator("tr.fiche").count() == 0
