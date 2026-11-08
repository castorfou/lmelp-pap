"""Collecte de radiofrance.fr, face à un faux site (sans réseau)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from lmelp_pap import collecte


FIXTURES = Path(__file__).parent / "fixtures" / "radiofrance"


def test_la_collecte_s_arrete_quand_le_site_renvoie_vers_la_premiere_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Au-delà de la dernière page, radiofrance.fr redirige vers la page 1."""
    page_1 = (FIXTURES / "liste-p100.html").read_text(encoding="utf-8")
    pages_demandees: list[str] = []

    def faux_get(adresse: str, params: dict[str, str] | None = None) -> object:
        if params is not None:  # page de liste
            pages_demandees.append(params["p"])
            if len(pages_demandees) > 5:
                raise AssertionError("la collecte tourne en boucle")
            return SimpleNamespace(text=page_1)
        return SimpleNamespace(text="<html>fiche</html>")

    monkeypatch.setattr(collecte, "_get", faux_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    collecte.collecter_radiofrance(tmp_path)

    assert pages_demandees == ["1", "2"]
    assert len(list((tmp_path / "fiches").glob("*.html"))) > 0
