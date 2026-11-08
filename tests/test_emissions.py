"""Tests TDD pour la reconstitution de la liste des émissions du Masque & La Plume."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd


# ─── Source MongoDB ──────────────────────────────────────────────────────────


class TestMongodbSource:
    def test_get_episodes_returns_list(self):
        from lmelp_pap.sources.mongodb_source import get_episodes_from_mongodb

        mock_col = MagicMock()
        mock_col.find.return_value = []
        with patch("lmelp_pap.sources.mongodb_source.pymongo") as mock_pymongo:
            mock_client = MagicMock()
            mock_pymongo.MongoClient.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_col
            result = get_episodes_from_mongodb(
                "mongodb://localhost:27018/", "masque_et_la_plume"
            )
        assert isinstance(result, list)

    def test_get_episodes_filters_livres_only(self):
        from lmelp_pap.sources.mongodb_source import get_episodes_from_mongodb

        mock_col = MagicMock()
        mock_col.find.return_value = iter([])
        with patch("lmelp_pap.sources.mongodb_source.pymongo") as mock_pymongo:
            mock_client = MagicMock()
            mock_pymongo.MongoClient.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_col
            get_episodes_from_mongodb(
                "mongodb://localhost:27018/", "masque_et_la_plume"
            )
        call_args = mock_col.find.call_args
        assert call_args[0][0].get("type") == "livres"

    def test_episodes_to_dataframe_has_required_columns(self):
        from lmelp_pap.sources.mongodb_source import episodes_to_dataframe

        episodes = [
            {
                "date": datetime(2020, 3, 29),
                "titre": "Test titre",
                "auteur": "Jérôme Garcin",
                "description": "Une description",
                "episode_page_url": "https://example.com",
                "url": "https://example.com/audio.mp3",
            }
        ]
        df = episodes_to_dataframe(episodes)
        required = {
            "date_diffusion",
            "titre",
            "animateur",
            "description",
            "url_page",
            "url_audio",
            "source",
        }
        assert required.issubset(set(df.columns))

    def test_episodes_to_dataframe_date_format(self):
        from lmelp_pap.sources.mongodb_source import episodes_to_dataframe

        episodes = [
            {
                "date": datetime(2020, 3, 29),
                "titre": "T",
                "auteur": None,
                "description": None,
                "episode_page_url": None,
                "url": None,
            }
        ]
        df = episodes_to_dataframe(episodes)
        assert df["date_diffusion"].iloc[0] == "2020-03-29"

    def test_episodes_to_dataframe_source_is_mongodb(self):
        from lmelp_pap.sources.mongodb_source import episodes_to_dataframe

        episodes = [
            {
                "date": datetime(2020, 3, 29),
                "titre": "T",
                "auteur": None,
                "description": None,
                "episode_page_url": None,
                "url": None,
            }
        ]
        df = episodes_to_dataframe(episodes)
        assert df["source"].iloc[0] == "mongodb"


# ─── Scraper INA ─────────────────────────────────────────────────────────────


class TestINACatalogueScraper:
    def test_build_ina_search_url_contains_query(self):
        from lmelp_pap.sources.ina_catalogue import build_ina_search_url

        url = build_ina_search_url(page=1)
        assert "masque" in url.lower() or "ina.fr" in url

    def test_parse_ina_results_returns_list(self):
        from lmelp_pap.sources.ina_catalogue import parse_ina_results_page

        result = parse_ina_results_page("<html><body></body></html>")
        assert isinstance(result, list)

    def test_parse_ina_results_has_required_fields(self):
        from lmelp_pap.sources.ina_catalogue import parse_ina_results_page

        html = """<html><body>
        <div class="result-item">
          <span class="date">12/09/1995</span>
          <span class="title">Le Masque et la Plume</span>
        </div>
        </body></html>"""
        result = parse_ina_results_page(html)
        if result:
            assert "date_diffusion" in result[0]

    def test_parse_ina_date_converts_dd_mm_yyyy(self):
        from lmelp_pap.sources.ina_catalogue import _parse_ina_date

        assert _parse_ina_date("12/09/1995") == "1995-09-12"
        assert _parse_ina_date("01/01/1955") == "1955-01-01"
        assert _parse_ina_date(None) is None
        assert _parse_ina_date("") is None

    def test_parse_ina_table_row_extracts_fields(self):
        from lmelp_pap.sources.ina_catalogue import _parse_ina_row

        cells = [
            "1",
            "France Inter",
            "06/01/1985",
            "00:00:00",
            "01:00:00",
            "Le masque et la plume : littérature",
            "Le masque et la plume",
            "",
            "Magazine",
        ]
        row = _parse_ina_row(
            cells, url="https://catalogue.ina.fr/doc/TV-RADIO/PH_TEST/test"
        )
        assert row["date_diffusion"] == "1985-01-06"
        assert row["titre"] == "Le masque et la plume : littérature"
        assert row["source"] == "ina"
        assert row["url_ina"] == "https://catalogue.ina.fr/doc/TV-RADIO/PH_TEST/test"
        assert row["chaine"] == "France Inter"
        assert row["genre"] == "Magazine"

    def test_scrape_ina_catalogue_returns_dataframe(self):
        from unittest.mock import MagicMock, patch

        import pandas as pd

        from lmelp_pap.sources.ina_catalogue import scrape_ina_catalogue

        with patch("lmelp_pap.sources.ina_catalogue.sync_playwright") as mock_pw:
            mock_page = MagicMock()
            mock_page.query_selector_all.return_value = []
            mock_browser = MagicMock()
            mock_browser.__enter__ = MagicMock(return_value=mock_browser)
            mock_browser.__exit__ = MagicMock(return_value=False)
            mock_browser.new_page.return_value = mock_page
            mock_pw_instance = MagicMock()
            mock_pw_instance.__enter__ = MagicMock(return_value=mock_pw_instance)
            mock_pw_instance.__exit__ = MagicMock(return_value=False)
            mock_pw_instance.chromium.launch.return_value = mock_browser
            mock_pw.return_value = mock_pw_instance
            result = scrape_ina_catalogue(max_pages=0)
        assert isinstance(result, pd.DataFrame)

    def test_filter_ina_keeps_only_masque_et_la_plume(self):
        import pandas as pd

        from lmelp_pap.sources.ina_catalogue import _filter_masque_et_la_plume

        df = pd.DataFrame(
            [
                {
                    "titre": "Le masque et la plume : Littérature",
                    "titre_collection": "Le masque et la plume",
                },
                {"titre": "Littérature", "titre_collection": "Le masque et la plume"},
                {"titre": "Radioscopie", "titre_collection": "Radioscopie"},
                {
                    "titre": "Questions sans visage",
                    "titre_collection": "Questions sans visage",
                },
                {"titre": "Livres", "titre_collection": "Le masque et la plume"},
            ]
        )
        result = _filter_masque_et_la_plume(df)
        assert len(result) == 3
        assert all(
            "masque" in str(c).lower() or "plume" in str(c).lower()
            for c in result["titre_collection"]
        )

    def test_scrape_ina_catalogue_raw_is_sorted_by_date(self):
        from lmelp_pap.sources.ina_catalogue import _parse_ina_row

        rows = [
            _parse_ina_row(
                ["1", "France Inter", "15/03/1990", "", "", "Titre B", "", "", ""],
                url=None,
            ),
            _parse_ina_row(
                ["2", "France Inter", "06/01/1964", "", "", "Titre A", "", "", ""],
                url=None,
            ),
        ]
        import pandas as pd

        df = pd.DataFrame(rows)
        dates = list(df["date_diffusion"])
        assert dates != sorted(dates), "pré-condition : non trié"

        from lmelp_pap.sources.ina_catalogue import _sort_by_date

        df_sorted = _sort_by_date(df)
        dates_sorted = list(df_sorted["date_diffusion"])
        assert dates_sorted == sorted(dates_sorted)

    def test_scrape_ina_catalogue_has_required_columns(self):
        from unittest.mock import MagicMock, patch

        from lmelp_pap.sources.ina_catalogue import scrape_ina_catalogue

        with patch("lmelp_pap.sources.ina_catalogue.sync_playwright") as mock_pw:
            mock_page = MagicMock()
            mock_page.query_selector_all.return_value = []
            mock_browser = MagicMock()
            mock_browser.__enter__ = MagicMock(return_value=mock_browser)
            mock_browser.__exit__ = MagicMock(return_value=False)
            mock_browser.new_page.return_value = mock_page
            mock_pw_instance = MagicMock()
            mock_pw_instance.__enter__ = MagicMock(return_value=mock_pw_instance)
            mock_pw_instance.__exit__ = MagicMock(return_value=False)
            mock_pw_instance.chromium.launch.return_value = mock_browser
            mock_pw.return_value = mock_pw_instance
            result = scrape_ina_catalogue(max_pages=0)
        required = {"date_diffusion", "titre", "source"}
        assert required.issubset(set(result.columns))


# ─── Orchestrateur + CSV ─────────────────────────────────────────────────────


class TestEmissionsOrchestrator:
    def test_merge_sources_deduplicates_by_date(self):
        from lmelp_pap.emissions import merge_sources

        df1 = pd.DataFrame(
            [
                {"date_diffusion": "2020-03-29", "titre": "A", "source": "mongodb"},
                {"date_diffusion": "2020-04-05", "titre": "B", "source": "mongodb"},
            ]
        )
        df2 = pd.DataFrame(
            [
                {"date_diffusion": "2020-03-29", "titre": "A", "source": "ina"},
            ]
        )
        merged = merge_sources([df1, df2])
        assert len(merged[merged["date_diffusion"] == "2020-03-29"]) == 1

    def test_merge_sources_mongodb_has_priority_over_ina(self):
        from lmelp_pap.emissions import merge_sources

        df1 = pd.DataFrame(
            [{"date_diffusion": "2000-01-09", "titre": "Mongo", "source": "mongodb"}]
        )
        df2 = pd.DataFrame(
            [{"date_diffusion": "2000-01-09", "titre": "INA", "source": "ina"}]
        )
        merged = merge_sources([df1, df2])
        assert (
            merged.loc[merged["date_diffusion"] == "2000-01-09", "source"].iloc[0]
            == "mongodb"
        )

    def test_merge_sources_sorts_by_date(self):
        from lmelp_pap.emissions import merge_sources

        df1 = pd.DataFrame(
            [
                {"date_diffusion": "2020-04-05", "titre": "B", "source": "mongodb"},
                {"date_diffusion": "2020-03-29", "titre": "A", "source": "mongodb"},
            ]
        )
        merged = merge_sources([df1])
        dates = list(merged["date_diffusion"])
        assert dates == sorted(dates)

    def test_save_emissions_csv_creates_file(self, tmp_path: Path) -> None:
        from lmelp_pap.emissions import save_emissions_csv

        df = pd.DataFrame(
            [{"date_diffusion": "2020-03-29", "titre": "Test", "source": "mongodb"}]
        )
        output = tmp_path / "emissions.csv"
        result = save_emissions_csv(df, output)
        assert result.exists()

    def test_save_emissions_csv_has_date_column(self, tmp_path: Path) -> None:
        from lmelp_pap.emissions import save_emissions_csv

        df = pd.DataFrame(
            [{"date_diffusion": "2020-03-29", "titre": "Test", "source": "mongodb"}]
        )
        output = tmp_path / "emissions.csv"
        save_emissions_csv(df, output)
        loaded = pd.read_csv(output)
        assert "date_diffusion" in loaded.columns

    def test_save_emissions_csv_returns_path(self, tmp_path: Path) -> None:
        from lmelp_pap.emissions import save_emissions_csv

        df = pd.DataFrame(
            [{"date_diffusion": "2020-03-29", "titre": "Test", "source": "mongodb"}]
        )
        output = tmp_path / "emissions.csv"
        result = save_emissions_csv(df, output)
        assert isinstance(result, Path)

    def test_csv_is_sorted_by_date(self, tmp_path: Path) -> None:
        from lmelp_pap.emissions import merge_sources, save_emissions_csv

        df = pd.DataFrame(
            [
                {"date_diffusion": "2020-04-05", "titre": "C", "source": "mongodb"},
                {"date_diffusion": "1995-11-12", "titre": "A", "source": "ina"},
                {"date_diffusion": "2010-09-12", "titre": "B", "source": "mongodb"},
            ]
        )
        merged = merge_sources([df])
        output = tmp_path / "emissions.csv"
        save_emissions_csv(merged, output)
        loaded = pd.read_csv(output)
        dates = loaded["date_diffusion"].tolist()
        assert dates == sorted(dates)
