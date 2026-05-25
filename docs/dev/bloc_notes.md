## ajout de packages

!!! warning "ne pas oublier --active dans les commandes uv"

    que ça soit pour ajouter un package ou executer une commande, e.g.

    ```bash
    uv add --active requests beautifulsoup4 lxml pymongo
    ```

## demarrage du serveur mkdocs

```bash
mkdocs serve -a localhost:8005
```

## lancement des tests unitaires

```bash
uv run --active pytest
```

## creer la liste des emissions sur base mongo

```bash
uv run --active python -c "
from lmelp_pap.emissions import collect_all_emissions
from pathlib import Path
path = collect_all_emissions(scrape_france_inter=False, scrape_ina=False)
print(f'CSV généré : {path}')
import pandas as pd; df = pd.read_csv(path); print(df.shape, df.head(3))
"
```

## gestion des .env

pour le moment pour l'URI mongo

en créant ce .env, VSCode suggere d'activer l'injection terminal des .env

```text
An environment file is configured but terminal environment injection is disabled. Enable "python.terminal.useEnvFile" to use environment variables from .env files in terminals.
```

## creer la liste des emissions sur base INA

```bash

```
