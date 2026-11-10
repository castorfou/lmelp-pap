"""La commande ``lmelp-pap emissions``, de bout en bout sur un cache déjà rempli."""

import csv
import json
import shutil
from pathlib import Path

import pytest

from lmelp_pap.cli import main


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _sans_base_lmelp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Les tests ne touchent jamais à la base Mongo de lmelp, ni au .env du dépôt."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)


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

    (ligne,) = [
        ligne
        for ligne in capsys.readouterr().err.splitlines()
        if ligne.startswith("Doutes : ")
    ]
    assert "désaccord de date 1" in ligne.split(" : ", 1)[1].split(", ")


def test_la_commande_page_ecrit_la_page_a_partir_des_csv(tmp_path: Path) -> None:
    sortie = tmp_path / "site" / "emissions" / "index.html"

    code = main(["page", "--donnees", str(FIXTURES / "liste"), "--sortie", str(sortie)])

    assert code == 0
    page = sortie.read_text(encoding="utf-8")
    assert page.lower().startswith("<!doctype html>")
    assert "1958-12-04" in page


def _attestations(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_la_commande_rattache_les_emissions_verifiees_de_lmelp(
    tmp_path: Path,
) -> None:
    cache, sortie = tmp_path / "cache", tmp_path / "sortie"
    _cache_rempli(cache)
    page = (
        "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/"
        "le-masque-et-la-plume-du-dimanche-11-fevrier-2024-2491269"
    )
    (cache / "lmelp").mkdir()
    (cache / "lmelp" / "emissions.json").write_text(
        json.dumps(
            [
                {
                    "page": page,
                    "titre": "Darrieussecq, Kerangal… que lire cette semaine ?",
                    "publication": "2024-02-10T09:00:00+00:00",
                    "fichier": "2024/14007-11.02.2024-ITEMA_2-2024F4007S0043.m4a",
                }
            ]
        ),
        encoding="utf-8",
    )
    (cache / "lmelp" / "collecte_terminee").touch()

    main(["emissions", "--cache", str(cache), "--sortie", str(sortie)])

    lmelp = [
        (a["emission_id"], a["source_id"], a["date"], a["themes"])
        for a in _attestations(sortie / "attestations.csv")
        if a["source"] == "lmelp"
    ]
    assert lmelp == [
        (
            "2024-02-11",
            "le-masque-et-la-plume-du-dimanche-11-fevrier-2024-2491269",
            "2024-02-10",
            "livres",
        )
    ]


def test_sans_acces_a_la_base_lmelp_la_collecte_est_sautee(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = tmp_path / "cache"

    code = main(["emissions", "--source", "lmelp", "--cache", str(cache)])

    assert code == 0
    assert "lmelp : collecte sautée" in capsys.readouterr().err
    assert not (cache / "lmelp" / "collecte_terminee").exists()


def _doutes(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_la_commande_applique_les_arbitrages_a_cote_de_la_liste(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache, sortie = tmp_path / "cache", tmp_path / "sortie"
    _cache_rempli(cache)
    sortie.mkdir()
    (sortie / "arbitrages.csv").write_text(
        "source,source_id,sorte,valeur,justification,date\n"
        # 1967-01-01, attesté par le seul MP3 Wayback, au thème inconnu
        "wayback_podcast,ITEMA_23820437,thème,théâtre,écouté l'enregistrement,"
        "2026-11-10\n"
        "ina,PH_INTROUVABLE,existence,n'existe pas,,2026-11-10\n",
        encoding="utf-8",
    )

    main(["emissions", "--cache", str(cache), "--sortie", str(sortie)])

    assert "1967-01-01" not in _ids(sortie / "emissions.csv")
    doutes = _doutes(sortie / "doutes.csv")
    # le thème est levé, l'existence reste fragile
    assert [d["type"] for d in doutes if d["emission_id"] == "1967-01-01"] == [
        "attestation fragile"
    ]
    assert [
        (d["source"], d["source_id"])
        for d in doutes
        if d["type"] == "arbitrage orphelin"
    ] == [("ina", "PH_INTROUVABLE")]
    assert "arbitrage orphelin 1" in capsys.readouterr().err


def test_un_theme_arbitre_est_marque_dans_emissions_csv(tmp_path: Path) -> None:
    cache, sortie = tmp_path / "cache", tmp_path / "sortie"
    _cache_rempli(cache)
    arbitrages = tmp_path / "arbitrages.csv"
    arbitrages.write_text(
        "source,source_id,sorte,valeur,justification,date\n"
        "wayback_podcast,ITEMA_23820437,thème,livres;théâtre,,2026-11-10\n",
        encoding="utf-8",
    )

    main(
        [
            "emissions",
            "--cache",
            str(cache),
            "--sortie",
            str(sortie),
            "--arbitrages",
            str(arbitrages),
        ]
    )

    with (sortie / "emissions.csv").open(encoding="utf-8", newline="") as f:
        (ligne,) = [e for e in csv.DictReader(f) if e["id"] == "1967-01-01"]
    assert (ligne["themes"], ligne["arbitrage"], ligne["justification_arbitrage"]) == (
        "livres;théâtre",
        "thème",
        "",
    )
