"""Construction de la liste des émissions à partir des attestations des sources.

Vocabulaire : voir CONTEXT.md. Décisions : docs/adr/0001, 0002 et 0003.
"""

import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from lmelp_pap.sources.audio_radiofrance import lire_nom_fichier


@dataclass(frozen=True)
class Enregistrement:
    """Un fichier audio d'une émission, intégral ou extrait."""

    url: str
    type: str  # "intégral" ou "extrait"


@dataclass(frozen=True)
class Attestation:
    """Ce qu'une source dit d'une émission, à une date donnée."""

    source: str
    source_id: str
    date: date
    themes: frozenset[str] = frozenset()
    titre: str | None = None
    description: str | None = None
    chaine: str | None = None
    heure: str | None = None
    duree: str | None = None
    animateur: str | None = None
    url: str | None = None
    enregistrements: tuple[Enregistrement, ...] = ()
    extrait: bool = False  # un fragment, qui ne décrit pas l'émission entière
    # La date de première diffusion, ou de publication dans le podcast (lmelp) :
    # une date de publication ne date pas l'émission.
    nature_date: Literal["première diffusion", "publication"] = "première diffusion"


@dataclass
class Emission:
    """Une émission de la liste, construite à partir de ses attestations."""

    id: str
    date: date
    themes: frozenset[str]
    titre: str | None = None
    description: str | None = None
    chaine: str | None = None
    heure: str | None = None
    duree: str | None = None
    animateur: str | None = None
    attestations: list[Attestation] = field(default_factory=list)
    enregistrements: list[Enregistrement] = field(default_factory=list)


@dataclass(frozen=True)
class Doute:
    """Un point d'une émission que les sources ne permettent pas d'affirmer."""

    type: str
    emission_id: str
    dans_la_liste: bool
    source: str
    source_id: str
    detail: str


def construire_liste(
    attestations: list[Attestation],
) -> tuple[list[Emission], list[Doute]]:
    """Rapproche les attestations, construit la liste et détecte ses doutes.

    Les doutes portent sur toutes les émissions, dans la liste ou non.
    """
    groupes: list[list[Attestation]] = []
    for a in sorted(attestations, key=lambda a: a.date):
        if a.source not in SOURCES_VERIFIEES:
            _rapprocher(a, groupes)
    for a in attestations:
        if a.source in SOURCES_VERIFIEES:
            fiche = [g for g in groupes if any(_meme_fiche(a, b) for b in g)]
            if fiche:
                fiche[0].append(a)
            else:
                _rapprocher(a, groupes)

    emissions = sorted((_fusionner(g) for g in groupes), key=_cle_de_tri)
    _attribuer_identifiants(emissions)
    liste = [e for e in emissions if _dans_la_liste(e)]
    return liste, _doutes(emissions)


