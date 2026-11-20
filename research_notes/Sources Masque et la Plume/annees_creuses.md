# Les années creuses (1960-1986) : combien d'émissions, et quelles sources pour les attester ?

Recherche pour l'issue #77 (carte #48). Constats du 2026-11-20, faits :

- sur le cache local du catalogue INA (`data/raw/cache/ina/notices.csv`, 3 621 notices de la collection « Le masque et la plume », et les fiches détaillées `data/raw/cache/ina/fiches/*.html`), croisé avec `data/processed/emissions.csv` et `attestations.csv` de `main` @ `fafd1dc` ;
- par des requêtes réelles sur letempsarchives.ch, archive.org, Gallica, lemonde.fr, inatheque.ina.fr, radiofrance.com, et des recherches web.

Les notes `presse_numerisee.md`, `academique_bibliographique.md`, `archives_web_radiofrance_ina.md`, `audio_communautes.md` (même dossier) et les notes des branches `research/ina-madelen` et `research/sources-integraux-anciens` sont supposées connues. Ce qui y est établi n'est pas refait ici.

Légende : **[vérifié]** = constaté par une requête ou en lisant la page ; **[supposé]** = déduit, non confirmé.

## Réponse courte

- **Le creux de 1975-1984 est réel, il ne vient pas des sources.** Pour ces années, le catalogue INA a une notice pour 35 à 45 dimanches par an, toutes thématiques confondues : il ne manque que 2 à 12 semaines entre septembre et juin. Mais 2 à 8 de ces notices seulement sont littéraires. Le reste est du cinéma (17 à 28 par an) et du théâtre (7 à 18). Dans ces années-là, le Masque parlait peu de livres. Même si toutes les semaines manquantes étaient littéraires, on n'atteindrait pas 12 émissions littéraires par an (1979 : 2 + 7 au plus).
- **Les vrais trous de source sont 1985-1986, et dans une moindre mesure 1960, 1971-1972 et 1978.** En 1985, l'INA n'a que 9 dimanches (aucun de février à mai, un seul par mois ensuite) ; en 1986, 24. En 1971-1972, il en a deux par mois environ. En 1960, une suspension de l'émission est documentée (Wikipédia).
- **Estimation du nombre réel d'émissions** : environ **40 à 46 par an, tous thèmes confondus** (une par dimanche de septembre à juin, plus quelques émissions d'été). Pour les **émissions littéraires** : environ 9 à 14 par an de 1956 à 1966, 5 à 8 de 1967 à 1974, **2 à 8 de 1975 à 1984**, sans doute 5 à 10 en 1985-1986, 9 à 12 de 1987 à 1993. Source : la répartition par thème des notices INA, sur des années où leur couverture est presque complète. Une estimation par la presse n'est possible que pour quelques semaines.
- **La seule source qui donne le thème de chaque dimanche est la presse de programmes**, en premier lieu *Télérama*. Elle n'est pas en ligne pour la période, sauf une vingtaine de numéros de 1980-1981 sur archive.org. La presse suisse (letempsarchives.ch, gratuite et interrogeable par script) atteste le créneau chaque semaine en 1974-1976, sans le thème, et donne thème et critiques de 1992 à 1998. Elle est muette de 1977 à 1991.
- **Recommandation** : (1) documenter que la courbe des années 1975-1984 reflète l'émission, pas les sources ; (2) pour 1985-1986, dépouiller *Télérama* papier (BnF ou Inathèque), environ 100 dimanches ; (3) ne pas automatiser la presse suisse tant que la liste ne retient que les émissions littéraires ; (4) réserver l'Inathèque, les archives écrites de Radio France et les Archives nationales à des doutes ponctuels ; (5) écarter Gallica, RetroNews, les livres et les passionnés pour cette question.

## 1. Combien d'émissions par an ? Ce que dit déjà le catalogue INA

### Constats

La liste publiée ne retient que les émissions littéraires. Le cache INA, lui, contient toutes les notices de la collection, quel que soit le thème. On peut donc compter les dimanches attestés, tous thèmes confondus **[vérifié]**.

Pour chaque année : nombre de dates distinctes ayant une notice INA ; dates dont le titre ou la facette « Littérature » indique les livres (L), le cinéma (C), le théâtre (T) ; dates sans thème lisible dans le titre (« Le masque et la plume du 13 janvier 1985 ») ; semaines de septembre à juin sans aucune notice ; nombre d'émissions dans la liste publiée.

