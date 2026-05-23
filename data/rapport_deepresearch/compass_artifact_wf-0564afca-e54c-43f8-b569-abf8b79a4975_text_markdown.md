# Rapport de sourcing : « Le Masque et la Plume » — émissions LITTÉRATURE (1955-2016)

## TL;DR
- **Aucune source unique** ne couvre 1955-2016 ; la stratégie viable est **hybride** : scraping du catalogue INA (`catalogue.ina.fr`) pour les métadonnées (date, durée, thématique, critiques, œuvres) et scraping de `franceinter.fr/emissions/le-masque-et-la-plume/archives-…` pour les liens audio, complété par l'Inathèque pour le pré-2006.
- **Aucune API publique INA**, pas d'OAI-PMH, pas de dataset téléchargeable ; le seul levier programmatique est le « partage de requête par URL » du catalogue avec pagination HTML.
- Pour la période **2006-2016**, ~520 émissions sont indexées sur franceinter.fr avec page dédiée et lecteur audio ; pour **1955-2005**, les métadonnées sont récupérables au catalogue INA mais les audios complets ne sont consultables **qu'à l'Inathèque** (sur place, gratuit pour chercheurs accrédités) ou ponctuellement via des extraits édités sur ina.fr et YouTube/INA.

## Key Findings

### 1. INA — la source de métadonnées la plus complète, mais sans API
- **Catalogue INA** : `https://catalogue.ina.fr` (interface publique) et `https://inatheque.ina.fr` (équivalent professionnel). Chaque notice radio comporte les champs **date de diffusion (JJ/MM/AAAA), heure, durée, thématique (Littérature ; Théâtre ; Cinéma ; Opéra), genre, générique (producteur/animateur), descripteurs, chapeau, résumé documentaire**.
- Exemple de notice publique vérifiée : `https://catalogue.ina.fr/doc/TV-RADIO/RD_1745311.001/le-masque-et-la-plume` — « collection d'émissions simples » couvrant l'année 1995, France Inter, 20:07-21:00, 53 min, thématique « Littérature ; Théâtre ; Cinéma », producteur/présentateur Jérôme Garcin, réalisatrice Monique Alligier.
- La plus ancienne émission conservée est le **n°3 du 22 janvier 1956** (le n°1 du 13 novembre 1955 n'a pas été enregistré).
- **Régime documentaire** : avant le dépôt légal radio (1er janvier 1995), des notices « collection » regroupent souvent toute une année ; depuis 1995, **notices unitaires systématiques** pour chaque diffusion (~52/an × 22 ans 1995-2016 ≈ **1 100 notices unitaires** fiables).
- **Pas d'API publique** : `apipartner.ina.fr` existe (Swagger/GraphiQL, JSON-LD/MRSS/XML) mais réservée aux partenaires commerciaux. `data.ina.fr` (lancé le 2 octobre 2024 — « véritable mine d'or numérique ouvrant les portes de 27 millions d'heures d'archives audiovisuelles françaises captées à partir de 184 chaînes ») ne propose que des dashboards de datavisualisation sur la période du 1er janvier 2019 au 30 juin 2024 (5,5 ans d'historique, 20 chaînes TV et radio, 700 000 heures traitées), sans export brut.
- **Audio numérisé** : intégralité consultable **sur place uniquement** dans le réseau Inathèque (7 lieux experts et 50 lieux partenaires — bibliothèques universitaires, médiathèques, cinémathèques, archives départementales — dont BnF Paris site François-Mitterrand, Bry-sur-Marne, BU Bordeaux Mériadeck, BU Grenoble Alpes). **Aucune copie autorisée**. Sur ina.fr (gratuit, public), seuls des **extraits édités** (2-10 min) sont publiés, type `https://www.ina.fr/ina-eclaire-actu/audio/p{ID}/...`. L'offre SVOD `madelen.ina.fr` (3,99 € TTC/mois sans engagement, ou 39,99 €/an, avec 7 jours gratuits) propose des sélections, mais le « Masque » n'y est pas systématiquement présent.

### 2. Radio France / France Inter — la meilleure source de liens audio (2006→)
- URL canonique : `https://www.franceinter.fr/emissions/le-masque-et-la-plume`. Le flux RSS du podcast : `https://radiofrance-podcast.net/podcast09/rss_14007.xml` (mais ne contient que ~50 derniers épisodes).
- **Pages d'archives par saison** scrappables : `https://www.franceinter.fr/emissions/le-masque-et-la-plume/archives-01-09-{AAAA}-25-06-{AAAA+1}`. La saison la plus ancienne accessible est **2006-2007**.
- Pattern d'URL d'épisode unitaire : `…/le-masque-et-la-plume-12-septembre-2010` (date en français). Chaque page liste les critiques présents (avec leur média de rattachement), les œuvres critiquées (titre + auteur/réalisateur + éditeur/maison), et parfois un lecteur audio (rétention variable selon les droits).
- **Sitemap bloqué** (`https://www.franceinter.fr/sitemap.xml` retourne un 403) : les pages saisons sont l'équivalent fonctionnel.

### 3. Wikipédia — bonne base humaine pour les animateurs et critiques
- `https://fr.wikipedia.org/wiki/Le_Masque_et_la_Plume` : historique détaillé, **liste complète des animateurs** (Polac+Bastide 1955-70 ; Bastide seul 1970-81 ; Bouteiller 1982-89 ; Garcin 1989-2023 ; Manzoni depuis janvier 2024) et **~70 critiques** classés par section (Cinéma / Littérature / Théâtre / Variétés), avec dates de participation et organe de presse.
- Catégorie `Collaborateur du Masque et la Plume` : 73 pages biographiques.
- Pas de liste d'épisodes. La page de discussion mentionne explicitement (2009) qu'aucune liste exhaustive d'œuvres avec notes n'existe.

### 4. Internet Archive — quasi rien d'utile
- Recherche `archive.org` : un upload `LeMasqueEtLaPlume01` (Pumuki42, 2012) ; le livre Garcin/Garcia (Les Arènes/INA/France Inter, 2005) en numérisation contrôlée.
- Wayback Machine : utile pour ressusciter d'anciennes pages `radiofrance.fr/franceinter/em/lemasqueetlaplume/archives.php` (URL aujourd'hui morte) pour la période **avant 2006**, à explorer manuellement.

