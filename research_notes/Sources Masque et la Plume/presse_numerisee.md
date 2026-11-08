# Presse numérisée attestant des émissions du Masque et la Plume (1955-2016)

Recherche faite le 2026-11-08 depuis le devcontainer (curl et WebFetch). Légende : **[vérifié]** = obtenu par une requête réelle ; **[supposé]** = connaissance générale ou source secondaire non recoupée.
Contrainte principale : plusieurs serveurs (Gallica, e-newspaperarchives.ch, lemonde.fr) **bloquent les accès automatisés depuis cet environnement** (Cloudflare 403, refus de fetch). Je n'ai donc pas pu obtenir de nombre de résultats pour ces sources. Ce que je donne sur ces sources est à revérifier depuis un navigateur.

## Gallica (SRU, texteBrut / ContentSearch) : y a-t-il des résultats pour « masque et la plume », dans quels titres et quelles années ?

### À retenir
Je n'ai pas pu interroger l'API SRU de Gallica : toutes les requêtes reçoivent une page Cloudflare « Attention Required! » (HTTP 403), avec ou sans User-Agent. Surtout, pour des raisons de droits, la presse quotidienne sur Gallica et RetroNews s'arrête vers 1950-1951 : Gallica ne peut presque rien attester pour 1955-2001.

