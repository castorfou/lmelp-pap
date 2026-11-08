"""Lecture des réponses de l'API CDX de la Wayback Machine (lignes réelles)."""

from datetime import date
from pathlib import Path

from lmelp_pap.liste import Enregistrement
from lmelp_pap.sources.wayback_podcast import lire_cdx


FIXTURES = Path(__file__).parent / "fixtures" / "wayback"
MEDIA = "https://media.radiofrance-podcast.net/podcast09/"


def test_les_fichiers_du_podcast_attestent_une_emission_par_identifiant_itema() -> None:
    texte = (FIXTURES / "cdx_podcast.txt").read_text(encoding="utf-8")

    attestations = {a.source_id: a for a in lire_cdx(texte)}

    assert sorted(attestations) == [
        "ITEMA_20496304",
        "ITEMA_21183424",
        "ITEMA_23820437",
        "ITEMA_24153905",
    ]
    archive_1967 = attestations["ITEMA_23820437"]
    assert archive_1967.source == "wayback_podcast"
    assert archive_1967.date == date(1967, 1, 1)
    assert archive_1967.themes == frozenset()
    assert archive_1967.enregistrements == (
        Enregistrement(
            url=MEDIA + "14007-01.01.1967-ITEMA_23820437-1967F4007E0001-22.mp3",
            type="extrait",
        ),
        Enregistrement(
            url=MEDIA + "14007-01.01.1967-ITEMA_23820437-1967F4007E0001-27.m4a",
            type="extrait",
        ),
    )
    assert attestations["ITEMA_21183424"].enregistrements == (
        Enregistrement(
            url=MEDIA + "14007-01.01.2017-ITEMA_21183424-0.mp3", type="intégral"
        ),
    )


def test_une_capture_en_echec_atteste_l_emission_sans_enregistrement() -> None:
    texte = (FIXTURES / "cdx_podcast.txt").read_text(encoding="utf-8")

    attestations = {a.source_id: a for a in lire_cdx(texte)}

    assert attestations["ITEMA_20496304"].date == date(2013, 6, 30)
    assert attestations["ITEMA_20496304"].enregistrements == ()  # capture 404
    assert attestations["ITEMA_24153905"].date == date(2025, 6, 1)
    assert attestations["ITEMA_24153905"].enregistrements == ()  # capture sans statut