### 5. Sources tierces — exploitables au cas par cas
- **YouTube** :
  - Playlist INA Culture *Les critiques cultes du Masque et la Plume* — `https://www.youtube.com/playlist?list=PLDBKGEFONgtTDuJtMtC7IDGjKJfqy4h8X`
  - Playlist INA *Les critiques du Masque et la Plume* — `https://www.youtube.com/playlist?list=PLTlNdNwB88ltmIULr-XmakHJOjNKZu2j2`
  - Playlist *Le masque et la plume — Années 80s (Archives)* — `PLT5hB4lLylBzQDmsycEQXpla0XNU666hT`
  - Largement orientées cinéma (~70-80 % cinéma observé, 15-20 % littérature, reste théâtre). Décompte exact via YouTube Data API v3 (`playlistItems.list`).
- **Babelio** : liste « Le Masque et La Plume (choix) » (~31 livres) + « Les enthousiasmes du Masque et la Plume 2011-2015 » (~45 livres) avec date d'émission ; format narratif, scraping HTML possible.
- **SensCritique** : liste « Le masque et la plume littérature » (197 livres, dernière maj 24 août 2023) avec date de sortie des œuvres ; même logique.
- **Mémoires universitaires** : Victoire Le Sager, *Le masque et la plume : un rituel radiophonique*, Université Panthéon-Assas, IFP, 2019 (`https://assasrecherche.u-paris2.fr/ori-oai-search/notice/view/univ-pantheon-assas-ori-13061`). Marina-Oltea Paunescu, *Le Débat en question(s). Une analyse du débat culturel « Le masque et la plume »*, L'Harmattan, ISBN 978-2-296-01565-4. Guy Robert, « Une émission quinquagénaire : Le Masque et la Plume », *Cahiers d'histoire de la radiodiffusion*, n° 89.
- **Livre de référence** : Jérôme Garcin & Daniel Garcia, *Le Masque et la Plume*, Les Arènes/INA/France Inter, 2005, 543 p. — Garcia s'est plongé dans les archives des « deux mille émissions » du Masque ; un appareil annexe et chronologique précieux pour 1955-2005.

### 6. Gallica / presse — utile uniquement pour 1955-1990
- Aucune liste d'épisodes ne ressort des recherches directes Gallica, mais les programmes radio des quotidiens (*Le Monde*, *Le Figaro*, *L'Humanité*, *Télérama*) publiés à l'époque sont indexés dans Gallica/RetroNews et permettent de **reconstruire les dates de diffusion** et parfois les sujets/invités annoncés. Travail laborieux mais c'est la seule voie pour l'audio jamais numérisé.

