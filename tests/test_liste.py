"""Construction de la liste des émissions à partir des attestations des sources."""

from dataclasses import replace
from datetime import date, datetime

import pytest

from lmelp_pap.liste import (
    Arbitrage,
    Attestation,
    Doute,
    Enregistrement,
    construire_liste,
)


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

    assert [d for d in doutes if d.type == "désaccord de date"] == []


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


# --- Source vérifiée lmelp (ADR 0003) ----------------------------------------

_PAGE = "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"


def _fiche(slug: str, jour: date, themes: set[str]) -> Attestation:
    return Attestation(
        source="radiofrance",
        source_id=slug,
        date=jour,
        themes=frozenset(themes),
        url=_PAGE + slug,
    )


def _lmelp(slug: str, publication: date) -> Attestation:
    return Attestation(
        source="lmelp",
        source_id=slug,
        date=publication,
        nature_date="publication",
        themes=frozenset({"livres"}),
        url=_PAGE + slug,
    )


def test_lmelp_se_rattache_par_sa_fiche_sans_changer_la_date_de_diffusion() -> None:
    # publiée le mercredi pour le dimanche 5 juillet : plus près, par la date,
    # de l'émission du dimanche précédent, au thème inconnu
    precedente = _fiche("dimanche-precedent-1", date(2026, 6, 28), set())
    fiche = _fiche("salman-rushdie-didier-decoin-2", date(2026, 7, 5), {"livres"})

    liste, doutes = construire_liste(
        [precedente, fiche, _lmelp("salman-rushdie-didier-decoin-2", date(2026, 7, 1))]
    )

    assert [(e.id, sorted(a.source for a in e.attestations)) for e in liste] == [
        ("2026-06-28", ["radiofrance"]),
        ("2026-07-05", ["lmelp", "radiofrance"]),
    ]
    assert [
        d for d in doutes if d.type in ("désaccord de date", "rapprochement ambigu")
    ] == []


def test_le_theme_verifie_par_lmelp_remplace_ceux_des_autres_sources() -> None:
    # 2018-01-21 : « Elena Ferrante, Delphine de Vigan… que lire cette semaine ? »
    ferrante = _fiche("elena-ferrante-1", date(2018, 1, 21), {"cinéma", "théâtre"})

    liste, _doutes = construire_liste(
        [ferrante, _lmelp("elena-ferrante-1", date(2018, 1, 21))]
    )

    assert [(e.id, e.themes) for e in liste] == [("2018-01-21", frozenset({"livres"}))]


def test_lmelp_sans_fiche_se_rapproche_par_la_date_et_c_est_un_doute() -> None:
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_7", date=date(2016, 3, 6)
    )

    liste, doutes = construire_liste(
        [podcast, _lmelp("page-disparue-3", date(2016, 3, 6))]
    )

    assert [(e.id, sorted(a.source for a in e.attestations)) for e in liste] == [
        ("2016-03-06", ["lmelp", "wayback_podcast"])
    ]
    assert [(d.type, d.emission_id, d.source_id) for d in doutes] == [
        ("sans fiche radiofrance", "2016-03-06", "page-disparue-3")
    ]


def test_une_emission_absente_de_lmelp_depuis_2017_est_un_doute() -> None:
    verifiees = [
        _fiche("verifiee-1", date(2017, 3, 5), {"livres"}),
        _lmelp("verifiee-1", date(2017, 3, 5)),
        _fiche("derniere-verifiee-2", date(2018, 2, 4), {"livres"}),
        _lmelp("derniere-verifiee-2", date(2018, 2, 4)),
    ]
    avant_2017 = _fiche("avant-2017-3", date(2016, 5, 1), {"livres"})
    absente = _fiche("mage-du-kremlin-4", date(2017, 6, 11), {"livres"})
    inconnu = Attestation(source="ina", source_id="PHD5", date=date(2017, 9, 10))
    cinema = _fiche("cinema-6", date(2017, 7, 9), {"cinéma"})
    apres = _fiche("apres-la-derniere-7", date(2018, 6, 3), {"livres"})

    _liste, doutes = construire_liste(
        [*verifiees, avant_2017, absente, inconnu, cinema, apres]
    )

    assert [d.emission_id for d in doutes if d.type == "absente de lmelp"] == [
        "2017-06-11",
        "2017-09-10",
    ]


