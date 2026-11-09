"""Fichiers audio du podcast conservés par la Wayback Machine (API CDX).

Requête : ``/cdx/search/cdx?url=media.radiofrance-podcast.net/podcast09/14007-
&matchType=prefix&fl=original,statuscode&collapse=urlkey``. Chaque ligne donne
l'URL d'origine d'un fichier et le statut HTTP de sa capture.
"""

from lmelp_pap.liste import Attestation, Enregistrement
from lmelp_pap.sources.audio_radiofrance import lire_nom_fichier


SOURCE = "wayback_podcast"
_CAPTURES_VALIDES = {"200", "206"}


def lire_cdx(texte: str) -> list[Attestation]:
    """Une attestation par identifiant ITEMA.

    Un fichier dont la capture a échoué atteste quand même l'émission (son nom
    porte la date), mais ne fournit pas d'enregistrement.
    """
    par_itema: dict[str, tuple[Attestation, list[Enregistrement]]] = {}
    for ligne in texte.splitlines():
        champs = ligne.split()
        if len(champs) < 2:
            continue
        url, statut = champs[0].split("?", 1)[0], champs[1]
        url = url.replace("http://", "https://", 1)
        fichier = lire_nom_fichier(url)
        if fichier is None:
            continue
        _attestation, enregistrements = par_itema.setdefault(
            fichier.itema,
            (
                Attestation(
                    source=SOURCE,
                    source_id=fichier.itema,
                    date=fichier.date,
                    extrait=fichier.type == "extrait",
                ),
                [],
            ),
        )
        enregistrement = Enregistrement(url=url, type=fichier.type)
        if statut in _CAPTURES_VALIDES and enregistrement not in enregistrements:
            enregistrements.append(enregistrement)

    return [
        Attestation(
            source=a.source,
            source_id=a.source_id,
            date=a.date,
            enregistrements=tuple(enregistrements),
            extrait=a.extrait,
        )
        for a, enregistrements in par_itema.values()
    ]
