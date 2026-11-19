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


def test_le_theme_se_lit_aussi_dans_un_titre_sans_accent_ou_d_opera() -> None:
    notices = _notices()

    assert notices["PH_PHD88021060"].themes == frozenset({"théâtre"})  # « Théatre »
    assert notices["PH_PHD99255941"].themes == frozenset({"opéra"})


def test_les_titres_television_musique_varietes_et_critique_dramatique() -> None:
    notices = _notices()

    assert notices["PH_PHD99226107"].themes == frozenset({"télévision"})
    assert notices["PH_PHD99255852"].themes == frozenset({"musique"})
    assert notices["PH_PHD99255882"].themes == frozenset({"variétés"})
    assert notices["PH_PHD88021037"].themes == frozenset({"théâtre"})


FICHES = FIXTURES / "fiches"


def _avec_fiche(source_id: str, titre: str, jour: str) -> Attestation:
    """La notice ``source_id`` au titre générique, lue avec sa fiche détaillée."""
    ligne = {
        "date_diffusion": jour,
        "titre": titre,
        "url_ina": f"https://catalogue.ina.fr/doc/TV-RADIO/{source_id}/le-masque",
        "facette_litterature": "non",
    }
    fiche = (FICHES / f"{source_id}.html").read_text(encoding="utf-8")
    (notice,) = lire_notices([ligne], fiches={source_id: fiche})
    return notice


def test_les_descripteurs_de_la_fiche_donnent_le_theme_d_un_titre_generique() -> None:
    # 2000-01-09 : descripteurs « cinéma ; film ; débat »
    notice = _avec_fiche(
        "RD_1098450.001", "Le masque et la plume du 09 janvier 2000", "2000-01-09"
    )

    assert notice.themes == frozenset({"cinéma"})


def test_le_resume_producteur_donne_le_theme_meme_en_capitales_sans_accent() -> None:
    # 1994-01-16 : ni descripteurs ni chapeau, résumé producteur « LITTERAIRE : … »
    notice = _avec_fiche(
        "RD_581453.001", "Le masque et la plume du 16 janvier 1994", "1994-01-16"
    )

    assert notice.themes == frozenset({"livres"})


def test_une_notice_multidiffusee_ne_date_pas_la_premiere_diffusion() -> None:
    # 2016-05-16 : rediffusion du lundi de l'émission du dimanche 15 mai 2016
    rediffusion = _avec_fiche(
        "RD_6476526.001",
        "Le masque et la plume : émission du 16 mai 2016",
        "2016-05-16",
    )
    premiere = _avec_fiche(
        "RD_1098450.001", "Le masque et la plume du 09 janvier 2000", "2000-01-09"
    )

    assert rediffusion.nature_date == "rediffusion"
    assert premiere.nature_date == "première diffusion"


def _notice_avec(fiche: str) -> Attestation:
    ligne = {
        "date_diffusion": "1986-04-13",
        "titre": "Le masque et la plume du 13 avril 1986",
        "url_ina": "https://catalogue.ina.fr/doc/TV-RADIO/PH_X2/le-masque",
        "facette_litterature": "non",
    }
    (notice,) = lire_notices([ligne], fiches={"PH_X2": fiche})
    return notice


def test_le_resume_documentaire_n_ajoute_pas_de_theme_aux_champs_de_classement() -> (
    None
):
    # une émission cinéma dont le résumé cite le roman adapté à l'écran
    fiche = (
        '<td id="DE" class="v">cinéma ; film (Le diamant du Nil)</td>'
        '<td id="RES" class="v">Débat sur les films, dont un adapté du roman de '
        "Joan Wilder.</td>"
    )

    assert _notice_avec(fiche).themes == frozenset({"cinéma"})


def test_le_resume_producteur_n_ajoute_pas_de_theme_au_titre() -> None:
    # 2026-01-25 : le résumé producteur reprend la description de France Inter,
    # qui cite le best-seller adapté et Shakespeare
    ligne = {
        "date_diffusion": "2026-01-25",
        "titre": "Le Mage du Kremlin, Hamnet, quels films voir cette semaine",
        "url_ina": "https://catalogue.ina.fr/doc/TV-RADIO/RD_X3/le-mage",
        "facette_litterature": "non",
    }
    fiche = (
        '<td id="RESPROD" class="v">[Source site internet de France Inter] '
        "Chloé Zhao qui ressuscite Shakespeare… « Le Mage du Kremlin » est "
        "l'adaptation du best-seller de Giuliano da Empoli. Le théâtre…</td>"
    )

    (notice,) = lire_notices([ligne], fiches={"RD_X3": fiche})

    assert notice.themes == frozenset({"cinéma"})


def test_le_premier_champ_qui_ne_designe_qu_un_theme_tranche() -> None:
    # 2019-03-10 : les descripteurs d'un film sur un écrivain citent la
    # littérature ; le chapeau dit l'émission consacrée au cinéma
    fiche = (
        '<td id="DE" class="v">cinéma ; film ; reine ; littérature</td>'
        '<td id="CHAP" class="v">Magazine consacré aujourd\'hui au cinéma.</td>'
    )

    assert _notice_avec(fiche).themes == frozenset({"cinéma"})


def test_un_resume_qui_designe_plusieurs_themes_ne_tranche_pas() -> None:
    # 2026-07-12 : ni descripteurs ni chapeau ; la description de France Inter
    # parle de théâtre et cite des auteurs
    fiche = (
        '<td id="RESPROD" class="v">[Source site internet de France Inter] '
        "Les critiques du Masque débattent du théâtre du festival, dont "
        "l'adaptation d'un roman.</td>"
    )

    assert _notice_avec(fiche).themes == frozenset()


def test_a_defaut_de_champ_de_classement_le_resume_documentaire_donne_le_theme() -> (
    None
):
    fiche = '<td id="RES" class="v">Débat à propos des livres suivants : …</td>'

    assert _notice_avec(fiche).themes == frozenset({"livres"})
