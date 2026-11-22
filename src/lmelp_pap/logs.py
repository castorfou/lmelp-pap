"""Les logs de l'appli : le module ``logging`` de la bibliothèque standard.

Chaque module écrit dans son logger (``logging.getLogger(__name__)``), sous
``lmelp_pap`` ; ``configurer`` dirige ce logger vers la sortie d'erreur, que
``docker logs`` montre, une ligne par événement :

    2026-11-21 14:03:12 INFO    arbitrer : vérification manuelle (complète) : 3 URL

horodatage local, niveau, module (sans le préfixe ``lmelp_pap.``), message.
"""

import logging
import sys


RACINE = "lmelp_pap"
FORMAT = "%(asctime)s %(levelname)-7s %(module_court)s : %(message)s"
HORODATAGE = "%Y-%m-%d %H:%M:%S"


class _Format(logging.Formatter):
    """Le format des lignes : le module sans le préfixe du paquet."""

    def format(self, record: logging.LogRecord) -> str:
        record.module_court = record.name.removeprefix(f"{RACINE}.")
        return super().format(record)


class _SortieErreur(logging.StreamHandler):
    """Écrit dans la sortie d'erreur du moment (``sys.stderr`` relu à chaque
    ligne : une capture de tests ou une redirection est suivie)."""

    @property
    def stream(self) -> object:
        return sys.stderr

    @stream.setter
    def stream(self, _valeur: object) -> None:
        pass


def configurer(niveau: int = logging.INFO) -> None:
    """Dirige les logs du paquet vers la sortie d'erreur, une seule fois."""
    logger = logging.getLogger(RACINE)
    logger.setLevel(niveau)
    if not any(isinstance(h, _SortieErreur) for h in logger.handlers):
        sortie = _SortieErreur()
        sortie.setFormatter(_Format(FORMAT, HORODATAGE))
        logger.addHandler(sortie)
