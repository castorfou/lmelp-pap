"""Construction de la liste des émissions à partir des attestations des sources.

Vocabulaire : voir CONTEXT.md. Décisions : docs/adr/0001 et 0002.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Attestation:
    """Ce qu'une source dit d'une émission, à une date donnée."""

    source: str
    source_id: str
    date: date
    themes: frozenset[str] = frozenset()
    titre: str | None = None


@dataclass
class Emission:
    """Une émission de la liste, construite à partir de ses attestations."""

    id: str
    date: date
    themes: frozenset[str]
    titre: str | None
    attestations: list[Attestation] = field(default_factory=list)


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

    liste = [
        Emission(
            id=groupe[0].date.isoformat(),
            date=groupe[0].date,
            themes=groupe[0].themes,
            titre=groupe[0].titre,
            attestations=groupe,
        )
        for groupe in groupes
    ]
    return liste, _rapport(liste)


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
