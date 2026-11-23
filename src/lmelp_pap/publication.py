"""La publication de la liste sur GitHub (ADR 0004).

L'appli du NAS garde un clone du dépôt (``Configuration.clone``). Publier y
copie les CSV de la liste et les décisions exportées dans ``data/processed/``,
les commite (``chore(data): publication depuis le NAS``), fait un
``pull --rebase`` puis pousse sur ``main``, jamais en force. Le push déclenche
``docs.yml``, qui reconstruit la page GitHub Pages.

Le clone reste d'une publication à l'autre. Un conflit au rebase (quelqu'un a
changé les mêmes lignes sur ``main``) refuse la publication et remet le clone
au distant : les CSV se régénèrent à chaque publication, la suivante repart
de ``main``. Un push en échec (réseau, branche protégée) laisse, lui, le
commit local, que la publication suivante pousse.
"""

import base64
import csv
import logging
import os
import re
import shutil
import subprocess
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from lmelp_pap import arbitrages, ecriture, notification
from lmelp_pap.maturite import COLONNES_QUALIFICATIONS, Enregistrement


log = logging.getLogger(__name__)

DISTANT = "https://github.com/castorfou/lmelp-pap.git"
MESSAGE = "chore(data): publication depuis le NAS"
DOSSIER = "data/processed"
AUTEUR = ("lmelp-pap (NAS)", "lmelp-pap@users.noreply.github.com")

# Les seuls fichiers publiés, avec leurs colonnes : la liste et les décisions.
# Une colonne de plus (un chemin audio, une donnée de l'API Radio France)
# refuse la publication.
PUBLIABLES: dict[str, list[str]] = {
    "emissions.csv": ecriture.COLONNES_EMISSIONS,
    "attestations.csv": ecriture.COLONNES_ATTESTATIONS,
    "enregistrements.csv": ecriture.COLONNES_ENREGISTREMENTS,
    "doutes.csv": ecriture.COLONNES_DOUTES,
    "arbitrages.csv": arbitrages.COLONNES,
    "qualifications.csv": COLONNES_QUALIFICATIONS,
}
# Ce qu'aucun fichier publié ne contient : les volumes du NAS.
TOUJOURS_PRIVES = ("/volume1/",)
# Un chemin absolu local (pas la fin d'une URL ni ``origin/main``) : il
# commence après un blanc, une parenthèse ou un guillemet.
CHEMIN_LOCAL = re.compile(r"(?<![^\s(\[\"'«])/[^\s()\[\]\"'«»,;]*")


class PublicationError(RuntimeError):
    """Une publication refusée : conflit au rebase, push rejeté, git en échec."""


@dataclass(frozen=True)
class Configuration:
    """Où publier : le clone local, le dépôt distant, sa branche, et le jeton
    GitHub (``contents:write`` sur le seul dépôt) pour le push."""

    clone: Path
    distant: str
    branche: str = "main"
    jeton: str | None = field(default=None, repr=False)

    @classmethod
    def depuis_env(cls, env: Mapping[str, str] | None = None) -> "Configuration | None":
        """La configuration de ``PAP_DEPOT_GIT`` (le clone, obligatoire : sans
        lui, pas de publication), ``PAP_DEPOT_URL`` (``DISTANT`` par défaut),
        ``PAP_DEPOT_BRANCHE`` (``main``) et ``GH_TOKEN`` (le jeton)."""
        env = os.environ if env is None else env
        if not (clone := env.get("PAP_DEPOT_GIT")):
            return None
        return cls(
            clone=Path(clone),
            distant=env.get("PAP_DEPOT_URL") or DISTANT,
            branche=env.get("PAP_DEPOT_BRANCHE") or "main",
            jeton=env.get("GH_TOKEN") or None,
        )


