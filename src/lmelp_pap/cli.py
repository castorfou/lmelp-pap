"""Commande ``lmelp-pap``."""

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from lmelp_pap.collecte import SOURCES, collecter, lire_cache
from lmelp_pap.ecriture import ecrire_liste
from lmelp_pap.liste import construire_liste
from lmelp_pap.page import construire_page


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
    page = commandes.add_parser(
        "page", help="génère la page HTML de la liste des émissions"
    )
    page.add_argument("--donnees", type=Path, default=Path("data/processed"))
    page.add_argument("--sortie", type=Path, default=Path("docs/emissions/index.html"))
    args = parser.parse_args(argv)

    if args.commande == "page":
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(construire_page(args.donnees), encoding="utf-8")
        print(f"Page de la liste des émissions → {args.sortie}", file=sys.stderr)
        return 0

    for source in args.source or sorted(SOURCES):
        print(f"Collecte : {source}", file=sys.stderr)
        collecter(source, args.cache, refresh=args.refresh)

    attestations = lire_cache(args.cache)
    liste, doutes = construire_liste(attestations)
    ecrire_liste(liste, doutes, args.sortie)

    par_source = Counter(a.source for a in attestations)
    print(
        f"{len(liste)} émissions, {len(attestations)} attestations "
        f"({', '.join(f'{s} {n}' for s, n in sorted(par_source.items()))}) "
        f"→ {args.sortie}",
        file=sys.stderr,
    )
    par_type = Counter(d.type for d in doutes)
    print(
        "Doutes : "
        + (", ".join(f"{t} {n}" for t, n in sorted(par_type.items())) or "aucun"),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
