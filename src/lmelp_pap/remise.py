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
section « Contrat ``pap_remises`` »). Sa description suit le format des
descriptions du flux RSS du Masque (« durée : HH:MM:SS  - Le Masque et la
Plume - par : animateur - résumé - équipe : noms - invités : nom rôle, … ») ;
chaque morceau vient de la première source qui le donne :
page radiofrance.fr, puis API Radio France, puis notice INA, sinon l'animateur
déduit de la date. La source de chaque morceau est gardée dans
``sources_description``.

La diffusion de l'API Radio France (``radiofrance_api.Diffusion``) est lue
par l'appelant ; ses données ne vont que dans la fiche, et son absence
n'empêche rien.
"""

import contextlib
import hashlib
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, NamedTuple

from lmelp_pap.liste import Emission
from lmelp_pap.maturite import MORCEAU, Enregistrement, empreinte
from lmelp_pap.radiofrance_api import Diffusion, Personnalite


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


def _noms(personnes: tuple[Personnalite, ...], roles: bool = False) -> str:
    """Les noms, séparés par des virgules ; avec ``roles``, chacun suivi de son
    rôle, comme les invités du flux RSS (« Arnaud Viviant Critique
    littéraire (Revue Regards) »)."""
    return ", ".join(
        f"{p.nom} {p.role.strip()}" if roles and p.role and p.role.strip() else p.nom
        for p in personnes
    )


def _premier(emission: Emission, api: str | None, champ: str) -> tuple[str, str] | None:
    """La valeur d'un morceau et sa source, dans l'ordre de ``ORDRE`` :
    ``api``, la valeur de l'API Radio France pour ce morceau."""
    for source in ORDRE:
        if source == "api_radiofrance":
            if api:
                return api, source
            continue
        for a in emission.entieres(source):
            if valeur := getattr(a, champ):
                return str(valeur), source
    return None


def _composer(
    emission: Emission, api: Diffusion | None, duree: tuple[int, str] | None
) -> tuple[str, dict[str, str]]:
    """La description au format du flux RSS, et la source de chaque morceau.

    Le flux sépare ses morceaux par « - », avec deux espaces après la durée
    (« durée : 00:48:14  - Le Masque et la Plume - par : … »)."""
    sources: dict[str, str] = {}
    morceaux: list[str] = []
    # les morceaux que donne l'API, vides sans diffusion
    du_api = {
        "animateur": _noms(api.animateurs) if api else "",
        "resume": (api.resume or "").strip() if api else "",
        "equipe": _noms(api.equipe) if api else "",
        "invites": _noms(api.invites, roles=True) if api else "",
    }
    animateur = _premier(emission, du_api["animateur"], "animateur")
    if animateur is None and emission.animateur:
        animateur = (emission.animateur, "deduit")
    if animateur:
        morceaux.append(f"par : {animateur[0]}")
        sources["animateur"] = animateur[1]
    if resume := _premier(emission, du_api["resume"], "description"):
        morceaux.append(resume[0])
        sources["resume"] = resume[1]
    for cle, libelle in (("equipe", "équipe"), ("invites", "invités")):
        if du_api[cle]:
            morceaux.append(f"{libelle} : {du_api[cle]}")
            sources[cle] = "api_radiofrance"
    description = " - ".join(["Le Masque et la Plume", *morceaux])
    if duree:
        description = f"durée : {_horaire(duree[0])}  - {description}"
        sources = {"duree": duree[1], **sources}
    return description, sources


def _titre(jour: date) -> str:
    numero = "1er" if jour.day == 1 else str(jour.day)
    return f"Le Masque et la Plume du {numero} {MOIS[jour.month - 1]} {jour.year}"


def mettre_a_disposition(
    enregistrement: Enregistrement,
    emission: Emission,
    audios: Path,
    audios_lmelp: Path,
    maintenant: datetime,
    api: Diffusion | None = None,
) -> Remise:
    """Copie le fichier d'un enregistrement qualifié dans
    ``audios_lmelp/<année>/<nom>`` et rend l'enregistrement valide et sa fiche
    pour ``pap_remises``. ``api`` : la diffusion lue dans l'API Radio
    France, ou ``None``. ``RemiseError`` sans rien écrire si
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
        duree = next(
            (
                (s, source_duree)
                for source_duree in ("radiofrance", "ina")
                for a in emission.entieres(source_duree)
                if (s := _secondes(a.duree))
            ),
            None,
        )
    description, sources = _composer(emission, api, duree)
    page = next(iter(emission.pages_radiofrance), None)
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
