# Image Docker de l'appli pap (#64)

Première tranche de la construction de l'appli pap décidée sur la carte wayfinder #48 (décision #58 : l'appli tourne sur le NAS dans docker-lmelp).

## Ce qui a été fait

- `src/lmelp_pap/cli.py` : parseur extrait dans `_parser()` ; variables `PAP_CACHE`, `PAP_DONNEES`, `PAP_ARBITRAGES`, `PAP_PORT`, `PAP_HOTE` comme défauts des options (option explicite prioritaire) ; `arbitrer --hote`.
- `src/lmelp_pap/arbitrer.py` : `GET /health` → `{"status": "ok"}` sans construire la page.
- `Dockerfile` (uv, `--no-editable` pour embarquer les gabarits HTML, Chromium de Playwright, `gosu`), `docker/entrypoint.sh`, `.dockerignore`, `.github/workflows/docker.yml` (build sur PR, push `latest`/`sha` sur `main`).
- Docs : `docs/user/appli-docker-nas.md` (volume, variables, NAS, reverse proxy `pap.lmelp.ascot63.synology.me` → `localhost:8090`), `docs/dev/image-docker.md`.
- Devcontainer : option PyFoundry `docker_in_docker` activée (PR #71) pour construire et tester l'image localement.

## Décisions et leçons

- **Propriétaire des fichiers (PUID/PGID)** : sujet récurrent de la stack lmelp. Ne jamais figer l'UID au build : démarrer en root, remapper `appuser` sur `PUID`/`PGID` (1027 sur le NAS), `chown -R` du volume à chaque démarrage, puis `gosu` — modèle de `back-office-lmelp/docker/build/backend/entrypoint.sh`. Oublié dans la première version, signalé par l'utilisateur.
- **Un seul montage** sur le NAS : `/volume1/docker/lmelp/pap` → `/data` (`cache/`, `processed/`, `audios/`, `logs/`). `audios/` du back-office reste réservé aux intégraux valides.
- Route de santé nommée `/health` (convention de la stack), pas `/sante`.
- Chromium installé dès cette image (`PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`) pour la collecte INA depuis l'interface (#66). Image ≈ 2,3 Go.
- Docker-in-Docker : les montages `-v` désignent des chemins du devcontainer.

## Suite

castorfou/docker-lmelp#94 (service `pap` : montage, `PAP_PORT`, `PUID`/`PGID` 1027, reverse proxy), puis #65 (arbitrages dans Mongo).
