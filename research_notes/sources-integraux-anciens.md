# Sources en ligne d'intégraux anciens hors catalogue INA et radiofrance.fr

Recherche pour #52 (carte #48). Constats du 2026-11-19, faits sur les données de `data/processed/` (784 émissions, 516 sans intégral) et par des requêtes directes : API CDX de la Wayback Machine, API de recherche et de métadonnées d'archive.org, API Dailymotion, pages YouTube. Le rapport `reports/Sources Masque et la Plume.md` et les notes `research_notes/Sources Masque et la Plume/` sont supposés connus. Ce qui y est déjà établi n'est pas refait ici.

Légende : **[vérifié]** = constaté par une requête ou en lisant la page ; **[supposé]** = déduit, non confirmé.

## Réponse courte

- **Hors Radio France et INA, aucune source en ligne ne fournit d'intégraux littéraires anciens en volume.** archive.org, Dailymotion, YouTube, les flux podcast archivés et les sites de France Inter des années 1999-2005 apportent au total **zéro à deux intégraux littéraires nouveaux**.
- **Le vrai gisement est déjà dans nos données.** **80 émissions de 2006 à 2011** ont un enregistrement Radio France de 48 à 57 minutes, classé `extrait` parce que son nom de fichier porte la lettre `E` (`2007F4007E0027`). Ce sont des intégraux. Exemple : le fichier du 5 août 2007 dure 50 min 41 s, et la diffusion notée par l'INA va de 20 h 08 à 20 h 58, soit 50 minutes. Corriger cette règle fait passer les émissions sans intégral de 516 à **436**. Les années 2006-2010 sont alors presque complètes.
- Ce qui reste (1955-2005, environ 430 émissions) ne se trouve qu'à l'INA (Madelen, Inathèque), à Radio France, ou chez des particuliers qui ont des enregistrements hors ligne.

## 0. Le gisement interne : 80 intégraux 2006-2011 classés « extrait »

