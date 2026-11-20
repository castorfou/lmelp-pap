# Webhook Watchtower et accès à pap sur le NAS (#73)

## Ce qui a été fait

- `.github/workflows/docker.yml` : étape « Mise à jour sur le NAS (Watchtower) » après le push sur `main`, copiée de back-office-lmelp : `POST https://watchtower.ascot63.synology.me/v1/update?image=ghcr.io/castorfou/lmelp-pap` (image sans tag), Bearer `secrets.WATCHTOWER_TOKEN`, puis `jq -e '.summary.scanned >= 1 and .summary.failed == 0'`.
- Doc dev : section « Mise à jour sur le NAS ». Doc user : port publié 8085 et accès hors maison.

## Leçons du premier déploiement (docker-lmelp#94)

- **Ports** : dans docker-lmelp, `PAP_PORT=8085` est le port **publié sur l'hôte** (`"${PAP_PORT}:8090"`). Dans l'image, `PAP_PORT` est le port d'écoute interne (8090). Le reverse proxy DSM doit donc viser `localhost:8085`.
- **Noms du reverse proxy** (`pap.lmelp.ascot63.synology.me`) : ils ne se résolvent vers le NAS que par la réécriture DNS d'AdGuard, sur le réseau de la maison. Depuis l'appart (VPN vers la maison, DNS de l'appart), on obtient la page 404 de DSM, sur n'importe quelle machine. On passe alors par le nom de machine du NAS, sur le port 8085.
- **Données** : le conteneur démarre avec une liste vide tant que `pap/cache` et `pap/processed` ne sont pas amorcés. Le SSH du NAS est fermé : on prépare une archive `tar.gz` (`cache/` + `processed/`, ~100 Mo), on la dépose et on l'extrait dans File Station, puis on redémarre le conteneur pour que l'entrypoint reprenne la propriété de `/data`.
- Secret `WATCHTOWER_TOKEN` = `WT_API_TOKEN` (Portainer) = `WATCHTOWER_HTTP_API_TOKEN` du conteneur Watchtower.
