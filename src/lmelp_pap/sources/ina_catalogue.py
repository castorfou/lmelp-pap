"""Scraper Playwright pour le catalogue INA du Masque & La Plume (1955-2026)."""

import time

import pandas as pd
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


_INA_URL = "https://catalogue.ina.fr"
_SEARCH_TERM = "masque et la plume"
_COLUMNS_RAW = [
    "date_diffusion",
    "titre",
    "titre_collection",
    "chaine",
    "heure",
    "duree",
    "genre",
    "url_ina",
    "source",
]

# JS appelé après la recherche pour filtrer la thématique Littérature
_FILTER_JS = "filterQueryByFacet('themat_facet','Littérature','Thématique1', '', 0, submitToGetSolr)"


def _parse_ina_date(date_str: str | None) -> str | None:
    """Convertit une date INA (JJ/MM/AAAA) en format YYYY-MM-DD."""
    if not date_str:
        return None
    parts = date_str.strip().split("/")
    if len(parts) == 3:
        day, month, year = parts
        try:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            return None
    return None


def _parse_ina_row(cells: list[str], url: str | None = None) -> dict:
    """Extrait un dict depuis les cellules d'une ligne du tableau INA.

    Ordre des colonnes (9 colonnes) :
    [index, chaîne, date(JJ/MM/AAAA), heure, durée, titre propre, titre collection,
     titre programme, genre]
    """
    return {
        "date_diffusion": _parse_ina_date(cells[2] if len(cells) > 2 else None),
        "titre": cells[5] if len(cells) > 5 else None,
        "titre_collection": cells[6] if len(cells) > 6 else None,
        "chaine": cells[1] if len(cells) > 1 else None,
        "heure": cells[3] if len(cells) > 3 else None,
        "duree": cells[4] if len(cells) > 4 else None,
        "genre": cells[8] if len(cells) > 8 else None,
        "url_ina": url,
        "source": "ina",
    }


_MASQUE_KEYWORDS = ("masque", "plume")


def _filter_masque_et_la_plume(df: pd.DataFrame) -> pd.DataFrame:
    """Garde uniquement les notices dont la collection est Le masque et la plume."""
    col = df["titre_collection"].str.lower().fillna("")
    mask = col.apply(lambda c: all(k in c for k in _MASQUE_KEYWORDS))
    return df[mask].reset_index(drop=True)


def _sort_by_date(df: pd.DataFrame) -> pd.DataFrame:
    """Trie un DataFrame par date_diffusion (ordre chronologique croissant)."""
    return df.sort_values("date_diffusion").reset_index(drop=True)


def _extract_table_rows(page) -> list[dict]:  # type: ignore[no-untyped-def]
    """Extrait les lignes de données du tableau de résultats (ignore les lignes de facettes)."""
    rows = page.query_selector_all("table tr")
    results = []
    for row in rows:
        cells = row.query_selector_all("td")
        if not cells:
            continue
        texts = [c.inner_text().strip() for c in cells]
        if len(texts) < 6:
            continue
        if not texts[0].isdigit():
            continue
        links = row.query_selector_all("a[href]")
        url = links[0].get_attribute("href") if links else None
        entry = _parse_ina_row(texts, url=url)
        if entry["date_diffusion"] or entry["titre"]:
            results.append(entry)
    return results


def scrape_ina_catalogue_raw(
    max_pages: int = 99, delay: float = 2.0, facette: bool = True
) -> pd.DataFrame:
    """Scrape le catalogue INA et retourne toutes les colonnes disponibles.

    Args:
        max_pages: Nombre maximum de pages à parcourir (0 = ne scrape pas).
        delay: Délai en secondes entre chaque page pour respecter les CGU INA.
        facette: Limite la recherche à la thématique Littérature ; sinon toute
            la collection.

    Returns:
        DataFrame brut avec date_diffusion, titre, titre_collection, chaine,
        heure, duree, genre, url_ina, source.
    """
    if max_pages == 0:
        return pd.DataFrame(columns=_COLUMNS_RAW)

    all_episodes: list[dict] = []

    with sync_playwright() as pw, pw.chromium.launch(headless=True) as browser:
        page = browser.new_page()

        page.goto(_INA_URL, wait_until="networkidle")
        time.sleep(2)

        search_input = page.query_selector("input[name='chValues[11]']")
        if search_input is None:
            return pd.DataFrame(columns=_COLUMNS_RAW)

        search_input.fill(_SEARCH_TERM)
        search_input.press("Enter")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        if facette:
            page.evaluate(_FILTER_JS)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

        for page_num in range(1, max_pages + 1):
            if page_num > 1:
                try:
                    page.evaluate(
                        f"pagerForm.page.value={page_num}; pagerForm.submit();"
                    )
                    page.wait_for_load_state("networkidle")
                    time.sleep(delay)
                except PlaywrightError:
                    break

            rows = _extract_table_rows(page)
            if not rows:
                break
            all_episodes.extend(rows)

    if not all_episodes:
        return pd.DataFrame(columns=_COLUMNS_RAW)
    return _sort_by_date(_filter_masque_et_la_plume(pd.DataFrame(all_episodes)))
