"""Construction de la liste des émissions à partir des attestations des sources."""

from dataclasses import replace
from datetime import date

import pytest

from lmelp_pap.liste import Attestation, Enregistrement, construire_liste


def test_une_attestation_donne_une_emission_identifiee_par_sa_date() -> None:
    attestation = Attestation(
        source="ina",
        source_id="PHD88021484",
        date=date(1956, 1, 22),
        themes=frozenset({"livres", "théâtre"}),
        titre="Théâtre et littérature",
    )

    liste, _doutes = construire_liste([attestation])

    assert len(liste) == 1
    emission = liste[0]
    assert emission.id == "1956-01-22"
    assert emission.date == date(1956, 1, 22)
    assert emission.themes == frozenset({"livres", "théâtre"})
    assert emission.titre == "Théâtre et littérature"
    assert emission.attestations == [attestation]


def test_deux_sources_a_la_meme_date_attestent_la_meme_emission() -> None:
    ina = Attestation(source="ina", source_id="PHD1", date=date(1967, 1, 1))
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_23820437", date=date(1967, 1, 1)
    )

    liste, _doutes = construire_liste([ina, podcast])

    assert len(liste) == 1
    assert liste[0].attestations == [ina, podcast]


def test_un_ecart_de_trois_jours_avec_un_theme_inconnu_est_rapproche() -> None:
    ina = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1956, 1, 19),
        themes=frozenset({"livres"}),
    )
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_1", date=date(1956, 1, 22)
    )

    liste, _doutes = construire_liste([ina, podcast])

    assert len(liste) == 1
    assert liste[0].attestations == [ina, podcast]


def test_des_themes_incompatibles_ne_sont_pas_rapproches() -> None:
    livres = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1957, 10, 24),
        themes=frozenset({"livres"}),
    )
    cinema = Attestation(
        source="radiofrance",
        source_id="cinema-1",
        date=date(1957, 10, 25),
        themes=frozenset({"cinéma"}),
    )

    liste, _doutes = construire_liste([livres, cinema])

    assert [e.attestations for e in liste] == [[livres]]


def test_au_dela_de_trois_jours_ce_sont_deux_emissions() -> None:
    a = Attestation(source="ina", source_id="PHD1", date=date(1960, 3, 6))
    b = Attestation(source="radiofrance", source_id="x-1", date=date(1960, 3, 10))

    liste, _doutes = construire_liste([a, b])

    assert len(liste) == 2


def test_une_attestation_rapprochable_de_deux_emissions_est_un_doute() -> None:
    livres = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1960, 3, 6),
        themes=frozenset({"livres"}),
    )
    theatre = Attestation(
        source="ina",
        source_id="PHD2",
        date=date(1960, 3, 10),
        themes=frozenset({"théâtre"}),
    )
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_9", date=date(1960, 3, 8)
    )

    _liste, doutes = construire_liste([livres, theatre, podcast])

    ambigus = [d.source_id for d in doutes if d.type == "rapprochement ambigu"]
    assert ambigus == ["ITEMA_9"]


def test_un_desaccord_de_date_de_plus_d_un_jour_est_un_doute() -> None:
    ina = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1956, 1, 19),
        themes=frozenset({"livres"}),
    )
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_1", date=date(1956, 1, 22)
    )

    liste, doutes = construire_liste([ina, podcast])

    assert [(d.type, d.emission_id, d.dans_la_liste) for d in doutes] == [
        ("désaccord de date", liste[0].id, True)
    ]


def test_un_jour_d_ecart_n_est_pas_un_doute() -> None:
    a = Attestation(source="ina", source_id="PHD1", date=date(1990, 5, 6))
    b = Attestation(source="radiofrance", source_id="x-1", date=date(1990, 5, 7))

    _liste, doutes = construire_liste([a, b])

    assert doutes == []


def test_un_doute_sur_une_emission_hors_de_la_liste_le_dit() -> None:
    ina = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1994, 5, 26),
        themes=frozenset({"cinéma"}),
    )
    radiofrance = Attestation(
        source="radiofrance",
        source_id="pulp-fiction",
        date=date(1994, 5, 29),
        themes=frozenset({"cinéma"}),
    )

    liste, doutes = construire_liste([ina, radiofrance])

    assert liste == []
    assert [(d.type, d.emission_id, d.dans_la_liste) for d in doutes] == [
        ("désaccord de date", "1994-05-29", False)
    ]


