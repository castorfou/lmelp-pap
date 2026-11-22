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
import hashlib
import logging
import os
import time
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import requests
from bson import ObjectId
from dotenv import find_dotenv, load_dotenv


log = logging.getLogger(__name__)


NIVEAUX = ("localise", "telechargeable", "rapatrie", "qualifie", "valide")
COLLECTION = "pap_enregistrements"
QUALIFICATIONS = "pap_qualifications"
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


def ecrire_qualifications(
    qualifications: Iterable[Qualification], dossier: Path
) -> None:
    """Écrit ``qualifications.csv`` : chaque qualification, de la plus ancienne
    à la plus récente."""
    with (dossier / "qualifications.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f, lineterminator="\n")
        ecrivain.writerow(["emission_id", "enregistrement", "verdict", "motif", "date"])
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
    relatif = (
        enregistrement.fichier
        or f"{enregistrement.emission_id[:4]}/{enregistrement.url.rsplit('/', 1)[-1]}"
    )
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

    def ajouter_qualification(self, qualification: Qualification) -> None:
        """Conserve une qualification (collection ``pap_qualifications``)."""
        self.base[QUALIFICATIONS].insert_one(_qualification_en_document(qualification))

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
    )
