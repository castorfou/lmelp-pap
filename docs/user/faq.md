# FAQ : lever les doutes

Questions fréquentes pendant l'arbitrage avec `lmelp-pap arbitrer`. La définition de chaque type de doute et le format de `arbitrages.csv` se trouvent dans [la liste des émissions](liste-des-emissions.md#doutescsv).

## Méthode

### Par où commencer ?

Par les doutes des émissions **dans la liste** (`dans_la_liste = oui`) : ce sont les seuls qui peuvent changer la liste. Dans l'outil, filtrer sur une année, puis sur un type de doute, et traiter un type à la fois.

Un doute d'une émission hors de la liste (cinéma, théâtre) n'a pas d'effet sur la liste. Il ne vaut la peine d'être levé que s'il laisse penser que l'émission est en fait littéraire.

### Faut-il toujours arbitrer ?

Non. Un doute se lève, dans l'ordre de préférence :

1. par une **règle**, quand un motif explique beaucoup de cas ;
2. par une **source**, quand l'information manque : une collecte à rafraîchir, une nouvelle source ;
3. par un **arbitrage**, en dernier recours.

Un arbitrage posé sur un doute qui vient d'un cache périmé reste attaché à un faux problème : rafraîchir d'abord (voir [Le doute vient-il d'un cache en retard ?](#le-doute-vient-il-dun-cache-en-retard)).

### Comment vérifier l'effet d'un arbitrage ?

L'outil reconstruit la liste à chaque clic et réécrit `data/processed/`. L'effet se voit dans la page, et dans `git diff data/processed/doutes.csv` : les lignes du doute levé disparaissent. Committer ensuite `arbitrages.csv` et les CSV de la liste.

## Sources et cache

### Le doute vient-il d'un cache en retard ?

Le cache ne se met pas à jour tout seul. Une émission récente peut être connue d'une source (lmelp, souvent) et absente d'une autre dont la collecte est plus ancienne. Pour vérifier, regarder la fiche la plus récente du cache :

```bash
ls data/raw/cache/radiofrance/fiches | grep "$(date +%Y)" | sort | tail -3
```

Si elle est antérieure à l'émission, rafraîchir la source, puis laisser la construction lever le doute :

```bash
uv run --active lmelp-pap emissions --source radiofrance --refresh
```

Le rafraîchissement réécrit les CSV de `data/processed/` : quitter `lmelp-pap arbitrer` avant, et le relancer après (voir [Peut-on arbitrer pendant un rafraîchissement ?](#peut-on-arbitrer-pendant-un-rafraichissement)).

### Combien de temps prend un rafraîchissement de radiofrance ?

Compter de 5 à 15 minutes. Le `--refresh` parcourt toutes les pages de la liste des podcasts sur radiofrance.fr, jusqu'à la dernière, sans s'arrêter aux fiches déjà connues :

- chaque page coûte une requête et une pause d'une seconde, pour une bonne centaine de pages ;
- seules les fiches absentes du cache sont téléchargées, chacune avec une requête et une pause d'une seconde. Le site ajoute parfois d'anciennes fiches à son catalogue : un rafraîchissement n'apporte donc pas que des émissions récentes ;
- quand le site limite le débit, la collecte attend 10 s, puis 20 s, puis 40 s avant de réessayer.

### Peut-on arbitrer pendant un rafraîchissement ?

Non. Au début d'un rafraîchissement, la collecte supprime le marqueur `collecte_terminee` de la source, et ne le remet qu'à la fin. Entre les deux, la construction de la liste considère la source comme incomplète et l'ignore. Un arbitrage enregistré pendant ce temps reconstruit la liste **sans cette source**, et réécrit les CSV de `data/processed/` avec beaucoup d'émissions et de doutes en moins.

Interrompre un rafraîchissement (Ctrl+C) a le même effet, durable : le marqueur ne revient pas, et toutes les constructions suivantes ignorent la source jusqu'à ce qu'un rafraîchissement aille à son terme.

La bonne séquence :

1. quitter `lmelp-pap arbitrer` ;
2. lancer le rafraîchissement et le laisser finir ;
3. vérifier que le marqueur est revenu, puis relire le `git diff` des CSV de `data/processed/` ;
4. relancer `lmelp-pap arbitrer`.

```bash
ls data/raw/cache/radiofrance/collecte_terminee
git diff --stat data/processed/
```

### Que veut dire « sans fiche radiofrance » ?

lmelp donne l'adresse de la fiche radiofrance.fr de l'émission, et cette fiche n'est pas dans le cache radiofrance. L'attestation lmelp est alors rattachée par la date. Deux causes :

- **la fiche est récente** et le cache est plus ancien : rafraîchir radiofrance (cas le plus fréquent pour les émissions des dernières semaines) ;
- **l'URL enregistrée dans lmelp est fausse** : la corriger dans lmelp.

Ce doute ne s'arbitre pas.

## Dates

### Pourquoi un fichier de podcast est-il daté du vendredi ou du samedi ?

La date inscrite dans le nom d'un fichier audio (`14007-13.02.2026-ITEMA_…`) est sa date de **mise en ligne**, pas celle de la diffusion. Le podcast est souvent publié un ou deux jours avant le dimanche. Ce décalage produit des `rapprochement ambigu` (le fichier est rapprochable aussi d'une émission du vendredi), des `jour inhabituel` et des `désaccord de date`.

### Comment savoir à quelle émission appartient un fichier ?

Par son numéro **ITEMA** : les fichiers qui partagent le même `ITEMA_…` sont des morceaux du même enregistrement. Si un fichier a le même ITEMA que l'enregistrement complet d'une émission (durée proche d'une heure dans `enregistrements.csv`), il appartient à cette émission.

```bash
grep ITEMA_24408480 data/processed/enregistrements.csv
```

## Rapprochements

### Quel arbitrage pour un « rapprochement ambigu » ?

Le `detail` donne l'émission rivale. Deux réponses possibles :

- l'attestation est à sa place : arbitrage de rapprochement **`garder ici`** ;
- elle appartient à l'émission rivale : arbitrage de rapprochement vers une attestation de l'émission cible.

Le titre de la fiche (« Le Masque et la Plume du dimanche 29 mars ») ou le numéro ITEMA suffit le plus souvent : justification « titre explicite ».

### Que sont les émissions `-b` qui n'ont que des extraits ?

Une émission suffixée `-b` (ou datée d'un vendredi) qui n'a que des extraits est le plus souvent faite de **fiches par livre** ou de fichiers de podcast mis en ligne autour de l'émission du dimanche. Elle a typiquement une `collision`, une `attestation fragile` ou un `jour inhabituel`. Rattacher ses attestations à l'émission du dimanche fait disparaître l'émission fantôme, et ses doutes avec elle.

### Que devient une fiche par livre étiquetée d'un autre thème que l'émission ?

radiofrance.fr étiquette parfois une fiche par livre d'un thème incompatible avec l'émission : « Les Piliers de la Mer », de Sylvain Tesson, est étiquetée « cinéma » le 3 août 2025. Le rapprochement, qui exige des thèmes compatibles, ne suffit pas à la rattacher à l'émission du dimanche.

Le numéro ITEMA la rattache : l'enregistrement de la fiche appartient à la même archive que l'émission entière (`ITEMA_24209925`). La règle de l'**archive partagée** réunit deux émissions qui ont une date d'attestation commune et un ITEMA commun (voir [les règles de construction](liste-des-emissions.md#regles-de-construction)). La fiche rejoint l'émission du dimanche, et son thème erroné produit un doute `thèmes divergents`, à lever par un arbitrage de thème si l'émission n'est pas attestée par lmelp.

Une paire `X` / `X-b` qui subsiste n'a pas d'archive commune : ce sont deux émissions distinctes, ou un rapprochement ambigu à arbitrer.

### Que faire d'un doute « republication » ?

Le doute signale une attestation dont l'enregistrement est daté, dans le nom de son fichier, à plus de trois jours d'elle : une émission remise en ligne plus tard, ou une fiche que radiofrance.fr date mal.

Quand l'archive (ITEMA) du fichier appartient à une autre émission, datée du jour du fichier, la fiche rejoint cette émission et le doute disparaît : c'est la règle de l'**archive d'une autre émission** (voir [les règles de construction](liste-des-emissions.md#regles-de-construction)). La fiche « L'État sauvage », datée du 16 novembre 1961 et dont le fichier est l'archive de l'émission du 15 novembre 1964, rejoint ainsi cette émission.

Le doute reste dans deux cas :

- aucune autre émission ne porte l'archive, ou elle n'est pas datée du jour du fichier : une archive remise en ligne un vendredi, par exemple ;
- la fiche est la seule attestation de son émission : la règle ne fusionne pas deux émissions.

Pour le lever, vérifier l'émission à l'écoute ou par le titre de la fiche, puis poser un arbitrage d'existence : **Existe** lève le doute (voir [Comment lever une attestation fragile ou une republication ?](#comment-lever-une-attestation-fragile-ou-une-republication)), **N'existe pas** écarte l'émission.

## Existence

### Comment lever une attestation fragile ou une republication ?

Par un arbitrage d'existence **Existe**, quand une pièce suffit à dire que l'émission a été diffusée. Exemples :

- `attestation fragile` : l'émission du 18 octobre 1975, « La Vie devant soi », d'Émile Ajar, n'est attestée que par un extrait d'archive de quatre minutes. Le titre suffit à dire qu'elle a existé : justification « titre explicite » ;
- `republication` : radiofrance.fr a remis en ligne d'anciennes fiches, dont le fichier est daté du jour de la remise en ligne (2024-10-24, 2025-02-28). L'émission n'est pas en doute, seul son fichier est récent.

« Existe » lève les deux doutes d'existence et rien d'autre : le thème, la date et l'appartenance à la liste ne changent pas. Arbitrer le thème ou retenir la date ne les lève pas ; recliquer ces boutons ajoute seulement des lignes à `arbitrages.csv`. Entre « Existe » et « N'existe pas », le plus récent l'emporte.

## Thèmes

### Comment trancher un « thème inconnu » au titre générique ?

Les notices INA des années 1980-2000 portent pour la plupart un titre générique (« Le masque et la plume du 13 janvier 1985 »). Leur **fiche détaillée** donne souvent le thème : descripteurs, chapeau, résumé producteur (« LITTERAIRE : avec la participation de… »), à défaut résumé documentaire. La collecte INA les met en cache et la construction en tire le thème (voir [Les fiches détaillées INA](liste-des-emissions.md#les-fiches-detaillees-ina)) : un thème inconnu qui subsiste n'a rien dans sa fiche non plus. Le lien de la notice, dans les attestations de l'émission, ouvre cette fiche pour vérifier.

Quand ni le titre ni la fiche ne donnent le thème, rien ne permet de le trancher sur pièces. Le **renvoi à l'écoute** range l'émission sous « À écouter », pour que la file « À trancher » ne garde que ce qui peut l'être.

Un thème inconnu au titre explicite (« Hommage à Jean-Louis Bory ») se tranche directement : justification « titre explicite ».

### Que faire des « thèmes divergents » sur des extraits ?

Une fiche d'extrait peut porter deux thèmes (`cinéma+théâtre`) quand l'émission entière n'en a qu'un. Si l'émission est hors de la liste et qu'aucune source ne la dit littéraire, le doute n'a pas d'effet sur la liste. Sinon, un arbitrage de thème fixe les thèmes de l'émission.