def _doutes(emissions: list[Emission]) -> list[Doute]:
    doutes: list[Doute] = []
    # la première diffusion de la dernière émission vérifiée, pas sa publication
    derniere_verifiee = max(
        (e.date for e in emissions if _verifiee(e)),
        default=None,
    )
    for emission in emissions:
        dans_la_liste = _dans_la_liste(emission)

        def ajouter(
            type_: str,
            detail: str,
            attestation: Attestation | None = None,
            emission: Emission = emission,
            dans_la_liste: bool = dans_la_liste,
        ) -> None:
            doutes.append(
                Doute(
                    type=type_,
                    emission_id=emission.id,
                    dans_la_liste=dans_la_liste,
                    source=attestation.source if attestation else "",
                    source_id=attestation.source_id if attestation else "",
                    detail=detail,
                )
            )

        # Rapprochement et date.
        autres = [e for e in emissions if e is not emission]
        for a in emission.attestations:
            if a.source in SOURCES_VERIFIEES:
                # rattachée par sa fiche, sans ambiguïté ; sinon par la date
                if not any(_meme_fiche(a, b) for b in emission.attestations):
                    ajouter("sans fiche radiofrance", f"aucune fiche {a.url}", a)
                continue
            rivales = [e.id for e in autres if _rapprochable(a, e.attestations)]
            if rivales:
                ajouter(
                    "rapprochement ambigu",
                    f"rapprochable aussi de {', '.join(rivales)}",
                    a,
                )
        dates = sorted(set(_dates_de_diffusion(emission.attestations)))
        if (dates[-1] - dates[0]).days > 1:
            ajouter(
                "désaccord de date",
                ", ".join(
                    f"{a.source}:{a.date.isoformat()}"
                    for a in emission.attestations
                    if a.nature_date == "première diffusion"
                ),
            )
        if emission.id != emission.date.isoformat():
            ajouter("collision", f"une autre émission le même jour : {emission.date}")

        # Une source vérifiée lève les doutes de thème et d'existence (ADR 0003).
        if _verifiee(emission):
            continue
        if (
            dans_la_liste
            and derniere_verifiee
            and LMELP_COMPLET_DEPUIS <= emission.date <= derniere_verifiee
        ):
            ajouter(
                "absente de lmelp",
                f"lmelp est complet depuis le {LMELP_COMPLET_DEPUIS:%d/%m/%Y}"
                " pour les émissions littéraires",
            )
        if not emission.themes:
            ajouter("thème inconnu", "aucune source ne donne de thème")
        divergence = _themes_divergents(emission.attestations)
        if divergence:
            ajouter("thèmes divergents", divergence)
        for a in emission.attestations:
            dates_des_fichiers = sorted(
                {
                    f.date
                    for e in a.enregistrements
                    if (f := lire_nom_fichier(e.url))
                    and abs((f.date - a.date).days) > ECART_REPUBLICATION_JOURS
                }
            )
            if dates_des_fichiers:
                ajouter(
                    "republication",
                    f"daté du {a.date}, enregistrement du "
                    + ", ".join(str(jour) for jour in dates_des_fichiers),
                    a,
                )
        fragilite = _fragilite(emission.attestations)
        if fragilite:
            ajouter("attestation fragile", fragilite)
    return doutes


def _verifiee(emission: Emission) -> bool:
    """L'émission est attestée par une source vérifiée."""
    return any(a.source in SOURCES_VERIFIEES for a in emission.attestations)


def _fragilite(groupe: list[Attestation]) -> str | None:
    """Pourquoi l'existence de l'émission est fragile, ou None.

    Ni un extrait ni un fichier conservé par la Wayback Machine ne décrit une
    émission diffusée en entier : une émission qu'eux seuls attestent peut être
    une republication ou un fragment publié à part.
    """
    if all(a.extrait for a in groupe):
        return "attestée seulement par des extraits"
    if all(a.source == "wayback_podcast" for a in groupe):
        return "attestée seulement par la Wayback Machine"
    if all(a.extrait or a.source == "wayback_podcast" for a in groupe):
        return "attestée seulement par des extraits et la Wayback Machine"
    return None


def _themes_divergents(groupe: list[Attestation]) -> str | None:
    """Le détail d'une divergence de thèmes entre attestations, ou None.

    Les attestations de l'émission entière divergent si elles ne donnent pas
    les mêmes thèmes ; un extrait diverge s'il porte un thème qu'aucune ne
    donne. Des extraits aux thèmes différents (un livre, un film) décrivent
    une émission mixte, sans divergence.
    """
    avec_theme = [a for a in groupe if a.themes]
    entieres = {a.themes for a in avec_theme if not a.extrait}
    themes_entiers = frozenset().union(*entieres)
    divergent = len(entieres) > 1 or any(
        a.extrait and entieres and not a.themes <= themes_entiers for a in avec_theme
    )
    if not divergent:
        return None
    return ", ".join(
        f"{a.source}:{'+'.join(sorted(a.themes))}" + (" (extrait)" if a.extrait else "")
        for a in avec_theme
    )


ECART_MAX_JOURS = 3
# Un enregistrement daté à plus de trois jours de son attestation signale une
# émission remise en ligne plus tard (republication), pas un simple décalage.
ECART_REPUBLICATION_JOURS = 3

# Sources dont chaque attestation a été vérifiée à la main (ADR 0003) : elles se
# rattachent à l'émission par leur fiche radiofrance.fr, et leur thème fait foi.
SOURCES_VERIFIEES = frozenset({"lmelp"})
# lmelp est complet depuis cette date : une émission de la liste qui n'y figure
# pas, jusqu'à sa dernière émission, est un doute.
LMELP_COMPLET_DEPUIS = date(2017, 1, 1)

