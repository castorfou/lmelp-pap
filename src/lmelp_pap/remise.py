"""La mise à disposition de lmelp d'un enregistrement qualifié.

Mettre à disposition (glossaire, *maturité d'un enregistrement*, niveau
valide) copie le fichier de l'enregistrement du dossier audio de pap
(``<année>/<nom>``) vers le dossier audio du back-office lmelp, sous le même
nom, en passant par un ``.part`` renommé à la fin. Un fichier de même nom déjà
présent fait refuser la mise à disposition, sans rien écrire, sauf s'il a
l'empreinte de l'enregistrement : c'est une mise à disposition interrompue
après la copie (panne), qui se termine (fiche, passage à valide).

La fiche rendue, écrite dans la collection ``pap_remises``, est prête à
devenir un document ``episodes`` de lmelp (schéma : ``docs/dev/architecture.md``,
section « Contrat ``pap_remises`` »). Sa description suit le format du flux
RSS (« durée : … - Le Masque et la Plume - par : animateur - résumé - équipe :
… - invités : … ») ; chaque morceau vient de la première source qui le donne :
page radiofrance.fr, puis API Radio France, puis notice INA, sinon l'animateur
déduit de la date. La source de chaque morceau est gardée dans
``sources_description``.

L'API Radio France n'est lue qu'au moment de la mise à disposition, avec un
jeton (``RADIOFRANCE_API_TOKEN``) ; ses données ne vont que dans la fiche,
et son absence ou son échec n'empêche rien.
"""

import contextlib
import hashlib
import os
from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, NamedTuple

from lmelp_pap.liste import Emission
from lmelp_pap.maturite import MORCEAU, Enregistrement, empreinte
from lmelp_pap.radiofrance_api import (
    ApiRadioFranceError,
    Personnalite,
    lire_diffusion,
)


MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
# L'ordre des sources de chaque morceau de la description (#62).
ORDRE = ("radiofrance", "api_radiofrance", "ina")


class RemiseError(ValueError):
    """Une mise à disposition impossible : niveau, fichier, collision."""


class Remise(NamedTuple):
    """Le résultat d'une mise à disposition : l'enregistrement devenu valide,
    sa fiche ``pap_remises``, et ``reprise`` si le fichier était déjà copié."""

    enregistrement: Enregistrement
    fiche: dict[str, Any]
    reprise: bool


def _copier(source: Path, final: Path, sha256: str | None) -> None:
    """Copie ``source`` vers ``final`` par un ``.part`` renommé, en vérifiant
    l'empreinte attendue. En cas d'échec, rien ne reste (ni ``.part``, ni
    dossier d'année créé pour l'occasion)."""
    annee_creee = not final.parent.exists()
    final.parent.mkdir(parents=True, exist_ok=True)
    partiel = final.with_name(final.name + ".part")
    h = hashlib.sha256()
    try:
        with source.open("rb") as lu, partiel.open("xb") as ecrit:
            for morceau in iter(lambda: lu.read(MORCEAU), b""):
                ecrit.write(morceau)
                h.update(morceau)
        if sha256 and h.hexdigest() != sha256:
            raise RemiseError(
                f"{source.name} : empreinte différente de celle du rapatriement"
            )
        if final.exists():  # apparu pendant la copie
            raise RemiseError(f"{final} existe déjà dans le dossier de lmelp")
        os.replace(partiel, final)
    except BaseException:
        partiel.unlink(missing_ok=True)
        if annee_creee:
            with contextlib.suppress(OSError):
                final.parent.rmdir()
        raise


def duree_du_fichier(chemin: Path) -> int | None:
    """La durée en secondes d'un fichier m4a, lue dans sa boîte ``mvhd`` ;
    ``None`` pour un fichier illisible ou d'un autre format."""
    try:
        with chemin.open("rb") as f:
            return _mvhd(f, chemin.stat().st_size)
    except (OSError, ValueError):
        return None


def _mvhd(f: Any, fin: int) -> int | None:
    """Parcourt les boîtes MP4 jusqu'à ``moov/mvhd``."""
    while f.tell() + 8 <= fin:
        debut = f.tell()
        taille = int.from_bytes(f.read(4), "big")
        nom = f.read(4)
        entete = 8
        if taille == 1:
            taille, entete = int.from_bytes(f.read(8), "big"), 16
        elif taille == 0:
            taille = fin - debut
        if taille < entete:
            return None
        if nom == b"moov":
            return _mvhd(f, debut + taille)
        if nom == b"mvhd":
            version = f.read(4)[0]
            if version == 1:
                f.read(16)
                echelle = int.from_bytes(f.read(4), "big")
                duree = int.from_bytes(f.read(8), "big")
            else:
                f.read(8)
                echelle = int.from_bytes(f.read(4), "big")
                duree = int.from_bytes(f.read(4), "big")
            return round(duree / echelle) if echelle else None
        f.seek(debut + taille)
    return None


def _secondes(horaire: str | None) -> int | None:
    """``HH:MM:SS`` en secondes."""
    if not horaire:
        return None
    try:
        h, m, s = (int(x) for x in horaire.split(":"))
    except ValueError:
        return None
    return h * 3600 + m * 60 + s


def _horaire(secondes: int) -> str:
    return f"{secondes // 3600:02d}:{secondes % 3600 // 60:02d}:{secondes % 60:02d}"


