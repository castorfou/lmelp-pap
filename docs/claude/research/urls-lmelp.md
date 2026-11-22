# Les URL de lmelp et du back-office à construire depuis pap (#88)

Recherche du 22/11/2026. Sources lues : `castorfou/back-office-lmelp` (commit `ef6e212`),
`castorfou/docker-lmelp` (commit `c7fcbc2`), `castorfou/lmelp` (commit `8320480`),
et le code de pap (`main`, `eff9356`).

## Le fait qui change la question : « lmelp » est le back-office

L'appli Streamlit historique `lmelp` n'est plus dans la stack. Le back-office la
remplace et s'appelle désormais « lmelp » :

- docker-lmelp, commit `38b6f75` « feat(compose)!: retirer le service Streamlit lmelp
  (#71) » ; mémoire `docs/claude/memory/260927-1735-issue71-retrait-streamlit-lmelp.md` :
  « back-office-lmelp remplace l'application Streamlit historique `lmelp`
  (back-office-lmelp#302) et se renomme « lmelp » (…) l'URL publique
  `lmelp.ascot63.synology.me` sert désormais le frontend du back-office ».
- `docker-compose.yml` ne déclare plus que `mongo`, `pgx-keys-watchdog`, `backend`,
  `frontend`, `lmelp-export`, `pap` (pas de service `lmelp`, plus de port 8501).
- Les titres des pages du back-office finissent par « - lmelp »
  (`frontend/src/router/index.js`, `meta.title`).

Les deux liens de pap visent donc **la même appli, sur le même port** : le frontend du
back-office.

## 1. Une émission dans lmelp (page « dans lmelp » de pap)

**URL : `<base lmelp>/emissions/<AAAAMMJJ>`**, par exemple
`http://nas923:8081/emissions/19780312`.

- Route : `frontend/src/router/index.js` l. 190 : `path: '/emissions/:date'`,
  `name: 'EmissionDetail'`, composant `views/Emissions.vue`.
- Format du paramètre : `Emissions.vue` l. 555 « Charge une émission par date (format
  YYYYMMDD) » ; `formatDateForUrl` l. 762 rend `${year}${month}${day}`. Le moteur de
  recherche fait les mêmes liens (`components/TextSearchEngine.vue` l. 85).
- Backend : `GET /api/emissions/by-date/{date_str}` (`src/back_office_lmelp/app.py`
  l. 1535) vérifie `^\d{8}$`, puis cherche dans la collection **`emissions`** un document
  dont `date` est entre `AAAA-MM-JJ 00:00:00` et `23:59:59` (datetimes naïfs, donc UTC
  pour pymongo).
- Liens profonds servis : le routeur est en `createWebHistory()` (`router/index.js`
  l. 256) et le nginx du frontend renvoie `index.html` pour tout chemin
  (`docker/build/frontend/nginx.conf` l. 70-71, `try_files $uri $uri/ /index.html`).

**Identifiant : la date de l'émission**, ni l'id Mongo de `episodes`, ni
`audio_rel_filename`. pap connaît cette date sans rien lire dans lmelp : c'est celle de
son émission, qu'il écrit aussi dans la fiche `pap_remises`
(`src/lmelp_pap/remise.py` l. 382 : `datetime(année, mois, jour, tzinfo=UTC)`, minuit UTC,
donc dans la fenêtre de la requête by-date). L'épisode créé par l'intégration reprend
cette date (`back-office-lmelp/src/back_office_lmelp/services/pap_remises_service.py`
l. 155 `"date": fiche["date"]`). pap n'a besoin de l'entrée `episodes` (via
`audio_rel_filename`, ou plus directement `pap_remise_id`, l. 165, égal au `_id` de la
fiche, c.-à-d. l'URL de l'enregistrement) que pour savoir **qu'**elle est dans lmelp,
pas pour construire le lien.

**Limite : la page n'existe qu'une fois l'émission complète côté lmelp.** La collection
`emissions` n'est pas `episodes` : `auto_convert_episodes_to_emissions`
(`app.py` l. 1443) ne crée une émission que pour un épisode qui a un `avis_critiques`
(résumé généré après transcription) et qui n'est pas masqué. Entre l'intégration et la
génération de l'avis critique, `/emissions/AAAAMMJJ` affiche « Aucune émission trouvée
pour la date … » (404 du backend, l. 1576-1580). Il n'existe pas de page par épisode :
`/episodes` (`EpisodePage.vue`) ne lit ni paramètre ni query (aucun `route.params` /
`route.query` dans ce composant). Conséquence pour pap : soit ne rendre le titre
cliquable que quand l'émission existe (pap lit la collection `emissions` par date ou
`episode_id`), soit accepter le message d'absence ; l'auto-conversion se déclenche à
chaque `GET /api/emissions`, que la page `/emissions/…` appelle au chargement
(`Emissions.vue` l. 796-800, `app.py` l. 1407).

Autre point : `find_one` par jour rend une seule émission par date. Une émission
ancienne par jour, c'est le cas du Masque.

## 2. L'import d'une émission dans le back-office (page « valide » de pap)

**L'écran existe, mais en liste : `<base lmelp>/emissions-anciennes`.**

- Route : `router/index.js` l. 230 : `path: '/emissions-anciennes'`,
  `name: 'RemisesPap'`, titre « Émissions anciennes - lmelp ».
- `views/RemisesPap.vue` : « Émissions anciennes à intégrer », liste de
  `GET /api/pap/remises` (fiches `pap_remises` pas encore intégrées, plus récentes
  d'abord, `pap_remises_service.py` l. 78-117), un bouton « Intégrer » par ligne
  (`POST /api/pap/remises/integrer` avec `remise_id`). Livré par back-office-lmelp#378
  (fermée le 22/11/2026).
- Pas de lien profond vers une remise : le composant ne lit ni `route.params` ni
  `route.query`, et les lignes n'ont pas d'`id` HTML servant d'ancre (seulement
  `data-testid="remise-row"`).
- Une fois intégrée, la remise sort de la liste (`_ids_integres`, l. 66-68) : le lien
  depuis « valide » n'a de sens que tant que l'émission est en attente d'intégration,
  ce qui est justement l'état « valide » de pap.

Lien recommandé, utilisable tout de suite : `<base lmelp>/emissions-anciennes` (même lien
pour toutes les émissions valides). La liste étant triée par date décroissante et courte
(émissions livrées non intégrées), c'est suffisant au début.

**Issue back-office-lmelp à ouvrir seulement si on veut cibler une ligne** : accepter
`/emissions-anciennes?date=AAAAMMJJ` (ou `?remise=<remise_id>`), surligner et faire
défiler jusqu'à la ligne. La date est préférable : `remise_id` est l'URL de
l'enregistrement (`remise.py` l. 379 `"_id": enregistrement.url`), longue et à encoder.
Rien de tel n'existe aujourd'hui (aucune issue trouvée par
`gh issue list -R castorfou/back-office-lmelp --search "emissions-anciennes OR remise"`).

## 3. L'hôte

**Ports publiés** (docker-lmelp) :

| Service | Variable | Défaut `.env.example` | NAS `.env.nas.example` | Port conteneur |
|---|---|---|---|---|
| lmelp (frontend du back-office) | `FRONTEND_PORT` | 8080 | **8081** (l. 100, « 8080 est souvent déjà pris ») | 80 (`docker-compose.yml` l. 139) |
| API backend | `BACKEND_PORT` | 8000 | 8000 | 8000 (l. 71) |
| pap | `PAP_PORT` | 8090 | 8085 (l. 194) | 8090 (l. 218) |

Le frontend proxifie `/api/` vers le backend (`nginx.conf` l. 32-33) : les liens de pap
ne visent que le frontend, jamais le port 8000.

**Reverse proxy DSM** (`docs/user/migration-nas.md` étape 8, l. 242-280) :
`https://lmelp.ascot63.synology.me` → `localhost:8081`,
`https://pap.lmelp.ascot63.synology.me` → `localhost:8085`, HTTPS 443, profil d'accès
« reseau local ».

**`nas923` à la maison** : indice favorable, non prouvé. Le guide de migration fait tester
les conteneurs par `http://nas923:8081/` et `http://nas923:8000/health`
(`migration-nas.md` l. 222-223, commit `4379b8e` du 19/08/2026, rédigé pendant
l'installation du NAS), donc vraisemblablement depuis le réseau de la maison. Rien dans
les dépôts ne dit d'où vient la résolution de `nas923` (le nom système du NAS est
`nasds923`, docker-lmelp `CLAUDE.md` l. 376 ; `nas923` vient donc d'un DNS, d'AdGuard,
du routeur ou du VPN, pas du NAS lui-même). Vérification d'une ligne, depuis un poste
**sur le réseau de la maison, VPN coupé** :

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://nas923:8081/ && curl -sS -o /dev/null -w '%{http_code}\n' http://nas923:8085/health
```

Deux `200` : `nas923` marche partout.

**Recommandation.**

- Si la vérification passe : une seule forme, **`http://nas923:8081`**, pour les deux
  liens. pap reçoit une seule base en configuration, par exemple `LMELP_URL` dans le
  `.env` de docker-lmelp (`LMELP_URL=http://nas923:8081` dans `.env.nas.example`,
  `http://localhost:8080` dans `.env.example`), passée au service `pap` du compose. pap
  construit `${LMELP_URL}/emissions/AAAAMMJJ` et `${LMELP_URL}/emissions-anciennes`.
  Une seule variable suffit : lmelp et le back-office sont la même appli.
- Si elle échoue : correspondance configurée entre l'hôte par lequel pap est ouvert et
  la base lmelp, par exemple
  `LMELP_URLS=nas923=http://nas923:8081,pap.lmelp.ascot63.synology.me=https://lmelp.ascot63.synology.me`,
  pap choisissant selon l'en-tête `Host` de la requête (ou `location.hostname` côté
  page), avec la première entrée par défaut.