# Pour chaque champ, les sources par ordre de priorité décroissante (issue #2).
PRIORITES: dict[str, tuple[str, ...]] = {
    "date": ("radiofrance", "ina", "anciennes_listes", "wayback_podcast"),
    "titre": ("radiofrance", "ina"),
    "description": ("radiofrance", "ina"),
    "chaine": ("ina", "radiofrance"),
    "heure": ("ina", "radiofrance"),
    "duree": ("ina", "radiofrance"),
    "animateur": ("radiofrance", "ina"),
}

# Mandats connus à l'année près (Wikipédia). Les années de transition (1970,
# 1989, 2023) sont absentes : l'animateur n'y est pas déduit.
MANDATS: tuple[tuple[int, int, str], ...] = (
    (1955, 1969, "Michel Polac, François-Régis Bastide"),
    (1971, 1981, "François-Régis Bastide"),
    (1982, 1988, "Pierre Bouteiller"),
    (1990, 2022, "Jérôme Garcin"),
    (2024, 9999, "Rebecca Manzoni"),
)


def animateur_du(jour: date) -> str | None:
    """L'animateur déduit de la date, ou None pour une année de transition."""
    for debut, fin, animateur in MANDATS:
        if debut <= jour.year <= fin:
            return animateur
    return None


# Champs qu'un extrait ne renseigne jamais : il ne couvre qu'un fragment.
_JAMAIS_D_UN_EXTRAIT = {"duree"}
# Une archive au moins aussi longue que 90 % de la diffusion (durée INA) est
# l'émission entière, pas un extrait.
_PART_MIN_ENTIERE = 0.9


def _valeur(champ: str, groupe: list[Attestation]) -> Any:
    """La valeur du champ dans la source la plus prioritaire qui le renseigne.

    Une attestation de l'émission entière passe avant un extrait.
    """
    ordre = PRIORITES[champ]
    candidats = [a for a in groupe if not (a.extrait and champ in _JAMAIS_D_UN_EXTRAIT)]
    if champ == "date" and any(a.nature_date == "première diffusion" for a in groupe):
        candidats = [a for a in candidats if a.nature_date == "première diffusion"]

    for a in sorted(candidats, key=lambda a: (a.extrait, _rang(a.source, ordre))):
        valeur = getattr(a, champ)
        if valeur:
            return valeur
    return None


def _rang(source: str, ordre: tuple[str, ...]) -> int:
    return ordre.index(source) if source in ordre else len(ordre)


def _dans_la_liste(emission: Emission) -> bool:
    """Thème incluant les livres, ou inconnu (ADR 0002)."""
    return not emission.themes or "livres" in emission.themes


def _cle_de_tri(emission: Emission) -> tuple[date, bool, list[str], str]:
    """Ordre déterministe, indépendant de l'ordre d'arrivée des attestations.

    À date égale, une émission de la liste passe avant une émission écartée :
    elle garde ainsi la date seule comme identifiant.
    """
    return (
        emission.date,
        not _dans_la_liste(emission),
        sorted(emission.themes),
        min(f"{a.source}:{a.source_id}" for a in emission.attestations),
    )


def _attribuer_identifiants(liste: list[Emission]) -> None:
    """La date de première diffusion, suffixée en cas de collision (ADR 0001)."""
    vus: dict[str, int] = {}
    for emission in liste:
        base = emission.date.isoformat()
        rang = vus.get(base, 0)
        vus[base] = rang + 1
        emission.id = base if rang == 0 else f"{base}-{chr(ord('a') + rang)}"


def _secondes(duree: str) -> int:
    """``HH:MM:SS`` en secondes."""
    h, m, s = (int(x) for x in duree.split(":"))
    return h * 3600 + m * 60 + s


