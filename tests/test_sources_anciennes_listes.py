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