def test_sans_aucune_emission_lmelp_l_absence_n_est_pas_un_doute() -> None:
    _liste, doutes = construire_liste(
        [_fiche("sans-lmelp-1", date(2019, 5, 5), {"livres"})]
    )

    assert doutes == []


# --- Doutes de thème, collision, republication, attestation fragile ----------

_MEDIA = "https://media.radiofrance-podcast.net/podcast09/"


def _types(doutes: list[Doute], emission_id: str) -> list[str]:
    return sorted(d.type for d in doutes if d.emission_id == emission_id)


def test_une_emission_sans_theme_a_un_doute_theme_inconnu() -> None:
    # 2010-07-11 : « Festival d'Avignon », une émission de théâtre sans thème
    ina = Attestation(
        source="ina",
        source_id="RD_4294389.001",
        date=date(2010, 7, 11),
        titre="Le masque et la plume du 11 juillet 2010",
    )
    avignon = Attestation(
        source="radiofrance",
        source_id="festival-d-avignon-5488789",
        date=date(2010, 7, 11),
        titre="Festival d'Avignon",
        enregistrements=(
            Enregistrement(
                _MEDIA + "14007-11.07.2010-ITEMA_20234917-2010F4007E0150-27.m4a",
                "extrait",
            ),
        ),
        extrait=True,
    )

    _liste, doutes = construire_liste([ina, avignon])

    assert _types(doutes, "2010-07-11") == ["thème inconnu"]


def _dimanche_18_aout_2024() -> list[Attestation]:
    """Le 18 août 2024 : fiches radiofrance « cinéma », notices INA « livres »."""
    return [
        _fiche(
            "le-masque-et-la-plume-du-dimanche-18-aout-2024-5609935",
            date(2024, 8, 18),
            {"cinéma"},
        ),
        replace(
            _fiche(
                "le-roman-de-jim-des-freres-larrieu-6664324",
                date(2024, 8, 19),
                {"cinéma", "livres"},
            ),
            extrait=True,
        ),
        replace(
            _fiche(
                "moi-moche-et-mechant-4-de-chris-renaud-4922866",
                date(2024, 8, 19),
                {"cinéma"},
            ),
            extrait=True,
        ),
        Attestation(
            source="ina",
            source_id="RD_16239327.001",
            date=date(2024, 8, 18),
            themes=frozenset({"livres"}),
        ),
    ]


def test_un_extrait_au_theme_absent_de_l_emission_entiere_est_un_doute() -> None:
    _liste, doutes = construire_liste(_dimanche_18_aout_2024())

    assert "thèmes divergents" in _types(doutes, "2024-08-18")


def test_une_seconde_emission_le_meme_jour_est_une_collision() -> None:
    _liste, doutes = construire_liste(_dimanche_18_aout_2024())

    assert "collision" in _types(doutes, "2024-08-18-b")
    assert "collision" not in _types(doutes, "2024-08-18")


def test_deux_attestations_de_l_emission_entiere_aux_themes_differents() -> None:
    # 1959-03-23 : deux notices INA rapprochées, « livres ; théâtre » et « livres »
    mixte = Attestation(
        source="ina",
        source_id="PH_PHD88020938",
        date=date(1959, 3, 23),
        themes=frozenset({"livres", "théâtre"}),
    )
    livres = Attestation(
        source="ina",
        source_id="PH_PHD88020939",
        date=date(1959, 3, 26),
        themes=frozenset({"livres"}),
    )

    _liste, doutes = construire_liste([mixte, livres])

    assert "thèmes divergents" in _types(doutes, "1959-03-23")


def test_une_emission_mixte_aux_extraits_par_livre_et_par_film_n_a_pas_de_doute() -> (
    None
):
    entiere = _fiche("du-dimanche-1", date(2025, 3, 2), {"cinéma", "livres"})
    livre = replace(_fiche("un-roman-2", date(2025, 3, 2), {"livres"}), extrait=True)
    film = replace(_fiche("un-film-3", date(2025, 3, 2), {"cinéma"}), extrait=True)

    _liste, doutes = construire_liste([entiere, livre, film])

    assert _types(doutes, "2025-03-02") == []


