"""Le script de démarrage et d'arrêt du serveur local (``scripts/start-dev.sh``).

Les tests lancent le vrai script sur un port libre, avec un cache, un dossier
de données et un fichier ``.dev-ports.json`` temporaires, sans Mongo.
"""

import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest


RACINE = Path(__file__).resolve().parents[1]
SCRIPT = RACINE / "scripts" / "start-dev.sh"


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _plage_libre(taille: int = 3) -> int:
    """Le premier port d'une plage de ``taille`` ports consécutifs libres."""
    while True:
        debut = _port_libre()
        try:
            for port in range(debut, debut + taille):
                with socket.socket() as s:
                    s.bind(("127.0.0.1", port))
        except OSError:
            continue
        return debut


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "cache").mkdir()
    (tmp_path / "donnees").mkdir()
    return {
        **os.environ,
        "PAP_PORT": str(_port_libre()),
        "PAP_DEV_PORTS": str(tmp_path / ".dev-ports.json"),
        "PAP_CACHE": str(tmp_path / "cache"),
        "PAP_DONNEES": str(tmp_path / "donnees"),
        "PAP_AUDIOS": str(tmp_path / "audios"),
        "PAP_AUDIOS_LMELP": str(tmp_path / "audios-lmelp"),
        "MONGO_URI": "",
    }