class Publication:
    """La publication des CSV de la liste dans le dépôt distant ; une à la
    fois."""

    def __init__(
        self,
        configuration: Configuration,
        *,
        prives: Iterable[Path] = (),
        notifier: Callable[..., bool] = notification.notifier,
    ):
        """``prives`` : les dossiers locaux (audios, cache…) dont aucun
        fichier publié ne doit porter le chemin ; ``notifier`` : la
        notification ntfy du résultat."""
        self.configuration = configuration
        self._notifier = notifier
        self.prives = (
            *TOUJOURS_PRIVES,
            *(str(p) for p in prives if p.is_absolute() and len(p.parts) > 1),
        )
        self._verrou = threading.Lock()

    def publier(self, fichiers: Mapping[str, Path], resume: str = "") -> dict[str, Any]:
        """Publie ``fichiers`` (nom dans ``data/processed/`` → fichier local) ;
        ``resume`` : ce qui change, en clair, pour le commit, le log et la
        notification.

        Rend ``statut`` : ``publiee`` (avec ``commit``, le sha poussé),
        ``rien`` (aucun changement, aucun commit) ou ``refusee`` (avec
        ``detail``). Chaque issue laisse sa ligne de log et sa notification
        ntfy (« rien à publier » en priorité basse)."""
        branche = self.configuration.branche
        with self._verrou:
            log.info(f"publication demandée vers {branche} : {resume or '-'}")
            try:
                resultat = self._publier(fichiers, resume)
            except PublicationError as erreur:
                return self.refuser(str(erreur))
        if resultat["statut"] == "rien":
            log.info("publication : rien à publier, aucun commit")
            self._notifier(
                "rien à publier",
                f"aucun changement par rapport à {branche}, aucun commit",
                priorite=2,
            )
            return resultat
        court = resultat["commit"][:7]
        log.info(f"publication : {court} poussé sur {branche} ({resume or '-'})")
        self._notifier(
            "liste publiée",
            f"{court} poussé sur {branche}" + (f" : {resume}" if resume else ""),
            tags=["books"],
        )
        return resultat

    def refuser(self, raison: str) -> dict[str, Any]:
        """Refuse la publication pour ``raison`` : ligne de log en erreur et
        alerte ntfy ; rend le résultat ``refusee``. ntfy est un service
        externe : l'alerte ne garde de chaque chemin local que son dernier
        nom, et jamais le jeton (le log local garde le chemin)."""
        log.error(f"publication refusée : {raison}")
        self._notifier(
            "publication refusée",
            sans_chemin(self._masquer(raison)),
            priorite=4,
            tags=["warning"],
        )
        return {"statut": "refusee", "detail": raison}

    def apercu(
        self,
        fichiers: Mapping[str, Path],
        enregistrements: Iterable[Enregistrement] = (),
    ) -> dict[str, Any]:
        """Ce que publier ``fichiers`` changerait sur le distant, avant de
        confirmer : ``emissions`` (identifiants ``ajoutees``, ``retirees``,
        ``modifiees``), ``arbitrages`` et ``qualifications`` (lignes
        ``ajoutes``, ``retires``), ``niveaux`` (par niveau, les
        ``enregistrements`` entrés dans un niveau depuis ``depuis``, la date
        de la dernière publication), ``fichiers`` changés, ``en_attente`` (les
        autres fichiers que les commits locaux, laissés par un push en échec,
        changent et que la publication pousserait), ``a_publier`` et
        ``resume`` en clair. Lève ``PublicationError`` si le distant est
        injoignable ou un fichier interdit."""
        with self._verrou:
            for nom, chemin in fichiers.items():
                self._controler(nom, chemin)
            self._preparer_clone()
            distants = {nom: self._distant(nom) for nom in fichiers}
            depuis = self._derniere_publication()
            en_attente = self._en_attente(fichiers)
        locaux = {
            nom: chemin.read_text(encoding="utf-8") for nom, chemin in fichiers.items()
        }
        changes = sorted(nom for nom in fichiers if locaux[nom] != distants[nom])
        emissions = _emissions(
            distants.get("emissions.csv", ""), locaux.get("emissions.csv", "")
        )
        decisions = {
            cle: _lignes(distants.get(nom, ""), locaux.get(nom, ""))
            for cle, nom in (
                ("arbitrages", "arbitrages.csv"),
                ("qualifications", "qualifications.csv"),
            )
        }
        niveaux = Counter(
            e.niveau for e in enregistrements if _change_depuis(e, depuis)
        )
        apercu = {
            "emissions": emissions,
            **decisions,
            "niveaux": dict(sorted(niveaux.items())),
            "depuis": depuis.isoformat() if depuis else None,
            "fichiers": changes,
            "en_attente": en_attente,
            "a_publier": bool(changes or en_attente),
        }
        apercu["resume"] = _resume(apercu)
        return apercu

    def _distant(self, nom: str) -> str:
        """Le fichier ``nom`` de ``data/processed/`` sur le distant, ou rien."""
        fait = self._executer(
            ("show", f"origin/{self.configuration.branche}:{DOSSIER}/{nom}"),
            self.configuration.clone,
        )
        return fait.stdout if fait.returncode == 0 else ""

    def _en_attente(self, fichiers: Mapping[str, Path]) -> list[str]:
        """Les chemins que les commits locaux du clone changent par rapport au
        distant, hors ``fichiers`` (que la publication réécrit de toute
        façon) : ce qu'un push en échec a laissé à pousser."""
        reecrits = {f"{DOSSIER}/{nom}" for nom in fichiers}
        changes = self._git_lignes(
            "diff", "--name-only", f"origin/{self.configuration.branche}", "HEAD"
        )
        return sorted(set(changes) - reecrits)

    def _derniere_publication(self) -> datetime | None:
        """La date du dernier commit du distant sur ``data/processed/``."""
        branche = self.configuration.branche
        date = self._git(
            "log", "-1", "--format=%cI", f"origin/{branche}", "--", DOSSIER
        )
        return datetime.fromisoformat(date) if date else None

    def _publier(self, fichiers: Mapping[str, Path], resume: str) -> dict[str, Any]:
        for nom, chemin in fichiers.items():
            self._controler(nom, chemin)
        self._preparer_clone()
        cible = self.configuration.clone / DOSSIER
        cible.mkdir(parents=True, exist_ok=True)
        for nom, chemin in fichiers.items():
            shutil.copyfile(chemin, cible / nom)
        self._git("add", "-f", "--", *(f"{DOSSIER}/{nom}" for nom in fichiers))
        change = not self._git_ok("diff", "--cached", "--quiet")
        if not change and not self._en_avance():
            return {"statut": "rien"}
        if change:
            corps = ["-m", resume] if resume else []
            self._git("commit", "-q", "-m", MESSAGE, *corps)
        self._rebaser()
        if not self._en_avance():  # le distant avait déjà ces changements
            return {"statut": "rien"}
        self._git("push", "-q", "origin", f"HEAD:{self.configuration.branche}")
        return {"statut": "publiee", "commit": self._git("rev-parse", "HEAD")}

    def _controler(self, nom: str, chemin: Path) -> None:
        """Refuse un fichier hors de ``PUBLIABLES``, aux colonnes inattendues,
        ou qui porte un chemin privé."""
        if nom not in PUBLIABLES:
            raise PublicationError(f"{nom} n'est pas un fichier publiable")
        texte = chemin.read_text(encoding="utf-8")
        entete = next(csv.reader(texte.splitlines()[:1]), [])
        if entete != PUBLIABLES[nom]:
            raise PublicationError(
                f"{nom} : colonnes inattendues {entete} (attendu : {PUBLIABLES[nom]})"
            )
        for prive in self.prives:
            if prive in texte:
                raise PublicationError(f"{nom} porte un chemin privé ({prive})")

    def _preparer_clone(self) -> None:
        """Clone le dépôt s'il n'est pas là ; sinon remet le clone au propre
        (rebase interrompu abandonné, fichiers modifiés rétablis, ses commits
        gardés) et lit le distant."""
        clone = self.configuration.clone
        if not (clone / ".git").exists():
            clone.parent.mkdir(parents=True, exist_ok=True)
            self._commande(
                "clone",
                "-q",
                "--branch",
                self.configuration.branche,
                self.configuration.distant,
                str(clone),
                dans=None,
            )
            return
        if (clone / ".git" / "rebase-merge").exists() or (
            clone / ".git" / "rebase-apply"
        ).exists():
            self._git_ok("rebase", "--abort")
        self._git("checkout", "-q", "-f", self.configuration.branche)
        self._git("reset", "-q", "--hard")
        self._git("fetch", "-q", "origin", self.configuration.branche)

    def _rebaser(self) -> None:
        """``pull --rebase`` sur le distant ; un conflit l'abandonne, remet le
        clone au distant (ses CSV se régénèrent à chaque publication : la
        suivante repart de là) et refuse la publication."""
        branche = self.configuration.branche
        if self._git_ok("pull", "-q", "--rebase", "origin", branche):
            return
        conflits = self._git_lignes("diff", "--name-only", "--diff-filter=U")
        self._git_ok("rebase", "--abort")
        self._git_ok("reset", "-q", "--hard", f"origin/{branche}")
        raise PublicationError(
            f"conflit au rebase sur {branche} : {', '.join(conflits) or '?'} "
            "(rien n'est poussé ; le clone est remis au distant, la prochaine "
            "publication repart de là)"
        )

    def _en_avance(self) -> bool:
        """Le clone porte des commits que le distant n'a pas."""
        branche = self.configuration.branche
        return self._git("rev-list", "--count", f"origin/{branche}..HEAD") != "0"

    def _git(self, *args: str) -> str:
        """Une commande git dans le clone ; rend sa sortie, ou lève
        ``PublicationError`` avec son erreur."""
        return self._commande(*args, dans=self.configuration.clone)

    def _git_ok(self, *args: str) -> bool:
        """Une commande git dans le clone ; vrai si elle réussit."""
        return self._executer(args, self.configuration.clone).returncode == 0

    def _git_lignes(self, *args: str) -> list[str]:
        """Les lignes de sortie d'une commande git dans le clone."""
        return self._executer(args, self.configuration.clone).stdout.split()

    def _commande(self, *args: str, dans: Path | None) -> str:
        fait = self._executer(args, dans)
        if fait.returncode != 0:
            erreur = self._masquer((fait.stderr or fait.stdout).strip())
            raise PublicationError(f"git {args[0]} en échec : {erreur}")
        return fait.stdout.strip()

    def _executer(
        self, args: tuple[str, ...], dans: Path | None
    ) -> subprocess.CompletedProcess[str]:
        commande = ["git", *(["-C", str(dans)] if dans else []), *args]
        return subprocess.run(
            commande,
            check=False,
            capture_output=True,
            text=True,
            env=self._environnement(),
        )

    def _environnement(self) -> dict[str, str]:
        """L'environnement de git : l'auteur des commits, jamais d'invite, et
        le jeton dans un en-tête HTTP passé par l'environnement (rien dans
        ``.git/config``, rien sur la ligne de commande)."""
        nom, courriel = AUTEUR
        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": nom,
            "GIT_AUTHOR_EMAIL": courriel,
            "GIT_COMMITTER_NAME": nom,
            "GIT_COMMITTER_EMAIL": courriel,
        }
        if self.configuration.jeton:
            identifiants = base64.b64encode(
                f"x-access-token:{self.configuration.jeton}".encode()
            ).decode()
            env |= {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Basic {identifiants}",
            }
        return env

    def _masquer(self, texte: str) -> str:
        """Le texte sans le jeton."""
        jeton = self.configuration.jeton
        return texte.replace(jeton, "***") if jeton else texte


