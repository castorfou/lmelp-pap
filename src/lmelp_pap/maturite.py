"""La maturité des enregistrements intégraux, conservée dans Mongo.

Un enregistrement intégral avance sur le chemin qui le mène à lmelp :
localisé, téléchargeable, rapatrié, qualifié, valide (glossaire,
*maturité d'un enregistrement*). Ce module tient le niveau de chaque
enregistrement dans la collection ``pap_enregistrements`` (un document par
URL) et le fait évoluer selon la vérification de son URL :

- une URL qui répond 200 avec un type audio rend l'enregistrement
  téléchargeable ;
- un échec net (404, 410, 200 non audio) fait redescendre un téléchargeable à
  localisé : Radio France détient toujours le fichier ;
- un échec passager (délai dépassé, erreur réseau, 5xx…) est noté sans
  changer le niveau ;
- à partir de rapatrié, la vérification ne change plus le niveau.

Chaque entrée dans un niveau est datée (``entrees``).

Le champ ``url`` (``_id`` du document) identifie l'enregistrement : l'URL du
fichier audio pour radiofrance, l'URL de la notice pour l'INA, ``piste:<uuid>``
pour une piste saisie à la main. Seules les URL d'intégral de la liste
(``integraux``) se vérifient et se rapatrient.

Le niveau localisé a deux autres entrées que le recul d'une URL :

- chaque notice INA des Archives Radio Pro d'une émission sans intégral
  (``localisations_ina``) crée un enregistrement localisé de source ``ina`` ;
  celles du Dépôt légal n'en créent aucun. La création n'ajoute que les
  enregistrements absents (``Depot.ajouter_absents``) : la relancer ne change
  rien, et n'écrase ni une piste ni un niveau plus avancé ;
- une piste saisie à la main (``piste``) : une source en texte libre (un
  passionné, les archives de Radio France après leur réponse) et une note.

Un enregistrement localisé garde le journal des échanges qui mènent à lui
(``echange``, collection ``pap_echanges``, jamais exportée). Une URL saisie à
la main (``url_saisie``) fait entrer un enregistrement à téléchargeable, un
fichier téléversé (``televerser``) à rapatrié.

Rapatrier un enregistrement téléchargeable télécharge son fichier dans le
dossier audio de pap (``<année>/<nom d'origine>``), en passant par un
``.part`` renommé à la fin : il devient rapatrié, avec le chemin du fichier,
son empreinte SHA-256 et sa taille.

Qualifier un enregistrement rapatrié le juge à l'écoute : favorable, il
devient qualifié ; écarté (avec un motif), il reste rapatrié et porte son
écart. Chaque qualification est conservée dans ``pap_qualifications`` et
s'exporte dans ``qualifications.csv``.
"""

import contextlib
import csv
import datetime as dt
import hashlib
import logging
import os
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

import requests
from bson import ObjectId
from dotenv import find_dotenv, load_dotenv

from lmelp_pap.liste import Emission
from lmelp_pap.sources.ina import SOURCE as SOURCE_INA
from lmelp_pap.sources.ina import archives_radio_pro


log = logging.getLogger(__name__)


NIVEAUX = ("localise", "telechargeable", "rapatrie", "qualifie", "valide")
COLLECTION = "pap_enregistrements"
QUALIFICATIONS = "pap_qualifications"
# le journal des échanges des enregistrements localisés : jamais exporté
ECHANGES = "pap_echanges"
REMISES = "pap_remises"  # fiches des mises à disposition, lues par lmelp
EPISODES_LMELP = "episodes"  # les épisodes de lmelp, dans la même base
DOUBLON = 3  # jours d'écart entre une émission et un épisode lmelp de doublon
ETAT = "pap_etat"  # état de l'appli : date de la dernière vérification complète
SOURCE = "radiofrance"
ENTETES = {"User-Agent": "lmelp-pap (https://github.com/castorfou/lmelp-pap)"}
DELAI = 30
CONCURRENCE = 4
MORCEAU = 1 << 20  # 1 Mo par lecture du flux
ESSAIS = 3  # tentatives d'un téléchargement sur échec passager
PAUSES = (5, 15)  # secondes avant le 2e, puis le 3e essai
# Encodages préférés pour l'intégral retenu d'une émission.
PREFERENCES = (".m4a", ".mp3")

Resultat = Literal["ok", "net", "passager"]


@dataclass(frozen=True)
class Verification:
    """Le résultat de la dernière vérification d'une URL."""

    date: datetime
    resultat: Resultat
    detail: str


