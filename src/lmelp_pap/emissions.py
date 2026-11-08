"""Orchestrateur : fusionne toutes les sources et produit le CSV des émissions."""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


load_dotenv()

_DEFAULT_OUTPUT = Path("data/processed/emissions.csv")
_DEFAULT_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27018/")
_DEFAULT_MONGO_DB = os.getenv("MONGO_DB", "masque_et_la_plume")

_COLUMNS = [
    "date_diffusion",
    "titre",
    "animateur",
    "description",
    "url_page",
    "url_audio",
    "source",
]


def merge_sources(dataframes: list[pd.DataFrame]) -> pd.DataFrame:
    """Fusionne plusieurs DataFrames, déduplique par date et trie chronologiquement.

    En cas de doublon sur date_diffusion, la source avec le rang de priorité
    le plus élevé est conservée (mongodb > ina).
    """
    priority = {"mongodb": 0, "ina": 1}

    combined = pd.concat(dataframes, ignore_index=True)
    combined = combined.dropna(subset=["date_diffusion"])
    combined["_priority"] = combined["source"].map(lambda s: priority.get(s, 99))
    combined = combined.sort_values(["date_diffusion", "_priority"])
    combined = combined.drop_duplicates(subset=["date_diffusion"], keep="first")
    combined = combined.drop(columns=["_priority"])
    combined = combined.sort_values("date_diffusion").reset_index(drop=True)
    return combined


def save_emissions_csv(df: pd.DataFrame, output_path: Path) -> Path:
    """Sauvegarde le DataFrame dans un fichier CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


def collect_all_emissions(
    mongo_uri: str = _DEFAULT_MONGO_URI,
    db_name: str = _DEFAULT_MONGO_DB,
    scrape_ina: bool = True,
    output_path: Path | None = None,
) -> Path:
    """Collecte toutes les émissions depuis toutes les sources et génère le CSV.

    Sources utilisées :
    - MongoDB : épisodes collectés depuis France Inter (2006→présent)
    - catalogue.ina.fr : notices archivées pour 1955-2005

    Args:
        mongo_uri: URI de connexion MongoDB (défaut : variable MONGO_URI du .env).
        db_name: Nom de la base de données MongoDB.
        scrape_ina: Active le scraping catalogue INA (1955-2005).
        output_path: Chemin du CSV de sortie.

    Returns:
        Chemin vers le fichier CSV généré.
    """
    from lmelp_pap.sources.mongodb_source import (
        episodes_to_dataframe,
        get_episodes_from_mongodb,
    )

    if output_path is None:
        output_path = _DEFAULT_OUTPUT

    dataframes: list[pd.DataFrame] = []

    # Source 1 : MongoDB (épisodes France Inter déjà collectés)
    episodes = get_episodes_from_mongodb(mongo_uri, db_name)
    df_mongo = episodes_to_dataframe(episodes)
    if not df_mongo.empty:
        dataframes.append(df_mongo)

    # Source 2 : INA catalogue (1955-2005)
    if scrape_ina:
        from lmelp_pap.sources.ina_catalogue import scrape_ina_catalogue

        df_ina = scrape_ina_catalogue()
        if not df_ina.empty:
            dataframes.append(df_ina)

    if not dataframes:
        df_result = pd.DataFrame(columns=_COLUMNS)
    else:
        df_result = merge_sources(dataframes)

    return save_emissions_csv(df_result, output_path)
