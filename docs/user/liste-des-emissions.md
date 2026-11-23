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

### Mettre la liste à jour

Le cache ne se met pas à jour tout seul : une source dont la collecte est terminée n'est relue qu'avec `--refresh`. On ne rafraîchit que les sources qui ont du nouveau, les autres restent lues depuis le cache.

**Après une nouvelle émission** (le lundi qui suit la diffusion du dimanche, par exemple) :

```bash
uv run --active lmelp-pap emissions --source radiofrance --source wayback_podcast --refresh
```

| Source | Ce que le rafraîchissement apporte | Durée |
|---|---|---|
| `radiofrance` | La fiche de l'émission, et celles des livres ou films qu'elle publie à part. Le parcours relit toutes les pages de liste, mais ne télécharge que les fiches absentes du cache. | quelques minutes |
| `wayback_podcast` | Les fichiers audio archivés par la Wayback Machine, quand elle les a déjà conservés. | moins d'une minute |
| `ina` | La notice de l'émission, que le catalogue publie avec du retard : inutile de la rafraîchir chaque semaine. | plusieurs minutes |

Une fiche déjà en cache n'est jamais retéléchargée. Pour reprendre une fiche récupérée trop tôt (audio ou description encore absents), supprimer son fichier dans `data/raw/cache/radiofrance/fiches/` avant de rafraîchir.

Depuis 2017, une émission littéraire que lmelp ne contient pas encore a un doute `absente de lmelp` : il disparaît quand l'émission est vérifiée dans lmelp et que cette source est rafraîchie.

**Après une vérification dans lmelp**, depuis le devcontainer (seul accès à la base) :

```bash
uv run --active lmelp-pap emissions --source lmelp --refresh
```

La commande recopie les émissions vérifiées de la base dans le cache. L'émission a ensuite une ligne `lmelp` dans `attestations.csv`, et son doute `absente de lmelp` disparaît. Un doute `sans fiche radiofrance` signale que l'URL enregistrée dans lmelp ne correspond à aucune fiche radiofrance.fr du cache : l'attestation est alors rattachée par la date. Corriger l'URL dans lmelp, ou rafraîchir aussi `radiofrance` si la fiche est récente.

