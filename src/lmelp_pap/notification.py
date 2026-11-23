"""Les notifications ntfy de l'appli, comme celles de ``lmelp-export`` et du
back-office lmelp : mêmes variables, même topic, titres préfixés « pap - ».

- ``NTFY_TOPIC`` : le topic ; absent, aucune notification ;
- ``NTFY_SERVER_URL`` : le serveur (``https://ntfy.sh`` par défaut) ;
- ``NTFY_TOKEN`` : un jeton d'accès, pour un serveur protégé (facultatif).

Une notification ne fait jamais échouer l'action qui la demande : une erreur
réseau laisse un avertissement dans les logs.
"""

import json
import logging
import os
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any


log = logging.getLogger(__name__)

SERVEUR = "https://ntfy.sh"
PREFIXE = "pap - "


def notifier(
    titre: str,
    message: str,
    *,
    priorite: int = 3,
    tags: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
    envoyer: Callable[..., Any] = urllib.request.urlopen,
) -> bool:
    """Publie la notification (API JSON de ntfy) ; vrai si elle est partie.
    ``env`` : l'environnement (``os.environ`` par défaut), ``envoyer`` :
    ``urlopen``."""
    env = os.environ if env is None else env
    titre = PREFIXE + titre
    topic = env.get("NTFY_TOPIC")
    if not topic:
        log.info(f"notification ntfy non configurée (NTFY_TOPIC absent) : {titre}")
        return False
    entetes = {"Content-Type": "application/json"}
    if jeton := env.get("NTFY_TOKEN"):
        entetes["Authorization"] = f"Bearer {jeton}"
    requete = urllib.request.Request(
        (env.get("NTFY_SERVER_URL") or SERVEUR).rstrip("/"),
        data=json.dumps(
            {
                "topic": topic,
                "title": titre,
                "message": message,
                "priority": priorite,
                "tags": list(tags),
            }
        ).encode(),
        headers=entetes,
        method="POST",
    )
    try:
        envoyer(requete, timeout=10)
    except Exception as erreur:  # noqa: BLE001 — jamais bloquant
        log.warning(f"notification ntfy non envoyée ({titre}) : {erreur}")
        return False
    log.info(f"notification ntfy envoyée : {titre}")
    return True
