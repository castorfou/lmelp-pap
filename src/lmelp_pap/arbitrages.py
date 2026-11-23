"""Les arbitrages : le fichier ``arbitrages.csv``, versionné à côté de la
liste, et la collection Mongo ``pap_arbitrages`` (``ArbitragesMongo``), qui
fait foi pour l'appli ; le fichier en est la publication (ADR 0004).

Colonnes : ``source``, ``source_id`` (l'attestation arbitrée), ``sorte``
(``thème``, ``existence``, ``date``, ``rapprochement``, ou ``écoute`` pour un
renvoi à l'écoute), ``valeur`` (les thèmes séparés par ``;``, ``existe`` ou
``n'existe pas``, la date retenue au format ISO, ``à écouter``, ou pour un
rapprochement ``garder ici`` ou l'attestation cible ``source:source_id``),
``justification`` (facultative) et ``date`` de la décision (ISO 8601, jour ou
jour et heure).
"""

import csv
import logging
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from lmelp_pap.liste import HOMMAGE, Arbitrage, CleAttestation, Sorte


log = logging.getLogger(__name__)

COLLECTION = "pap_arbitrages"
EXISTANTE = "existe"
INEXISTANTE = "n'existe pas"
A_ECOUTER = "à écouter"
GARDER_ICI = "garder ici"
THEMES = (
    "livres",
    "cinéma",
    "théâtre",
    "opéra",
    "télévision",
    "musique",
    "variétés",
    HOMMAGE,
)
COLONNES = ["source", "source_id", "sorte", "valeur", "justification", "date"]


def erreur_de_themes(themes: frozenset[str]) -> str | None:
    """Pourquoi ces thèmes ne font pas un arbitrage de thème, ou None.

    Il en faut au moins un, parmi ``THEMES`` ; ``hommage`` est seul.
    """
    if not themes or not themes <= set(THEMES):
        return f"thèmes invalides : {sorted(themes)} (attendu : {THEMES})"
    if HOMMAGE in themes and len(themes) > 1:
        return f"le thème {HOMMAGE} ne se cumule avec aucun autre : {sorted(themes)}"
    return None


def lire_arbitrages(chemin: Path) -> list[Arbitrage]:
    """Les arbitrages du fichier, dans son ordre ; aucun s'il n'existe pas."""
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        return [
            _arbitrage(ligne, f"arbitrages.csv, ligne {n}")
            for n, ligne in enumerate(csv.DictReader(f), 2)
        ]


def _arbitrage(ligne: dict[str, str], ou: str) -> Arbitrage:
    """L'arbitrage d'une ligne du fichier (ou d'un document de
    ``pap_arbitrages``, situé par ``ou``) ; ``ValueError`` s'il est invalide."""
    sorte, valeur = ligne["sorte"].strip(), ligne["valeur"].strip()
    themes = frozenset(t.strip() for t in valeur.split(";") if t.strip())
    retenue, cible, existe = None, None, False
    if sorte == "thème" and themes:
        if erreur := erreur_de_themes(themes):
            raise ValueError(f"{ou} : {erreur}")
        sorte_lue: Sorte = "thème"
    elif sorte == "existence" and valeur in (EXISTANTE, INEXISTANTE):
        sorte_lue, themes, existe = "existence", frozenset(), valeur == EXISTANTE
    elif sorte == "écoute" and valeur == A_ECOUTER:
        sorte_lue, themes = "écoute", frozenset()
    elif sorte == "date" and (retenue := lire_date(valeur)):
        sorte_lue, themes = "date", frozenset()
    elif sorte == "rapprochement" and (
        valeur == GARDER_ICI or (cible := _attestation(valeur))
    ):
        sorte_lue, themes = "rapprochement", frozenset()
    else:
        raise ValueError(
            f"{ou} : sorte « {sorte} » et valeur "
            f"« {valeur} » invalides (attendu : thème et des thèmes séparés par "
            f"« ; », existence et « {EXISTANTE} » ou « {INEXISTANTE} », date "
            f"et une date AAAA-MM-JJ, écoute et « {A_ECOUTER} », ou "
            f"rapprochement et « {GARDER_ICI} » ou une attestation "
            f"source:source_id)"
        )
    return Arbitrage(
        source=ligne["source"].strip(),
        source_id=ligne["source_id"].strip(),
        sorte=sorte_lue,
        themes=themes,
        date_retenue=retenue,
        cible=cible,
        existe=existe,
        justification=(ligne.get("justification") or "").strip(),
        date=datetime.fromisoformat(ligne["date"].strip()),
    )


