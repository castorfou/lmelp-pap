"""Commande ``lmelp-pap``."""

import argparse
import os
import sys
import webbrowser
from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from lmelp_pap.arbitrages import lire_arbitrages
from lmelp_pap.arbitrer import creer_serveur
from lmelp_pap.collecte import SOURCES, collecter, lire_cache
from lmelp_pap.ecriture import ecrire_liste
from lmelp_pap.liste import construire_liste
from lmelp_pap.maturite import depot_depuis_env
from lmelp_pap.page import construire_page


def _chemin(variable: str, defaut: str | None) -> Path | None:
    """Le chemin donné par une variable d'environnement, sinon le défaut."""
    valeur = os.environ.get(variable) or defaut
    return Path(valeur) if valeur else None


def _parser() -> argparse.ArgumentParser:
    """Le parseur des commandes. Les variables ``PAP_*`` (image Docker) fixent
    les défauts des options ; une option explicite l'emporte."""
    cache = _chemin("PAP_CACHE", "data/raw/cache")
    donnees = _chemin("PAP_DONNEES", "data/processed")
    arbitrages = _chemin("PAP_ARBITRAGES", None)
    audios = _chemin("PAP_AUDIOS", "data/raw/audios")
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
    emissions.add_argument("--cache", type=Path, default=cache)
    emissions.add_argument("--sortie", type=Path, default=donnees)
    emissions.add_argument(
        "--arbitrages",
        type=Path,
        default=arbitrages,
        help="fichier des arbitrages (par défaut : arbitrages.csv dans --sortie)",
    )
    page = commandes.add_parser(
        "page", help="génère la page HTML de la liste des émissions"
    )
    page.add_argument("--donnees", type=Path, default=donnees)
    page.add_argument("--sortie", type=Path, default=Path("docs/emissions/index.html"))
    arbitrer = commandes.add_parser(
        "arbitrer",
        help="ouvre la liste en mode arbitrage dans un serveur local",
    )
    arbitrer.add_argument("--cache", type=Path, default=cache)
    arbitrer.add_argument("--sortie", type=Path, default=donnees)
    arbitrer.add_argument(
        "--arbitrages",
        type=Path,
        default=arbitrages,
        help="fichier des arbitrages (par défaut : arbitrages.csv dans --sortie)",
    )
    arbitrer.add_argument(
        "--audios",
        type=Path,
        default=audios,
        help="dossier des enregistrements rapatriés (par défaut data/raw/audios)",
    )
    arbitrer.add_argument(
        "--audios-lmelp",
        type=Path,
        default=_chemin("PAP_AUDIOS_LMELP", "data/raw/audios-lmelp"),
        help="dossier audio du back-office lmelp, où vont les enregistrements "
        "mis à disposition (par défaut data/raw/audios-lmelp)",
    )
    arbitrer.add_argument(
        "--verification-jours",
        type=float,
        default=float(os.environ.get("PAP_VERIFICATION_JOURS") or 7),
        help="jours entre deux vérifications complètes des URL (par défaut 7)",
    )
    arbitrer.add_argument(
        "--port", type=int, default=int(os.environ.get("PAP_PORT") or 8765)
    )
    arbitrer.add_argument(
        "--hote",
        default=os.environ.get("PAP_HOTE") or "127.0.0.1",
        help="adresse d'écoute (0.0.0.0 dans un conteneur)",
    )
    arbitrer.add_argument(
        "--sans-navigateur",
        action="store_true",
        help="n'ouvre pas la page dans le navigateur",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée de ``lmelp-pap`` : commandes ``emissions``, ``page`` et
    ``arbitrer``. Rend le code de sortie."""
    args = _parser().parse_args(argv)

    if args.commande == "arbitrer":
        return _arbitrer(args)

    if args.commande == "page":
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(construire_page(args.donnees), encoding="utf-8")
        print(f"Page de la liste des émissions → {args.sortie}", file=sys.stderr)
        return 0

    for source in args.source or sorted(SOURCES):
        print(f"Collecte : {source}", file=sys.stderr)
        collecter(source, args.cache, refresh=args.refresh)

    attestations = lire_cache(args.cache)
    arbitrages = lire_arbitrages(args.arbitrages or args.sortie / "arbitrages.csv")
    liste, doutes = construire_liste(attestations, arbitrages)
    ecrire_liste(liste, doutes, args.sortie)

    par_source = Counter(a.source for a in attestations)
    print(
        f"{len(liste)} émissions, {len(attestations)} attestations "
        f"({', '.join(f'{s} {n}' for s, n in sorted(par_source.items()))}), "
        f"{len(arbitrages)} arbitrages → {args.sortie}",
        file=sys.stderr,
    )
    par_type = Counter(d.type for d in doutes)
    print(
        "Doutes : "
        + (", ".join(f"{t} {n}" for t, n in sorted(par_type.items())) or "aucun"),
        file=sys.stderr,
    )
    return 0


def _arbitrer(args: argparse.Namespace) -> int:
    """Sert la page en mode arbitrage jusqu'à Ctrl+C."""
    print("Lecture du cache et construction de la liste…", file=sys.stderr)
    serveur = creer_serveur(
        args.cache,
        args.sortie,
        port=args.port,
        hote=args.hote,
        arbitrages=args.arbitrages,
        # La maturité des enregistrements vit dans Mongo (MONGO_URI) ; sans
        # base, l'appli sert la liste sans elle.
        depot=depot_depuis_env(),
        audios=args.audios,
        audios_lmelp=args.audios_lmelp,
        # Vérification des URL d'intégral : au démarrage sur une base vide,
        # puis à chaque échéance, et pour les URL nouvelles.
        planification=True,
        intervalle=timedelta(days=args.verification_jours),
    )
    # VS Code redirige le port vers la machine hôte et y ouvre l'adresse.
    url = f"http://localhost:{serveur.server_address[1]}/"
    print(f"Arbitrage de la liste : {url} (Ctrl+C pour arrêter)", file=sys.stderr)
    if not args.sans_navigateur:
        webbrowser.open(url)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