def test_chaque_champ_vient_de_la_source_prioritaire_pour_ce_champ() -> None:
    ina = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1958, 12, 18),
        themes=frozenset({"livres"}),
        titre="Littérature",
        description=None,
        chaine="Paris Inter",
        heure="22:00:00",
        duree="01:02:00",
    )
    radiofrance = Attestation(
        source="radiofrance",
        source_id="louis-aragon-4684213",
        date=date(1958, 12, 20),
        themes=frozenset({"livres", "théâtre"}),
        titre="Louis Aragon",
        description="Entretien avec Louis Aragon",
        duree="00:30:00",
    )

    liste, _doutes = construire_liste([ina, radiofrance])

    emission = liste[0]
    assert emission.date == date(1958, 12, 20)  # radiofrance > ina
    assert emission.themes == frozenset({"livres", "théâtre"})  # radiofrance > ina
    assert emission.titre == "Louis Aragon"  # radiofrance > ina
    assert emission.description == "Entretien avec Louis Aragon"
    assert emission.chaine == "Paris Inter"  # ina > radiofrance
    assert emission.heure == "22:00:00"
    assert emission.duree == "01:02:00"  # ina > radiofrance


def test_un_champ_absent_de_la_source_prioritaire_vient_de_la_suivante() -> None:
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_1", date=date(1975, 10, 19)
    )
    ancienne_liste = Attestation(
        source="anciennes_listes",
        source_id="2005-10",
        date=date(1975, 10, 18),
        themes=frozenset({"livres"}),
    )

    liste, _doutes = construire_liste([podcast, ancienne_liste])

    assert liste[0].date == date(1975, 10, 18)  # anciennes listes > podcast
    assert liste[0].themes == frozenset({"livres"})


def test_une_emission_livres_garde_sa_date_comme_identifiant_malgre_une_collision() -> (
    None
):
    livres = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1957, 10, 24),
        themes=frozenset({"livres"}),
    )
    cinema = Attestation(
        source="ina",
        source_id="PHD2",
        date=date(1957, 10, 24),
        themes=frozenset({"cinéma"}),
    )

    liste, _ = construire_liste([livres, cinema])
    liste_inversee, _ = construire_liste([cinema, livres])

    assert [(e.id, e.themes) for e in liste] == [("1957-10-24", frozenset({"livres"}))]
    assert [(e.id, e.themes) for e in liste_inversee] == [
        (e.id, e.themes) for e in liste
    ]


def test_la_liste_garde_les_emissions_livres_mixtes_ou_de_theme_inconnu() -> None:
    livres = Attestation(
        source="ina",
        source_id="1",
        date=date(1970, 1, 4),
        themes=frozenset({"livres"}),
    )
    mixte = Attestation(
        source="ina",
        source_id="2",
        date=date(1970, 1, 11),
        themes=frozenset({"livres", "théâtre"}),
    )
    inconnu = Attestation(
        source="wayback_podcast", source_id="3", date=date(1970, 1, 18)
    )
    cinema = Attestation(
        source="ina",
        source_id="4",
        date=date(1970, 1, 25),
        themes=frozenset({"cinéma"}),
    )
    theatre = Attestation(
        source="ina",
        source_id="5",
        date=date(1970, 2, 1),
        themes=frozenset({"théâtre"}),
    )

    liste, _ = construire_liste([livres, mixte, inconnu, cinema, theatre])

    assert [e.id for e in liste] == ["1970-01-04", "1970-01-11", "1970-01-18"]