def _attestation(texte: str) -> CleAttestation | None:
    """Une attestation ``source:source_id``, ou None."""
    source, _, source_id = texte.partition(":")
    return (source, source_id) if source and source_id else None


def lire_date(texte: str) -> date | None:
    """Une date ``AAAA-MM-JJ``, ou None si le texte n'en est pas une."""
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return None


def ajouter_arbitrage(chemin: Path, arbitrage: Arbitrage) -> None:
    """Ajoute l'arbitrage en fin de fichier, sans toucher aux lignes existantes."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not chemin.exists() or not chemin.read_text(encoding="utf-8").strip()
    if not nouveau and not chemin.read_bytes().endswith(b"\n"):
        with chemin.open("a", encoding="utf-8") as f:
            f.write("\n")
    with chemin.open("w" if nouveau else "a", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, lineterminator="\n")
        if nouveau:
            ecrivain.writeheader()
        ecrivain.writerow(_ligne(arbitrage))


def _ligne(arbitrage: Arbitrage) -> dict[str, str]:
    """La ligne du fichier d'un arbitrage, colonne par colonne."""
    return {
        "source": arbitrage.source,
        "source_id": arbitrage.source_id,
        "sorte": arbitrage.sorte,
        "valeur": valeur(arbitrage),
        "justification": arbitrage.justification,
        "date": _date(arbitrage.date),
    }


def retirer_arbitrages(chemin: Path, cles: set[CleAttestation]) -> int:
    """Retire les lignes des attestations ``cles``, sans réécrire les autres.

    Rend le nombre de lignes retirées.
    """
    if not chemin.exists():
        return 0
    entete, *lignes = chemin.read_text(encoding="utf-8").splitlines(keepends=True)
    gardees = [
        ligne
        for ligne in lignes
        if not (
            (champs := next(csv.DictReader([entete, ligne]), None))
            and (champs["source"].strip(), champs["source_id"].strip()) in cles
        )
    ]
    if len(gardees) < len(lignes):
        chemin.write_text(entete + "".join(gardees), encoding="utf-8")
    return len(lignes) - len(gardees)


def valeur(arbitrage: Arbitrage) -> str:
    """La colonne ``valeur`` : les thèmes séparés par ``;``, ``existe`` ou
    ``n'existe pas``, la date retenue, ``à écouter``, ``garder ici`` ou
    l'attestation cible."""
    if arbitrage.sorte == "existence":
        return EXISTANTE if arbitrage.existe else INEXISTANTE
    if arbitrage.sorte == "écoute":
        return A_ECOUTER
    if arbitrage.sorte == "date":
        return arbitrage.date_retenue.isoformat() if arbitrage.date_retenue else ""
    if arbitrage.sorte == "rapprochement":
        return ":".join(arbitrage.cible) if arbitrage.cible else GARDER_ICI
    return ";".join(sorted(arbitrage.themes))


def decision(arbitrage: Arbitrage) -> str:
    """La décision d'un arbitrage en clair, pour les logs, avec sa
    justification : la colonne ``valeur`` (``existe``, ``n'existe pas``, la
    date retenue, ou « sans date »), sauf pour les thèmes (séparés par des
    virgules), un rapprochement (l'attestation et où elle va) et un renvoi à
    l'écoute."""
    if arbitrage.sorte == "thème":
        texte = ", ".join(sorted(arbitrage.themes))
    elif arbitrage.sorte == "rapprochement":
        vers = ":".join(arbitrage.cible) if arbitrage.cible else "gardée ici"
        texte = f"{arbitrage.source}:{arbitrage.source_id} → {vers}"
    elif arbitrage.sorte == "écoute":
        texte = "renvoi à l'écoute"
    else:
        texte = valeur(arbitrage) or "sans date"
    pourquoi = arbitrage.justification
    return f"{texte} (« {pourquoi} »)" if pourquoi else texte


