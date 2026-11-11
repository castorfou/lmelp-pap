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
| `--arbitrages FICHIER` | Fichier des arbitrages (par défaut `arbitrages.csv` dans le dossier de sortie). Sans ce fichier, aucun arbitrage n'est appliqué. |

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
- des filtres par thème, par source, « avec enregistrement » et par doute, et un bouton « Effacer les filtres ». Le filtre « Doute » propose « Au moins un doute », « À trancher » (les émissions qui ont au moins un doute, sans renvoi à l'écoute), « À écouter » (les émissions renvoyées à l'écoute), puis chaque type de doute ;
- un badge « doute » sur la ligne d'une émission qui a des doutes, « à écouter » si elle est renvoyée à l'écoute ;
- dans les sources de chaque émission, le badge vert `lmelp ✓` de la source vérifiée, les autres sources en gris ;
- le détail de chaque émission : description, attestations avec liens vers les sources, enregistrements avec leur durée quand elle est connue (`extrait · 3:56 · 14007-18.10.1975-…m4a`) et doutes ;
- une marque « ✎ arbitré » à côté d'un thème fixé par un arbitrage, avec la justification au survol.

```bash
uv run --active lmelp-pap page
```

La frise compte les émissions qui passent tous les filtres sauf l'année : avec « Thème : inconnu », chaque barre ne compte que les émissions de thème inconnu de son année, l'échelle verticale se recalcule sur la plus haute barre et l'infobulle donne les mêmes nombres. Elle montre toujours toutes les années, puisqu'elle sert à en choisir une : choisir une année ne change pas les barres des autres. Sans filtre, son en-tête invite à cliquer une année ; avec des filtres, il les affiche, chacun avec une croix qui le retire, suivis d'un lien « Tout effacer » qui fait comme « Effacer les filtres » :

