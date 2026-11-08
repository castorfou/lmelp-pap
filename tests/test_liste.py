"""Construction de la liste des émissions à partir des attestations des sources."""

from datetime import date

from lmelp_pap.liste import Attestation, construire_liste


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

    assert [e.attestations for e in liste] == [[livres], [cinema]]


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
