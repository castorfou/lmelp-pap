"""Écriture de la liste des émissions en CSV liés (ADR 0001)."""

import csv
from datetime import date
from pathlib import Path

from lmelp_pap.ecriture import ecrire_liste
from lmelp_pap.liste import (
    Attestation,
    Emission,
    Enregistrement,
    Rapport,
    construire_liste,
)


AUDIO = "https://media.radiofrance-podcast.net/podcast09/14007-04.12.1958-ITEMA_1.m4a"


def _lire(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _liste_exemple() -> tuple[list[Emission], Rapport]:
    return construire_liste(
        [
            Attestation(
                source="ina",
                source_id="PH_PHD1",
                date=date(1958, 12, 4),
                themes=frozenset({"théâtre", "livres"}),
                titre="Théâtre et littérature",
                chaine="Paris Inter",
                url="https://catalogue.ina.fr/doc/TV-RADIO/PH_PHD1/theatre",
            ),
            Attestation(
                source="wayback_podcast",
                source_id="ITEMA_1",
                date=date(1958, 12, 4),
                enregistrements=(Enregistrement(url=AUDIO, type="extrait"),),
            ),
            Attestation(source="ina", source_id="PH_PHD2", date=date(1956, 1, 22)),
        ]
    )


def test_la_liste_est_ecrite_en_trois_csv_lies_par_l_identifiant(
    tmp_path: Path,
) -> None:
    liste, rapport = _liste_exemple()

    ecrire_liste(liste, rapport, tmp_path)

    emissions = _lire(tmp_path / "emissions.csv")
    assert [e["id"] for e in emissions] == ["1956-01-22", "1958-12-04"]
    assert emissions[1] == {
        "id": "1958-12-04",
        "date": "1958-12-04",
        "themes": "livres;théâtre",
        "titre": "Théâtre et littérature",
        "description": "",
        "animateur": "Michel Polac, François-Régis Bastide",
        "chaine": "Paris Inter",
        "heure": "",
        "duree": "",
    }
    assert emissions[0]["themes"] == ""  # thème inconnu

    attestations = _lire(tmp_path / "attestations.csv")
    assert [(a["emission_id"], a["source"], a["source_id"]) for a in attestations] == [
        ("1956-01-22", "ina", "PH_PHD2"),
        ("1958-12-04", "ina", "PH_PHD1"),
        ("1958-12-04", "wayback_podcast", "ITEMA_1"),
    ]
    assert attestations[1]["url"] == (
        "https://catalogue.ina.fr/doc/TV-RADIO/PH_PHD1/theatre"
    )

    assert _lire(tmp_path / "enregistrements.csv") == [
        {
            "emission_id": "1958-12-04",
            "url": AUDIO,
            "type": "extrait",
            "sources": "wayback_podcast",
        }
    ]


def test_le_rapport_de_rapprochement_est_ecrit_a_cote(tmp_path: Path) -> None:
    liste, rapport = construire_liste(
        [
            Attestation(
                source="ina",
                source_id="PH_PHD1",
                date=date(1956, 1, 19),
                themes=frozenset({"livres"}),
            ),
            Attestation(
                source="wayback_podcast", source_id="ITEMA_1", date=date(1956, 1, 22)
            ),
        ]
    )

    ecrire_liste(liste, rapport, tmp_path)

    (signalement,) = _lire(tmp_path / "rapport_rapprochement.csv")
    assert signalement["type"] == "désaccord de date"
    assert signalement["emission_id"] == "1956-01-19"


def test_un_enregistrement_retype_garde_les_sources_qui_le_donnent(
    tmp_path: Path,
) -> None:
    # radiofrance.fr sait que l'archive est un extrait ; la Wayback ne voit
    # que la lettre S du fichier et le donne pour intégral
    mp3 = "https://media.radiofrance-podcast.net/podcast09/14007-12.02.2024-ITEMA_2-2024F4007S0043-22.mp3"
    m4a = mp3.replace("-22.mp3", "-27.m4a")
    liste, rapport = construire_liste(
        [
            Attestation(
                source="radiofrance",
                source_id="fabriquer-une-femme",
                date=date(2024, 2, 11),
                duree="00:11:22",
                enregistrements=(Enregistrement(url=m4a, type="extrait"),),
                extrait=True,
            ),
            Attestation(
                source="wayback_podcast",
                source_id="ITEMA_2",
                date=date(2024, 2, 11),
                enregistrements=(Enregistrement(url=mp3, type="intégral"),),
            ),
        ]
    )

    ecrire_liste(liste, rapport, tmp_path)

    lignes = _lire(tmp_path / "enregistrements.csv")
    assert [(r["url"], r["type"], r["sources"]) for r in lignes] == [
        (m4a, "extrait", "radiofrance"),
        (mp3, "extrait", "wayback_podcast"),
    ]