Verdict = Literal["favorable", "ecarte"]
VERDICTS: tuple[Verdict, ...] = ("favorable", "ecarte")


@dataclass(frozen=True)
class Qualification:
    """Le jugement porté à l'écoute sur un enregistrement (glossaire,
    *qualification*) : favorable, ou écarté avec un motif."""

    enregistrement: str  # l'URL de l'enregistrement
    emission_id: str
    verdict: Verdict
    motif: str
    date: datetime


@dataclass(frozen=True)
class Enregistrement:
    """Un enregistrement intégral, identifié par son URL, et sa maturité."""

    url: str
    emission_id: str
    source: str
    niveau: str
    entrees: dict[str, datetime] = field(default_factory=dict)
    verification: Verification | None = None
    fichier: str | None = None  # relatif au dossier audio, une fois rapatrié
    sha256: str | None = None
    taille: int | None = None
    echec: Verification | None = None  # dernier échec de rapatriement
    ecart: Qualification | None = None  # rapatrié, mais écarté à l'écoute
    note: str | None = None  # ce qu'on sait d'une piste saisie à la main
    provenance: str | None = None  # qui a fourni un fichier téléversé
    datation: str | None = None  # ce qui établit sa date (``DATATIONS``)


class PisteError(ValueError):
    """Une piste impossible : sans source."""


def piste(
    emission_id: str, source: str, note: str, maintenant: datetime
) -> Enregistrement:
    """Un enregistrement localisé saisi à la main : ``source`` en texte libre
    (obligatoire : qui le détient, par quel canal, ce qu'il détient), ``note``
    facultative."""
    source = source.strip()
    if not source:
        raise PisteError("une piste demande une source")
    return Enregistrement(
        url=f"piste:{uuid.uuid4().hex}",
        emission_id=emission_id,
        source=source,
        niveau="localise",
        entrees={"localise": maintenant},
        note=note.strip() or None,
    )


SOURCE_URL = "url"  # la source d'une URL saisie à la main


class UrlError(ValueError):
    """Une URL saisie impossible : pas en http(s)."""


def url_saisie(
    emission_id: str, url: str, note: str, maintenant: datetime
) -> Enregistrement:
    """Un enregistrement téléchargeable saisi à la main : ``url`` http(s)
    (obligatoire) du fichier intégral, ``note`` facultative. Il part avec le
    prochain lot de téléchargement, comme une URL radiofrance."""
    url = url.strip()
    morceaux = urlsplit(url)
    if (
        morceaux.scheme not in ("http", "https")
        or not morceaux.netloc
        or any(c.isspace() for c in url)
    ):
        raise UrlError(f"URL invalide : {url!r} (attendu : une URL http(s))")
    return Enregistrement(
        url=url,
        emission_id=emission_id,
        source=SOURCE_URL,
        niveau="telechargeable",
        entrees={"telechargeable": maintenant},
        note=note.strip() or None,
    )


# Ce qui établit la date d'un fichier téléversé.
DATATIONS = {
    "etiquette": "étiquette de la cassette ou du fichier",
    "antenne": "annonce à l'antenne",
    "contenu": "déduite du contenu",
    "inconnue": "inconnue",
}
EXTENSIONS_AUDIO = (
    ".mp3", ".m4a", ".mp4", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus",
    ".wma", ".aif", ".aiff",
)  # fmt: skip


class Lisible(Protocol):
    """Un flux d'octets (un fichier ouvert, le corps d'une requête)."""

    def read(self, n: int = -1, /) -> bytes: ...


class FichierError(ValueError):
    """Un fichier téléversé refusé : provenance, nom, nom déjà pris."""


