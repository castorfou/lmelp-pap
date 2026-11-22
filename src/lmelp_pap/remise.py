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
    """La durée en secondes d'un fichier m4a (boîte ``mvhd``) ou mp3 (en-tête
    Xing, Info ou VBRI, sinon débit constant) ; ``None`` pour un fichier
    illisible ou d'un autre format."""
    try:
        with chemin.open("rb") as f:
            taille = chemin.stat().st_size
            duree = _mvhd(f, taille)
            if duree is None:
                f.seek(0)
                duree = _duree_mp3(f, taille)
            return duree
    except (OSError, ValueError):
        return None


# Les débits (kbit/s) des couches III, MPEG-1 puis MPEG-2/2.5, par index.
_DEBITS = (
    (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
    (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
)
# Les fréquences (Hz) par version MPEG (bits 19-20 de l'en-tête) et index.
_FREQUENCES = {
    3: (44100, 48000, 32000),
    2: (22050, 24000, 16000),
    0: (11025, 12000, 8000),
}


def _trame_mp3(entete: bytes) -> tuple[int, int, int, int, bool] | None:
    """Une trame MPEG couche III : (débit en bit/s, fréquence, échantillons par
    trame, longueur en octets, mono) ; ``None`` si ce n'en est pas une."""
    if len(entete) < 4:
        return None
    mot = int.from_bytes(entete[:4], "big")
    version, couche = (mot >> 19) & 3, (mot >> 17) & 3
    i_debit, i_frequence = (mot >> 12) & 15, (mot >> 10) & 3
    if mot >> 21 != 0x7FF or version == 1 or couche != 1:
        return None
    if i_debit in (0, 15) or i_frequence == 3:
        return None
    mpeg1 = version == 3
    debit = _DEBITS[0 if mpeg1 else 1][i_debit] * 1000
    frequence = _FREQUENCES[version][i_frequence]
    echantillons = 1152 if mpeg1 else 576
    longueur = echantillons // 8 * debit // frequence + ((mot >> 9) & 1)
    return debit, frequence, echantillons, longueur, (mot >> 6) & 3 == 3


def _duree_mp3(f: Any, fin: int) -> int | None:
    """La durée d'un mp3 : saute le tag ID3v2, lit la première trame ; le
    nombre de trames de son en-tête Xing/Info ou VBRI, sinon (débit
    constant) la taille du flux et le débit, confirmé par la trame suivante."""
    debut = 0
    tete = f.read(10)
    if tete[:3] == b"ID3" and len(tete) == 10:
        debut = 10 + sum(b << s for b, s in zip(tete[6:10], (21, 14, 7, 0)))
    f.seek(debut)
    premiere = f.read(200)
    trame = _trame_mp3(premiere)
    if trame is None:
        return None
    debit, frequence, echantillons, longueur, mono = trame
    mpeg1 = echantillons == 1152
    annexe = (17 if mono else 32) if mpeg1 else (9 if mono else 17)
    xing = premiere[4 + annexe : 4 + annexe + 12]
    nombre = None
    if xing[:4] in (b"Xing", b"Info") and int.from_bytes(xing[4:8], "big") & 1:
        nombre = int.from_bytes(xing[8:12], "big")
    elif premiere[36:40] == b"VBRI":
        nombre = int.from_bytes(premiere[50:54], "big")
    if nombre:
        return round(nombre * echantillons / frequence)
    f.seek(debut + longueur)
    if _trame_mp3(f.read(4)) is None:
        return None
    return round((fin - debut) * 8 / debit)


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
    # l'équipe et les invités : l'API, sinon le générique de la notice INA
    for cle, libelle in (("equipe", "équipe"), ("invites", "invités")):
        if du_api[cle]:
            morceaux.append(f"{libelle} : {du_api[cle]}")
            sources[cle] = "api_radiofrance"
        elif noms := next(
            (getattr(a, cle) for a in emission.entieres("ina") if getattr(a, cle)),
            (),
        ):
            morceaux.append(f"{libelle} : {', '.join(noms)}")
            sources[cle] = "ina"
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

    fiche = _fiche(enregistrement, emission, final, maintenant, api)
    entrees = {**enregistrement.entrees, "valide": maintenant}
    valide = replace(enregistrement, niveau="valide", entrees=entrees)
    return Remise(valide, fiche, reprise)


def apercu_fiche(
    enregistrement: Enregistrement,
    emission: Emission,
    audios: Path,
    api: Diffusion | None = None,
) -> dict[str, Any]:
    """La fiche ``pap_remises`` que recevrait lmelp si l'enregistrement
    qualifié était mis à disposition maintenant, sans rien copier ni écrire
    (``date_remise`` vide). ``RemiseError`` si l'enregistrement n'est pas
    qualifié ou n'a pas de fichier."""
    if enregistrement.niveau != "qualifie" or not enregistrement.fichier:
        raise RemiseError(
            f"{enregistrement.url} : niveau {enregistrement.niveau}, "
            "seul un enregistrement qualifié a un aperçu de sa fiche"
        )
    fiche = _fiche(enregistrement, emission, audios / enregistrement.fichier, None, api)
    return fiche


def _fiche(
    enregistrement: Enregistrement,
    emission: Emission,
    fichier: Path,
    maintenant: datetime | None,
    api: Diffusion | None,
) -> dict[str, Any]:
    """La fiche ``pap_remises`` de l'enregistrement ; la durée vient de
    ``fichier`` s'il est lisible."""
    relatif = enregistrement.fichier
    secondes = duree_du_fichier(fichier) if fichier.is_file() else None
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
    return {
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


def annuler_mise_a_disposition(
    enregistrement: Enregistrement, audios_lmelp: Path
) -> tuple[Enregistrement, Path | None]:
    """Ramène un enregistrement valide à qualifié et retire sa copie du
    dossier audio de lmelp, si elle a encore son empreinte (un fichier
    remplacé chez lmelp est gardé). Rend l'enregistrement qualifié et le
    chemin retiré (``None`` si rien n'a été retiré). ``RemiseError`` si
    l'enregistrement n'est pas valide. La fiche ``pap_remises`` est retirée
    par l'appelant."""
    if enregistrement.niveau != "valide" or not enregistrement.fichier:
        raise RemiseError(
            f"{enregistrement.url} : niveau {enregistrement.niveau}, "
            "seule une mise à disposition (valide) s'annule"
        )
    copie = audios_lmelp / enregistrement.fichier
    retiree = None
    if (
        enregistrement.sha256
        and copie.is_file()
        and empreinte(copie) == enregistrement.sha256
    ):
        copie.unlink()
        retiree = copie
    entrees = {k: v for k, v in enregistrement.entrees.items() if k != "valide"}
    return replace(enregistrement, niveau="qualifie", entrees=entrees), retiree