L'appli fait la même chose sans terminal : bouton **Collecte** de l'accueil (voir [Collecter les sources depuis l'appli](#collecter-les-sources-depuis-lappli)).

Les sources se combinent dans une même commande (`--source radiofrance --source lmelp --refresh`). Chaque reconstruction réécrit les fichiers de `data/processed/` : vérifier le changement (`git diff --stat data/processed`), puis le committer. Une fois le commit sur `main`, la page publiée est régénérée à partir des CSV et redéployée (voir « Consulter la liste »).

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
| `ina` | Toutes les notices de la collection « Le masque et la plume » du catalogue INA : date, titre, chaîne, heure, durée, et la fiche détaillée de chaque notice (voir ci-dessous). | environ 2 h la première fois (une fiche toutes les deux secondes environ), puis quelques minutes : une fiche en cache n'est pas re-téléchargée. La progression s'affiche toutes les 100 fiches, avec le temps restant estimé |
| `anciennes_listes` | Les listes d'émissions de l'ancien site France Inter, archivées par la Wayback Machine : liste annuelle (2002-2008) et listes mensuelles (2009-2012), avec date et thème. Un dimanche « Pas de masque et la plume » n'atteste aucune émission. | quelques minutes |
| `lmelp` | Les émissions vérifiées à la main dans l'application lmelp (2014 à aujourd'hui), lues dans sa base MongoDB : page radiofrance.fr, titre, date de publication du podcast. C'est une **source vérifiée** (voir ci-dessous). | quelques secondes |

### Les fiches détaillées INA

La collecte INA enregistre, en plus de la liste des notices, la fiche détaillée de chacune dans `data/raw/cache/ina/fiches/`, un fichier par notice (`RD_1098450.001.html`). Une collecte interrompue reprend où elle s'était arrêtée.

Le **thème** d'une notice vient d'abord de son titre. Quand le titre n'en donne aucun (« Le masque et la plume du 09 janvier 2000 »), il vient de la fiche, dont les champs sont lus dans l'ordre : descripteurs (« cinéma ; film ; débat »), chapeau (« Magazine présenté par Jérôme GARCIN consacré aujourd'hui au cinéma »), résumé producteur (« LITTERAIRE : avec la participation de… »), résumé documentaire. Le **premier champ qui ne désigne qu'un thème** tranche : un champ qui en désigne plusieurs ne dit rien de sûr, car tous citent volontiers d'autres arts que celui de l'émission (les descripteurs d'un film sur un écrivain portent « littérature », la description d'une émission cinéma cite le roman adapté et Shakespeare). Une notice dont aucun champ ne tranche reste au thème inconnu. Les mêmes mots-clés s'appliquent partout, sans tenir compte des accents ni des majuscules ; les notices de la facette Littérature reçoivent en plus le thème livres. Les descripteurs et le chapeau sont surtout renseignés à partir du milieu des années 1990 ; plus tôt, le résumé producteur donne souvent le thème. Pour les émissions récentes, le résumé producteur reprend la description de France Inter.

Le **statut de diffusion** distingue la première diffusion d'une rediffusion (« Multidiffusé ») : une notice de rediffusion, souvent datée du lendemain, atteste l'émission mais ne date pas sa première diffusion. Elle ne produit donc pas de `désaccord de date`. Une notice sans fiche en cache date l'émission.

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

Une ligne par source et par émission : `emission_id`, `source`, `source_id`, `date` et `themes` tels que la source les donne, `titre`, `url` de la notice ou de la page d'origine, `extrait` (`oui` pour une attestation qui ne couvre qu'une partie de l'émission, comme la fiche radiofrance.fr d'un seul livre, `non` sinon). L'écoute ne propose comme page radiofrance.fr de l'émission que les fiches qui ne sont pas des extraits.

### `enregistrements.csv`

Une ligne par fichier audio : `emission_id`, `url`, `type` (`intégral` ou `extrait`), `sources` qui le donnent, `duree`.

Le `type` se décide par **segment** : l'archive (`ITEMA_24209925`) et le code qui la suit (`2025F4007S0215`). Une même archive couvre souvent l'émission entière et ses fiches par livre, chacune dans son segment (`S0215` pour l'émission, `S0216` à `S0219` pour les livres) : seul le segment les distingue. Un segment qu'une source sait être un extrait l'est pour tous ses fichiers, quel que soit leur encodage, même quand une autre source, qui ne voit que le nom du fichier, le croit intégral. Un fichier sans code de segment (`ITEMA_21072908-0.mp3`) garde le type que lui donne sa source.

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

- `rapprochement ambigu` : une attestation aurait pu être rapprochée de plusieurs émissions ; `detail` donne les émissions rivales. Trois situations : deux émissions le même jour (`2007-03-25` et `2007-03-25-b`) sans archive commune (voir **Archive partagée** dans les règles de construction), une émission voisine (un fichier Wayback du 4 décembre 1958 rapprochable aussi du 6), ou des fiches par livre publiées le lendemain de l'émission. Un arbitrage de rapprochement le lève ;
- `désaccord de date` : les sources d'une même émission donnent des dates de première diffusion écartées de plus d'un jour, et la règle du jour de diffusion (voir ci-dessous) ne le lève pas ;
- `jour inhabituel` : la date de l'émission ne tombe pas le jour de diffusion habituel de sa période (`un mardi, quand l'émission passe le jeudi`). Les années de transition (1957, 1964-1965) n'ont pas ce doute ;
- `absente de lmelp` : une émission de la liste ou au thème `hommage`, datée de 2017 à la dernière émission de lmelp, que lmelp ne contient pas. Pour une émission hommage, hors de la liste (`dans_la_liste = non`), le doute reste tracé : son thème explique l'absence ;
- `sans fiche radiofrance` : une attestation lmelp dont la fiche radiofrance.fr est introuvable ; elle est rapprochée par la date ;
- `thème inconnu` : aucune source ne donne le thème de l'émission ;
- `thèmes divergents` : les attestations de l'émission entière ne donnent pas les mêmes thèmes, ou un extrait porte un thème qu'aucune d'elles ne donne. Des extraits aux thèmes différents (une fiche par livre, une par film) décrivent une émission mixte, sans divergence ;
- `collision` : une autre émission a la même date de première diffusion ; le doute porte sur l'émission suffixée (`-b`, `-c`) ;
- `republication` : un enregistrement d'une attestation porte, dans le nom de son fichier, une date à plus de trois jours de la sienne : une émission remise en ligne plus tard, ou une fiche rattachée à l'enregistrement d'une autre émission. Une fiche dont l'archive est celle d'une autre émission, datée du jour du fichier, rejoint cette émission sans doute (voir **Archive d'une autre émission** dans les règles de construction) ;
- `attestation fragile` : l'émission n'est attestée que par des extraits, que par la Wayback Machine, ou que par les deux ;
- `contradiction lmelp` : un arbitrage contredit lmelp, en déclarant inexistante une émission vérifiée ou en lui donnant un autre thème que `livres` seul. L'arbitrage s'applique, mais la contradiction reste signalée ;
- `arbitrage orphelin` : un arbitrage porte sur une attestation qu'aucune source ne donne plus ; il n'a aucun effet. Le doute n'a pas d'`emission_id` : `source` et `source_id` désignent l'attestation introuvable. Un arbitrage de rapprochement dont l'émission cible a disparu (son attestation cible est introuvable) est aussi orphelin : le doute porte alors sur l'émission de l'attestation arbitrée, avec `émission cible introuvable` dans `detail`, et le rapprochement ambigu, s'il demeure, reste un doute. Il en va de même quand l'émission cible est arbitrée inexistante (`émission cible arbitrée inexistante`) : l'attestation déplacée sort de la liste avec elle, et le doute n'a pas d'`emission_id` ;
- `arbitrage déplacé` : un arbitrage de thème, d'existence, d'écoute ou de date est posé sur une attestation déplacée par un arbitrage de rapprochement. Il la suit dans l'émission cible et quitte son ancienne émission. Le doute porte sur l'émission cible ; il se lève en annulant l'arbitrage déplacé, puis en arbitrant à nouveau chaque émission si besoin.

Un champ simplement absent (durée, animateur) n'est pas un doute. Une émission dont la date est arbitrée n'a plus de doute de date (`désaccord de date`, `jour inhabituel`). Une émission attestée par lmelp n'a ni doute de thème (`thème inconnu`, `thèmes divergents`) ni doute d'existence (`republication`, `attestation fragile`). Une émission dont le thème est arbitré n'a plus de doute de thème ; une émission arbitrée « existe » n'a plus de doute d'existence ; une émission arbitrée inexistante n'a plus aucun doute.

`lmelp-pap emissions` affiche le nombre de doutes par type à la fin de la construction.

### Jour de diffusion

L'émission passe chaque semaine le même jour, qui dépend de la période :

| Période | Jour de diffusion |
|---|---|
| 1955 – 1956 | dimanche |
| 1957 | transition, pas de jour habituel |
| 1958 – 1963 | jeudi |
| 1964 – 1965 | transition, pas de jour habituel |
| depuis 1966 | dimanche |

Une émission datée d'un autre jour est une exception à vérifier, un événement particulier ou une date erronée : c'est le doute `jour inhabituel`.

Le jour de diffusion lève aussi la plupart des désaccords de date. Ceux-ci viennent souvent d'attestations voisines qui ne sont pas des premières diffusions : une notice INA à J+1 ou J+2 au titre générique (une rediffusion), un fichier de podcast daté de sa publication. **Règle** : un désaccord de date est levé quand la date retenue est la seule, parmi les dates que donnent les sources, à tomber le jour habituel. Le 8 septembre 2019, un dimanche, n'a ainsi pas de désaccord, malgré un fichier daté du samedi et une notice INA du lundi. La règle ne change jamais la date de l'émission : quand la date retenue n'est pas au jour habituel (le samedi 1er août 2020, que l'INA donne aussi le dimanche 2), le désaccord reste un doute, à lever par un arbitrage de date.

### Renvoi à l'écoute

Certains doutes ne se lèvent pas sur pièces, seulement en écoutant l'émission : un extrait de quatre minutes, une émission au titre générique. Un **renvoi à l'écoute** est une décision humaine qui le reconnaît. Il ne lève aucun doute : il marque tous ceux de l'émission `a_ecouter = oui` dans `doutes.csv`, et la page les range sous « À écouter » plutôt que « À trancher ». La file des doutes à trancher se vide ainsi de ce qui ne peut pas l'être.

Le renvoi s'enregistre et s'applique comme un arbitrage (voir ci-dessous) : il s'attache à une attestation, figure dans `arbitrages.csv` avec la sorte `écoute`, et survit aux reconstructions de la liste. Il vise l'émission entière et ne concerne que les doutes des émissions de la liste. Un renvoi ne se pose que sur une émission qui a au moins un doute. Un arbitrage posé ensuite sur l'émission le remplace, le plus récent l'emportant : l'écoute aboutit à un arbitrage ordinaire, par exemple un thème justifié par « écouté l'enregistrement ». Ses doutes restants ne sont alors plus « à écouter ». À l'inverse, un renvoi posé après un arbitrage de thème le remplace aussi : l'émission retrouve les thèmes de ses sources et leurs doutes, « à écouter ».

## Arbitrages

Un **arbitrage** est une décision humaine qui lève un doute : le thème d'une émission, sa date de première diffusion, l'émission à laquelle se rattache une attestation, ou le fait qu'elle existe ou n'existe pas. Les arbitrages sont enregistrés dans `data/processed/arbitrages.csv`, versionné, écrit par l'outil `lmelp-pap arbitrer` ou rédigé à la main, et appliqués à chaque construction de la liste : une décision survit ainsi aux régénérations.

| Colonne | Contenu |
|---|---|
| `source`, `source_id` | L'attestation à laquelle l'arbitrage s'attache, telle qu'elle figure dans `attestations.csv`. |
| `sorte` | `thème`, `existence`, `date`, `rapprochement`, ou `écoute` pour un renvoi à l'écoute. |
| `valeur` | Pour un arbitrage de thème, les thèmes séparés par `;` (`théâtre`, `livres;cinéma`), ou `hommage` seul. Pour un arbitrage d'existence, `existe` ou `n'existe pas`. Pour un arbitrage de date, la date retenue (`2020-08-02`). Pour un arbitrage de rapprochement, `garder ici`, ou l'attestation qui désigne l'émission cible, `source:source_id` (`ina:RD_3061769.001`). Pour un renvoi à l'écoute, `à écouter`. |
| `justification` | Facultative : « titre explicite », « écouté l'enregistrement », « connaissance de l'émission » ou texte libre. |
| `date` | Date de la décision, au format ISO (`2026-11-10` ou `2026-11-10T14:30`). |

Exemple :

```csv
source,source_id,sorte,valeur,justification,date
ina,RD_4294389.001,thème,théâtre,titre explicite,2026-11-10
radiofrance,le-mage-du-kremlin-de-giuliano-da-empoli-1192090,existence,n'existe pas,écouté l'enregistrement,2026-11-10
radiofrance,la-vie-devant-soi-d-emile-ajar,écoute,à écouter,,2026-11-11
ina,RD_11930110.001,date,2020-08-02,jour habituel,2026-11-11
ina,RD_3061768.001,rapprochement,garder ici,titre explicite,2026-11-18
radiofrance,les-livres-de-la-rentree-1234567,rapprochement,ina:RD_3061769.001,écouté l'enregistrement,2026-11-18
```

**Attestation plutôt qu'émission.** Un arbitrage s'attache à une attestation et non à l'identifiant d'une émission, qui peut changer (nouvelle date retenue, suffixe `-b`). Il s'applique à l'émission qui contient cette attestation, quelle que soit sa date. Choisir l'attestation la plus stable de l'émission : la notice INA, sinon la fiche radiofrance.fr. Un arbitrage de rapprochement fait exception : il s'attache à l'attestation ambiguë elle-même, et désigne l'émission cible par une de ses attestations, jamais par son identifiant.

**Effets.** Les arbitrages s'appliquent après le rapprochement et avant le filtre de la liste :

- un arbitrage de **thème** remplace exactement les thèmes de l'émission, sans les cumuler avec ceux des sources, et lève ses doutes de thème. Une émission arbitrée `théâtre` sort de la liste ; une émission arbitrée `livres;théâtre` y reste. La colonne `arbitrage` d'`emissions.csv` le signale ;
- un arbitrage de thème **hommage** marque une émission sans critique nouvelle, consacrée au Masque ou à l'un de ses critiques : souvenirs, passage de témoin, anniversaire (« La dernière de Jérôme Garcin » le 31 décembre 2023, les 70 ans de l'émission le 28 décembre 2025). Le thème `hommage` ne se cumule avec aucun autre : il remplace tous ceux des sources, et l'émission sort de la liste même si elle évoque des livres. Aucune règle ne le déduit du titre : il s'attribue au cas par cas. Une ligne qui combine `hommage` avec un autre thème (`hommage;livres`) est refusée, comme une ligne dont un thème n'est pas dans la liste des thèmes ;
- un arbitrage d'existence **n'existe pas** retire l'émission de l'ensemble des émissions : elle n'est ni dans la liste ni dans `doutes.csv` ;
- un arbitrage d'existence **existe** lève les doutes d'existence de l'émission (`attestation fragile`, `republication`), sans toucher à ses thèmes, à sa date ni à son appartenance à la liste. Il se cumule avec un arbitrage de thème, un renvoi à l'écoute ou un arbitrage de date. Un arbitrage de thème ou de date ne lève pas les doutes d'existence : seul « existe » les lève ;
- un renvoi à l'**écoute** laisse à l'émission les thèmes de ses sources et ses doutes, marqués `a_ecouter = oui` ;
- un arbitrage de **date** donne à l'émission la date retenue, d'où découle son identifiant (`2020-08-01` devient `2020-08-02`), et lève ses doutes de date. Retenir la date actuelle confirme une exception : le doute `jour inhabituel` disparaît, l'identifiant ne change pas. L'arbitrage de date porte sur un autre point que les autres sortes : il se cumule avec un arbitrage de thème ou un renvoi à l'écoute de la même émission au lieu de le remplacer ;
- un arbitrage de **rapprochement** lève le doute `rapprochement ambigu` de son attestation. **Garder ici** confirme sa position actuelle, sans rien changer d'autre. **Déplacer vers** l'envoie sur l'émission de l'attestation cible, avant que ses champs soient établis : elle y participe comme si elle y avait été rapprochée (champs, thèmes, enregistrements, doutes), et quitte son ancienne émission, qui disparaît si elle n'avait plus d'autre attestation. L'attestation lmelp rattachée à une fiche déplacée suit la fiche. Une cible elle-même déplacée est suivie jusqu'à son émission d'arrivée, quel que soit l'ordre des arbitrages ; des déplacements en cycle laissent leurs attestations en place. Les autres arbitrages attachés à l'attestation déplacée la suivent, et chacun produit un doute `arbitrage déplacé`. L'arbitrage de rapprochement porte sur un autre point que les autres sortes et se cumule avec eux ;
- un arbitrage dont l'attestation est introuvable n'a aucun effet et produit un doute `arbitrage orphelin` ; de même pour un arbitrage de rapprochement dont l'attestation cible est introuvable ;
- si plusieurs arbitrages portent sur la même émission, le plus récent l'emporte ; à date égale, le dernier du fichier. Les arbitrages de date se départagent entre eux, les arbitrages de rapprochement entre eux, « existe » et « n'existe pas » entre eux, et les arbitrages de thème, « n'existe pas » et les renvois à l'écoute entre eux. Un « existe » plus récent qu'un « n'existe pas » l'annule : l'émission revient avec son dernier arbitrage de thème ou renvoi à l'écoute ;
- un arbitrage qui contredit lmelp s'applique, et produit un doute `contradiction lmelp`.

Un arbitrage n'atteste aucune émission : il tranche entre ce que disent les sources. La commande `lmelp-pap emissions` indique le nombre d'arbitrages lus.

### Arbitrer depuis la liste

```bash
uv run --active lmelp-pap arbitrer
```

La commande lit le cache, reconstruit la liste et lance un serveur local qui sert la page de la liste en **mode arbitrage**. Elle ouvre la page dans le navigateur : dans le devcontainer, VS Code redirige le port vers la machine hôte. Le serveur tourne jusqu'à `Ctrl+C`. La liste est reconstruite depuis le cache, sans réseau ; seule la vérification des URL d'intégral (voir « Maturité des enregistrements ») interroge radiofrance.fr, à la demande.

Le script `scripts/start-dev.sh` lance le même serveur sans ouvrir le navigateur, et sait l'arrêter ou le remplacer depuis un autre terminal :

```bash
scripts/start-dev.sh             # démarre au premier plan ; Ctrl+C l'arrête
scripts/start-dev.sh --restart   # arrête le serveur précédent, puis démarre
scripts/start-dev.sh --stop      # arrête le serveur et quitte
scripts/start-dev.sh --status    # URL, pid, ancienneté, /health, commit servi
scripts/start-dev.sh -- --verification-jours 1   # options passées à arbitrer
```

Le port est `PAP_PORT` s'il est défini, et le démarrage est refusé s'il est pris ; sinon, le premier port libre de 8765 à 8799 (plage modifiable par `PAP_PLAGE_PORTS`, par exemple `8765-8799`). L'adresse d'écoute vient de `PAP_HOTE` (127.0.0.1 par défaut). Une fois le serveur prêt, le script affiche les liens de l'accueil, de la liste et de `/health`, et, avec `PAP_HOTE=0.0.0.0`, une adresse réseau par interface de la machine.

Le serveur démarré est décrit dans `.dev-ports.json`, à la racine du dépôt (à ne pas commiter) : `pid`, `port`, `host`, `url`, `started_at`, `commit` et `branche` du code servi. `--stop`, `--restart` et `--status` le relisent, et retrouvent aussi par leur port les serveurs pap qui n'y figurent pas (lancés à la main, ou par un second démarrage) : `--stop` les arrête tous. Un second démarrage prend le port libre suivant et prévient qu'un serveur pap tourne déjà, car les deux écrivent les mêmes CSV et la même base Mongo. `--status` signale quand le dépôt a changé de commit depuis le démarrage.

La page garde la frise et les filtres de la page publiée (année, thème, source, type de doute). Sous le détail de chaque émission s'ajoutent :

- une case par thème (livres, cinéma, théâtre, opéra, télévision, musique, variétés, hommage), cochée pour les thèmes actuels, et le bouton **Arbitrer le thème**. Cocher `hommage` décoche les autres thèmes, et cocher un autre thème décoche `hommage` ;
- le bouton **Existe**, qui lève les doutes d'existence, et le bouton **N'existe pas** ;
- le bouton **À écouter**, qui renvoie l'émission à l'écoute ;
- pour une émission qui a un doute de date (`désaccord de date` ou `jour inhabituel`), ou dont la date est déjà arbitrée, chaque date candidate, c'est-à-dire chaque date de première diffusion que donnent ses sources, avec son jour et ses sources. La date actuelle est cochée et le jour habituel signalé. Le bouton **Retenir cette date** enregistre un arbitrage de date ; sur une date déjà arbitrée, il la remplace sans toucher à l'arbitrage de thème ni au renvoi à l'écoute :

  ```
  Date de première diffusion
    ● 2020-08-01 samedi    INA, radiofrance   ← date actuelle
    ○ 2020-08-02 dimanche  INA                ← jour habituel
    ○ 2020-08-03 lundi     INA
    [ Retenir cette date ]
  ```

- pour chaque doute `rapprochement ambigu`, sur sa ligne de la section « Doutes », le bouton **Garder ici** et un bouton **Déplacer vers** par émission rivale :

  ```
  rapprochement ambigu · INA RD_3061768.001 · rapprochable aussi de 2007-03-25-b
    [ Garder ici ]  [ Déplacer vers 2007-03-25-b ]
  ```

  La justification choisie sous l'émission accompagne la décision ;
- les justifications en un clic, « titre explicite », « écouté l'enregistrement » et « connaissance de l'émission », et un champ libre facultatif ;
- le bouton **Annuler l'arbitrage**, pour une émission dont le thème, la date ou l'existence est arbitré, ou qui est renvoyée à l'écoute. Il retire tous les arbitrages de l'émission, « existe » compris.

L'outil attache l'arbitrage à l'attestation la plus stable de l'émission : la notice INA, sinon la fiche radiofrance.fr, sinon une autre attestation. À chaque décision, il l'enregistre (dans Mongo si `MONGO_URI` est défini, sinon dans `arbitrages.csv`, voir [Arbitrages dans Mongo](#arbitrages-dans-mongo)), reconstruit la liste, réécrit ses CSV, et la page se met à jour aussitôt : l'émission change d'aspect, ou sort de la liste (arbitrée sans le thème livres, ou inexistante). Un message sous le bandeau « Mode arbitrage » confirme la décision.

Le panneau **Arbitrages enregistrés** du bandeau liste tous les arbitrages du fichier, du plus récent au plus ancien, chacun avec un bouton **Annuler** : c'est ainsi qu'on annule l'arbitrage d'une émission sortie de la liste. Annuler depuis ce panneau retire du fichier les lignes de cette attestation ; **Annuler l'arbitrage** sous une émission retire celles de toutes ses attestations. L'émission retrouve alors les thèmes que lui donnent les sources. Un arbitrage s'ajoute en fin de fichier et une annulation retire seulement ses lignes : les autres lignes, écrites à la main ou non, restent telles quelles.

Exemple : lever les doutes « thème inconnu » de 2010. Cliquer sur 2010 dans la frise, choisir « thème inconnu » dans le filtre Doute, ouvrir l'émission du 11 juillet 2010 (Avignon), cocher « théâtre », cliquer « titre explicite », puis **Arbitrer le thème** : l'émission sort de la liste.

| Option | Effet |
|---|---|
| `--cache DOSSIER` | Dossier du cache (par défaut `data/raw/cache`). |
| `--sortie DOSSIER` | Dossier des CSV de la liste, réécrits à chaque décision (par défaut `data/processed`). |
| `--arbitrages FICHIER` | Fichier des arbitrages (par défaut `arbitrages.csv` dans le dossier de sortie). |
| `--verification-jours N` | Jours entre deux vérifications complètes des URL (par défaut 7, ou `PAP_VERIFICATION_JOURS`). |
| `--audios DOSSIER` | Dossier des enregistrements rapatriés (par défaut `data/raw/audios`, ou `PAP_AUDIOS`). |
| `--audios-lmelp DOSSIER` | Dossier audio du back-office lmelp, où vont les enregistrements mis à disposition (par défaut `data/raw/audios-lmelp`, ou `PAP_AUDIOS_LMELP`). |
| `--port PORT` | Port du serveur (par défaut 8765). |
| `--sans-navigateur` | N'ouvre pas la page ; l'adresse d'écoute s'affiche dans les logs. |

La page publiée n'a aucun de ces contrôles. Elle reflète les décisions d'une séance d'arbitrage une fois les CSV de `data/processed/` et `arbitrages.csv` committés sur `main`, qui la régénère et la redéploie.

#### Arbitrages dans Mongo

Quand `MONGO_URI` est défini (base `MONGO_DB`, par défaut `masque_et_la_plume`), les arbitrages de l'appli vivent dans la collection Mongo `pap_arbitrages`, qui fait foi : l'appli y écrit chaque décision et chaque annulation, et y relit les arbitrages à chaque reconstruction de la liste. Le fichier `arbitrages.csv` n'est alors ni lu ni écrit par l'appli ; il en est la publication (ADR 0004). Un arbitrage survit ainsi au redémarrage de l'appli. Sans `MONGO_URI`, l'appli lit et écrit `arbitrages.csv` comme décrit plus haut. Si Mongo est illisible à la reconstruction, la liste se construit avec `arbitrages.csv` et un avertissement va aux logs.

La commande `lmelp-pap arbitrages` passe les arbitrages d'un support à l'autre :

```bash
# Ajoute à pap_arbitrages les arbitrages du fichier qui n'y sont pas encore
uv run lmelp-pap arbitrages importer
# Réécrit le fichier avec tous les arbitrages de pap_arbitrages
uv run lmelp-pap arbitrages exporter
```

| Option | Effet |
|---|---|
| `--fichier FICHIER` | Fichier des arbitrages (par défaut `arbitrages.csv` dans `data/processed`, ou `PAP_ARBITRAGES`, ou `PAP_DONNEES`). |

L'import est idempotent : un arbitrage est reconnu par son attestation, sa sorte, sa valeur et sa date ; importer deux fois le même fichier n'ajoute rien la seconde fois. Il ne retire rien de Mongo. L'export écrit le format de `arbitrages.csv`, dans l'ordre d'entrée des arbitrages (l'ordre du fichier importé, puis celui des décisions), si bien qu'importer puis exporter redonne le même fichier. La commande `lmelp-pap emissions` lit toujours le fichier, sans Mongo : pour construire la liste hors ligne avec les décisions de l'appli, exporter d'abord. pap n'écrit que dans des collections préfixées `pap_`.