def televerser(
    emission_id: str,
    nom: str,
    flux: Lisible,
    taille: int,
    dossier: Path,
    provenance: str,
    datation: str,
    note: str,
    maintenant: datetime,
    piste: Enregistrement | None = None,
) -> Enregistrement:
    """Écrit les ``taille`` octets de ``flux`` dans ``dossier/<année>/<nom>``
    (via un ``.part``) et rend l'enregistrement rapatrié : celui de ``piste``
    (un enregistrement localisé de l'émission), sinon un nouveau, de source
    ``provenance``. ``provenance`` est obligatoire, ``datation`` une clé de
    ``DATATIONS`` ; un nom de fichier déjà pris est refusé, rien n'est
    écrasé, et rien ne reste en cas d'échec."""
    provenance = provenance.strip()
    if not provenance:
        raise FichierError("un fichier demande sa provenance")
    if datation not in DATATIONS:
        raise FichierError(
            f"datation invalide : {datation!r} (attendu : {', '.join(DATATIONS)})"
        )
    if not nom or nom != Path(nom).name or nom.startswith("."):
        raise FichierError(f"nom de fichier invalide : {nom!r}")
    if not nom.lower().endswith(EXTENSIONS_AUDIO):
        raise FichierError(f"{nom} : pas un fichier audio")
    if taille <= 0:
        raise FichierError(f"{nom} : fichier vide")
    if piste is not None and (
        piste.emission_id != emission_id or piste.niveau != "localise"
    ):
        raise FichierError(
            f"{piste.url} : pas un enregistrement localisé de {emission_id}"
        )
    relatif = f"{emission_id[:4]}/{nom}"
    final = dossier / relatif
    if final.exists():
        raise FichierError(f"{relatif} : nom de fichier déjà pris")
    final.parent.mkdir(parents=True, exist_ok=True)
    partiel = final.with_name(final.name + ".part")
    h, recus = hashlib.sha256(), 0
    try:
        with partiel.open("xb") as f:
            while recus < taille:
                morceau = flux.read(min(MORCEAU, taille - recus))
                if not morceau:
                    raise FichierError(
                        f"{nom} : fichier incomplet ({recus} octets sur {taille})"
                    )
                f.write(morceau)
                h.update(morceau)
                recus += len(morceau)
        if final.exists():
            raise FichierError(f"{relatif} : nom de fichier déjà pris")
        os.replace(partiel, final)
    except BaseException:
        partiel.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            final.parent.rmdir()  # le dossier de l'année, s'il est resté vide
        raise
    base = piste or Enregistrement(
        url=f"fichier:{uuid.uuid4().hex}",
        emission_id=emission_id,
        source=provenance,
        niveau="rapatrie",
        entrees={"rapatrie": maintenant},
    )
    fait = _rapatrie(base, relatif, h.hexdigest(), recus, maintenant)
    return replace(
        fait,
        provenance=provenance,
        datation=datation,
        note=note.strip() or base.note,
    )


CANAUX = ("courriel", "téléphone", "forum", "courrier", "sur place", "autre")


@dataclass(frozen=True)
class Echange:
    """Une entrée du journal des échanges d'un enregistrement localisé (une
    piste) : ce qui s'est passé avec son détenteur, et la prochaine relance.
    ``note_le`` : l'heure de la saisie, qui départage deux échanges du même
    jour."""

    enregistrement: str  # l'URL (l'identifiant) de l'enregistrement
    emission_id: str
    date: dt.date
    canal: str
    interlocuteur: str
    texte: str
    relance: dt.date | None
    note_le: datetime


class EchangeError(ValueError):
    """Un échange impossible : sans texte, canal inconnu, niveau."""


def echange(
    enregistrement: Enregistrement,
    jour: date,
    canal: str,
    interlocuteur: str,
    texte: str,
    relance: date | None,
    maintenant: datetime,
) -> Echange:
    """Un échange noté sur un enregistrement localisé : ``texte`` obligatoire,
    ``canal`` parmi ``CANAUX``, ``relance`` facultative. Il ne change ni le
    niveau de l'enregistrement ni sa date d'entrée."""
    if enregistrement.niveau != "localise":
        raise EchangeError(
            f"{enregistrement.url} : niveau {enregistrement.niveau}, "
            "un échange se note sur un enregistrement localisé"
        )
    if canal not in CANAUX:
        raise EchangeError(
            f"canal invalide : {canal!r} (attendu : {', '.join(CANAUX)})"
        )
    texte = texte.strip()
    if not texte:
        raise EchangeError("un échange demande un texte")
    return Echange(
        enregistrement.url,
        enregistrement.emission_id,
        jour,
        canal,
        interlocuteur.strip(),
        texte,
        relance,
        maintenant,
    )


def dernier_echange(echanges: Iterable[Echange]) -> Echange | None:
    """Le plus récent des échanges, par date puis par heure de saisie."""
    return max(echanges, key=lambda x: (x.date, x.note_le), default=None)


def relance_piste(echanges: Iterable[Echange]) -> date | None:
    """La relance d'une piste : celle de son dernier échange."""
    dernier = dernier_echange(echanges)
    return dernier.relance if dernier else None


