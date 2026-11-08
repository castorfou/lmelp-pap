# Archives web, Radio France et INA : ressources en ligne attestant les émissions du Masque et la Plume (1955-2016)

Légende : **[vérifié]** = constaté par requête réelle le 2026-11-08 ; **[supposé]** = déduit ou non testé.

## 1. Familles d'URL Radio France dans la Wayback Machine (CDX), comptes par année, trou 2009-2011

### Takeaway
Quatre générations de sites Radio France sont archivées. Le trou 2009-2011 se comble par la famille `franceinter.fr/em/lemasqueetlaplume/{id}` et surtout par les listes mensuelles `franceinter.fr/archives-diffusions/319/AAAA-MM`. Ces listes remontent jusqu'à décembre 2002 (« 455 archives » en 2011) mais seulement 30 mois sont capturés. Ce trou est de toute façon couvert par une source plus riche, le site actuel radiofrance.fr (section 2).

### Cited Findings
Requêtes `https://web.archive.org/cdx/search/cdx?url=<préfixe>&matchType=prefix&collapse=urlkey&fl=timestamp,original,statuscode`. Les comptes portent sur les **URL uniques**, et l'année est celle de la **première capture**. L'API CDX renvoie souvent « Temporarily Offline » ou 504 : il faut prévoir des relances.

