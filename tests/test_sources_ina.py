"""Lecture des notices du catalogue INA (lignes réelles du scraping)."""

import csv
from datetime import date
from pathlib import Path

from lmelp_pap.liste import Attestation
from lmelp_pap.sources.ina import lire_notices


FIXTURES = Path(__file__).parent / "fixtures" / "ina"


def _notices() -> dict[str, Attestation]:
    with (FIXTURES / "notices.csv").open(encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    return {a.source_id: a for a in lire_notices(lignes)}


def test_une_notice_atteste_une_emission_avec_les_champs_de_l_ina() -> None:
    notice = _notices()["PH_PHD88021484"]

    assert notice.source == "ina"
    assert notice.date == date(1956, 1, 22)
    assert notice.titre == "Théâtre et littérature"
    assert notice.themes == frozenset({"théâtre", "livres"})
    assert notice.chaine == "X"
    assert notice.heure == "14:30:00"
    assert notice.duree == "01:53:31"
    assert notice.url == (
        "https://catalogue.ina.fr/doc/TV-RADIO/PH_PHD88021484/theatre-et-litterature"
    )


def test_la_facette_litterature_donne_le_theme_livres_meme_sans_mot_cle() -> None:
    notices = _notices()

    assert notices["PH_PHY02000980"].themes == frozenset({"livres"})
    assert notices["PH_PHD88021062"].themes == frozenset({"cinéma", "livres"})


def test_une_notice_sans_date_est_ignoree() -> None:
    assert "PH_PHD88020898" not in _notices()


def test_une_heure_mal_formee_par_l_ina_est_ignoree() -> None:
    notice = _notices()["PH_PHD88020899"]

    assert notice.heure is None
    assert notice.duree == "00:47:10"


def test_hors_facette_une_notice_sans_mot_cle_a_un_theme_inconnu() -> None:
    ligne = {
        "date_diffusion": "1985-08-25",
        "titre": "Le masque et la plume du 25 août 1985",
        "url_ina": "https://catalogue.ina.fr/doc/TV-RADIO/PH_X1/le-masque",
        "facette_litterature": "non",
    }

    (notice,) = lire_notices([ligne])

    assert notice.themes == frozenset()