def relance_emission(echanges: Iterable[Echange]) -> date | None:
    """La relance d'une émission : la plus proche parmi celles de ses pistes
    (``echanges`` : le journal de toutes ses pistes)."""
    par_piste: dict[str, list[Echange]] = {}
    for x in echanges:
        par_piste.setdefault(x.enregistrement, []).append(x)
    relances = [r for liste in par_piste.values() if (r := relance_piste(liste))]
    return min(relances, default=None)


def localisations_ina(
    emissions: Iterable[Emission], maintenant: datetime
) -> list[Enregistrement]:
    """Un enregistrement localisé par notice INA des Archives Radio Pro, pour
    chaque émission sans intégral, identifié par l'URL de sa notice. Une
    émission connue seulement par le Dépôt légal n'en reçoit aucun."""
    return [
        Enregistrement(
            url=a.url,
            emission_id=e.id,
            source=SOURCE_INA,
            niveau="localise",
            entrees={"localise": maintenant},
        )
        for e in emissions
        if not any(x.type == "intégral" for x in e.enregistrements)
        for a in e.attestations
        if a.source == SOURCE_INA and a.url and archives_radio_pro(a.source_id)
    ]


class QualificationError(ValueError):
    """Une qualification impossible : niveau, verdict, motif manquant."""


def qualifier(
    enregistrement: Enregistrement, verdict: str, motif: str, maintenant: datetime
) -> tuple[Enregistrement, Qualification]:
    """Qualifie un enregistrement rapatrié : favorable, il devient qualifié ;
    écarté (motif obligatoire), il reste rapatrié et garde son écart. Rend
    l'enregistrement et la qualification à conserver. Une qualification ne
    touche ni l'émission ni son thème."""
    if enregistrement.niveau != "rapatrie":
        raise QualificationError(
            f"{enregistrement.url} : niveau {enregistrement.niveau}, "
            "seul un enregistrement rapatrié se qualifie"
        )
    if verdict not in VERDICTS:
        raise QualificationError(
            f"verdict invalide : {verdict!r} (attendu : {', '.join(VERDICTS)})"
        )
    motif = motif.strip()
    if verdict == "ecarte" and not motif:
        raise QualificationError("un écart demande un motif")
    qualification = Qualification(
        enregistrement.url,
        enregistrement.emission_id,
        "favorable" if verdict == "favorable" else "ecarte",
        motif,
        maintenant,
    )
    if verdict == "ecarte":
        return replace(enregistrement, ecart=qualification), qualification
    entrees = {**enregistrement.entrees, "qualifie": maintenant}
    qualifie = replace(enregistrement, niveau="qualifie", entrees=entrees, ecart=None)
    return qualifie, qualification


# Les colonnes de ``qualifications.csv``.
COLONNES_QUALIFICATIONS = ["emission_id", "enregistrement", "verdict", "motif", "date"]