def test_une_emission_reunit_les_enregistrements_de_toutes_ses_sources() -> None:
    mp3 = Enregistrement(
        url="https://media.radiofrance-podcast.net/podcast09/14007-04.12.1958-ITEMA_1.mp3",
        type="intégral",
    )
    m4a = Enregistrement(
        url="https://media.radiofrance-podcast.net/podcast09/14007-04.12.1958-ITEMA_1.m4a",
        type="intégral",
    )
    extrait = Enregistrement(
        url="https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/louis-aragon-4684213",
        type="extrait",
    )
    podcast_mp3 = Attestation(
        source="wayback_podcast",
        source_id="ITEMA_1",
        date=date(1958, 12, 4),
        enregistrements=(mp3,),
    )
    podcast_m4a = Attestation(
        source="wayback_podcast",
        source_id="ITEMA_1",
        date=date(1958, 12, 4),
        enregistrements=(m4a, mp3),
    )
    radiofrance = Attestation(
        source="radiofrance",
        source_id="louis-aragon-4684213",
        date=date(1958, 12, 4),
        enregistrements=(extrait,),
    )

    liste, _ = construire_liste([podcast_mp3, podcast_m4a, radiofrance])

    assert liste[0].enregistrements == [mp3, m4a, extrait]


@pytest.mark.parametrize(
    ("jour", "animateur"),
    [
        (date(1958, 12, 4), "Michel Polac, François-Régis Bastide"),
        (date(1975, 3, 2), "François-Régis Bastide"),
        (date(1985, 6, 9), "Pierre Bouteiller"),
        (date(2005, 1, 9), "Jérôme Garcin"),
        (date(2025, 1, 12), "Rebecca Manzoni"),
        (date(1989, 9, 10), None),  # année de transition : on ne devine pas
    ],
)
def test_l_animateur_se_deduit_de_la_date(jour: date, animateur: str | None) -> None:
    attestation = Attestation(source="ina", source_id="1", date=jour)

    liste, _ = construire_liste([attestation])

    assert liste[0].animateur == animateur


def test_un_animateur_precise_par_une_source_l_emporte_sur_la_deduction() -> None:
    attestation = Attestation(
        source="radiofrance",
        source_id="x-1",
        date=date(2005, 1, 9),
        animateur="Arnaud Viviant",
    )

    liste, _ = construire_liste([attestation])

    assert liste[0].animateur == "Arnaud Viviant"


DIMANCHE = date(2024, 2, 11)
URL_INTEGRAL = "https://media.radiofrance-podcast.net/podcast09/20904-11.02.2024-ITEMA_23644545-2024F4007S0042-27.m4a"
URL_EXTRAIT = "https://media.radiofrance-podcast.net/podcast09/14007-12.02.2024-ITEMA_23783945-2024F4007S0043-27.m4a"


def _fiche_du_dimanche() -> Attestation:
    return Attestation(
        source="radiofrance",
        source_id="le-masque-et-la-plume-du-dimanche-11-fevrier-2024-2491269",
        date=DIMANCHE,
        themes=frozenset({"livres"}),
        titre="Les nouvelles pages de Marie Darrieussecq, Philippe Besson",
        description="Les critiques ont lu les nouveaux livres de la semaine.",
        duree="00:46:54",
        enregistrements=(Enregistrement(url=URL_INTEGRAL, type="intégral"),),
    )


def _fiche_par_livre() -> Attestation:
    return Attestation(
        source="radiofrance",
        source_id="fabriquer-une-femme-de-marie-darrieussecq-3613378",
        date=date(2024, 2, 12),
        themes=frozenset({"livres"}),
        titre="CRITIQUE l Le Masque unanime face à Marie Darrieussecq",
        description="Le Masque a lu « Fabriquer une femme ».",
        duree="00:11:22",
        enregistrements=(Enregistrement(url=URL_EXTRAIT, type="extrait"),),
        extrait=True,
    )


def test_les_champs_viennent_de_l_emission_entiere_plutot_que_d_un_extrait() -> None:
    # publié le même dimanche et arrivé en premier : sa place ne doit rien changer
    extrait = replace(_fiche_par_livre(), date=DIMANCHE)
    liste, _doutes = construire_liste([extrait, _fiche_du_dimanche()])

    emission = liste[0]
    assert emission.date == DIMANCHE
    assert (
        emission.titre == "Les nouvelles pages de Marie Darrieussecq, Philippe Besson"
    )
    assert (
        emission.description
        == "Les critiques ont lu les nouveaux livres de la semaine."
    )
    assert emission.duree == "00:46:54"


def test_une_emission_attestee_seulement_par_un_extrait_n_a_pas_de_duree() -> None:
    liste, _doutes = construire_liste([_fiche_par_livre()])

    emission = liste[0]
    assert emission.titre == "CRITIQUE l Le Masque unanime face à Marie Darrieussecq"
    assert emission.duree is None