| Année | Dates INA | L | C | T | Sans thème | Semaines sept.-juin sans notice | Liste publiée |
|---|---|---|---|---|---|---|---|
| 1958 | 32 | 12 | 12 | 8 | 0 | 12 | 12 |
| 1959 | 43 | 13 | 17 | 13 | 0 | 5 | 13 |
| 1960 | 23 | 8 | 6 | 7 | 2 | 23 | 8 |
| 1961 | 32 | 8 | 10 | 13 | 2 | 13 | 7 |
| 1962 | 41 | 13 | 16 | 10 | 2 | 6 | 14 |
| 1963 | 40 | 10 | 16 | 14 | 3 | 5 | 10 |
| 1964 | 34 | 7 | 16 | 11 | 1 | 14 | 7 |
| 1965 | 36 | 9 | 15 | 12 | 0 | 8 | 9 |
| 1966 | 32 | 9 | 15 | 10 | 0 | 11 | 9 |
| 1967 | 32 | 5 | 16 | 10 | 1 | 11 | 5 |
| 1968 | 31 | 7 | 17 | 9 | 0 | 12 | 6 |
| 1969 | 38 | 6 | 19 | 14 | 0 | 8 | 6 |
| 1970 | 32 | 7 | 19 | 8 | 0 | 13 | 7 |
| 1971 | 23 | 3 | 12 | 9 | 0 | 21 | 3 |
| 1972 | 26 | 3 | 13 | 10 | 0 | 17 | 3 |
| 1973 | 38 | 6 | 18 | 16 | 0 | 5 | 6 |
| 1974 | 38 | 5 | 18 | 15 | 0 | 6 | 5 |
| 1975 | 43 | 3 | 17 | 18 | 5 | 3 | 4 |
| 1976 | 42 | 6 | 23 | 14 | 10 | 4 | 6 |
| 1977 | 42 | 3 | 26 | 13 | 0 | 5 | 3 |
| 1978 | 35 | 3 | 24 | 9 | 0 | 12 | 3 |
| 1979 | 38 | 2 | 27 | 8 | 1 | 7 | 2 |
| 1980 | 42 | 5 | 28 | 8 | 1 | 2 | 5 |
| 1981 | 38 | 3 | 25 | 8 | 2 | 7 | 3 |
| 1982 | 41 | 3 | 28 | 7 | 4 | 5 | 2 |
| 1983 | 45 | 6 | 26 | 8 | 5 | 3 | 6 |
| 1984 | 39 | 8 | 20 | 8 | 3 | 6 | 8 |
| **1985** | **9** | 2 | 1 | 1 | 5 | **36** | 2 |
| **1986** | **24** | 5 | 2 | 2 | 15 | **20** | 5 |
| 1987 | 47 | 9 | 1 | 0 | 37 | 2 | 9 |
| 1988 | 42 | 11 | 16 | 9 | 7 | 9 | 11 |
| 1989 | 48 | 12 | 22 | 7 | 7 | 2 | 12 |
| 1990 | 44 | 11 | 20 | 9 | 5 | 5 | 11 |

(Une date peut compter dans plusieurs colonnes de thème : émission mixte, ou plusieurs notices le même jour. Pour 1986-1987, le thème vient surtout de la facette « Littérature » des fiches, les titres étant de la forme « Le masque et la plume du … ».)

- Exemple, 1979 : notices pour 38 dimanches. 27 sont du cinéma (dont trois émissions sur le Festival de Cannes), 8 du théâtre, 2 de la littérature (8 juillet et 25 novembre), 1 hommage à Jean-Louis Bory (15 juillet). Les dimanches sans notice sont les 7 et 14 janvier, 25 février, 15, 22 et 29 avril, puis l'été (22 juillet - 9 septembre) **[vérifié]**.
- Les fiches de ces années décrivent des émissions entières et datées : par exemple la fiche `PHD99233379` (7 octobre 1979), « Emission publique présentée par François Régis BASTIDE et Martine de RABAUDY consacrée au cinéma », avec les critiques et les films, durée 1 h **[vérifié]**.
- 1985 : notices les 6, 13, 20 et 27 janvier, 9 juin, 25 août, 1er septembre, 6 octobre et 10 novembre, rien d'autre. 1986 : rien de février à mars ni de juin à septembre, sauf le 27 juillet et le 21 septembre **[vérifié]**.
- 1971-1972 : deux notices par mois presque partout (cinq en octobre 1972) **[vérifié]**. Je ne sais pas si l'émission était alors bimensuelle ou si l'INA n'a gardé qu'une émission sur deux **[lacune]**.

