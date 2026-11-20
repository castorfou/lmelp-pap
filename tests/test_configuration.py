"""La configuration des commandes par variables d'environnement (image Docker)."""

from pathlib import Path

import pytest

from lmelp_pap.cli import _parser


_VARIABLES = ("PAP_CACHE", "PAP_DONNEES", "PAP_ARBITRAGES", "PAP_PORT", "PAP_HOTE")


@pytest.fixture(autouse=True)
def _sans_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_sans_variable_les_defauts_restent_ceux_du_depot() -> None:
    args = _parser().parse_args(["arbitrer"])

    assert args.cache == Path("data/raw/cache")
    assert args.sortie == Path("data/processed")
    assert args.arbitrages is None
    assert args.port == 8765
    assert args.hote == "127.0.0.1"


def test_les_variables_pap_configurent_l_appli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAP_CACHE", "/data/cache")
    monkeypatch.setenv("PAP_DONNEES", "/data/processed")
    monkeypatch.setenv("PAP_ARBITRAGES", "/data/arbitrages.csv")
    monkeypatch.setenv("PAP_PORT", "8090")
    monkeypatch.setenv("PAP_HOTE", "0.0.0.0")

    args = _parser().parse_args(["arbitrer"])

    assert args.cache == Path("/data/cache")
    assert args.sortie == Path("/data/processed")
    assert args.arbitrages == Path("/data/arbitrages.csv")
    assert args.port == 8090
    assert args.hote == "0.0.0.0"


def test_les_variables_valent_aussi_pour_la_construction_et_la_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAP_CACHE", "/data/cache")
    monkeypatch.setenv("PAP_DONNEES", "/data/processed")

    emissions = _parser().parse_args(["emissions"])
    page = _parser().parse_args(["page"])

    assert emissions.cache == Path("/data/cache")
    assert emissions.sortie == Path("/data/processed")
    assert page.donnees == Path("/data/processed")


def test_une_option_explicite_l_emporte_sur_la_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAP_PORT", "8090")

    args = _parser().parse_args(["arbitrer", "--port", "9000"])

    assert args.port == 9000
