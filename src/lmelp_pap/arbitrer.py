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
- ``GET /audios/<fichier>`` : un fichier du dossier audio, avec les requêtes
  ``Range`` (206) pour le saut ; rien hors du dossier audio.

Avec un dépôt Mongo, chaque émission des données porte sa ``maturite`` (le
niveau de son enregistrement le plus avancé, ou ``null``), ``maturite_depuis``
(la date d'entrée dans ce niveau), ``fichier_audio`` (le fichier écoutable,
relatif au dossier audio), ``ecart`` (``date``, ``motif``) et les données
``maturite_active`` ; sans dépôt, la vérification, le rapatriement et la
qualification répondent 503.

Chaque requête d'écriture renvoie les données à jour, comme ``GET /api/donnees``.
Une émission y porte en plus, pour l'arbitrage de date, ses ``dates_candidates``
(vides sans doute de date ni date arbitrée) et son ``arbitrage_date`` ; son
``arbitrage_existence``, quand elle est arbitrée « existe » ; pour
l'arbitrage de rapprochement, ses ``rapprochements`` : chaque attestation
ambiguë (``source``, ``source_id``) avec ses ``rivales``.
"""

import json
import mimetypes
import sys
import threading
import time
import traceback
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

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
    MORCEAU,
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


# Les doutes qu'un arbitrage de date lève.
DOUTES_DE_DATE = ("désaccord de date", "jour inhabituel")


# Période du fil de planification de la vérification des URL, en secondes.
PLANIFICATION = 3600


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
        fichier: Path | None = None,
        depot: Depot | None = None,
        session: Any = None,
        audios: Path | None = None,
        intervalle: timedelta = timedelta(days=7),
    ):
        """Lit le cache et construit une première fois la liste. ``depot`` :
        la maturité des enregistrements (Mongo), ``session`` : le client HTTP
        de la vérification et du rapatriement (``requests`` par défaut),
        ``audios`` : le dossier des enregistrements rapatriés."""
        self.depot = depot
        self._session = session
        self.audios = audios or Path("data/raw/audios")
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
            par_emission: dict[str, list[Any]] = {}
            for enregistrement in self.depot.tous():
                par_emission.setdefault(enregistrement.emission_id, []).append(
                    enregistrement
                )
            for e in emissions:
                plus_avance = meilleur(par_emission.get(e["id"], []))
                e["maturite"] = plus_avance.niveau if plus_avance else None
                echecs = [x.echec for x in par_emission.get(e["id"], []) if x.echec]
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


TYPES_AUDIO = {".m4a": "audio/mp4", ".mp3": "audio/mpeg"}


def fichier_audio(dossier: Path, chemin_url: str) -> Path | None:
    """Le fichier que désigne ``/audios/<chemin>`` dans le dossier audio, ou
    ``None`` s'il n'existe pas ou sort du dossier."""
    relatif = unquote(urlsplit(chemin_url).path.removeprefix("/audios/"))
    racine = dossier.resolve()
    chemin = (racine / relatif).resolve()
    if not relatif or not chemin.is_relative_to(racine) or not chemin.is_file():
        return None
    return chemin


def plage(entete: str | None, taille: int) -> tuple[int, int] | None:
    """Les bornes (incluses) d'une plage ``bytes=a-b``, ``bytes=a-`` ou
    ``bytes=-n`` ; ``None`` sans plage lisible (tout le fichier) ;
    ``ValueError`` pour une plage hors du fichier (416)."""
    if not entete or not entete.startswith("bytes=") or "," in entete:
        return None
    debut, _, fin = entete.removeprefix("bytes=").strip().partition("-")
    if not (debut.isdigit() or fin.isdigit()) or not (debut + fin).isdigit():
        return None
    if not debut:  # les n derniers octets
        n = int(fin)
        if n == 0 or taille == 0:
            raise ValueError("plage vide")
        return max(0, taille - n), taille - 1
    a = int(debut)
    b = min(int(fin), taille - 1) if fin else taille - 1
    if a >= taille or a > b:
        raise ValueError("plage hors du fichier")
    return a, b


def type_audio(chemin: Path) -> str:
    """Le type MIME d'un fichier audio, d'après son extension."""
    return TYPES_AUDIO.get(chemin.suffix.lower()) or (
        mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    )


def _ressource(nom: str) -> str:
    """Un fichier livré avec le paquet (la page d'accueil)."""
    return files("lmelp_pap").joinpath(nom).read_text(encoding="utf-8")


def creer_serveur(
    cache: Path,
    sortie: Path,
    port: int = 8765,
    hote: str = "127.0.0.1",
    arbitrages: Path | None = None,
    depot: Depot | None = None,
    session: Any = None,
    audios: Path | None = None,
    planification: bool = False,
    intervalle: timedelta = timedelta(days=7),
) -> ThreadingHTTPServer:
    """Le serveur de l'outil, prêt à servir (``serve_forever``). Sans
    ``depot``, la maturité des enregistrements est absente. Avec
    ``planification``, la vérification des URL part seule quand elle est due
    (``Atelier.planifier``) ; l'atelier est ``serveur.atelier``."""
    atelier = Atelier(cache, sortie, arbitrages, depot, session, audios, intervalle)
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
            elif self.path.startswith("/audios/"):
                self._audio()
            else:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            """Un arbitrage, une annulation ou une vérification ; erreur 400 si
            la demande est invalide, 503 sans base pour la maturité."""
            if self.path == "/api/verifications":
                try:
                    self._json(atelier.lancer_verification())
                except MaturiteIndisponibleError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if self.path == "/api/rapatriements/arret":
                self._json(atelier.arreter_rapatriement())
                return
            if self.path == "/api/rapatriements":
                try:
                    self._json(atelier.lancer_rapatriement(self._demande()))
                except MaturiteIndisponibleError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.SERVICE_UNAVAILABLE)
                except TacheEnCoursError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.CONFLICT)
                except (DemandeInvalideError, json.JSONDecodeError) as e:
                    self._json({"erreur": str(e)}, HTTPStatus.BAD_REQUEST)
                return
            if self.path == "/api/qualifications":
                try:
                    self._json(atelier.qualifier(self._demande()))
                except MaturiteIndisponibleError as e:
                    self._json({"erreur": str(e)}, HTTPStatus.SERVICE_UNAVAILABLE)
                except (DemandeInvalideError, json.JSONDecodeError) as e:
                    self._json({"erreur": str(e)}, HTTPStatus.BAD_REQUEST)
                return
            actions = {
                "/api/arbitrages": atelier.arbitrer,
                "/api/annulations": atelier.annuler,
            }
            action = actions.get(self.path)
            if action is None:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            try:
                self._json(action(self._demande()))
            except (DemandeInvalideError, json.JSONDecodeError) as e:
                self._json({"erreur": str(e)}, HTTPStatus.BAD_REQUEST)

        def _audio(self) -> None:
            """Un fichier du dossier audio, entier ou par plage (``Range``,
            206), pour l'écoute et le saut dans le fichier."""
            chemin = fichier_audio(atelier.audios, self.path)
            if chemin is None:
                journal(f"audio introuvable : {self.path}")
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            taille = chemin.stat().st_size
            try:
                bornes = plage(self.headers.get("Range"), taille)
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{taille}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            debut, fin = bornes or (0, taille - 1)
            self.send_response(HTTPStatus.PARTIAL_CONTENT if bornes else HTTPStatus.OK)
            self.send_header("Content-Type", type_audio(chemin))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(fin - debut + 1))
            if bornes:
                self.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
            self.end_headers()
            reste = fin - debut + 1
            try:
                with chemin.open("rb") as f:
                    f.seek(debut)
                    while reste > 0 and (morceau := f.read(min(MORCEAU, reste))):
                        self.wfile.write(morceau)
                        reste -= len(morceau)
            except (BrokenPipeError, ConnectionResetError):
                pass  # le lecteur a sauté ailleurs : il abandonne la plage

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
