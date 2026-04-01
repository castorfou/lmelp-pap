# lmelp pap

Le Masque & La Plume : **Projet d'Archivage Patrimonial (1955-2016)**


## pyfoundry-template

Ce projet a été instancié depuis un template.

Toutes les infos sur ce template et la façon de l'utiliser sont dans sa [documentation](https://castorfou.github.io/PyFoundry/).

## 📝 Présentation du projet

Ce projet a pour mission de reconstituer la mémoire sonore et textuelle du **Masque et la Plume**, la doyenne des émissions de radio française (créée en 1955 par François-Régis Bastide et Michel Polac), avec une focalisation spécifique sur les émissions dédiées à la **littérature**.

L'objectif est de combler le fossé numérique entre les archives modernes disponibles sur Radio France (post-juillet 2016) et les soixante années d'histoire radiophonique précédentes, souvent dispersées ou non indexées.

* * *

## 🛠️ Artefacts du Projet

Le projet produit deux jeux de données (datasets) principaux :

### 1\. Le Master Index (Metadata)

Une base de données structurée recensant l'intégralité des émissions littéraires depuis 1955.

-   **Format :** `CSV` / `SQLite`

-   **Champs :** `Date de diffusion`, `Animateur`, `Œuvres critiquées`, `Auteurs`, `Critiques présents`, `Lien archive (si existant)`.

-   **Sources :** Scraping des notices de l'INA, archives de presse (Gallica/RetroNews), et bibliographie spécialisée.


### 2\. La Phonothèque (Audio)

Une collection d'enregistrements audio (MP3) sourcés via des collectionneurs privés, des archives publiques et du web mining.

-   **Format :** `MP3` (Mono/Stéréo selon l'époque)

-   **Traitement :** Normalisation sonore et tagging ID3 basé sur le Master Index.


* * *

## 📊 Dashboard d'Avancement

_Mise à jour automatique des métriques de complétude du projet._

| Décennie        | Métadonnées (Index) | Audio (Collecte) | Statut      |
| --------------- | ------------------- | ---------------- | ----------- |
| **1955 - 1969** | ░░░░░░░░░░ 0%       | ░░░░░░░░░░ 0%    | 🔍 Recherche |
| **1970 - 1989** | ░░░░░░░░░░ 0%       | ░░░░░░░░░░ 0%    | 🔍 Recherche |
| **1990 - 2005** | ░░░░░░░░░░ 0%       | ░░░░░░░░░░ 0%    | 🔍 Recherche |
| **2006 - 2016** | ▓▓▓▓▓▓▓▓▓▓ 10%      | ▓▓▓▓▓▓▓▓▓▓ 5%    | 🏗️ En cours  |

* * *

## 🚀 Outils & Logiciels (Toolbox)

Ce dépôt héberge également les outils Python développés pour automatiser la quête :

-   `/scrapers/` : Scripts pour extraire les métadonnées de l'INA et de Gallica.

-   `/audio_processing/` : Outils de traitement du signal (normalisation, réduction de bruit via modèles ML).

-   `/discovery/` : Algorithmes de recherche par "Dorking" et scan de répertoires ouverts (Open Directories).

-   `/tagger/` : Script d'alignement automatique entre les fichiers audio trouvés et le Master Index.


* * *

## 🤝 Appel à la Communauté

Nous recherchons des **passionnés**, **archivistes** ou **anciens auditeurs** possédant :

-   Des enregistrements sur cassettes (K7) ou bandes magnétiques.

-   Des numérisations personnelles réalisées entre 1980 et 2010.

-   Des journaux de programmes radio d'époque.


> **Note éthique :** Ce projet s'inscrit dans une démarche de conservation patrimoniale privée et de recherche historique. Il ne se substitue pas aux services commerciaux de l'INA ou de Radio France.

* * *

## 📚 Références et Sources

-   **INA (Institut National de l'Audiovisuel)** : [ina.fr](https://www.ina.fr/)

-   **Gallica / BnF** : Archives de la presse française.

-   **Ouvrage de référence** : _Le Masque et la Plume_, Jérôme Garcin, Actes Sud.




[![CI](https://github.com/castorfou/lmelp-pap/actions/workflows/ci.yml/badge.svg)](https://github.com/castorfou/lmelp-pap/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/castorfou/lmelp-pap/branch/main/graph/badge.svg)](https://codecov.io/gh/castorfou/lmelp-pap)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

## Installation

Ce projet utilise **uv** pour la gestion des dépendances et des environnements Python.

### Avec VS Code + Devcontainer (Recommandé)

Si vous avez Docker et VS Code :

```bash
# 1. Authentifiez-vous à ghcr.io (si nécessaire)
# Créez un Personal Access Token : https://github.com/settings/tokens/new
# Permissions : read:packages
docker login ghcr.io -u VOTRE_USERNAME

# 2. Ouvrez dans VS Code
code .
# VS Code proposera "Reopen in Container"
```

## Structure du projet

```
├── src/           # Code source du projet
├── data/          # Données du projet
│   ├── raw/       # Données brutes
│   └── processed/ # Données traitées
├── notebooks/     # Notebooks Jupyter
└── pyproject.toml # Configuration du projet
```

## Documentation

📚 La documentation complète est disponible sur [castorfou.github.io/lmelp-pap](https://castorfou.github.io/lmelp-pap)

### Activer GitHub Pages (première fois)

Pour déployer la documentation, activez GitHub Pages :

```bash
# Via gh CLI (recommandé)
gh api repos/castorfou/lmelp-pap/pages \
  -X POST \
  -f build_type=workflow

# Ou manuellement :
# 1. Allez dans Settings > Pages
# 2. Source : sélectionnez "GitHub Actions"
```

### Générer localement

```bash
# Installer les dépendances de documentation
uv sync --extra docs

# Prévisualiser localement
uv run mkdocs serve

# La documentation sera accessible à l'URL affichée dans les logs
# Example: http://127.0.0.1:8000/lmelp-pap/
```

!!! note "URL locale"
    Comme `site_url` est configuré pour GitHub Pages avec un chemin de base,
    MkDocs servira la documentation avec ce même chemin en local.
    Accédez à l'URL complète affichée dans les logs (avec le chemin `/lmelp-pap/`).

    Si vous souhaitez servir sans chemin de base pour le développement local,
    commentez temporairement la ligne `site_url` dans `mkdocs.yml`.

## Usage

Décrivez ici comment utiliser votre projet.

## Contribution

1. Installez les hooks pre-commit : `pre-commit install`
2. Créez une branche pour votre fonctionnalité
3. Commitez vos changements
4. Ouvrez une Pull Request