## Détails — classement des sources par qualité/exploitabilité

| Rang | Source | Période couverte | Type de données | Densité | Structure | Scrapable ? | Audio téléchargeable ? |
|---|---|---|---|---|---|---|---|
| 1 | catalogue.ina.fr (HTML) | 1956-2016 (lacunes années 50-60) | date, durée, thématique, animateur, descripteurs, résumé | Très haute (DL 1995→) | Notice tabulaire | Oui via partage de requête par URL + pagination HTML | Non (Inathèque sur place uniquement) |
| 2 | franceinter.fr/emissions/le-masque-et-la-plume/archives-… | 2006-07 à 2015-16 | date, titre, critiques, œuvres, parfois audio embed | Haute pour 2006+ | Liste HTML par saison | Oui | Variable (extraits audio sur la page, parfois retirés) |
| 3 | fr.wikipedia.org/wiki/Le_Masque_et_la_Plume | 1955-2016 (méta) | animateurs, critiques, organes de presse, dates | Moyenne | Listes structurées | Oui (table HTML) | Non |
| 4 | Livre Garcin/Garcia 2005 (Les Arènes/INA) | 1955-2005 | citations, anecdotes, chronologie partielle | Haute mais qualitative | Narratif | Non (livre imprimé, numérisation contrôlée sur archive.org) | 2 CD inclus (extraits) |
| 5 | Playlists YouTube INA Culture | années 60-90 | extraits édités avec date et thématique | Faible (sélection) | Vidéos isolées | Oui via YouTube Data API v3 | Oui (extraits seulement) |
| 6 | ina.fr/ina-eclaire-actu/audio/p{ID}/… | 1956-2016 | extraits édités avec date, durée, contexte | Faible (sélection éditoriale) | Pages article | Robots.txt bloqué pour fetcher | Streaming oui ; téléchargement non |
| 7 | Babelio / SensCritique listes auditeurs | 2011-2023 | titre + auteur + date d'émission | Moyenne (subjective) | Liste | Oui | Non |
| 8 | Wayback Machine (radiofrance.fr/franceinter/em/lemasqueetlaplume/archives.php) | ~2000-2006 | listes anciennes du site France Inter | Faible (snapshots irréguliers) | HTML legacy | Oui | Audio rarement archivé |
| 9 | Gallica + presse d'époque | 1955-1995 | programme radio annoncé | Très faible/chronophage | Journaux scannés (OCR) | Oui via API Gallica/RetroNews | Non |

## Volume estimé pour le CSV cible (1955-2016, littérature)
- L'émission est hebdomadaire depuis la rentrée 1957 ; le cinéma occupe ~50 % de l'antenne (« une semaine sur deux »), littérature ~25 %, théâtre ~25 %. Sur 60 ans (1955-2015), on estime **~3 000-3 200 émissions au total**, dont **~750-900 émissions « littérature »** (numéros monothématiques + segments littérature dans les émissions mixtes des années 50-60).
- Pour 1995-2016 (DL radio), volume utile fiable : **~250-300 émissions strictement littérature** au catalogue.
- Pour 2006-2016 sur franceinter.fr : ~10 saisons × ~17 émissions livres/an ≈ **~170 émissions avec lien audio public potentiel**.

## Recommandations

### Étape 1 — Constitution du squelette du CSV (priorité haute, faisable immédiatement)
1. **Scraper catalogue.ina.fr** avec la requête : `« le masque et la plume »` + chaîne `France Inter ; Paris Inter ; RTF` + facette `Thématique = Littérature`, en parcourant la pagination HTML. Utiliser `requests` + `BeautifulSoup` ; respecter un délai de 1-2 s entre requêtes.
2. Pour chaque notice, extraire `id_notice`, `date_diffusion`, `heure`, `durée`, `thématique`, `générique` (animateur, producteur, réalisateur), `chapeau`, `résumé documentaire` (qui contient souvent les œuvres critiquées + les critiques présents en clair).
3. Stocker l'URL canonique `https://catalogue.ina.fr/doc/TV-RADIO/{id}/le-masque-et-la-plume` dans une colonne `lien_metadonnees_ina`.

