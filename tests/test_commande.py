"""La commande ``lmelp-pap emissions``, de bout en bout sur un cache déjà rempli."""

import csv
import shutil
from pathlib import Path

import pytest

from lmelp_pap.cli import main


FIXTURES = Path(__file__).parent / "fixtures"


def _cache_rempli(cache: Path) -> None:
    """Un cache comme le laisse une collecte terminée, construit avec les fixtures."""
    fiches = cache / "radiofrance" / "fiches"
    fiches.mkdir(parents=True)
    for fiche in (FIXTURES / "radiofrance").glob("*.html"):
        if not fiche.name.startswith("liste-"):
            shutil.copy(fiche, fiches / fiche.name)

    (cache / "wayback_podcast").mkdir()
    shutil.copy(FIXTURES / "wayback" / "cdx_podcast.txt", cache / "wayback_podcast")

    (cache / "ina").mkdir()
    shutil.copy(FIXTURES / "ina" / "notices.csv", cache / "ina")

    (cache / "anciennes_listes").mkdir()
    (cache / "anciennes_listes" / "archives-2006.html").write_text(
        (FIXTURES / "anciennes_listes" / "archives-2006.html").read_text(
            encoding="latin-1"
        ),
        encoding="utf-8",
    )

    for source in ("radiofrance", "wayback_podcast", "ina", "anciennes_listes"):
        (cache / source / "collecte_terminee").touch()


def _ids(chemin: Path) -> set[str]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return {ligne["id"] for ligne in csv.DictReader(f)}


def test_la_commande_construit_la_liste_depuis_le_cache_sans_reseau(
    tmp_path: Path,
) -> None:
    cache, sortie = tmp_path / "cache", tmp_path / "sortie"
    _cache_rempli(cache)

    code = main(["emissions", "--cache", str(cache), "--sortie", str(sortie)])

    assert code == 0
    ids = _ids(sortie / "emissions.csv")
    assert "1958-12-04" in ids  # extrait Aragon, radiofrance.fr
    assert "1967-01-01" in ids  # MP3 Wayback, thème inconnu
    assert "1956-01-22" in ids  # notice INA
    assert "2006-12-17" in ids  # ancienne liste, Livres
    assert "2006-12-24" not in ids  # ancienne liste, Cinéma : hors liste
    assert "1994-05-29" not in ids  # extrait Pulp Fiction : cinéma
    for fichier in ("attestations.csv", "enregistrements.csv"):
        assert (sortie / fichier).exists()
    assert (sortie / "doutes.csv").exists()
    assert not (sortie / "rapport_rapprochement.csv").exists()


def test_la_commande_affiche_le_nombre_de_doutes_par_type(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache, sortie = tmp_path / "cache", tmp_path / "sortie"
    _cache_rempli(cache)
    # une seconde notice de l'émission du 22 janvier 1956, datée deux jours après
    with (cache / "ina" / "notices.csv").open("a", encoding="utf-8") as f:
        f.write(
            "1956-01-24,Littérature,Le masque et la plume,Paris Inter,,00:50:00,"
            "Magazine,https://catalogue.ina.fr/doc/TV-RADIO/PH_PHD1/litterature,oui\n"
        )

    main(["emissions", "--cache", str(cache), "--sortie", str(sortie)])

    assert "Doutes : désaccord de date 1\n" in capsys.readouterr().err


def test_la_commande_page_ecrit_la_page_a_partir_des_csv(tmp_path: Path) -> None:
    sortie = tmp_path / "site" / "emissions" / "index.html"

    code = main(["page", "--donnees", str(FIXTURES / "liste"), "--sortie", str(sortie)])

    assert code == 0
    page = sortie.read_text(encoding="utf-8")
    assert page.lower().startswith("<!doctype html>")
    assert "1958-12-04" in page