### Déductions

- De 1973 à 1984, le catalogue INA est **presque complet** sur les dimanches d'antenne, et la presse suisse le confirme pour 1974-1976 (section 2) : sur environ 105 annonces hebdomadaires, une dizaine seulement tombent un dimanche sans notice INA **[vérifié]**. Le faible nombre d'émissions littéraires de ces années est donc **un fait de programmation**, pas une lacune de collecte. Le Masque de l'époque Bastide-Bory-Charensol est surtout une émission de cinéma **[supposé pour l'interprétation, vérifié pour les chiffres]**.
- Borne haute des émissions littéraires : L + semaines sans notice. Elle donne 9 en 1979, 8 en 1982, 7 en 1980. L'hypothèse de l'issue (« une douzaine par an ») ne tient pas pour 1975-1984.
- La part littéraire passe d'environ 25-30 % des émissions (1958-1966) à 10-15 % (1967-1984), puis revient à 25 % (1988-1990). Appliquée à environ 42 émissions par an, elle donne l'estimation de la réponse courte **[supposé]**.
- 1985-1986 sont les seules années de la période où l'INA est vraiment lacunaire. En 1986, 5 des 24 notices sont littéraires (environ 20 %) : sur 42 émissions, cela ferait environ 8 émissions littéraires par an, dont 3 à 6 manqueraient chaque année **[supposé]**.

### Lacunes

- Le cache ne contient que les notices de la collection « Le masque et la plume » retrouvées par la recherche « masque et la plume » (`src/lmelp_pap/sources/ina_catalogue.py`). Des notices de 1985-1986 rangées sous un autre titre de collection ont pu échapper ; je ne l'ai pas vérifié dans catalogue.ina.fr.
- La cause du trou de 1985-1986 à l'INA (versement manquant de Radio France, grève, changement de politique de conservation) n'est pas établie.

## 2. Presse d'époque

### 2.1 Gallica et RetroNews

- [vérifié] Le SRU de Gallica (`gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=gallica all "masque et la plume" and dc.date >= "1985"`) répond toujours **403 Cloudflare** (« Attention Required! ») à curl comme à WebFetch, comme le 2026-11-08.
- [vérifié, note `presse_numerisee.md`] La presse de Gallica et RetroNews s'arrête vers 1950-1951, pour des raisons de droits.
- **Bilan** : couverture nulle pour 1960-1986. À écarter.

### 2.2 Presse suisse : letempsarchives.ch (*Journal de Genève*, *Gazette de Lausanne*, *Le Nouveau Quotidien*, 1798-1998)

#### Constats
- [vérifié] Le site est gratuit et sans Cloudflare. La recherche se fait par un appel `POST /rechercheAjax` (`type=articles`, `qry="masque et la plume"`, `skip`, `sort=date_asc`), qui renvoie du JSON : `numFound` et le HTML des résultats, avec des liens `/page/JDG_AAAA_MM_JJ/page/article/id`. La page de chaque article donne le cadre de l'article dans l'image de la page (`imageToViewportRectangle(x,y,l,h)`), et l'image se découpe par IIIF (`/iiif/GDL_1976_01_24_16/x,y,l,h/largeur,/0/default.jpg`). Le texte OCR n'est pas exposé : l'extrait (`/extrait/...`) et `/data/search/...` reviennent vides — [letempsarchives.ch](https://www.letempsarchives.ch/recherche?q=%22masque+et+la+plume%22).
- [vérifié] **689 résultats** pour `"masque et la plume"`. Par année (dates distinctes) : 1960 : 5, 1962-1971 : 1 à 7 par an, **1974 : 28, 1975 : 38, 1976 : 25**, 1977 : 4, 1978-1985 : 0 à 3 par an, 1986 : 66, 1988-1991 : 1 à 2, **1992 : 13, 1993 : 43, 1994 : 59, 1995 : 95, 1996 : 97, 1997 : 51**, 1998 : 10.
- [vérifié] En 1974-1976, ce sont les pages radio du samedi, rubrique « France : choix d'émissions ». Exemple, *Gazette de Lausanne* du 24 janvier 1976, p. 16, pour le dimanche 25 : « France Inter : 20.15 Le masque et la plume — 21.15 La musique est à vous ». *Journal de Genève* du 8 mars 1975, p. 24 : même ligne. **Pas de thème.** Les dimanches correspondants ont une notice INA (25 janvier 1976 : « Cinéma » ; 9 mars 1975 : « Télévision »).
- [vérifié] Sur environ 105 annonces de 1974-1976, une dizaine tombent un dimanche sans notice INA : 9 juin, 14 et 21 juillet, 1er et 8 décembre 1974 ; 5 et 26 janvier 1975 ; 1er août, 14 et 21 novembre 1976 (dimanche suivant la date du journal ; à vérifier un par un).
- [vérifié] En 1993, *Le Nouveau Quotidien* donne **le thème et les critiques** : le 17 janvier 1993, p. 60 : « 20 h 00 Le masque et la plume. Emission proposée par Jérôme Garcin. Cinéma, avec : Jacques Siclier, Pierre Murat et Michel Ciment. » L'INA a la notice (« Cinéma », 17 janvier 1993).
- [vérifié] Les 66 dates de 1986 (juillet-septembre, tous les jours) et les résultats de 1985 sont des **homonymes** : la page « cinémas » de Lausanne pendant l'été 1986, et une collection d'édition théâtrale lyonnaise « Le masque et la plume » (*Journal de Genève*, 19 octobre 1985, p. 20).

