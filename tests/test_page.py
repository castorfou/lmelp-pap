"""Page HTML de la liste des émissions, générée à partir de ses CSV."""

import json
import re
from pathlib import Path
from typing import Any

from lmelp_pap.page import construire_page


FIXTURES = Path(__file__).parent / "fixtures" / "liste"


def _donnees(page: str) -> list[dict[str, Any]]:
    """Les données embarquées dans la page, telles que le JavaScript les lit."""
    bloc = re.search(
        r'<script type="application/json" id="donnees">(.*?)</script>', page, re.DOTALL
    )
    assert bloc is not None
    donnees: list[dict[str, Any]] = json.loads(bloc.group(1))
    return donnees


def test_la_page_embarque_chaque_emission_avec_ses_champs() -> None:
    emissions = _donnees(construire_page(FIXTURES))

    assert [e["id"] for e in emissions] == ["1956-01-22", "1958-12-04", "1967-01-01"]
    premiere = emissions[0]
    assert premiere["themes"] == ["livres", "théâtre"]
    assert premiere["date"] == "1956-01-22"
    assert premiere["titre"] == "Théâtre et littérature"
    assert premiere["animateur"] == "Michel Polac, François-Régis Bastide"
    assert premiere["chaine"] == "Paris Inter"
    assert premiere["duree"] == "01:53:31"
    assert emissions[2]["themes"] == []  # thème inconnu


def test_chaque_emission_porte_ses_attestations_enregistrements_et_doutes() -> None:
    aragon = _donnees(construire_page(FIXTURES))[1]

    assert aragon["attestations"] == [
        {
            "source": "radiofrance",
            "date": "1958-12-04",
            "titre": "Louis Aragon",
            "url": "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/louis-aragon-4684213",
        },
        {"source": "wayback_podcast", "date": "1958-12-04", "titre": "", "url": ""},
    ]
    assert aragon["enregistrements"] == [
        {
            "url": "https://media.radiofrance-podcast.net/podcast09/14007-04.12.1958-ITEMA_24232446-1958F4007E0005.m4a",
            "type": "extrait",
        }
    ]
    assert aragon["doutes"] == [
        {"type": "rapprochement ambigu", "detail": "rapprochable aussi de 1958-12-06"}
    ]
    assert aragon["description"].endswith("</script> incluse")


def test_une_emission_sans_enregistrement_ni_doute_a_des_listes_vides() -> None:
    sans = _donnees(construire_page(FIXTURES))[0]

    assert sans["enregistrements"] == []
    assert sans["doutes"] == []


def test_les_doutes_d_une_emission_hors_de_la_liste_ne_sont_pas_sur_la_page() -> None:
    emissions = _donnees(construire_page(FIXTURES))

    assert "1958-12-06" not in [e["id"] for e in emissions]
    assert [d["type"] for e in emissions for d in e["doutes"]] == [
        "rapprochement ambigu"
    ]


def test_la_page_est_un_document_html_complet_qui_s_ouvre_seul() -> None:
    page = construire_page(FIXTURES)

    assert page.lstrip().lower().startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in page
    assert "<title>Liste des émissions du Masque et la Plume</title>" in page
    assert page.rstrip().endswith("</html>")
