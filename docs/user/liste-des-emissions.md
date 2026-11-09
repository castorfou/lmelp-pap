# Liste des émissions

La liste des émissions recense les émissions du Masque et la Plume **attestées** par au moins une source en ligne, de 1955 à aujourd'hui. Elle retient les émissions dont le thème inclut les livres, y compris les émissions mixtes (théâtre et littérature, par exemple), et celles dont le thème est inconnu. Les termes utilisés ici (émission, attestation, extrait, rapprochement…) sont définis dans le glossaire `CONTEXT.md` à la racine du dépôt.

## Générer la liste

```bash
uv run --active lmelp-pap emissions
```

La commande collecte chaque source dans un cache local, rapproche les attestations, puis écrit les fichiers de `data/processed/`. Une source dont la collecte est terminée n'est pas re-collectée : relancer la commande reconstruit la liste à partir du cache, sans accès réseau.

| Option | Effet |
|---|---|
| `--source NOM` | Ne collecte que cette source (répétable). La liste est construite avec toutes les sources déjà en cache. |
| `--refresh` | Re-collecte les sources choisies, même si leur cache est complet. |
| `--cache DOSSIER` | Dossier du cache (par défaut `data/raw/cache`). |
| `--sortie DOSSIER` | Dossier des fichiers produits (par défaut `data/processed`). |

Exemple : rafraîchir seulement radiofrance.fr, puis reconstruire la liste.

```bash
uv run --active lmelp-pap emissions --source radiofrance --refresh
```

### Prérequis pour la source INA

Le catalogue INA est une application JavaScript, parcourue avec Playwright. Il faut le navigateur Chromium et ses bibliothèques système :

```bash
uv run --active playwright install chromium
sudo -E env "PATH=$PATH" /tmp/venv/bin/playwright install-deps chromium
```

## Consulter la liste

Une page HTML présente la liste des émissions :
- une frise des émissions par année, où un clic sur une année filtre la liste ;
- une recherche sans tenir compte des accents ;
- des filtres par thème, par source, « avec enregistrement » et par type de doute, et un bouton « Effacer les filtres » ;
- le détail de chaque émission : description, attestations avec liens vers les sources, enregistrements et doutes.

```bash
uv run --active lmelp-pap page
```

La commande lit les CSV de `data/processed/` et écrit `docs/emissions/index.html`. Ce fichier autonome s'ouvre directement dans un navigateur, sans serveur. Les données et le code y sont embarqués ; seules les polices de caractères viennent d'Internet. Le fichier est régénéré à partir des CSV et n'est pas versionné.

| Option | Effet |
|---|---|
| `--donnees DOSSIER` | Dossier des CSV de la liste (par défaut `data/processed`). |
| `--sortie FICHIER` | Fichier HTML produit (par défaut `docs/emissions/index.html`). |

La page fait partie de la documentation et elle est publiée sur [castorfou.github.io/lmelp-pap/emissions/](https://castorfou.github.io/lmelp-pap/emissions/), régénérée à chaque mise à jour de la liste sur `main`. Pour construire ou prévisualiser la documentation en local, générer d'abord la page : sans elle, `mkdocs build --strict` échoue sur l'entrée « Liste des émissions » de la navigation.

```bash
uv run --active lmelp-pap page && uv run --active mkdocs serve
```

## Sources

| Source (`--source`) | Ce qu'elle atteste | Durée de collecte |
|---|---|---|
| `radiofrance` | Les pages podcast de radiofrance.fr : émissions depuis 2003 (date, thème, titre, description, animateurs, audio à partir de 2006), et extraits d'archives de 1956 à 2002. | environ 1 h (une requête par seconde) |
| `wayback_podcast` | Les fichiers audio du podcast conservés par la Wayback Machine : la date d'origine et l'identifiant d'archive Radio France (ITEMA) figurent dans le nom du fichier. Pas de thème. | moins d'une minute |
| `ina` | Toutes les notices de la collection « Le masque et la plume » du catalogue INA : date, titre, chaîne, heure, durée. Le thème vient du titre, et les notices de la facette Littérature reçoivent le thème livres. | plusieurs minutes |
| `anciennes_listes` | Les listes d'émissions de l'ancien site France Inter, archivées par la Wayback Machine : liste annuelle (2002-2008) et listes mensuelles (2009-2012), avec date et thème. Un dimanche « Pas de masque et la plume » n'atteste aucune émission. | quelques minutes |
| `lmelp` | Les émissions vérifiées à la main dans l'application lmelp (2014 à aujourd'hui), lues dans sa base MongoDB : page radiofrance.fr, titre, date de publication du podcast. C'est une **source vérifiée** (voir ci-dessous). | quelques secondes |

### La source vérifiée lmelp

Chaque émission retenue dans lmelp a été vérifiée à la main : ce que lmelp en dit fait foi, comme un arbitrage (`docs/adr/0003-lmelp-source-verifiee.md`).

- **Rattachement.** Une attestation lmelp se rattache à l'émission qui contient la fiche radiofrance.fr de même URL, et non par la date. Son identifiant (`source_id`) est le slug de cette fiche.
- **Date.** lmelp donne la date de **publication** du podcast, qui peut précéder ou suivre de quelques jours la première diffusion. Elle figure dans `attestations.csv`, mais ne date pas l'émission et n'entre pas dans le désaccord de date.
- **Thème.** Une émission attestée par lmelp est dans la liste, avec le thème `livres` seul : les thèmes des autres sources ne s'y ajoutent pas.
- **Complétude.** Depuis 2017, lmelp contient toutes les émissions littéraires : une émission de la liste absente de lmelp sur cette période est un doute. Avant 2017, son absence ne prouve rien.