def sans_chemin(texte: str) -> str:
    """``texte`` où chaque chemin absolu local se réduit à son dernier nom :
    « /data/processed/arbitrages.csv » devient « arbitrages.csv »."""
    return CHEMIN_LOCAL.sub(lambda m: PurePosixPath(m[0]).name or "…", texte)


def _rangs(texte: str) -> list[list[str]]:
    """Les lignes d'un CSV, sans l'en-tête."""
    return list(csv.reader(texte.splitlines()))[1:]


def _emissions(avant: str, apres: str) -> dict[str, list[str]]:
    """Les émissions ajoutées, retirées et modifiées, par identifiant."""
    a = {r[0]: r for r in _rangs(avant) if r}
    b = {r[0]: r for r in _rangs(apres) if r}
    return {
        "ajoutees": sorted(b.keys() - a.keys()),
        "retirees": sorted(a.keys() - b.keys()),
        "modifiees": sorted(i for i in a.keys() & b.keys() if a[i] != b[i]),
    }


def _lignes(avant: str, apres: str) -> dict[str, int]:
    """Les lignes ajoutées et retirées d'un fichier de décisions."""
    a = Counter(map(tuple, _rangs(avant)))
    b = Counter(map(tuple, _rangs(apres)))
    return {"ajoutes": sum((b - a).values()), "retires": sum((a - b).values())}


