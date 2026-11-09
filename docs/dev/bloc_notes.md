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
