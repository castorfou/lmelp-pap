# Les intégraux du Masque à l'INA : Madelen, ina.fr, catalogue, rapatriement

Recherche pour l'issue #51 (carte #48). Question : quelles émissions du Masque et la
Plume l'INA propose-t-elle en écoute intégrale, et peut-on les rapatrier pour un usage
privé (téléchargement, export, coût, sinon démarche) ?

Sources lues le 19/11/2026 :

- madelen.ina.fr : moteur de recherche du site (`/api/ajax/search?query=…`, celui
  qu'appelle la page `/search`), page d'aide (`/page/aide`), CGU (`/legal-cgu`, mai
  2023) et CGV (`/legal-cgv`).
- ina.fr : recherche `https://www.ina.fr/recherche?q=masque+et+la+plume` et deux
  articles « INA éclaire l'actu » consacrés au Masque.
- Cache local du catalogue INA (`data/raw/cache/ina/notices.csv`, 3 621 notices de la
  collection « Le masque et la plume », et les 3 621 fiches détaillées
  `data/raw/cache/ina/fiches/*.html`), croisé avec `data/processed/emissions.csv`,
  `enregistrements.csv` et `attestations.csv` de `main` @ `303738e`.
- inamediapro.com (page d'accueil), bnf.fr (salles A et P), page InaTHÈQUE de la BU de
  Grenoble Alpes.

## Réponse courte

- **Aucune émission du Masque n'est écoutable intégralement en ligne à l'INA.**
  Madelen est une offre vidéo (« les meilleurs programmes créés pour la télé ») : la
  recherche « masque et la plume » ne renvoie aucun numéro, ni radio ni télé (la
  version FR3 de 1976 n'y est pas non plus). ina.fr ne propose que des **extraits**
  (1 à 14 minutes) dans 21 contenus éditoriaux.
- **Les fiches du catalogue n'ont aucun indicateur de disponibilité** (ni lien Madelen,
  ni lecteur, ni mention « consultable en ligne ») : seulement la base d'origine
  (`BASE`), le fonds (`FONDS`) et, pour le dépôt légal, le numéro du support (`DL`,
  `TIDL`, `SELDL`).
- **Le catalogue atteste en revanche presque toutes les émissions sans intégral** :
  506 des 516 émissions sans intégral ont au moins une notice INA, dont 456 d'une durée
  d'au moins 40 minutes (donc vraisemblablement l'émission entière conservée). 511 des
  516 sont littéraires (thème `livres`).
- **Rapatriement** : Madelen n'en offre aucun (et n'a pas le Masque) ; ina.fr non plus.
  Les deux voies réelles sont **INA mediapro** (vente aux professionnels, pour les
  notices « Archives Radio Pro », ~1955-1998) et la **consultation sur place à
  l'InaTHÈQUE** (chercheurs accrédités, écoute seule, pas de copie). Pour un
  particulier, il n'existe pas d'offre publique de copie à usage privé : la seule
  démarche possible est une demande écrite à l'INA (contact INA mediapro), sans
  garantie.

## 1. Madelen

### Le Masque n'y est pas

Requêtes envoyées au moteur de recherche du site (`https://madelen.ina.fr/api/ajax/search?page=N&query=…`,
pages 1 à 5 pour « le masque et la plume ») : `masque et la plume`, `masque`, `plume`,
`garcin`, `bastide`, `polac`, `pierre bouteiller`, `critique`, `france inter`,
`radio`, `france culture`. Aucun résultat n'appartient à la collection « Le masque et
la plume » ; les correspondances sont *Le Masque et la Vérité* (Apostrophes, 1984),
*Le Masque de Fer* (Alain Decaux raconte), *Plume au vent* (Airs de France), etc.
Toutes les catégories rencontrées sont vidéo : Émissions, Documentaires, Films,
Séries, Théâtre, Musique.