def _mage_du_kremlin() -> Attestation:
    """2026-01-14 : une fiche par livre, dont le fichier date de mars 2022."""
    return Attestation(
        source="radiofrance",
        source_id="le-mage-du-kremlin-de-giuliano-da-empoli-1192090",
        date=date(2026, 1, 14),
        themes=frozenset({"livres"}),
        url=_PAGE + "le-mage-du-kremlin-de-giuliano-da-empoli-1192090",
        enregistrements=(
            Enregistrement(
                _MEDIA + "14007-14.03.2022-ITEMA_24373986-2022F4007S0102-"
                "ITE_00156369_RSCE-27-fe21e419a0fb974761d3823a8ebef3a3.m4a",
                "extrait",
            ),
        ),
        extrait=True,
    )


def test_un_fichier_audio_date_d_un_autre_jour_signale_une_republication() -> None:
    _liste, doutes = construire_liste([_mage_du_kremlin()])

    (republication,) = [d for d in doutes if d.type == "republication"]
    assert (republication.emission_id, republication.source_id) == (
        "2026-01-14",
        "le-mage-du-kremlin-de-giuliano-da-empoli-1192090",
    )
    assert "2022-03-14" in republication.detail


def test_une_emission_attestee_seulement_par_des_extraits_est_fragile() -> None:
    _liste, doutes = construire_liste([_mage_du_kremlin()])

    assert "attestation fragile" in _types(doutes, "2026-01-14")


def test_une_emission_attestee_seulement_par_la_wayback_est_fragile() -> None:
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_24183916", date=date(2025, 6, 29)
    )

    _liste, doutes = construire_liste([podcast])

    assert "attestation fragile" in _types(doutes, "2025-06-29")


def test_lmelp_leve_les_doutes_de_theme_et_d_existence() -> None:
    # une fiche par livre, au fichier ancien et au thème contredit par un extrait
    fiche = replace(_mage_du_kremlin(), themes=frozenset({"cinéma"}))
    lmelp = _lmelp("le-mage-du-kremlin-de-giuliano-da-empoli-1192090", fiche.date)

    _liste, doutes = construire_liste([fiche, lmelp])

    assert _types(doutes, "2026-01-14") == []


def test_une_duree_ou_un_animateur_absent_n_est_pas_un_doute() -> None:
    # 1970 : année de transition, l'animateur n'est pas déduit ; aucune durée
    ina = Attestation(
        source="ina",
        source_id="PHD1970",
        date=date(1970, 3, 1),
        themes=frozenset({"livres"}),
    )

    liste, doutes = construire_liste([ina])

    assert (liste[0].duree, liste[0].animateur) == (None, None)
    assert doutes == []


def test_une_emission_attestee_par_des_extraits_et_la_wayback_est_fragile() -> None:
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_24373986", date=date(2026, 1, 14)
    )

    _liste, doutes = construire_liste([_mage_du_kremlin(), podcast])

    assert "attestation fragile" in _types(doutes, "2026-01-14")


def test_une_fiche_de_l_emission_entiere_n_est_pas_fragile() -> None:
    fiche = _fiche("le-masque-et-la-plume-du-dimanche-1", date(2025, 6, 1), {"livres"})
    podcast = Attestation(
        source="wayback_podcast", source_id="ITEMA_1", date=date(2025, 6, 1)
    )

    _liste, doutes = construire_liste([fiche, podcast])

    assert "attestation fragile" not in _types(doutes, "2025-06-01")


# --- Arbitrages ----------------------------------------------------------------


def _avignon() -> list[Attestation]:
    """2010-07-11 : « Festival d'Avignon », notice INA et extrait sans thème."""
    return [
        Attestation(
            source="ina",
            source_id="RD_4294389.001",
            date=date(2010, 7, 11),
            titre="Le masque et la plume du 11 juillet 2010",
        ),
        Attestation(
            source="radiofrance",
            source_id="festival-d-avignon-5488789",
            date=date(2010, 7, 11),
            titre="Festival d'Avignon",
            extrait=True,
        ),
    ]


def _theme(
    source: str, source_id: str, themes: set[str], jour: date = date(2026, 11, 10)
) -> Arbitrage:
    return Arbitrage(
        source=source,
        source_id=source_id,
        sorte="thème",
        themes=frozenset(themes),
        justification="titre explicite",
        date=datetime.combine(jour, datetime.min.time()),
    )