def test_un_extrait_l_est_pour_tous_les_fichiers_de_son_archive() -> None:
    # la Wayback ne connaît que le nom du fichier : lettre S, donc « intégral »
    mp3_du_fragment = URL_EXTRAIT.replace("-27.m4a", "-22.mp3")
    wayback = Attestation(
        source="wayback_podcast",
        source_id="ITEMA_23783945",
        date=date(2024, 2, 12),
        enregistrements=(Enregistrement(url=mp3_du_fragment, type="intégral"),),
    )

    liste, _doutes = construire_liste(
        [_fiche_du_dimanche(), _fiche_par_livre(), wayback]
    )

    assert [(e.url, e.type) for e in liste[0].enregistrements] == [
        (URL_INTEGRAL, "intégral"),
        (URL_EXTRAIT, "extrait"),
        (mp3_du_fragment, "extrait"),
    ]


URL_HITCHCOCK = "https://media.radiofrance-podcast.net/podcast09/14007-01.01.1967-ITEMA_23820437-1967F4007E0001"


def _archive_hitchcock(duree: str) -> list[Attestation]:
    """L'émission du 1er janvier 1967 : notice INA, archive E, MP3 de la Wayback."""
    return [
        Attestation(
            source="ina",
            source_id="PH_PHD99205665",
            date=date(1967, 1, 1),
            themes=frozenset({"cinéma"}),
            titre="Cinéma",
            duree="00:23:10",
        ),
        Attestation(
            source="radiofrance",
            source_id="francois-truffaut-invite-du-masque-pour-parler-d-alfred-hitchcock-1030980",
            date=date(1967, 1, 1),
            themes=frozenset({"cinéma", "livres"}),
            titre='"Le cinéma selon Hitchcock" par Truffaut',
            duree=duree,
            enregistrements=(
                Enregistrement(url=f"{URL_HITCHCOCK}-27.m4a", type="extrait"),
            ),
            extrait=True,
        ),
        Attestation(
            source="wayback_podcast",
            source_id="ITEMA_23820437",
            date=date(1967, 1, 1),
            enregistrements=(
                Enregistrement(url=f"{URL_HITCHCOCK}-22.mp3", type="extrait"),
            ),
            extrait=True,
        ),
    ]


def test_une_archive_presque_aussi_longue_que_la_diffusion_est_l_emission_entiere() -> (
    None
):
    liste, _doutes = construire_liste(_archive_hitchcock(duree="00:21:05"))

    emission = liste[0]
    assert [e.type for e in emission.enregistrements] == ["intégral", "intégral"]
    assert emission.titre == '"Le cinéma selon Hitchcock" par Truffaut'


def test_une_archive_nettement_plus_courte_que_la_diffusion_reste_un_extrait() -> None:
    liste, _doutes = construire_liste(_archive_hitchcock(duree="00:10:00"))

    emission = liste[0]
    assert [e.type for e in emission.enregistrements] == ["extrait", "extrait"]
    assert emission.titre == "Cinéma"


def test_la_regle_des_90_pourcent_ne_vaut_que_pour_les_archives_e() -> None:
    # une fiche par livre (lettre S) face à une durée INA du même ordre
    ina = Attestation(source="ina", source_id="RD_1", date=DIMANCHE, duree="00:12:00")

    liste, _doutes = construire_liste([ina, _fiche_par_livre()])

    assert [e.type for e in liste[0].enregistrements] == ["extrait"]


def test_les_themes_se_cumulent_entre_sources_et_extraits() -> None:
    # 70 ans du Masque : la fiche entière ne dit que « cinéma » ; un extrait
    # et la notice INA, rapprochés par ce thème commun, apportent les autres
    entiere = replace(_fiche_du_dimanche(), themes=frozenset({"cinéma"}))
    extrait = replace(
        _fiche_par_livre(), date=DIMANCHE, themes=frozenset({"cinéma", "livres"})
    )
    ina = Attestation(
        source="ina",
        source_id="RD_2",
        date=DIMANCHE,
        themes=frozenset({"cinéma", "théâtre"}),
    )

    liste, _doutes = construire_liste([entiere, extrait, ina])

    assert liste[0].themes == frozenset({"cinéma", "livres", "théâtre"})