La page d'aide présente le service comme vidéo : « madelen est la plateforme de
streaming de l'INA qui fait découvrir à tous les curieux d'aujourd'hui les meilleurs
programmes créés pour la télé depuis qu'elle existe » (`/page/aide`). Les CGV
définissent les Contenus comme des « Contenus audiovisuels » et le Streaming comme la
« Visualisation d'un Contenu audiovisuel » (`/legal-cgv`).

Les articles de presse de 2020 sur des « programmes radio » dans Madelen décrivent une
offre antérieure ; le catalogue actuel ne les contient pas (aucun résultat radio aux
requêtes ci-dessus).

### Prix et conditions (pour mémoire)

- **Prix** : « gratuitement pendant 7 jours, puis au prix de 3,99€ TTC par mois ou
  39,99€ TTC par an, sans engagement » (depuis le 2 mars 2026 ; 2,99 €/29,99 €
  auparavant) — `/page/aide`.
- **Téléchargement** : seulement le « Téléchargement temporaire » dans l'application
  mobile, « pour une durée de 30 (trente) jours suivant le téléchargement » (CGV,
  définitions) ; « les Contenus étant uniquement disponibles en streaming, ils ne
  peuvent en aucun cas être téléchargés (en dehors des fonctionnalités de
  téléchargement offertes sur le Site) » (CGU art. 3.2). Aucun export de fichier.
