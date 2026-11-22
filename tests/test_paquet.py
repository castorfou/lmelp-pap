"""Le paquet installé (image Docker, wheel) embarque ses gabarits HTML et icônes.

En mode éditable, un fichier oublié dans ``package-data`` reste trouvable :
seul un vrai paquet révèle l'oubli. Ce test lit la configuration.
"""

import fnmatch
import tomllib
from pathlib import Path


RACINE = Path(__file__).parents[1]


def test_chaque_gabarit_html_est_dans_package_data() -> None:
    config = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    motifs = config["tool"]["setuptools"]["package-data"]["lmelp_pap"]
    gabarits = [p.name for p in (RACINE / "src" / "lmelp_pap").glob("*.html")]
    assert gabarits
    oublies = [g for g in gabarits if not any(fnmatch.fnmatch(g, m) for m in motifs)]
    assert oublies == []


def test_chaque_icone_est_dans_package_data() -> None:
    config = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    motifs = config["tool"]["setuptools"]["package-data"]["lmelp_pap"]
    paquet = RACINE / "src" / "lmelp_pap"
    icones = [p.relative_to(paquet).as_posix() for p in (paquet / "icones").iterdir()]
    assert "icones/favicon.ico" in icones
    oubliees = [i for i in icones if not any(fnmatch.fnmatch(i, m) for m in motifs)]
    assert oubliees == []
