# L'appli pap en conteneur et sur le NAS

L'appli web de lmelp-pap (la liste en mode arbitrage, `lmelp-pap arbitrer`) est publiée en image Docker : `ghcr.io/castorfou/lmelp-pap`. Sur le NAS, elle tourne comme service `pap` de la stack [docker-lmelp](https://github.com/castorfou/docker-lmelp).

## Le volume `/data`

Le conteneur range toutes ses données dans `/data` :

| Dossier | Contenu |
|---|---|
| `/data/cache/` | cache des sources : pages radiofrance.fr, notices INA, index Wayback, anciennes listes, copie lmelp |
| `/data/processed/` | CSV de la liste (`emissions.csv`, `attestations.csv`, `enregistrements.csv`, `doutes.csv`) et `arbitrages.csv` |
| `/data/audios/` | enregistrements rapatriés, par année |
| `/data/logs/` | journaux |

Au premier lancement, la liste se construit à partir du cache : `cache/` et `processed/` s'amorcent par une copie de `data/raw/cache/` et `data/processed/` du dépôt. Sans cache, la page affiche une liste vide.

## Variables

| Variable | Défaut dans l'image | Rôle |
|---|---|---|
| `PAP_PORT` | `8090` | port d'écoute |
| `PAP_HOTE` | `0.0.0.0` | adresse d'écoute |
| `PAP_CACHE` | `/data/cache` | cache des sources |
| `PAP_DONNEES` | `/data/processed` | CSV de la liste et arbitrages |
| `PAP_ARBITRAGES` | `arbitrages.csv` dans `PAP_DONNEES` | fichier des arbitrages |
| `PUID` / `PGID` | `1000` / `1000` | propriétaire des fichiers créés dans `/data` |

Le conteneur démarre en root, attribue à son utilisateur `appuser` l'UID et le GID `PUID`/`PGID`, reprend la propriété de tout `/data` (y compris les fichiers d'un déploiement précédent), puis sert l'appli sous cet utilisateur. Les fichiers restent ainsi lisibles et supprimables depuis l'hôte.

## Lancer l'image sur un poste

```bash
mkdir -p ~/pap
cp -r data/raw/cache ~/pap/cache
cp -r data/processed ~/pap/processed

docker run -d --name pap -p 8090:8090 \
  -e PUID=$(id -u) -e PGID=$(id -g) \
  -v ~/pap:/data \
  ghcr.io/castorfou/lmelp-pap:latest
```

L'appli est servie sur `http://localhost:8090/`. `GET /health` répond `{"status": "ok"}` ; c'est aussi le contrôle de santé du conteneur (`docker inspect --format '{{.State.Health.Status}}' pap`).

## Sur le NAS

### Dossiers

Le dossier `pap/` est frère des autres dossiers de la stack, sous `/volume1/docker/lmelp/`. Le dossier `audios/` du back-office ne reçoit que des intégraux valides ; les enregistrements de pap en cours de rapatriement ou de qualification restent dans `pap/audios/`.

```
/volume1/docker/lmelp/
├── audios/          ← back-office : intégraux valides, par année
├── cache/
├── logs/
├── mongodb/ …
└── pap/             ← monté sur /data dans le service pap, et seulement là
    ├── cache/
    ├── processed/
    ├── audios/
    └── logs/
```

1. Dans File Station, créer `docker/lmelp/pap` et ses sous-dossiers `cache`, `processed`, `audios`, `logs`.
2. Amorcer `pap/cache` et `pap/processed` avec le contenu de `data/raw/cache/` et `data/processed/` du dépôt (archive zip déposée puis extraite dans File Station).

### Service

Le service `pap` se déclare dans le `docker-compose.yml` de docker-lmelp : image `ghcr.io/castorfou/lmelp-pap:latest`, montage `/volume1/docker/lmelp/pap:/data`, `PAP_PORT`, et `PUID`/`PGID` à `1027`, comme le backend (`.env.nas.example`). Les fichiers de `pap/` appartiennent alors à `1027:1027`. Watchtower met l'image à jour après chaque publication sur `main`.

### Reverse proxy

L'appli s'ouvre par un nom d'hôte, via le reverse proxy natif de DSM : **Portail de connexion** → **Avancé** → **Proxy inversé** → **Créer**.

- Reverse Proxy Name : pap
- Source
    - Protocol : HTTPS
    - Hostname : `pap.lmelp.ascot63.synology.me`
    - Port : 443
    - Enable HSTS
    - Access control profile : réseau local
- Destination
    - Protocol : HTTP
    - Hostname : `localhost`
    - Port : `8090` (valeur de `PAP_PORT`)

L'appli est alors servie sur `https://pap.lmelp.ascot63.synology.me`, depuis le réseau local.
