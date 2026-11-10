"""Lecture des anciennes listes d'émissions de France Inter, archivées par la Wayback Machine.

Deux formats :

- 2002-2008, liste annuelle ``radiofrance.fr/franceinter/em/lemasqueetlaplume/
  archives.php?annee=AAAA`` : ``<strong>17/12/2006</strong> ><a href="index.php?
  id=49171">Livres</a>`` ;
- 2009-2012, liste mensuelle ``franceinter.fr/archives-diffusions/319/AAAA-MM`` :
  ``<h3><a href="/em/lemasqueetlaplume/100998">Livres</a></h3><div class="date
  gris"> du 13/03/2011</div><div class="description"><p>…</p>``.
"""

import html as html_lib
import re
from datetime import date

from lmelp_pap.liste import Attestation


SOURCE = "anciennes_listes"

_ANNUELLE = re.compile(
    r"<strong>(?P<date>\d{2}/\d{2}/\d{4})</strong>\s*>"
    r'<a href="index\.php\?id=(?P<id>\d+)">(?P<libelle>[^<]*)</a>'
)
_MENSUELLE = re.compile(
    r'<h3><a href="/em/lemasqueetlaplume/(?P<id>\d+)"[^>]*>(?P<libelle>[^<]*)</a>'
    r'</h3><div class="date gris">\s*du\s*(?P<date>\d{2}/\d{2}/\d{4})</div>'
    r'(?:<div class="description"><p>(?P<description>.*?)</p>)?',
    re.DOTALL,
)
_SANS_EMISSION = re.compile(r"pas de masque|aucune émission", re.IGNORECASE)
_THEMES = (
    (re.compile(r"livre|prix des auditeurs", re.IGNORECASE), "livres"),
    (re.compile(r"cinéma|cannes", re.IGNORECASE), "cinéma"),
    (re.compile(r"théâtre|avignon", re.IGNORECASE), "théâtre"),
    (re.compile(r"opéra|aix-en-provence", re.IGNORECASE), "opéra"),
)


def lire_liste(page: str) -> list[Attestation]:
    """Une attestation par émission listée ; un dimanche sans émission est ignoré."""
    attestations = []
    for motif in (_ANNUELLE, _MENSUELLE):
        for m in motif.finditer(page):
            libelle = _texte(m["libelle"])
            if libelle is None or _SANS_EMISSION.search(libelle):
                continue
            jour, mois, annee = (int(x) for x in m["date"].split("/"))
            attestations.append(
                Attestation(
                    source=SOURCE,
                    source_id=f"em-{m['id']}",
                    date=date(annee, mois, jour),
                    themes=frozenset(t for cle, t in _THEMES if cle.search(libelle)),
                    titre=libelle,
                    description=_texte(m.groupdict().get("description")),
                )
            )
    return attestations


def _texte(valeur: str | None) -> str | None:
    """Le texte d'un fragment HTML, entités décodées, espaces réduits, ou None."""
    if not valeur:
        return None
    texte = re.sub(r"\s+", " ", html_lib.unescape(valeur)).strip()
    return texte or None
