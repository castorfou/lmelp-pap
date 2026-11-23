"""La publication de la liste sur GitHub (``lmelp_pap.publication``).

Le dépôt distant est un dépôt nu temporaire : aucun test ne touche le réseau
ni le vrai dépôt GitHub.
"""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from lmelp_pap.maturite import Enregistrement
from lmelp_pap.publication import Configuration, Publication
from tests.test_logs import lignes, messages


EMISSIONS = (
    "id,date,themes,titre,description,animateur,chaine,heure,duree,arbitrage,"
    "justification_arbitrage\n"
)
ARBITRAGES = "source,source_id,sorte,valeur,justification,date\n"


def git(dossier: Path, *args: str) -> str:
    """Une commande git dans ``dossier`` ; rend sa sortie."""
    return subprocess.run(
        ["git", "-C", str(dossier), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _identite(dossier: Path) -> None:
    git(dossier, "config", "user.name", "test")
    git(dossier, "config", "user.email", "test@example.org")


@pytest.fixture
def distant(tmp_path: Path) -> Path:
    """Un dépôt nu, ``main`` avec du code et les CSV de la liste."""
    nu = tmp_path / "distant.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(nu))
    poste = tmp_path / "poste"
    git(tmp_path, "clone", str(nu), str(poste))
    _identite(poste)
    (poste / "README.md").write_text("pap\n")
    donnees = poste / "data" / "processed"
    donnees.mkdir(parents=True)
    (donnees / "emissions.csv").write_text(
        EMISSIONS + "1956-01-22,1956-01-22" + "," * 9 + "\n"
    )
    (donnees / "arbitrages.csv").write_text(ARBITRAGES)
    git(poste, "add", ".")
    git(poste, "commit", "-m", "init")
    git(poste, "push", "origin", "main")
    return nu


@pytest.fixture
def poste(distant: Path, tmp_path: Path) -> Path:
    """Le clone d'un développeur, qui pousse aussi sur ``main``."""
    return tmp_path / "poste"


@pytest.fixture
def sortie(tmp_path: Path) -> Path:
    """Les CSV de la liste, tels que l'appli les écrit."""
    dossier = tmp_path / "processed"
    dossier.mkdir()
    (dossier / "emissions.csv").write_text(
        EMISSIONS + "1956-01-22,1956-01-22" + "," * 9 + "\n"
    )
    (dossier / "arbitrages.csv").write_text(
        ARBITRAGES + "ina,RD_1,thème,théâtre,titre explicite,2026-11-10\n"
    )
    return dossier


def _publication(distant: Path, tmp_path: Path, **kwargs: Any) -> Publication:
    """La publication vers ``distant`` ; jamais de vraie notification."""
    kwargs.setdefault("notifier", Notifications())
    return Publication(
        Configuration(clone=tmp_path / "depot", distant=str(distant)), **kwargs
    )


def _fichiers(sortie: Path) -> dict[str, Path]:
    return {p.name: p for p in sortie.glob("*.csv")}


def _distant(distant: Path, chemin: str) -> str:
    return git(distant, "show", f"main:{chemin}")


def test_publier_pousse_les_csv_changes_sur_main(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    resultat = _publication(distant, tmp_path).publier(_fichiers(sortie))

    assert resultat["statut"] == "publiee"
    assert "RD_1" in _distant(distant, "data/processed/arbitrages.csv")
    assert (
        git(distant, "log", "-1", "--format=%s", "main")
        == "chore(data): publication depuis le NAS"
    )
    assert resultat["commit"] == git(distant, "rev-parse", "main")


def test_sans_changement_publier_ne_cree_pas_de_commit_vide(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))
    avant = git(distant, "rev-parse", "main")

    resultat = publication.publier(_fichiers(sortie))

    assert resultat["statut"] == "rien"
    assert git(distant, "rev-parse", "main") == avant


def test_le_commit_est_signe_du_nas_et_le_jeton_ne_reste_pas_dans_le_clone(
    distant: Path, sortie: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # le conteneur n'a pas de configuration git globale
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("HOME", str(tmp_path))
    configuration = Configuration(
        clone=tmp_path / "depot", distant=str(distant), jeton="github_pat_secret"
    )

    resultat = Publication(configuration, notifier=Notifications()).publier(
        _fichiers(sortie)
    )

    assert resultat["statut"] == "publiee"
    assert git(distant, "log", "-1", "--format=%an", "main") == "lmelp-pap (NAS)"
    clone = tmp_path / "depot" / ".git"
    assert not any(
        "github_pat_secret" in f.read_text(errors="replace")
        for f in clone.rglob("*")
        if f.is_file() and f.suffix != ".pack"
    )


def _pousser_depuis_le_poste(poste: Path, chemin: str, contenu: str) -> str:
    """Un développeur pousse un commit sur ``main`` ; rend son sha."""
    git(poste, "pull", "-q", "origin", "main")
    (poste / chemin).write_text(contenu)
    git(poste, "commit", "-qam", f"modifie {chemin}")
    git(poste, "push", "-q", "origin", "main")
    return git(poste, "rev-parse", "HEAD")


def test_publier_rebase_sur_le_code_pousse_entre_deux_publications(
    distant: Path, poste: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))
    code = _pousser_depuis_le_poste(poste, "README.md", "pap, nouvelle doc\n")
    (sortie / "arbitrages.csv").write_text(
        ARBITRAGES + "ina,RD_2,existence,n'existe pas,,2026-11-11\n"
    )

    resultat = publication.publier(_fichiers(sortie))

    assert resultat["statut"] == "publiee"
    assert git(distant, "rev-parse", "main~1") == code
    assert "RD_2" in _distant(distant, "data/processed/arbitrages.csv")
    assert _distant(distant, "README.md") == "pap, nouvelle doc"


def test_un_conflit_au_rebase_refuse_la_publication_sans_toucher_main(
    distant: Path, poste: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))
    avant = _pousser_depuis_le_poste(
        poste,
        "data/processed/arbitrages.csv",
        ARBITRAGES + "ina,RD_9,thème,livres,à la main,2026-11-12\n",
    )
    (sortie / "arbitrages.csv").write_text(
        ARBITRAGES + "ina,RD_2,existence,n'existe pas,,2026-11-11\n"
    )

    resultat = publication.publier(_fichiers(sortie))

    assert resultat["statut"] == "refusee"
    assert "data/processed/arbitrages.csv" in resultat["detail"]
    assert git(distant, "rev-parse", "main") == avant
    clone = tmp_path / "depot"
    assert not (clone / ".git" / "rebase-merge").exists()
    assert not (clone / ".git" / "rebase-apply").exists()


def test_apres_un_conflit_le_clone_revient_au_distant_et_la_suivante_passe(
    distant: Path, poste: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))
    avant = _pousser_depuis_le_poste(
        poste,
        "data/processed/arbitrages.csv",
        ARBITRAGES + "ina,RD_9,thème,livres,à la main,2026-11-12\n",
    )
    (sortie / "arbitrages.csv").write_text(
        ARBITRAGES + "ina,RD_2,existence,n'existe pas,,2026-11-11\n"
    )
    assert publication.publier(_fichiers(sortie))["statut"] == "refusee"
    # le clone ne garde pas le commit en conflit : il est au distant
    assert git(tmp_path / "depot", "rev-parse", "HEAD") == avant

    resultat = publication.publier(_fichiers(sortie))

    # les CSV se régénèrent à chaque publication : la suivante repart du
    # distant et passe
    assert resultat["statut"] == "publiee"
    assert git(distant, "rev-parse", "main~1") == avant
    assert "RD_2" in _distant(distant, "data/processed/arbitrages.csv")


