# Archives audio et communautés d'amateurs : « Le Masque et la Plume » (1955-2016)

Légende : **[vérifié]** = constaté directement (requête API exécutée le 2026-11-08 ou page lue) ; **[supposé]** = déduit ou non confirmé.

## 1. archive.org (Internet Archive) : nombre d'items, années, audio

### Takeaway
L'API de recherche d'archive.org ne renvoie qu'une **quinzaine d'items** pour « masque et la plume », dont 5 audio seulement, presque tous des dépôts isolés : intérêt **faible** pour un inventaire. En revanche, la **Wayback Machine** (CDX API) a capturé **2 653 URL de fichiers MP3/M4A** du podcast officiel (`media.radiofrance-podcast.net/podcast09/14007-*`). Leurs noms donnent **361 dates distinctes ≤ 2016**, de 1956 à 2016. C'est la source « hors institution » la plus riche et la plus exploitable automatiquement : intérêt **fort**.

### Cited Findings
- Requête `q="masque et la plume"` : **13 résultats** ; `q="masque & la plume"` : 1 ; `q=title:(masque plume)` : 6. Union : **14 items**, soit 6 `movies`, 5 `audio` et 3 `texts` **[vérifié]** — [API advancedsearch](https://archive.org/advancedsearch.php?q=%22masque+et+la+plume%22&fl[]=identifier,title,date&rows=500&output=json)
- `q=masque plume AND mediatype:audio` : 7 résultats, dont 2 hors sujet (Verdi, conférences) **[vérifié]** — [API advancedsearch](https://archive.org/advancedsearch.php?q=masque+plume+AND+mediatype%3Aaudio&fl[]=identifier,title,date&rows=200&output=json)
- Items audio pertinents **[vérifié]** :
  - `LeMasqueEtLaPlume01` : 1 fichier `Thtre01.mp3`, description « THEATRE », sans date, déposé par un particulier en 2012 — [archive.org](https://archive.org/details/LeMasqueEtLaPlume01)
  - `masque-et-la-plume-chinois-encore-un-effort-..` : extrait de 1977 (Charensol sur le film de René Viénet), déposé en 2020 — [archive.org](https://archive.org/details/masque-et-la-plume-chinois-encore-un-effort-..)
  - `EPISODE2.LeMasqueEtLaPlumeLezardeRenaudotL1958` : épisode d'un podcast tiers (« Paroles d'Édouard Glissant ») autour de la critique de *La Lézarde* (Renaudot 1958) — [archive.org](https://archive.org/details/EPISODE2.LeMasqueEtLaPlumeLezardeRenaudotL1958)
  - `2026-03-29` : « An archive of Le masque et la plume on France Inter », un seul fichier `.m4a` (68 Mo) d'une émission récente, déposé le 2026-03-29 — [archive.org](https://archive.org/details/2026-03-29)
- Items vidéo : copies « mirrortube » de vidéos YouTube, dont `youtube-MLv_RVNYeeE`, « Georges Charensol et Jean-Louis Bory (France Inter - Le masque et la plume) | Archive INA », datée 2015-10-16 **[vérifié]** — [archive.org](https://archive.org/details/youtube-MLv_RVNYeeE)
- Items texte : le livre *Le Masque et la Plume* (Garcia/Garcin, 2005) et *Nos dimanches soirs* (2017), en prêt numérique contrôlé **[vérifié]** — [archive.org](https://archive.org/details/lemasqueetlaplum0000garc)
- **Wayback Machine, flux RSS officiel** `radiofrance-podcast.net/podcast09/rss_14007.xml` : 153 captures HTTP 200 entre 2009 et 2026, réparties ainsi : 2009 : 1, 2010 : 1, 2011 : 6, 2012 : 3, 2013 : 2, 2014 : 2, 2015 : 6, 2016 : 2, puis davantage après 2019 **[vérifié]** — [CDX API](http://web.archive.org/cdx/search/cdx?url=radiofrance-podcast.net/podcast09/rss_14007.xml)
- La capture du 2011-08-18 contient des `<item>` avec `pubDate` (par exemple « Sun, 14 Aug 2011 20:10:00 ») et des enclosures MP3 nommés `14007-14.08.2011-ITEMA_20301297-0.mp3`. Le nom contient la date de l'émission et l'identifiant ITEMA de Radio France **[vérifié]** — [capture Wayback 2011](http://web.archive.org/web/20110818112528/http://radiofrance-podcast.net/podcast09/rss_14007.xml)
- **Wayback Machine, fichiers MP3/M4A** (préfixe `media.radiofrance-podcast.net/podcast09/14007-`) : 2 800 URL distinctes, dont 2 653 en HTTP 200, soit **791 dates distinctes au total** **[vérifié]** — [CDX API](http://web.archive.org/cdx/search/cdx?url=media.radiofrance-podcast.net/podcast09/14007-&matchType=prefix&fl=original,statuscode&collapse=urlkey)
  - **185 dates de 1956 à 2004**. Les noms portent un code d'archive, par exemple `14007-01.01.1967-ITEMA_23820437-1967F4007E0001-22.mp3` ou `…1998F4007E0004…`. Ce sont des émissions anciennes que Radio France a republiées en podcast **[vérifié pour le nommage]**
  - **176 dates de 2005 à 2016**, réparties ainsi : 2005 : 6, 2006 : 8, 2007 : 22, 2008 : 5, 2009 : 4, 2010 : 5, 2011 : 25, 2012 : 9, 2013 : 28, 2014 : 15, 2015 : 20, 2016 : 29 **[vérifié]**

### Inferences
- Les noms de fichiers du podcast encodent la **date de diffusion** (JJ.MM.AAAA) et l'**identifiant ITEMA** (référence documentaire interne de Radio France). On en tire une liste datée sans saisie manuelle, recoupable avec le catalogue INA et Radio France **[supposé : ITEMA = identifiant de la base documentaire Radio France]**.
- Pour les URL d'archives (avant 2005), la date du nom de fichier semble être la date de la diffusion d'origine (1956-2004), et non celle de la republication **[supposé : à confirmer sur quelques fichiers, en vérifiant l'audio ou la page franceinter.fr associée]**.
- Les MP3 capturés sont probablement téléchargeables via `http://web.archive.org/web/<timestamp>id_/<url>` **[supposé : non testé en téléchargement]**.
- Les quelques items audio d'archive.org sont des dépôts isolés de particuliers : aucune « collection » organisée n'y existe.

### Gaps
- Je n'ai pas vérifié que la date du nom de fichier correspond toujours à la date de diffusion d'origine pour les archives republiées.
- Je n'ai pas téléchargé ni contrôlé l'intégrité des MP3 capturés (certains peuvent être tronqués ou n'être que des redirections).
- Les captures du flux RSS sont rares entre 2009 et 2016 (une vingtaine en tout). Un flux ne garde qu'environ 50 items, donc les métadonnées titre et description de la période 2005-2016 restent très lacunaires dans la Wayback Machine.

## 2. Agrégateurs de podcasts (2005-2016)

### Takeaway
Le flux officiel actuel ne garde que **52 items**, les plus récents, et les agrégateurs grand public (Deezer, Rephonic, Apple) n'exposent que des épisodes récents. **Aucun agrégateur consulté ne conserve d'épisodes de 2005 à 2016** de façon vérifiable. Le seul « historique de flux » exploitable est la Wayback Machine (section 1). Intérêt : **faible** pour les agrégateurs, **fort** pour la Wayback Machine.

### Cited Findings
- Le flux `https://radiofrance-podcast.net/podcast09/rss_14007.xml` contient **52 `<item>`** ; le plus récent est daté du 6 septembre 2026 **[vérifié]** — [flux RSS Radio France](https://radiofrance-podcast.net/podcast09/rss_14007.xml)
- Rephonic indique **82 épisodes publiés**, ce qui correspond au catalogue récent et non à l'historique **[vérifié via extrait de recherche]** — [Rephonic](https://rephonic.com/podcasts/le-masque-et-la-plume)
- Deezer liste surtout des épisodes récents **[supposé, d'après le résumé de recherche]** — [Deezer](https://www.deezer.com/sl/show/48457)
- IMDb Pro référence une série podcast « Le masque et la plume » à partir de 2006 **[supposé, page non lisible]** — [IMDb Pro](https://pro.imdb.com/title/tt28118056/)
- Podcast Addict renvoie HTTP 403 au robot : profondeur d'historique non vérifiable **[vérifié : accès refusé]** — [Podcast Addict](https://podcastaddict.com/podcast/le-masque-et-la-plume/120593)
- Le podcast officiel existe au moins depuis 2009 : première capture Wayback du flux le 2009-04-04 **[vérifié]** — [CDX API](http://web.archive.org/cdx/search/cdx?url=radiofrance-podcast.net/podcast09/rss_14007.xml)

### Inferences
- Les agrégateurs (Podcast Addict, Player.fm, Listen Notes) conservent parfois les épisodes déjà vus dans un flux. Leurs enclosures pointent cependant vers les mêmes MP3 Radio France, que la Wayback Machine capture déjà de manière plus systématique **[supposé]**.
- PodcastIndex.org (API avec clé gratuite) pourrait renvoyer des épisodes historiques déjà vus, mais son indexation date de 2020 : il est peu probable qu'il couvre 2005-2016 **[supposé, non testé faute de clé API]**.

### Gaps
- Listen Notes, Player.fm et PodcastIndex n'ont pas été interrogés (clé API nécessaire, ou robots bloqués).
- Je n'ai trouvé aucun miroir (Podbean, etc.) du flux France Inter.

## 3. Sites de fans, blogs, forums, listes privées

### Takeaway
Aucun site de fans, forum de collectionneurs, blog ou page personnelle ne publie une liste exhaustive ou datée des émissions. Les rares traces non institutionnelles sont des **dépôts isolés** sur archive.org et des livres (Garcia/Garcin 2005, *Instants critiques* 2012). Intérêt : **faible**.

### Cited Findings
- Plusieurs recherches web en français (« liste des émissions », « forum archives radio enregistrements collectionneur ») ne renvoient que des articles de presse, des notices de bibliothèque et des fiches INA Mediaclip, sans aucun site communautaire **[vérifié : résultat négatif]** — par exemple [ActuaLitté, 70 ans](https://actualitte.com/article/127997/radio/le-masque-et-la-plume-fete-ses-70-ans), [ladn.eu, 60 ans](https://www.ladn.eu/reflexion/vu-dans-la-revue/le-masque-et-la-plume-60-ans-de-succes)
- Un lecteur sur Goodreads déplore que le site de l'émission ne donne pas accès à toutes les archives **[vérifié via extrait]** — [Goodreads](https://www.goodreads.com/book/show/27406064)
- *Instants critiques* (Solitaires intempestifs, 2012) transcrit des échanges Bory/Charensol tirés de l'émission. C'est une source imprimée, sans audio **[supposé, d'après les résultats de recherche]** — [Offi](https://www.offi.fr/theatre/theatre-71-3268/instants-critiques-42518.html)
- IMDb contient au moins une fiche d'épisode, « Episode dated 11 January 1976 » (tt10720898), avec Bory, Charensol, Bastide et Jacob. IMDb se nourrit de contributions d'utilisateurs **[supposé : page en 403, constaté seulement via les résultats de recherche]** — [IMDb Pro](https://pro.imdb.com/title/tt10720898/cast)

### Inferences
- Les fiches d'épisodes IMDb sont une petite source communautaire datée, mais l'accès automatisé est bloqué (403) et le volume paraît marginal **[supposé]**.

### Gaps
- Je n'ai pas fouillé les forums francophones de passionnés de radio (par exemple les forums d'échange de vieilles émissions, Reddit r/france, Doctissimo) : les moteurs n'en remontent aucun. L'absence de résultat ne prouve pas l'absence de listes privées.
- Le nombre total de fiches d'épisodes IMDb n'a pas pu être compté.

## 4. YouTube (chaînes INA et autres)

### Takeaway
Des **extraits** de l'émission circulent sur YouTube, notamment sur la chaîne de l'INA (Bory/Charensol). Une copie en existe sur archive.org. Je n'ai trouvé **aucune chaîne qui mette en ligne des émissions intégrales**. L'API YouTube Data v3 permet de lister ces vidéos, mais elle date la **mise en ligne**, pas la diffusion. Intérêt : **faible à moyen**, pour l'illustration et non pour l'inventaire.

### Cited Findings
- La vidéo « Georges Charensol et Jean-Louis Bory (France Inter - Le masque et la plume) | Archive INA » (YouTube MLv_RVNYeeE, 2015-10-16) est copiée sur archive.org **[vérifié]** — [archive.org](https://archive.org/details/youtube-MLv_RVNYeeE)
- Les recherches web n'ont trouvé aucune émission intégrale sur YouTube ; elles renvoient vers INA Mediaclip (reportages sur l'émission, débat sur son arrêt à la télévision) **[vérifié : résultat négatif]** — [INA Mediaclip](https://mediaclip.ina.fr/en/i21349486-the-mask-and-the-pen-critical-cultural-magazine.html), [INA Mediaclip, débat](https://mediaclip.ina.fr/en/i23348813-debate-on-stopping-the-mask-and-the-pen-on-television-part-2.html)

### Inferences
- L'API YouTube Data v3 (`search.list`, clé gratuite, quota de 10 000 unités par jour, 100 unités par recherche) renvoie `publishedAt`, la date de mise en ligne. Une éventuelle date de diffusion n'apparaît que dans le titre ou la description, à extraire par expression régulière **[supposé, d'après la connaissance de l'API ; non testé ici]**.
- Le contenu est surtout constitué d'extraits INA, déjà couverts par les sources institutionnelles **[supposé]**.

### Gaps
- Je n'ai pas exécuté de requête sur l'API YouTube (pas de clé) : le nombre de vidéos reste inconnu.

## 5. Jeux de données ouverts (data.gouv.fr, Kaggle, GitHub, Wikidata, Hugging Face)

### Takeaway
Aucun jeu de données ouvert ne liste les émissions de 1955 à 2016. Wikidata n'a qu'un item pour l'émission (Q3224370), sans items d'épisodes. Sur GitHub, les seuls dépôts trouvés sont ceux de ce projet (castorfou/lmelp, back-office-lmelp), qui portent sur les épisodes récents. Intérêt : **faible**.

### Cited Findings
- Wikidata : item **Q3224370**. Les items qui y renvoient utilisent P1344 (« participant à », 6 items), P3919 (4), P1855 (1) et P2650 (1). Aucun item d'épisode ne s'y rattache par P179 ou P361 **[vérifié]** — [Wikidata Q3224370](https://www.wikidata.org/wiki/Q3224370), [SPARQL](https://query.wikidata.org/)
- La recherche de dépôts GitHub `"masque et la plume"` renvoie **2 résultats**, `castorfou/lmelp` (transcriptions) et `castorfou/back-office-lmelp` ; `masque plume` renvoie les deux mêmes **[vérifié]** — [GitHub API](https://api.github.com/search/repositories?q=%22masque+et+la+plume%22)

### Inferences
- data.gouv.fr et Kaggle n'ont pas été interrogés directement. Aucune trace n'en est ressortie dans les recherches web : un jeu de données existant y est peu probable **[supposé]**.

### Gaps
- Je n'ai pas lancé de recherche dédiée sur data.gouv.fr, Kaggle ni Hugging Face Datasets.

## Synthèse : tableau des sources

| Source | URL | Période | Info | Accès | Volume estimé | Intérêt |
|---|---|---|---|---|---|---|
| Wayback Machine, MP3 du podcast officiel | `web.archive.org/cdx/search/cdx?url=media.radiofrance-podcast.net/podcast09/14007-&matchType=prefix` | 1956-2016 (et après) | date + ITEMA dans le nom de fichier ; audio | CDX API, sans clé | 361 dates ≤ 2016 (185 avant 2005, 176 de 2005 à 2016) [vérifié] | **fort** |
| Wayback Machine, flux RSS 14007 | `web.archive.org/cdx/search/cdx?url=radiofrance-podcast.net/podcast09/rss_14007.xml` | 2009-2016 (23 captures) | titre, pubDate, description, enclosure | CDX + `id_` | quelques centaines d'items avec chevauchements [supposé] | **moyen** |
| archive.org, items | `archive.org/advancedsearch.php?q="masque et la plume"` | 1958, 1977, sans date | dépôts isolés de particuliers | API sans clé | 14 items, dont 5 audio [vérifié] | faible |
| Flux RSS officiel actuel | `radiofrance-podcast.net/podcast09/rss_14007.xml` | récent seulement | 52 items | RSS | 0 avant 2017 [vérifié] | faible |
| Agrégateurs (Rephonic, Deezer, Podcast Addict) | voir section 2 | récent | épisodes récents | web, souvent 403 | non mesurable | faible |
| YouTube (INA et autres) | YouTube Data API v3 | extraits | date de mise en ligne seulement | clé API | inconnu, quelques extraits [supposé] | faible à moyen |
| IMDb, fiches d'épisodes | `imdb.com/title/tt10720898` | ex. 1976 | participants | 403 pour les robots | marginal [supposé] | faible |
| Wikidata, GitHub | Q3224370, castorfou/* | aucune liste 1955-2016 | — | API | 0 | faible |

**Droits** : les enregistrements restent la propriété de Radio France, et les archives antérieures à 1975 sont gérées par l'INA. Les copies sur archive.org et dans la Wayback Machine ne sont pas une licence. Exploiter les **métadonnées** (dates, identifiants ITEMA) pour un inventaire pose peu de problème. Republier ou rediffuser l'**audio** serait une contrefaçon, sauf accord ou exception (usage privé, recherche). Les dépôts de particuliers sur archive.org sont probablement non autorisés **[supposé]**.