### Étape 2 — Adjonction des liens audio publics (priorité moyenne)
4. **Scraper franceinter.fr** des pages `/emissions/le-masque-et-la-plume/archives-01-09-{AAAA}-25-06-{AAAA+1}` pour les saisons 2006-07 à 2015-16. Récupérer date, titre (qui contient le thème « Livres » ou les titres d'œuvres), liste des critiques présents, et URL de la page épisode.
5. Sur chaque page épisode (pattern `…/le-masque-et-la-plume-{JJ-mois-AAAA}`), tenter de récupérer le lien audio direct (élément `<audio src=…>` ou JSON-LD embarqué). Stocker dans `lien_audio_public`.
6. Joindre sur `date_diffusion` (clé naturelle) avec le squelette de l'étape 1.

### Étape 3 — Compléments pour 1956-2005 (priorité basse, qualitatif)
7. **Croiser avec la chronologie du livre Garcin/Garcia (2005)** pour identifier les émissions « culte » sans audio en ligne.
8. **Lister manuellement** les extraits YouTube via API Data v3 sur les deux playlists INA (ne pas s'attendre à plus de 80-150 résultats au total, dont peu en littérature).
9. **Pour les irréductibles** : prévoir un déplacement à un centre Inathèque (BnF site Mitterrand, BU Bordeaux Mériadeck, BU Grenoble Alpes). Aucune extraction automatique possible, mais la base de notices y est exhaustive et les collections de l'INA représentent près de 30 millions d'heures de programmes audiovisuels conservés.

### Schéma CSV recommandé
```
id_notice_ina, date_diffusion (YYYY-MM-DD), heure_diffusion (HH:MM), duree (mm:ss),
chaine (Paris Inter / France Inter / RTF), animateur, realisateur,
thematique (Littérature / Théâtre / Cinéma / Mixte), critiques_presents (pipe-separated),
oeuvres_critiquees (pipe-separated : titre — auteur — éditeur),
lien_metadonnees_ina, lien_audio_public, lien_extrait_ina, lien_youtube_extrait,
source_collecte (ina / franceinter / wayback / youtube / livre_garcin_2005),
audio_consultable_inatheque (oui/non), notes
```

### Seuils qui changeraient la stratégie
- Si l'INA ouvrait un endpoint OAI-PMH ou un dataset sur `data.gouv.fr` (à surveiller via la page de l'organisation `https://www.data.gouv.fr/organizations/institut-national-de-laudiovisuel`), l'étape 1 deviendrait triviale et exhaustive.
- Si un partenariat avec `apipartner.ina.fr` est financièrement envisageable, on obtient un JSON-LD propre couvrant tout le fonds.
- Si Radio France publiait un flux RSS rétroactif complet (au-delà des ~50 derniers épisodes du flux `rss_14007.xml`), l'étape 2 serait simplifiée.

## Caveats
- **Pré-1995, les notices INA sont souvent groupées par année** (« collection d'émissions simples ») et la thématique cumule Littérature+Théâtre+Cinéma — un filtre simple « Thématique = Littérature » ne renverra **pas** toutes les émissions littéraires de cette période. Prévoir un nettoyage textuel sur titre matériel et résumé documentaire.
- Le **flux RSS officiel** `https://radiofrance-podcast.net/podcast09/rss_14007.xml` ne conserve qu'une fenêtre glissante : il n'est pas une source d'archive exploitable.
- L'**audio public** sur ina.fr et franceinter.fr est soumis à des droits qui expirent : les pages anciennes peuvent perdre leur lecteur, même quand l'URL reste vivante. Il faut horodater chaque collecte.
- Les **listes Babelio/SensCritique** sont des sélections éditoriales subjectives (œuvres « plébiscitées » ou « unanimement enthousiasmées ») — exhaustivité non garantie.
- Le **scraping de catalogue.ina.fr nécessite de respecter les CGU de l'INA** : usage personnel/recherche autorisé, pas de rediffusion commerciale des notices ; le téléchargement et la photographie de l'audio sont explicitement interdits à l'Inathèque.
- Pour les années 1955-1957, l'émission était **mensuelle** (pas hebdomadaire) — adapter le volume estimé en conséquence.
- Wikipédia n'est **pas une source primaire** ; les dates de participation des critiques y sont souvent imprécises (« ?–? »).
- Le périmètre « littérature » a évolué dans le temps : à l'origine (1955-1957), l'émission ne couvrait QUE théâtre + littérature (avant l'arrivée du cinéma en octobre 1957). Donc pour la période 1955-1957, **toute** émission contient une part littérature.