Chaque commande laisse une ligne de log :

```
2026-11-23 09:12:03 INFO    arbitrages : import de data/processed/arbitrages.csv : 187 arbitrages lus, 187 ajoutés à pap_arbitrages
2026-11-23 09:40:51 INFO    arbitrages : export de pap_arbitrages : 189 arbitrages → data/processed/arbitrages.csv
```

#### Logs

L'appli écrit ses logs sur la sortie d'erreur (dans le conteneur : `docker logs lmelp-pap`), une ligne par événement : horodatage local, niveau (`INFO`, `WARNING`, `ERROR`), module, message. Le démarrage donne la version, l'adresse d'écoute (`hôte:port`), l'état de Mongo, le nombre d'émissions de la liste et les dossiers (voir [L'appli pap en conteneur](appli-docker-nas.md#logs)). Puis :

```
2026-11-21 10:53:51 INFO    arbitrer : vérification automatique (complète : jamais vérifiée) : 570 URL
2026-11-21 10:53:58 WARNING maturite : vérification 1980-02-24 https://media.radiofrance-podcast.net/… : HTTP 503
2026-11-21 10:54:02 INFO    arbitrer : vérification terminée en 10 s : 569 ok, 0 morte, 1 échec passager
2026-11-21 10:58:10 INFO    arbitrer : arbitrage thème 2010-07-11 : théâtre (« titre explicite »)
2026-11-21 10:58:10 INFO    http : POST /api/arbitrages 200 (192.168.1.20)
2026-11-21 11:01:33 INFO    arbitrer : annulation 2010-07-11 : 1 arbitrage retiré
2026-11-21 11:04:46 INFO    arbitrer : rapatriement : 1 émission demandée
2026-11-21 11:04:53 INFO    arbitrer : rapatrié 2006-04-23 : 2006/14007-23.04.2006-ITEMA_20025254-2006F4007E0016-27.m4a, 71 Mo en 7 s
2026-11-21 11:04:53 INFO    arbitrer : rapatriement terminé en 7 s : 1 rapatrié, 0 déjà là, 0 échec
2026-11-21 11:20:12 INFO    arbitrer : écarté 2006-04-23 (2006/14007-23.04.2006-ITEMA_20025254-2006F4007E0016-27.m4a) : « coupé à 40 min »
2026-11-21 11:31:40 INFO    arbitrer : qualifié 2014-09-28 (2014/14007-28.09.2014-ITEMA_20674220-2014F4007S0271-27.m4a) : favorable
2026-11-21 11:40:02 INFO    arbitrer : mis à disposition 2014-09-28 : /data/audios/2014/14007-28.09.2014-….m4a → /audios-lmelp/2014/14007-28.09.2014-….m4a (sha256 3f1c0e9a77b2)
2026-11-21 11:40:02 INFO    arbitrer : mise à disposition refusée 2006-04-23 (niveau qualifie) : 2006/14007-23.04.2006-….m4a existe déjà dans le dossier de lmelp
2026-11-21 11:40:02 INFO    arbitrer : mise à disposition : 1 mise à disposition, 1 refus
2026-11-21 11:40:10 INFO    arbitrer : collecte demandée : radiofrance (re-collecte)
2026-11-21 11:40:10 INFO    arbitrer : collecte radiofrance : début
2026-11-21 11:40:14 INFO    collecte : radiofrance : page 1, 20 fiches vues, 1 téléchargées
2026-11-21 11:40:20 INFO    arbitrer : collecte ina refusée : une collecte est déjà en cours (radiofrance) : attendez sa fin
2026-11-21 11:42:05 INFO    arbitrer : collecte radiofrance : collectée en 1 min 55 s
2026-11-21 11:42:09 INFO    arbitrer : collecte terminée en 1 min 59 s : 2391 émissions (avant 2390), 9120 attestations
2026-11-21 11:42:17 ERROR   arbitrer : GET /api/donnees : erreur interne (ServerSelectionTimeoutError)
Traceback (most recent call last):
  …
```

**Actions.** Une vérification lancée par le bouton est « manuelle » ; la raison d'une vérification automatique est indiquée (jamais vérifiée, base vide, date de la précédente, nouvelles URL). Chaque arbitrage donne sa sorte, l'émission, la décision (thèmes, existence, date retenue, rapprochement, renvoi à l'écoute) et sa justification ; chaque annulation, l'émission ou l'attestation et le nombre d'arbitrages retirés. Avec Mongo, ces deux lignes finissent par « (pap_arbitrages) ». Un rapatriement trace chaque nouvel essai (« échec 1980-02-24 (essai 1/3) : …, nouvel essai dans 5 s »), chaque échec définitif et l'arrêt d'un lot. Une qualification refusée est tracée avec sa raison (« qualification refusée 2024-02-11 : … aucun enregistrement rapatrié à qualifier »). Chaque mise à disposition refusée donne l'émission, le niveau de son enregistrement le plus avancé et la raison ; une mise à disposition qui a lu l'API Radio France le signale (« …, API Radio France »). Les appels à l'API Radio France donnent leur résultat, le nombre de requêtes et la durée, jamais le contenu reçu. Une collecte donne les sources demandées, le début et l'issue de chaque source (collectée, déjà complète, sautée, en échec) avec sa durée, ses lignes de progression (module `collecte` : une par page de la liste radiofrance.fr, une toutes les 100 fiches INA), le refus d'une deuxième demande avec sa raison, et le bilan (durée, émissions avant et après, attestations).

**Requêtes HTTP.** Chaque requête donne sa méthode, son chemin, son statut et l'adresse du client (module `http`), sauf `GET /health` (sondé par Docker) et les sondages de l'avancement par la page (`GET /api/verifications`, `GET /api/rapatriements`, `GET /api/collectes`). Une demande refusée donne en plus sa raison (« POST /api/arbitrages refusée (400) : sorte invalide : … »).

**Erreurs.** Niveau `WARNING` : échec passager d'une vérification d'URL (réseau, 5xx, 429, 403), échec d'un essai ou d'un rapatriement, erreur de l'API Radio France, fichier audio introuvable. Niveau `ERROR`, avec le type de l'exception et la trace : exception imprévue pendant une requête (Mongo injoignable, par exemple ; la page reçoit une 500 au message générique `{"erreur": "erreur interne"}`, le détail ne reste que dans les logs), dans la planification de la vérification, ou dans une tâche de fond (« vérification en échec », « rapatriement en échec » : la tâche s'arrête sans bilan ; « collecte ina en échec : … » : la collecte passe à la source suivante). Mongo injoignable n'empêche pas le démarrage : la ligne « Mongo : injoignable … » le signale et l'appli sert la liste.

#### API

Le serveur expose une petite API JSON, utilisée par la page :

| Requête | Effet |
|---|---|
| `GET /` | L'accueil. `GET /liste` : la liste en mode arbitrage. |
| `GET /api/donnees` | Les données courantes : `emissions` (comme dans la page) et `arbitrages` (du plus récent au plus ancien, avec la date et le titre de l'attestation). Chaque émission porte en plus `dates_candidates` (vide sans doute de date ni date arbitrée ; sinon, pour chaque date des sources : `date`, `jour`, `sources`, `habituel`, `actuelle`), `arbitrage_date` (`date` et `justification`, ou `null`), et `rapprochements` (pour chaque attestation au rapprochement ambigu : `source`, `source_id` et `rivales`, les identifiants des émissions rivales). Chaque doute porte `source` et `source_id`, l'attestation en cause, vides si le doute porte sur l'émission entière. Avec une base Mongo, chaque émission porte aussi `maturite`, `maturite_depuis`, `echec_rapatriement`, `fichier_audio` (le fichier écoutable, relatif au dossier audio, ou `null`) `ecart` (`date` et `motif` de l'écart, ou `null`) `dans_lmelp` (vrai si un épisode de lmelp porte le fichier d'un de ses enregistrements valides, ou si lmelp l'atteste) `integration_lmelp` (l'heure de création de cet épisode par le back-office, ISO 8601, ou `null`) `localisations` (ses enregistrements localisés, du plus ancien au plus récent : `id`, l'identifiant de l'enregistrement, `source`, `note`, `notice`, l'URL de la notice INA ou `null`, `depuis`, la date d'entrée dans le niveau, `relance`, celle de son dernier échange, et `journal`, ses échanges du plus récent au plus ancien : `date`, `canal`, `interlocuteur`, `texte`, `relance`), `relance` (la plus proche de ses pistes, ou `null`) et `dernier_echange` (`date` et `canal`, ou `null`). Les données portent aussi `detenteurs`, les détenteurs des pistes déjà saisies. |
| `POST /api/localisations` | Ajoute à une ou plusieurs émissions un enregistrement localisé saisi à la main (une piste) : `{"emissions": ["2008-03-02", "2008-03-09"], "source": "Jean D., forum, cassettes 2008", "note": "face B abîmée", "premier_echange": {"canal": "forum", "texte": "message reçu"}}` (`"emission_id"` pour une seule émission ; `note` et `premier_echange` facultatifs). Le premier échange est daté du jour, avec le détenteur pour interlocuteur. Tout est vérifié avant d'écrire : un refus ne localise aucune émission. Renvoie les données à jour. Erreurs : 400 (émission inconnue, source vide, premier échange sans texte ou de canal inconnu), 503 (sans base Mongo). |
| `POST /api/echanges` | Note un échange au journal d'une piste : `{"emission_id": "2008-03-02", "enregistrement": "piste:…", "date": "2026-11-21", "canal": "courriel", "interlocuteur": "Jean", "texte": "relancé", "relance": "2026-12-21"}`. `enregistrement` est facultatif si l'émission n'a qu'une piste, `date` vaut aujourd'hui par défaut, `interlocuteur` et `relance` sont facultatifs. Canaux : `courriel`, `téléphone`, `forum`, `courrier`, `sur place`, `autre`. Ni la maturité ni la date d'entrée dans l'état ne changent. Erreurs : 400 (émission inconnue ou sans piste, piste à préciser, texte vide, canal inconnu, date illisible), 503 (sans base Mongo). |
| `POST /api/urls` | Ajoute à une émission un enregistrement téléchargeable : `{"emission_id": "2008-03-02", "url": "https://…/masque.mp3", "note": "…"}`. Il part avec le prochain lot de téléchargement. Erreurs : 400 (URL qui n'est pas en http(s), URL déjà connue), 503 (sans base Mongo). |
| `POST /api/fichiers?emission_id=…&nom=…&provenance=…&datation=…&note=…&piste=…` | Téléverse un fichier audio : le corps de la requête est le fichier, ses champs sont dans l'adresse. Il est écrit dans le dossier audio de pap, sous `<année>/<nom>`, et l'enregistrement passe à rapatrié avec son empreinte et sa taille : celui de la piste `piste` (facultative), sinon un nouveau. `datation` : `etiquette`, `antenne`, `contenu` ou `inconnue`. Erreurs : 400 (provenance vide, nom qui n'est pas celui d'un fichier audio, nom déjà pris dans `<année>/` : rien n'est écrasé), 503 (sans base Mongo). |
| `POST /api/arbitrages` | Enregistre un arbitrage : `{"emission_id": "2010-07-11", "sorte": "thème", "themes": ["théâtre"], "justification": "titre explicite"}`, ou `"sorte": "existence"` sans thèmes, avec `"valeur": "existe"` ou `"valeur": "n'existe pas"` (par défaut), `"sorte": "date"` avec `"date": "2020-08-02"`, `"sorte": "écoute"` sans thèmes pour un renvoi à l'écoute, ou `"sorte": "rapprochement"` avec l'attestation ambiguë (`"source"`, `"source_id"`) et `"vers"` : l'identifiant de l'émission rivale où la déplacer, ou `null` pour la garder ici. L'outil enregistre l'émission cible par son attestation la plus stable. |
| `POST /api/rapatriements` | Lance en fond le rapatriement des émissions `{"emissions": ["2007-01-14", …]}`, l'une après l'autre. Erreurs : 400 (liste vide, émission sans intégral téléchargeable), 409 (un lot tourne déjà), 503 (sans base Mongo). |
| `GET /api/rapatriements` | L'avancement : `en_cours`, `faites`, `total`, `en_cours_sur`, `octets` (reçus), `fichier_octets` et `fichier_total` (fichier en cours), `debut`, `arrete`, `rapatriees` (dates des émissions rapatriées), `erreurs`, et `bilan` (`rapatries`, `deja_la`, `echecs`) une fois fini. |
| `POST /api/rapatriements/arret` | Arrête le lot en cours. |
| `POST /api/qualifications` | Qualifie l'enregistrement rapatrié d'une émission : `{"emission_id": "2014-09-28", "verdict": "favorable"}`, ou `"verdict": "ecarte"` avec `"motif": "…"` ; `"enregistrement"` (son URL) choisit l'enregistrement quand l'émission en a plusieurs. Renvoie les données à jour. Erreurs : 400 (verdict inconnu, écart sans motif, aucun enregistrement rapatrié pour cette émission), 503 (sans base Mongo). |
| `GET /api/remises/<emission_id>` | Ce que lmelp reçoit pour l'émission, sans `_id`, dates en ISO 8601 : sa fiche `pap_remises` si elle est mise à disposition (`apercu` faux), sinon l'aperçu de la fiche de son enregistrement qualifié (`apercu` vrai, `date_remise` vide, rien n'est écrit) ; 404 sinon. |
| `POST /api/remises/annulation` | Annule la mise à disposition d'une émission valide qui n'est pas encore dans lmelp : `{"emission": "2014-09-28"}`. Retire la fiche `pap_remises` et la copie chez lmelp (si elle a encore son empreinte), ramène l'enregistrement à qualifié et renvoie les données à jour. Erreurs : 400 (émission inconnue, déjà dans lmelp, ou sans mise à disposition), 503 (sans base Mongo). |
| `POST /api/remises` | Met à disposition de lmelp l'enregistrement qualifié de chaque émission : `{"emissions": ["2014-09-28", …]}`, l'une après l'autre. Renvoie les données à jour et `remise` : `mises` (`emission`, `fichier`) et `refus` (`emission`, `detail`). Une émission refusée (déjà dans lmelp, sans enregistrement qualifié, fichier de même nom chez lmelp) ne change rien et n'arrête pas les suivantes. Erreurs : 400 (liste vide), 503 (sans base Mongo). |
| `GET /audios/<fichier>` | Un fichier du dossier audio (`fichier_audio` d'une émission), entier ou par plage (`Range: bytes=…`, réponse 206 ; 416 hors du fichier). Rien n'est servi hors du dossier audio (404). |
| `POST /api/collectes` | Lance en fond la collecte d'une source, `{"source": "radiofrance"}`, ou de toutes, `{"source": "toutes"}` ; `"refresh": true` re-collecte une source au cache complet. À la fin, la liste est reconstruite depuis le cache. Rend l'avancement. Erreurs : 400 (source inconnue), 409 (une collecte tourne déjà, avec la source en cours dans le message). |
| `GET /api/collectes` | L'avancement : `en_cours`, `faites` et `total` (sources), `sources`, `refresh`, `en_cours_sur` (la source en cours), `progression` (sa dernière ligne de progression), `debut`, `erreurs` (`source`, `detail`), et `bilan` une fois finie : `emissions`, `emissions_avant`, `attestations`, et `sources`, l'issue de chacune (`collectee`, `deja_complete`, `sautee`, `echec`). |
| `POST /api/verifications` | Lance en fond la vérification des URL d'intégral et rend son avancement. Sans base Mongo : erreur 503. |
| `GET /api/verifications` | L'avancement de la vérification : `en_cours`, `faites`, `total`, `bilan` (`ok`, `net`, `passager`) une fois finie, `derniere` et `prochaine` (dates de la dernière vérification complète et de la suivante). |
| `POST /api/annulations` | Annule les arbitrages d'une émission, `{"emission_id": "…"}`, ou d'une attestation, `{"source": "ina", "source_id": "…"}`. |
| `GET /api/publication` | L'aperçu de la publication sur GitHub (voir [Publier la liste sur GitHub](#publier-la-liste-sur-github)) : `emissions` (`ajoutees`, `retirees`, `modifiees`), `arbitrages` et `qualifications` (`ajoutes`, `retires`), `niveaux` (enregistrements entrés dans un niveau depuis `depuis`, la date de la dernière publication), `fichiers` changés, `a_publier`, `resume`. Erreurs : 503 (sans `PAP_DEPOT_GIT`), 502 (dépôt injoignable, fichier refusé). |
| `POST /api/publication` | Publie : `statut` `publiee` (avec `commit`), `rien` (aucun commit) ou `refusee` (avec `detail`), et `resume`. Erreur : 503 (sans `PAP_DEPOT_GIT`). |

Les deux requêtes `POST` renvoient les données à jour, comme `GET /api/donnees`. Une demande invalide (émission inconnue, thème hors de la liste, `hommage` combiné à un autre thème, date absente des dates candidates ou émission sans doute de date, attestation sans rapprochement ambigu ou émission qui n'est pas rivale, rien à annuler) reçoit une erreur 400 `{"erreur": "…"}` et ne change rien.

### Accueil et pages d'état

L'appli s'ouvre sur l'**accueil** (`/`) ; la liste et ses arbitrages sont sur `/liste` (bouton « Liste et arbitrages », retour par « ← Accueil »).

Chaque émission y a un **état** : « dans lmelp » si lmelp l'atteste ou si un épisode de lmelp porte le fichier (`audio_rel_filename`) d'un de ses enregistrements valides, sinon la maturité de son enregistrement le plus avancé (localisé, téléchargeable, rapatrié, qualifié, valide), sinon « sans enregistrement ».

- **En haut, fixes** : l'histogramme des émissions par année, empilé par état, et un compteur par état avec l'action qu'il annonce.
- **Dessous, la frise** des émissions par année, de la plus récente à la plus ancienne, dans son propre ascenseur : chaque ligne donne la date, le titre, l'état et l'ancienneté dans cet état (« 12 j ») ; pour un état qui attend une action, elle passe en ambre à partir de 21 jours, en rouge à partir de 45. Sur « valide (attend lmelp) », elle dit depuis combien de jours lmelp n'a pas pris l'enregistrement.
- **Survoler une année** affiche ses chiffres dans le titre du graphique et place la frise sur cette année. **Cliquer une année** filtre tout sur elle : compteurs, frise et page d'état ouverte ensuite ; le bouton « 1987 × » lève le filtre.
- **Survoler un compteur** fait ressortir son état dans le graphique et la frise ; **cliquer** ouvre la **page de l'état** : son histogramme (un clic sur une année filtre la liste) et le tableau de ses émissions, trié par ancienneté dans l'état, de la plus ancienne à la plus récente, sauf « rapatrié », trié de l'émission la plus récente à la plus ancienne, et les états sans action, triés par date décroissante ; un clic sur un en-tête trie la colonne, un second inverse le sens. Les pages d'état n'ont pas de colonne de thèmes, presque toutes les émissions de la liste étant « livres » : une émission qui a d'autres thèmes les montre après son titre (« · cinéma, livres »). Le tri choisi sur une page est retenu dans le navigateur et retrouvé à la visite suivante, page par page. L'adresse garde l'état et l'année (`/#etat=telechargeable&annee=2008`).
- La page **dans lmelp** a une colonne **Intégrée** : le jour et l'heure où le back-office a fait un épisode de l'enregistrement remis par pap (création du document `episodes`). Une émission entrée dans lmelp par son flux RSS ou une page radiofrance.fr affiche « — ».

L'accueil suit le thème clair ou sombre du système. Sans base Mongo, il n'affiche que « sans enregistrement » et « dans lmelp », avec un bandeau. « pap », en haut à gauche, ramène à l'accueil sans filtre.

### Collecter les sources depuis l'appli

Le bouton **Collecte**, en haut à droite de l'accueil, ouvre une boîte avec un bouton par source (`radiofrance`, `ina`, `wayback_podcast`, `anciennes_listes`, `lmelp`) et **Toutes**. La case **Re-collecter** reprend une source même si son cache est complet, comme `--refresh` ; sans elle, une source déjà collectée est seulement relue.

La collecte tourne en fond, dans le serveur : la boîte se ferme et la page reste utilisable. Pendant la collecte, le bouton de l'en-tête affiche la source en cours (« Collecte : radiofrance… ») et la boîte, rouverte, sa dernière ligne de progression (« radiofrance : page 3, 60 fiches vues, 12 téléchargées », « ina : fiches détaillées 300/2000 (≈ 31 min restantes) »). À la fin, la liste est reconstruite depuis le cache, avec les arbitrages, la page relit ses données et un message donne le nombre d'émissions avant et après, et les compteurs qui ont changé.

Une seule collecte tourne à la fois : une demande pendant une collecte, depuis cette page ou une autre, est refusée et la boîte affiche la raison (« une collecte est déjà en cours (radiofrance) : attendez sa fin »). Une source en échec (réseau, par exemple) n'arrête pas les suivantes : le message final la nomme, et la trace est dans les logs. Sans `MONGO_URI`, la source `lmelp` est sautée et son cache précédent reste valable.

La collecte écrit dans le dossier du cache de l'appli (`--cache`, ou `PAP_CACHE`) ; la source INA demande Chromium (voir « Prérequis pour la source INA »).

### Sans enregistrement et localisé : faire avancer une émission

Sur les pages **sans enregistrement** et **localisé**, un clic sur une ligne la déplie en pleine largeur juste en dessous ; un second clic la referme, et une seule ligne est dépliée à la fois.

- **À gauche** : pour une émission sans enregistrement, **Ce qu'on sait** (les sources qui l'attestent) ; pour une émission localisée, le **journal des échanges**, du plus récent au plus ancien (date · canal · interlocuteur · relance, puis le texte), et le formulaire **Noter un échange**.
- **À droite**, **Faire avancer** : trois onglets, chacun avec une ligne qui dit où il mène.
  1. **Une piste** (**Une autre piste** sur une émission déjà localisée) → localisé. Le **détenteur** est obligatoire ; les détenteurs déjà saisis sont proposés à la saisie. Une note dit ce qu'on sait de son fonds. La case « noter aussi le premier échange », cochée par défaut, note en même temps un échange daté du jour (canal et texte). Sur une émission localisée, la piste s'ajoute aux autres et l'émission reste localisée.
  2. **URL** → téléchargeable : l'**URL http(s)** du fichier intégral (obligatoire) et une note. L'émission part avec le prochain lot de téléchargement de la page « téléchargeable ».
  3. **Fichier** → rapatrié : le **fichier audio** (obligatoire), sa **provenance** (obligatoire, préremplie avec le détenteur de la piste), ce qui établit sa date (étiquette de la cassette ou du fichier, annonce à l'antenne, déduite du contenu, inconnue) et une note. Le fichier est écrit dans le dossier audio de pap, sous `<année>/`, puis s'écoute et se qualifie dans « rapatrié ». S'il vient d'une piste (« Vient de »), il rapatrie l'enregistrement de cette piste ; sinon il en crée un nouveau. Un nom de fichier déjà pris dans `<année>/` est refusé : rien n'est écrasé.

Un refus (échange sans texte, URL invalide, nom de fichier déjà pris…) s'affiche dans la ligne dépliée.

**Colonnes.** « sans enregistrement » : Date, Titre, Attestée par, Depuis, et une case par ligne. « localisé » : Date, Titre, **Détenteur** (la notice INA, en lien vers le catalogue, ou le détenteur saisi, avec sa note en dessous), **Relance**, **Dernier échange** (il y a combien de jours, et par quel canal), Depuis. Au survol, la colonne « Depuis » donne la date d'entrée dans le niveau.

**Relance.** La relance d'une piste est celle de son dernier échange ; celle d'une émission, la plus proche parmi ses pistes. Elle s'affiche en **rouge** si elle est due, en **ambre** si elle tombe dans les 7 jours, en **gris** au-delà, et « — » s'il n'y en a pas. La page « localisé » s'ouvre triée par relance croissante : les relances dues d'abord, les émissions sans relance à la fin.

**Le journal des échanges** se rattache à une piste, pas à l'émission : si l'émission a plusieurs pistes, le formulaire demande laquelle. Une entrée porte la date (aujourd'hui par défaut), le canal (courriel, téléphone, forum, courrier, sur place, autre), l'interlocuteur (prérempli avec le détenteur), le texte (obligatoire) et la prochaine relance (facultative, avec les raccourcis +7, +15 et +30 jours). Noter un échange ne change ni la maturité ni la date d'entrée dans l'état. Le journal est conservé dans la collection Mongo `pap_echanges` ; il n'est ni exporté en CSV ni publié, car il contient des noms de particuliers.

**Une piste pour plusieurs émissions.** Sur « sans enregistrement », cocher des émissions puis **Une piste pour la sélection (n)** ouvre la saisie de piste dans une boîte : toutes les émissions cochées sont localisées d'un coup, avec le même détenteur, la même note et, si la case est cochée, le même premier échange. Les échanges suivants se notent émission par émission.

### Télécharger les enregistrements (rapatrier)

La page **téléchargeable** télécharge l'intégral des émissions sur le disque de l'appli : bouton **Télécharger** sur une ligne, cases à cocher puis **Télécharger : sélection (N)**, ou **Télécharger : tout (N)** après confirmation. Chaque fichier va dans le dossier audio (`--audios`, variable `PAP_AUDIOS` ; par défaut `data/raw/audios`), sous `<année>/<nom d'origine du fichier>`, et l'émission passe à **rapatrié**.

- **Un intégral par émission** : quand une émission en a plusieurs encodages, le m4a passe avant le mp3.
- **Fichier sûr** : le téléchargement s'écrit dans un `.part`, renommé une fois complet ; une interruption ne laisse jamais de fichier final incomplet. L'empreinte SHA-256 et la taille sont notées dans `pap_enregistrements` ; un fichier déjà présent avec la bonne empreinte n'est pas retéléchargé.
- **Échecs** : un échec passager (délai dépassé, coupure) est retenté jusqu'à trois fois, après 5 puis 15 secondes ; une réponse HTTP autre que 200 ne l'est pas. Un échec persistant s'affiche en rouge sous le titre de l'émission (« échec le 21/11 à 09:23 : … ») jusqu'au prochain succès.
- **Un lot à la fois**, les fichiers l'un après l'autre.

Un **panneau flottant**, en haut à droite, suit le lot sur toutes les pages, et se retrouve après un rechargement ou depuis un autre poste :

- replié : « Téléchargement 3 / 12 » et la barre du lot ;
- déplié : les Mo reçus, le temps restant estimé, l'émission en cours avec son pourcentage, son débit et sa barre ;
- **Arrêter** coupe aussitôt le fichier en cours (le `.part` est supprimé) ; les fichiers finis restent rapatriés ;
- à la fin, le bilan (rapatriés, échecs et leurs erreurs) reste affiché jusqu'à ✕ ; survoler « N rapatriés » liste les dates des émissions rapatriées pendant le lot.

### Écouter et qualifier un enregistrement rapatrié

La page **rapatrié** propose, sur chaque ligne, **Écouter et qualifier** : un lecteur s'ouvre sous la ligne, sur le fichier rapatrié. On s'y déplace librement (barre du lecteur, boutons **−30 s** et **+30 s**) : le fichier se lit par morceaux, sans être téléchargé en entier. Un second clic sur le bouton referme le lecteur.

Pour vérifier ce qu'on entend, le lecteur montre aussi :

- **page radiofrance.fr ↗**, un lien par fiche radiofrance.fr de l'émission, qui s'ouvre dans un nouvel onglet ; sans fiche connue, pas de lien ;
- la diffusion vue par l'**Open API Radio France**, lue à l'ouverture du lecteur : titre, chapô, présentation (animateur), équipe (critiques) et invités. Il faut la clé `RADIOFRANCE_API_TOKEN` dans l'environnement de l'appli (`.env`). Sans clé, sans diffusion du Masque ce jour-là ou si l'API ne répond pas, une ligne le dit ; l'écoute et la qualification restent possibles.

Les données de l'API ne sont gardées que dans la page ouverte et, une heure au plus, dans la mémoire de l'appli : rien n'est écrit sur disque, en base ni dans les logs, qui ne notent que l'appel, son résultat (`trouvée`, `introuvable`, `pas de clé`, `erreur HTTP 403`), le nombre de requêtes faites, le compteur de la journée sur les 1 000 autorisées et la durée : `api radiofrance 2007-01-14 : trouvée, 1 requête (12/1000 aujourd'hui), 1 s`. Une diffusion déjà en mémoire ne coûte rien : `api radiofrance 2007-01-14 : trouvée (cache), 0 requête (12/1000 aujourd'hui)`. Le compteur, commun à l'écoute et à la mise à disposition, vit dans la mémoire de l'appli et repart de zéro à minuit (heure de Paris) ou au redémarrage. Une lecture coûte une à trois requêtes, sur un quota de 1 000 par jour ; écouter puis mettre à disposition la même émission dans l'heure n'en coûte qu'une. Les URL que rend l'API sont sous `www.franceinter.fr` : la diffusion se reconnaît au chemin de sa page, quel que soit le domaine.

La **qualification** juge l'enregistrement, pas l'émission : elle ne change ni l'émission ni son thème.

- **Favorable** : l'enregistrement devient **qualifié** (date d'entrée notée) et l'émission quitte la page rapatrié.
- **Écarter**, avec un motif libre obligatoire (« pas la bonne émission », « coupé à 40 min »…) : l'enregistrement reste **rapatrié**, et la ligne de l'émission affiche « écarté : motif ». Un enregistrement écarté peut être réécouté et qualifié favorable plus tard.

Après chaque qualification, les données sont rechargées et une notification donne les compteurs qui ont changé (« 1987-10-04 qualifié — rapatrié 7→6 · qualifié 0→1 »).

Chaque qualification est conservée dans la collection `pap_qualifications` (enregistrement, émission, verdict, motif, date) et exportée dans `data/processed/qualifications.csv` :

| Colonne | Contenu |
|---|---|
| `emission_id` | Identifiant de l'émission. |
| `enregistrement` | URL de l'enregistrement qualifié. |
| `verdict` | `favorable` ou `ecarte`. |
| `motif` | Le motif d'un écart, vide pour un verdict favorable. |
| `date` | Date et heure de la qualification (ISO 8601, UTC). |

Une ligne par qualification, de la plus ancienne à la plus récente : un enregistrement écarté puis retenu a deux lignes.

### Mettre à disposition de lmelp

La page **qualifié** propose **Mettre à disposition de lmelp** sur chaque ligne, sur une sélection (cases à cocher) ou sur toutes les émissions de la page. Chaque fois, une confirmation est demandée, dans une boîte de la page ; pendant la mise à disposition, la boîte reste ouverte (« Mise à disposition en cours… ») : la lecture de l'API Radio France prend quelques secondes quand la diffusion n'est pas déjà en cache (une heure après l'écoute).

Pour chaque émission :

1. le fichier de l'enregistrement qualifié est copié du dossier audio de pap vers le dossier audio du back-office lmelp (`--audios-lmelp`, variable `PAP_AUDIOS_LMELP` ; par défaut `data/raw/audios-lmelp`), sous le même chemin `<année>/<nom>`, en passant par un fichier `.part` renommé à la fin ; l'empreinte SHA-256 de la copie doit être celle du rapatriement ;
2. une fiche est écrite dans la collection Mongo `pap_remises`, que lit le back-office (titre, date, type, durée, description, page radiofrance.fr, fichier, empreinte) ;
3. l'enregistrement passe à **valide** (date d'entrée notée) : l'émission quitte la page qualifié pour la page « valide (attend lmelp) ».

lmelp prend ensuite l'enregistrement à son rythme. Dès que la collection `episodes` de lmelp contient un épisode de même `audio_rel_filename`, l'émission passe à « dans lmelp ».

Sur les pages « qualifié » et « valide (attend lmelp) », un clic sur une émission (hors case à cocher et bouton) déplie sa **fiche**, c'est-à-dire tout ce que lmelp reçoit : titre, date, type, durée, description (et la source de chacun de ses morceaux), page radiofrance.fr, URL de l'intégral, fichier (`audio_rel_filename`), empreinte SHA-256 et date de la mise à disposition. Pour une émission qualifiée, c'est un **aperçu** : la fiche est calculée à la demande, sans rien copier ni écrire, comme elle le serait si l'émission était mise à disposition maintenant (la lecture de l'API Radio France peut prendre quelques secondes). Un second clic la replie.

Tant que l'émission n'est pas dans lmelp, la page « valide (attend lmelp) » propose sur chaque ligne un petit bouton **Annuler** qui, après confirmation, annule la mise à disposition : la fiche `pap_remises` est retirée, la copie du dossier audio de lmelp aussi (seulement si elle a encore l'empreinte de l'enregistrement : un fichier remplacé chez lmelp est gardé), et l'enregistrement revient à **qualifié**. Une ligne de log le trace (« mise à disposition annulée … »).

Une mise à disposition est **refusée**, sans rien écrire, quand :

- un fichier de même nom, mais d'un autre contenu (autre empreinte SHA-256), existe déjà dans le dossier de lmelp (rien n'est écrasé) ;
- l'émission est déjà dans lmelp ;
- un épisode de lmelp (collection `episodes`) est daté à trois jours près de l'émission, quelle que soit sa voie d'entrée : c'est un doublon (« 2016-06-05 : doublon, épisode lmelp du 2016-06-06 (« … ») ») ;
- l'émission n'a pas d'enregistrement qualifié, ou son fichier manque ou a changé depuis le rapatriement.

Un fichier de même nom et de même empreinte que l'enregistrement est celui d'une mise à disposition interrompue après la copie (panne, redémarrage) : relancer la mise à disposition la termine, sans recopier le fichier (fiche écrite, passage à valide), et le journal le signale (« …, reprise : fichier déjà copié, même sha256 »).

Les refus s'affichent en haut de la page, en rouge, avec l'émission et la raison, jusqu'à **✕** ; la notification donne le bilan et les compteurs changés (« 1 mis à disposition · 1 refus — qualifié 2→1 · valide 0→1 »).

La **description** de la fiche suit le format des descriptions du flux RSS du Masque, que lmelp reprend dans ses épisodes : « durée : 00:54:12  - Le Masque et la Plume - par : Jérôme Garcin - résumé - équipe : … - invités : Arnaud Viviant Critique littéraire (Revue Regards), … » (deux espaces après la durée, chaque invité suivi de son rôle quand l'API le donne). Chaque morceau vient de la première source qui le donne : la page radiofrance.fr de l'émission, puis l'API Radio France, puis la notice INA, sinon l'animateur déduit de la date. La durée est lue dans le fichier m4a, sinon dans les sources. L'API Radio France n'est interrogée que si `RADIOFRANCE_API_TOKEN` est défini (environnement ou `.env`), au moment de la mise à disposition (ou reprise du cache d'une heure de l'écoute) ; ses données ne vont que dans la fiche, et son absence ou son échec, tracé dans le journal (`api radiofrance 2014-09-28 (mise à disposition) : erreur HTTP 403, 1 requête (13/1000 aujourd'hui), 0 s`), n'empêche pas la mise à disposition. Le titre est « Le Masque et la Plume du 28 septembre 2014 » ; le type, `livres`.

### Publier la liste sur GitHub

Le bouton **Publier**, dans l'en-tête de l'accueil, publie sur GitHub ce que l'appli du NAS a décidé : la page GitHub Pages reflète alors les arbitrages faits sur le NAS. Seul le NAS publie ; le bouton répond « Publication impossible » ailleurs (sans `PAP_DEPOT_GIT`, voir [L'appli pap sur le NAS](appli-docker-nas.md#publication-sur-github)).

1. Un clic montre d'abord un **résumé** de ce qui changera sur `main` : émissions ajoutées, retirées ou modifiées, arbitrages et qualifications ajoutés ou retirés, enregistrements ayant changé de niveau depuis la dernière publication (par exemple « 3 émissions changées (1 ajoutée, 2 modifiées), 2 arbitrages ajoutés, 1 enregistrement a changé de niveau (valide 1) »). Sans changement, une notification dit « Rien à publier » et rien n'est commité.
2. Après confirmation, l'appli exporte les arbitrages de Mongo dans `arbitrages.csv`, réécrit `qualifications.csv`, reconstruit la liste, puis commite les fichiers de `data/processed/` (`chore(data): publication depuis le NAS`, le résumé en corps de message), fait un `pull --rebase` et pousse sur `main`.
3. Le push déclenche `docs.yml`, qui reconstruit la page de la liste et la déploie sur GitHub Pages.

Fichiers publiés, et seulement eux : `emissions.csv`, `attestations.csv`, `enregistrements.csv`, `doutes.csv`, `arbitrages.csv` et `qualifications.csv`. La publication est refusée si l'un d'eux porte une colonne inattendue, ou un chemin du NAS (`/volume1/…`, le dossier des audios ou du cache) : jamais d'audio, de chemin NAS ni de donnée de l'API Radio France sur GitHub.

Une publication est **refusée**, sans rien pousser, quand :

- le `pull --rebase` bute sur un conflit : quelqu'un a modifié sur `main` les mêmes lignes de `data/processed/` ; le rebase est abandonné, jamais de push forcé ;
- GitHub rejette le push (jeton absent ou expiré, branche protégée) ;
- un fichier contient ce qui ne se publie pas (voir plus haut).

La boîte affiche la raison du refus, et une alerte ntfy (priorité haute) la transmet. Après un conflit, chaque publication est refusée de même tant que le conflit n'est pas réglé : corriger `main` à la main, ou supprimer le clone (`/data/depot` dans le conteneur) pour repartir de `main`, la publication suivante y reposant les fichiers du NAS. Une publication réussie envoie une notification ntfy « pap - liste publiée » avec le commit et le résumé.

Logs :

```
2026-11-23 18:02:10 INFO    arbitrages : export de pap_arbitrages : 214 arbitrages → /data/processed/arbitrages.csv
2026-11-23 18:02:11 INFO    publication : publication demandée vers main : 2 arbitrages ajoutés
2026-11-23 18:02:14 INFO    publication : 3f1c0e9 poussé sur main (2 arbitrages ajoutés)
2026-11-23 18:02:14 INFO    notification : notification ntfy envoyée : pap - liste publiée
2026-11-23 18:10:40 INFO    publication : rien à publier, aucun commit
2026-11-23 18:20:05 ERROR   publication : publication refusée : conflit au rebase sur main : data/processed/arbitrages.csv (rien n'est poussé ; …)
2026-11-23 18:20:05 INFO    notification : notification ntfy envoyée : pap - publication refusée
```

### Maturité des enregistrements

Avec une base Mongo (`MONGO_URI` et `MONGO_DB`, dans l'environnement ou le fichier `.env`), l'appli suit la **maturité** de chaque enregistrement intégral, c'est-à-dire le niveau atteint sur le chemin qui le mène à lmelp : localisé, téléchargeable, rapatrié, qualifié, valide. Elle la conserve dans la collection `pap_enregistrements`, un document par enregistrement, avec la date d'entrée dans chaque niveau. Un enregistrement est identifié par son URL d'intégral (radiofrance), par l'URL de sa notice (INA) ou par un identifiant `piste:…` (saisie manuelle). Sans base, la page n'a ni badge, ni filtre, ni bouton de vérification.

- La **vérification des URL d'intégral** interroge chaque URL de `enregistrements.csv` (requête `HEAD`, quatre à la fois). Elle part seule :
    - au démarrage de l'appli, si aucune vérification complète n'a encore eu lieu (base neuve) ;
    - quand la dernière vérification complète date de plus de 7 jours (`--verification-jours`, variable `PAP_VERIFICATION_JOURS`) ; l'appli regarde toutes les heures ;
    - après une reconstruction de la liste qui apporte des URL d'intégral jamais vues, pour celles-ci seulement.

  Le bouton **Vérifier les URL des intégraux** du bandeau force une vérification complète et affiche l'avancement, puis le bilan. À côté, la page indique la date de la dernière vérification complète et de la prochaine. Une vérification ne démarre jamais si une autre tourne.

  | Réponse | Effet |
  |---|---|
  | 200 avec un type audio | l'enregistrement est **téléchargeable** |
  | 404, 410, ou 200 sans son (échec net) | un enregistrement téléchargeable redevient **localisé** : Radio France détient toujours le fichier |
  | délai dépassé, erreur réseau, 5xx (échec passager) | noté, niveau inchangé |

  Un enregistrement rapatrié, qualifié ou valide ne change plus de niveau, même si son URL ne répond plus. Une URL jamais vue qui échoue entre au niveau localisé.
- Les **notices INA des Archives Radio Pro** localisent les émissions sans intégral. Chaque notice crée un enregistrement **localisé** de source `ina`, rattaché à la notice : une copie se demande à INA mediapro. L'identifiant de la notice départage les fonds :

  | Notice | Fonds | Effet |
  |---|---|---|
  | `PH_…` | Archives Radio Pro (≈ 1955-1998) | un enregistrement localisé par notice |
  | `RD_…` | Dépôt légal radio (≈ 1995 à aujourd'hui, consultable seulement à l'InaTHÈQUE) | aucun : l'émission reste sans enregistrement |

  Ce préfixe correspond au champ « Base » de la fiche détaillée de la notice. La création se fait seule, au démarrage de l'appli, toutes les heures et après chaque reconstruction de la liste. Elle n'ajoute que les enregistrements absents : la relancer ne change rien, et elle n'écrase ni une piste saisie à la main ni un enregistrement déjà plus avancé. Une émission qui a une URL d'intégral n'en reçoit pas. Les archives de Radio France ne localisent aucune émission tant qu'elles n'ont pas répondu : leur réponse se saisit comme une piste. Le journal note chaque création :

  ```
  2026-11-22 17:40:02 INFO    arbitrer : localisation INA : 273 enregistrements localisés créés (273 notices des Archives Radio Pro)
  2026-11-22 17:45:10 INFO    arbitrer : enregistrement localisé ajouté : 2008-03-02 (source « Jean D., forum », premier échange forum)
  2026-11-22 17:46:31 INFO    arbitrer : piste en lot : 3 émissions localisées (source « Jean D., forum »)
  2026-11-22 17:50:02 INFO    arbitrer : échange noté : 2008-03-02, piste piste:3f2a… (Jean D., forum), courriel, relance le 2026-12-22
  2026-11-22 17:52:40 INFO    arbitrer : URL enregistrée : 2008-03-09 https://exemple.org/masque.mp3 → téléchargeable
  2026-11-22 17:55:12 INFO    arbitrer : fichier téléversé : 2008-03-16 2008/masque 2008-03-16.mp3, 52428800 octets (provenance « Jean D., cassette numérisée », piste piste:3f2a…)
  2026-11-22 17:56:03 INFO    arbitrer : fichier refusé 2008-03-16 : 2008/masque 2008-03-16.mp3 : nom de fichier déjà pris
  ```

  Chaque refus laisse sa ligne, avec son motif : `piste refusée …`, `échange refusé …`, `URL refusée …`, `fichier refusé …`.
- Chaque émission porte un badge : le niveau de son enregistrement le plus avancé, ou **dans lmelp** si lmelp l'atteste, état qui l'emporte sur la maturité.
- Le filtre **Maturité** retient un niveau, « dans lmelp », ou les émissions sans enregistrement suivi.

## Règles de construction

**Rapprochement.** Deux attestations décrivent la même émission si elles ont la même date, ou au plus trois jours d'écart avec des thèmes compatibles. Un thème inconnu est compatible avec tous les thèmes.

**Archive partagée.** Deux émissions qui ont une date d'attestation en commun et dont des enregistrements partagent une archive (`ITEMA_24209925`) sont une seule émission : leurs attestations sont réunies, quels que soient leurs thèmes. Une fiche par livre que radiofrance.fr étiquette d'un thème incompatible avec l'émission (« Les Piliers de la Mer », de Sylvain Tesson, étiquetée « cinéma » le 3 août 2025) rejoint ainsi l'émission entière, au lieu de former une émission `-b` ; son thème produit un doute `thèmes divergents`. Une archive partagée sans date commune (`ITEMA_24041574`, en 1992 et en 2013) signale une republication : les émissions restent distinctes. La réunion a lieu avant les arbitrages de rapprochement.

**Archive d'une autre émission.** Une attestation dont un enregistrement porte, dans le nom de son fichier, une date à plus de trois jours de la sienne, et l'archive (ITEMA) d'une autre émission datée de ce jour-là, rejoint cette émission. La fiche « L'État sauvage », de Georges Conchon, que radiofrance.fr date du 16 novembre 1961, porte ainsi le fichier `14007-15.11.1964-ITEMA_23788885-…`, l'archive de l'émission du 15 novembre 1964 : elle rejoint cette émission. Dans l'émission qu'elle rejoint, sa date devient une date de **publication** : elle reste dans `attestations.csv`, mais ne date pas l'émission, n'entre pas dans le désaccord de date et ne la rapproche d'aucune autre émission. La règle déplace une attestation, jamais une émission entière :

- une émission dont toutes les attestations partiraient reste distincte : une émission qui republie l'archive d'une autre n'est pas fusionnée avec elle ;
- une fiche qu'une source vérifiée rattache à son émission y reste ;
- une attestation qui porte un arbitrage de rapprochement (`garder ici` ou une attestation cible) reste où l'arbitrage la met : la décision humaine l'emporte ;
- une archive (ITEMA) qui désigne plusieurs émissions candidates datées du jour du fichier ne déplace rien ;
- le fichier doit être daté du jour même de l'émission retenue : une archive remise en ligne un vendredi (`14007-24.10.2024-ITEMA_23902448-…`, des archives de 1959 sur François Truffaut) ne rejoint pas l'émission du dimanche suivant.

Le déplacement a lieu après la réunion des archives partagées et avant les arbitrages de rapprochement.

**Extraits.** Un extrait atteste son émission sans la décrire en entier :

- une fiche radiofrance.fr est un extrait si elle dure moins de 25 minutes ou si son fichier audio porte la lettre `E` ; une fiche sans durée décrit l'émission entière ;
- les champs de l'émission viennent d'abord d'une attestation de l'émission entière (fiche longue, notice INA), et seulement à défaut d'un extrait ; une émission ancienne prend ainsi le titre de sa notice INA (« Littérature »), le titre de l'extrait restant dans les attestations ;
- la durée ne vient jamais d'un extrait ;
- les thèmes se cumulent : ceux de toutes les attestations, extraits compris, sauf quand lmelp atteste l'émission ;
- une archive dont la durée atteint 90 % de la durée de diffusion INA, ou au moins 45 minutes quand cette durée est inconnue, est l'émission entière, pas un extrait. Ses fichiers deviennent des intégraux dans tous leurs encodages et toutes leurs sources ; les autres segments de la même archive (ITEMA), qui peuvent être de vrais extraits, gardent leur type.

**Fusion.** Chaque champ de l'émission vient de la source la plus prioritaire qui le renseigne, parmi les attestations de l'émission entière d'abord (voir ci-dessus) :

| Champ | Priorité |
|---|---|
| Date | radiofrance > ina > anciennes_listes > wayback_podcast |
| Titre, description | radiofrance > ina |
| Chaîne, heure, durée | ina > radiofrance |
| Animateur | radiofrance > ina, sinon déduit de la date |

Les enregistrements de toutes les sources sont conservés. Leur type (`intégral` ou `extrait`) vaut pour tous les fichiers d'une même archive Radio France (ITEMA) : la Wayback Machine ne voit que le nom d'un fichier, radiofrance.fr en connaît la durée. Les décisions sur le format et le périmètre de la liste sont dans `docs/adr/`.
