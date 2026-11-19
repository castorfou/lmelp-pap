# Conventions de stockage audio de lmelp sur le NAS

Recherche pour l'issue #53 (carte #48). Question : comment l'écosystème lmelp stocke et
référence l'audio de ses épisodes, pour que lmelp-pap puisse un jour lui remettre des
enregistrements intégraux.

Sources primaires lues le 19/11/2026 :

- `castorfou/back-office-lmelp` @ `a3b40ec` (code de production de l'ingestion audio)
- `castorfou/docker-lmelp` @ `da9f72d` (déploiement NAS : compose, `.env.nas.example`, docs)
- `castorfou/lmelp` @ `8320480` (appli historique, notebooks nbdev)
- `castorfou/lmelp-mobile` (export SQLite)
- base Mongo `masque_et_la_plume`, collection `episodes`, lue en lecture seule (245 documents)

Aucun secret n'est reproduit ici.

## Réponse courte

- L'audio vit sur le NAS Synology dans `/volume1/docker/lmelp/audios`, monté dans le
  conteneur backend du back-office sur `/app/audios`. Variables : `AUDIO_PATH` (côté
  hôte, docker-compose) et `AUDIO_STORAGE_PATH=/app/audios` (côté conteneur).
- Un fichier est rangé dans `<année>/<nom d'origine>` : l'année de la date de l'épisode,
  et le nom exact du fichier dans l'URL radiofrance (`os.path.basename(url)`), sans
  renommage ni conversion (`.m4a` ou `.mp3`, tel que publié).
- En base, l'épisode porte `url` (URL du fichier audio source) et `audio_rel_filename`
  (chemin relatif à la racine audio, par ex. `2024/14007-21.07.2024-ITEMA_…-27.m4a`).
  `episode_page_url` (page radiofrance.fr) est facultatif.
- Un épisode entre par deux chemins seulement : la synchro du flux RSS France Inter
  (`POST /api/rss/sync`) ou l'ajout manuel depuis une page
  `https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/…`
  (`POST /api/episodes/from-radiofrance-page`). Aucun chemin n'accepte un fichier local
  ni une URL hors radiofrance.fr.
- Le back-office identifie un épisode par `_id` Mongo ; les dédoublonnages se font par
  (`titre`, `date`) pour le RSS et par **jour calendaire UTC** pour l'ajout manuel.

## 1. Chemin de stockage

| Couche | Valeur | Source |
|---|---|---|
| Hôte NAS | `AUDIO_PATH=/volume1/docker/lmelp/audios` | `docker-lmelp/.env.nas.example:126` |
| Hôte (dév laptop) | `AUDIO_PATH=./data/audios` (défaut) | `docker-lmelp/.env.example:124`, `docker-compose.yml:77` |
| Montage | `${AUDIO_PATH:-./data/audios}:/app/audios` sur le service `backend` | `docker-lmelp/docker-compose.yml:77` |
| Conteneur | `AUDIO_STORAGE_PATH=/app/audios` (fixe) | `docker-lmelp/docker-compose.yml:96` |
| Défaut du code | `<cwd>/data/audios` si `AUDIO_STORAGE_PATH` absent | `back-office-lmelp/src/back_office_lmelp/settings.py:110-119` |

Le dossier se crée depuis DSM sous `/docker/lmelp/audios` (vu comme
`/volume1/docker/lmelp/audios` en SSH) ; il pesait environ 10 Go en août 2026
(`docker-lmelp/docs/user/migration-nas.md`, étapes 1 et 4).

Le dossier contient aussi, à côté de chaque audio, un éventuel cache de transcription
`<même nom>.txt` (`pgx_transcription_runner.py:346`). Pour la transcription, l'audio est
copié par `scp` vers PGX dans `PGX_REMOTE_AUDIO_ROOT/<année>/` et converti là-bas en
`.mp3` ; la copie locale reste inchangée (`pgx_transcription_runner.py:385-426`).

Ce devcontainer n'a pas accès au dossier audio, seulement à la base Mongo.

## 2. Nommage et format

`RssSyncService.download_audio(audio_url, episode_date)`
(`back-office-lmelp/src/back_office_lmelp/services/rss_sync_service.py:177-214`) :

```python
year = str(episode_date.year)
basename = os.path.basename(audio_url)
audio_rel_filename = f"{year}/{basename}"
```

- Dossier : année de `date` (la date stockée, en UTC). Dans la base, 243 épisodes sur 245
  respectent cette règle.
- Nom : celui de l'URL, conservé tel quel. Exemples réels :
  - `1958/14007-18.12.1958-ITEMA_23787915-2024F4007E0108-27.m4a`
  - `2024/14007-21.07.2024-ITEMA_23808923-2024F4007S0203-27.m4a`
  - `2026/24613-15.11.2026-ITEMA_24753344-2026F4007S0319-NET_MFI_<uuid>-27-<hash>.m4a`
- Format : celui de la source, sans conversion. Types acceptés depuis le flux RSS :
  `audio/mpeg`, `audio/x-m4a`, `audio/mp4`, `audio/aac` (`rss_sync_service.py:29`).
  En base : 114 `.m4a`, 131 `.mp3`.
- Si le fichier existe déjà, il n'est pas retéléchargé (le nom fait office de clé).
  Le téléchargement passe par un `.part` renommé à la fin (`rss_sync_service.py:189-212`).

L'appli historique `lmelp` suit la même convention (`AUDIO_PATH="audios"` relatif à la
racine git, sous-dossier année, `basename` de l'URL) :
`lmelp/nbs/config.py:156-182`, `lmelp/nbs/mongo_episode.py:639-660`.

## 3. Lien fichier ↔ épisode en base (collection `episodes`)

Champs présents (sur 245 documents) : `_id`, `titre`, `date`, `description`, `url` (245),
`audio_rel_filename` (245), `duree` (245, secondes), `type` (245), `masked` (80),
`episode_page_url` (189), `transcription`, `source` (1), plus quelques champs de
correction (`titre_corrige`, `description_corrigee`…).

| Champ | Sens |
|---|---|
| `url` | URL du fichier audio d'origine (hôtes : `media.radiofrance-podcast.net`, `proxycast.radiofrance.fr`, `rf.proxycast.org`) |
| `audio_rel_filename` | chemin relatif à `AUDIO_STORAGE_PATH` ; seul lien entre document et fichier |
| `episode_page_url` | page radiofrance.fr de l'épisode (absente pour 56 épisodes anciens) |
| `date` | date de publication du podcast, `datetime` naïf en UTC |
| `duree` | durée en secondes ; 53 épisodes font moins de 30 min (extraits d'archives, ex. « Le Masque et les Goncourt » 1958, 6 min) |
| `type` | `livres` (classification LLM pour le RSS, forcé pour l'ajout manuel) |
| `source` | `radiofrance_page` pour un ajout manuel ; absent pour le RSS et l'historique |

Construction du document : `rss_sync_service.py:241-260` (RSS),
`manual_episode_service.py:201-215` (ajout manuel). La collection `emissions` référence
l'épisode par `episode_id` ; elle n'a pas de champ audio. Aucun index autre que `_id`.

## 4. Comment un épisode entre dans la base

1. **Flux RSS** — `POST /api/rss/sync`, déclenché par Automatisch
   (`rss_sync_service.py`, `RSS_MASQUE_ET_LA_PLUME_URL` par défaut
   `https://radiofrance-podcast.net/podcast09/rss_14007.xml`). Garde les entrées plus
   récentes que la dernière connue, de durée ≥ `RSS_DUREE_MINI_MINUTES` (15), classées
   « livres » par LLM ; télécharge l'audio puis insère l'épisode ; trace chaque run dans
   `rss_download_logs`.
2. **Ajout manuel** — page frontend « Ajouter une émission »,
   `POST /api/episodes/from-radiofrance-page` (`app.py:3677`,
   `manual_episode_service.py`). Contraintes :
   - URL `https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/<slug>` ;
   - la page doit contenir un JSON-LD `RadioEpisode` avec `mainEntity.contentUrl`
     (audio), `dateCreated` et `duration` ;
   - durée ≥ 30 min (`MIN_FULL_EPISODE_SECONDS = 1800`), sinon refus 422 « séquence » ;
   - aucun épisode le même jour UTC (`find_episode_on_same_day`), sinon 409 ;
   - l'épisode n'est inséré qu'une fois l'audio sur disque, puis la transcription PGX
     est lancée.

Les épisodes anciens (extraits d'archives 1958-2015) viennent de l'appli historique
`lmelp` (notebooks `21 read historical episodes`, `08 download mp3 from db info`), même
convention de stockage.

## 5. Comment le back-office identifie un épisode

- Identifiant interne : `_id` (ObjectId) ; `emissions.episode_id` y renvoie.
- Dédoublonnage RSS : égalité exacte (`titre`, `date`)
  (`mongodb_service.py:317-324`).
- Dédoublonnage ajout manuel : même jour calendaire UTC (`mongodb_service.py:326`).
- URL radiofrance : `episode_page_url` (slug du type
  `le-masque-et-la-plume-du-dimanche-15-novembre-2026-1230115`). Elle sert à
  l'ajout manuel, à l'extraction des métadonnées pour les avis critiques
  (`avis_critiques_generation_service.py:620-731`, qui la cherche et la renseigne si
  absente) et à l'export mobile (`lmelp-mobile/scripts/export_mongo_to_sqlite.py:270`,
  repli sur `url`). Ce n'est pas une clé d'unicité.
- lmelp-pap identifie déjà une émission lmelp par le dernier segment de
  `episode_page_url` (`src/lmelp_pap/sources/lmelp.py`).

## Conséquences pour lmelp-pap (carte #48)

- **Lien** : un intégral radiofrance.fr avec page `www.radiofrance.fr/.../le-masque-et-la-plume/…`
  se remet tel quel ; le back-office sait déjà l'ingérer (ajout manuel), à condition
  que la page ait le JSON-LD et que l'audio dure ≥ 30 min.
- **Fichier rapatrié** (INA, Wayback, cassette) : aucun chemin d'entrée n'existe dans
  le back-office. Pour s'aligner sur la convention, un fichier déposé dans
  `/volume1/docker/lmelp/audios/<année>/<nom>` avec un document `episodes` dont
  `audio_rel_filename = "<année>/<nom>"` suffirait côté stockage, mais `url` (non nul
  partout aujourd'hui) n'aurait pas de valeur radiofrance et l'insertion reste à
  définir dans back-office-lmelp.
- **Format** : aucune contrainte imposée (m4a et mp3 coexistent ; PGX convertit en mp3).
- **Nom** : le `basename` doit être unique dans le dossier de l'année ; les noms
  radiofrance le sont (identifiant ITEMA). Un fichier d'autre provenance a besoin d'une
  règle de nommage qui garantisse cette unicité (par ex. date + source).
- **Date** : le dossier année et le dédoublonnage reposent sur la date UTC ; une
  émission ancienne doit arriver avec sa date de première diffusion pour éviter un
  faux doublon au même jour.
