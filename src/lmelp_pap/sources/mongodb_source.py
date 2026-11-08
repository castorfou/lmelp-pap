"""Export des épisodes littéraires depuis MongoDB vers un DataFrame structuré."""

from datetime import datetime
from typing import Any

import pandas as pd
import pymongo


def get_episodes_from_mongodb(mongo_uri: str, db_name: str) -> list[dict]:
    """Récupère tous les épisodes littéraires (type='livres') depuis MongoDB."""
    client: pymongo.MongoClient[dict[str, Any]] = pymongo.MongoClient(mongo_uri)
    collection = client[db_name]["episodes"]
    docs = list(collection.find({"type": "livres"}))
    client.close()
    return docs


def episodes_to_dataframe(episodes: list[dict]) -> pd.DataFrame:
    """Convertit une liste de documents MongoDB en DataFrame normalisé."""
    rows = []
    for ep in episodes:
        date = ep.get("date")
        if isinstance(date, datetime):
            date_str = date.strftime("%Y-%m-%d")
        elif date is not None:
            date_str = str(date)[:10]
        else:
            date_str = None

        rows.append(
            {
                "date_diffusion": date_str,
                "titre": ep.get("titre"),
                "animateur": ep.get("auteur"),
                "description": ep.get("description"),
                "url_page": ep.get("episode_page_url"),
                "url_audio": ep.get("url"),
                "source": "mongodb",
            }
        )
    return pd.DataFrame(rows)
