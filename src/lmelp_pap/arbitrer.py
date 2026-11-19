"""Outil local ``lmelp-pap arbitrer`` : la page de la liste en mode arbitrage.

Un serveur HTTP de la bibliothèque standard sert la page et une petite API
JSON. À chaque arbitrage, il réécrit ``arbitrages.csv``, reconstruit la liste
depuis le cache, sans réseau, réécrit ses CSV et renvoie les données à jour.

API :

- ``GET /`` : la page en mode arbitrage ;
- ``GET /api/donnees`` : les données courantes ;
- ``POST /api/arbitrages`` : enregistre un arbitrage sur une émission
  (``emission_id``, ``sorte`` : ``thème``, ``existence``, ``date``,
  ``rapprochement`` ou ``écoute`` pour un renvoi à l'écoute, ``themes``,
  ``date``, ``justification``) ; un arbitrage d'existence porte en plus
  ``valeur`` : ``existe``, ou ``n'existe pas`` (par défaut) ; un arbitrage de rapprochement porte en plus
  l'attestation ambiguë (``source``, ``source_id``) et ``vers``, l'identifiant
  de l'émission rivale où la déplacer, ou ``null`` pour la garder ici ;
- ``POST /api/annulations`` : annule les arbitrages d'une émission
  (``emission_id``) ou d'une attestation (``source`` et ``source_id``).

Chaque requête d'écriture renvoie les données à jour, comme ``GET /api/donnees``.
Une émission y porte en plus, pour l'arbitrage de date, ses ``dates_candidates``
(vides sans doute de date ni date arbitrée) et son ``arbitrage_date`` ; son
``arbitrage_existence``, quand elle est arbitrée « existe » ; pour
l'arbitrage de rapprochement, ses ``rapprochements`` : chaque attestation
ambiguë (``source``, ``source_id``) avec ses ``rivales``.
"""

import json
import threading
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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
from lmelp_pap.page import construire_page, donnees_page


# Les doutes qu'un arbitrage de date lève.
DOUTES_DE_DATE = ("désaccord de date", "jour inhabituel")


class DemandeInvalideError(ValueError):
    """Une requête d'arbitrage invalide."""


class Atelier:
    """La liste en cours d'arbitrage : le cache lu une fois, les CSV réécrits."""

    def __init__(self, cache: Path, sortie: Path, fichier: Path | None = None):
        """Lit le cache et construit une première fois la liste."""
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
            return self._donnees()

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
            return self._donnees()

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
        return {
            "emissions": [self._pour_arbitrer(e) for e in donnees_page(self.sortie)],
            "arbitrages": [
                self._arbitrage(a) for a in reversed(lire_arbitrages(self.fichier))
            ],
        }

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


def creer_serveur(
    cache: Path,
    sortie: Path,
    port: int = 8765,
    hote: str = "127.0.0.1",
    arbitrages: Path | None = None,
) -> ThreadingHTTPServer:
    """Le serveur de l'outil, prêt à servir (``serve_forever``)."""
    atelier = Atelier(cache, sortie, arbitrages)

    class Requetes(BaseHTTPRequestHandler):
        """Les routes de la page et de l'API JSON."""

        def do_GET(self) -> None:
            """La page, ou les données courantes."""
            if self.path in ("/", "/index.html"):
                self._repondre(atelier.page().encode(), "text/html; charset=utf-8")
            elif self.path == "/api/donnees":
                self._json(atelier.donnees())
            else:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            """Un arbitrage ou une annulation ; erreur 400 si invalide."""
            actions = {
                "/api/arbitrages": atelier.arbitrer,
                "/api/annulations": atelier.annuler,
            }
            action = actions.get(self.path)
            if action is None:
                self._json({"erreur": "introuvable"}, HTTPStatus.NOT_FOUND)
                return
            try:
                taille = int(self.headers.get("Content-Length") or 0)
                demande = json.loads(self.rfile.read(taille) or b"{}")
                if not isinstance(demande, dict):
                    raise DemandeInvalideError("un objet JSON est attendu")
                self._json(action(demande))
            except (DemandeInvalideError, json.JSONDecodeError) as e:
                self._json({"erreur": str(e)}, HTTPStatus.BAD_REQUEST)

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

    return ThreadingHTTPServer((hote, port), Requetes)
