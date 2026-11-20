# Image Docker

L'image `ghcr.io/castorfou/lmelp-pap` sert l'appli web (`lmelp-pap arbitrer`). Son usage (volume, variables, NAS, reverse proxy) est décrit dans [L'appli pap en conteneur et sur le NAS](../user/appli-docker-nas.md).

## Fichiers

| Fichier | Rôle |
|---|---|
| `Dockerfile` | image en deux étapes : `builder` installe le paquet et ses dépendances (sans celles de dev) dans `/app/.venv` avec `uv sync --frozen --no-dev --no-editable` ; l'étape finale copie ce venv, installe Chromium de Playwright et `gosu`, fixe les variables `PAP_*` |
| `docker/entrypoint.sh` | remap d'`appuser` sur `PUID`/`PGID`, `chown -R /data`, puis `gosu appuser` |
| `.dockerignore` | exclut données, docs, tests, notebooks et caches du contexte de build |
| `.github/workflows/docker.yml` | construit l'image à chaque PR touchant le code ou l'image ; à chaque push sur `main`, la pousse sur ghcr (`latest`, `sha-…`) puis déclenche sa mise à jour sur le NAS |

Le paquet est installé hors mode éditable : les gabarits `page.html` et `arbitrage.html` (déclarés en `package-data`) sont dans le venv, et l'image ne contient pas `src/`.

## Configuration de la commande

`src/lmelp_pap/cli.py` construit le parseur dans `_parser()`. Les variables `PAP_CACHE`, `PAP_DONNEES`, `PAP_ARBITRAGES`, `PAP_PORT` et `PAP_HOTE` fixent les défauts des options ; une option explicite l'emporte. Sans variable, les défauts restent ceux du dépôt (`data/raw/cache`, `data/processed`, port 8765, `127.0.0.1`). L'image fixe `PAP_HOTE=0.0.0.0`, `PAP_PORT=8090`, `PAP_CACHE=/data/cache`, `PAP_DONNEES=/data/processed`.

## Santé

`GET /health` (`src/lmelp_pap/arbitrer.py`) répond `{"status": "ok"}` sans construire la page. Le `HEALTHCHECK` de l'image l'interroge toutes les 30 secondes, après un délai de démarrage de 60 secondes (le temps de lire le cache et de construire la liste).

## Propriétaire des fichiers

L'image publiée sert sur des machines où l'utilisateur n'a pas le même UID (1000 sur un poste, 1027 sur le NAS). Le conteneur démarre donc en root ; `docker/entrypoint.sh` remappe `appuser` sur `PUID`/`PGID` (défaut 1000), reprend la propriété de `/data` à chaque démarrage, puis exécute la commande sous `appuser` avec `gosu`. C'est le même modèle que le backend de back-office-lmelp.

## Mise à jour sur le NAS

Sur `main`, après le push de l'image, l'étape « Mise à jour sur le NAS (Watchtower) » de `docker.yml` appelle l'API HTTP du Watchtower de la stack (`POST https://watchtower.ascot63.synology.me/v1/update?image=ghcr.io/castorfou/lmelp-pap`). L'appel s'authentifie par `Authorization: Bearer` avec le secret de dépôt `WATCHTOWER_TOKEN`, de même valeur que `WATCHTOWER_HTTP_API_TOKEN` du conteneur Watchtower. Watchtower tire alors l'image et redémarre le conteneur `pap`, qui porte le label `com.centurylinklabs.watchtower.enable=true`.

L'étape échoue si Watchtower ne trouve aucun conteneur pour cette image (`summary.scanned = 0`) ou si la mise à jour échoue (`summary.failed > 0`). Si l'appel n'aboutit pas, le contrôle périodique de Watchtower (hebdomadaire) finit par appliquer la nouvelle image.

## Construire et tester en local

Le devcontainer dispose d'un daemon Docker (option PyFoundry `docker_in_docker`).

```bash
docker build -t lmelp-pap:test .
mkdir -p /tmp/pap && cp -r data/raw/cache /tmp/pap/cache && cp -r data/processed /tmp/pap/processed
docker run -d --name pap-test -p 8090:8090 -e PUID=1027 -e PGID=1027 -v /tmp/pap:/data lmelp-pap:test
curl localhost:8090/health
docker inspect --format '{{.State.Health.Status}}' pap-test
stat -c '%u:%g %n' /tmp/pap/processed/emissions.csv   # 1027:1027
docker rm -f pap-test
```

Chromium se vérifie dans le conteneur :

```bash
docker exec pap-test python -c "from playwright.sync_api import sync_playwright as s; p = s().start(); print(p.chromium.launch().version)"
```