def _change_depuis(enregistrement: Enregistrement, depuis: datetime | None) -> bool:
    """L'enregistrement est entré dans un niveau après ``depuis``."""
    if depuis is None:
        return bool(enregistrement.entrees)
    return any(
        (d if d.tzinfo else d.replace(tzinfo=UTC)) > depuis
        for d in enregistrement.entrees.values()
    )


def _accorder(n: int, singulier: str, pluriel: str) -> str:
    """« 1 arbitrage ajouté », « 2 qualifications ajoutées » : le singulier
    jusqu'à 1, le pluriel au-delà."""
    return f"{n} {singulier if n <= 1 else pluriel}"


def _resume(apercu: dict[str, Any]) -> str:
    """L'aperçu en une phrase, pour la confirmation, le commit et ntfy."""
    morceaux = []
    e = apercu["emissions"]
    if n := sum(len(v) for v in e.values()):
        detail = ", ".join(
            _accorder(len(e[cle]), mot, mot + "s")
            for cle, mot in (
                ("ajoutees", "ajoutée"),
                ("retirees", "retirée"),
                ("modifiees", "modifiée"),
            )
            if e[cle]
        )
        morceaux.append(
            f"{_accorder(n, 'émission changée', 'émissions changées')} ({detail})"
        )
    # l'accord du participe suit le genre du nom : « qualifications ajoutées »
    for cle, nom, e_ in (
        ("arbitrages", "arbitrage", ""),
        ("qualifications", "qualification", "e"),
    ):
        d = apercu[cle]
        for champ, participe in (("ajoutes", "ajouté"), ("retires", "retiré")):
            if d[champ]:
                accord = participe + e_
                morceaux.append(
                    _accorder(d[champ], f"{nom} {accord}", f"{nom}s {accord}s")
                )
    if n := sum(apercu["niveaux"].values()):
        detail = ", ".join(f"{k} {v}" for k, v in apercu["niveaux"].items())
        quoi = _accorder(n, "enregistrement a", "enregistrements ont")
        morceaux.append(f"{quoi} changé de niveau ({detail})")
    if apercu["en_attente"]:
        noms = ", ".join(c.rsplit("/", 1)[-1] for c in apercu["en_attente"])
        morceaux.append(f"commit local en attente de push ({noms})")
    if morceaux:
        return ", ".join(morceaux)
    if apercu["fichiers"]:
        return "fichiers changés : " + ", ".join(apercu["fichiers"])
    return "aucun changement"
