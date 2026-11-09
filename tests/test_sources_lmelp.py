"""Lecture du cache de lmelp, source vérifiée (ADR 0003)."""

import json
from datetime import date
from pathlib import Path

from lmelp_pap.sources.lmelp import lire_emissions


FIXTURES = Path(__file__).parent / "fixtures" / "lmelp"
PAGES = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"


def _emissions() -> list[dict[str, str]]:
    donnees: list[dict[str, str]] = json.loads(
        (FIXTURES / "emissions.json").read_text(encoding="utf-8")
    )
    return donnees


def test_une_emission_verifiee_atteste_le_theme_livres_par_sa_fiche_radiofrance() -> (
    None
):
    premiere, _ = lire_emissions(_emissions())

    assert premiere.source == "lmelp"
    assert (
        premiere.source_id
        == "le-masque-et-la-plume-du-dimanche-01-novembre-2026-2020600"
    )
    assert premiere.url == (
        PAGES + "le-masque-et-la-plume-du-dimanche-01-novembre-2026-2020600"
    )
    assert premiere.themes == frozenset({"livres"})
    assert (premiere.titre or "").startswith("Emma Marsantes, Jonathan Littell")


def test_lmelp_donne_la_date_de_publication_a_l_heure_de_paris() -> None:
    premiere, publiee_un_vendredi = lire_emissions(_emissions())

    assert (premiere.date, premiere.nature_date) == (date(2026, 11, 1), "publication")
    # publiée le vendredi 19 juin à 22 h 30 UTC : déjà le samedi 20 à Paris
    assert publiee_un_vendredi.date == date(2026, 6, 20)