```
Année 2010 ×   Thème : inconnu ×   Avec enregistrement ×   « Duras » ×        Tout effacer
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

Les quatre fichiers produits par la commande sont versionnés dans git et liés par l'identifiant d'émission, sa date de première diffusion (`1958-12-04`), suffixée en cas de collision (`1957-10-24-b`).

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
| `arbitrage` | `thème` si les thèmes viennent d'un arbitrage, `écoute` si l'émission est renvoyée à l'écoute, vide sinon. |
| `justification_arbitrage` | La justification de cet arbitrage ou de ce renvoi, s'il en a une. |

### `attestations.csv`

Une ligne par source et par émission : `emission_id`, `source`, `source_id`, `date` et `themes` tels que la source les donne, `titre`, `url` de la notice ou de la page d'origine.

### `enregistrements.csv`

Une ligne par fichier audio : `emission_id`, `url`, `type` (`intégral` ou `extrait`), `sources` qui le donnent, `duree`.

La `duree` (`HH:MM:SS`) est celle de la fiche radiofrance.fr qui publie le fichier ; elle vaut aussi pour les autres encodages du même fichier (même nom au suffixe près : `-22.mp3`, `-27.m4a`). Elle est vide quand aucune source ne la connaît, par exemple pour un fichier connu seulement par la Wayback Machine. Elle permet de juger, sans l'écouter, si un enregistrement est un court extrait : la durée de l'émission, dans `emissions.csv`, ne vient jamais d'un extrait.

### `doutes.csv`

Une ligne par **doute** : un point d'une émission que les sources ne permettent pas d'affirmer avec certitude. Les doutes sont détectés à chaque construction, sur toutes les émissions rapprochées, qu'elles soient dans la liste ou non : une émission écartée de la liste peut ainsi avoir des doutes.

| Colonne | Contenu |
|---|---|
| `type` | Type de doute (voir ci-dessous). |
| `emission_id` | Identifiant de l'émission concernée. |
| `dans_la_liste` | `oui` si l'émission est dans `emissions.csv`, `non` sinon. |
| `source`, `source_id` | L'attestation en cause, quand le doute porte sur une seule attestation. |
| `detail` | Précisions : émissions rivales, dates données par chaque source. |
| `a_ecouter` | `oui` si l'émission, dans la liste, est renvoyée à l'écoute ; `non` sinon. |

Types de doute :

- `rapprochement ambigu` : une attestation aurait pu être rapprochée de plusieurs émissions ;
- `désaccord de date` : les sources d'une même émission donnent des dates de première diffusion écartées de plus d'un jour ;
- `absente de lmelp` : une émission de la liste, datée de 2017 à la dernière émission de lmelp, que lmelp ne contient pas ;
- `sans fiche radiofrance` : une attestation lmelp dont la fiche radiofrance.fr est introuvable ; elle est rapprochée par la date ;
- `thème inconnu` : aucune source ne donne le thème de l'émission ;
- `thèmes divergents` : les attestations de l'émission entière ne donnent pas les mêmes thèmes, ou un extrait porte un thème qu'aucune d'elles ne donne. Des extraits aux thèmes différents (une fiche par livre, une par film) décrivent une émission mixte, sans divergence ;
- `collision` : une autre émission a la même date de première diffusion ; le doute porte sur l'émission suffixée (`-b`, `-c`) ;
- `republication` : un enregistrement d'une attestation porte, dans le nom de son fichier, une date à plus de trois jours de la sienne : une émission remise en ligne plus tard, ou une fiche rattachée à l'enregistrement d'une autre émission ;
- `attestation fragile` : l'émission n'est attestée que par des extraits, que par la Wayback Machine, ou que par les deux ;
- `contradiction lmelp` : un arbitrage contredit lmelp, en déclarant inexistante une émission vérifiée ou en lui donnant un autre thème que `livres` seul. L'arbitrage s'applique, mais la contradiction reste signalée ;
- `arbitrage orphelin` : un arbitrage porte sur une attestation qu'aucune source ne donne plus ; il n'a aucun effet. Le doute n'a pas d'`emission_id` : `source` et `source_id` désignent l'attestation introuvable.

Un champ simplement absent (durée, animateur) n'est pas un doute. Une émission attestée par lmelp n'a ni doute de thème (`thème inconnu`, `thèmes divergents`) ni doute d'existence (`republication`, `attestation fragile`). Une émission dont le thème est arbitré n'a plus de doute de thème ; une émission arbitrée inexistante n'a plus aucun doute.

`lmelp-pap emissions` affiche le nombre de doutes par type à la fin de la construction.

### Renvoi à l'écoute

Certains doutes ne se lèvent pas sur pièces, seulement en écoutant l'émission : un extrait de quatre minutes, une émission au titre générique. Un **renvoi à l'écoute** est une décision humaine qui le reconnaît. Il ne lève aucun doute : il marque tous ceux de l'émission `a_ecouter = oui` dans `doutes.csv`, et la page les range sous « À écouter » plutôt que « À trancher ». La file des doutes à trancher se vide ainsi de ce qui ne peut pas l'être.

Le renvoi s'enregistre et s'applique comme un arbitrage (voir ci-dessous) : il s'attache à une attestation, figure dans `arbitrages.csv` avec la sorte `écoute`, et survit aux reconstructions de la liste. Il vise l'émission entière et ne concerne que les doutes des émissions de la liste. Un arbitrage posé ensuite sur l'émission le remplace, le plus récent l'emportant : l'écoute aboutit à un arbitrage ordinaire, par exemple un thème justifié par « écouté l'enregistrement ». Ses doutes restants ne sont alors plus « à écouter ».

## Arbitrages

Un **arbitrage** est une décision humaine qui lève un doute : le thème d'une émission, ou le fait qu'elle n'existe pas. Les arbitrages sont enregistrés dans `data/processed/arbitrages.csv`, versionné, écrit par l'outil `lmelp-pap arbitrer` ou rédigé à la main, et appliqués à chaque construction de la liste : une décision survit ainsi aux régénérations.

| Colonne | Contenu |
|---|---|
| `source`, `source_id` | L'attestation à laquelle l'arbitrage s'attache, telle qu'elle figure dans `attestations.csv`. |
| `sorte` | `thème`, `existence`, ou `écoute` pour un renvoi à l'écoute. |
| `valeur` | Pour un arbitrage de thème, les thèmes séparés par `;` (`théâtre`, `livres;cinéma`). Pour un arbitrage d'existence, `n'existe pas`. Pour un renvoi à l'écoute, `à écouter`. |
| `justification` | Facultative : « titre explicite », « écouté l'enregistrement », « connaissance de l'émission » ou texte libre. |
| `date` | Date de la décision, au format ISO (`2026-11-10` ou `2026-11-10T14:30`). |

Exemple :

```csv
source,source_id,sorte,valeur,justification,date
ina,RD_4294389.001,thème,théâtre,titre explicite,2026-11-10
radiofrance,le-mage-du-kremlin-de-giuliano-da-empoli-1192090,existence,n'existe pas,écouté l'enregistrement,2026-11-10
radiofrance,la-vie-devant-soi-d-emile-ajar,écoute,à écouter,,2026-11-11
```

**Attestation plutôt qu'émission.** Un arbitrage s'attache à une attestation et non à l'identifiant d'une émission, qui peut changer (nouvelle date retenue, suffixe `-b`). Il s'applique à l'émission qui contient cette attestation, quelle que soit sa date. Choisir l'attestation la plus stable de l'émission : la notice INA, sinon la fiche radiofrance.fr.

**Effets.** Les arbitrages s'appliquent après le rapprochement et avant le filtre de la liste :

