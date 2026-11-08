"""Écriture de la liste des émissions en CSV liés par l'identifiant (ADR 0001)."""

import csv
from collections.abc import Iterable
from pathlib import Path

from lmelp_pap.liste import Emission, Rapport


COLONNES_EMISSIONS = [
    "id",
    "date",
    "themes",
    "titre",
    "description",
    "animateur",
    "chaine",
    "heure",
    "duree",
]
COLONNES_ATTESTATIONS = [
    "emission_id",
    "source",
    "source_id",
    "date",
    "themes",
    "titre",
    "url",
]
COLONNES_ENREGISTREMENTS = ["emission_id", "url", "type", "sources"]
COLONNES_RAPPORT = ["type", "emission_id", "source", "source_id", "detail"]


def ecrire_liste(liste: list[Emission], rapport: Rapport, dossier: Path) -> None:
    """Écrit emissions.csv, attestations.csv, enregistrements.csv et le rapport."""
    dossier.mkdir(parents=True, exist_ok=True)
    emissions = sorted(liste, key=lambda e: e.id)

    _ecrire(
        dossier / "emissions.csv",
        COLONNES_EMISSIONS,
        (
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "themes": _themes(e.themes),
                "titre": e.titre,
                "description": e.description,
                "animateur": e.animateur,
                "chaine": e.chaine,
                "heure": e.heure,
                "duree": e.duree,
            }
            for e in emissions
        ),
    )
    _ecrire(
        dossier / "attestations.csv",
        COLONNES_ATTESTATIONS,
        (
            {
                "emission_id": e.id,
                "source": a.source,
                "source_id": a.source_id,
                "date": a.date.isoformat(),
                "themes": _themes(a.themes),
                "titre": a.titre,
                "url": a.url,
            }
            for e in emissions
            for a in sorted(e.attestations, key=lambda a: (a.source, a.source_id))
        ),
    )
    _ecrire(
        dossier / "enregistrements.csv",
        COLONNES_ENREGISTREMENTS,
        (
            {
                "emission_id": e.id,
                "url": r.url,
                "type": r.type,
                "sources": ";".join(
                    sorted({a.source for a in e.attestations if r in a.enregistrements})
                ),
            }
            for e in emissions
            for r in e.enregistrements
        ),
    )
    _ecrire(
        dossier / "rapport_rapprochement.csv",
        COLONNES_RAPPORT,
        (
            {
                "type": s.type,
                "emission_id": s.emission_id,
                "source": s.source,
                "source_id": s.source_id,
                "detail": s.detail,
            }
            for s in sorted(rapport.signalements, key=lambda s: (s.emission_id, s.type))
        ),
    )


def _themes(themes: frozenset[str]) -> str:
    return ";".join(sorted(themes))


def _ecrire(
    chemin: Path, colonnes: list[str], lignes: Iterable[dict[str, object]]
) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, lineterminator="\n")
        ecrivain.writeheader()
        ecrivain.writerows(
            {k: "" if v is None else v for k, v in ligne.items()} for ligne in lignes
        )
