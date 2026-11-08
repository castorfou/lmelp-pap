"""Construction de la liste des émissions à partir des attestations des sources.

Vocabulaire : voir CONTEXT.md. Décisions : docs/adr/0001 et 0002.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


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
    enregistrements: tuple[Enregistrement, ...] = ()


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
class Signalement:
    """Un cas à vérifier à la main dans le rapport de rapprochement."""

    type: str
    emission_id: str
    source: str
    source_id: str
    detail: str


@dataclass
class Rapport:
    """Le rapport de rapprochement : cas ambigus et désaccords entre sources."""

    signalements: list[Signalement] = field(default_factory=list)


def construire_liste(
    attestations: list[Attestation],
) -> tuple[list[Emission], Rapport]:
    """Rapproche les attestations et construit la liste des émissions."""
    groupes: list[list[Attestation]] = []
    for a in sorted(attestations, key=lambda a: a.date):
        candidats = [g for g in groupes if _rapprochable(a, g)]
        if candidats:
            min(candidats, key=lambda g: _ecart(a, g)).append(a)
        else:
            groupes.append([a])

    emissions = sorted((_fusionner(g) for g in groupes), key=_cle_de_tri)
    _attribuer_identifiants(emissions)
    liste = [e for e in emissions if _dans_la_liste(e)]
    return liste, _rapport(emissions)


def _rapport(liste: list[Emission]) -> Rapport:
    rapport = Rapport()
    for emission in liste:
        autres = [e for e in liste if e is not emission]
        for a in emission.attestations:
            rivales = [e.id for e in autres if _rapprochable(a, e.attestations)]
            if rivales:
                rapport.signalements.append(
                    Signalement(
                        type="ambigu",
                        emission_id=emission.id,
                        source=a.source,
                        source_id=a.source_id,
                        detail=f"rapprochable aussi de {', '.join(rivales)}",
                    )
                )
        dates = sorted({a.date for a in emission.attestations})
        if (dates[-1] - dates[0]).days > 1:
            rapport.signalements.append(
                Signalement(
                    type="désaccord de date",
                    emission_id=emission.id,
                    source="",
                    source_id="",
                    detail=", ".join(
                        f"{a.source}:{a.date.isoformat()}"
                        for a in emission.attestations
                    ),
                )
            )
    return rapport


ECART_MAX_JOURS = 3

# Pour chaque champ, les sources par ordre de priorité décroissante (issue #2).
PRIORITES: dict[str, tuple[str, ...]] = {
    "date": ("radiofrance", "ina", "anciennes_listes", "wayback_podcast"),
    "themes": ("radiofrance", "anciennes_listes", "ina"),
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


def _valeur(champ: str, groupe: list[Attestation]) -> Any:
    """La valeur du champ dans la source la plus prioritaire qui le renseigne."""
    ordre = PRIORITES[champ]
    for a in sorted(groupe, key=lambda a: _rang(a.source, ordre)):
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


def _fusionner(groupe: list[Attestation]) -> Emission:
    jour: date = _valeur("date", groupe)
    return Emission(
        id=jour.isoformat(),
        date=jour,
        themes=_valeur("themes", groupe) or frozenset(),
        titre=_valeur("titre", groupe),
        description=_valeur("description", groupe),
        chaine=_valeur("chaine", groupe),
        heure=_valeur("heure", groupe),
        duree=_valeur("duree", groupe),
        animateur=_valeur("animateur", groupe) or animateur_du(jour),
        attestations=groupe,
        enregistrements=list(
            dict.fromkeys(e for a in groupe for e in a.enregistrements)
        ),
    )


def _themes(groupe: list[Attestation]) -> frozenset[str]:
    return frozenset().union(*(a.themes for a in groupe))


def _ecart(a: Attestation, groupe: list[Attestation]) -> int:
    return min(abs((a.date - b.date).days) for b in groupe)


def _rapprochable(a: Attestation, groupe: list[Attestation]) -> bool:
    """Même date, ou écart d'au plus 3 jours avec des thèmes compatibles."""
    if _ecart(a, groupe) > ECART_MAX_JOURS:
        return False
    themes = _themes(groupe)
    return not a.themes or not themes or bool(a.themes & themes)