def _script(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        check=False,
        env=env,
        cwd=RACINE,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _demarrer(env: dict[str, str]) -> subprocess.Popen[str]:
    """Lance le script au premier plan et attend que le fichier soit écrit."""
    processus = subprocess.Popen(
        [str(SCRIPT)],
        env=env,
        cwd=RACINE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    fichier = Path(env["PAP_DEV_PORTS"])
    limite = time.monotonic() + 60
    while not fichier.exists():
        if processus.poll() is not None or time.monotonic() > limite:
            sortie = processus.stdout.read() if processus.stdout else ""
            processus.kill()
            pytest.fail(f"le serveur n'a pas démarré :\n{sortie}")
        time.sleep(0.2)
    return processus


def _vivant(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _attendre_mort(pid: int, secondes: float = 15) -> bool:
    limite = time.monotonic() + secondes
    while _vivant(pid) and time.monotonic() < limite:
        time.sleep(0.2)
    return not _vivant(pid)


def _sante(url: str) -> int:
    with urllib.request.urlopen(f"{url}/health", timeout=5) as reponse:
        return int(reponse.status)


def test_demarrage_ecrit_le_fichier_et_le_serveur_repond(env):
    processus = _demarrer(env)
    try:
        pap = json.loads(Path(env["PAP_DEV_PORTS"]).read_text())["pap"]
        assert pap["port"] == int(env["PAP_PORT"])
        assert pap["url"] == f"http://localhost:{env['PAP_PORT']}"
        assert _vivant(pap["pid"])
        assert pap["commit"]
        assert pap["started_at"] <= time.time()
        assert _sante(pap["url"]) == 200
    finally:
        _script(env, "--stop")
        processus.wait(timeout=30)


def test_status_decrit_le_serveur_actif(env):
    processus = _demarrer(env)
    try:
        resultat = _script(env, "--status")
        assert resultat.returncode == 0, resultat.stdout + resultat.stderr
        assert f"http://localhost:{env['PAP_PORT']}" in resultat.stdout
        assert "actif" in resultat.stdout
    finally:
        _script(env, "--stop")
        processus.wait(timeout=30)


def test_status_sans_serveur_echoue(env):
    resultat = _script(env, "--status")
    assert resultat.returncode == 1
    assert "aucun serveur" in resultat.stdout + resultat.stderr


def test_stop_arrete_le_serveur_et_retire_le_fichier(env):
    processus = _demarrer(env)
    pid = json.loads(Path(env["PAP_DEV_PORTS"]).read_text())["pap"]["pid"]

    resultat = _script(env, "--stop")

    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert _attendre_mort(pid)
    assert not Path(env["PAP_DEV_PORTS"]).exists()
    processus.wait(timeout=30)


def test_stop_sans_serveur_ne_fait_rien(env):
    resultat = _script(env, "--stop")
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr


def test_ctrl_c_arrete_le_serveur_et_retire_le_fichier(env):
    processus = _demarrer(env)
    pid = json.loads(Path(env["PAP_DEV_PORTS"]).read_text())["pap"]["pid"]

    processus.send_signal(signal.SIGINT)
    processus.wait(timeout=30)

    assert _attendre_mort(pid)
    assert not Path(env["PAP_DEV_PORTS"]).exists()


def test_restart_remplace_le_serveur_precedent(env):
    premier = _demarrer(env)
    ancien = json.loads(Path(env["PAP_DEV_PORTS"]).read_text())["pap"]["pid"]
    Path(env["PAP_DEV_PORTS"]).unlink()  # le nouveau l'écrira de nouveau

    env_restart = {**env}
    second = subprocess.Popen(
        [str(SCRIPT), "--restart"],
        env=env_restart,
        cwd=RACINE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        limite = time.monotonic() + 60
        while not Path(env["PAP_DEV_PORTS"]).exists():
            assert second.poll() is None, second.stdout.read() if second.stdout else ""
            assert time.monotonic() < limite
            time.sleep(0.2)
        nouveau = json.loads(Path(env["PAP_DEV_PORTS"]).read_text())["pap"]["pid"]
        assert nouveau != ancien
        assert _attendre_mort(ancien)
        assert _sante(f"http://localhost:{env['PAP_PORT']}") == 200
    finally:
        _script(env, "--stop")
        second.wait(timeout=30)
        premier.wait(timeout=30)


def test_demarrage_refuse_un_port_occupe(env):
    with socket.socket() as occupant:
        occupant.bind(("127.0.0.1", int(env["PAP_PORT"])))
        occupant.listen()
        resultat = _script(env)
    assert resultat.returncode == 1
    assert "--restart" in resultat.stdout + resultat.stderr


def test_argument_inconnu(env):
    resultat = _script(env, "--n-importe-quoi")
    assert resultat.returncode == 1
    assert "Usage" in resultat.stdout + resultat.stderr


@pytest.fixture
def env_plage(env: dict[str, str]) -> dict[str, str]:
    """Sans ``PAP_PORT`` : le port vient d'une plage de trois ports libres."""
    debut = _plage_libre()
    sans_port = {k: v for k, v in env.items() if k != "PAP_PORT"}
    return {**sans_port, "PAP_PLAGE_PORTS": f"{debut}-{debut + 2}"}


def _debut(env: dict[str, str]) -> int:
    return int(env["PAP_PLAGE_PORTS"].split("-")[0])


def _pap(env: dict[str, str]) -> dict[str, Any]:
    pap: dict[str, Any] = json.loads(Path(env["PAP_DEV_PORTS"]).read_text())["pap"]
    return pap


def test_sans_pap_port_le_premier_port_libre_de_la_plage(env_plage):
    debut = _debut(env_plage)
    with socket.socket() as occupant:
        occupant.bind(("127.0.0.1", debut))
        occupant.listen()
        processus = _demarrer(env_plage)
        try:
            assert _pap(env_plage)["port"] == debut + 1
            assert _sante(f"http://localhost:{debut + 1}") == 200
        finally:
            _script(env_plage, "--stop")
            processus.wait(timeout=30)


def test_second_demarrage_prend_le_port_suivant_et_stop_arrete_les_deux(env_plage):
    debut = _debut(env_plage)
    premier = _demarrer(env_plage)
    ancien = _pap(env_plage)["pid"]
    second = subprocess.Popen(
        [str(SCRIPT)],
        env=env_plage,
        cwd=RACINE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        limite = time.monotonic() + 60
        while _pap(env_plage)["pid"] == ancien:
            assert second.poll() is None, second.stdout.read() if second.stdout else ""
            assert time.monotonic() < limite
            time.sleep(0.2)
        assert _pap(env_plage)["port"] == debut + 1

        statut = _script(env_plage, "--status")
        assert f"port {debut}" in statut.stdout

        resultat = _script(env_plage, "--stop")
        assert resultat.returncode == 0, resultat.stdout + resultat.stderr
        assert _attendre_mort(ancien)
        assert _script(env_plage, "--status").returncode == 1
    finally:
        _script(env_plage, "--stop")
        second.wait(timeout=30)
        premier.wait(timeout=30)
    assert second.stdout is not None
    assert "un autre serveur pap tourne déjà" in second.stdout.read()
