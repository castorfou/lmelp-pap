"""Commande ``lmelp-pap``."""

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from lmelp_pap.collecte import SOURCES, collecter, lire_cache
from lmelp_pap.ecriture import ecrire_liste
from lmelp_pap.liste import construire_liste


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lmelp-pap")
    commandes = parser.add_subparsers(dest="commande", required=True)
    emissions = commandes.add_parser(
        "emissions", help="construit la liste des émissions depuis les sources"
    )
    emissions.add_argument(
        "--source",
        action="append",
        choices=sorted(SOURCES),
        help="source à collecter (répétable ; toutes par défaut)",
    )
    emissions.add_argument(
        "--refresh",
        action="store_true",
        help="re-collecte les sources choisies même si leur cache est complet",
    )
    emissions.add_argument("--cache", type=Path, default=Path("data/raw/cache"))
    emissions.add_argument("--sortie", type=Path, default=Path("data/processed"))
    args = parser.parse_args(argv)

    for source in args.source or sorted(SOURCES):
        print(f"Collecte : {source}", file=sys.stderr)
        collecter(source, args.cache, refresh=args.refresh)

    attestations = lire_cache(args.cache)
    liste, rapport = construire_liste(attestations)
    ecrire_liste(liste, rapport, args.sortie)

    par_source = Counter(a.source for a in attestations)
    print(
        f"{len(liste)} émissions, {len(attestations)} attestations "
        f"({', '.join(f'{s} {n}' for s, n in sorted(par_source.items()))}), "
        f"{len(rapport.signalements)} signalements → {args.sortie}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
