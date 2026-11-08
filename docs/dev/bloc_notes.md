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
path = collect_all_emissions(scrape_ina=False)
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

## creer la liste des emissions sur base INA + Mongo

```bash
uv run --active python -c "
from lmelp_pap.emissions import collect_all_emissions
path = collect_all_emissions()
import pandas as pd
df = pd.read_csv(path)
print('Total:', len(df), 'émissions')
print('Dates:', df['date_diffusion'].min(), '→', df['date_diffusion'].max())
print(df['source'].value_counts())
"
```

## ina_brut.csv

```bash
uv run --active python -c "
from lmelp_pap.sources.ina_catalogue import scrape_ina_catalogue_raw
from pathlib import Path

df = scrape_ina_catalogue_raw(max_pages=99, delay=1.5)
output = Path('data/raw/ina_brut.csv')
df.to_csv(output, index=False, encoding='utf-8')
print(f'{len(df)} notices, {output}')
print('Premières dates:', df['date_diffusion'].head(5).tolist())
print('Dernières dates:', df['date_diffusion'].tail(5).tolist())
" 2>&1
```