@pytest.mark.parametrize(
    ("nom", "contenu", "raison"),
    [
        ("1987-03-01.mp3", "ID3", "1987-03-01.mp3"),
        ("notes.csv", "a,b\n", "notes.csv"),
        (
            "emissions.csv",
            EMISSIONS.strip() + ",resume\n",
            "colonnes",
        ),
        (
            "arbitrages.csv",
            ARBITRAGES + "ina,RD_1,thème,livres,/volume1/docker/lmelp/pap/x,2026\n",
            "/volume1/",
        ),
        (
            "arbitrages.csv",
            ARBITRAGES + "ina,RD_1,thème,livres,vu dans /srv/audios/1987,2026\n",
            "/srv/audios",
        ),
    ],
)
def test_ne_publie_ni_audio_ni_chemin_du_nas_ni_colonne_inconnue(
    distant: Path, sortie: Path, tmp_path: Path, nom: str, contenu: str, raison: str
) -> None:
    (sortie / nom).write_text(contenu)
    avant = git(distant, "rev-parse", "main")
    publication = _publication(
        distant, tmp_path, prives=[Path("/srv/audios"), Path("/srv/cache")]
    )

    resultat = publication.publier({**_fichiers(sortie), nom: sortie / nom})

    assert resultat["statut"] == "refusee"
    assert raison in resultat["detail"]
    assert git(distant, "rev-parse", "main") == avant


