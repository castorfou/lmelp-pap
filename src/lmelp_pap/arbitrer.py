"""Outil local ``lmelp-pap arbitrer`` : la page de la liste en mode arbitrage.

Un serveur HTTP de la bibliothèque standard sert la page et une petite API
JSON. À chaque arbitrage, il l'enregistre dans la collection Mongo
``pap_arbitrages`` (ou, sans Mongo, dans ``arbitrages.csv``), reconstruit la
liste depuis le cache, sans réseau, réécrit ses CSV et renvoie les données à
jour. Avec Mongo, ``arbitrages.csv`` n'est ni lu ni écrit : il s'importe et
s'exporte par ``lmelp-pap arbitrages``.

API :

- ``GET /`` : l'accueil (histogramme, compteurs et frise par état, pages
  d'état) ;
- ``GET /liste`` : la page de la liste en mode arbitrage ;
- ``GET /api/donnees`` : les données courantes ;
- ``POST /api/arbitrages`` : enregistre un arbitrage sur une émission
  (``emission_id``, ``sorte`` : ``thème``, ``existence``, ``date``,
  ``rapprochement`` ou ``écoute`` pour un renvoi à l'écoute, ``themes``,
  ``date``, ``justification``) ; un arbitrage d'existence porte en plus
  ``valeur`` : ``existe``, ou ``n'existe pas`` (par défaut) ; un arbitrage de
  rapprochement porte en plus l'attestation ambiguë (``source``,
  ``source_id``) et ``vers``, l'identifiant de l'émission rivale où la
  déplacer, ou ``null`` pour la garder ici ;
- ``POST /api/annulations`` : annule les arbitrages d'une émission
  (``emission_id``) ou d'une attestation (``source`` et ``source_id``) ;
- ``POST /api/verifications`` : lance, en fond, la vérification des URL
  d'intégral (maturité des enregistrements, module ``maturite``) ;
- ``GET /api/verifications`` : son avancement (``en_cours``, ``faites``,
  ``total``) et son ``bilan`` une fois finie ;
- ``POST /api/rapatriements`` / ``GET /api/rapatriements`` /
  ``POST /api/rapatriements/arret`` : le rapatriement des intégraux ;
- ``POST /api/qualifications`` : qualifie l'enregistrement rapatrié d'une
  émission (``emission_id``, ``verdict`` : ``favorable`` ou ``ecarte``,
  ``motif``, obligatoire pour un écart) ;
- ``POST /api/localisations`` : ajoute à une émission (``emission_id``) ou à
  plusieurs (``emissions``) un enregistrement localisé saisi à la main
  (``source`` en texte libre, obligatoire, ``note``, ``premier_echange``
  facultatif : ``canal``, ``texte``) ;
- ``POST /api/echanges`` : note un échange au journal d'une piste
  (``emission_id``, ``enregistrement``, ``date``, ``canal``,
  ``interlocuteur``, ``texte`` obligatoire, ``relance``) ;
- ``POST /api/urls`` : ajoute à une émission un enregistrement téléchargeable
  (``emission_id``, ``url`` http(s), ``note``) ;
- ``POST /api/fichiers?emission_id=…&nom=…&provenance=…&datation=…`` : le
  corps est un fichier audio, écrit dans le dossier audio ; l'enregistrement
  (celui de ``piste``, sinon un nouveau) passe à rapatrié ;
- ``GET /api/radiofrance/<emission_id>`` : la diffusion de l'émission dans
  l'Open API Radio France, lue à la demande (module ``radiofrance_api``) :
  ``statut`` (``trouvee``, ``introuvable``, ``sans_cle``, ``erreur`` avec son
  ``detail``) et ``diffusion`` (``titre``, ``resume``, ``url``, ``equipe`` et
  ``invites`` : ``nom``, ``role``) ; rien n'en est conservé ;
- ``POST /api/remises`` : met à disposition de lmelp l'enregistrement qualifié
  de chaque émission (``emissions``) : copie dans le dossier audio de lmelp,
  fiche ``pap_remises``, passage à valide ; la réponse porte en plus
  ``remise`` (``mises``, ``refus`` avec leur ``detail``) ;
- ``GET /api/remises/<emission_id>`` : ce que lmelp reçoit, la fiche
  ``pap_remises`` de l'émission mise à disposition, ou l'aperçu de celle de
  son enregistrement qualifié (``apercu``) ; 404 sinon ;
- ``POST /api/remises/annulation`` : annule la mise à disposition d'une
  émission valide pas encore dans lmelp (``emission``) : fiche et copie chez
  lmelp retirées, retour à qualifié ;
- ``POST /api/collectes`` : lance, en fond, la collecte d'une source
  (``source`` : un nom de ``collecte.SOURCES``, ou ``toutes``), re-collecte
  comprise si ``refresh`` ; à la fin, la liste est reconstruite depuis le
  cache. Une seule collecte à la fois : une deuxième demande est refusée
  (409) ;
- ``GET /api/collectes`` : son avancement (``en_cours``, ``faites``,
  ``total``, ``sources``, ``en_cours_sur``, ``progression``, la dernière
  ligne de progression de la source, ``erreurs``) et son ``bilan`` une fois
  finie (``emissions``, ``attestations``, l'issue de chaque source) ;
- ``GET /audios/<fichier>`` : un fichier du dossier audio, avec les requêtes
  ``Range`` (206) pour le saut ; rien hors du dossier audio.

Avec un dépôt Mongo, chaque émission des données porte sa ``maturite`` (le
niveau de son enregistrement le plus avancé, ou ``null``), ``maturite_depuis``
(la date d'entrée dans ce niveau), ``fichier_audio`` (le fichier écoutable,
relatif au dossier audio), ``ecart`` (``date``, ``motif``), ``dans_lmelp``
(attestée par lmelp, ou un épisode de lmelp porte le fichier d'un de ses
enregistrements valides), ``integration_lmelp`` (l'heure de création de cet
épisode, ou ``null``), ``localisations`` (ses enregistrements localisés, du
plus ancien au plus récent : ``source``, ``note``, ``notice``, l'URL de la
notice INA, et ``depuis``, la date d'entrée dans le niveau) et les données ``maturite_active`` ; sans dépôt, la
vérification, le rapatriement, la qualification et la mise à disposition
répondent 503.

Chaque requête d'écriture renvoie les données à jour, comme ``GET /api/donnees``.
Une émission y porte en plus, pour l'arbitrage de date, ses ``dates_candidates``
(vides sans doute de date ni date arbitrée) et son ``arbitrage_date`` ; son
``arbitrage_existence``, quand elle est arbitrée « existe » ; pour
l'arbitrage de rapprochement, ses ``rapprochements`` : chaque attestation
ambiguë (``source``, ``source_id``) avec ses ``rivales``.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from lmelp_pap import audio
from lmelp_pap.arbitrages import (
    COLLECTION as ARBITRAGES_MONGO,
)
from lmelp_pap.arbitrages import (
    EXISTANTE,
    INEXISTANTE,
    ArbitragesMongo,
    ajouter_arbitrage,
    decision,
    erreur_de_themes,
    lire_arbitrages,
    lire_date,
    retirer_arbitrages,
    valeur,
)
from lmelp_pap.collecte import SOURCES, collecter, lire_cache
from lmelp_pap.ecriture import ecrire_liste
from lmelp_pap.liste import (
    JOURS,
    Arbitrage,
    CleAttestation,
    Emission,
    Rivale,
    attestation_stable,
    au_jour_habituel,
    construire_liste,
    dates_candidates,
)
from lmelp_pap.maturite import (
    ESSAIS,
    Depot,
    Echange,
    EchangeError,
    Enregistrement,
    FichierError,
    Lisible,
    PisteError,
    QualificationError,
    RapatriementError,
    RapatriementInterrompuError,
    Resultat,
    UrlError,
    Verification,
    dernier_echange,
    echange,
    ecrire_qualifications,
    integraux,
    localisations_ina,
    meilleur,
    piste,
    qualifier,
    rapatrier,
    relance_emission,
    relance_piste,
    retenu,
    televerser,
    url_saisie,
    verification_due,
    verifier,
)
from lmelp_pap.page import construire_page, donnees_page, icone
from lmelp_pap.radiofrance_api import (
    QUOTA,
    ApiRadioFranceError,
    Diffusion,
    LecteurDiffusions,
    jeton,
)
from lmelp_pap.remise import (
    RemiseError,
    annuler_mise_a_disposition,
    apercu_fiche,
    mettre_a_disposition,
)


# Les doutes qu'un arbitrage de date lève.
DOUTES_DE_DATE = ("désaccord de date", "jour inhabituel")


# Période du fil de planification de la vérification des URL, en secondes.
PLANIFICATION = 3600

# Les dossiers audio par défaut : celui de pap (enregistrements rapatriés) et
# celui du back-office lmelp (enregistrements mis à disposition).
AUDIOS = Path("data/raw/audios")
AUDIOS_LMELP = Path("data/raw/audios-lmelp")

log = logging.getLogger(__name__)
# Les requêtes HTTP du serveur, dans leur propre logger.
log_http = logging.getLogger("lmelp_pap.http")

# Les requêtes que le journal des requêtes tait : la santé (sondée toutes les
# 30 s par Docker) et les sondages de l'avancement par la page.
SILENCIEUSES = {
    ("GET", "/health"),
    ("GET", "/api/verifications"),
    ("GET", "/api/rapatriements"),
    ("GET", "/api/collectes"),
}


# L'issue de la collecte d'une source, telle que les logs la disent.
ISSUES_COLLECTE = {
    "collectee": "collectée",
    "deja_complete": "déjà complète, rien à collecter",
    "sautee": "sautée",
    "echec": "en échec",
}


def _s(n: int) -> str:
    """Le « s » du pluriel."""
    return "s" if n > 1 else ""


def _duree(secondes: float) -> str:
    """Une durée lisible : « 16 s », « 3 min 41 s »."""
    s = round(secondes)
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60} s"


class Maturites:
    """Les enregistrements du dépôt, par émission, et ceux des fichiers
    valides qu'un épisode de lmelp porte : lus une fois pour une requête."""

    def __init__(self, depot: Depot):
        self.par_emission: dict[str, list[Enregistrement]] = {}
        for e in depot.tous():
            self.par_emission.setdefault(e.emission_id, []).append(e)
        self._presents = depot.dans_lmelp(
            e.fichier
            for liste in self.par_emission.values()
            for e in liste
            if e.niveau == "valide" and e.fichier
        )

    def de(self, emission_id: str) -> list[Enregistrement]:
        """Les enregistrements de l'émission."""
        return self.par_emission.get(emission_id, [])

    def dans_lmelp(self, emission: Emission) -> bool:
        """L'émission est dans lmelp : attestée par lmelp, ou un de ses
        enregistrements valides y est entré (un épisode de lmelp porte son
        fichier en ``audio_rel_filename``)."""
        return any(a.source == "lmelp" for a in emission.attestations) or any(
            e.niveau == "valide" and e.fichier in self._presents
            for e in self.de(emission.id)
        )

    def integration_lmelp(self, emission_id: str) -> datetime | None:
        """L'heure où le back-office a fait un épisode d'un enregistrement
        valide de l'émission (création de l'épisode), ou ``None``."""
        heures = [
            self._presents.get(e.fichier)
            for e in self.de(emission_id)
            if e.niveau == "valide" and e.fichier
        ]
        return min((h for h in heures if h), default=None)


