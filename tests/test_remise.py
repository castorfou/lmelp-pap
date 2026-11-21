"""La mise à disposition de lmelp d'un enregistrement qualifié (module
``remise``) : copie du fichier dans le dossier audio du back-office, fiche de
``pap_remises``, passage à valide."""

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap.liste import Attestation, Emission
from lmelp_pap.maturite import Enregistrement
from lmelp_pap.remise import (
    RemiseError,
    duree_du_fichier,
    lire_api,
    mettre_a_disposition,
)


MAINTENANT = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
NOM = "14007-28.09.2014-ITEMA_20674220-2014F4007S0271-27.m4a"
URL = f"https://media.radiofrance-podcast.net/podcast09/{NOM}"
PAGE = (
    "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"
    "les-livres-a-lire-2989961"
)
SON = b"ID3" + bytes(range(256)) * 40
EMPREINTE = hashlib.sha256(SON).hexdigest()


def qualifie(audios: Path) -> Enregistrement:
    (audios / "2014").mkdir(parents=True, exist_ok=True)
    (audios / "2014" / NOM).write_bytes(SON)
    return Enregistrement(
        url=URL,
        emission_id="2014-09-28",
        source="radiofrance",
        niveau="qualifie",
        entrees={"qualifie": datetime(2026, 11, 20, tzinfo=UTC)},
        fichier=f"2014/{NOM}",
        sha256=EMPREINTE,
        taille=len(SON),
    )


def emission(*attestations: Attestation, animateur: str | None = None) -> Emission:
    return Emission(
        id="2014-09-28",
        date=date(2014, 9, 28),
        themes=frozenset({"livres"}),
        animateur=animateur,
        attestations=list(attestations),
    )


RADIOFRANCE = Attestation(
    source="radiofrance",
    source_id="les-livres-a-lire-2989961",
    date=date(2014, 9, 28),
    titre="Les livres à lire",
    description="Les critiques parlent de la rentrée.",
    animateur="Jérôme Garcin",
    duree="00:54:12",
    url=PAGE,
)
INA = Attestation(
    source="ina",
    source_id="PH_1",
    date=date(2014, 9, 28),
    description="Résumé de l'INA.",
    animateur="Animateur INA",
)


