# L'appli pap en conteneur et sur le NAS

L'appli web de lmelp-pap (`lmelp-pap arbitrer` : l'accueil par état sur `/`, la liste en mode arbitrage sur `/liste`) est publiée en image Docker : `ghcr.io/castorfou/lmelp-pap`. Sur le NAS, elle tourne comme service `pap` de la stack [docker-lmelp](https://github.com/castorfou/docker-lmelp).

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
| `PAP_AUDIOS` | `/data/audios` | enregistrements rapatriés, par année |
| `PAP_AUDIOS_LMELP` | `/audios-lmelp` | dossier audio du back-office lmelp, où vont les enregistrements mis à disposition |
| `RADIOFRANCE_API_TOKEN` | aucune | jeton de l'API Radio France, lue seulement au moment d'une mise à disposition pour compléter la description |
| `PAP_VERIFICATION_JOURS` | `7` | jours entre deux vérifications complètes des URL d'intégral (la première part seule au démarrage sur une base neuve) |
| `PAP_URL_PUBLIQUE` | aucune | adresse publique de l'appli (par exemple `https://pap.lmelp.ascot63.synology.me`), donnée dans les logs de démarrage |
| `PUID` / `PGID` | `1000` / `1000` | propriétaire des fichiers créés dans `/data` |
| `MONGO_URI` / `MONGO_DB` | aucune / `masque_et_la_plume` | base Mongo de la maturité des enregistrements (collection `pap_enregistrements`) et des arbitrages (collection `pap_arbitrages`) ; sans `MONGO_URI`, l'appli sert la liste sans maturité et garde ses arbitrages dans `arbitrages.csv` |

Le conteneur démarre en root, attribue à son utilisateur `appuser` l'UID et le GID `PUID`/`PGID`, reprend la propriété de tout `/data` (y compris les fichiers d'un déploiement précédent), puis sert l'appli sous cet utilisateur. Les fichiers restent ainsi lisibles et supprimables depuis l'hôte.

## Logs

L'appli écrit ses logs sur la sortie d'erreur du conteneur : `docker logs lmelp-pap` (ou `docker logs -f` pour les suivre). Le dossier `/data/logs` reste vide. Chaque ligne porte l'horodatage local, le niveau (`INFO`, `WARNING`, `ERROR`), le module et le message. Au démarrage :

```
2026-11-21 10:53:40 INFO    cli : lecture du cache et construction de la liste…
2026-11-21 10:53:49 INFO    cli : lmelp-pap 0.1.0 : écoute sur 0.0.0.0:8090
2026-11-21 10:53:49 INFO    cli : Mongo : connecté (base masque_et_la_plume)
2026-11-21 10:53:49 INFO    cli : liste : 2123 émissions
2026-11-21 10:53:49 INFO    cli : arbitrages : collection pap_arbitrages
2026-11-21 10:53:49 INFO    cli : dossiers : cache /data/cache, données /data/processed, arbitrages /data/processed/arbitrages.csv, audios /data/audios, audios lmelp /audios-lmelp
2026-11-21 10:53:49 INFO    cli : page publique : https://pap.lmelp.ascot63.synology.me
```

L'adresse d'écoute est celle du conteneur (`0.0.0.0:8090`) ; l'adresse vue depuis le réseau est celle de `PAP_URL_PUBLIQUE`, ligne absente sans cette variable. Mongo est `connecté`, `absent (MONGO_URI non défini)` ou `injoignable (base …) : <erreur>` : le démarrage tente un `ping` et compte les émissions sans lire la base : l'appli démarre dans tous les cas. Les arbitrages viennent de la `collection pap_arbitrages` avec `MONGO_URI`, sinon du `fichier …` des arbitrages. Les lignes qui suivent (requêtes, actions, erreurs) sont décrites dans [la liste des émissions](liste-des-emissions.md#logs).

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

Le service `pap` se déclare dans le `docker-compose.yml` de docker-lmelp : image `ghcr.io/castorfou/lmelp-pap:latest`, montage `/volume1/docker/lmelp/pap:/data`, et `PUID`/`PGID` à `1027`, comme le backend (`.env.nas.example`). Les fichiers de `pap/` appartiennent alors à `1027:1027`.

Dans docker-lmelp, `PAP_PORT` est le port publié sur le NAS (`8085` dans `.env.nas.example`). Le conteneur, lui, écoute toujours sur `8090` (`"${PAP_PORT}:8090"`). L'appli est donc servie sur `http://<NAS>:8085/`.

Pour la mise à disposition de lmelp, le service `pap` monte aussi le dossier audio du back-office (`${AUDIO_PATH}`, celui que `backend` monte sur `/app/audios`) sur `/audios-lmelp` :

```yaml
    volumes:
      - ${PAP_PATH_HOTE:-./data/pap}:/data
      - ${AUDIO_PATH:-./data/audios}:/audios-lmelp
```

L'entrypoint ne reprend pas la propriété de ce dossier : il appartient au back-office, et doit seulement être inscriptible par `PUID`/`PGID`. pap y crée `<année>/<nom>` et n'écrase jamais un fichier existant.

Watchtower met le conteneur à jour après chaque publication de l'image sur `main`.

### Arbitrages

Avec `MONGO_URI`, les arbitrages vivent dans la collection `pap_arbitrages` de la base de lmelp, couverte par sa sauvegarde (`mongodump --db=masque_et_la_plume`). Une fois, au premier déploiement, importer le fichier amorcé dans `pap/processed` :

```bash
docker exec -u appuser lmelp-pap lmelp-pap arbitrages importer
```

L'import est idempotent : le relancer n'ajoute que les arbitrages absents. `docker exec -u appuser lmelp-pap lmelp-pap arbitrages exporter` réécrit `/data/processed/arbitrages.csv` avec les arbitrages de Mongo (voir [Arbitrages dans Mongo](liste-des-emissions.md#arbitrages-dans-mongo)). `-u appuser` laisse le fichier au propriétaire `PUID`/`PGID` ; la ligne de log de la commande s'affiche dans le terminal du `docker exec`, pas dans `docker logs`.

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
    - Port : `8085` (port publié sur le NAS, `PAP_PORT` de docker-lmelp)

L'appli est alors servie sur `https://pap.lmelp.ascot63.synology.me`, depuis le réseau local. Ce nom se résout vers le NAS par la réécriture DNS d'AdGuard sur le réseau de la maison. Depuis un autre réseau relié par VPN, dont les DNS ne sont pas ceux d'AdGuard, le nom tombe sur la page « introuvable » de DSM. On passe alors par le nom de machine du NAS : `http://<NAS>:8085/`.