def _date(moment: datetime) -> str:
    """Le jour seul à minuit (saisie à la main), sinon le jour et l'heure."""
    if moment.time() == datetime.min.time():
        return moment.date().isoformat()
    return moment.isoformat(timespec="seconds")


class ArbitragesMongo:
    """La collection ``pap_arbitrages`` d'une base Mongo : un document par
    arbitrage, les colonnes de ``arbitrages.csv`` telles qu'écrites dans le
    fichier, plus ``rang`` (l'ordre d'entrée, celui du fichier exporté).

    L'identifiant d'un document (``_id``) est fait de l'attestation, de la
    sorte, de la valeur et de la date de la décision : réimporter un fichier
    ne crée aucun doublon.
    """

    def __init__(self, base: Any):
        """``base`` : une base pymongo (ou mongomock)."""
        self._collection = base[COLLECTION]

    def tous(self) -> list[Arbitrage]:
        """Les arbitrages, dans l'ordre où ils sont entrés."""
        return [
            _arbitrage(d, f"{COLLECTION}, document {d['_id']}")
            for d in self._collection.find().sort("rang", 1)
        ]

    def nombre(self) -> int:
        """Le nombre d'arbitrages de la collection."""
        return int(self._collection.count_documents({}))

    def ajouter(self, arbitrage: Arbitrage) -> bool:
        """Ajoute l'arbitrage après les autres ; ``False`` s'il y était déjà."""
        return self._ajouter([_ligne(arbitrage)]) == 1

    def retirer(self, cles: Iterable[tuple[str, str]]) -> int:
        """Retire les arbitrages des attestations ``cles`` ; rend leur nombre."""
        filtre = [{"source": s, "source_id": i} for s, i in cles]
        if not filtre:
            return 0
        return int(self._collection.delete_many({"$or": filtre}).deleted_count)

    def importer(self, chemin: Path) -> tuple[int, int]:
        """Ajoute les arbitrages du fichier absents de la collection, dans
        l'ordre du fichier ; rend le nombre de lignes lues et d'ajouts.
        Tout le fichier est validé avant le premier ajout."""
        arbitrages = lire_arbitrages(chemin)
        ajouts = self._ajouter([_ligne(a) for a in arbitrages])
        lus = len(arbitrages)
        log.info(
            f"import de {chemin} : {lus} arbitrage{_s(lus)} lu{_s(lus)}, "
            f"{ajouts} ajouté{_s(ajouts)} à {COLLECTION}"
        )
        return lus, ajouts

    def exporter(self, chemin: Path) -> int:
        """Écrit ``chemin`` (au format de ``arbitrages.csv``) avec tous les
        arbitrages de la collection, dans leur ordre ; rend leur nombre."""
        arbitrages = self.tous()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("w", encoding="utf-8", newline="") as f:
            ecrivain = csv.DictWriter(f, fieldnames=COLONNES, lineterminator="\n")
            ecrivain.writeheader()
            ecrivain.writerows(_ligne(a) for a in arbitrages)
        n = len(arbitrages)
        log.info(f"export de {COLLECTION} : {n} arbitrage{_s(n)} → {chemin}")
        return n

    def _ajouter(self, lignes: list[dict[str, str]]) -> int:
        """Ajoute les lignes absentes à la suite des autres ; rend leur nombre."""
        dernier = self._collection.find_one(sort=[("rang", -1)])
        rang = dernier["rang"] if dernier else 0
        ajouts = 0
        for ligne in lignes:
            identifiant = "|".join(
                (
                    f"{ligne['source']}:{ligne['source_id']}",
                    ligne["sorte"],
                    ligne["valeur"],
                    ligne["date"],
                )
            )
            resultat = self._collection.update_one(
                {"_id": identifiant},
                {"$setOnInsert": {**ligne, "rang": rang + 1}},
                upsert=True,
            )
            if resultat.upserted_id is not None:
                rang += 1
                ajouts += 1
        return ajouts


def _s(n: int) -> str:
    """La marque du pluriel."""
    return "s" if n > 1 else ""