@pytest.fixture
def dossiers(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "audios", tmp_path / "audios-lmelp"


def test_mettre_a_disposition_copie_le_fichier_et_rend_valide(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers
    enregistrement = qualifie(audios)

    valide, fiche = mettre_a_disposition(
        enregistrement, emission(RADIOFRANCE), audios, lmelp, MAINTENANT
    )

    assert (lmelp / "2014" / NOM).read_bytes() == SON
    assert not list(lmelp.rglob("*.part"))
    assert (audios / "2014" / NOM).exists()  # l'original reste dans pap
    assert valide.niveau == "valide"
    assert valide.entrees["valide"] == MAINTENANT
    assert valide.entrees["qualifie"] == enregistrement.entrees["qualifie"]
    assert fiche["_id"] == URL
    assert fiche["emission_id"] == "2014-09-28"
    assert fiche["audio_rel_filename"] == f"2014/{NOM}"
    assert fiche["sha256"] == EMPREINTE
    assert fiche["type"] == "livres"
    assert fiche["titre"] == "Le Masque et la Plume du 28 septembre 2014"
    assert fiche["date"] == datetime(2014, 9, 28, tzinfo=UTC)
    assert fiche["episode_page_url"] == PAGE
    assert fiche["url"] == URL
    assert fiche["date_remise"] == MAINTENANT


def test_une_collision_de_nom_est_refusee_sans_rien_ecrire(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers
    (lmelp / "2014").mkdir(parents=True)
    (lmelp / "2014" / NOM).write_bytes(b"le fichier de lmelp")

    with pytest.raises(RemiseError, match="existe déjà"):
        mettre_a_disposition(
            qualifie(audios), emission(RADIOFRANCE), audios, lmelp, MAINTENANT
        )

    assert (lmelp / "2014" / NOM).read_bytes() == b"le fichier de lmelp"
    assert [p.name for p in (lmelp / "2014").iterdir()] == [NOM]


@pytest.mark.parametrize("niveau", ["rapatrie", "valide", "telechargeable"])
def test_seul_un_enregistrement_qualifie_se_met_a_disposition(
    dossiers: tuple[Path, Path], niveau: str
) -> None:
    audios, lmelp = dossiers
    enregistrement = replace(qualifie(audios), niveau=niveau)

    with pytest.raises(RemiseError, match="qualifié"):
        mettre_a_disposition(
            enregistrement, emission(RADIOFRANCE), audios, lmelp, MAINTENANT
        )

    assert not lmelp.exists()


def test_un_fichier_altere_est_refuse_sans_rien_laisser(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers
    enregistrement = qualifie(audios)
    (audios / "2014" / NOM).write_bytes(b"autre chose")

    with pytest.raises(RemiseError, match="empreinte"):
        mettre_a_disposition(
            enregistrement, emission(RADIOFRANCE), audios, lmelp, MAINTENANT
        )

    assert not list(lmelp.rglob("*.*"))  # ni fichier, ni .part
    assert not (lmelp / "2014").exists()


def test_un_fichier_absent_est_refuse(dossiers: tuple[Path, Path]) -> None:
    audios, lmelp = dossiers
    enregistrement = qualifie(audios)
    (audios / "2014" / NOM).unlink()

    with pytest.raises(RemiseError, match="introuvable"):
        mettre_a_disposition(
            enregistrement, emission(RADIOFRANCE), audios, lmelp, MAINTENANT
        )


# --- la description composée (#62) -----------------------------------------


def test_la_description_prend_la_page_radiofrance_d_abord(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers

    _, fiche = mettre_a_disposition(
        qualifie(audios), emission(INA, RADIOFRANCE), audios, lmelp, MAINTENANT
    )

    assert fiche["description"] == (
        "durée : 00:54:12 - Le Masque et la Plume - par : Jérôme Garcin"
        " - Les critiques parlent de la rentrée."
    )
    assert fiche["sources_description"] == {
        "duree": "radiofrance",
        "animateur": "radiofrance",
        "resume": "radiofrance",
    }
    assert fiche["duree"] == 54 * 60 + 12


def test_sans_page_radiofrance_l_api_puis_l_ina(dossiers: tuple[Path, Path]) -> None:
    audios, lmelp = dossiers
    api = {
        "animateur": "Jérôme Garcin",
        "resume": "Le chapô de l'API.",
        "equipe": "Ilinca Negulesco",
        "invites": "Arnaud Viviant, Elisabeth Philippe",
    }

    _, fiche = mettre_a_disposition(
        qualifie(audios), emission(INA), audios, lmelp, MAINTENANT, api=api
    )

    assert fiche["description"] == (
        "Le Masque et la Plume - par : Jérôme Garcin - Le chapô de l'API."
        " - équipe : Ilinca Negulesco - invités : Arnaud Viviant, Elisabeth Philippe"
    )
    assert fiche["sources_description"] == {
        "animateur": "api_radiofrance",
        "resume": "api_radiofrance",
        "equipe": "api_radiofrance",
        "invites": "api_radiofrance",
    }
    assert fiche["episode_page_url"] is None


def test_sans_api_l_ina_donne_resume_et_animateur(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers

    _, fiche = mettre_a_disposition(
        qualifie(audios), emission(INA), audios, lmelp, MAINTENANT
    )

    assert fiche["description"] == (
        "Le Masque et la Plume - par : Animateur INA - Résumé de l'INA."
    )
    assert fiche["sources_description"] == {"animateur": "ina", "resume": "ina"}


def test_sans_aucune_source_l_animateur_est_deduit_de_la_date(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers

    _, fiche = mettre_a_disposition(
        qualifie(audios),
        emission(animateur="Jérôme Garcin"),
        audios,
        lmelp,
        MAINTENANT,
    )

    assert fiche["description"] == "Le Masque et la Plume - par : Jérôme Garcin"
    assert fiche["sources_description"] == {"animateur": "deduit"}
    assert fiche["duree"] is None  # SON n'est pas un m4a lisible


# --- la durée calculée sur le fichier ----------------------------------------


def _boite(nom: bytes, contenu: bytes) -> bytes:
    return (8 + len(contenu)).to_bytes(4, "big") + nom + contenu


def _m4a(secondes: int, echelle: int = 44100) -> bytes:
    mvhd = (
        bytes(4)  # version 0, drapeaux
        + bytes(8)  # création, modification
        + echelle.to_bytes(4, "big")
        + (secondes * echelle).to_bytes(4, "big")
        + bytes(80)
    )
    return _boite(b"ftyp", b"M4A \x00\x00\x00\x00") + _boite(
        b"moov", _boite(b"mvhd", mvhd)
    )


def test_la_duree_d_un_m4a_se_lit_dans_son_entete(tmp_path: Path) -> None:
    chemin = tmp_path / "a.m4a"
    chemin.write_bytes(_m4a(2893))
    assert duree_du_fichier(chemin) == 2893


def test_une_duree_illisible_rend_none(tmp_path: Path) -> None:
    chemin = tmp_path / "a.mp3"
    chemin.write_bytes(SON)
    assert duree_du_fichier(chemin) is None


def test_la_duree_du_fichier_l_emporte_sur_celle_des_sources(
    dossiers: tuple[Path, Path],
) -> None:
    audios, lmelp = dossiers
    enregistrement = qualifie(audios)
    contenu = _m4a(3000)
    (audios / "2014" / NOM).write_bytes(contenu)
    enregistrement = replace(enregistrement, sha256=hashlib.sha256(contenu).hexdigest())

    _, fiche = mettre_a_disposition(
        enregistrement, emission(RADIOFRANCE), audios, lmelp, MAINTENANT
    )

    assert fiche["duree"] == 3000
    assert fiche["description"].startswith("durée : 00:50:00 - ")
    assert fiche["sources_description"]["duree"] == "fichier"


# --- l'API Radio France, lue seulement avec un jeton ------------------------


class ReponseApi:
    def __init__(self, donnees: Any, statut: int = 200):
        self.status_code = statut
        self._donnees = donnees

    def json(self) -> Any:
        return self._donnees


def _diffusion(jour: str, url: str = "", **champs: Any) -> dict[str, Any]:
    horodatage = int(datetime.fromisoformat(jour + "T10:00:00+02:00").timestamp())
    return {
        "node": {
            "url": url,
            "published_date": str(horodatage),
            "standFirst": champs.get("chapo"),
            "personalitiesConnection": {
                "edges": [
                    {"relation": r, "node": {"name": n}}
                    for r, n in champs.get("personnes", [])
                ]
            },
        },
        "cursor": jour,
    }


class SessionApi:
    """Une API Radio France factice : des pages de diffusions, de la plus
    récente à la plus ancienne."""

    def __init__(self, pages: list[list[dict[str, Any]]], statut: int = 200):
        self.pages = pages
        self.statut = statut
        self.demandes: list[dict[str, Any]] = []

    def post(self, url: str, **options: Any) -> ReponseApi:
        self.demandes.append({"url": url, **options})
        page = self.pages[len(self.demandes) - 1]
        return ReponseApi(
            {
                "data": {
                    "diffusionsOfShowByUrl": {
                        "edges": page,
                        "pageInfo": {
                            "hasNextPage": len(self.demandes) < len(self.pages),
                            "endCursor": page[-1]["cursor"] if page else None,
                        },
                    }
                }
            },
            self.statut,
        )


def test_lire_api_trouve_la_diffusion_du_jour_en_remontant_les_pages() -> None:
    session = SessionApi(
        [
            [_diffusion("2026-11-15"), _diffusion("2020-01-05")],
            [
                _diffusion(
                    "2014-09-28",
                    chapo="Le chapô.",
                    personnes=[
                        ("producer", "Jérôme Garcin"),
                        ("staff", "Ilinca Negulesco"),
                        ("guest", "Arnaud Viviant"),
                        ("guest", "Elisabeth Philippe"),
                        ("tag", "Roman"),
                    ],
                ),
                _diffusion("2014-09-21"),
            ],
            [_diffusion("2014-09-14")],
        ]
    )

    api = lire_api(session, "jeton", date(2014, 9, 28))

    assert api == {
        "animateur": "Jérôme Garcin",
        "resume": "Le chapô.",
        "equipe": "Ilinca Negulesco",
        "invites": "Arnaud Viviant, Elisabeth Philippe",
    }
    assert len(session.demandes) == 2  # la page plus ancienne n'est pas lue
    assert session.demandes[0]["headers"]["x-token"] == "jeton"
    assert session.demandes[0]["url"] == "https://openapi.radiofrance.fr/v1/graphql"


def test_lire_api_sans_diffusion_ce_jour_rend_none() -> None:
    session = SessionApi([[_diffusion("2014-10-05"), _diffusion("2014-09-21")]])
    assert lire_api(session, "jeton", date(2014, 9, 28)) is None


def test_une_api_en_erreur_ne_bloque_pas() -> None:
    assert lire_api(SessionApi([[]], statut=403), "jeton", date(2014, 9, 28)) is None