def ecrire_qualifications(
    qualifications: Iterable[Qualification], dossier: Path
) -> None:
    """Écrit ``qualifications.csv`` : chaque qualification, de la plus ancienne
    à la plus récente."""
    with (dossier / "qualifications.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f, lineterminator="\n")
        ecrivain.writerow(COLONNES_QUALIFICATIONS)
        for q in sorted(qualifications, key=lambda q: q.date):
            ecrivain.writerow(
                [
                    q.emission_id,
                    q.enregistrement,
                    q.verdict,
                    q.motif,
                    q.date.isoformat(),
                ]
            )


class RapatriementError(RuntimeError):
    """Un rapatriement impossible : niveau, réponse HTTP."""


class RapatriementInterrompuError(RuntimeError):
    """Un rapatriement arrêté à la demande."""


def classer(reponse: Any, maintenant: datetime) -> Verification:
    """Le verdict d'une vérification : la réponse à un HEAD, ou l'exception
    levée en la demandant."""
    if isinstance(reponse, Exception):
        return Verification(maintenant, "passager", type(reponse).__name__)
    statut = reponse.status_code
    type_ = reponse.headers.get("Content-Type", "")
    if statut == 200:
        if type_.startswith("audio/"):
            return Verification(maintenant, "ok", f"200 {type_}")
        return Verification(maintenant, "net", f"200 {type_ or 'sans type'}")
    if statut in (404, 410):
        return Verification(maintenant, "net", str(statut))
    return Verification(maintenant, "passager", str(statut))


def appliquer(
    existant: Enregistrement | None,
    verification: Verification,
    url: str,
    emission_id: str,
) -> Enregistrement:
    """L'enregistrement après une vérification de son URL."""
    if existant is None:
        niveau = "telechargeable" if verification.resultat == "ok" else "localise"
        return Enregistrement(
            url=url,
            emission_id=emission_id,
            source=SOURCE,
            niveau=niveau,
            entrees={niveau: verification.date},
            verification=verification,
        )
    niveau = existant.niveau
    if niveau == "localise" and verification.resultat == "ok":
        niveau = "telechargeable"
    elif niveau == "telechargeable" and verification.resultat == "net":
        niveau = "localise"
    entrees = dict(existant.entrees)
    if niveau != existant.niveau:
        entrees[niveau] = verification.date
    return replace(existant, niveau=niveau, entrees=entrees, verification=verification)


def meilleur(enregistrements: Iterable[Enregistrement]) -> Enregistrement | None:
    """L'enregistrement le plus avancé, ou ``None`` sans enregistrement."""
    return max(enregistrements, key=lambda e: NIVEAUX.index(e.niveau), default=None)


def maturite_emission(enregistrements: Iterable[Enregistrement]) -> str | None:
    """La maturité d'une émission : celle de son enregistrement le plus avancé."""
    plus_avance = meilleur(enregistrements)
    return plus_avance.niveau if plus_avance else None


def retenu(enregistrements: Iterable[Enregistrement]) -> Enregistrement | None:
    """L'intégral à rapatrier parmi les enregistrements téléchargeables d'une
    émission : m4a, sinon mp3, sinon le premier."""
    candidats = [e for e in enregistrements if e.niveau == "telechargeable"]

    def rang(e: Enregistrement) -> int:
        fin = e.url.lower().rsplit("?", 1)[0]
        return next(
            (i for i, ext in enumerate(PREFERENCES) if fin.endswith(ext)),
            len(PREFERENCES),
        )

    return min(candidats, key=rang, default=None)


def empreinte(chemin: Path) -> str:
    """L'empreinte SHA-256 (hexadécimale) d'un fichier, lu par morceaux."""
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for morceau in iter(lambda: f.read(MORCEAU), b""):
            h.update(morceau)
    return h.hexdigest()


def rapatrier(
    enregistrement: Enregistrement,
    dossier: Path,
    session: Any = None,
    maintenant: datetime | None = None,
    progres: Callable[[int, int | None], None] | None = None,
    arreter: Callable[[], bool] | None = None,
    attendre: Callable[[float], None] = time.sleep,
    relance: Callable[[int, Exception, float], None] | None = None,
) -> Enregistrement:
    """Télécharge le fichier d'un enregistrement téléchargeable dans
    ``dossier/<année>/<nom d'origine>`` et le rend rapatrié. Un fichier déjà
    présent avec l'empreinte connue n'est pas retéléchargé. Un échec passager
    (délai, coupure) est retenté jusqu'à ``ESSAIS`` fois ; un statut HTTP ≠ 200
    ne l'est pas. ``progres(reçus, total)`` suit les octets reçus ;
    ``relance(essai, erreur, pause)`` signale un nouvel essai ;
    ``arreter()`` vrai interrompt (``RapatriementInterrompuError``). En cas d'échec,
    aucun fichier (ni ``.part``) ne reste."""
    if enregistrement.niveau not in ("telechargeable", "rapatrie"):
        raise RapatriementError(
            f"{enregistrement.url} : niveau {enregistrement.niveau}, "
            "seul un enregistrement téléchargeable se rapatrie"
        )
    quand = maintenant or datetime.now(UTC)
    # le nom d'origine, sans paramètres (``?jeton=…``) ni fragment
    nom = urlsplit(enregistrement.url).path.rsplit("/", 1)[-1] or (
        f"{enregistrement.emission_id}.mp3"
    )
    relatif = enregistrement.fichier or f"{enregistrement.emission_id[:4]}/{nom}"
    final = dossier / relatif
    if (
        enregistrement.sha256
        and final.is_file()
        and empreinte(final) == enregistrement.sha256
    ):
        return _rapatrie(
            enregistrement, relatif, enregistrement.sha256, final.stat().st_size, quand
        )

    http: Any = session or requests.Session()
    for essai in range(1, ESSAIS + 1):
        try:
            sha256, taille = _telecharger(
                http, enregistrement.url, final, progres, arreter
            )
            break
        except requests.RequestException as erreur:
            if essai == ESSAIS:
                raise
            if relance:
                relance(essai, erreur, PAUSES[essai - 1])
            attendre(PAUSES[essai - 1])
    return _rapatrie(enregistrement, relatif, sha256, taille, quand)


def _telecharger(
    http: Any,
    url: str,
    final: Path,
    progres: Callable[[int, int | None], None] | None,
    arreter: Callable[[], bool] | None,
) -> tuple[str, int]:
    """Un essai de téléchargement en flux vers ``final`` (via ``.part``) ;
    rend l'empreinte et la taille. Aucun fichier ne reste en cas d'échec."""
    final.parent.mkdir(parents=True, exist_ok=True)
    partiel = final.with_name(final.name + ".part")
    h, taille = hashlib.sha256(), 0
    try:
        reponse = http.get(url, stream=True, timeout=DELAI, headers=ENTETES)
        try:
            if reponse.status_code != 200:
                raise RapatriementError(f"{url} : HTTP {reponse.status_code}")
            longueur = reponse.headers.get("Content-Length")
            total = int(longueur) if longueur and longueur.isdigit() else None
            with partiel.open("wb") as f:
                for morceau in reponse.iter_content(chunk_size=MORCEAU):
                    if arreter and arreter():
                        raise RapatriementInterrompuError("rapatriement arrêté")
                    f.write(morceau)
                    h.update(morceau)
                    taille += len(morceau)
                    if progres:
                        progres(taille, total)
        finally:
            reponse.close()
        os.replace(partiel, final)
    except BaseException:
        partiel.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            final.parent.rmdir()  # le dossier de l'année, s'il est resté vide
        raise
    return h.hexdigest(), taille


def _rapatrie(
    e: Enregistrement, fichier: str, sha256: str, taille: int, quand: datetime
) -> Enregistrement:
    entrees = dict(e.entrees)
    if e.niveau != "rapatrie":
        entrees["rapatrie"] = quand
    return replace(
        e,
        echec=None,
        niveau="rapatrie",
        entrees=entrees,
        fichier=fichier,
        sha256=sha256,
        taille=taille,
    )


class Depot:
    """La collection ``pap_enregistrements`` d'une base Mongo."""

    def __init__(self, base: Any):
        """``base`` : une base pymongo (ou mongomock)."""
        self.base = base
        self._collection = base[COLLECTION]

    def tous(self) -> list[Enregistrement]:
        """Tous les enregistrements connus."""
        return [_depuis_document(d) for d in self._collection.find()]

    def derniere_verification(self) -> datetime | None:
        """La date de la dernière vérification complète des URL, ou ``None``."""
        document = self.base[ETAT].find_one({"_id": "verification"})
        return _aware(document["derniere"]) if document else None

    def noter_verification(self, quand: datetime) -> None:
        """Note la fin d'une vérification complète des URL."""
        self.base[ETAT].replace_one(
            {"_id": "verification"},
            {"_id": "verification", "derniere": quand},
            upsert=True,
        )

    def enregistrer(self, enregistrement: Enregistrement) -> None:
        """Écrit (ou remplace) le document de l'enregistrement."""
        document = _en_document(enregistrement)
        self._collection.replace_one({"_id": document["_id"]}, document, upsert=True)

    def ajouter_absents(self, enregistrements: Iterable[Enregistrement]) -> int:
        """Écrit les enregistrements dont l'identifiant est absent, sans
        toucher aux autres ; rend le nombre de créations."""
        creations = 0
        for e in enregistrements:
            document = _en_document(e)
            resultat = self._collection.update_one(
                {"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True
            )
            creations += resultat.upserted_id is not None
        return creations

    def ajouter_qualification(self, qualification: Qualification) -> None:
        """Conserve une qualification (collection ``pap_qualifications``)."""
        self.base[QUALIFICATIONS].insert_one(_qualification_en_document(qualification))

    def ajouter_echange(self, x: Echange) -> None:
        """Conserve un échange (collection ``pap_echanges``)."""
        self.base[ECHANGES].insert_one(
            {
                "enregistrement": x.enregistrement,
                "emission_id": x.emission_id,
                "date": x.date.isoformat(),
                "canal": x.canal,
                "interlocuteur": x.interlocuteur,
                "texte": x.texte,
                "relance": x.relance.isoformat() if x.relance else None,
                "note_le": x.note_le,
            }
        )

    def echanges(self) -> list[Echange]:
        """Tout le journal des échanges, du plus ancien au plus récent."""
        return sorted(
            (
                Echange(
                    d["enregistrement"],
                    d["emission_id"],
                    date.fromisoformat(d["date"]),
                    d["canal"],
                    d["interlocuteur"],
                    d["texte"],
                    date.fromisoformat(d["relance"]) if d.get("relance") else None,
                    _aware(d["note_le"]),
                )
                for d in self.base[ECHANGES].find({}, {"_id": False})
            ),
            key=lambda x: (x.date, x.note_le),
        )

    def ajouter_remise(self, fiche: dict[str, Any]) -> None:
        """Écrit la fiche d'une mise à disposition (collection ``pap_remises``,
        une par enregistrement)."""
        self.base[REMISES].replace_one({"_id": fiche["_id"]}, fiche, upsert=True)

    def episodes_proches(
        self, jour: date, jours: int = DOUBLON
    ) -> list[dict[str, Any]]:
        """Les épisodes de lmelp datés à ``jours`` jours près de ``jour``
        (collection ``episodes``) : la date d'un épisode est parfois celle de
        sa publication, un ou deux jours après la diffusion, ou un autre jour
        de la semaine pour les anciens ; une fenêtre de trois jours ne touche
        jamais l'émission de la semaine voisine."""
        debut = datetime(jour.year, jour.month, jour.day) - timedelta(days=jours)
        fin = debut + timedelta(days=2 * jours + 1)
        return list(
            self.base[EPISODES_LMELP].find(
                {"date": {"$gte": debut, "$lt": fin}},
                {"date": True, "titre": True, "audio_rel_filename": True},
            )
        )

    def remise_de(self, emission_id: str) -> dict[str, Any] | None:
        """La fiche ``pap_remises`` d'une émission, ou ``None``."""
        fiche: dict[str, Any] | None = self.base[REMISES].find_one(
            {"emission_id": emission_id}
        )
        return fiche

    def retirer_remise(self, url: str) -> None:
        """Retire la fiche ``pap_remises`` d'un enregistrement (annulation
        d'une mise à disposition)."""
        self.base[REMISES].delete_one({"_id": url})

    def dans_lmelp(self, fichiers: Iterable[str]) -> dict[str, datetime | None]:
        """Ceux des fichiers (``<année>/<nom>``) qu'un épisode de lmelp porte
        en ``audio_rel_filename`` (collection ``episodes`` de la même base),
        avec l'heure où le back-office a créé cet épisode : celle de son
        ``_id`` ObjectId (``None`` pour un autre type d'identifiant)."""
        noms = sorted(set(fichiers))
        if not noms:
            return {}
        return {
            d["audio_rel_filename"]: (
                d["_id"].generation_time if isinstance(d["_id"], ObjectId) else None
            )
            for d in self.base[EPISODES_LMELP].find(
                {"audio_rel_filename": {"$in": noms}}, {"audio_rel_filename": True}
            )
        }

    def qualifications(self) -> list[Qualification]:
        """Toutes les qualifications conservées, de la plus ancienne à la plus
        récente."""
        documents = self.base[QUALIFICATIONS].find({}, {"_id": False})
        return sorted(
            (_qualification_depuis_document(d) for d in documents),
            key=lambda q: q.date,
        )


def verification_due(
    a_verifier: list[tuple[str, str]],
    connues: set[str],
    derniere: datetime | None,
    maintenant: datetime,
    intervalle: timedelta,
) -> tuple[str | None, list[tuple[str, str]]]:
    """La vérification à lancer : ``("complete", toutes)`` sur une base vide
    ou si la dernière vérification complète manque ou date de plus
    d'``intervalle`` ; ``("nouvelles", urls)`` pour les URL d'intégral jamais
    vues ; sinon ``(None, [])``."""
    if not connues or derniere is None or maintenant - derniere >= intervalle:
        return "complete", list(a_verifier)
    nouvelles = [(u, e) for u, e in a_verifier if u not in connues]
    return ("nouvelles", nouvelles) if nouvelles else (None, [])


def depot_depuis_env() -> Depot | None:
    """Le dépôt de la base ``MONGO_URI`` / ``MONGO_DB`` (environnement ou
    ``.env``), ou ``None`` sans ``MONGO_URI``."""
    load_dotenv(find_dotenv(usecwd=True))
    uri = os.environ.get("MONGO_URI")
    if not uri:
        return None
    from pymongo import MongoClient

    client: Any = MongoClient(uri, serverSelectionTimeoutMS=10_000, tz_aware=True)
    return Depot(client[os.environ.get("MONGO_DB", "masque_et_la_plume")])


def integraux(dossier: Path) -> list[tuple[str, str]]:
    """Les URL d'intégral de la liste (``enregistrements.csv``), avec leur
    émission."""
    with (dossier / "enregistrements.csv").open(encoding="utf-8", newline="") as f:
        return [
            (ligne["url"], ligne["emission_id"])
            for ligne in csv.DictReader(f)
            if ligne["type"] == "intégral"
        ]


def verifier(
    a_verifier: list[tuple[str, str]],
    depot: Depot,
    session: Any = None,
    maintenant: datetime | None = None,
    progres: Callable[[int], None] | None = None,
) -> dict[str, int]:
    """Vérifie chaque URL (HEAD, concurrence modérée) et met à jour sa
    maturité. Rend le nombre de vérifications par résultat."""
    # une session ``requests``, ou tout objet qui a sa méthode ``head``
    http: Any = session or requests.Session()
    existants = {e.url: e for e in depot.tous()}
    bilan: Counter[str] = Counter()
    faites = 0

    def une(url: str) -> Verification:
        quand = maintenant or datetime.now(UTC)
        try:
            reponse = http.head(
                url, allow_redirects=True, timeout=DELAI, headers=ENTETES
            )
        except requests.RequestException as erreur:
            return classer(erreur, quand)
        return classer(reponse, quand)

    with ThreadPoolExecutor(CONCURRENCE) as pool:
        for (url, emission_id), verification in zip(
            a_verifier, pool.map(une, [u for u, _ in a_verifier])
        ):
            depot.enregistrer(
                appliquer(existants.get(url), verification, url, emission_id)
            )
            if verification.resultat == "passager":
                # un échec réseau ou serveur : l'URL sera revérifiée
                log.warning(f"vérification {emission_id} {url} : {verification.detail}")
            bilan[verification.resultat] += 1
            faites += 1
            if progres:
                progres(faites)
    return {r: bilan[r] for r in ("ok", "net", "passager")}


def _en_document(e: Enregistrement) -> dict[str, Any]:
    v = e.verification
    return {
        "_id": e.url,
        "emission_id": e.emission_id,
        "source": e.source,
        "niveau": e.niveau,
        "entrees": e.entrees,
        "verification": (
            {"date": v.date, "resultat": v.resultat, "detail": v.detail} if v else None
        ),
        "fichier": e.fichier,
        "sha256": e.sha256,
        "taille": e.taille,
        "echec": (
            {
                "date": e.echec.date,
                "resultat": e.echec.resultat,
                "detail": e.echec.detail,
            }
            if e.echec
            else None
        ),
        "ecart": _qualification_en_document(e.ecart) if e.ecart else None,
        "note": e.note,
        "provenance": e.provenance,
        "datation": e.datation,
    }


def _qualification_en_document(q: Qualification) -> dict[str, Any]:
    return {
        "enregistrement": q.enregistrement,
        "emission_id": q.emission_id,
        "verdict": q.verdict,
        "motif": q.motif,
        "date": q.date,
    }


def _qualification_depuis_document(d: dict[str, Any]) -> Qualification:
    return Qualification(
        d["enregistrement"],
        d["emission_id"],
        d["verdict"],
        d["motif"],
        _aware(d["date"]),
    )


def _aware(d: datetime) -> datetime:
    """Mongo rend des dates naïves en UTC (sans ``tz_aware``) : on les date."""
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _depuis_document(d: dict[str, Any]) -> Enregistrement:
    v = d.get("verification")
    return Enregistrement(
        url=d["_id"],
        emission_id=d["emission_id"],
        source=d["source"],
        niveau=d["niveau"],
        entrees={k: _aware(t) for k, t in d["entrees"].items()},
        verification=(
            Verification(_aware(v["date"]), v["resultat"], v["detail"]) if v else None
        ),
        fichier=d.get("fichier"),
        sha256=d.get("sha256"),
        taille=d.get("taille"),
        echec=(
            Verification(
                _aware(d["echec"]["date"]), d["echec"]["resultat"], d["echec"]["detail"]
            )
            if d.get("echec")
            else None
        ),
        ecart=_qualification_depuis_document(d["ecart"]) if d.get("ecart") else None,
        note=d.get("note"),
        provenance=d.get("provenance"),
        datation=d.get("datation"),
    )