La collecte lit la base en lecture seule, avec les variables `MONGO_URI` et `MONGO_DB` de l'environnement ou du fichier `.env` (voir `.env.example`). La base n'est accessible que depuis le devcontainer : sans `MONGO_URI`, la collecte lmelp est sautée avec un message, et la liste est construite avec le cache lmelp s'il existe.

Une fiche radiofrance.fr décrit soit l'émission entière, soit un **extrait** : une fiche par livre ou par film (moins de 25 minutes, contre 40 minutes à une heure pour une émission entière), ou une archive. Le nom d'un fichier audio Radio France signale les archives : dans `14007-04.12.1958-ITEMA_24232446-1958F4007E0005-….m4a`, la lettre `E` après `F4007` désigne un épisode d'une série d'archives (un extrait). La lettre `S` ne suffit pas à reconnaître une émission entière : les fiches par livre la portent aussi.

## Fichiers produits

Les quatre fichiers sont versionnés dans git et liés par l'identifiant d'émission, sa date de première diffusion (`1958-12-04`), suffixée en cas de collision (`1957-10-24-b`).

### `emissions.csv`

Une ligne par émission de la liste.

| Colonne | Contenu |
|---|---|
| `id` | Identifiant de l'émission. |
| `date` | Date de première diffusion. |
| `themes` | Thèmes séparés par `;` (`livres`, `cinéma`, `théâtre`, `opéra`, `télévision`, `musique`, `variétés`). Vide : thème inconnu. |
| `titre`, `description` | Titre et description, selon la source prioritaire. |
| `animateur` | Animateur précisé par une source, sinon déduit de la date. Vide pour les années de transition (1970, 1989, 2023). |
| `chaine`, `heure`, `duree` | Selon l'INA en priorité. |

### `attestations.csv`

Une ligne par source et par émission : `emission_id`, `source`, `source_id`, `date` et `themes` tels que la source les donne, `titre`, `url` de la notice ou de la page d'origine.

### `enregistrements.csv`

Une ligne par fichier audio : `emission_id`, `url`, `type` (`intégral` ou `extrait`), `sources` qui le donnent.

### `doutes.csv`

Une ligne par **doute** : un point d'une émission que les sources ne permettent pas d'affirmer avec certitude. Les doutes sont détectés à chaque construction, sur toutes les émissions rapprochées, qu'elles soient dans la liste ou non : une émission écartée de la liste peut ainsi avoir des doutes.

| Colonne | Contenu |
|---|---|
| `type` | Type de doute (voir ci-dessous). |
| `emission_id` | Identifiant de l'émission concernée. |
| `dans_la_liste` | `oui` si l'émission est dans `emissions.csv`, `non` sinon. |
| `source`, `source_id` | L'attestation en cause, quand le doute porte sur une seule attestation. |
| `detail` | Précisions : émissions rivales, dates données par chaque source. |

Types de doute :

- `rapprochement ambigu` : une attestation aurait pu être rapprochée de plusieurs émissions ;
- `désaccord de date` : les sources d'une même émission donnent des dates de première diffusion écartées de plus d'un jour ;
- `absente de lmelp` : une émission de la liste, datée de 2017 à la dernière émission de lmelp, que lmelp ne contient pas ;
- `sans fiche radiofrance` : une attestation lmelp dont la fiche radiofrance.fr est introuvable ; elle est rapprochée par la date.

`lmelp-pap emissions` affiche le nombre de doutes par type à la fin de la construction.

## Règles de construction

**Rapprochement.** Deux attestations décrivent la même émission si elles ont la même date, ou au plus trois jours d'écart avec des thèmes compatibles. Un thème inconnu est compatible avec tous les thèmes.

**Extraits.** Un extrait atteste son émission sans la décrire en entier :

- une fiche radiofrance.fr est un extrait si elle dure moins de 25 minutes ou si son fichier audio porte la lettre `E` ; une fiche sans durée décrit l'émission entière ;
- les champs de l'émission viennent d'abord d'une attestation de l'émission entière (fiche longue, notice INA), et seulement à défaut d'un extrait ; une émission ancienne prend ainsi le titre de sa notice INA (« Littérature »), le titre de l'extrait restant dans les attestations ;
- la durée ne vient jamais d'un extrait ;
- les thèmes se cumulent : ceux de toutes les attestations, extraits compris, sauf quand lmelp atteste l'émission ;
- une archive dont la durée atteint 90 % de la durée de diffusion INA est l'émission entière, pas un extrait.

**Fusion.** Chaque champ de l'émission vient de la source la plus prioritaire qui le renseigne, parmi les attestations de l'émission entière d'abord (voir ci-dessus) :

| Champ | Priorité |
|---|---|
| Date | radiofrance > ina > anciennes_listes > wayback_podcast |
| Titre, description | radiofrance > ina |
| Chaîne, heure, durée | ina > radiofrance |
| Animateur | radiofrance > ina, sinon déduit de la date |

Les enregistrements de toutes les sources sont conservés. Leur type (`intégral` ou `extrait`) vaut pour tous les fichiers d'une même archive Radio France (ITEMA) : la Wayback Machine ne voit que le nom d'un fichier, radiofrance.fr en connaît la durée. Les décisions sur le format et le périmètre de la liste sont dans `docs/adr/`.
