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
            return SimpleNamespace(text=page_1, content=page_1.encode())
        return SimpleNamespace(text="<html>fiche</html>", content=b"<html>fiche</html>")

    monkeypatch.setattr(collecte, "_get", faux_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    lignes: list[str] = []

    collecte.collecter_radiofrance(tmp_path, lignes.append)

    assert pages_demandees == ["1", "2"]
    assert len(list((tmp_path / "fiches").glob("*.html"))) > 0
    # une ligne de progression par page lue
    assert lignes == ["radiofrance : page 1, 20 fiches vues, 20 téléchargées"]


def test_une_fiche_est_enregistree_en_utf8_meme_sans_charset_annonce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """radiofrance.fr n'annonce pas d'encodage : requests devine latin-1."""
    page_1 = (FIXTURES / "liste-p100.html").read_text(encoding="utf-8")
    fiche = "<html>Jérôme Garcin</html>".encode()
    listes: list[str] = []

    def faux_get(adresse: str, params: dict[str, str] | None = None) -> object:
        if params is not None:
            listes.append(params["p"])
            contenu = page_1.encode() if len(listes) == 1 else b""
        else:
            contenu = fiche
        return SimpleNamespace(content=contenu, text=contenu.decode("latin-1"))

    monkeypatch.setattr(collecte, "_get", faux_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    collecte.collecter_radiofrance(tmp_path)

    enregistree = next((tmp_path / "fiches").glob("*.html"))
    assert "Jérôme Garcin" in enregistree.read_text(encoding="utf-8")


def test_la_collecte_ina_met_en_cache_la_fiche_detaillee_de_chaque_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pandas as pd

    from lmelp_pap.sources import ina_catalogue

    url = "https://catalogue.ina.fr/doc/TV-RADIO/RD_1098450.001/le-masque-du-09-janvier-2000"
    notices = pd.DataFrame(
        [{"date_diffusion": "2000-01-09", "url_ina": f"{url}?rang=3", "source": "ina"}]
    )
    monkeypatch.setattr(
        ina_catalogue, "scrape_ina_catalogue_raw", lambda facette: notices.copy()
    )
    fiche = '<td id="DE" class="val">cinéma ; film</td>'.encode()
    demandees: list[str] = []

    def faux_get(adresse: str, params: dict[str, str] | None = None) -> object:
        demandees.append(adresse)
        return SimpleNamespace(status_code=200, content=fiche)

    monkeypatch.setattr(collecte, "_get", faux_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    collecte.collecter_ina(tmp_path)
    collecte.collecter_ina(tmp_path)  # une fiche en cache n'est pas re-téléchargée

    assert demandees == [url]
    enregistree = (tmp_path / "fiches" / "RD_1098450.001.html").read_text("utf-8")
    assert "cinéma ; film" in enregistree


def test_la_collecte_des_fiches_ina_affiche_sa_progression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Seules les fiches absentes du cache sont comptées dans la progression."""
    base = "https://catalogue.ina.fr/doc/TV-RADIO/RD_{}.001/le-masque"
    (tmp_path / "fiches").mkdir()
    (tmp_path / "fiches" / "RD_1.001.html").write_text("déjà là", "utf-8")
    monkeypatch.setattr(
        collecte,
        "_get",
        lambda adresse, params=None: SimpleNamespace(status_code=200, content=b"x"),
    )
    monkeypatch.setattr("time.sleep", lambda _: None)

    lignes: list[str] = []

    collecte._collecter_fiches_ina(
        tmp_path, [base.format(n) for n in (1, 2, 3)], lignes.append
    )

    erreurs = capsys.readouterr().err
    assert "INFO    collecte : ina : fiches détaillées 2/2" in erreurs
    assert lignes == ["ina : fiches détaillées 2/2 (≈ 0 min restantes)"]


def test_la_lecture_du_cache_ina_tient_compte_des_fiches_detaillees(
    tmp_path: Path,
) -> None:
    fixtures_ina = Path(__file__).parent / "fixtures" / "ina" / "fiches"
    (tmp_path / "notices.csv").write_text(
        "date_diffusion,titre,url_ina,facette_litterature\n"
        "2000-01-09,Le masque et la plume du 09 janvier 2000,"
        "https://catalogue.ina.fr/doc/TV-RADIO/RD_1098450.001/le-masque?rang=3,non\n",
        encoding="utf-8",
    )
    (tmp_path / "fiches").mkdir()
    (tmp_path / "fiches" / "RD_1098450.001.html").write_text(
        (fixtures_ina / "RD_1098450.001.html").read_text("utf-8"), "utf-8"
    )

    (notice,) = collecte.lire_ina(tmp_path)

    assert notice.themes == frozenset({"cinéma"})
