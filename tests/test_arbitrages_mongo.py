"""Les arbitrages conservés dans Mongo (collection ``pap_arbitrages``), simulé
par mongomock : import du CSV, ajout, retrait, export."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import mongomock
import pytest

from lmelp_pap import cli, logs
from lmelp_pap.arbitrages import ArbitragesMongo, lire_arbitrages
from lmelp_pap.arbitrer import Atelier
from lmelp_pap.liste import Arbitrage
from lmelp_pap.maturite import Depot
from tests.test_commande import _cache_rempli
from tests.test_logs import _demarrer_la_commande, messages


CSV = (
    "source,source_id,sorte,valeur,justification,date\n"
    "ina,RD_4294389.001,thème,théâtre,titre explicite,2026-11-10\n"
    "radiofrance,le-mage-du-kremlin-1192090,existence,n'existe pas,"
    "écouté l'enregistrement,2026-11-10\n"
    "ina,RD_1.001,date,2014-09-28,,2026-11-12T08:30:00\n"
)


@pytest.fixture
def base() -> Any:
    return mongomock.MongoClient()["masque_et_la_plume"]


@pytest.fixture
def csv_existant(tmp_path: Path) -> Path:
    chemin = tmp_path / "arbitrages.csv"
    chemin.write_text(CSV, encoding="utf-8")
    return chemin


def _theme(source_id: str, theme: str = "cinéma") -> Arbitrage:
    return Arbitrage(
        source="ina",
        source_id=source_id,
        sorte="thème",
        themes=frozenset({theme}),
        justification="titre explicite",
        date=datetime(2026, 11, 20, 14, 3, 12),
    )


def test_importer_le_csv_rend_ses_arbitrages_dans_l_ordre(
    base: Any, csv_existant: Path
) -> None:
    arbitrages = ArbitragesMongo(base)

    assert arbitrages.importer(csv_existant) == (3, 3)
    assert arbitrages.tous() == lire_arbitrages(csv_existant)


def test_importer_deux_fois_le_meme_csv_ne_cree_pas_de_doublon(
    base: Any, csv_existant: Path
) -> None:
    arbitrages = ArbitragesMongo(base)
    arbitrages.importer(csv_existant)

    assert arbitrages.importer(csv_existant) == (3, 0)
    assert len(arbitrages.tous()) == 3


def test_un_arbitrage_ajoute_survit_a_un_nouveau_client(base: Any) -> None:
    ArbitragesMongo(base).ajouter(_theme("RD_9.001"))

    assert ArbitragesMongo(base).tous() == [_theme("RD_9.001")]


def test_les_arbitrages_ajoutes_suivent_ceux_importes(
    base: Any, csv_existant: Path
) -> None:
    arbitrages = ArbitragesMongo(base)
    arbitrages.importer(csv_existant)
    arbitrages.ajouter(_theme("RD_9.001"))

    assert arbitrages.tous() == [*lire_arbitrages(csv_existant), _theme("RD_9.001")]


def test_retirer_enleve_les_arbitrages_des_attestations_donnees(
    base: Any, csv_existant: Path
) -> None:
    arbitrages = ArbitragesMongo(base)
    arbitrages.importer(csv_existant)

    assert arbitrages.retirer({("ina", "RD_4294389.001"), ("ina", "RD_1.001")}) == 2
    assert [a.source_id for a in arbitrages.tous()] == ["le-mage-du-kremlin-1192090"]
    assert arbitrages.retirer({("ina", "inconnue")}) == 0


def test_l_export_redonne_le_csv_importe_au_caractere_pres(
    base: Any, csv_existant: Path, tmp_path: Path
) -> None:
    arbitrages = ArbitragesMongo(base)
    arbitrages.importer(csv_existant)
    exporte = tmp_path / "sortie" / "arbitrages.csv"

    assert arbitrages.exporter(exporte) == 3
    assert exporte.read_text(encoding="utf-8") == CSV


def test_un_arbitrage_ajoute_apparait_dans_le_csv_apres_export(
    base: Any, tmp_path: Path
) -> None:
    arbitrages = ArbitragesMongo(base)
    arbitrages.ajouter(_theme("RD_9.001"))
    exporte = tmp_path / "arbitrages.csv"

    arbitrages.exporter(exporte)

    assert exporte.read_text(encoding="utf-8").splitlines()[1] == (
        "ina,RD_9.001,thème,cinéma,titre explicite,2026-11-20T14:03:12"
    )


def test_l_export_d_une_collection_vide_ecrit_l_entete(
    base: Any, tmp_path: Path
) -> None:
    exporte = tmp_path / "arbitrages.csv"

    assert ArbitragesMongo(base).exporter(exporte) == 0
    assert exporte.read_text(encoding="utf-8") == (
        "source,source_id,sorte,valeur,justification,date\n"
    )


def test_importer_un_csv_absent_n_importe_rien(base: Any, tmp_path: Path) -> None:
    assert ArbitragesMongo(base).importer(tmp_path / "absent.csv") == (0, 0)


def test_n_ecrit_que_dans_des_collections_pap(base: Any, csv_existant: Path) -> None:
    arbitrages = ArbitragesMongo(base)
    arbitrages.importer(csv_existant)
    arbitrages.ajouter(_theme("RD_9.001"))
    arbitrages.retirer({("ina", "RD_1.001")})

    assert base.list_collection_names() == ["pap_arbitrages"]


def test_l_import_et_l_export_laissent_une_ligne_de_log(
    base: Any, csv_existant: Path, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    logs.configurer()
    arbitrages = ArbitragesMongo(base)
    arbitrages.importer(csv_existant)
    arbitrages.importer(csv_existant)
    arbitrages.exporter(tmp_path / "export.csv")

    journal = messages(capfd.readouterr().err, "arbitrages")
    assert (
        f"import de {csv_existant} : 3 arbitrages lus, 3 ajoutés à pap_arbitrages"
        in journal
    )
    assert (
        f"import de {csv_existant} : 3 arbitrages lus, 0 ajouté à pap_arbitrages"
        in journal
    )
    assert (
        f"export de pap_arbitrages : 3 arbitrages → {tmp_path / 'export.csv'}"
        in journal
    )


# --- dans l'appli (l'atelier avec un dépôt Mongo) -----------------------------


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGO_URI", raising=False)
    cache = tmp_path / "cache"
    _cache_rempli(cache)
    return cache


def _atelier(cache: Path, sortie: Path, base: Any) -> Atelier:
    return Atelier(cache, sortie, depot=Depot(base))


THEATRE = {"emission_id": "1967-01-01", "sorte": "thème", "themes": ["théâtre"]}
ANNULATION = {"source": "wayback_podcast", "source_id": "ITEMA_23820437"}


def test_un_arbitrage_de_l_appli_survit_a_un_redemarrage_et_s_exporte(
    cache: Path, tmp_path: Path, base: Any
) -> None:
    sortie = tmp_path / "sortie"
    _atelier(cache, sortie, base).arbitrer(THEATRE)

    redemarre = _atelier(cache, sortie, base)

    [arbitrage] = redemarre.donnees()["arbitrages"]
    assert (arbitrage["source_id"], arbitrage["valeur"]) == (
        "ITEMA_23820437",
        "théâtre",
    )
    assert "1967-01-01" not in [e["id"] for e in redemarre.donnees()["emissions"]]
    ArbitragesMongo(base).exporter(sortie / "arbitrages.csv")
    [ligne] = lire_arbitrages(sortie / "arbitrages.csv")
    assert (ligne.source_id, ligne.themes) == ("ITEMA_23820437", {"théâtre"})


def test_avec_mongo_l_appli_n_ecrit_pas_arbitrages_csv(
    cache: Path, tmp_path: Path, base: Any
) -> None:
    sortie = tmp_path / "sortie"
    _atelier(cache, sortie, base).arbitrer(THEATRE)

    assert not (sortie / "arbitrages.csv").exists()


def test_avec_mongo_l_appli_ignore_arbitrages_csv(
    cache: Path, tmp_path: Path, base: Any
) -> None:
    """Mongo fait foi : un fichier non importé ne change pas la liste."""
    sortie = tmp_path / "sortie"
    sortie.mkdir()
    (sortie / "arbitrages.csv").write_text(
        "source,source_id,sorte,valeur,justification,date\n"
        "wayback_podcast,ITEMA_23820437,thème,théâtre,,2026-11-10\n",
        encoding="utf-8",
    )

    atelier = _atelier(cache, sortie, base)

    assert atelier.donnees()["arbitrages"] == []


def test_annuler_dans_l_appli_retire_l_arbitrage_de_mongo(
    cache: Path, tmp_path: Path, base: Any
) -> None:
    atelier = _atelier(cache, tmp_path / "sortie", base)
    atelier.arbitrer(THEATRE)

    atelier.annuler(ANNULATION)

    assert ArbitragesMongo(base).tous() == []


def test_l_appli_n_ecrit_que_dans_des_collections_pap(
    cache: Path, tmp_path: Path, base: Any
) -> None:
    atelier = _atelier(cache, tmp_path / "sortie", base)
    atelier.arbitrer(THEATRE)
    atelier.annuler(ANNULATION)
    atelier.arbitrer(THEATRE)

    assert all(c.startswith("pap_") for c in base.list_collection_names())


def test_l_arbitrage_et_l_annulation_laissent_une_ligne_de_log(
    cache: Path, tmp_path: Path, base: Any, capfd: pytest.CaptureFixture[str]
) -> None:
    logs.configurer()
    atelier = _atelier(cache, tmp_path / "sortie", base)
    atelier.arbitrer(THEATRE)
    atelier.annuler(ANNULATION)

    journal = messages(capfd.readouterr().err, "arbitrer")
    assert "arbitrage thème 1967-01-01 : théâtre (pap_arbitrages)" in journal
    assert (
        "annulation wayback_podcast:ITEMA_23820437 : 1 arbitrage retiré "
        "(pap_arbitrages)"
    ) in journal


def test_mongo_illisible_la_liste_se_construit_avec_le_fichier(
    cache: Path,
    tmp_path: Path,
    base: Any,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    logs.configurer()

    def injoignable(*_args: object, **_options: object) -> None:
        raise RuntimeError("nas923:27018: timed out")

    monkeypatch.setattr(ArbitragesMongo, "tous", injoignable)

    atelier = _atelier(cache, tmp_path / "sortie", base)

    assert atelier.nombre_emissions() > 0
    assert (
        f"pap_arbitrages illisible (RuntimeError) : liste construite avec "
        f"{tmp_path / 'sortie' / 'arbitrages.csv'}"
    ) in messages(capfd.readouterr().err, "arbitrer")


def test_le_demarrage_dit_d_ou_viennent_les_arbitrages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    base: Any = mongomock.MongoClient()["masque_et_la_plume"]
    ArbitragesMongo(base).ajouter(_theme("RD_9.001"))

    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd, Depot(base))

    assert "arbitrages : collection pap_arbitrages" in journal


def test_sans_mongo_le_demarrage_dit_que_les_arbitrages_sont_dans_le_fichier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    journal = _demarrer_la_commande(tmp_path, monkeypatch, capfd)

    assert f"arbitrages : fichier {tmp_path / 'sortie' / 'arbitrages.csv'}" in journal


# --- la commande ``lmelp-pap arbitrages`` ---------------------------------------


@pytest.fixture
def commande(
    base: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., int]:
    """``lmelp-pap arbitrages …`` sur la base mongomock."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "depot_depuis_env", lambda: Depot(base))
    return lambda *argv: cli.main(["arbitrages", *argv])


def test_la_commande_importe_puis_exporte_le_fichier(
    base: Any, commande: Callable[..., int], csv_existant: Path, tmp_path: Path
) -> None:
    exporte = tmp_path / "export.csv"

    assert commande("importer", "--fichier", str(csv_existant)) == 0
    assert commande("importer", "--fichier", str(csv_existant)) == 0
    assert commande("exporter", "--fichier", str(exporte)) == 0

    assert exporte.read_text(encoding="utf-8") == CSV


def test_la_commande_vise_par_defaut_arbitrages_csv_des_donnees(
    base: Any, commande: Callable[..., int], tmp_path: Path
) -> None:
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "processed" / "arbitrages.csv").write_text(
        CSV, encoding="utf-8"
    )

    assert commande("importer") == 0

    assert len(ArbitragesMongo(base).tous()) == 3


def test_la_commande_sans_mongo_echoue_en_le_disant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "depot_depuis_env", lambda: None)

    assert cli.main(["arbitrages", "exporter"]) == 1
    assert "MONGO_URI absent" in capfd.readouterr().err