def _archives_entieres(groupe: list[Attestation]) -> list[Attestation]:
    """Les extraits d'archive qui couvrent en fait toute la diffusion INA.

    Ils redeviennent des attestations de l'émission entière, et leurs
    enregistrements des intégraux : la règle de type par archive (ITEMA)
    étend ce changement aux fichiers des autres sources.
    """
    diffusion = max(
        (_secondes(a.duree) for a in groupe if a.source == "ina" and a.duree),
        default=None,
    )
    if diffusion is None:
        return groupe
    seuil = _PART_MIN_ENTIERE * diffusion
    entieres = {
        _itema(e.url)
        for a in groupe
        if a.extrait and a.duree and _secondes(a.duree) >= seuil
        for e in a.enregistrements
        if _archive(e.url)
    } - {None}
    if not entieres:
        return groupe

    def entiere(a: Attestation) -> Attestation:
        if not any(_itema(e.url) in entieres for e in a.enregistrements):
            return a
        return replace(
            a,
            extrait=False,
            enregistrements=tuple(
                Enregistrement(e.url, "intégral") if _itema(e.url) in entieres else e
                for e in a.enregistrements
            ),
        )

    return [entiere(a) for a in groupe]


def _fusionner(groupe: list[Attestation]) -> Emission:
    groupe = _archives_entieres(groupe)
    jour: date = _valeur("date", groupe)
    return Emission(
        id=jour.isoformat(),
        date=jour,
        themes=_themes(groupe),
        titre=_valeur("titre", groupe),
        description=_valeur("description", groupe),
        chaine=_valeur("chaine", groupe),
        heure=_valeur("heure", groupe),
        duree=_valeur("duree", groupe),
        animateur=_valeur("animateur", groupe) or animateur_du(jour),
        attestations=groupe,
        enregistrements=_enregistrements(groupe),
    )


def _archive(url: str) -> bool:
    """Un fichier d'une série d'archives : lettre ``E`` du code de publication."""
    return re.search(r"\d{4}F4007E\d+", url) is not None


def _itema(url: str) -> str | None:
    """L'identifiant d'archive Radio France d'un fichier audio, s'il y figure."""
    m = re.search(r"ITEMA_\d+", url)
    return m.group(0) if m else None


def _enregistrements(groupe: list[Attestation]) -> list[Enregistrement]:
    """Les enregistrements de toutes les sources, typés par archive (ITEMA).

    Une source qui sait qu'une archive est un extrait (radiofrance.fr connaît
    la durée) l'emporte sur une autre qui ne voit que le nom du fichier.
    """
    tous = [e for a in groupe for e in a.enregistrements]
    extraits = {_itema(e.url) for e in tous if e.type == "extrait"} - {None}
    return list(
        dict.fromkeys(
            Enregistrement(e.url, "extrait") if _itema(e.url) in extraits else e
            for e in tous
        )
    )


def _themes(groupe: list[Attestation]) -> frozenset[str]:
    """Les thèmes de toutes les attestations, extraits compris.

    Ceux d'une source vérifiée font foi, sans cumul avec les autres.
    """
    verifiees = [a for a in groupe if a.source in SOURCES_VERIFIEES]
    return frozenset().union(*(a.themes for a in verifiees or groupe))


def _rapprocher(a: Attestation, groupes: list[list[Attestation]]) -> None:
    """Ajoute l'attestation au groupe le plus proche, ou en crée un."""
    candidats = [g for g in groupes if _rapprochable(a, g)]
    if candidats:
        min(candidats, key=lambda g: _ecart(a, g)).append(a)
    else:
        groupes.append([a])


def _meme_fiche(verifiee: Attestation, b: Attestation) -> bool:
    """``b`` est la fiche radiofrance.fr de l'attestation vérifiée (même URL)."""
    return b.source not in SOURCES_VERIFIEES and b.url == verifiee.url


def _dates_de_diffusion(groupe: list[Attestation]) -> list[date]:
    """Les dates de première diffusion du groupe, à défaut ses autres dates."""
    diffusion = [a.date for a in groupe if a.nature_date == "première diffusion"]
    return diffusion or [a.date for a in groupe]


def _ecart(a: Attestation, groupe: list[Attestation]) -> int:
    return min(abs((a.date - jour).days) for jour in _dates_de_diffusion(groupe))


def _rapprochable(a: Attestation, groupe: list[Attestation]) -> bool:
    """Même date, ou écart d'au plus 3 jours avec des thèmes compatibles."""
    if _ecart(a, groupe) > ECART_MAX_JOURS:
        return False
    themes = _themes(groupe)
    return not a.themes or not themes or bool(a.themes & themes)