def test_l_alerte_ntfy_d_un_refus_ne_porte_aucun_chemin_local(
    distant: Path, sortie: Path, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """ntfy est un service externe : ni chemin du NAS ni jeton dans l'alerte ;
    la ligne de log locale garde le détail."""
    (sortie / "arbitrages.csv").write_text(
        ARBITRAGES + "ina,RD_1,thème,livres,vu dans /srv/audios/1987,2026\n"
    )
    notifications = Notifications()
    publication = _publication(
        distant, tmp_path, prives=[Path("/srv/audios")], notifier=notifications
    )
    capfd.readouterr()

    publication.publier(_fichiers(sortie))

    (alerte,) = notifications.recues
    assert "chemin privé" in str(alerte["message"])
    assert "/srv" not in str(alerte["message"])
    assert any(
        "/srv/audios" in m for m in messages(capfd.readouterr().err, "publication")
    )


def test_l_alerte_ntfy_d_un_depot_injoignable_ne_porte_ni_chemin_ni_jeton(
    tmp_path: Path,
) -> None:
    notifications = Notifications()
    publication = Publication(
        Configuration(
            clone=tmp_path / "depot",
            distant=str(tmp_path / "absent.git"),
            jeton="github_pat_secret",
        ),
        notifier=notifications,
    )
    sortie = tmp_path / "processed"
    sortie.mkdir()
    (sortie / "arbitrages.csv").write_text(ARBITRAGES)

    resultat = publication.publier(_fichiers(sortie))

    assert resultat["statut"] == "refusee"
    (alerte,) = notifications.recues
    message = str(alerte["message"])
    assert "git clone en échec" in message
    assert str(tmp_path) not in message and "github_pat_secret" not in message
    assert "absent.git" in message  # le nom reste, pour comprendre


def test_la_configuration_vient_de_l_environnement() -> None:
    env = {"PAP_DEPOT_GIT": "/data/depot", "GH_TOKEN": "github_pat_x"}

    configuration = Configuration.depuis_env(env)

    assert configuration == Configuration(
        clone=Path("/data/depot"),
        distant="https://github.com/castorfou/lmelp-pap.git",
        branche="main",
        jeton="github_pat_x",
    )
    assert Configuration.depuis_env(
        {**env, "PAP_DEPOT_URL": "file:///tmp/x.git", "PAP_DEPOT_BRANCHE": "essai"}
    ) == Configuration(
        clone=Path("/data/depot"),
        distant="file:///tmp/x.git",
        branche="essai",
        jeton="github_pat_x",
    )


def test_sans_clone_configure_pas_de_publication() -> None:
    # le devcontainer ne publie pas, même avec le GH_TOKEN de gh
    assert Configuration.depuis_env({"GH_TOKEN": "github_pat_x"}) is None


def test_le_jeton_n_apparait_pas_dans_la_configuration_affichee() -> None:
    configuration = Configuration(
        clone=Path("/d"), distant="https://x", jeton="github_pat_secret"
    )

    assert "github_pat_secret" not in repr(configuration)


def test_l_image_installe_git_et_active_la_publication() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text()

    assert " git " in dockerfile
    assert "PAP_DEPOT_GIT=/data/depot" in dockerfile


def _ligne_emission(jour: str, titre: str = "") -> str:
    return f"{jour},{jour},livres,{titre}" + "," * 7 + "\n"


def test_l_apercu_resume_ce_que_la_publication_changera(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    (sortie / "emissions.csv").write_text(
        EMISSIONS + _ligne_emission("1956-01-22") + _ligne_emission("1957-02-03")
    )
    (sortie / "arbitrages.csv").write_text(
        ARBITRAGES + "ina,RD_1,thème,théâtre,titre explicite,2026-11-10\n"
    )
    publication.publier(_fichiers(sortie))
    (sortie / "emissions.csv").write_text(
        EMISSIONS
        + _ligne_emission("1956-01-22", "Nouveau titre")
        + _ligne_emission("1958-04-05")
    )
    (sortie / "arbitrages.csv").write_text(
        ARBITRAGES
        + "ina,RD_2,existence,n'existe pas,,2026-11-11\n"
        + "ina,RD_3,thème,livres,,2026-11-11\n"
    )

    apercu = publication.apercu(_fichiers(sortie))

    assert apercu["a_publier"] is True
    assert apercu["emissions"] == {
        "ajoutees": ["1958-04-05"],
        "retirees": ["1957-02-03"],
        "modifiees": ["1956-01-22"],
    }
    assert apercu["arbitrages"] == {"ajoutes": 2, "retires": 1}
    assert apercu["fichiers"] == ["arbitrages.csv", "emissions.csv"]
    assert "3 émissions changées" in apercu["resume"]
    assert "2 arbitrages ajoutés" in apercu["resume"]


def test_le_resume_accorde_les_qualifications_au_feminin(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    entete = "emission_id,enregistrement,verdict,motif,date\n"
    (sortie / "qualifications.csv").write_text(
        entete + "1956-01-22,https://a/1.mp3,bon,,2026-11-10\n"
    )
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))
    (sortie / "qualifications.csv").write_text(
        entete
        + "1956-01-22,https://a/2.mp3,bon,,2026-11-11\n"
        + "1956-01-22,https://a/3.mp3,bon,,2026-11-11\n"
    )

    resume = publication.apercu(_fichiers(sortie))["resume"]

    assert "2 qualifications ajoutées" in resume
    assert "1 qualification retirée" in resume


def test_l_apercu_sans_changement_n_a_rien_a_publier(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))

    apercu = publication.apercu(_fichiers(sortie))

    assert apercu["a_publier"] is False
    assert apercu["fichiers"] == []
    assert apercu["resume"] == "aucun changement"