- un arbitrage de **thème** remplace exactement les thèmes de l'émission, sans les cumuler avec ceux des sources, et lève ses doutes de thème. Une émission arbitrée `théâtre` sort de la liste ; une émission arbitrée `livres;théâtre` y reste. La colonne `arbitrage` d'`emissions.csv` le signale ;
- un arbitrage d'**existence** retire l'émission de l'ensemble des émissions : elle n'est ni dans la liste ni dans `doutes.csv` ;
- un renvoi à l'**écoute** laisse à l'émission les thèmes de ses sources et ses doutes, marqués `a_ecouter = oui` ;
- un arbitrage dont l'attestation est introuvable n'a aucun effet et produit un doute `arbitrage orphelin` ;
- si plusieurs arbitrages portent sur la même émission, le plus récent l'emporte ; à date égale, le dernier du fichier ;
- un arbitrage qui contredit lmelp s'applique, et produit un doute `contradiction lmelp`.

Un arbitrage n'atteste aucune émission : il tranche entre ce que disent les sources. La commande `lmelp-pap emissions` indique le nombre d'arbitrages lus.

### Arbitrer depuis la liste

```bash
uv run --active lmelp-pap arbitrer
```

La commande lit le cache, reconstruit la liste et lance un serveur local qui sert la page de la liste en **mode arbitrage**. Elle ouvre la page dans le navigateur : dans le devcontainer, VS Code redirige le port vers la machine hôte. Le serveur tourne jusqu'à `Ctrl+C`. Il n'accède jamais au réseau : la liste est reconstruite depuis le cache.

La page garde la frise et les filtres de la page publiée (année, thème, source, type de doute). Sous le détail de chaque émission s'ajoutent :

- une case par thème (livres, cinéma, théâtre, opéra, télévision, musique, variétés), cochée pour les thèmes actuels, et le bouton **Arbitrer le thème** ;
- le bouton **N'existe pas** ;
- le bouton **À écouter**, qui renvoie l'émission à l'écoute ;
- les justifications en un clic, « titre explicite », « écouté l'enregistrement » et « connaissance de l'émission », et un champ libre facultatif ;
- le bouton **Annuler l'arbitrage**, pour une émission dont le thème est arbitré ou qui est renvoyée à l'écoute.

L'outil attache l'arbitrage à l'attestation la plus stable de l'émission : la notice INA, sinon la fiche radiofrance.fr, sinon une autre attestation. À chaque décision, il écrit `arbitrages.csv`, reconstruit la liste, réécrit ses CSV, et la page se met à jour aussitôt : l'émission change d'aspect, ou sort de la liste (arbitrée sans le thème livres, ou inexistante). Un message sous le bandeau « Mode arbitrage » confirme la décision.

Le panneau **Arbitrages enregistrés** du bandeau liste tous les arbitrages du fichier, du plus récent au plus ancien, chacun avec un bouton **Annuler** : c'est ainsi qu'on annule l'arbitrage d'une émission sortie de la liste. Annuler depuis ce panneau retire du fichier les lignes de cette attestation ; **Annuler l'arbitrage** sous une émission retire celles de toutes ses attestations. L'émission retrouve alors les thèmes que lui donnent les sources. Un arbitrage s'ajoute en fin de fichier et une annulation retire seulement ses lignes : les autres lignes, écrites à la main ou non, restent telles quelles.

Exemple : lever les doutes « thème inconnu » de 2010. Cliquer sur 2010 dans la frise, choisir « thème inconnu » dans le filtre Doute, ouvrir l'émission du 11 juillet 2010 (Avignon), cocher « théâtre », cliquer « titre explicite », puis **Arbitrer le thème** : l'émission sort de la liste.

| Option | Effet |
|---|---|
| `--cache DOSSIER` | Dossier du cache (par défaut `data/raw/cache`). |
| `--sortie DOSSIER` | Dossier des CSV de la liste, réécrits à chaque décision (par défaut `data/processed`). |
| `--arbitrages FICHIER` | Fichier des arbitrages (par défaut `arbitrages.csv` dans le dossier de sortie). |
| `--port PORT` | Port du serveur (par défaut 8765). |
| `--sans-navigateur` | N'ouvre pas la page ; l'adresse s'affiche dans le terminal. |

La page publiée (`lmelp-pap page`) n'a aucun de ces contrôles. Après une séance d'arbitrage, la régénérer pour qu'elle reflète les décisions.

#### API

Le serveur expose une petite API JSON, utilisée par la page :

| Requête | Effet |
|---|---|
| `GET /api/donnees` | Les données courantes : `emissions` (comme dans la page) et `arbitrages` (du plus récent au plus ancien, avec la date et le titre de l'attestation). |
| `POST /api/arbitrages` | Enregistre un arbitrage : `{"emission_id": "2010-07-11", "sorte": "thème", "themes": ["théâtre"], "justification": "titre explicite"}`, ou `"sorte": "existence"` sans thèmes, ou `"sorte": "écoute"` sans thèmes pour un renvoi à l'écoute. |
| `POST /api/annulations` | Annule les arbitrages d'une émission, `{"emission_id": "…"}`, ou d'une attestation, `{"source": "ina", "source_id": "…"}`. |

Les deux requêtes `POST` renvoient les données à jour, comme `GET /api/donnees`. Une demande invalide (émission inconnue, thème hors de la liste, rien à annuler) reçoit une erreur 400 `{"erreur": "…"}` et ne change rien.

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
