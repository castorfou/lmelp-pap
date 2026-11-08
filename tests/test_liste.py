"""Construction de la liste des émissions à partir des attestations des sources."""

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

    liste, _rapport = construire_liste([attestation])

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

    liste, _rapport = construire_liste([ina, podcast])

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

    liste, _rapport = construire_liste([ina, podcast])

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

    liste, _rapport = construire_liste([livres, cinema])

    assert [e.attestations for e in liste] == [[livres]]


def test_au_dela_de_trois_jours_ce_sont_deux_emissions() -> None:
    a = Attestation(source="ina", source_id="PHD1", date=date(1960, 3, 6))
    b = Attestation(source="radiofrance", source_id="x-1", date=date(1960, 3, 10))

    liste, _rapport = construire_liste([a, b])

    assert len(liste) == 2


def test_une_attestation_rapprochable_de_deux_emissions_est_signalee() -> None:
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

    _liste, rapport = construire_liste([livres, theatre, podcast])

    ambigus = [s.source_id for s in rapport.signalements if s.type == "ambigu"]
    assert ambigus == ["ITEMA_9"]


def test_un_desaccord_de_date_de_plus_d_un_jour_est_signale() -> None:
    ina = Attestation(
        source="ina",
        source_id="PHD1",
        date=date(1956, 1, 19),
        themes=frozenset({"livres"}),
    )
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_1", date=date(1956, 1, 22)
    )

    liste, rapport = construire_liste([ina, podcast])

    assert [(s.type, s.emission_id) for s in rapport.signalements] == [
        ("désaccord de date", liste[0].id)
    ]


def test_un_jour_d_ecart_n_est_pas_signale() -> None:
    a = Attestation(source="ina", source_id="PHD1", date=date(1990, 5, 6))
    b = Attestation(source="radiofrance", source_id="x-1", date=date(1990, 5, 7))

    _liste, rapport = construire_liste([a, b])

    assert rapport.signalements == []


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

    liste, _rapport = construire_liste([ina, radiofrance])

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

    liste, _rapport = construire_liste([podcast, ancienne_liste])

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