- **Usage** : « pour un usage strictement personnel dans le cercle de famille » (CGV,
  définition de l'Offre SVOD).

Conclusion : un abonnement Madelen n'apporte rien au projet.

## 2. ina.fr

La recherche ina.fr renvoie 21 contenus pour « masque et la plume », tous éditoriaux
(« INA éclaire l'actu »). Les deux articles de fond n'embarquent que des extraits :

- « Le masque et la plume : 70 ans d'impertinence… » : 16 documents, de 2 à 12 minutes
  (audio 1956-1989, vidéo FR3 1976), présentés comme extraits.
- « Les films que Le masque et la plume a aimés, ou pas » : 9 documents de 1 à 14
  minutes (1957-1983).

Ces extraits ne sont pas des intégraux au sens de la carte #48 (reconstituer un
intégral à partir d'extraits est hors périmètre). La plateforme podcasts.ina.fr est une
application JavaScript qui n'a pas pu être interrogée ici.

## 3. Catalogue INA (catalogue.ina.fr) : ce que disent les fiches en cache

### Pas d'indicateur de disponibilité

Les 3 621 fiches en cache contiennent 41 champs `<td id="…">`. Aucun ne signale une
mise en ligne ou une consultation possible ; les seuls liens des pages sont ceux du
gabarit (madelen.ina.fr, inatheque.fr, inamediapro.com…), identiques sur toutes les
fiches. Les champs utiles pour l'accès sont :

| Champ | Valeurs | Sens |
|---|---|---|
| `BASE` | Archives Radio Pro (1 389), Dépôt Légal Radio (2 220), Archives TV Pro (12) | base d'origine de la notice |
| `FONDS` | INA (619), INA - Radio France (757), Radio France Production (2 220), Club d'Essai (12)… | détenteur du fonds |
| `DL`, `TIDL` | ex. `DL R 20191006 FIT 12`, « France Inter, 6 octobre 2019, 12 h - 24 h » | support du dépôt légal : une captation de l'antenne par tranche de 12 h |
| `SELDL` | `O` (1 603) | « Sélection DL » : notice documentée parmi le flux capté |

### Répartition des notices par base

| Décennie | Archives Radio Pro | Dépôt Légal Radio | Archives TV Pro |
|---|---|---|---|
| 1950 | 108 | | |
| 1960 | 358 | | |
| 1970 | 356 | | 12 (FR3, 1976) |
| 1980 | 377 | | |
| 1990 | 181 | 290 | |
| 2000 | | 494 | |
| 2010 | | 693 | |
| 2020 | | 743 | |

(9 notices Archives Radio Pro sans date.) Bascule vers 1995 : avant, les archives
professionnelles de l'INA (fonds INA ou INA - Radio France) ; après, le dépôt légal de
la radio (Radio France Production).

### Croisement avec la liste (516 émissions sans intégral)

| Décennie | Notice INA | dont durée ≥ 40 min | Sans notice |
|---|---|---|---|
| 1950 | 44 | 16 | |
| 1960 | 81 | 66 | |
| 1970 | 41 | 39 | 1 |
| 1980 | 62 | 57 | |
| 1990 | 109 | 109 | |
| 2000 | 150 | 150 | 8 |
| 2010 | 19 | 19 | 1 |
| **Total** | **506** | **456** | **10** |

Par base (une émission peut avoir des notices dans deux bases) : environ 267 émissions
relèvent des Archives Radio Pro (1955-1998) et 239 du Dépôt Légal Radio (1995-2010).
Les notices courtes des années 1950 sont souvent des fragments ou des émissions
découpées en plusieurs notices (`TYPDESCR` « Emission simple incluse »). 511 des 516
émissions sans intégral ont le thème `livres`.

## 4. Démarches de rapatriement

### INA mediapro (archives professionnelles)

inamediapro.com s'adresse aux professionnels (« Les contenus de l'Ina pour les
professionnels ») et couvre la radio (« Collection Radio INA », « Fonds Ina Radio »).
Le compte doit être rattaché à une société (« Votre compte Ina MEDIAPRO n'est associé à
aucun nom de société ») ; les tarifs ne sont pas publics (bandeau « Grille tarifaire »)
et une « recherche documentaire payante par un documentaliste de l'Ina » est proposée.
Les CGV de Madelen confirment la séparation : les cessions de droits d'exploitation sur
les archives se font « auprès des professionnels […] notamment via le site
inamediapro.com ».

Ce canal ne vaut que pour les notices Archives Radio Pro (l'INA en est détenteur ou
codétenteur avec Radio France). Pour un particulier : pas d'offre en libre-service ;
une demande écrite au service commercial (contact INA mediapro) en expliquant l'usage
privé et non diffusé est la seule voie, avec un devis probable par heure de
programme. Non vérifié : aucune page publique ne décrit une offre « copie privée » pour
les particuliers.

### InaTHÈQUE (dépôt légal et archives, sur place)

- À la BnF, les collections du dépôt légal de l'INA se consultent en salle P
  (bibliothèque de recherche) ; la BnF précise ne pas détenir de droits d'exploitation
  et que « l'accord des ayants-droits est donc le préalable indispensable à toute
  demande » de reproduction (bnf.fr, « Consulter collections audiovisuelles en salle A
  et en salle P »).
- Dans les centres en région (ex. BU Grenoble Alpes) : accès sur formulaire
  d'accréditation, postes « for viewing only », copie sur clé USB interdite.
- Le régime du dépôt légal (Code du patrimoine, livre I, titre III) réserve la
  consultation sur place à des chercheurs accrédités ; le texte exact n'a pas pu être
  récupéré en ligne lors de cette recherche.

Utile pour **vérifier** qu'une notice correspond bien à l'émission entière et noter sa
durée, pas pour rapatrier un fichier. Les 239 émissions du dépôt légal (1995-2010)
n'ont pas d'autre canal INA : leur détenteur est Radio France (fonds « Radio France
Production »), ce qui renvoie aux pistes Radio France de la carte (#49, #50).

## Ce qui reste incertain

- Le tarif réel d'INA mediapro pour une copie d'archive radio, et son acceptation d'une
  demande de particulier : à demander.
- Le contenu de podcasts.ina.fr (application JavaScript non interrogée).
- Le catalogue Madelen change (« Continuer d'alimenter notre catalogue avec de
  nouvelles acquisitions ») : une nouvelle recherche « masque et la plume » sur
  `https://madelen.ina.fr/search` suffit pour revérifier.
