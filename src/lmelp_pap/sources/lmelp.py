"""Émissions vérifiées de lmelp, source vérifiée (ADR 0003).

La collecte copie de la base Mongo de lmelp, pour chaque émission vérifiée,
la page radiofrance.fr de son épisode, son titre, sa date de publication dans
le podcast (UTC) et le nom de son fichier audio.
"""

from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

from lmelp_pap.liste import Attestation


SOURCE = "lmelp"
_PARIS = ZoneInfo("Europe/Paris")


def lire_emissions(emissions: Iterable[dict[str, str]]) -> list[Attestation]:
    """Une attestation par émission vérifiée, identifiée par sa fiche radiofrance.

    Le thème « livres » fait foi : lmelp ne retient que des émissions
    littéraires, vérifiées à la main.
    """
    return [
        Attestation(
            source=SOURCE,
            source_id=e["page"].rstrip("/").rsplit("/", 1)[-1],
            date=datetime.fromisoformat(e["publication"]).astimezone(_PARIS).date(),
            nature_date="publication",
            themes=frozenset({"livres"}),
            titre=e["titre"],
            url=e["page"],
        )
        for e in emissions
    ]