#### Bilan
Période utile : 1974-1976 (créneau seul) et 1992-1998 (thème et critiques). **Rien pour 1977-1991**, ni pour 1985-1986. Gratuit et automatisable (recherche JSON + images IIIF), mais il faut lire ou passer à l'OCR chaque découpe d'image. Gain pour la liste littéraire : quasi nul (une dizaine de dates de 1974-1976 sans thème, et 1992-1998 est déjà couvert par l'INA).

### 2.3 *Télérama* (ex-*Radio-Cinéma-Télévision*)

#### Constats
- [vérifié] *Télérama* annonce le thème de chaque Masque. Numéro 1615 (24 décembre 1980), pour le dimanche 28 décembre : « 20.15 LE MASQUE ET LA PLUME. Magazine de François-Régis Bastide, avec l'équipe des Critiques. LA LITTERATURE. » Numéro 1622 (11 février 1981), pour le dimanche 15 février : « 20.15 Le masque et la plume. Magazine de François-Régis Bastide. Cinéma. » — [archive.org telerama-1615-1980-12-24](https://archive.org/details/telerama-1615-1980-12-24) ; [archive.org telerama-1622-1981-02-11](https://archive.org/details/telerama-1622-1981-02-11)
- [vérifié] L'annonce peut différer de ce qui est diffusé : pour le 28 décembre 1980, la fiche INA `PHD99255837` s'intitule « Théâtre » et décrit une émission « consacrée à Pierre DUX, comédien et ancien administrateur général de la Comédie française, à l'occasion de la parution de son livre ». Le 15 février 1981, l'INA a bien « Cinéma ».
- [vérifié] Sur archive.org, une recherche sur le titre « télérama » donne 41 items, dont une vingtaine de numéros de 1980-1981 (collection `videomagazinesmisc`, avec OCR `_djvu.txt` en accès libre), un de 1974 et un de 1967. Aucun pour 1985-1986 — [API archive.org](https://archive.org/advancedsearch.php?q=title%3A%28telerama%29&fl[]=identifier&fl[]=date&rows=100&output=json).
- [vérifié, résultat de recherche] PressReader propose des numéros de *Télérama* sur abonnement ; je n'ai pas vérifié quelles années — [PressReader](https://www.pressreader.com/fr/magazines/m/telerama/issues).
- [supposé] La collection complète se consulte sur papier ou microfilm à la BnF (dépôt légal), et sans doute parmi les périodiques de l'Inathèque (salle P, section 3.1).

#### Bilan
Période : toute la période (hebdomadaire depuis 1950). Atteste la date, le thème annoncé, parfois les œuvres. Coût : lecture sur place (BnF, carte de lecteur), ou abonnement PressReader à évaluer. Automatisable : non, sauf les numéros d'archive.org. Gain attendu : le thème de chaque dimanche manquant, donc **3 à 6 émissions littéraires par an en 1985-1986**, et quelques-unes en 1960, 1971-1972 et 1978. Une émission attestée seulement par l'annonce reste à confirmer : le cas du 28 décembre 1980 montre qu'une annonce peut être fausse.

### 2.4 *Le Monde*, *Le Figaro* et autres quotidiens français

- [vérifié] `lemonde.fr/archives-du-monde/` répond **402 « Accès restreint »** à un accès automatisé ; la recherche avait renvoyé 410 le 2026-11-08.
- [vérifié, résultats de recherche] Les archives du *Monde* depuis 1944 sont en ligne pour les abonnés, et consultables sur place à la BnF ; ProQuest diffuse 1944-2000 aux bibliothèques, Europresse seulement depuis 2001 — [BnF, ressources électroniques de presse](https://www.bnf.fr/fr/ressources-electroniques-de-presse) ; [ProQuest](https://about.proquest.com/en/news/2021/frances-le-monde-newspaper-archive-will-be-available-to-academic-and-public-libraries-through-proquest).
- [supposé] La grille radio quotidienne du *Monde* cite le Masque, avec un thème court ou pas de thème. Les CGU du *Monde* interdisent l'extraction automatique.
- *Le Figaro* : présent sur Gallica et RetroNews jusqu'en 1942-1950 seulement [vérifié, note `presse_numerisee.md`] ; ensuite, aucune archive en ligne repérée.
- **Bilan** : couverture complète mais payante et non automatisable ; utile comme vérification ponctuelle, moins précise que *Télérama*.

## 3. Inathèque et catalogue public

### Constats
- [vérifié] Le catalogue en ligne de l'Inathèque est **catalogue.ina.fr**, le même que celui qu'utilise la collecte : la page d'accueil renvoie vers lui par « Commencez vos recherches » — [inatheque.ina.fr](https://inatheque.ina.fr/).
- [vérifié] Les *Règles de la consultation à l'Inathèque* (février 2026) : accès « à tout usager justifiant d'un projet de recherche et sur accréditation délivrée par l'INA », sur réservation, avec la carte de lecteur de la BnF. Reproduction du son interdite. La photocopie est permise pour les archives écrites, la photo pour les monographies et périodiques. Surtout, l'usager peut demander un **export de notices et de listes de notices** (20 Mo au plus) — [Règles 2026 (PDF)](https://inatheque.ina.fr/hub-p/public/2026-02/Regles-de-consultation-a-l-INAtheque-2026.pdf).
- [vérifié] L'Inathèque propose aussi des « sources écrites » : monographies, périodiques et « documents déposés par des diffuseurs » — [fonds et collections](https://inatheque.ina.fr/fonds-et-collections-ina-par-medias).
- [vérifié, note `ina-madelen.md`] Dans le catalogue, le dépôt légal de la radio commence vers 1995 ; avant, toutes les notices du Masque viennent des « Archives Radio Pro » (fonds INA et INA - Radio France).

### Bilan
Pour 1960-1986, l'Inathèque ne devrait pas connaître **plus de notices** que catalogue.ina.fr : ce sont les mêmes archives professionnelles **[supposé]**. Son intérêt est ailleurs : écouter une émission pour trancher un doute de thème, consulter des périodiques de programmes et des archives écrites, exporter une liste de notices. Coût : accréditation (projet de recherche), sur place. Automatisable : non. Gain sur les années creuses : faible.

## 4. Archives de Radio France et Archives nationales

### Constats
- [vérifié] Le Service Archives écrites et Musée de Radio France (SAEM) conserve les archives des directions et des chaînes avant leur versement aux Archives nationales. Il est ouvert au public sur rendez-vous en semaine (catalogue de 2018) — [catalogue SAEM 2018 (PDF)](https://www.radiofrance.com/sites/default/files/2021-02/catalogue_ouvrages_archives_ecrites_musee_radio_france_2018.pdf).
- [vérifié] L'inventaire « ORTF, Direction de la radiodiffusion 1937-1975 » (Archives nationales, CAC de Fontainebleau, 2001) a une série « Programme France-Inter 1280/rqfi » (Paris-Inter puis France-Inter, responsable Agathe Mella de 1955 à 1968). On y trouve des généralités, des rapports d'écoutes 1957-1958, des projets d'émissions 1960-1963, des minutiers (Paris Inter et France I, 1963 ; Mme Mella, 1963-1964), et, au service de la musique enregistrée, des « Programmes définitifs, 1949-1964 » (cotes 1986/23-54). Aucune mention du Masque — [inventaire SAEM 1937-1975 (PDF)](https://www.radiofrance.com/sites/default/files/imported_pdfs/saem_inventaire_1937_1975.pdf).
- [vérifié, résultat de recherche] Une réponse ministérielle indique que les archives historiques de Radio France sont accessibles au SAEM, aux Archives nationales ou à l'Inathèque (accord tripartite de 1995) — [question écrite, Assemblée nationale](https://www.assemblee-nationale.fr/dyn/12/questions/QANR5L12QE80668.pdf).
- Le champ `transcript.magnetothequeId` de l'Open API Radio France n'a pas été réexaminé ici (clé non utilisée).

### Bilan
Période : 1955-1975 aux Archives nationales (ORTF), après 1975 au SAEM. Ce que ces fonds attesteraient (programmes définitifs, minutiers, conducteurs) est probable mais non vérifié pour le Masque **[supposé]**. Coût : sur place, sur rendez-vous, délais de communicabilité. Automatisable : non. Gain attendu : inconnu ; utile seulement pour un doute précis, ou pour 1985-1986 si *Télérama* ne suffit pas.

## 5. Ouvrages et travaux sur l'émission

- [vérifié] Le catalogue du SAEM décrit le livre de Garcin et Garcia (Les Arènes, 2005) : « Retrace 50 ans d'une émission culte […] 1. 1955-1960, les fondations ; 2. 1960-1979, la grande époque ; 3. 1979-2005, l'institution ; 4. Les masquaires. » Le volume de 2007 retranscrit des passages de l'année 2006. — [catalogue SAEM 2018 (PDF)](https://www.radiofrance.com/sites/default/files/2021-02/catalogue_ouvrages_archives_ecrites_musee_radio_france_2018.pdf)
- [vérifié, note `academique_bibliographique.md`] Aucune thèse ni aucun article ne liste les émissions ; le livre de 2005 est en prêt contrôlé sur Internet Archive, sans recherche plein texte publique.
- **Bilan** : récit et anthologie, pas de liste **[supposé]**. Le chapitre « 1960-1979 » pourrait expliquer la place du cinéma dans ces années, ce qui confirmerait l'interprétation de la section 1. Gain pour attester des émissions : faible.

## 6. Passionnés

- [vérifié, notes `audio_communautes.md` et `sources-integraux-anciens.md`] Aucun site, forum ou collection de passionnés en ligne ; les rares dépôts (YouTube, archive.org) sont du cinéma ou non datés.
- **Bilan** : aucun gain attendu pour 1960-1986 sans appel ciblé (#54).

## Synthèse

| Piste | Période couverte | Ce qu'elle atteste | Accès | Automatisable | Gain attendu sur les années creuses |
|---|---|---|---|---|---|
| Catalogue INA, tous thèmes (déjà en cache) | 1956-… ; presque complet 1973-1984 et 1987+ | date, thème, critiques, œuvres | en ligne, gratuit | oui (déjà fait) | explique le creux 1975-1984 : il est réel |
| *Télérama* | 1950-… | date, thème annoncé, parfois œuvres | papier à la BnF ou Inathèque ; 20 numéros 1980-1981 sur archive.org ; PressReader payant | non (sauf archive.org) | **3 à 6 émissions littéraires par an en 1985-1986**, quelques-unes en 1960, 1971-1972, 1978 |
| letempsarchives.ch (presse suisse) | 1974-1976 (créneau) ; 1992-1998 (thème, critiques) | date ; thème après 1992 | en ligne, gratuit | oui (JSON + IIIF, lecture d'image) | une dizaine de dates 1974-1976 sans thème ; rien pour 1977-1991 |
| *Le Monde* (archives) | 1944-… | date, thème court [supposé] | abonnement, BnF, ProQuest | non (CGU) | vérification ponctuelle |
| Gallica, RetroNews | jusqu'à ~1950 | — | bloqué (403) | — | nul |
| Inathèque | mêmes notices que catalogue.ina.fr [supposé] | écoute, export de notices, périodiques | accréditation, sur place | non | faible (doutes ponctuels) |
| SAEM Radio France, Archives nationales | 1937-1975 (AN) ; après 1975 (SAEM) | programmes définitifs, minutiers [supposé] | sur rendez-vous | non | inconnu |
| Livres (Garcin et Garcia 2005…) | 1955-2005 | récits, débats célèbres | prêt contrôlé, papier | non | faible |
| Passionnés | — | — | — | — | nul en ligne |

## Lacunes

- Je n'ai pas vérifié dans catalogue.ina.fr si des notices de 1985-1986 existent sous un autre titre de collection.
- Je n'ai testé *Télérama* que sur deux numéros de 1980-1981. Je n'ai pas téléchargé les autres numéros d'archive.org, ni vérifié la couverture de PressReader.
- La cause des trous de 1971-1972 (émission bimensuelle ?) et de 1985-1986 à l'INA reste inconnue.
- Les dix dates 1974-1976 attestées seulement par la presse suisse n'ont pas été vérifiées une par une (lecture de l'image, dimanche concerné).
