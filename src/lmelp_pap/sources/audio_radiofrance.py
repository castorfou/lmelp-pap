"""Noms des fichiers audio du podcast Radio France du Masque et la Plume.

Exemple : ``14007-04.12.1958-ITEMA_24232446-1958F4007E0005-…-27.m4a``

- ``14007`` : le podcast du Masque et la Plume ;
- ``04.12.1958`` : la date de l'émission d'origine ;
- ``ITEMA_24232446`` : l'identifiant d'archive Radio France ;
- ``1958F4007E0005`` : le code de publication. Après ``F4007``, ``S`` désigne
  une émission diffusée et ``E`` un épisode d'une série d'archives (un extrait).
"""

import re
from dataclasses import dataclass
from datetime import date


_MOTIF = re.compile(
    r"/14007-(?P<jour>\d{2})\.(?P<mois>\d{2})\.(?P<annee>\d{4})"
    r"-(?P<itema>ITEMA_\d+)(?:-\d{4}F4007(?P<lettre>[SE])\d+)?"
)


@dataclass(frozen=True)
class FichierAudio:
    """Ce que le nom d'un fichier audio dit de l'émission."""

    date: date
    itema: str
    type: str  # "intégral" ou "extrait"


def lire_nom_fichier(url: str) -> FichierAudio | None:
    """Interprète l'URL d'un fichier audio du podcast, ou None si elle n'en est pas un."""
    m = _MOTIF.search(url)
    if m is None:
        return None
    return FichierAudio(
        date=date(int(m["annee"]), int(m["mois"]), int(m["jour"])),
        itema=m["itema"],
        type="extrait" if m["lettre"] == "E" else "intégral",
    )
