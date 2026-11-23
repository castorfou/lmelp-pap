"""La collecte des sources depuis l'accueil, dans un vrai navigateur.

L'accueil est servi hors ligne (``test_accueil_navigateur``) ; ``/api/collectes``
est simulé : la collecte demandée tourne, puis finit au bon vouloir du test.
"""

import json
from typing import Any

from tests import test_accueil_navigateur
from tests.test_accueil_navigateur import _donnees, _ouvrir


# le navigateur partagé avec les tests de l'accueil
navigateur = test_accueil_navigateur.navigateur


EN_COURS = {
    "en_cours": True,
    "faites": 0,
    "total": 1,
    "sources": ["radiofrance"],
    "refresh": False,
    "en_cours_sur": "radiofrance",
    "progression": "radiofrance : page 3, 60 fiches vues, 12 téléchargées",
    "erreurs": [],
    "bilan": None,
}
FINIE = {
    **EN_COURS,
    "en_cours": False,
    "faites": 1,
    "en_cours_sur": None,
    "progression": None,
    "bilan": {
        "emissions": 2,
        "emissions_avant": 1,
        "attestations": 5,
        "sources": {"radiofrance": "collectee"},
    },
}


class FausseCollecte:
    """``/api/collectes`` : enregistre les demandes, rend l'état courant ;
    ``refus`` : la réponse 409 à la prochaine demande."""

    def __init__(self) -> None:
        self.demandes: list[Any] = []
        self.etat: dict[str, Any] = {**FINIE, "bilan": None, "total": 0}
        self.refus: str | None = None

    def __call__(self, route: Any) -> None:
        requete = route.request
        if requete.method == "POST":
            self.demandes.append(json.loads(requete.post_data))
            if self.refus:
                route.fulfill(
                    status=409,
                    body=json.dumps({"erreur": self.refus}),
                    content_type="application/json",
                )
                return
            self.etat = EN_COURS
        route.fulfill(body=json.dumps(self.etat), content_type="application/json")


def _ouvrir_collecte(navigateur: Any, donnees_apres: Any = None) -> tuple[Any, Any]:
    collecte = FausseCollecte()
    lectures = {"n": 0}
    avant = _donnees()

    def donnees(_requete: Any) -> Any:
        lectures["n"] += 1
        return avant if lectures["n"] == 1 or donnees_apres is None else donnees_apres

    page = _ouvrir(navigateur, avant, api={"/api/donnees": donnees})
    page.route("**/api/collectes", collecte)
    return page, collecte


def test_le_bouton_collecte_propose_chaque_source_et_toutes(navigateur: Any) -> None:
    page, _ = _ouvrir_collecte(navigateur)

    page.get_by_role("button", name="Collecte").click()

    boite = page.locator("#boite")
    for nom in (
        "radiofrance",
        "ina",
        "wayback_podcast",
        "anciennes_listes",
        "lmelp",
        "Toutes",
    ):
        assert boite.get_by_role("button", name=nom, exact=True).is_visible()
    assert boite.get_by_label("Re-collecter").is_visible()


def test_collecter_radiofrance_suit_la_progression_puis_recharge_la_liste(
    navigateur: Any,
) -> None:
    apres = _donnees()
    apres["emissions"] = apres["emissions"][:-1]  # la liste a changé
    page, collecte = _ouvrir_collecte(navigateur, apres)
    page.get_by_role("button", name="Collecte").click()
    page.get_by_label("Re-collecter").check()

    page.locator("#boite").get_by_role("button", name="radiofrance").click()

    assert collecte.demandes == [{"source": "radiofrance", "refresh": True}]
    page.locator("#collecte-etat", has_text="page 3, 60 fiches vues").wait_for()
    # la page reste utilisable : la boîte se ferme, le suivi reste en tête
    page.keyboard.press("Escape")
    page.locator("#collecter", has_text="radiofrance").wait_for()
    page.locator('.compteur[data-etat="sans"]').click()

    collecte.etat = FINIE
    page.locator("#toast", has_text="Collecte terminée").wait_for()
    assert "2 émissions (avant 1)" in page.locator("#toast").inner_text()
    assert page.locator("#collecter").inner_text() == "Collecte"
    nb = len(apres["emissions"])
    page.locator("#resume", has_text=f"{nb} émissions").wait_for()


def test_une_collecte_refusee_affiche_le_message_du_serveur(navigateur: Any) -> None:
    page, collecte = _ouvrir_collecte(navigateur)
    collecte.refus = "une collecte est déjà en cours (ina) : attendez sa fin"
    page.get_by_role("button", name="Collecte").click()

    page.locator("#boite").get_by_role("button", name="Toutes").click()

    erreur = page.locator("#collecte-erreur")
    erreur.wait_for()
    assert "déjà en cours (ina)" in erreur.inner_text()
    assert collecte.demandes == [{"source": "toutes", "refresh": False}]