**Le prototype (`location.hostname` + port).** `src/lmelp_pap/prototype_accueil/index.html`
l. 131-133 fait `http://${location.hostname}:LMELP_PORT/…`. Par `nas923:8085`, cela donne
`http://nas923:8081/…`, juste. Par `pap.lmelp.ascot63.synology.me`, cela donne
`http://pap.lmelp.ascot63.synology.me:8081/…` : ça ne marche que si AdGuard réécrit ce
nom vers l'IP LAN du NAS (le port 8081 y est publié), en contournant le reverse proxy, en
HTTP. Tenable par accident, mais le port reste en dur dans pap et le lien ignore le nom
public `lmelp.ascot63.synology.me` (et sa PWA). À remplacer par la base en configuration.

Les liens sont de simples `<a href>` (navigation, pas d'appel `fetch`) : un lien
`http://` depuis pap servi en `https://` n'est pas bloqué comme contenu mixte.

## Incertitudes

- Résolution de `nas923` à la maison : à vérifier par la commande ci-dessus.
- `/emissions/AAAAMMJJ` vide tant que l'avis critique n'est pas généré : choix d'affichage
  à faire dans pap (lien conditionnel ou non).
- Le lien vers une ligne précise de `/emissions-anciennes` suppose une issue dans
  back-office-lmelp, optionnelle.
