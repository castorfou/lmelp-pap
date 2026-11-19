# Open API Radio France : ce qu'elle peut donner pour les archives du Masque

Ticket : #49 (carte #48). Constats du 2026-11-19, établis sans clé d'API, à partir de la documentation publique, des CGU et d'exemples de code publics.

Légende : **[vérifié]** = lu dans une source primaire ou constaté par requête ; **[supposé]** = déduit, à confirmer avec une clé.

## Réponse courte

- L'Open API est une API GraphQL sur les **émissions** (`Show`), leurs **diffusions** (`Diffusion`), la **grille** des programmes (`grid`, `Step`) et l'**épisode de podcast** rattaché à une diffusion (`podcastEpisode` : `url`, `playerUrl`, `duration`, `created`). **[vérifié]**
- Elle ne documente **aucune notion de « manifestation »** ni de type intégral/extrait : une diffusion porte au plus un épisode de podcast. Le type se déduit comme aujourd'hui, du nom de fichier (`F4007S…`/`F4007E…`, voir `audio_radiofrance.py`) et de la durée. **[vérifié pour la doc ; l'absence dans le schéma complet reste à vérifier par introspection]**
- Le Masque se trouve par `showByUrl` / `diffusionsOfShowByUrl` avec l'URL déjà utilisée par la collecte : `https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume`. **[vérifié pour la forme des requêtes]**
- Profondeur probable : celle du site radiofrance.fr, que lmelp-pap moissonne déjà (2 277 épisodes, émissions complètes depuis 2003, environ 340 extraits d'archives 1956-2002). On ne doit **pas** attendre d'intégraux antérieurs à 2011 qui manqueraient au site. **[supposé]**
- Quota : **1 000 requêtes par jour et par clé**, au-delà l'accès est bloqué. Les CGU interdisent de **stocker ou mettre en cache** les sons (« Contenu éditorial ») et les données, et d'en faire un agrégateur de podcasts : l'audio doit être repris par lien hypertexte. **[vérifié]**
- La couverture réelle reste à vérifier avec la clé : voir les requêtes de la section 5.

## 1. Accès, format, documentation

- Point d'accès : `POST https://openapi.radiofrance.fr` (exemples : `https://openapi.radiofrance.fr/v1/graphql`), au format GraphQL. La clé passe dans l'en-tête HTTP `x-token` ou en paramètre d'URL `x-token`. **[vérifié]** — [Introduction](https://developers.radiofrance.fr/doc/)
- Sans clé, `POST https://openapi.radiofrance.fr/v1/graphql` renvoie HTTP 403 `{"message":"Unauthorized: Missing x-token"}`, y compris pour une requête d'introspection. **[vérifié le 2026-11-19]**
- Le schéma complet n'est pas publié : il est « (sommairement) auto-documenté » dans l'explorateur `https://openapi.radiofrance.fr/v1/graphql?x-token=<clé>`, protégé par la clé. **[vérifié]** — [Introduction](https://developers.radiofrance.fr/doc/)
- La documentation publique se limite à six pages : introduction, glossaire, FAQ, technologies, et un tutoriel (marques, stations locales, grille, émission, taxonomies). **[vérifié]** — [sitemap](https://developers.radiofrance.fr/doc/sitemap.xml)
- L'API existe depuis 2018 (Node.js/Fastify). Support : `support.openapi@radiofrance.com`. **[vérifié]** — [Technologies](https://developers.radiofrance.fr/doc/technologies)

## 2. Entités exposées

D'après le glossaire **[vérifié]** — [Lexique](https://developers.radiofrance.fr/doc/glosssary) :

| Terme Radio France | Type API | Ce que c'est | Correspondance lmelp-pap (CONTEXT.md) |
|---|---|---|---|
| Marque | `Brand` | France Inter (`FRANCEINTER`), France Culture… | chaîne |
| Émission | `Show` | une émission de radio sur une station | le Masque et la Plume (la série, pas une émission au sens de CONTEXT.md) |
| Diffusion | `Diffusion` | « une émission de radio diffusée à une date donnée » | une émission ou un extrait publié (voir plus bas) |
| Chronique | `Diffusion` enfant | sous-partie d'une diffusion (`childrenSteps`) | — |
| Grille / zone de temps | `grid`, `paginatedGrid`, `Step` (`DiffusionStep`, `TrackStep`, `BlankStep`) | programme d'une station sur une période | diffusion à l'antenne |
| Podcast | `Podcast` / `podcastEpisode` | « épisode de podcast (url du fichier son, date de création, durée) » | enregistrement |
| Taxonomie | `Taxonomy` | thème ou tag | thème (en partie) |
| Personnalité | `Personality` | personne physique ou morale | critiques, animateur |

Champs attestés dans la documentation officielle **[vérifié]** — [tutoriel Émission](https://developers.radiofrance.fr/doc/tutorial-by-example/show), [Grille](https://developers.radiofrance.fr/doc/tutorial-by-example/program-grid), [Taxonomies](https://developers.radiofrance.fr/doc/tutorial-by-example/taxonomies) :

- `showByUrl(url)` → `id title url standFirst podcast { rss itunes } taxonomiesConnection personalitiesConnection`.
- `diffusionsOfShowByUrl(url, first, after)` → connexion paginée (`edges { cursor node }`) de `Diffusion { id title url published_date podcastEpisode { url playerUrl title } }`. La doc la présente comme « les **dernières** diffusions d'une émission ».
- `shows(station, first, after)` → émissions d'une station, chacune avec `diffusionsConnection`.
- `diffusions(station, themes | subthemes | subsubthemes, …)` → diffusions filtrées par taxonomie.
- `grid(start, end, station)` (100 éléments au plus) et `paginatedGrid(start, end, station, after)` : fenêtre **inférieure à 24 h**, horodatages POSIX en secondes UTC.
- `Diffusion.playerUrl` : URL du lecteur web Radio France, « disponible dans toutes les diffusions ». — [FAQ](https://developers.radiofrance.fr/doc/faq)

Champs attestés seulement par du code public **[vérifié dans le code, non garanti par Radio France]** :

- `podcastEpisode { id title url playerUrl duration created }` et `Diffusion.show { id title }` — [RadioFrance-kafka-elasticsearch-pipeline, RADIOFRANCE_API.md](https://github.com/khaledbouabdallah/RadioFrance-kafka-elasticsearch-pipeline/blob/68da0d71ef273dde8b71c1a9e3a54b6488613140/RADIOFRANCE_API.md) ; [radiofrance-downloader, api.py](https://github.com/chocobn69/radiofrance-downloader/blob/4f3123d3264cf6bc756194143faf761967cf6f34/src/radiofrance_downloader/api.py). Ce second client pagine `diffusionsOfShowByUrl` jusqu'au bout avec `after` et traite `published_date` comme une chaîne d'horodatage POSIX, `duration` comme un entier (secondes).

### Intégral ou extrait ?

- Aucun champ documenté ne distingue un intégral d'un extrait, et un seul `podcastEpisode` est rattaché à chaque diffusion. **[vérifié pour la doc]** Le mot « manifestation » (modèle interne du site radiofrance.fr) n'apparaît nulle part dans la doc publique. **[vérifié]**
- Le type se déduit donc comme dans `src/lmelp_pap/sources/radiofrance.py` et `audio_radiofrance.py` : code `F4007S…` (émission diffusée) ou `F4007E…` (épisode d'une série d'archives), complété par le seuil de durée de 25 min. **[supposé : même URL `media.radiofrance-podcast.net` que celle lue sur le site]**

## 3. Trouver le Masque et la Plume

- URL de l'émission, déjà utilisée par `src/lmelp_pap/collecte.py` : `https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume`. **[vérifié dans le dépôt]**
- Requêtes : `showByUrl(url: …)` pour l'`id`, puis `diffusionsOfShowByUrl(url: …, first: N, after: curseur)` pour toutes les diffusions. **[vérifié pour la forme]**
- Les extraits d'archives (« 1956-1981 : les entretiens du Masque »…) sont publiés sur la page du Masque elle-même : ils devraient sortir de la même requête. Une série d'archives rangée dans une autre émission se repère avec `shows(station: FRANCEINTER)` en filtrant les titres contenant « masque ». **[supposé]**

## 4. Profondeur historique probable

- L'Open API sert « les données des programmes […] et podcasts » et le « Contenu éditorial » est défini comme les sons « accessibles en streaming à la demande et sous forme de podcasts depuis les sites Internet de Radio France ». Elle expose donc ce que publie radiofrance.fr, pas le fonds d'archives (INA, ITEMA non publiés). **[vérifié pour les définitions des CGU, art. 1.6-1.7]** — [CGU du 06/06/2019](https://developers.radiofrance.fr/DN_API_CGU_vdaj06062019_fr.pdf)
- Le site, déjà moissonné, compte 2 277 épisodes : émissions complètes continues depuis le 4 janvier 2003, et environ 340 extraits d'archives datés de 1956 à 2002. Pour 2003-2005 la fiche indique « Cet épisode n'est plus écoutable, les droits d'auteur ont expiré ». **[vérifié]** — `research_notes/Sources Masque et la Plume/archives_web_radiofrance_ina.md`, section 2.
- Dans `data/processed/enregistrements.csv`, les enregistrements de source `radiofrance` antérieurs à 2011 sont tous des extraits, sauf un (1980-02-24, `F4007E`, 1 h 02, classé intégral par sa durée). 143 émissions antérieures à 2011 n'ont qu'un extrait Radio France. **[vérifié dans le dépôt]**
- Ce qu'on peut en attendre **[supposé]** :
  - pas d'intégral 1955-2002 absent du site : le back-office est le même ;
  - pour 2003-2010, des diffusions complètes existent, mais leur `podcastEpisode` est probablement vide (droits expirés) ; c'est le point le plus utile à vérifier ;
  - la `grid` avant 2003, et à plus forte raison avant 1970 (horodatages négatifs), est probablement vide : la grille documentée commence avec les programmes numérisés du site ;
  - un gain marginal : durées exactes en secondes, `id` stables, `created` (date de publication) au lieu du scraping HTML/JSON-LD.

## 5. Requêtes à lancer avec la clé

Coût total : une trentaine de requêtes, loin du quota de 1 000. Mode d'emploi, avec la clé dans une variable d'environnement (ne jamais la commiter) :

```bash
export RF_TOKEN=…   # clé reçue par courriel
rf() { curl -s https://openapi.radiofrance.fr/v1/graphql \
  -H "x-token: $RF_TOKEN" -H 'content-type: application/json' \
  --data "$(jq -n --arg q "$1" --argjson v "${2:-null}" '{query:$q,variables:$v}')"; }
```

### R1. Le schéma réel (introspection)

Vérifie les noms de champs, l'existence d'un type « manifestation » ou d'un champ intégral/extrait, et les arguments de pagination ou de tri.

```graphql
{
  query: __type(name: "Query") { fields { name args { name type { name kind ofType { name } } } } }
  diffusion: __type(name: "Diffusion") { fields { name type { name kind ofType { name } } } }
  podcast: __type(name: "PodcastEpisode") { fields { name type { name kind ofType { name } } } }
  show: __type(name: "Show") { fields { name type { name kind ofType { name } } } }
}
```

Puis, si un nom diffère (`Podcast` au lieu de `PodcastEpisode`, par exemple) : `{ __schema { types { name } } }` et chercher `manifest`, `media`, `audio`, `expression`.

### R2. L'émission

```graphql
{
  showByUrl(url: "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume") {
    id title url standFirst
    podcast { rss itunes }
  }
}
```

### R3. Toutes les diffusions du Masque (la plus ancienne en fin de liste)

À répéter avec `after` = dernier `cursor` reçu jusqu'à une page vide (2 277 épisodes → environ 23 pages de 100). Noter le nombre total, l'ordre, la plus ancienne `published_date`, et pour chaque diffusion la présence de `podcastEpisode`.

```graphql
query ($after: String) {
  diffusionsOfShowByUrl(
    url: "https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume"
    first: 100
    after: $after
  ) {
    edges {
      cursor
      node {
        id title url published_date playerUrl
        podcastEpisode { id title url playerUrl duration created }
      }
    }
  }
}
```

Variables : `{}` pour la première page, puis `{"after": "<cursor>"}`. Si `first: 100` est refusé, essayer 50.

Analyse locale suggérée : garder les nœuds dont `published_date` < `1293836400` (1er janvier 2011), lire `podcastEpisode.url` avec `lire_nom_fichier` et comparer à `data/processed/enregistrements.csv` : un fichier `F4007S`, ou une durée ≥ 25 min, pour une émission sans intégral serait un gain.

### R4. Les diffusions de 2003-2010 : écoutables ou non ?

Sur deux diffusions complètes repérées en R3 (par exemple une « Livres » de 2005 et une de 2009), lire le détail. Si l'argument diffère, R1 donne le nom de la requête par identifiant.

```graphql
{
  diffusion(id: "<id d'une diffusion de 2005>") {
    id title url published_date playerUrl
    podcastEpisode { url duration created }
    show { id title }
  }
}
```

### R5. La grille à des dates anciennes (fenêtres < 24 h, heure de Paris)

Une requête par date ; si la réponse est vide, la grille ne remonte pas jusque-là.

```graphql
{
  d2010: grid(start: 1293318000, end: 1293404399, station: FRANCEINTER) { ...masque }
  d2005: grid(start: 1135465200, end: 1135551599, station: FRANCEINTER) { ...masque }
  d1980: grid(start: 320194800, end: 320281199, station: FRANCEINTER) { ...masque }
  d1958: grid(start: -349578000, end: -349491601, station: FRANCEINTER) { ...masque }
}
fragment masque on Step {
  ... on DiffusionStep {
    start end
    diffusion { id title url show { title } podcastEpisode { url duration } }
  }
}
```

Dates : 26 décembre 2010, 25 décembre 2005, 24 février 1980 (seul « intégral » ancien connu), 4 décembre 1958 (extrait « Louis Aragon » connu). Si les fragments sur une interface sont refusés, écrire les `... on DiffusionStep` directement dans chaque alias.

### R6. Une série d'archives du Masque ailleurs ?

À paginer comme R3 (`after`) ; quelques pages suffisent si l'ordre est alphabétique ou si le nombre d'émissions de France Inter reste modeste.

```graphql
query ($after: String) {
  shows(station: FRANCEINTER, first: 100, after: $after) {
    edges { cursor node { id title url } }
  }
}
```

Chercher localement les titres contenant « masque », « plume » ou « archives ».

## 6. Conditions d'usage et quotas

- **Quota** : 1 000 requêtes par jour et par clé, gratuit jusque-là ; au-delà, Radio France bloque l'accès et propose un contrat de partenariat. Contourner le seuil (plusieurs clés, par exemple) est interdit. **[vérifié]** — [FAQ](https://developers.radiofrance.fr/doc/faq) ; CGU art. 5.3 et 9.1.
- **Clé** : personnelle, délivrée après validation d'un projet décrit en quelques mots ; usage strictement personnel. **[vérifié]** — CGU art. 4.1.
- **Pas de stockage** : « Reproduire, stocker et/ou héberger le Contenu éditorial, y compris mise en mémoire cache » est interdit ; le son doit être repris « au moyen de liens hypertextes ». La FAQ étend cela aux données : « vous ne pouvez pas avoir un serveur en coupure (proxy) qui stockerait les données ». **[vérifié]** — CGU art. 5.3 ; [FAQ](https://developers.radiofrance.fr/doc/faq)
- **Pas d'agrégation** de podcasts ou de flux, même non commerciale ; pas d'usage commercial ; pas de modification des données. **[vérifié]** — CGU art. 5.3 ; FAQ.
- **Crédit** obligatoire dans l'application : « données fournies par l'Open API Radio France ». **[vérifié]** — CGU art. 5.4.

Conséquences pour la carte #48 **[supposé, lecture non juridique]** :

- Un **lien** vers `media.radiofrance-podcast.net` ou `playerUrl` est le mode de reprise prévu par les CGU : il convient au livrable « lien ».
- **Rapatrier sur le NAS** un son obtenu via l'API contredit l'art. 5.3. Les URL de ces fichiers sont toutefois publiques sur radiofrance.fr et dans le flux RSS, hors API : la question relève de la décision sur le stockage (#48), pas de l'API seule.
- Écrire dans `enregistrements.csv` des URL ou durées lues dans l'API s'apparente au stockage de données que la FAQ proscrit ; s'en servir pour **vérifier** les données déjà moissonnées sur le site pose moins de difficulté.

## 7. Ce qui reste ouvert

- Le schéma exact (R1) et l'éventuel champ intégral/extrait.
- La profondeur réelle de `diffusionsOfShowByUrl` (toute l'histoire ou seulement « les dernières ») et la présence d'un `podcastEpisode` pour 2003-2010 (R3, R4).
- La profondeur de la grille (R5).
- Si R3 ne rapporte rien de plus que le site, l'API n'apporte aucun intégral nouveau et le brouillard 1955-2009 se lève ailleurs (INA, Wayback, passionnés).
