"""Écriture de la liste des émissions en CSV liés par l'identifiant (ADR 0001)."""

import csv
from collections.abc import Iterable
from pathlib import Path

from lmelp_pap.liste import Doute, Emission


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
    "arbitrage",
    "justification_arbitrage",
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
COLONNES_ENREGISTREMENTS = ["emission_id", "url", "type", "sources", "duree"]
COLONNES_DOUTES = [
    "type",
    "emission_id",
    "dans_la_liste",
    "source",
    "source_id",
    "detail",
    "a_ecouter",
]


def ecrire_liste(liste: list[Emission], doutes: list[Doute], dossier: Path) -> None:
    """Écrit emissions.csv, attestations.csv, enregistrements.csv et doutes.csv."""
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
                "arbitrage": e.arbitrage.sorte if e.arbitrage else None,
                "justification_arbitrage": (
                    e.arbitrage.justification if e.arbitrage else None
                ),
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
                # par l'URL : la fusion peut avoir retypé le fichier (ITEMA)
                "sources": ";".join(
                    sorted(
                        {
                            a.source
                            for a in e.attestations
                            if any(x.url == r.url for x in a.enregistrements)
                        }
                    )
                ),
                "duree": r.duree,
            }
            for e in emissions
            for r in e.enregistrements
        ),
    )
    _ecrire(
        dossier / "doutes.csv",
        COLONNES_DOUTES,
        (
            {
                "type": d.type,
                "emission_id": d.emission_id,
                "dans_la_liste": "oui" if d.dans_la_liste else "non",
                "source": d.source,
                "source_id": d.source_id,
                "detail": d.detail,
                "a_ecouter": "oui" if d.a_ecouter else "non",
            }
            for d in sorted(doutes, key=lambda d: (d.emission_id, d.type))
        ),
    )


def _themes(themes: frozenset[str]) -> str:
    """Les thèmes triés, séparés par ``;``."""
    return ";".join(sorted(themes))


def _ecrire(
    chemin: Path, colonnes: list[str], lignes: Iterable[dict[str, object]]
) -> None:
    """Écrit un CSV ; une valeur ``None`` donne une cellule vide."""
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, lineterminator="\n")
        ecrivain.writeheader()
        ecrivain.writerows(
            {k: "" if v is None else v for k, v in ligne.items()} for ligne in lignes
        )