def test_un_arbitrage_de_theme_theatre_sort_l_emission_de_la_liste() -> None:
    arbitrage = _theme("radiofrance", "festival-d-avignon-5488789", {"théâtre"})

    liste, doutes = construire_liste(_avignon(), [arbitrage])

    assert liste == []
    assert _types(doutes, "2010-07-11") == []


def test_une_emission_coupee_en_deux_arbitree_cinema_sort_de_la_liste() -> None:
    # une attestation de chacune des deux émissions du 18 août 2024
    arbitrages = [
        _theme(
            "radiofrance",
            "le-masque-et-la-plume-du-dimanche-18-aout-2024-5609935",
            {"cinéma"},
        ),
        _theme("ina", "RD_16239327.001", {"cinéma"}),
    ]

    liste, doutes = construire_liste(_dimanche_18_aout_2024(), arbitrages)

    assert [e.id for e in liste] == []
    assert "thèmes divergents" not in _types(doutes, "2024-08-18")
    assert "thèmes divergents" not in _types(doutes, "2024-08-18-b")


def test_un_arbitrage_d_existence_retire_l_emission_et_ses_doutes() -> None:
    mage = _mage_du_kremlin()
    arbitrage = Arbitrage(
        source=mage.source,
        source_id=mage.source_id,
        sorte="existence",
        date=datetime(2026, 11, 10),
    )

    liste, doutes = construire_liste([mage], [arbitrage])

    assert liste == []
    assert doutes == []


def test_entre_deux_arbitrages_d_une_attestation_le_plus_recent_l_emporte() -> None:
    recent = _theme("radiofrance", "festival-d-avignon-5488789", {"livres", "théâtre"})
    ancien = _theme(
        "radiofrance", "festival-d-avignon-5488789", {"théâtre"}, date(2026, 1, 1)
    )

    liste, _doutes = construire_liste(_avignon(), [recent, ancien])

    assert [(e.id, e.themes) for e in liste] == [
        ("2010-07-11", frozenset({"livres", "théâtre"}))
    ]
    assert liste[0].arbitrage == recent


def test_un_arbitrage_sur_une_attestation_introuvable_est_orphelin() -> None:
    orphelin = _theme("radiofrance", "fiche-disparue-1", {"cinéma"})

    liste, doutes = construire_liste(_avignon(), [orphelin])

    assert [(e.id, e.themes) for e in liste] == [("2010-07-11", frozenset())]
    assert [
        (d.type, d.emission_id, d.dans_la_liste, d.source, d.source_id)
        for d in doutes
        if d.type == "arbitrage orphelin"
    ] == [("arbitrage orphelin", "", False, "radiofrance", "fiche-disparue-1")]


def test_a_date_egale_le_dernier_arbitrage_de_l_emission_l_emporte() -> None:
    ina = _theme("ina", "RD_4294389.001", {"théâtre"})
    fiche = _theme("radiofrance", "festival-d-avignon-5488789", {"livres", "théâtre"})

    liste, _doutes = construire_liste(_avignon(), [ina, fiche])

    assert liste[0].arbitrage == fiche


def test_un_arbitrage_qui_contredit_lmelp_est_un_doute() -> None:
    # 2018-01-21 : vérifiée par lmelp (livres), arbitrée cinéma
    fiche = _fiche("elena-ferrante-1", date(2018, 1, 21), {"livres"})
    lmelp = _lmelp("elena-ferrante-1", date(2018, 1, 21))
    arbitrage = _theme("radiofrance", "elena-ferrante-1", {"cinéma"})

    liste, doutes = construire_liste([fiche, lmelp], [arbitrage])

    assert liste == []
    assert [(d.type, d.emission_id, d.dans_la_liste, d.source_id) for d in doutes] == [
        ("contradiction lmelp", "2018-01-21", False, "elena-ferrante-1")
    ]


URL_AJAR = "https://media.radiofrance-podcast.net/podcast09/14007-18.10.1975-ITEMA_23787751-2024F4007E0106"