def _refuser_les_push(distant: Path) -> Path:
    crochet = distant / "hooks" / "pre-receive"
    crochet.write_text("#!/bin/sh\necho 'branche protégée' >&2\nexit 1\n")
    crochet.chmod(0o755)
    return crochet


def test_l_apercu_compte_le_commit_local_qu_un_push_en_echec_a_laisse(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    crochet = _refuser_les_push(distant)
    assert publication.publier(_fichiers(sortie))["statut"] == "refusee"
    crochet.unlink()
    # emissions.csv est déjà sur le distant ; le commit local porte, lui,
    # l'arbitrage RD_1
    seulement = {"emissions.csv": sortie / "emissions.csv"}

    apercu = publication.apercu(seulement)

    assert apercu["a_publier"] is True
    assert apercu["en_attente"] == ["data/processed/arbitrages.csv"]
    assert "en attente" in apercu["resume"]
    assert publication.publier(seulement)["statut"] == "publiee"
    assert "RD_1" in _distant(distant, "data/processed/arbitrages.csv")


def test_l_apercu_compte_les_enregistrements_qui_ont_change_de_niveau(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    publication = _publication(distant, tmp_path)
    publication.publier(_fichiers(sortie))
    derniere = datetime.fromisoformat(git(distant, "log", "-1", "--format=%cI", "main"))
    avant, apres = derniere - timedelta(days=3), derniere + timedelta(hours=1)
    enregistrements = [
        Enregistrement(
            "u1",
            "1987-01-04",
            "radiofrance",
            "valide",
            {"telechargeable": avant, "valide": apres},
        ),
        Enregistrement(
            "u2", "1987-01-11", "radiofrance", "qualifie", {"qualifie": apres}
        ),
        Enregistrement(
            "u3", "1987-01-18", "radiofrance", "rapatrie", {"rapatrie": avant}
        ),
    ]

    apercu = publication.apercu(_fichiers(sortie), enregistrements=enregistrements)

    assert apercu["niveaux"] == {"qualifie": 1, "valide": 1}
    assert apercu["depuis"] == derniere.isoformat()
    assert "2 enregistrements ont changé de niveau" in apercu["resume"]


class Notifications:
    """Un faux ``notifier`` : garde les notifications demandées."""

    def __init__(self) -> None:
        self.recues: list[dict[str, object]] = []

    def __call__(self, titre: str, message: str, **options: object) -> bool:
        self.recues.append({"titre": titre, "message": message, **options})
        return True


def test_une_publication_reussie_notifie_et_se_logue(
    distant: Path, sortie: Path, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    notifications = Notifications()

    resultat = _publication(distant, tmp_path, notifier=notifications).publier(
        _fichiers(sortie), resume="1 arbitrage"
    )

    court = resultat["commit"][:7]
    (recue,) = notifications.recues
    assert recue["titre"] == "liste publiée"
    assert court in str(recue["message"]) and "1 arbitrage" in str(recue["message"])
    assert any(
        court in m and "poussé sur main" in m and "1 arbitrage" in m
        for m in messages(capfd.readouterr().err, "publication")
    )


def test_un_refus_alerte_par_ntfy_et_se_logue_en_erreur(
    distant: Path,
    poste: Path,
    sortie: Path,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    notifications = Notifications()
    publication = _publication(distant, tmp_path, notifier=notifications)
    publication.publier(_fichiers(sortie))
    _pousser_depuis_le_poste(
        poste,
        "data/processed/arbitrages.csv",
        ARBITRAGES + "ina,RD_9,thème,livres,à la main,2026-11-12\n",
    )
    (sortie / "arbitrages.csv").write_text(ARBITRAGES)
    capfd.readouterr()

    publication.publier(_fichiers(sortie))

    alerte = notifications.recues[-1]
    assert alerte["titre"] == "publication refusée"
    assert alerte["priorite"] == 4
    assert "conflit" in str(alerte["message"])
    assert any(
        niveau == "ERROR" and module == "publication" and "conflit" in m
        for niveau, module, m in lignes(capfd.readouterr().err)
    )


def test_rien_a_publier_notifie_en_priorite_basse_et_se_logue(
    distant: Path, sortie: Path, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    notifications = Notifications()
    publication = _publication(distant, tmp_path, notifier=notifications)
    publication.publier(_fichiers(sortie))
    notifications.recues.clear()

    publication.publier(_fichiers(sortie))

    (recue,) = notifications.recues
    assert recue["titre"] == "rien à publier"
    assert recue["priorite"] == 2
    assert any(
        "rien à publier" in m for m in messages(capfd.readouterr().err, "publication")
    )


def test_un_push_refuse_par_le_distant_refuse_la_publication(
    distant: Path, sortie: Path, tmp_path: Path
) -> None:
    crochet = distant / "hooks" / "pre-receive"
    crochet.write_text("#!/bin/sh\necho 'branche protégée' >&2\nexit 1\n")
    crochet.chmod(0o755)
    avant = git(distant, "rev-parse", "main")

    resultat = _publication(distant, tmp_path).publier(_fichiers(sortie))

    assert resultat["statut"] == "refusee"
    assert "branche protégée" in resultat["detail"]
    assert git(distant, "rev-parse", "main") == avant