def _premier(
    emission: Emission, api: dict[str, str] | None, champ: str, cle_api: str
) -> tuple[str, str] | None:
    """La valeur d'un morceau et sa source, dans l'ordre de ``ORDRE``."""
    for source in ORDRE:
        if source == "api_radiofrance":
            if api and api.get(cle_api):
                return api[cle_api], source
            continue
        for a in emission.attestations:
            valeur = getattr(a, champ)
            if a.source == source and not a.extrait and valeur:
                return str(valeur), source
    return None


def _composer(
    emission: Emission, api: dict[str, str] | None, duree: tuple[int, str] | None
) -> tuple[str, dict[str, str]]:
    """La description au format du flux RSS, et la source de chaque morceau."""
    sources: dict[str, str] = {}
    morceaux: list[str] = []
    if duree:
        morceaux.append(f"durée : {_horaire(duree[0])}")
        sources["duree"] = duree[1]
    morceaux.append("Le Masque et la Plume")
    animateur = _premier(emission, api, "animateur", "animateur")
    if animateur is None and emission.animateur:
        animateur = (emission.animateur, "deduit")
    if animateur:
        morceaux.append(f"par : {animateur[0]}")
        sources["animateur"] = animateur[1]
    if resume := _premier(emission, api, "description", "resume"):
        morceaux.append(resume[0])
        sources["resume"] = resume[1]
    for cle, libelle in (("equipe", "équipe"), ("invites", "invités")):
        if api and api.get(cle):
            morceaux.append(f"{libelle} : {api[cle]}")
            sources[cle] = "api_radiofrance"
    return " - ".join(morceaux), sources


def _titre(jour: date) -> str:
    numero = "1er" if jour.day == 1 else str(jour.day)
    return f"Le Masque et la Plume du {numero} {MOIS[jour.month - 1]} {jour.year}"


def mettre_a_disposition(
    enregistrement: Enregistrement,
    emission: Emission,
    audios: Path,
    audios_lmelp: Path,
    maintenant: datetime,
    api: dict[str, str] | None = None,
) -> Remise:
    """Copie le fichier d'un enregistrement qualifié dans
    ``audios_lmelp/<année>/<nom>`` et rend l'enregistrement valide et sa fiche
    pour ``pap_remises``. ``api`` : les morceaux lus dans l'API Radio France
    (``lire_api``), ou ``None``. ``RemiseError`` sans rien écrire si
    l'enregistrement n'est pas qualifié, si son fichier manque ou a changé, ou
    si un fichier de même nom et d'une autre empreinte existe chez lmelp ; de
    même empreinte, la copie est tenue pour faite (``reprise``)."""
    if enregistrement.niveau != "qualifie" or not enregistrement.fichier:
        raise RemiseError(
            f"{enregistrement.url} : niveau {enregistrement.niveau}, "
            "seul un enregistrement qualifié se met à disposition de lmelp"
        )
    relatif = enregistrement.fichier
    source = audios / relatif
    if not source.is_file():
        raise RemiseError(f"{relatif} : fichier introuvable dans le dossier de pap")
    final = audios_lmelp / relatif
    reprise = final.exists()
    if reprise and not (
        enregistrement.sha256
        and final.is_file()
        and empreinte(final) == enregistrement.sha256
    ):
        raise RemiseError(f"{relatif} existe déjà dans le dossier de lmelp")
    if not reprise:
        _copier(source, final, enregistrement.sha256)

    secondes = duree_du_fichier(final)
    duree = (secondes, "fichier") if secondes else None
    if duree is None:
        for source_duree in ("radiofrance", "ina"):
            for a in emission.attestations:
                s = _secondes(a.duree) if a.source == source_duree else None
                if s and not a.extrait and duree is None:
                    duree = (s, source_duree)
    description, sources = _composer(emission, api, duree)
    page = next(
        (
            a.url
            for a in emission.attestations
            if a.source == "radiofrance" and not a.extrait and a.url
        ),
        None,
    )
    fiche = {
        "_id": enregistrement.url,
        "emission_id": emission.id,
        "titre": _titre(emission.date),
        "date": datetime(
            emission.date.year, emission.date.month, emission.date.day, tzinfo=UTC
        ),
        "type": "livres",
        "duree": duree[0] if duree else None,
        "description": description,
        "sources_description": sources,
        "episode_page_url": page,
        "url": enregistrement.url if enregistrement.url.startswith("http") else None,
        "audio_rel_filename": relatif,
        "sha256": enregistrement.sha256,
        "date_remise": maintenant,
    }
    entrees = {**enregistrement.entrees, "valide": maintenant}
    valide = replace(enregistrement, niveau="valide", entrees=entrees)
    return Remise(valide, fiche, reprise)


def lire_api(
    session: Any, jeton: str, jour: date, pages: Iterable[str] = ()
) -> dict[str, str] | None:
    """Les morceaux de description que l'API Radio France donne pour la
    diffusion du Masque de ce jour (client ``radiofrance_api`` ; ``pages`` :
    les pages radiofrance.fr connues de l'émission) : ``animateur``
    (producteur), ``resume`` (chapô), ``equipe``, ``invites``. ``None`` sans
    diffusion ce jour-là, ou si l'API échoue. Rien n'est conservé."""
    try:
        diffusion = lire_diffusion(jour, pages, jeton, session)
    except ApiRadioFranceError:
        return None  # l'API ne bloque jamais la mise à disposition
    if diffusion is None:
        return None

    def noms(personnes: tuple[Personnalite, ...]) -> str:
        return ", ".join(p.nom for p in personnes)

    morceaux = {
        "animateur": noms(diffusion.animateurs),
        "resume": (diffusion.resume or "").strip(),
        "equipe": noms(diffusion.equipe),
        "invites": noms(diffusion.invites),
    }
    return {k: v for k, v in morceaux.items() if v}