### Constats sourcés
- [vérifié] `https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=gallica all "masque et la plume"` (et ses variantes avec `dc.date >= "1955"` ou `dc.type all "fascicule"`) renvoie un 403 Cloudflare (titre de page « Attention Required! | Cloudflare ») avec curl sans User-Agent, avec un User-Agent navigateur, python-requests ou personnalisé. WebFetch reçoit aussi un 403. Aucun nombre de résultats n'est disponible. — [Gallica SRU](https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=gallica%20all%20%22masque%20et%20la%20plume%22)
- [vérifié, source secondaire] La BnF a reconnu avoir mis en ligne par erreur des documents publiés après 1951 sans l'accord des éditeurs, puisque les œuvres collectives restent protégées 70 ans. Selon elle, les journaux de RetroNews et de Gallica s'arrêtent au plus tard en 1951. Les liens vers les titres retirés mènent à des pages vides. — [Revue française de généalogie, « Rétropédalage chez RetroNews »](https://www.rfgenealogie.com/infos/retropedalage-chez-retronews)
- [vérifié, source secondaire] Combat est présent sur Gallica pour 1941-1948 selon un annuaire, pour 1941-1944 selon un miroir de Wikipédia. Je n'ai trouvé aucune trace d'une numérisation 1950-1974. — [theancestorhunt.com](https://theancestorhunt.com/blog/france-free-online-historical-newspapers) ; [Combat (newspaper), Wikipedia](https://www.Wikipedia.com/wiki/Combat_(newspaper))
- [vérifié] Une recherche web « "Masque et la Plume" gallica.bnf.fr » ne renvoie aucune notice Gallica sur l'émission. — [recherche web, aucun résultat pertinent ; ex. Causeur ne cite Gallica que pour une photo](https://www.causeur.fr/fabienne-pascaud-telerama-moliere-159918)

### Déductions
- [supposé] Une fois le blocage levé, une requête SRU sur la période 1955-2001 ne devrait trouver que des documents hors presse quotidienne : livres, revues sous convention, et peut-être quelques périodiques institutionnels ou régionaux. Ces documents peuvent contenir des grilles de programmes, mais pas de manière systématique.
- [supposé] Si on obtient des résultats, l'OCR est en principe récupérable. Il faut alors passer par les points d'accès documentés sur api.bnf.fr : `https://gallica.bnf.fr/services/ContentSearch?ark=...&query=...` pour les extraits, `.../texteBrut` ou `/RequestDigitalElement?O=...&E=ALTO&Deb=n` pour le texte intégral. Le blocage Cloudflare constaté s'appliquerait aussi à ces points d'accès.
- Intérêt pour la période 1955-2001 : **faible**.

### Lacunes
- Le nombre réel de résultats SRU reste inconnu. Il faut relancer la requête depuis un navigateur ou une IP non bloquée, ou demander un accès à la BnF (api.bnf.fr).
- Je n'ai pas pu vérifier la présence de titres d'après 1955 sur Gallica : périodiques régionaux, bulletins de la RTF, *Radio-Cinéma-Télévision*.

## Magazines de programmes (Radio-Cinéma-Télévision / Télérama, Télé 7 jours, Télé-Magazine, La Semaine radiophonique, Télé-Poche) : sont-ils numérisés ?

### À retenir
Je n'ai trouvé aucune numérisation accessible librement ou par API de ces magazines pour 1955-2001. Pourtant, ce seraient les meilleures sources, car leurs programmes détaillent les thèmes des émissions.

### Constats sourcés
- [vérifié, source secondaire] *Radio-Cinéma-Télévision* devient *Télérama* en 1960, au n° 559. La Národní filmový archiv (Prague) recense le titre du n° 364 (6.01.1957) au n° 558 (25.09.1960). L'hebdomadaire est né en 1950 d'une collaboration entre La Vie catholique et les Éditions du Cerf. — [NFA, notice Radio-cinéma-télévision](https://arl.nfa.cz/arl-nfa/en/detail-nfa_un_cat-193761-Radio-cinema-television) ; [Télérama, Wikipedia](https://en.wikipedia.org/wiki/T%C3%A9l%C3%A9rama)
- [vérifié] La recherche web n'a trouvé aucune mention d'une numérisation de *Radio-Cinéma-Télévision* ou de *Télérama* (années 1950-1990) sur Gallica. — [résultats de recherche, ex. Wikipedia Télérama](https://en.wikipedia.org/wiki/T%C3%A9l%C3%A9rama)

### Déductions
- [supposé] Télérama propose à ses abonnés des archives d'articles en ligne, surtout depuis la fin des années 1990. Les numéros anciens ne sont pas en ligne en mode image avec OCR. Télé 7 jours, Télé-Magazine, La Semaine radiophonique et Télé-Poche : à ma connaissance, aucune numérisation publique.
- [supposé] Ces collections papier se consultent sur place : BnF (dépôt légal), Inathèque. L'Inathèque conserve aussi les conducteurs et les fiches de programmes, une piste à transmettre au chercheur qui couvre l'INA.
- Intérêt : **fort sur le fond, nul pour l'automatisation** en l'état.

### Lacunes
- Je n'ai pas vérifié s'il existe une numérisation partielle de Télérama ou Radio-Cinéma-Télévision par Bayard, La Vie ou le Cerf, ou dans Europeana.

## RetroNews : période couverte, API, accès payant, nombre de résultats

### À retenir
RetroNews couvre 1631 à environ 1950 : la période du Masque (1955+) est hors champ. Son API exige un jeton (bearer) et le site est une application en JavaScript sans recherche publique scriptable.

### Constats sourcés
- [vérifié] `https://api.retronews.fr/search?...` et `/v1/search?...` répondent HTTP 401 « No bearer provided ». La page `retronews.fr/search` est une application Next.js qui appelle `api.retronews.fr`. — [api.retronews.fr](https://api.retronews.fr/search?q=%22masque+et+la+plume%22)
- [vérifié] La BnF annonce des titres publiés de 1631 à 1954. D'autres sources parlent de 1631 à 1950 (700 ou 1 500 titres selon la date). Les documents d'après 1951 ont été retirés (voir plus haut). Les archives se consultent gratuitement. L'abonnement donne accès aux contenus éditoriaux complets et aux fonctions avancées. Il existe une offre « Edu » pour l'enseignement supérieur, avec une sélection de journaux contemporains. — [BnF, RetroNews](https://www.bnf.fr/fr/retronews-le-site-de-presse-de-la-bnf) ; [RetroNews Edu Universitaires (PDF)](https://www.bnf.fr/sites/default/files/2025-02/RetroNews_Edu_Universitaires.pdf) ; [rfgenealogie](https://www.rfgenealogie.com/infos/retropedalage-chez-retronews)

### Déductions
- Le nombre de résultats pour « masque et la plume » est inconnu, mais il devrait être proche de zéro pour 1955+. L'offre Edu (« journaux contemporains ») reste à examiner : on ne sait pas quels titres ni quelles années elle couvre.
- Intérêt : **faible**.

### Lacunes
- La liste des titres contemporains de RetroNews Edu n'est pas vérifiée.

## Archives du Monde (lemonde.fr/archives) : grilles et présentations de l'émission ?

### À retenir
Je n'ai rien pu vérifier : lemonde.fr refuse WebFetch, et la requête curl a reçu HTTP 410. Les archives du Monde depuis 1944 sont en ligne et réservées aux abonnés [supposé]. On peut donc penser que la rubrique radio-télévision du Monde y figure.

### Constats sourcés
- [vérifié] `https://www.lemonde.fr/recherche/?search_keywords="masque et la plume"&start_at=01/01/1955...` renvoie HTTP 410 à curl ; WebFetch répond « unable to fetch from www.lemonde.fr ». La recherche web `site:lemonde.fr/archives` ne renvoie rien. — [lemonde.fr/recherche](https://www.lemonde.fr/recherche/)

### Déductions
- [supposé] Le Monde publiait chaque jour une page de programmes radio-TV, avec des « sélections » commentées pour certaines émissions. Les archives en ligne contiennent des articles en texte OCR, chacun avec une URL `lemonde.fr/archives/article/AAAA/MM/JJ/...`, mais les pages de grilles ne sont pas forcément découpées en articles. Accès payant, extraction automatique contraire aux CGU et techniquement filtrée.
- Intérêt : **moyen**, pour des mentions de critiques et de débats, et non pour une liste complète des émissions.

### Lacunes
- Nombre de résultats et format des grilles anciennes : à vérifier depuis un navigateur avec un compte abonné.

## Europeana, presse régionale, presse suisse, belge et luxembourgeoise

### À retenir
L'API Europeana fonctionne mais ne renvoie que 2 notices audiovisuelles INA. L'API plein texte Europeana Newspapers renvoie 0 résultat. e-newspaperarchives.ch bloque les requêtes automatisées (403). L'API eluxemburgensia n'est pas documentée publiquement. La piste la plus prometteuse reste la presse suisse romande, dont les pages radio listaient aussi des stations étrangères [supposé], mais elle n'est pas vérifiée.

### Constats sourcés
- [vérifié] L'API Europeana Search (`wskey=api2demo`, `query="masque et la plume"`) donne `totalResults=2`, deux vidéos INA/EUscreenXL : « Le masque et la plume : "Chroniques martiennes" » et « Pourquoi Michel Polac a quitté "le Masque et la plume" en 1970 ». Avec `theme=newspaper` : 0. — [Europeana item P12160834](https://www.europeana.eu/item/2051908/data_euscreenXL_ina_P12160834) ; [Europeana item P14211319](https://www.europeana.eu/item/2051908/data_euscreenXL_ina_P14211319)
- [vérifié] L'API plein texte Europeana Newspapers (`newspapers.eanadev.org/api/v2/search.json`) donne `totalResults: 0`. — [newspapers.eanadev.org](https://newspapers.eanadev.org/api/v2/search.json?wskey=api2demo&query=%22masque+et+la+plume%22)
- [vérifié] Recherche plein texte sur e-newspaperarchives.ch : HTTP 403 avec curl et WebFetch. — [e-newspaperarchives.ch](https://www.e-newspaperarchives.ch/)
- [vérifié] La page de recherche `eluxemburgensia.lu/search?query=...` répond 200 mais les résultats sont chargés par JavaScript. Le point d'accès `/api/viewer2/search` répond 404. — [eluxemburgensia](https://eluxemburgensia.lu/)

### Déductions
- [supposé] La presse suisse romande (L'Impartial, Feuille d'avis de Neuchâtel / L'Express, La Liberté, Le Confédéré…) est numérisée en OCR jusqu'aux années 1990-2000 sur e-newspaperarchives.ch, avec une interface Veridian. Les pages radio de ces journaux donnaient surtout Sottens/RSR, parfois des postes français. À tester à la main dans un navigateur ; si cela donne des résultats, l'export Veridian (`&f=XML`) pourrait permettre un traitement automatique. Intérêt : **moyen** (à confirmer).
- [supposé] Les archives de Letempsarchives.ch (Journal de Genève, Gazette de Lausanne, 1798-1998, gratuites, OCR) sont une autre piste suisse, non testée. BelgicaPress (KBR) ne donne accès en ligne qu'aux numéros d'avant 1950 environ ; le reste se consulte sur place. Lectura+, Limédia, Numelyo et les archives Ouest-France n'ont pas été testés : leurs fonds de presse numérisée s'arrêtent en général avant 1950, pour la même raison de droits. Intérêt : **faible**.

### Lacunes
- Aucun nombre de résultats n'a été obtenu pour e-newspaperarchives.ch, letempsarchives.ch, BelgicaPress, eluxemburgensia ni la presse régionale française.

## Les grilles donnent-elles le thème de la semaine (« les livres » / « le cinéma ») ? Exemples datés

### À retenir
Je n'ai trouvé dans la presse numérisée aucun exemple vérifié de grille donnant le thème. La seule grille trouvée (RadioScope) donne le créneau et les animateurs, sans thème.

### Constats sourcés
- [vérifié] RadioScope, grille Paris-Inter 1957-1958 : « Le masque et la plume (Michel Polac, François Régis-Bastide) », le jeudi à 22h. La page ne cite pas ses sources et ne donne pas de thème. — [RadioScope, Paris Inter 1957-1958](https://www.radioscope.fr/grilles/inter/inter1957.htm)
- [vérifié, source secondaire] Selon l'INA, la première séance consacrée au cinéma date du 24 octobre 1957, et la plus ancienne émission conservée à l'INA du 22 janvier 1956. Des émissions du 2 décembre 1956 (*L'Emploi du temps*) et du 7 novembre 1957 (*La Modification*) sont recensées à l'Inathèque. — [INA, « 70 ans d'impertinence »](https://www.ina.fr/ina-eclaire-actu/le-masque-et-la-plume-emission-radio-france-inter-jerome-farcin-critique) ; [Wikipedia FR](https://fr.wikipedia.org/wiki/Le_Masque_et_la_Plume)

### Déductions
- [supposé] Les grilles des quotidiens (années 1960-1990) donnent souvent un intitulé court (« Le Masque et la Plume : cinéma »). Les magazines de programmes (Télérama) détaillent les œuvres discutées. Ces sources ne sont pas accessibles automatiquement (voir plus haut).

### Lacunes
- Aucun exemple daté de grille avec thème n'a été trouvé. Il faudrait des consultations manuelles : Télérama papier à la BnF, Inathèque.