class DemandeInvalideError(ValueError):
    """Une requête d'arbitrage invalide."""


class MaturiteIndisponibleError(RuntimeError):
    """La maturité des enregistrements demande une base Mongo."""


class TacheEnCoursError(RuntimeError):
    """Une tâche de fond du même genre tourne déjà."""


class Tache:
    """Une tâche de fond (vérification, rapatriement) et son avancement :
    ``en_cours``, ``faites``, ``total``, ``bilan`` une fois finie, et les
    champs propres à la tâche. ``nom`` la désigne dans les logs."""

    def __init__(self, nom: str = "tâche", **champs: Any):
        self.nom = nom
        self._champs = champs
        self._etat: dict[str, Any] = self._repos()
        self._verrou = threading.Lock()
        self._arret = threading.Event()

    def _repos(self) -> dict[str, Any]:
        return {
            "en_cours": False,
            "faites": 0,
            "total": 0,
            "bilan": None,
            **{
                k: (list(v) if isinstance(v, list) else v)
                for k, v in self._champs.items()
            },
        }

    def etat(self) -> dict[str, Any]:
        """L'avancement courant."""
        with self._verrou:
            return dict(self._etat)

    def arreter(self) -> dict[str, Any]:
        """Demande l'arrêt de la tâche en cours ; rend l'avancement."""
        self._arret.set()
        return self.etat()

    def arret_demande(self) -> bool:
        """Vrai si l'arrêt a été demandé."""
        return self._arret.is_set()

    def maj(self, **champs: Any) -> None:
        """Met à jour l'avancement (appelé depuis le fil de la tâche)."""
        with self._verrou:
            self._etat.update(champs)

    def lancer(
        self, total: int, travail: Any, refuser: bool = False, **champs: Any
    ) -> dict[str, Any]:
        """Lance ``travail(tache)`` dans un fil, qui rend le bilan. Une tâche
        déjà en cours est rendue telle quelle, ou refusée si ``refuser``. Une
        exception du travail va aux logs avec sa trace ; la tâche finit alors
        sans bilan. ``champs`` : l'état de départ propre à cette exécution."""
        with self._verrou:
            if self._etat["en_cours"]:
                if refuser:
                    raise TacheEnCoursError("une tâche est déjà en cours")
                return dict(self._etat)
            self._etat = {
                **self._repos(),
                "en_cours": True,
                "total": total,
                "debut": datetime.now().astimezone().isoformat(),
                **champs,
            }
            self._arret.clear()

        def executer() -> None:
            bilan = None
            try:
                bilan = travail(self)
            except Exception:
                # pas de bilan ni de ligne « terminée » : la trace dit pourquoi
                log.exception(f"{self.nom} en échec")
            finally:
                self.maj(en_cours=False, bilan=bilan)

        threading.Thread(target=executer, daemon=True).start()
        return self.etat()


