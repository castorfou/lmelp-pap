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
- des filtres par thème, par source, « avec enregistrement » et « à vérifier » ;
- le détail de chaque émission : description, attestations avec liens vers les sources, enregistrements et signalements.

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

### `rapport_rapprochement.csv`

Les cas à vérifier à la main :

- `ambigu` : une attestation aurait pu être rapprochée de plusieurs émissions ;
- `désaccord de date` : les sources d'une même émission donnent des dates écartées de plus d'un jour.

## Règles de construction

**Rapprochement.** Deux attestations décrivent la même émission si elles ont la même date, ou au plus trois jours d'écart avec des thèmes compatibles. Un thème inconnu est compatible avec tous les thèmes.

**Extraits.** Un extrait atteste son émission sans la décrire en entier :

- une fiche radiofrance.fr est un extrait si elle dure moins de 25 minutes ou si son fichier audio porte la lettre `E` ; une fiche sans durée décrit l'émission entière ;
- les champs de l'émission viennent d'abord d'une attestation de l'émission entière (fiche longue, notice INA), et seulement à défaut d'un extrait ; une émission ancienne prend ainsi le titre de sa notice INA (« Littérature »), le titre de l'extrait restant dans les attestations ;
- la durée ne vient jamais d'un extrait ;
- les thèmes se cumulent : ceux de toutes les attestations, extraits compris ;
- une archive dont la durée atteint 90 % de la durée de diffusion INA est l'émission entière, pas un extrait.

**Fusion.** Chaque champ de l'émission vient de la source la plus prioritaire qui le renseigne, parmi les attestations de l'émission entière d'abord (voir ci-dessus) :

| Champ | Priorité |
|---|---|
| Date | radiofrance > ina > anciennes_listes > wayback_podcast |
| Titre, description | radiofrance > ina |
| Chaîne, heure, durée | ina > radiofrance |
| Animateur | radiofrance > ina, sinon déduit de la date |

Les enregistrements de toutes les sources sont conservés. Leur type (`intégral` ou `extrait`) vaut pour tous les fichiers d'une même archive Radio France (ITEMA) : la Wayback Machine ne voit que le nom d'un fichier, radiofrance.fr en connaît la durée. Les décisions sur le format et le périmètre de la liste sont dans `docs/adr/`.
