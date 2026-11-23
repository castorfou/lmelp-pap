"""Commande ``lmelp-pap``."""

import argparse
import logging
import os
import sys
import webbrowser
from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path

from lmelp_pap import logs
from lmelp_pap.arbitrages import ArbitragesMongo, lire_arbitrages
from lmelp_pap.arbitrer import AUDIOS, AUDIOS_LMELP, creer_serveur
from lmelp_pap.collecte import SOURCES, collecter, lire_cache
from lmelp_pap.ecriture import ecrire_liste
from lmelp_pap.liste import construire_liste
from lmelp_pap.maturite import Depot, depot_depuis_env
from lmelp_pap.page import construire_page
from lmelp_pap.publication import Configuration, Publication


log = logging.getLogger(__name__)


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
    audios = _chemin("PAP_AUDIOS", str(AUDIOS))
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
    sous_arbitrages = commandes.add_parser(
        "arbitrages",
        help="importe arbitrages.csv dans Mongo (pap_arbitrages), ou l'en exporte",
    )
    sous_arbitrages.add_argument(
        "sens",
        choices=["importer", "exporter"],
        help="importer : ajoute les arbitrages absents du fichier ; exporter : "
        "réécrit le fichier avec ceux de Mongo",
    )
    sous_arbitrages.add_argument(
        "--fichier",
        type=Path,
        default=arbitrages or Path(donnees or "data/processed") / "arbitrages.csv",
        help="fichier des arbitrages (par défaut : arbitrages.csv des données)",
    )
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
        help=f"dossier des enregistrements rapatriés (par défaut {AUDIOS})",
    )
    arbitrer.add_argument(
        "--audios-lmelp",
        type=Path,
        default=_chemin("PAP_AUDIOS_LMELP", str(AUDIOS_LMELP)),
        help="dossier audio du back-office lmelp, où vont les enregistrements "
        f"mis à disposition (par défaut {AUDIOS_LMELP})",
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
    """Point d'entrée de ``lmelp-pap`` : commandes ``emissions``, ``page``, ``arbitrages`` et
    ``arbitrer``. Rend le code de sortie."""
    args = _parser().parse_args(argv)
    logs.configurer()

    if args.commande == "arbitrer":
        return _arbitrer(args)

    if args.commande == "arbitrages":
        return _echanger_arbitrages(args)

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


def _etat_mongo(depot: Depot | None) -> str:
    """L'état de la base de la maturité : absente, connectée, ou injoignable
    (un ``ping`` au démarrage)."""
    if depot is None:
        return "absent (MONGO_URI non défini)"
    base = depot.base.name
    try:
        depot.base.client.admin.command("ping")
    except Exception as erreur:  # noqa: BLE001 — l'appli démarre sans base
        return f"injoignable (base {base}) : {erreur}"
    return f"connecté (base {base})"


def _echanger_arbitrages(args: argparse.Namespace) -> int:
    """Importe le fichier des arbitrages dans ``pap_arbitrages``, ou l'en
    exporte ; chacun laisse sa ligne de log."""
    depot = depot_depuis_env()
    if depot is None:
        log.error(f"arbitrages : MONGO_URI absent, rien à {args.sens}")
        return 1
    arbitrages = ArbitragesMongo(depot.base)
    if args.sens == "importer":
        arbitrages.importer(args.fichier)
    else:
        arbitrages.exporter(args.fichier)
    return 0


def _publication(args: argparse.Namespace) -> Publication | None:
    """La publication sur GitHub, si ``PAP_DEPOT_GIT`` donne son clone ;
    aucun fichier publié ne porte le chemin des audios ni du cache."""
    configuration = Configuration.depuis_env()
    if configuration is None:
        return None
    prives = [args.audios, args.audios_lmelp, args.cache]
    return Publication(configuration, prives=[p.resolve() for p in prives])


def _etat_publication(publication: Publication | None) -> str:
    """La publication pour le log du démarrage, sans le jeton."""
    if publication is None:
        return "désactivée (PAP_DEPOT_GIT non défini)"
    c = publication.configuration
    jeton = "GH_TOKEN présent" if c.jeton else "GH_TOKEN absent"
    ntfy = os.environ.get("NTFY_TOPIC")
    return (
        f"vers {c.distant} ({c.branche}), clone {c.clone}, {jeton}, "
        f"ntfy {ntfy or 'non configuré (NTFY_TOPIC absent)'}"
    )


def _arbitrer(args: argparse.Namespace) -> int:
    """Sert l'appli (la page en mode arbitrage) jusqu'à l'arrêt du processus."""
    log.info("lecture du cache et construction de la liste…")
    # La maturité des enregistrements vit dans Mongo (MONGO_URI) ; sans
    # base, l'appli sert la liste sans elle.
    depot = depot_depuis_env()
    publication = _publication(args)
    serveur = creer_serveur(
        args.cache,
        args.sortie,
        port=args.port,
        hote=args.hote,
        arbitrages=args.arbitrages,
        depot=depot,
        audios=args.audios,
        audios_lmelp=args.audios_lmelp,
        # Vérification des URL d'intégral : au démarrage sur une base vide,
        # puis à chaque échéance, et pour les URL nouvelles.
        planification=True,
        intervalle=timedelta(days=args.verification_jours),
        publication=publication,
    )
    port = serveur.server_address[1]
    atelier = serveur.atelier  # type: ignore[attr-defined]
    log.info(f"lmelp-pap {version('lmelp-pap')} : écoute sur {args.hote}:{port}")
    # ni l'un ni l'autre ne lit la base : l'appli démarre même sans elle
    log.info(f"Mongo : {_etat_mongo(depot)}")
    log.info(f"liste : {atelier.nombre_emissions()} émissions")
    log.info(f"arbitrages : {atelier.origine_arbitrages()}")
    try:
        if raison := atelier.arbitrages_a_importer():
            log.warning(f"arbitrages : {raison}")
    except Exception as erreur:  # noqa: BLE001 — Mongo injoignable : démarrer quand même
        log.warning(f"arbitrages : {type(erreur).__name__} en comptant pap_arbitrages")
    log.info(
        f"dossiers : cache {args.cache}, données {args.sortie}, "
        f"arbitrages {atelier.fichier}, audios {args.audios}, "
        f"audios lmelp {args.audios_lmelp}"
    )
    log.info(f"publication : {_etat_publication(publication)}")
    if publique := os.environ.get("PAP_URL_PUBLIQUE"):
        log.info(f"page publique : {publique}")
    if not args.sans_navigateur:
        # VS Code redirige le port vers la machine hôte et y ouvre l'adresse.
        url = f"http://localhost:{port}/"
        log.info(f"ouverture de {url} dans le navigateur (Ctrl+C pour arrêter)")
        webbrowser.open(url)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
        log.info("arrêt du serveur")
    return 0


if __name__ == "__main__":
    sys.exit(main())
