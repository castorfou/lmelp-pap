"""Lecture des anciennes listes d'émissions de France Inter archivées."""

from datetime import date
from pathlib import Path

from lmelp_pap.sources.anciennes_listes import lire_liste


FIXTURES = Path(__file__).parent / "fixtures" / "anciennes_listes"


def test_la_liste_annuelle_donne_la_date_et_le_theme_de_chaque_dimanche() -> None:
    page = (FIXTURES / "archives-2006.html").read_text(encoding="latin-1")

    attestations = {a.date: a for a in lire_liste(page)}

    livres = attestations[date(2006, 12, 17)]
    assert livres.source == "anciennes_listes"
    assert livres.source_id == "em-49171"
    assert livres.themes == frozenset({"livres"})
    assert livres.titre == "Livres"
    assert attestations[date(2006, 12, 24)].themes == frozenset({"cinéma"})


def test_un_dimanche_sans_emission_n_atteste_rien() -> None:
    page = (FIXTURES / "archives-2006.html").read_text(encoding="latin-1")

    attestations = lire_liste(page)

    assert len(attestations) == 51  # 52 dimanches, dont un « Pas de masque »
    assert all(a.titre != "Pas de masque et la plume" for a in attestations)


def test_les_libelles_speciaux_ont_un_theme() -> None:
    page = (FIXTURES / "archives-2006.html").read_text(encoding="latin-1")

    themes = {a.titre: a.themes for a in lire_liste(page)}

    assert themes["Festival d'Avignon"] == frozenset({"théâtre"})
    assert themes["Festival de Cannes"] == frozenset({"cinéma"})
    assert themes["Le 16e Prix des auditeurs du Masque et la Plume"] == frozenset(
        {"livres"}
    )


def test_la_liste_mensuelle_donne_date_theme_et_oeuvres_critiquees() -> None:
    page = (FIXTURES / "archives-diffusions-2011-03.html").read_text(encoding="utf-8")

    attestations = {a.date: a for a in lire_liste(page)}

    assert sorted(attestations) == [
        date(2011, 3, 6),
        date(2011, 3, 13),
        date(2011, 3, 20),
        date(2011, 3, 27),
    ]
    livres = attestations[date(2011, 3, 13)]
    assert livres.source_id == "em-100998"
    assert livres.themes == frozenset({"livres"})
    assert livres.description == (
        "Les livres : Tu verras - La vie très privée de Mr Sim - "
        "L’écologie en bas de chez moi - Un homme de passage - "
        "Fontenoy ne reviendra plus"
    )
    assert attestations[date(2011, 3, 27)].themes == frozenset({"théâtre"})


def _ligne(jour: str, identifiant: str, libelle: str) -> str:
    return f'<li><strong>{jour}</strong> ><a href="index.php?id={identifiant}">{libelle}</a></li>'


def test_aucune_emission_n_atteste_rien() -> None:
    page = _ligne("06/08/2006", "1", "Aucune émission")

    assert lire_liste(page) == []


def test_le_festival_d_aix_est_un_theme_opera() -> None:
    page = _ligne("16/07/2006", "2", "Festival d'Aix-en-Provence")

    (attestation,) = lire_liste(page)

    assert attestation.themes == frozenset({"opéra"})


def test_une_emission_presente_dans_deux_listes_n_est_attestee_qu_une_fois(
    tmp_path: Path,
) -> None:
    from lmelp_pap.collecte import lire_anciennes_listes

    (tmp_path / "archives.php.html").write_text(
        _ligne("17/12/2006", "49171", "Livres"), encoding="utf-8"
    )
    (tmp_path / "archives.php_annee_2006.html").write_text(
        _ligne("17/12/2006", "49171", "Livres")
        + _ligne("24/12/2006", "50272", "Cinéma"),
        encoding="utf-8",
    )

    attestations = lire_anciennes_listes(tmp_path)

    assert sorted((a.date, a.source_id) for a in attestations) == [
        (date(2006, 12, 17), "em-49171"),
        (date(2006, 12, 24), "em-50272"),
    ]