### Constats
- `data/processed/enregistrements.csv` contient, pour 80 émissions sans intégral, un fichier de 48 à 57 minutes de type `extrait`, de source `radiofrance` (parfois aussi `wayback_podcast`) **[vérifié]**. Répartition : 2006 : 15, 2007 : 16, 2008 : 16, 2009 : 15, 2010 : 14, 2011 : 4.
- Exemples : `14007-05.08.2007-ITEMA_20081152-2007F4007E0027-27.m4a` (50:41), `14007-14.09.2008-ITEMA_20144334-2008F4007E0162-27.m4a` (55:16), `14007-17.01.2010-ITEMA_20212163-2010F4007E0002-27.m4a` (55:22) **[vérifié]**.
- La règle est dans `src/lmelp_pap/sources/audio_radiofrance.py` : `type="extrait" if m["lettre"] == "E"`. Son docstring dit que `E` désigne « un épisode d'une série d'archives (un extrait) ». Pour 2006-2011, `E` numérote en fait les émissions de l'année (`E0002`, `E0004`… une semaine sur deux, en alternance avec le cinéma ou le théâtre) **[vérifié sur les noms ; interprétation supposée]**.
- La règle de secours `_archives_entieres` (`src/lmelp_pap/liste.py`) ne s'applique pas : elle a besoin de la durée de diffusion INA, et la colonne `duree` d'`emissions.csv` est vide pour ces émissions **[vérifié]**. La notice INA en donne pourtant une : pour `RD_3189906.001` (5 août 2007), diffusion de 20:08 à 20:58, durée 00:50:00 ([catalogue INA](https://catalogue.ina.fr/doc/TV-RADIO/RD_3189906.001/le-masque-et-la-plume-du-05-aout-2007)) **[vérifié]**.

### Conséquence
Deux corrections possibles, qui ne dépendent d'aucune source nouvelle : récupérer la durée des notices INA `RD_*` pour que `_archives_entieres` joue, ou traiter un fichier `E` de plus de 40 minutes comme un intégral. On peut aussi faire les deux. Restent sans intégral en 2005-2011 : les 17 émissions de 2005 et environ 6 émissions isolées de 2006 à 2011.

## 1. Flux podcast France Inter 2005-2010 archivés (Wayback)

### Constats
- Le collecteur actuel (`wayback_podcast.py`) ne lit que `media.radiofrance-podcast.net/podcast09/14007-`. Avant 2009, le podcast avait une autre adresse : flux `radiofrance-podcast.net/podcast/rss_14007.xml`, fichiers `www.radiofrance-podcast.net/podcast/14007-JJ.MM.AAAA-ITEMA_N-0.mp3` (2007), puis `media.radiofrance-podcast.net/podcast/…` (2008-2009) **[vérifié]**.
- Ce flux ancien a **27 captures HTTP 200, du 2007-06-30 au 2009-03-09** ([CDX](http://web.archive.org/cdx/search/cdx?url=radiofrance-podcast.net/podcast/rss_14007.xml&fl=timestamp,statuscode,length)). Chaque capture ne contient qu'**un seul `<item>`**, la dernière émission (taille d'environ 1 Ko). Exemple : la capture du 2007-06-30 donne l'émission du 24.06.2007, ITEMA_20076184, durée 00:51:15 et la liste des critiques ([capture](http://web.archive.org/web/20070630163024id_/http://radiofrance-podcast.net/podcast/rss_14007.xml)) **[vérifié]**.
- **Aucun MP3 de l'ancien chemin n'est capturé.** `radiofrance-podcast.net/podcast/14007-` : 0 URL. `media.radiofrance-podcast.net/podcast/14007-` : 1 URL, un 404 de 2021. Le préfixe `radiofrance-podcast.net/podcast/` ne contient que 74 MP3, tous d'autres émissions **[vérifié]**. Sur le serveur actuel, ces anciennes URL répondent 404 **[vérifié]**.
- Sur `podcast09/14007-`, les dates 2005-2010 sont déjà toutes collectées. Pour les émissions hebdomadaires de 2009-2010, la Wayback n'a capturé que 4 dates **[vérifié]**.
- Aucune trace d'un podcast du Masque en 2005-2006 : la première capture du flux date de juin 2007 **[vérifié]**.

### Bilan
Période : juin 2007 à mars 2009. **Intégraux nouveaux : 0.** Apport : environ 25 couples date et ITEMA d'émissions hebdomadaires. Ils peuvent servir de références pour une demande à Radio France, mais ces dates sont déjà couvertes par le gisement de la section 0. Fiabilité des métadonnées : haute (flux officiel).

## 2. Sites France Inter 1999-2005 et RealAudio

### Constats
- Les pages du Masque sur `radio-france.fr` et `radiofrance.fr/chaines/france-inter01/emissions/masque/` (2002-2005 : 258 URL, uniquement du HTML et des images) et sur `franceinter.com/…/masque/` (2003 : 7 URL) n'ont **aucun lien audio** : pas de `.ram`, `.rm`, `.asx` ni `.mp3`. La fiche du 01-02-2004 (`index.php?date_demande=01-02-2004&emission=86&affichage=fiche`) ne propose pas d'écoute **[vérifié]**. Les rubriques sont : présentation, diffusion, archives (listes), enregistrements (dates de captation en public), contact.
- La page d'aide « écouter » de 2002 (`aide_outils/ecouter/`) ne décrit que le direct, en Real, QuickTime ou WMP. Le préfixe `radio-france.fr/chaines/france-inter01/` (20 000 premières URL, jusqu'à 2003) ne contient aucun fichier audio : seulement du HTML, des images et du Flash **[vérifié]**.
- Les requêtes CDX par domaine filtrées sur les extensions audio (`radiofrance.fr`, `franceinter.fr`) échouent en 504. Elles n'ont rien renvoyé pour `radio-france.fr` et `franceinter.com` **[vérifié]**.

### Bilan
Période : 1999-2005. **Intégraux nouveaux : 0.** Le Masque n'était pas proposé à la réécoute avant le podcast. Un flux RealAudio, de toute façon diffusé en RTSP, ne pourrait pas être archivé par la Wayback **[supposé]**.

## 3. archive.org (collections audio)

### Constats
- Les requêtes `"masque et la plume"` (13 items), `masque AND plume` (27), `subject:"masque et la plume"` (6), `bory AND charensol`, `"jean-louis bory"` et `"pierre bouteiller"` (0) ne donnent pas plus que le rapport antérieur ([API](https://archive.org/advancedsearch.php?q=%22masque+et+la+plume%22&fl[]=identifier&rows=100&output=json)) **[vérifié]**.
- Seuls trois items audio sont des émissions entières, et aucun n'est un intégral littéraire ancien et daté **[vérifié par l'API metadata]** :
  - `LeMasqueEtLaPlume01` : `Thtre01.mp3`, 54 min 48 s, description « THEATRE », sans date ([item](https://archive.org/details/LeMasqueEtLaPlume01)). C'est probablement un intégral, mais de théâtre, à dater à l'écoute **[supposé]**.
  - `2026-03-29` : une émission de 2026, 46 min ([item](https://archive.org/details/2026-03-29)).
  - `masque-et-la-plume-chinois-encore-un-effort-..` : extrait cinéma de 1977.
- Aucune collection de type « France Inter, années 1970-2000 » ou dépôt de cassettes : `mediatype:audio AND "france inter"` sur ces décennies ne donne que 3 items hors sujet **[vérifié]**.

### Bilan
**Intégraux littéraires nouveaux : 0** (au mieux un intégral théâtre non daté). Fiabilité faible : dépôts anonymes, sans date.

## 4. YouTube et Dailymotion

### Constats
- **Dailymotion** ([API](https://api.dailymotion.com/videos?search=masque+et+la+plume&fields=id,title,duration,created_time,owner.screenname&limit=100)) : une seule vidéo longue, `xfvwal`, publiée par France Inter (58 min). C'est la captation du 25 novembre 2010 au studio 105, soit l'émission du 28 novembre 2010, déjà couverte par la section 0 ([vidéo](https://www.dailymotion.com/video/xfvwal)). Le reste : teasers, extraits INA, homonymes **[vérifié]**.
- **YouTube** (pages de résultats, oEmbed, flux de chaîne) :
  - La chaîne INA publie des extraits de 3 à 21 minutes, tous cinéma (« Archive INA ») **[vérifié]**.
  - Un particulier (`@dd329`) a mis en ligne « Le masque et la plume du 1988 12 25 » (52 min 55 s), une émission de cinéma, et un extrait Grimault de 1980. Sa chaîne porte sur le cinéma (Daney, Rozier), pas sur les livres ([vidéo](https://www.youtube.com/watch?v=O4xzdJJPRfw), [flux](https://www.youtube.com/feeds/videos.xml?channel_id=UCLBzFriVFAM8qDhP4on_5Ag)) **[vérifié]**.
  - « Le Livre sur la Place » (Nancy) publie des captations vidéo d'émissions littéraires de 2018 et 2021, hors période **[vérifié]**.
  - La chaîne « mieuhen PUB RADIO RÉTRO » a une compilation de 4 minutes sur 1955-1965 **[vérifié]**.
- Je n'ai pas utilisé l'API YouTube Data (pas de clé). La recherche par pages ne montre que les premiers résultats.

### Bilan
**Intégraux littéraires nouveaux : 0 trouvé.** Des intégraux cinéma de particuliers existent : la piste « passionnés » est réelle, mais orientée cinéma. Faisabilité : téléchargement possible (yt-dlp), usage privé. Fiabilité de la date : titre déclaratif, à recouper avec la liste.

## 5. Sites ou forums de passionnés, rediffusions sur d'autres antennes

### Constats
- Les recherches web n'ont trouvé aucun site, forum ni collection de cassettes consacré au Masque **[vérifié : résultat négatif]**.
- Aucune trace de rediffusion du Masque sur France Culture (« Les Nuits de France Culture »), RTBF, RSR, Radio-Canada ou RFI **[vérifié : résultat négatif]**. Les archives republiées par Radio France sont dans le podcast 14007 et dans un second podcast, 26831, déjà collectés par la source `radiofrance` **[vérifié dans enregistrements.csv]**.
- Les pages « archives » du Festival d'Avignon (enregistrements publics de juillet) n'ont ni audio ni vidéo ([exemple 2016](https://festival-avignon.com/en/edition-2016/programme/le-masque-et-la-plume-9486)) **[vérifié]**.

### Bilan
**Intégraux nouveaux : 0 en ligne.** Les particuliers qui ont enregistré l'émission (cassettes des années 1970-2000) ne se trouvent pas par le web. Il faudrait un appel ciblé (forums radio, réseaux sociaux, critiques et auditeurs). C'est le « rapatriement manuel » encore non spécifié dans #48.

## Synthèse

| Piste | Période | Intégraux littéraires nouveaux | Faisabilité | Fiabilité |
|---|---|---|---|---|
| Fichiers `E` de 48-57 min déjà collectés (radiofrance.fr) | 2006-2011 | **80** | immédiate : corriger la règle de type ou récupérer la durée INA | haute (fichiers officiels, durée conforme à l'INA) |
| Ancien flux podcast `podcast/rss_14007.xml` (Wayback) | 2007-06 → 2009-03 | 0 (métadonnées seulement : ~25 date + ITEMA) | facile, mais sans audio | haute |
| Sites France Inter 1999-2005, RealAudio | 1999-2005 | 0 | aucune réécoute n'était proposée | — |
| archive.org | sans date, 1977, 2026 | 0 (1 intégral théâtre non daté) | facile (API) | faible |
| Dailymotion | 2010 | 0 (1 vidéo, déjà couverte) | facile | haute |
| YouTube (INA, particuliers) | 1965-1988 (cinéma) | 0 trouvé | yt-dlp, usage privé | moyenne (dates déclaratives) |
| Passionnés, forums, autres antennes | — | 0 en ligne | appel manuel | inconnue |

## Lacunes
- Je n'ai pas écouté les fichiers `E` de 2006-2011. Leur intégralité se déduit de leur durée, comparée à une notice INA. Il faudrait vérifier quelques autres notices INA (2009-2011, 55-57 min) avant de changer la règle.
- Pas de clé pour l'API YouTube Data, Listen Notes ni PodcastIndex : la recherche YouTube ne voit que les premiers résultats.
- Les requêtes CDX par domaine entier (`radiofrance.fr`, `franceinter.fr`) échouent en 504. Un fichier audio isolé, hors des chemins du Masque, a pu échapper.