def test_la_duree_d_un_enregistrement_vaut_pour_ses_autres_encodages() -> None:
    fiche = Attestation(
        source="radiofrance",
        source_id="la-vie-devant-soi-d-emile-ajar",
        date=date(1975, 10, 18),
        duree="00:03:56",
        enregistrements=(
            Enregistrement(f"{URL_AJAR}-27.m4a", "extrait", duree="00:03:56"),
        ),
        extrait=True,
    )
    wayback = Attestation(
        source="wayback_podcast",
        source_id="ITEMA_23787751",
        date=date(1975, 10, 18),
        enregistrements=(Enregistrement(f"{URL_AJAR}-22.mp3", "extrait"),),
        extrait=True,
    )
    autre_fichier = Attestation(
        source="wayback_podcast",
        source_id="ITEMA_1",
        date=date(1975, 10, 18),
        enregistrements=(
            Enregistrement(
                "https://media.radiofrance-podcast.net/podcast09/14007-18.10.1975-ITEMA_1-1975F4007E0001-22.mp3",
                "extrait",
            ),
        ),
        extrait=True,
    )

    liste, _doutes = construire_liste([fiche, wayback, autre_fichier])

    assert [(e.url, e.duree) for e in liste[0].enregistrements] == [
        (f"{URL_AJAR}-27.m4a", "00:03:56"),
        (f"{URL_AJAR}-22.mp3", "00:03:56"),
        (autre_fichier.enregistrements[0].url, None),
    ]
    assert liste[0].duree is None  # un extrait ne dure pas autant que l'émission


def test_une_archive_redevenue_integrale_garde_sa_duree() -> None:
    attestations = _archive_hitchcock(duree="00:21:05")
    fiche = attestations[1]
    attestations[1] = replace(
        fiche,
        enregistrements=(replace(fiche.enregistrements[0], duree="00:21:05"),),
    )

    liste, _doutes = construire_liste(attestations)

    assert [(e.type, e.duree) for e in liste[0].enregistrements] == [
        ("intégral", "00:21:05"),
        ("intégral", "00:21:05"),
    ]


# --- Renvoi à l'écoute ----------------------------------------------------------


def _la_vie_devant_soi() -> Attestation:
    """1975-10-18 : un extrait de 4 minutes, « La Vie devant soi »."""
    return Attestation(
        source="radiofrance",
        source_id="la-vie-devant-soi-d-emile-ajar",
        date=date(1975, 10, 18),
        titre="La Vie devant soi d'Émile Ajar",
        enregistrements=(Enregistrement(f"{URL_AJAR}-27.m4a", "extrait"),),
        extrait=True,
    )


def _renvoi(source: str, source_id: str, jour: date = date(2026, 11, 10)) -> Arbitrage:
    return Arbitrage(
        source=source,
        source_id=source_id,
        sorte="écoute",
        date=datetime.combine(jour, datetime.min.time()),
    )


def test_un_renvoi_a_l_ecoute_marque_les_doutes_sans_les_lever() -> None:
    ajar = _la_vie_devant_soi()

    liste, doutes = construire_liste([ajar], [_renvoi(ajar.source, ajar.source_id)])

    assert [e.id for e in liste] == ["1975-10-18"]
    assert sorted((d.type, d.a_ecouter) for d in doutes) == [
        ("attestation fragile", True),
        ("thème inconnu", True),
    ]


def test_sans_renvoi_les_doutes_ne_sont_pas_a_ecouter() -> None:
    _liste, doutes = construire_liste([_la_vie_devant_soi()])

    assert doutes and not any(d.a_ecouter for d in doutes)


def test_un_arbitrage_de_theme_pose_apres_le_renvoi_le_remplace() -> None:
    ajar = _la_vie_devant_soi()
    renvoi = _renvoi(ajar.source, ajar.source_id, date(2026, 11, 1))
    theme = _theme(ajar.source, ajar.source_id, {"livres"})

    liste, doutes = construire_liste([ajar], [theme, renvoi])

    assert liste[0].arbitrage == theme
    assert [(d.type, d.a_ecouter) for d in doutes] == [("attestation fragile", False)]


def test_un_renvoi_ne_concerne_que_les_doutes_des_emissions_de_la_liste() -> None:
    # deux émissions le même jour, cinéma et théâtre : hors de la liste
    fiche = _fiche("pulp-fiction-1", date(1994, 5, 29), {"cinéma"})
    ina = Attestation(
        source="ina",
        source_id="PH_PHD2",
        date=date(1994, 5, 29),
        themes=frozenset({"théâtre"}),
    )

    liste, doutes = construire_liste([fiche, ina], [_renvoi("ina", "PH_PHD2")])

    assert liste == []
    assert [(d.type, d.dans_la_liste, d.a_ecouter) for d in doutes] == [
        ("collision", False, False)
    ]