**Famille A, site radio-france.fr 2002-2004** — [CDX radio-france.fr/chaines/france-inter](https://web.archive.org/cdx/search/cdx?url=radio-france.fr/chaines/france-inter&matchType=prefix&collapse=urlkey)
- Motif : `http://radio-france.fr/chaines/france-inter01/emissions/masque/index.php?{affichage=archive|diffusion|presentation|contact}` ; fiches `index.php?date_demande=JJ-MM-AAAA&emission=86&affichage=fiche` et `index.php?numero=NNNNN&emission=86&affichage=fiche`. Pages annexes : `historique.php`, `prix.php`, `enregistrement.php`. **[vérifié]**
- Volume : 21 URL uniques capturées en 2003, 1 en 2004, 1 en 2006 (un 404 sur `diremissions/masque/`). Les fiches datées capturées vont du 22-12-2002 au 02-02-2003 (6 dates), plus 3 fiches `numero=`. **[vérifié]**
- Contenu de la page `affichage=archive` (capture du 2003-01-04) : elle ne liste que les dernières émissions, « Le 29 décembre 2002 Livres / Le 22 décembre 2002 Cinéma », avec la mention « vous ne pouvez pas réécouter les émissions ». **[vérifié]** — [capture](https://web.archive.org/web/20030104034410/http://radio-france.fr:80/chaines/france-inter01/emissions/masque/index.php?affichage=archive)
- Le même site est aussi capturé sous `www.franceinter.com/chaines/france-inter01/emissions/masque/` (captures 2003 : archive, diffusion, prix.php). **[vérifié]**
- Intérêt : **faible**, couverture minime.

**Famille B, radiofrance.fr/franceinter/em/lemasqueetlaplume/ (2006-2009)** — déjà connue, voici les comptes exacts.
- 103 URL uniques : première capture en 2006 (7), 2007 (25), 2008 (56), 2009 (7), puis quelques-unes plus tard. Parmi elles, 72 fiches `index.php?id=N` et `archives.php?annee=2002…2008` (7 années, capturées en 2007-2008). **[vérifié]**
- Miroir `franceinter.com/franceinter/em/lemasqueetlaplume/` : 2 URL seulement (2008). **[vérifié]**

**Famille C, franceinter.fr « v1 » 2009-2012 (comble le trou)** **[vérifié]**
- Fiches : `http://www.franceinter.fr/em/lemasqueetlaplume/{id}` donne 58 URL uniques, avec des id de 11817 à 105359. Première capture : 2011 (18), 2012 (31), 2013-2016 (7). Exemple : la fiche id 100011, « l'émission du dimanche 20 février 2011, 21e Prix des Auditeurs », donne le thème, les critiques avec leur journal, les œuvres, ainsi que des liens « émission précédente du 13/02/2011 Livres / à venir du 27/02/2011 Théâtre ». — [capture](https://web.archive.org/web/2012/http://www.franceinter.fr/em/lemasqueetlaplume/100011)
- **Listes mensuelles** : `http://www.franceinter.fr/archives-diffusions/319/AAAA-MM` (319 est l'identifiant de l'émission dans ce CMS). 30 mois sont capturés : 2002-12, 2003-12, 2004-12 … 2009-12 (un seul mois, décembre, pour chaque année de 2002 à 2009), 2010-09, 2010-10, 2010-12, puis chaque mois de 2011-01 à 2012-06, et 2012-12. Toutes ces captures datent de juillet 2011 ou après. — [CDX](https://web.archive.org/cdx/search/cdx?url=franceinter.fr/archives-diffusions/319&matchType=prefix&collapse=urlkey)
  - La page 2005-12 affiche « **455 archives dont 43 à (ré)écouter** » et la liste « Cinéma du 25/12/2005, Théâtre du 18/12/2005, Cinéma du 11/12/2005, Cinéma du 04/12/2005 », chacune liée à `/em/lemasqueetlaplume/{id}` (ids 38786-39152). — [capture](https://web.archive.org/web/2012/http://www.franceinter.fr/archives-diffusions/319/2005-12)
  - La page 2011-03 affiche « **478 archives dont 66 à (ré)écouter** ». Les entrées y sont enrichies : « Théâtre du 27/03/2011 Les pièces critiquées : La Célestine (Amandiers-Nanterre) - Adagio (Odéon)… ». — [capture](https://web.archive.org/web/2012/http://www.franceinter.fr/archives-diffusions/319/2011-03)
- Autres pages : `franceinter.fr/reecouter-diffusions/319?page=0..5` (6 URL), `franceinter.fr/diffusions-a-venir/319`, `franceinter.fr/programmes/AAAA-MM-JJ` (grille quotidienne, non comptée), `franceinter.fr/emission-le-masque-et-la-plume-saison-2011-2012`. **[vérifié]** pour l'existence, **[supposé]** pour le détail des grilles.

**Famille D, franceinter.fr « v2 » (Drupal) 2011-2016** — déjà connue. `franceinter.fr/emission-le-masque-et-la-plume[-slug]` : 291 URL uniques. Première capture : 2011 (26), 2012 (56), 2013 (80), 2014 (53), 2015 (50), 2016 (25). Les slugs sont du type `-cinema-12`, `-6-films-passes-au-crible-de-nos-critiques`, `-23e-prix-des-auditeurs…`. **[vérifié]**

### Inferences
- Le CMS franceinter.fr v1 (2009-2012) contenait une base de 455 à 478 fiches remontant à fin 2002, la même que celle de la famille B (dates et thèmes identiques). Les dates et thèmes de 2002-2008 sont donc déjà couverts par `archives.php?annee=` (famille B) ; la famille C apporte surtout 2009-2011. **[supposé]**
- Pour la période 2003-2016, toutes ces familles Wayback sont largement redondantes avec radiofrance.fr (section 2). Leur intérêt se limite au recoupement et aux cas où une page radiofrance.fr est vide.

### Gaps
- Le site radio-france.fr des années 1996-2001 : la requête CDX par domaine filtrée sur « masque|plume » (to=2002) a échoué deux fois en 504 Gateway Time-out. L'existence de pages pour l'émission avant 2002 n'est donc pas vérifiée. La capture la plus ancienne de `radio-france.fr/chaines/france-inter` date de 2000-01-24 (301). Celle de `franceinter.com/` date de 1999-01-25.
- Je n'ai pas vérifié si les fiches de la famille C (`/em/lemasqueetlaplume/{id}`) restent accessibles en masse au-delà des 58 capturées : les id ne sont pas séquentiels par émission.

## 2. Radio France : site actuel radiofrance.fr et Open API (GraphQL)

### Takeaway
**Découverte majeure** : la page podcast actuelle `https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume?p=N` est paginée (116 pages, « 2 277 épisodes ») et remonte en continu jusqu'au **4 janvier 2003**. Chaque fiche donne la date, le thème, les critiques et la **liste des livres avec leur éditeur**, sans authentification. Elle contient aussi environ 340 extraits d'archives datés de 1956 à 2002, avec audio. L'Open API GraphQL exige un jeton ; je n'ai pas pu la tester.

### Cited Findings
- `https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume?p=1…116` : HTML statique d'environ 20 épisodes par page, en-tête « 2 277 épisodes ». La page 100 contient des émissions de 1994-1996 et la page 114 va du 19 mars 1959 au 20 mai 1956. **[vérifié]** — [page 100](https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume?p=100)
- Un crawl complet (pages 1-116, 2 225 URL d'épisodes uniques) donne, par année de diffusion affichée **[vérifié]** :
  - 1956-2002 : 1 à 15 entrées par an, environ 340 au total, aucune pour 1985. Ce sont des **extraits thématiques d'archives** (ex. « Louis Aragon… », Jeudi 4 décembre 1958, série « 1956-1981 : les entretiens du Masque », 30 min audio, critiques présents nommés dans le texte). — [exemple](https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/louis-aragon-4684213)
  - 2003-2012 : 52 à 62 entrées par an. Les slugs `livres-NNNNNNN`, `cinema-…` et `theatre-…` correspondent aux émissions complètes (par an : 12-17 livres, 20-23 cinéma, 6-9 théâtre) ; les autres entrées sont des extraits par œuvre ou des émissions spéciales (Prix des auditeurs, Avignon, Cannes, Brive).
  - 2013-2016 : 56 à 64 entrées par an, avec des slugs descriptifs (le thème doit être lu dans la page).
  - Pour 2003-2005, aucune durée n'est affichée : « Cet épisode n'est plus écoutable, les droits d'auteur ont expiré ». La durée (environ 55 min) apparaît à partir de 2006.
- Fiche type du 5 décembre 2004 « Livres » : « Les critiques : Jean-Louis Ezine (Le Nouvel Observateur), Patricia Martin (France-Inter), Michel Crépu (…), Arnaud Viviant (…). Les livres : "Le soleil des Scorta", Laurent Gaudé (Actes Sud), "Suite française", Irène Némirovsky (Denoël)… Les conseils… ». La page inclut un JSON-LD schema.org (`WebPage`, `name`, `description`). **[vérifié]** — [fiche](https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/livres-5737051)
- Fiche du 4 janvier 2009 « Livres » : critiques et livres « titre, auteur (éditeur) », avec en plus les coups de cœur de chaque critique. **[vérifié]** — [fiche](https://www.radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume/livres-6765643)
- Open API : `POST https://openapi.radiofrance.fr/v1/graphql` sans en-tête renvoie `{"message":"Unauthorized: Missing x-token"}` (HTTP 403). **[vérifié]** L'inscription se fait sur developers.radiofrance.fr — [data.gouv.fr, API Radio France](https://www.data.gouv.fr/dataservices/api-radio-france). L'API couvre la grille des programmes, les émissions et podcasts, et les « derniers épisodes avec liens d'écoute ». Elle n'est pas destinée aux applications d'agrégation de podcasts — [data.gouv.fr](https://www.data.gouv.fr/dataservices/api-radio-france). Sa taxonomie comprend « diffusions, brands, grid » — [mcp.so, radiofrance-podcast-explorer](https://mcp.so/servers/radiofrance-podcast-explorer-mcp).
- developers.radiofrance.fr n'a pas pu être récupéré par WebFetch. Les noms de requêtes (`diffusionsOfShowByUrl`, `grid`, `brand`, `show`) relèvent de la mémoire et ne sont pas vérifiés ici. **[supposé]**

### Inferences
- Pour 2003-2016, radiofrance.fr est la source primaire la plus riche et la plus simple à moissonner. Elle couvre date, thème, critiques et livres avec éditeur, en HTML et JSON-LD. Elle comble à elle seule le « trou 2009-2011 » et rend les familles Wayback B, C et D secondaires. Intérêt : **fort**.
- L'API GraphQL interroge probablement le même back-office (mêmes « diffusions »). On peut supposer qu'elle remonte aussi à 2003 et inclut les extraits historiques. **[supposé]** C'est à tester avec un x-token gratuit.
- Les extraits 1956-2002 n'attestent qu'un échantillon des émissions (environ 340 dates sur plus de 2 000). Ils sont précieux pour le **contenu** (invités, critiques, œuvres, audio) mais pas pour l'exhaustivité. Intérêt : **moyen**.

### Gaps
- Écart entre les 2 225 URL uniques extraites et les « 2 277 épisodes » annoncés (environ 50). Causes possibles : des pages hors de la plage 1-116, ou des épisodes listés uniquement dans l'onglet « Séries ».
- Je n'ai pas vérifié si les dates des extraits anciens sont toujours les dates de diffusion originales (une date « Samedi 6 décembre 1958 » apparaît à côté de jeudis, ce qui suggère un enregistrement plutôt qu'une diffusion).
- Je n'ai pas testé l'API, faute de jeton.

## 3. INA : ressources en ligne hors catalogue.ina.fr

### Takeaway
Hors catalogue.ina.fr, je n'ai trouvé qu'une notice isolée de reportage sur l'émission (mediaclip.ina.fr). Je n'ai pas pu vérifier le nombre total de notices sans facette dans catalogue.ina.fr.

### Cited Findings
- mediaclip.ina.fr (B2B, licences payantes) : notice I21349486, « Le Masque et la Plume : magazine culturel critique », 2 avril 1966, 2 min 02 s, collection « Histoire de la radio ». Il s'agit d'un reportage sur l'émission, pas d'une émission. La page n'affiche aucun autre extrait du Masque. **[vérifié]** — [mediaclip](https://mediaclip.ina.fr/en/i21349486-the-mask-and-the-pen-critical-cultural-magazine.html)
- Archives historiques de Radio France : elles sont consultables au SAEM, aux Archives nationales ou à l'Inathèque — [catalogue SAEM Radio France 2018 (PDF)](https://www.radiofrance.com/sites/default/files/2021-02/catalogue_ouvrages_archives_ecrites_musee_radio_france_2018.pdf).

### Inferences
- madelen (abonnement grand public) et ina.fr/ina-eclaire-actu proposent de l'éditorial sur des extraits, pas de liste d'émissions interrogeable par machine. Intérêt : **faible**. **[supposé]**
- L'Inathèque (Hyperbase) est consultable uniquement sur place (BnF et centres régionaux). Elle n'est pas utilisable à distance. **[supposé]**

### Gaps
- Total des notices de la collection « Le masque et la plume » dans catalogue.ina.fr sans facette Littérature : non vérifié (application JavaScript, non testée ici).
- data.ina.fr ou un éventuel SPARQL INA : aucune ressource trouvée ni testée.

## 4. Archives écrites Radio France, FranceArchives et Archives nationales

### Takeaway
Je n'ai trouvé aucun instrument de recherche en ligne consacré au Masque et la Plume. Les conducteurs et dossiers d'émission relèvent du SAEM de Radio France (versements aux Archives nationales), consultables sur demande.

### Cited Findings
- Le SAEM (Service des archives écrites et du Musée de Radio France) conserve les fonds des directions et des chaînes, avant leur versement aux Archives nationales, sous réserve des règles de communicabilité — [catalogue SAEM 2018](https://www.radiofrance.com/sites/default/files/2021-02/catalogue_ouvrages_archives_ecrites_musee_radio_france_2018.pdf).
- La recherche FranceArchives `q="masque et la plume"` n'a pas pu être lue : WebFetch a renvoyé un contenu vide et curl une page de 258 octets (front-end JavaScript). **[non vérifié]**
- data.bnf.fr expose une notice d'organisation « Le Masque et la Plume (Paris) » — [data.bnf.fr](https://data.bnf.fr/41108749/le_masque_et_la_plume__paris_/fr.pdf).

### Inferences
- D'éventuels conducteurs ORTF du Masque se trouveraient dans les versements Radio France / ORTF des Archives nationales (site de Fontainebleau puis Pierrefitte). Ces instruments ne listent pas les émissions individuellement en ligne. Intérêt pour une extraction automatique : **faible**. **[supposé]**

### Gaps
- Je n'ai pas interrogé la salle des inventaires virtuelle des Archives nationales, faute de temps et de budget d'appels.

## 5. Grilles de programmes ORTF/RTF publiées (Gallica, data.bnf)

### Takeaway
Non vérifié : les requêtes SRU Gallica n'ont pas abouti (l'un des appels a été bloqué par le contrôle de permissions de l'environnement).

### Cited Findings
- Aucun résultat obtenu.

### Inferences
- Les hebdomadaires de programmes radio numérisés sur Gallica (presse quotidienne « Programmes de la radio », Radio-Cinéma-Télévision / Télérama ancienne formule, si numérisés) permettraient, par OCR, d'attester les dates de diffusion 1955-2002. **[supposé]** Il faudrait le vérifier par l'API SRU Gallica (`https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=gallica all "masque et la plume"`).

### Gaps
- Le nombre de résultats Gallica et les titres de périodiques de programmes disponibles restent à déterminer.

## Tableau récapitulatif des sources

| Source | URL / motif | Période | Informations | Accès | Volume estimé | Intérêt |
|---|---|---|---|---|---|---|
| radiofrance.fr, page podcast paginée | `radiofrance.fr/franceinter/podcasts/le-masque-et-la-plume?p=1..116` puis fiches `/le-masque-et-la-plume/{slug}-{id}` | 2003-01-04 → aujourd'hui en continu ; extraits 1956-2002 | date, thème, critiques et journaux, livres avec éditeur, conseils ; audio dès 2006 ; JSON-LD | HTML public, sans authentification | 2 277 épisodes, dont environ 1 195 ≤ 2016 (environ 860 pour 2003-2016, environ 340 extraits 1956-2002) | **fort** [vérifié] |
| Open API Radio France | `POST openapi.radiofrance.fr/v1/graphql` (en-tête x-token) | supposé identique à radiofrance.fr | diffusions, brands, grid | jeton gratuit (developers.radiofrance.fr) | ? | moyen [non testé] |
| Wayback famille C (franceinter.fr v1) | `franceinter.fr/archives-diffusions/319/AAAA-MM`, `franceinter.fr/em/lemasqueetlaplume/{id}`, `reecouter-diffusions/319?page=N` | 2002-12 → 2012 (base de 455-478 fiches) | date, thème ; œuvres critiquées (2011) | Wayback, CDX | 30 listes mensuelles, 58 fiches, 6 pages réécoute | moyen [vérifié] |
| Wayback famille B | `radiofrance.fr/franceinter/em/lemasqueetlaplume/archives.php?annee=2002..2008`, `index.php?id=N` | 2002-2008 | date et thème par année ; fiches | Wayback | 7 listes annuelles, 72 fiches | moyen [vérifié] |
| Wayback famille D | `franceinter.fr/emission-le-masque-et-la-plume-*` | 2011-2016 | fiches émission | Wayback | 291 URL | moyen (redondant) [vérifié] |
| Wayback famille A | `radio-france.fr/chaines/france-inter01/emissions/masque/index.php?...affichage=fiche` | fin 2002-début 2003 | date, thème, fiche | Wayback | environ 23 URL | faible [vérifié] |
| mediaclip.ina.fr | `mediaclip.ina.fr/.../i21349486-...` | 1966 | reportage sur l'émission | public, licences payantes | 1 notice | faible [vérifié] |
| SAEM Radio France / Archives nationales | sur place ou inventaires | 1955- | conducteurs, dossiers | manuel | ? | faible pour l'automatisation [supposé] |
| Gallica, programmes radio | API SRU | 1955-… | grilles de diffusion (OCR) | API publique | ? | à évaluer [supposé] |
