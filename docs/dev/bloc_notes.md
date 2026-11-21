## ajout de packages

!!! warning "ne pas oublier --active dans les commandes uv"

    que ça soit pour ajouter un package ou executer une commande, e.g.

    ```bash
    uv add --active requests
    ```

## demarrage du serveur mkdocs

La navigation pointe vers la page générée de la liste des émissions : `lmelp-pap page` d'abord.

```bash
uv run --active lmelp-pap page
mkdocs serve -a localhost:8005
```

## lancement des tests unitaires

```bash
uv run --active pytest
```

## creer la liste des emissions

```bash
uv run --active lmelp-pap emissions
```

Voir [Liste des émissions](../user/liste-des-emissions.md) pour les options et les sources.

## gestion des .env

Le fichier `.env` (non versionné) contient les secrets locaux, par exemple `RADIOFRANCE_API_TOKEN`.

en créant ce .env, VSCode suggere d'activer l'injection terminal des .env

```text
An environment file is configured but terminal environment injection is disabled. Enable "python.terminal.useEnvFile" to use environment variables from .env files in terminals.
```

## Playwright et son navigateur dans le devcontainer

Les tests de pages HTML (`tests/test_page_navigateur.py`) et les captures passent par Playwright, qui pilote un Chromium téléchargé à part.

- **Bibliothèques système** : dans `.devcontainer/Dockerfile` (liste de `playwright install-deps chromium` pour Debian bookworm).
- **Navigateur** : `postCreateCommand.sh` (étape `install_playwright_browser`) lance `playwright install chromium` après la création du venv. La commande installe la révision de Chromium qui correspond à la version de `playwright` du venv, dans `~/.cache/ms-playwright` (HOME persistant), et retire les révisions devenues inutiles.
- **Après une montée de version de `playwright`** dans `pyproject.toml` : relancer `uv run --active playwright install chromium`, sans attendre un rebuild.

### Symptôme : aucune image, tout attend

Navigateur qui démarre, page qui se charge, `evaluate` qui répond, mais `page.screenshot`, `hover`, `click` ou `wait_for_function` attendent jusqu'au délai (« waiting for fonts to load… », « waiting for element to be visible and stable »). La page ne produit aucune image : `requestAnimationFrame` ne se déclenche jamais.

Diagnostic rapide :

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.set_content("<p>x</p>")
    print(page.evaluate(
        "new Promise(r => { setTimeout(() => r('pas de frame'), 2000);"
        " requestAnimationFrame(() => r('frame ok')) })"
    ))
```

Dans ce devcontainer, le Chromium 148 (révision 1223) de `playwright` 1.60 ne produisait aucune image, quelles que soient les options de lancement (GPU, swiftshader, single-process). Le Chromium 159 (révision 1255) de `playwright` 1.65.2 fonctionne. Remède : monter `playwright` (`playwright>=1.65.2` dans `pyproject.toml`, `uv lock`, `uv sync --active --all-extras`), puis `playwright install chromium`. Pour tester une révision avant de changer la dépendance : `p.chromium.launch(executable_path=...)` sur un binaire de `~/.cache/ms-playwright`, ou `uv run --no-project --with playwright==<version> python script.py`.