class Atelier:
    """La liste en cours d'arbitrage : le cache lu une fois, les CSV réécrits."""

    def __init__(
        self,
        cache: Path,
        sortie: Path,
        *,
        fichier: Path | None = None,
        depot: Depot | None = None,
        session: Any = None,
        audios: Path | None = None,
        intervalle: timedelta = timedelta(days=7),
        audios_lmelp: Path | None = None,
    ):
        """Lit le cache et construit une première fois la liste. ``depot`` :
        la maturité des enregistrements (Mongo), ``session`` : le client HTTP
        de la vérification, du rapatriement et de l'API Radio France
        (``requests`` par défaut), ``audios`` : le dossier des enregistrements
        rapatriés, ``audios_lmelp`` : le dossier audio du back-office lmelp,
        où vont les enregistrements mis à disposition."""
        self.depot = depot
        self._session = session
        self.audios = audios or AUDIOS
        self.audios_lmelp = audios_lmelp or AUDIOS_LMELP
        self._verrou_remise = threading.Lock()  # une mise à disposition à la fois
        self._verrou_fichiers = threading.Lock()  # un téléversement à la fois
        # l'API Radio France, avec son cache en mémoire partagé par l'écoute
        # et la mise à disposition
        self._radiofrance = LecteurDiffusions(session)
        self.intervalle = intervalle  # entre deux vérifications complètes
        self.planification = False
        self._verification = Tache("vérification")
        self._rapatriement = Tache(
            "rapatriement",
            en_cours_sur=None,
            erreurs=[],
            octets=0,
            fichier_octets=0,
            fichier_total=None,
            debut=None,
            arrete=False,
            rapatriees=[],  # émissions rapatriées (ou déjà là) pendant le lot
        )
        self._collecte = Tache(
            "collecte",
            sources=[],
            refresh=False,
            en_cours_sur=None,
            progression=None,
            erreurs=[],
        )
        self.cache = cache
        self.sortie = sortie
        self.fichier = fichier or sortie / "arbitrages.csv"
        # Avec Mongo, les arbitrages vivent dans pap_arbitrages, qui fait foi
        # (ADR 0004) : le fichier n'est ni lu ni écrit, il s'exporte.
        self.arbitrages = ArbitragesMongo(depot.base) if depot else None
        self.attestations = lire_cache(cache)
        self._par_cle = {a.cle: a for a in self.attestations}
        self._emissions: dict[str, Emission] = {}
        # les types de doute de chaque émission de la liste qui en a
        self._doutes: dict[str, set[str]] = {}
        # les attestations ambiguës de chaque émission de la liste, avec leurs
        # rivales : identifiant de l'émission et attestation qui la désigne
        self._ambigues: dict[str, dict[CleAttestation, tuple[Rivale, ...]]] = {}
        self._verrou = threading.Lock()
        with self._verrou:
            self._reconstruire()

    def donnees(self) -> dict[str, Any]:
        """Les émissions de la liste et les arbitrages, pour la page."""
        with self._verrou:
            return self._donnees()

    def nombre_emissions(self) -> int:
        """Le nombre d'émissions de la liste, sans lire la base Mongo."""
        with self._verrou:
            return len(self._emissions)

    def etat_verification(self) -> dict[str, Any]:
        """L'avancement de la vérification des URL d'intégral, avec la date de
        la dernière vérification complète et de la prochaine."""
        etat = self._verification.etat()
        derniere = self.depot.derniere_verification() if self.depot else None
        etat["derniere"] = derniere.isoformat() if derniere else None
        etat["prochaine"] = (
            (derniere + self.intervalle).isoformat() if derniere else None
        )
        return etat

    def lancer_verification(
        self,
        a_verifier: list[tuple[str, str]] | None = None,
        origine: str = "manuelle",
    ) -> dict[str, Any]:
        """Lance en fond la vérification des URL d'intégral, sauf si une est
        déjà en cours ; rend son avancement. Sans liste, toutes les URL de la
        liste sont vérifiées et la date de cette vérification complète est
        notée ; avec une liste, seulement celles-là."""
        depot = self._depot()
        complete = a_verifier is None
        if a_verifier is None:
            with self._verrou:
                a_verifier = integraux(self.sortie)
        urls = a_verifier
        if self._verification.etat()["en_cours"]:
            return self._verification.etat()
        genre = "complète" if complete else "partielle"
        log.info(
            f"vérification {origine}"
            f"{'' if '(' in origine else f' ({genre})'} : {len(urls)} URL"
        )

        def travail(t: Tache) -> dict[str, int]:
            debut = time.monotonic()
            bilan = verifier(
                urls, depot, self._session, progres=lambda n: t.maj(faites=n)
            )
            if complete:
                depot.noter_verification(datetime.now(UTC))
            log.info(
                f"vérification terminée en {round(time.monotonic() - debut)} s : "
                f"{bilan['ok']} ok, {bilan['net']} morte{_s(bilan['net'])}, "
                f"{bilan['passager']} échec{_s(bilan['passager'])} "
                f"passager{_s(bilan['passager'])}"
            )
            return bilan

        return self._verification.lancer(len(urls), travail)

    def planifier(self, maintenant: datetime | None = None) -> str | None:
        """Lance la vérification due (base vide, dernière vérification
        complète trop ancienne, URL nouvelles), sauf si une tourne déjà ;
        rend son genre (``complete``, ``nouvelles``) ou ``None``."""
        if self.depot is None or self._verification.etat()["en_cours"]:
            return None
        with self._verrou:
            a_verifier = integraux(self.sortie)
        connues = {e.url for e in self.depot.tous()}
        derniere = self.depot.derniere_verification()
        maintenant = maintenant or datetime.now(UTC)
        genre, urls = verification_due(
            a_verifier, connues, derniere, maintenant, self.intervalle
        )
        if genre == "complete":
            raison = (
                "jamais vérifiée"
                if derniere is None
                else "base vide"
                if not connues
                else "dernière le " + derniere.astimezone().strftime("%d/%m/%Y à %H:%M")
            )
            self.lancer_verification(None, f"automatique (complète : {raison})")
        elif genre == "nouvelles":
            self.lancer_verification(urls, "automatique (nouvelles URL)")
        return genre

    def _apres_reconstruction(self) -> None:
        """Une reconstruction peut apporter des URL d'intégral nouvelles, ou
        des notices INA à localiser."""
        if self.planification:
            self.localiser_ina()
            self.planifier()

    def localiser_ina(self) -> int:
        """Crée un enregistrement localisé pour chaque notice INA des Archives
        Radio Pro d'une émission sans intégral, s'il n'existe pas encore ;
        rend le nombre de créations."""
        if self.depot is None:
            return 0
        with self._verrou:
            candidats = localisations_ina(self._emissions.values(), datetime.now(UTC))
        creations = self.depot.ajouter_absents(candidats)
        if creations:
            log.info(
                f"localisation INA : {creations} enregistrement{_s(creations)} "
                f"localisé{_s(creations)} créé{_s(creations)} "
                f"({len(candidats)} notice{_s(len(candidats))} des Archives "
                "Radio Pro)"
            )
        return creations

    def ajouter_localise(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Ajoute à une ou plusieurs émissions (``emission_id``, ou la liste
        ``emissions``) un enregistrement localisé saisi à la main : ``source``
        (le détenteur, en texte libre), ``note``, et ``premier_echange``
        facultatif (``canal``, ``texte``), noté aujourd'hui avec le détenteur
        pour interlocuteur. Tout est vérifié avant d'écrire : un refus ne
        localise aucune émission."""
        depot = self._depot()
        ids = demande.get("emissions")
        if ids is None:
            ids = [demande.get("emission_id")]
        cible = ", ".join(str(i) for i in ids) if isinstance(ids, list) else "?"
        source = str(demande.get("source") or "")
        premier = demande.get("premier_echange")
        maintenant = datetime.now(UTC)
        try:
            if not isinstance(ids, list) or not ids:
                raise DemandeInvalideError(
                    "« emissions » : une liste non vide attendue"
                )
            if premier is not None and not isinstance(premier, dict):
                raise DemandeInvalideError("« premier_echange » : un objet attendu")
            with self._verrou:
                faits = []
                for emission_id in ids:
                    emission = self._emission(emission_id)
                    localise = piste(
                        emission.id, source, str(demande.get("note") or ""), maintenant
                    )
                    premier_echange = (
                        echange(
                            localise,
                            _aujourd_hui(),
                            str(premier.get("canal") or ""),
                            localise.source,
                            str(premier.get("texte") or ""),
                            None,
                            maintenant,
                        )
                        if premier is not None
                        else None
                    )
                    faits.append((localise, premier_echange))
                for localise, premier_echange in faits:
                    depot.enregistrer(localise)
                    if premier_echange:
                        depot.ajouter_echange(premier_echange)
        except (DemandeInvalideError, PisteError, EchangeError) as erreur:
            log.info(f"piste refusée {cible} : {erreur}")
            raise DemandeInvalideError(str(erreur)) from erreur
        for localise, premier_echange in faits:
            log.info(
                f"enregistrement localisé ajouté : {localise.emission_id} "
                f"(source « {localise.source} »"
                f"{', premier échange ' + premier_echange.canal if premier_echange else ''})"
            )
        if len(faits) > 1:
            log.info(
                f"piste en lot : {len(faits)} émissions localisées "
                f"(source « {faits[0][0].source} »)"
            )
        return self.donnees()

    def noter_echange(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Note un échange au journal d'un enregistrement localisé
        (``emission_id``, ``enregistrement`` : l'identifiant de la piste,
        facultatif si l'émission n'en a qu'une ; ``date`` AAAA-MM-JJ,
        aujourd'hui par défaut ; ``canal``, ``interlocuteur``, ``texte``
        obligatoire, ``relance`` facultative). Ni la maturité ni la date
        d'entrée ne changent."""
        depot = self._depot()
        emission_id = str(demande.get("emission_id") or "?")
        try:
            with self._verrou:
                emission = self._emission(demande.get("emission_id"))
            pistes = [
                e
                for e in depot.tous()
                if e.emission_id == emission.id and e.niveau == "localise"
            ]
            voulue = demande.get("enregistrement")
            if voulue:
                pistes = [e for e in pistes if e.url == voulue]
                if not pistes:
                    raise DemandeInvalideError(
                        f"{voulue} : pas un enregistrement localisé de {emission.id}"
                    )
            elif not pistes:
                raise DemandeInvalideError(
                    f"{emission.id} : aucun enregistrement localisé"
                )
            elif len(pistes) > 1:
                raise DemandeInvalideError(
                    f"{emission.id} a {len(pistes)} pistes : « enregistrement » "
                    "dit laquelle"
                )
            choisie = pistes[0]
            fait = echange(
                choisie,
                _jour(demande.get("date"), "date") or _aujourd_hui(),
                str(demande.get("canal") or ""),
                str(demande.get("interlocuteur") or ""),
                str(demande.get("texte") or ""),
                _jour(demande.get("relance"), "relance"),
                datetime.now(UTC),
            )
            depot.ajouter_echange(fait)
        except (DemandeInvalideError, EchangeError) as erreur:
            log.info(f"échange refusé {emission_id} : {erreur}")
            raise DemandeInvalideError(str(erreur)) from erreur
        log.info(
            f"échange noté : {fait.emission_id}, piste {fait.enregistrement} "
            f"({choisie.source}), {fait.canal}"
            + (f", relance le {fait.relance.isoformat()}" if fait.relance else "")
        )
        return self.donnees()

    def ajouter_url(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Ajoute à une émission un enregistrement téléchargeable saisi à la
        main (``emission_id``, ``url`` http(s) obligatoire, ``note``) : il
        part avec le prochain lot de téléchargement."""
        depot = self._depot()
        emission_id = str(demande.get("emission_id") or "?")
        try:
            with self._verrou:
                emission = self._emission(demande.get("emission_id"))
            fait = url_saisie(
                emission.id,
                str(demande.get("url") or ""),
                str(demande.get("note") or ""),
                datetime.now(UTC),
            )
            if any(e.url == fait.url for e in depot.tous()):
                raise DemandeInvalideError(f"{fait.url} : URL déjà connue")
            depot.enregistrer(fait)
        except (DemandeInvalideError, UrlError) as erreur:
            log.info(f"URL refusée {emission_id} : {erreur}")
            raise DemandeInvalideError(str(erreur)) from erreur
        log.info(f"URL enregistrée : {fait.emission_id} {fait.url} → téléchargeable")
        return self.donnees()

    def televerser(
        self, parametres: dict[str, str], flux: Lisible, taille: int
    ) -> dict[str, Any]:
        """Écrit un fichier audio téléversé dans le dossier audio
        (``<année>/<nom>``) et rend son enregistrement rapatrié : celui de la
        piste ``piste`` s'il vient d'une piste, sinon un nouveau.
        ``parametres`` : ``emission_id``, ``nom``, ``provenance``
        (obligatoire), ``datation`` (``DATATIONS``), ``note``, ``piste``."""
        depot = self._depot()
        emission_id = parametres.get("emission_id") or "?"
        try:
            with self._verrou:
                emission = self._emission(parametres.get("emission_id"))
            origine = None
            if voulue := parametres.get("piste"):
                origine = next((e for e in depot.tous() if e.url == voulue), None)
                if origine is None:
                    raise DemandeInvalideError(f"{voulue} : piste inconnue")
            with self._verrou_fichiers:
                fait = televerser(
                    emission.id,
                    parametres.get("nom", ""),
                    flux,
                    taille,
                    self.audios,
                    parametres.get("provenance", ""),
                    parametres.get("datation", ""),
                    parametres.get("note", ""),
                    datetime.now(UTC),
                    origine,
                )
            depot.enregistrer(fait)
        except (DemandeInvalideError, FichierError) as erreur:
            log.info(f"fichier refusé {emission_id} : {erreur}")
            raise DemandeInvalideError(str(erreur)) from erreur
        log.info(
            f"fichier téléversé : {fait.emission_id} {fait.fichier}, "
            f"{fait.taille} octets (provenance « {fait.provenance} »"
            f"{', piste ' + fait.url if origine else ''})"
        )
        return self.donnees()

    def planifier_en_continu(self, periode: float = PLANIFICATION) -> None:
        """Vérifie au démarrage, puis toutes les ``periode`` secondes, si une
        vérification est due (fil de fond)."""

        def boucle() -> None:
            while True:
                try:
                    self.localiser_ina()
                    self.planifier()
                except Exception:
                    log.exception("planification de la vérification en échec")
                time.sleep(periode)

        self.planification = True
        threading.Thread(target=boucle, daemon=True).start()

    def etat_rapatriement(self) -> dict[str, Any]:
        """L'avancement du rapatriement en cours ou du dernier."""
        return self._rapatriement.etat()

    def lancer_rapatriement(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Lance en fond, un par un, le rapatriement de l'intégral retenu de
        chaque émission demandée (``emissions``). Une seule tâche à la fois."""
        depot = self._depot()
        ids = demande.get("emissions")
        if not isinstance(ids, list) or not ids:
            raise DemandeInvalideError("« emissions » : une liste non vide attendue")
        par_emission: dict[str, list[Enregistrement]] = {}
        for e in depot.tous():
            par_emission.setdefault(e.emission_id, []).append(e)
        a_rapatrier = []
        for emission_id in ids:
            choisi = retenu(par_emission.get(str(emission_id), []))
            if choisi is None:
                raise DemandeInvalideError(
                    f"{emission_id} n'a aucun intégral téléchargeable"
                )
            a_rapatrier.append(choisi)

        def travail(tache: Tache) -> dict[str, int]:
            bilan = {"rapatries": 0, "deja_la": 0, "echecs": 0}
            erreurs: list[dict[str, str]] = []
            recus = 0  # octets des fichiers finis
            rapatriees: list[str] = []
            debut_lot = time.monotonic()
            n_demandes = len(a_rapatrier)
            log.info(
                f"rapatriement : {n_demandes} émission{_s(n_demandes)} "
                f"demandée{_s(n_demandes)}"
            )
            for n, enregistrement in enumerate(a_rapatrier, 1):
                if tache.arret_demande():
                    tache.maj(arrete=True)
                    break
                tache.maj(
                    en_cours_sur=enregistrement.emission_id,
                    fichier_octets=0,
                    fichier_total=None,
                )

                def progres(octets: int, total: int | None, base: int = recus) -> None:
                    tache.maj(
                        fichier_octets=octets, fichier_total=total, octets=base + octets
                    )

                def relance(
                    essai: int,
                    erreur: Exception,
                    pause: float,
                    emission: str = enregistrement.emission_id,
                ) -> None:
                    log.warning(
                        f"échec {emission} (essai {essai}/{ESSAIS}) : "
                        f"{erreur or type(erreur).__name__}, "
                        f"nouvel essai dans {pause:g} s"
                    )

                debut = time.monotonic()
                try:
                    avant = enregistrement.sha256
                    fait = rapatrier(
                        enregistrement,
                        self.audios,
                        self._session,
                        progres=progres,
                        arreter=tache.arret_demande,
                        relance=relance,
                    )
                    depot.enregistrer(fait)
                    recus += fait.taille or 0
                    deja = bool(avant) and avant == fait.sha256
                    bilan["deja_la" if deja else "rapatries"] += 1
                    rapatriees.append(enregistrement.emission_id)
                    tache.maj(rapatriees=list(rapatriees))
                    log.info(
                        f"{'déjà là' if deja else 'rapatrié'} "
                        f"{enregistrement.emission_id} : {fait.fichier}, "
                        f"{round((fait.taille or 0) / 1e6)} Mo en "
                        f"{round(time.monotonic() - debut)} s"
                    )
                except RapatriementInterrompuError:
                    tache.maj(arrete=True, octets=recus)
                    log.info(
                        f"rapatriement arrêté pendant {enregistrement.emission_id}"
                    )
                    break
                except Exception as erreur:  # noqa: BLE001 — l'erreur va au bilan
                    bilan["echecs"] += 1
                    detail = str(erreur) or type(erreur).__name__
                    log.warning(f"échec {enregistrement.emission_id} : {detail}")
                    erreurs.append(
                        {"emission": enregistrement.emission_id, "detail": detail}
                    )
                    resultat: Resultat = (
                        "net" if isinstance(erreur, RapatriementError) else "passager"
                    )
                    depot.enregistrer(
                        replace(
                            enregistrement,
                            echec=Verification(datetime.now(UTC), resultat, detail),
                        )
                    )
                tache.maj(faites=n, erreurs=list(erreurs), octets=recus)
            tache.maj(en_cours_sur=None)
            arrete = " (arrêté)" if tache.etat()["arrete"] else ""
            log.info(
                f"rapatriement terminé en {_duree(time.monotonic() - debut_lot)} : "
                f"{bilan['rapatries']} rapatrié{_s(bilan['rapatries'])}, "
                f"{bilan['deja_la']} déjà là, "
                f"{bilan['echecs']} échec{_s(bilan['echecs'])}{arrete}"
            )
            return bilan

        return self._rapatriement.lancer(len(a_rapatrier), travail, refuser=True)

    def arreter_rapatriement(self) -> dict[str, Any]:
        """Arrête le rapatriement en cours : le fichier en cours est abandonné,
        ceux qui sont finis restent rapatriés."""
        return self._rapatriement.arreter()

    def etat_collecte(self) -> dict[str, Any]:
        """L'avancement de la collecte en cours ou de la dernière."""
        return self._collecte.etat()

    def lancer_collecte(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Lance en fond la collecte d'une source (``source`` : son nom, ou
        ``toutes``), re-collecte comprise si ``refresh``, puis reconstruit la
        liste depuis le cache. Une seule collecte à la fois."""
        source = demande.get("source")
        refresh = bool(demande.get("refresh"))
        if source == "toutes":
            sources = sorted(SOURCES)
        elif isinstance(source, str) and source in SOURCES:
            sources = [source]
        else:
            raise DemandeInvalideError(
                f"source inconnue : {source!r} (attendu : "
                f"{', '.join(sorted(SOURCES))} ou toutes)"
            )
        etat = self._collecte.etat()
        if etat["en_cours"]:
            raison = (
                f"une collecte est déjà en cours ({etat['en_cours_sur'] or '…'}) : "
                "attendez sa fin"
            )
            log.info(f"collecte {source} refusée : {raison}")
            raise TacheEnCoursError(raison)

        def travail(tache: Tache) -> dict[str, Any]:
            debut = time.monotonic()
            log.info(
                f"collecte demandée : {', '.join(sources)}"
                f"{' (re-collecte)' if refresh else ''}"
            )
            issues: dict[str, str] = {}
            erreurs: list[dict[str, str]] = []
            for n, nom in enumerate(sources, 1):
                tache.maj(en_cours_sur=nom, progression=None)
                debut_source = time.monotonic()
                log.info(f"collecte {nom} : début")
                issue: str
                try:
                    issue = collecter(
                        nom,
                        self.cache,
                        refresh=refresh,
                        progres=lambda ligne: tache.maj(progression=ligne),
                    )
                except Exception as erreur:
                    issue = "echec"
                    detail = str(erreur) or type(erreur).__name__
                    log.exception(f"collecte {nom} en échec : {detail}")
                    erreurs.append({"source": nom, "detail": detail})
                issues[nom] = issue
                log.info(
                    f"collecte {nom} : {ISSUES_COLLECTE[issue]} en "
                    f"{_duree(time.monotonic() - debut_source)}"
                )
                tache.maj(faites=n, erreurs=list(erreurs))
            tache.maj(en_cours_sur=None, progression="reconstruction de la liste")
            avant = self.nombre_emissions()
            self.recharger_cache()
            bilan = {
                "emissions": self.nombre_emissions(),
                "emissions_avant": avant,
                "attestations": len(self.attestations),
                "sources": issues,
            }
            log.info(
                f"collecte terminée en {_duree(time.monotonic() - debut)} : "
                f"{bilan['emissions']} émissions (avant {avant}), "
                f"{bilan['attestations']} attestations"
                f"{f', {len(erreurs)} échec(s)' if erreurs else ''}"
            )
            tache.maj(progression=None)
            return bilan

        return self._collecte.lancer(
            len(sources),
            travail,
            refuser=True,
            sources=sources,
            refresh=refresh,
        )

    def recharger_cache(self) -> None:
        """Relit le cache (après une collecte) et reconstruit la liste."""
        attestations = lire_cache(self.cache)  # long : hors du verrou
        with self._verrou:
            self.attestations = attestations
            self._par_cle = {a.cle: a for a in attestations}
            self._reconstruire()
        self._apres_reconstruction()

    def qualifier(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Qualifie l'enregistrement rapatrié d'une émission (``emission_id``,
        ``verdict`` : ``favorable`` ou ``ecarte``, ``motif`` obligatoire pour
        un écart ; ``enregistrement`` : son URL, s'il y en a plusieurs) ;
        conserve la qualification et réécrit ``qualifications.csv``."""
        depot = self._depot()
        emission_id = str(demande.get("emission_id") or "")
        try:
            with self._verrou:
                choisi = self._rapatrie(
                    depot, emission_id, demande.get("enregistrement")
                )
                fait, qualification = qualifier(
                    choisi,
                    str(demande.get("verdict") or ""),
                    str(demande.get("motif") or ""),
                    datetime.now(UTC),
                )
                depot.enregistrer(fait)
                depot.ajouter_qualification(qualification)
                ecrire_qualifications(depot.qualifications(), self.sortie)
        except (DemandeInvalideError, QualificationError) as erreur:
            log.info(f"qualification refusée {emission_id or '?'} : {erreur}")
            raise DemandeInvalideError(str(erreur)) from erreur
        if qualification.verdict == "favorable":
            log.info(f"qualifié {emission_id} ({fait.fichier}) : favorable")
        else:
            log.info(
                f"écarté {emission_id} ({fait.fichier}) : « {qualification.motif} »"
            )
        return self.donnees()

    def diffusion_radiofrance(self, emission_id: str) -> dict[str, Any]:
        """La diffusion de l'émission dans l'Open API Radio France, pour
        l'écoute : ``statut`` (``trouvee``, ``introuvable``, ``sans_cle``,
        ``erreur`` avec son ``detail``) et ``diffusion``."""
        with self._verrou:
            emission = self._emissions.get(emission_id)
        if emission is None:
            log.info(f"api radiofrance {emission_id} : émission inconnue")
            raise DemandeInvalideError(f"{emission_id} : émission inconnue")
        statut, diffusion, detail = self._diffusion(emission)
        reponse: dict[str, Any] = {
            "emission_id": emission_id,
            "statut": statut,
            "diffusion": asdict(diffusion) if diffusion else None,
        }
        return {**reponse, "detail": detail} if detail else reponse

    def _diffusion(
        self, emission: Emission, contexte: str = ""
    ) -> tuple[str, Diffusion | None, str | None]:
        """La diffusion de l'émission dans l'API Radio France (cache en
        mémoire d'une heure, partagé par l'écoute et la mise à disposition) :
        statut, diffusion, détail de l'erreur. Le journal dit l'appel, sa
        durée ou « cache », et son résultat, sans rien du contenu reçu (CGU)."""
        prefixe = f"api radiofrance {emission.id}{contexte} :"
        cle = jeton()
        if not cle:
            log.info(f"{prefixe} pas de clé")
            return "sans_cle", None, None
        debut = time.monotonic()

        def requetes(n: int, du_jour: int) -> str:
            return f"{n} requête{_s(n)} ({du_jour}/{QUOTA} aujourd'hui)"

        try:
            lecture = self._radiofrance.lire(
                emission.id, emission.date, emission.pages_radiofrance, cle
            )
        except ApiRadioFranceError as erreur:
            log.warning(
                f"{prefixe} erreur {erreur}, "
                f"{requetes(erreur.requetes, erreur.du_jour)}, "
                f"{_duree(time.monotonic() - debut)}"
            )
            return "erreur", None, str(erreur)
        statut = "trouvee" if lecture.diffusion else "introuvable"
        libelle = "trouvée" if lecture.diffusion else "introuvable"
        compte = requetes(lecture.requetes, lecture.du_jour)
        if lecture.cache:
            log.info(f"{prefixe} {libelle} (cache), {compte}")
        else:
            log.info(
                f"{prefixe} {libelle}, {compte}, {_duree(time.monotonic() - debut)}"
            )
        return statut, lecture.diffusion, None

    @staticmethod
    def _rapatrie(depot: Depot, emission_id: str, url: object) -> Enregistrement:
        """L'enregistrement rapatrié de l'émission à qualifier (celui de
        l'URL donnée, sinon le premier)."""
        candidats = [
            e
            for e in depot.tous()
            if e.emission_id == emission_id
            and e.niveau == "rapatrie"
            and (url is None or e.url == url)
        ]
        if not candidats:
            raise DemandeInvalideError(
                f"{emission_id or 'émission absente'} : aucun enregistrement "
                "rapatrié à qualifier"
            )
        return candidats[0]

    def mettre_a_disposition(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Met à disposition de lmelp l'enregistrement qualifié de chaque
        émission demandée (``emissions``), une par une : copie de son fichier
        dans le dossier audio de lmelp, fiche dans ``pap_remises``, passage à
        valide. Une émission déjà dans lmelp, sans enregistrement qualifié, ou
        dont le fichier existe déjà chez lmelp avec une autre empreinte est
        refusée sans rien écrire. Rend les données à jour et le bilan
        (``remise`` : ``mises``, ``refus``). L'API Radio France n'est lue
        qu'avec ``RADIOFRANCE_API_TOKEN`` ; son échec n'empêche rien."""
        depot = self._depot()
        ids = demande.get("emissions")
        if not isinstance(ids, list) or not ids:
            raise DemandeInvalideError("« emissions » : une liste non vide attendue")
        mises: list[dict[str, str]] = []
        refus: list[dict[str, str]] = []
        with self._verrou_remise:
            maturites = Maturites(depot)
            for brut in ids:
                emission_id = str(brut)
                enregistrements = maturites.de(emission_id)
                plus_avance = meilleur(enregistrements)
                niveau = plus_avance.niveau if plus_avance else "aucun"
                try:
                    emission = self._emissions.get(emission_id)
                    if emission is None:
                        raise RemiseError(f"émission inconnue : {emission_id}")
                    if maturites.dans_lmelp(emission):
                        raise RemiseError(f"{emission_id} est déjà dans lmelp")
                    if proches := depot.episodes_proches(emission.date):
                        raise RemiseError(
                            f"{emission_id} : doublon, épisode lmelp "
                            + ", ".join(_episode(e) for e in proches)
                        )
                    choisi = next(
                        (e for e in enregistrements if e.niveau == "qualifie"), None
                    )
                    if choisi is None:
                        raise RemiseError(
                            f"{emission_id} : aucun enregistrement qualifié"
                        )
                    _, api, _ = self._diffusion(emission, " (mise à disposition)")
                    fait, fiche, reprise = mettre_a_disposition(
                        choisi,
                        emission,
                        self.audios,
                        self.audios_lmelp,
                        datetime.now(UTC),
                        api,
                    )
                    depot.ajouter_remise(fiche)
                    depot.enregistrer(fait)
                except RemiseError as erreur:
                    log.info(
                        f"mise à disposition refusée {emission_id} "
                        f"(niveau {niveau}) : {erreur}"
                    )
                    refus.append({"emission": emission_id, "detail": str(erreur)})
                    continue
                relatif = fait.fichier or ""
                deja_copie = ", reprise : fichier déjà copié, même sha256"
                log.info(
                    f"mis à disposition {emission_id} : {self.audios / relatif} → "
                    f"{self.audios_lmelp / relatif} (sha256 {(fait.sha256 or '')[:12]}"
                    f"{', API Radio France' if api else ''}"
                    f"{deja_copie if reprise else ''})"
                )
                mises.append({"emission": emission_id, "fichier": relatif})
        log.info(
            f"mise à disposition : {len(mises)} mise{_s(len(mises))} à disposition, "
            f"{len(refus)} refus"
        )
        return {**self.donnees(), "remise": {"mises": mises, "refus": refus}}

    def fiche_remise(self, emission_id: str) -> dict[str, Any]:
        """Ce que lmelp reçoit pour une émission, dates en ISO 8601 : sa
        fiche ``pap_remises`` si elle est mise à disposition (``apercu``
        faux), sinon l'aperçu de la fiche de son enregistrement qualifié
        (``apercu`` vrai, rien n'est écrit) ; ``DemandeInvalideError`` sinon."""
        depot = self._depot()
        fiche = depot.remise_de(emission_id)
        apercu = fiche is None
        if fiche is None:
            emission = self._emissions.get(emission_id)
            qualifie = next(
                (e for e in Maturites(depot).de(emission_id) if e.niveau == "qualifie"),
                None,
            )
            if emission is None or qualifie is None:
                raise DemandeInvalideError(
                    f"{emission_id} : ni mise à disposition, ni enregistrement qualifié"
                )
            _, api, _ = self._diffusion(emission, " (aperçu de la fiche)")
            fiche = apercu_fiche(qualifie, emission, self.audios, api)
        return {
            **{
                cle: _iso(valeur) if isinstance(valeur, datetime) else valeur
                for cle, valeur in fiche.items()
                if cle != "_id"
            },
            "apercu": apercu,
        }

    def annuler_mise_a_disposition(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Annule la mise à disposition d'une émission valide qui n'est pas
        encore dans lmelp (``emission``) : retire sa fiche ``pap_remises`` et
        sa copie chez lmelp (si elle a encore son empreinte), et ramène son
        enregistrement à qualifié. Rend les données à jour."""
        depot = self._depot()
        emission_id = str(demande.get("emission") or "")
        with self._verrou_remise:
            maturites = Maturites(depot)
            emission = self._emissions.get(emission_id)
            if emission is None:
                raise DemandeInvalideError(f"émission inconnue : {emission_id!r}")
            if maturites.dans_lmelp(emission):
                raise DemandeInvalideError(f"{emission_id} est déjà dans lmelp")
            valide = next(
                (e for e in maturites.de(emission_id) if e.niveau == "valide"), None
            )
            if valide is None:
                raise DemandeInvalideError(f"{emission_id} : aucune mise à disposition")
            qualifie, retiree = annuler_mise_a_disposition(valide, self.audios_lmelp)
            depot.retirer_remise(valide.url)
            depot.enregistrer(qualifie)
        copie = (
            f"copie retirée {retiree}"
            if retiree
            else f"copie gardée {self.audios_lmelp / (valide.fichier or '')}"
        )
        log.info(
            f"mise à disposition annulée {emission_id} : fiche pap_remises "
            f"retirée, {copie}, retour à qualifié"
        )
        return self.donnees()

    def _depot(self) -> Depot:
        if self.depot is None:
            raise MaturiteIndisponibleError("MONGO_URI absent")
        return self.depot

    def page(self) -> str:
        """La page de la liste en mode arbitrage."""
        with self._verrou:
            return construire_page(self.sortie, arbitrage=True)

    def arbitrer(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Enregistre un arbitrage, ou un renvoi à l'écoute, sur une émission
        de la liste."""
        with self._verrou:
            emission = self._emission(demande.get("emission_id"))
            attestation = attestation_stable(emission).cle
            sorte = demande.get("sorte")
            themes = frozenset(demande.get("themes") or ())
            retenue, cible, existe = None, None, False
            if sorte == "thème":
                if erreur := erreur_de_themes(themes):
                    raise DemandeInvalideError(erreur)
            elif sorte == "existence":
                existe = self._existe(demande.get("valeur", INEXISTANTE))
                themes = frozenset()
            elif sorte == "date":
                retenue = self._date_candidate(emission, demande.get("date"))
                themes = frozenset()
            elif sorte == "rapprochement":
                attestation, cible = self._rapprochement(emission, demande)
                themes = frozenset()
            elif sorte == "écoute":
                if emission.id not in self._doutes:
                    raise DemandeInvalideError(
                        f"{emission.id} n'a aucun doute à renvoyer à l'écoute"
                    )
                themes = frozenset()
            else:
                raise DemandeInvalideError(f"sorte invalide : {sorte!r}")
            arbitrage = Arbitrage(
                source=attestation[0],
                source_id=attestation[1],
                sorte=sorte,
                themes=themes,
                date_retenue=retenue,
                cible=cible,
                existe=existe,
                justification=str(demande.get("justification") or "").strip(),
                date=datetime.now().replace(microsecond=0),
            )
            if self.arbitrages is not None:
                self.arbitrages.ajouter(arbitrage)
            else:
                ajouter_arbitrage(self.fichier, arbitrage)
            log.info(
                f"arbitrage {sorte} {emission.id} : {decision(arbitrage)}"
                + self._ou_arbitrages()
            )
            self._reconstruire()
            donnees = self._donnees()
        self._apres_reconstruction()
        return donnees

    def annuler(self, demande: dict[str, Any]) -> dict[str, Any]:
        """Retire les arbitrages d'une émission, ou d'une attestation."""
        with self._verrou:
            if demande.get("emission_id"):
                emission = self._emission(demande["emission_id"])
                cles = {a.cle for a in emission.attestations}
            elif demande.get("source") and demande.get("source_id"):
                cles = {(demande["source"], demande["source_id"])}
            else:
                raise DemandeInvalideError(
                    "emission_id, ou source et source_id, attendus"
                )
            if self.arbitrages is not None:
                retires = self.arbitrages.retirer(cles)
            else:
                retires = retirer_arbitrages(self.fichier, cles)
            if not retires:
                raise DemandeInvalideError("aucun arbitrage à annuler")
            cible = demande.get("emission_id") or ":".join(next(iter(cles)))
            log.info(
                f"annulation {cible} : {retires} arbitrage{_s(retires)} "
                f"retiré{_s(retires)}" + self._ou_arbitrages()
            )
            self._reconstruire()
            donnees = self._donnees()
        self._apres_reconstruction()
        return donnees

    def _rapprochement(
        self, emission: Emission, demande: dict[str, Any]
    ) -> tuple[CleAttestation, CleAttestation | None]:
        """L'attestation ambiguë de l'émission, et l'attestation qui désigne
        l'émission rivale où la déplacer (None pour la garder ici)."""
        attestation = (str(demande.get("source")), str(demande.get("source_id")))
        ambigues = self._ambigues.get(emission.id, {})
        if attestation not in ambigues:
            raise DemandeInvalideError(
                f"{emission.id} n'a aucun rapprochement ambigu sur "
                f"{attestation[0]}:{attestation[1]}"
            )
        vers = demande.get("vers")
        if vers is None:
            return attestation, None
        rivales = dict(ambigues[attestation])
        if vers not in rivales:
            raise DemandeInvalideError(
                f"émission rivale invalide : {vers!r} (attendu : "
                f"{', '.join(rivales)}, ou null pour garder ici)"
            )
        return attestation, rivales[vers]

    @staticmethod
    def _existe(texte: object) -> bool:
        """La valeur d'un arbitrage d'existence : existe, ou n'existe pas."""
        if texte not in (EXISTANTE, INEXISTANTE):
            raise DemandeInvalideError(
                f"valeur d'existence invalide : {texte!r} (attendu : "
                f"{EXISTANTE!r} ou {INEXISTANTE!r})"
            )
        return texte == EXISTANTE

    def _date_candidate(self, emission: Emission, texte: object) -> date:
        """La date à retenir, parmi celles des sources d'une émission qui a un
        doute de date."""
        if not self._date_arbitrable(emission):
            raise DemandeInvalideError(f"{emission.id} n'a aucun doute de date")
        retenue = lire_date(texte) if isinstance(texte, str) else None
        if retenue is None or retenue not in dates_candidates(emission):
            raise DemandeInvalideError(
                f"date invalide : {texte!r} (attendu : une date des sources, "
                f"{', '.join(str(d) for d in dates_candidates(emission))})"
            )
        return retenue

    def _date_arbitrable(self, emission: Emission) -> bool:
        """L'émission de la liste a un doute qu'un arbitrage de date lève, ou
        une date déjà arbitrée, qui se change sans annuler ses autres arbitrages."""
        return emission.arbitrage_date is not None or bool(
            self._doutes.get(emission.id, set()) & set(DOUTES_DE_DATE)
        )

    def _emission(self, emission_id: object) -> Emission:
        """L'émission de la liste qui porte cet identifiant."""
        if not isinstance(emission_id, str) or emission_id not in self._emissions:
            raise DemandeInvalideError(f"émission inconnue : {emission_id!r}")
        return self._emissions[emission_id]

    def _ou_arbitrages(self) -> str:
        """Où vivent les arbitrages, pour les logs : rien pour le fichier."""
        return f" ({ARBITRAGES_MONGO})" if self.arbitrages is not None else ""

    def _lire_arbitrages(self) -> list[Arbitrage]:
        """Les arbitrages de ``pap_arbitrages``, ou du fichier sans Mongo ;
        Mongo injoignable, ceux du fichier, avec un avertissement : l'appli
        sert la liste quand même."""
        if self.arbitrages is None:
            return lire_arbitrages(self.fichier)
        try:
            return self.arbitrages.tous()
        except Exception as erreur:  # noqa: BLE001 — la liste se sert sans base
            log.warning(
                f"{ARBITRAGES_MONGO} illisible ({type(erreur).__name__}) : "
                f"liste construite avec {self.fichier}"
            )
            return lire_arbitrages(self.fichier)

    def origine_arbitrages(self) -> str:
        """D'où viennent les arbitrages, pour le log du démarrage."""
        if self.arbitrages is None:
            return f"fichier {self.fichier}"
        return f"collection {ARBITRAGES_MONGO}"

    def _reconstruire(self) -> None:
        """Reconstruit la liste avec les arbitrages (Mongo, ou le fichier) et
        réécrit ses CSV."""
        liste, doutes = construire_liste(self.attestations, self._lire_arbitrages())
        ecrire_liste(liste, doutes, self.sortie)
        self._emissions = {e.id: e for e in liste}
        self._doutes = {}
        self._ambigues = {}
        for d in doutes:
            if d.dans_la_liste:
                self._doutes.setdefault(d.emission_id, set()).add(d.type)
                if d.rivales:
                    self._ambigues.setdefault(d.emission_id, {})[
                        (d.source, d.source_id)
                    ] = d.rivales

    def _donnees(self) -> dict[str, Any]:
        """Les données de la page et les arbitrages, du plus récent au plus ancien."""
        emissions = [self._pour_arbitrer(e) for e in donnees_page(self.sortie)]
        donnees: dict[str, Any] = {
            "emissions": emissions,
            "arbitrages": [
                self._arbitrage(a) for a in reversed(self._lire_arbitrages())
            ],
        }
        if self.depot is not None:
            maturites = Maturites(self.depot)
            journal: dict[str, list[Echange]] = {}
            for x in self.depot.echanges():
                journal.setdefault(x.enregistrement, []).append(x)
            for e in emissions:
                localises = [x for x in maturites.de(e["id"]) if x.niveau == "localise"]
                echanges = [x for loc in localises for x in journal.get(loc.url, [])]
                relance = relance_emission(echanges)
                e["relance"] = relance.isoformat() if relance else None
                recent = dernier_echange(echanges)
                e["dernier_echange"] = (
                    {"date": recent.date.isoformat(), "canal": recent.canal}
                    if recent
                    else None
                )
                plus_avance = meilleur(maturites.de(e["id"]))
                e["dans_lmelp"] = maturites.dans_lmelp(self._emissions[e["id"]])
                integration = maturites.integration_lmelp(e["id"])
                e["integration_lmelp"] = (
                    integration.isoformat() if integration else None
                )
                e["maturite"] = plus_avance.niveau if plus_avance else None
                e["localisations"] = _localisations(localises, journal)
                echecs = [x.echec for x in maturites.de(e["id"]) if x.echec]
                dernier = max(echecs, key=lambda v: v.date, default=None)
                e["echec_rapatriement"] = (
                    {"date": dernier.date.isoformat(), "detail": dernier.detail}
                    if dernier
                    else None
                )
                e["fichier_audio"] = plus_avance.fichier if plus_avance else None
                ecart = plus_avance.ecart if plus_avance else None
                e["ecart"] = (
                    {"date": ecart.date.isoformat(), "motif": ecart.motif}
                    if ecart
                    else None
                )
                e["maturite_depuis"] = (
                    plus_avance.entrees[plus_avance.niveau].isoformat()
                    if plus_avance and plus_avance.niveau in plus_avance.entrees
                    else None
                )
            # les détenteurs déjà saisis, proposés à la saisie d'une piste
            donnees["detenteurs"] = sorted(
                {
                    x.source
                    for liste in maturites.par_emission.values()
                    for x in liste
                    if x.url.startswith("piste:")
                }
            )
            donnees["maturite_active"] = True
        return donnees

    def _pour_arbitrer(self, donnees: dict[str, Any]) -> dict[str, Any]:
        """Une émission de la page, avec ce qu'il faut pour arbitrer sa date et
        ses rapprochements."""
        emission = self._emissions[donnees["id"]]
        arbitrage = emission.arbitrage_date
        existence = emission.arbitrage_existence
        return {
            **donnees,
            "dates_candidates": [
                {
                    "date": jour.isoformat(),
                    "jour": JOURS[jour.weekday()],
                    "sources": sources,
                    "habituel": au_jour_habituel(jour),
                    "actuelle": jour == emission.date,
                }
                for jour, sources in dates_candidates(emission).items()
            ]
            if self._date_arbitrable(emission)
            else [],
            "arbitrage_date": (
                {
                    "date": arbitrage.date_retenue.isoformat(),
                    "justification": arbitrage.justification,
                }
                if arbitrage and arbitrage.date_retenue
                else None
            ),
            "arbitrage_existence": (
                {"justification": existence.justification} if existence else None
            ),
            "rapprochements": [
                {
                    "source": source,
                    "source_id": source_id,
                    "rivales": [i for i, _cle in rivales],
                }
                for (source, source_id), rivales in sorted(
                    self._ambigues.get(emission.id, {}).items()
                )
            ],
        }

    def _arbitrage(self, arbitrage: Arbitrage) -> dict[str, Any]:
        """Un arbitrage, avec ce que dit l'attestation qu'il porte."""
        attestation = self._par_cle.get(arbitrage.cle)
        return {
            "source": arbitrage.source,
            "source_id": arbitrage.source_id,
            "sorte": arbitrage.sorte,
            "valeur": valeur(arbitrage),
            "justification": arbitrage.justification,
            "date": arbitrage.date.isoformat(),
            "attestation": (
                {
                    "date": attestation.date.isoformat(),
                    "titre": attestation.titre,
                    "url": attestation.url,
                }
                if attestation
                else None
            ),
        }


def _localisations(
    localises: list[Enregistrement], journal: dict[str, list[Echange]]
) -> list[dict[str, Any]]:
    """Les enregistrements localisés d'une émission, du plus ancien au plus
    récent : leur identifiant, leur source, leur note, l'URL de leur notice
    INA, leur date d'entrée dans le niveau (toujours notée en y entrant), leur
    relance et leur journal des échanges, du plus récent au plus ancien."""
    return [
        {
            "id": x.url,
            "source": x.source,
            "note": x.note,
            "notice": x.url if x.url.startswith("http") else None,
            "depuis": x.entrees["localise"].isoformat(),
            "relance": _iso_jour(relance_piste(journal.get(x.url, []))),
            "journal": [
                {
                    "date": j.date.isoformat(),
                    "canal": j.canal,
                    "interlocuteur": j.interlocuteur,
                    "texte": j.texte,
                    "relance": _iso_jour(j.relance),
                }
                for j in sorted(
                    journal.get(x.url, []),
                    key=lambda j: (j.date, j.note_le),
                    reverse=True,
                )
            ],
        }
        for x in sorted(localises, key=lambda x: x.entrees["localise"])
    ]


def _iso_jour(jour: date | None) -> str | None:
    return jour.isoformat() if jour else None


def _aujourd_hui() -> date:
    """Le jour local du serveur."""
    return datetime.now().astimezone().date()


def _jour(texte: object, champ: str) -> date | None:
    """Un jour AAAA-MM-JJ d'une demande, ou ``None`` s'il est absent."""
    if texte in (None, ""):
        return None
    try:
        return date.fromisoformat(str(texte))
    except ValueError:
        raise DemandeInvalideError(
            f"{champ} invalide : {texte!r} (attendu : AAAA-MM-JJ)"
        ) from None


def _episode(document: dict[str, Any]) -> str:
    """Un épisode de lmelp dans un message : sa date et son titre."""
    quand = document.get("date")
    jour = quand.date().isoformat() if isinstance(quand, datetime) else "sans date"
    titre = document.get("titre")
    return f"du {jour}" + (f" (« {titre} »)" if titre else "")


def _iso(quand: datetime) -> str:
    """Une date de Mongo en ISO 8601 ; Mongo rend l'UTC sans fuseau."""
    return (quand if quand.tzinfo else quand.replace(tzinfo=UTC)).isoformat()


class _Lecture:
    """Le corps d'une requête, lu au plus ``taille`` octets."""

    def __init__(self, flux: Any, taille: int):
        self._flux = flux
        self.reste = taille

    def read(self, n: int = -1) -> bytes:
        n = self.reste if n < 0 else min(n, self.reste)
        morceau: bytes = self._flux.read(n) if n else b""
        self.reste -= len(morceau)
        return morceau

    def vider(self) -> None:
        """Lit et jette ce qui reste du corps."""
        while self.reste and self.read(1 << 20):
            pass


# Les routes POST : l'action de l'atelier, appelée avec le corps JSON
# (``/api/fichiers`` à part : le corps est le fichier).
ACTIONS_POST: dict[str, Callable[[Atelier, dict[str, Any]], Any]] = {
    "/api/arbitrages": Atelier.arbitrer,
    "/api/annulations": Atelier.annuler,
    "/api/verifications": lambda atelier, _demande: atelier.lancer_verification(),
    "/api/rapatriements": Atelier.lancer_rapatriement,
    "/api/rapatriements/arret": lambda atelier, _: atelier.arreter_rapatriement(),
    "/api/qualifications": Atelier.qualifier,
    "/api/localisations": Atelier.ajouter_localise,
    "/api/echanges": Atelier.noter_echange,
    "/api/urls": Atelier.ajouter_url,
    "/api/remises": Atelier.mettre_a_disposition,
    "/api/remises/annulation": Atelier.annuler_mise_a_disposition,
    "/api/collectes": Atelier.lancer_collecte,
}

# Le statut HTTP de chaque erreur qu'une route POST rend en JSON.
ERREURS_POST: dict[type[Exception], HTTPStatus] = {
    MaturiteIndisponibleError: HTTPStatus.SERVICE_UNAVAILABLE,
    TacheEnCoursError: HTTPStatus.CONFLICT,
    DemandeInvalideError: HTTPStatus.BAD_REQUEST,
    json.JSONDecodeError: HTTPStatus.BAD_REQUEST,
}


def _ressource(nom: str) -> str:
    """Un fichier livré avec le paquet (la page d'accueil)."""
    return files("lmelp_pap").joinpath(nom).read_text(encoding="utf-8")


# Le favicon de pap (``scripts/generer_favicon.py``), servi à la racine.
ICONES = {
    "favicon.ico": "image/x-icon",
    "favicon-32x32.png": "image/png",
    "apple-touch-icon.png": "image/png",
}
# Les icônes, elles, se gardent : servies en ``no-store``, Chrome les affiche
# dans l'onglet sans les enregistrer, et les favoris restent sans favicon.
CACHE_ICONES = "public, max-age=604800"


def creer_serveur(
    cache: Path,
    sortie: Path,
    *,
    port: int = 8765,
    hote: str = "127.0.0.1",
    arbitrages: Path | None = None,
    depot: Depot | None = None,
    session: Any = None,
    audios: Path | None = None,
    planification: bool = False,
    intervalle: timedelta = timedelta(days=7),
    audios_lmelp: Path | None = None,
) -> ThreadingHTTPServer:
    """Le serveur de l'outil, prêt à servir (``serve_forever``). Sans
    ``depot``, la maturité des enregistrements est absente. Avec
    ``planification``, la vérification des URL part seule quand elle est due
    (``Atelier.planifier``) ; l'atelier est ``serveur.atelier``."""
    atelier = Atelier(
        cache,
        sortie,
        fichier=arbitrages,
        depot=depot,
        session=session,
        audios=audios,
        intervalle=intervalle,
        audios_lmelp=audios_lmelp,
    )
    if planification and depot is not None:
        atelier.planifier_en_continu()

    class Requetes(BaseHTTPRequestHandler):
        """Les routes de la page et de l'API JSON."""

        repondu = False  # la ligne de statut est partie

        def do_GET(self) -> None:
            self._sans_panne(self._get)

        def do_POST(self) -> None:
            self._sans_panne(self._post)

        def _sans_panne(self, route: Callable[[], None]) -> None:
            """Sert la route ; une exception imprévue (Mongo injoignable…) va
            aux logs avec son type et sa trace et donne une 500 au message
            générique (rien du détail : il peut porter une adresse ou un
            identifiant), si la réponse n'est pas déjà partie."""
            try:
                route()
            except Exception as erreur:
                log.exception(
                    f"{self.command} {self.path} : erreur interne "
                    f"({type(erreur).__name__})"
                )
                if not self.repondu:
                    self._json(
                        {"erreur": "erreur interne"},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )

        def send_response(self, code: int, message: str | None = None) -> None:
            self.repondu = True
            super().send_response(code, message)

        def _get(self) -> None:
            """La page, les données courantes, ou l'état du service."""
            # le nom d'une icône, sans query string (``/favicon.ico?v=2``)
            nom = urlsplit(self.path).path.lstrip("/")
            if self.path == "/health":
                self._json({"status": "ok"})
            elif self.path in ("/", "/index.html"):
                self._repondre(
                    _ressource("accueil.html").encode(), "text/html; charset=utf-8"
                )
            elif self.path == "/liste":
                self._repondre(atelier.page().encode(), "text/html; charset=utf-8")
            elif self.path == "/api/donnees":
                self._json(atelier.donnees())
            elif self.path == "/api/verifications":
                self._json(atelier.etat_verification())
            elif self.path == "/api/rapatriements":
                self._json(atelier.etat_rapatriement())
            elif self.path == "/api/collectes":
                self._json(atelier.etat_collecte())
            elif self.path.startswith("/api/remises/"):
                emission_id = unquote(self.path.removeprefix("/api/remises/"))
                try:
                    self._json(atelier.fiche_remise(emission_id))
                except DemandeInvalideError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.NOT_FOUND)
            elif self.path.startswith("/api/radiofrance/"):
                emission_id = unquote(self.path.removeprefix("/api/radiofrance/"))
                try:
                    self._json(atelier.diffusion_radiofrance(emission_id))
                except DemandeInvalideError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.NOT_FOUND)
            elif self.path.startswith("/audios/"):
                self._audio()
            elif nom in ICONES:
                self._repondre(icone(nom), ICONES[nom], cache=CACHE_ICONES)
            else:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)

        def _post(self) -> None:
            """Une action de ``ACTIONS_POST`` sur le corps JSON de la requête ;
            chaque erreur connue donne son statut (``ERREURS_POST``)."""
            chemin, _, requete = self.path.partition("?")
            action = ACTIONS_POST.get(self.path)
            if action is None and chemin != "/api/fichiers":
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            try:
                if action is None:
                    self._json(self._fichier(dict(parse_qsl(requete))))
                else:
                    self._json(action(atelier, self._demande()))
            except tuple(ERREURS_POST) as e:
                statut = next(s for t, s in ERREURS_POST.items() if isinstance(e, t))
                log_http.info(f"POST {self.path} refusée ({statut.value}) : {e}")
                self._json({"erreur": str(e)}, statut)

        def _audio(self) -> None:
            """Un fichier du dossier audio, entier ou par plage (``Range``,
            206), pour l'écoute et le saut dans le fichier."""
            chemin = audio.fichier_audio(atelier.audios, self.path)
            if chemin is None:
                log.warning(f"audio introuvable : {self.path}")
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            audio.servir(self, chemin)

        def _fichier(self, parametres: dict[str, str]) -> dict[str, Any]:
            """Un fichier audio téléversé : le corps brut de la requête, ses
            champs dans la query string. Un refus lit quand même le reste du
            corps, pour que le navigateur reçoive la réponse."""
            taille = int(self.headers.get("Content-Length") or 0)
            flux = _Lecture(self.rfile, taille)
            try:
                return atelier.televerser(parametres, flux, taille)
            finally:
                flux.vider()

        def _demande(self) -> dict[str, Any]:
            """Le corps JSON de la requête, un objet."""
            taille = int(self.headers.get("Content-Length") or 0)
            demande = json.loads(self.rfile.read(taille) or b"{}")
            if not isinstance(demande, dict):
                raise DemandeInvalideError("un objet JSON est attendu")
            return demande

        def _json(self, donnees: object, statut: HTTPStatus = HTTPStatus.OK) -> None:
            """Répond en JSON."""
            corps = json.dumps(donnees, ensure_ascii=False).encode()
            self._repondre(corps, "application/json; charset=utf-8", statut)

        def _repondre(
            self,
            corps: bytes,
            type_: str,
            statut: HTTPStatus = HTTPStatus.OK,
            cache: str = "no-store",
        ) -> None:
            """Envoie la réponse, par défaut jamais mise en cache par le
            navigateur."""
            self.send_response(statut)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(corps)

        def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
            """Une ligne par requête (méthode, chemin, statut, client), hors
            ``/health`` et sondages de l'avancement (``SILENCIEUSES``)."""
            if (self.command, self.path) in SILENCIEUSES:
                return
            statut = code.value if isinstance(code, HTTPStatus) else code
            log_http.info(
                f"{self.command} {self.path} {statut} ({self.address_string()})"
            )

        def log_error(self, format: str, *args: Any) -> None:
            """Une requête malformée, refusée par le serveur."""
            log_http.warning(format % args)

        def log_message(self, format: str, *args: Any) -> None:
            """Rien d'autre du serveur HTTP sur la sortie d'erreur."""

    serveur = ThreadingHTTPServer((hote, port), Requetes)
    serveur.atelier = atelier  # type: ignore[attr-defined]
    return serveur
