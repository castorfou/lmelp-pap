"""Outil local ``lmelp-pap arbitrer`` : la page de la liste en mode arbitrage.

Un serveur HTTP de la bibliothèque standard sert la page et une petite API
JSON. À chaque arbitrage, il réécrit ``arbitrages.csv``, reconstruit la liste
depuis le cache, sans réseau, réécrit ses CSV et renvoie les données à jour.

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
- ``GET /api/radiofrance/<emission_id>`` : la diffusion de l'émission dans
  l'Open API Radio France, lue à la demande (module ``radiofrance_api``) :
  ``statut`` (``trouvee``, ``introuvable``, ``sans_cle``, ``erreur`` avec son
  ``detail``) et ``diffusion`` (``titre``, ``resume``, ``url``, ``equipe`` et
  ``invites`` : ``nom``, ``role``) ; rien n'en est conservé ;
- ``POST /api/remises`` : met à disposition de lmelp l'enregistrement qualifié
  de chaque émission (``emissions``) : copie dans le dossier audio de lmelp,
  fiche ``pap_remises``, passage à valide ; la réponse porte en plus
  ``remise`` (``mises``, ``refus`` avec leur ``detail``) ;
- ``GET /audios/<fichier>`` : un fichier du dossier audio, avec les requêtes
  ``Range`` (206) pour le saut ; rien hors du dossier audio.

Avec un dépôt Mongo, chaque émission des données porte sa ``maturite`` (le
niveau de son enregistrement le plus avancé, ou ``null``), ``maturite_depuis``
(la date d'entrée dans ce niveau), ``fichier_audio`` (le fichier écoutable,
relatif au dossier audio), ``ecart`` (``date``, ``motif``), ``dans_lmelp``
(attestée par lmelp, ou un épisode de lmelp porte le fichier d'un de ses
enregistrements valides) et les données ``maturite_active`` ; sans dépôt, la
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
import sys
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from lmelp_pap import audio
from lmelp_pap.arbitrages import (
    EXISTANTE,
    INEXISTANTE,
    ajouter_arbitrage,
    erreur_de_themes,
    lire_arbitrages,
    lire_date,
    retirer_arbitrages,
    valeur,
)
from lmelp_pap.collecte import lire_cache
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
    Enregistrement,
    QualificationError,
    RapatriementError,
    RapatriementInterrompuError,
    Resultat,
    Verification,
    ecrire_qualifications,
    integraux,
    meilleur,
    qualifier,
    rapatrier,
    retenu,
    verification_due,
    verifier,
)
from lmelp_pap.page import construire_page, donnees_page
from lmelp_pap.radiofrance_api import (
    QUOTA,
    ApiRadioFranceError,
    Diffusion,
    LecteurDiffusions,
    jeton,
)
from lmelp_pap.remise import RemiseError, mettre_a_disposition


# Les doutes qu'un arbitrage de date lève.
DOUTES_DE_DATE = ("désaccord de date", "jour inhabituel")


# Période du fil de planification de la vérification des URL, en secondes.
PLANIFICATION = 3600

# Les dossiers audio par défaut : celui de pap (enregistrements rapatriés) et
# celui du back-office lmelp (enregistrements mis à disposition).
AUDIOS = Path("data/raw/audios")
AUDIOS_LMELP = Path("data/raw/audios-lmelp")


def _s(n: int) -> str:
    """Le « s » du pluriel."""
    return "s" if n > 1 else ""


def _duree(secondes: float) -> str:
    """Une durée lisible : « 16 s », « 3 min 41 s »."""
    s = round(secondes)
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60} s"


def journal(message: str) -> None:
    """Une ligne horodatée dans les logs (sortie d'erreur, ``docker logs``)."""
    horodatage = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    # un seul write : les lignes de deux fils ne se mêlent pas
    sys.stderr.write(f"{horodatage} {message}\n")
    sys.stderr.flush()


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


class DemandeInvalideError(ValueError):
    """Une requête d'arbitrage invalide."""


class MaturiteIndisponibleError(RuntimeError):
    """La maturité des enregistrements demande une base Mongo."""


class TacheEnCoursError(RuntimeError):
    """Une tâche de fond du même genre tourne déjà."""


class Tache:
    """Une tâche de fond (vérification, rapatriement) et son avancement :
    ``en_cours``, ``faites``, ``total``, ``bilan`` une fois finie, et les
    champs propres à la tâche."""

    def __init__(self, **champs: Any):
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

    def lancer(self, total: int, travail: Any, refuser: bool = False) -> dict[str, Any]:
        """Lance ``travail(tache)`` dans un fil, qui rend le bilan. Une tâche
        déjà en cours est rendue telle quelle, ou refusée si ``refuser``."""
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
            }
            self._arret.clear()

        def executer() -> None:
            bilan = None
            try:
                bilan = travail(self)
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
        # l'API Radio France, avec son cache en mémoire partagé par l'écoute
        # et la mise à disposition
        self._radiofrance = LecteurDiffusions(session)
        self.intervalle = intervalle  # entre deux vérifications complètes
        self.planification = False
        self._verification = Tache()
        self._rapatriement = Tache(
            en_cours_sur=None,
            erreurs=[],
            octets=0,
            fichier_octets=0,
            fichier_total=None,
            debut=None,
            arrete=False,
            rapatriees=[],  # émissions rapatriées (ou déjà là) pendant le lot
        )
        self.sortie = sortie
        self.fichier = fichier or sortie / "arbitrages.csv"
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
        journal(
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
            journal(
                f"vérification terminée en {round(time.monotonic() - debut)} s : "
                f"{bilan['ok']} ok, {bilan['net']} mortes, "
                f"{bilan['passager']} échecs passagers"
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
        """Une reconstruction peut apporter des URL d'intégral nouvelles."""
        if self.planification:
            self.planifier()

    def planifier_en_continu(self, periode: float = PLANIFICATION) -> None:
        """Vérifie au démarrage, puis toutes les ``periode`` secondes, si une
        vérification est due (fil de fond)."""

        def boucle() -> None:
            while True:
                try:
                    self.planifier()
                except Exception:  # noqa: BLE001 — la planification ne doit pas mourir
                    traceback.print_exc()  # visible dans les logs du conteneur
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
            journal(
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
                    journal(
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
                    journal(
                        f"{'déjà là' if deja else 'rapatrié'} "
                        f"{enregistrement.emission_id} : {fait.fichier}, "
                        f"{round((fait.taille or 0) / 1e6)} Mo en "
                        f"{round(time.monotonic() - debut)} s"
                    )
                except RapatriementInterrompuError:
                    tache.maj(arrete=True, octets=recus)
                    journal(f"rapatriement arrêté pendant {enregistrement.emission_id}")
                    break
                except Exception as erreur:  # noqa: BLE001 — l'erreur va au bilan
                    bilan["echecs"] += 1
                    detail = str(erreur) or type(erreur).__name__
                    journal(f"échec {enregistrement.emission_id} : {detail}")
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
            journal(
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
            journal(f"qualification refusée {emission_id or '?'} : {erreur}")
            raise DemandeInvalideError(str(erreur)) from erreur
        if qualification.verdict == "favorable":
            journal(f"qualifié {emission_id} ({fait.fichier}) : favorable")
        else:
            journal(
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
            journal(f"api radiofrance {emission_id} : émission inconnue")
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
            journal(f"{prefixe} pas de clé")
            return "sans_cle", None, None
        debut = time.monotonic()

        def requetes(n: int, du_jour: int) -> str:
            return f"{n} requête{_s(n)} ({du_jour}/{QUOTA} aujourd'hui)"

        try:
            lecture = self._radiofrance.lire(
                emission.id, emission.date, emission.pages_radiofrance, cle
            )
        except ApiRadioFranceError as erreur:
            journal(
                f"{prefixe} erreur {erreur}, "
                f"{requetes(erreur.requetes, erreur.du_jour)}, "
                f"{_duree(time.monotonic() - debut)}"
            )
            return "erreur", None, str(erreur)
        statut = "trouvee" if lecture.diffusion else "introuvable"
        libelle = "trouvée" if lecture.diffusion else "introuvable"
        compte = requetes(lecture.requetes, lecture.du_jour)
        if lecture.cache:
            journal(f"{prefixe} {libelle} (cache), {compte}")
        else:
            journal(
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
                    journal(
                        f"mise à disposition refusée {emission_id} "
                        f"(niveau {niveau}) : {erreur}"
                    )
                    refus.append({"emission": emission_id, "detail": str(erreur)})
                    continue
                relatif = fait.fichier or ""
                journal(
                    f"mis à disposition {emission_id} : {self.audios / relatif} → "
                    f"{self.audios_lmelp / relatif} (sha256 {(fait.sha256 or '')[:12]}"
                    f"{', API Radio France' if api else ''}"
                    f"{', reprise : fichier déjà copié, même sha256' if reprise else ''})"
                )
                mises.append({"emission": emission_id, "fichier": relatif})
        journal(
            f"mise à disposition : {len(mises)} mise{_s(len(mises))} à disposition, "
            f"{len(refus)} refus"
        )
        return {**self.donnees(), "remise": {"mises": mises, "refus": refus}}

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
            ajouter_arbitrage(self.fichier, arbitrage)
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
            if not retirer_arbitrages(self.fichier, cles):
                raise DemandeInvalideError("aucun arbitrage à annuler")
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

    def _reconstruire(self) -> None:
        """Reconstruit la liste avec les arbitrages du fichier et réécrit ses CSV."""
        liste, doutes = construire_liste(
            self.attestations, lire_arbitrages(self.fichier)
        )
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
                self._arbitrage(a) for a in reversed(lire_arbitrages(self.fichier))
            ],
        }
        if self.depot is not None:
            maturites = Maturites(self.depot)
            for e in emissions:
                plus_avance = meilleur(maturites.de(e["id"]))
                e["dans_lmelp"] = maturites.dans_lmelp(self._emissions[e["id"]])
                e["maturite"] = plus_avance.niveau if plus_avance else None
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


# Les routes POST : l'action de l'atelier, appelée avec le corps JSON.
ACTIONS_POST: dict[str, Callable[[Atelier, dict[str, Any]], Any]] = {
    "/api/arbitrages": Atelier.arbitrer,
    "/api/annulations": Atelier.annuler,
    "/api/verifications": lambda atelier, _demande: atelier.lancer_verification(),
    "/api/rapatriements": Atelier.lancer_rapatriement,
    "/api/rapatriements/arret": lambda atelier, _: atelier.arreter_rapatriement(),
    "/api/qualifications": Atelier.qualifier,
    "/api/remises": Atelier.mettre_a_disposition,
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


def _icone(nom: str) -> bytes:
    """Une icône livrée avec le paquet (``lmelp_pap/icones/``)."""
    return files("lmelp_pap").joinpath("icones", nom).read_bytes()


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

        def do_GET(self) -> None:
            """La page, les données courantes, ou l'état du service."""
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
            elif self.path.startswith("/api/radiofrance/"):
                emission_id = unquote(self.path.removeprefix("/api/radiofrance/"))
                try:
                    self._json(atelier.diffusion_radiofrance(emission_id))
                except DemandeInvalideError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.NOT_FOUND)
            elif self.path.startswith("/audios/"):
                self._audio()
            elif self.path.lstrip("/") in ICONES:
                nom = self.path.lstrip("/")
                self._repondre(_icone(nom), ICONES[nom])
            else:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            """Une action de ``ACTIONS_POST`` sur le corps JSON de la requête ;
            chaque erreur connue donne son statut (``ERREURS_POST``)."""
            action = ACTIONS_POST.get(self.path)
            if action is None:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            try:
                self._json(action(atelier, self._demande()))
            except tuple(ERREURS_POST) as e:
                statut = next(s for t, s in ERREURS_POST.items() if isinstance(e, t))
                self._json({"erreur": str(e)}, statut)

        def _audio(self) -> None:
            """Un fichier du dossier audio, entier ou par plage (``Range``,
            206), pour l'écoute et le saut dans le fichier."""
            chemin = audio.fichier_audio(atelier.audios, self.path)
            if chemin is None:
                journal(f"audio introuvable : {self.path}")
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            audio.servir(self, chemin)

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
            self, corps: bytes, type_: str, statut: HTTPStatus = HTTPStatus.OK
        ) -> None:
            """Envoie la réponse, jamais mise en cache par le navigateur."""
            self.send_response(statut)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, format: str, *args: Any) -> None:
            """Pas de ligne par requête dans le terminal."""

    serveur = ThreadingHTTPServer((hote, port), Requetes)
    serveur.atelier = atelier  # type: ignore[attr-defined]
    return serveur
