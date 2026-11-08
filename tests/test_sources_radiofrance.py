"""Lecture des fiches d'émission de radiofrance.fr (pages réelles enregistrées)."""

from datetime import date
from pathlib import Path

from lmelp_pap.liste import Attestation, Enregistrement
from lmelp_pap.sources.radiofrance import lire_fiche, lire_page_liste


FIXTURES = Path(__file__).parent / "fixtures" / "radiofrance"


def _fiche(slug: str) -> Attestation:
    return lire_fiche((FIXTURES / f"{slug}.html").read_text(encoding="utf-8"))


def test_un_extrait_d_archive_atteste_l_emission_d_origine() -> None:
    attestation = _fiche("louis-aragon-4684213")

    assert attestation.source == "radiofrance"
    assert attestation.source_id == "louis-aragon-4684213"
    assert attestation.url == (
        "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"
        "louis-aragon-4684213"
    )
    assert attestation.date == date(1958, 12, 4)
    assert attestation.themes == frozenset({"livres"})
    assert attestation.titre == (
        'Louis Aragon : "Je déteste cette façon d\'expliquer le passé par le présent"'
    )
    assert attestation.description is not None
    assert attestation.description.startswith("En 1958, Louis Aragon est l'invité")
    assert attestation.animateur == "Michel Polac, François-Régis Bastide"
    assert attestation.duree == "00:30:15"
    assert attestation.enregistrements == (
        Enregistrement(
            url="https://media.radiofrance-podcast.net/podcast09/14007-04.12.1958-ITEMA_24232446-1958F4007E0005-NET_MFI_9DB9F391-96BF-40A6-B343-C1ED9E574CB1-27.m4a",
            type="extrait",
        ),
    )


def test_une_emission_livres_ancienne_tire_son_theme_de_l_url() -> None:
    attestation = _fiche("livres-5737051")

    assert attestation.date == date(2004, 12, 5)
    assert attestation.themes == frozenset({"livres"})
    assert attestation.titre == "Livres"
    assert attestation.description is None
    assert attestation.animateur == "Jérôme Garcin"
    assert attestation.enregistrements == ()  # droits expirés, plus écoutable


def test_une_emission_recente_tire_son_theme_des_etiquettes() -> None:
    attestation = _fiche("les-livres-a-lire-2989961")

    assert attestation.date == date(2014, 9, 28)
    assert attestation.themes == frozenset({"livres"})
    assert attestation.duree == "00:54:12"
    assert [e.type for e in attestation.enregistrements] == ["intégral"]


def test_un_extrait_de_cinema_est_un_extrait_de_theme_cinema() -> None:
    attestation = _fiche("pulp-fiction-9826652")

    assert attestation.date == date(1994, 5, 29)
    assert attestation.themes == frozenset({"cinéma"})
    assert [e.type for e in attestation.enregistrements] == ["extrait"]


def test_une_page_de_liste_donne_les_urls_des_fiches() -> None:
    page = (FIXTURES / "liste-p100.html").read_text(encoding="utf-8")

    urls = lire_page_liste(page)

    assert len(urls) == 20
    assert urls[0] == (
        "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"
        "mission-impossible-1-de-brian-de-palma-6043240"
    )
