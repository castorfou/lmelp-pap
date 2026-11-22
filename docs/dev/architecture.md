# Architecture : de la collecte à la page publiée

Le projet produit deux livrables, qui partagent une même construction de la liste :

- **la liste publiée** : la page statique des émissions, générée par la CI à partir des CSV de `data/processed/` et publiée sur GitHub Pages ;
- **l'outil d'arbitrage** (`lmelp-pap arbitrer`) : un serveur local qui lève les doutes de la liste par des décisions humaines, enregistrées dans `arbitrages.csv`.

Les données de référence sont les CSV versionnés de `data/processed/` ; la page n'en est qu'une vue.

## Flux

```mermaid
flowchart TD
    subgraph Sources["Sources (en ligne)"]
        RF[radiofrance.fr]
        INA[catalogue INA]
        WB[Wayback Machine]
        AL[anciennes listes]
        LM[(lmelp · Mongo<br/>source vérifiée)]
    end

    Sources -->|"lmelp-pap emissions<br/>--source X --refresh"| Cache[(data/raw/cache<br/>non versionné)]

    Cache --> Construire{{"construire_liste<br/>rapprochement · arbitrages · doutes"}}
    Arb[(data/processed/<br/>arbitrages.csv)] --> Construire

    Construire --> CSV[(data/processed/<br/>emissions · attestations<br/>enregistrements · doutes .csv)]

    subgraph Appli["Outil d'arbitrage · lmelp-pap arbitrer (local)"]
        Page2[page en mode arbitrage]
        Humain([décision humaine<br/>thème · existence · date<br/>rapprochement · écoute])
        Page2 --> Humain
    end

    CSV --> Page2
    Humain -->|écrit| Arb
    Humain -.->|reconstruit aussitôt| Construire

    CSV -->|"commit + push main"| CI

    subgraph CI["CI · workflow docs.yml"]
        HTML["lmelp-pap page<br/>docs/emissions/index.html"]
        Site[mkdocs build]
        HTML --> Site
    end

    Site --> GH[[GitHub Pages<br/>liste publiée]]
```

## Étapes

**Collecte.** `lmelp-pap emissions` collecte chaque source dans `data/raw/cache/`. Une source dont la collecte est terminée est relue depuis le cache ; `--refresh` la collecte à nouveau. lmelp n'est accessible que depuis le devcontainer.

**Construction.** `construire_liste` (`src/lmelp_pap/liste.py`) rapproche les attestations des sources, applique les arbitrages de `arbitrages.csv`, fusionne chaque émission champ par champ et détecte ses doutes. `ecrire_liste` (`src/lmelp_pap/ecriture.py`) écrit les CSV liés par l'identifiant de l'émission. La commande `emissions` et l'outil d'arbitrage passent tous deux par cette construction.

**Arbitrage.** `lmelp-pap arbitrer` (`src/lmelp_pap/arbitrer.py`) sert la page de la liste avec ses contrôles d'arbitrage. Chaque décision s'ajoute à `arbitrages.csv` ; la liste est reconstruite depuis le cache, sans réseau, et ses CSV sont réécrits. Un arbitrage s'attache à une attestation, pas à l'identifiant d'une émission : il s'applique de nouveau à chaque construction, y compris après une nouvelle collecte.

**Maturité des enregistrements.** `src/lmelp_pap/maturite.py` tient, dans la collection Mongo `pap_enregistrements` (ADR 0004), un document par URL d'intégral : `_id` (l'URL), `emission_id`, `source`, `niveau` (`localise`, `telechargeable`, `rapatrie`, `qualifie`, `valide`), `entrees` (date d'entrée dans chaque niveau) et `verification` (date, résultat `ok`, `net` ou `passager`, détail). `classer` donne le verdict d'une requête `HEAD` ; `appliquer`, fonction pure, en déduit le nouveau niveau ; `verifier` interroge les URL de `enregistrements.csv` en parallèle et écrit par `Depot`. L'appli (`arbitrer.py`) lance la vérification dans un fil de fond et ajoute la maturité aux données de la page quand `MONGO_URI` est défini (`depot_depuis_env`). Les contrôles de maturité vivent dans `arbitrage.html` et s'accrochent à `page.html` par des fonctions facultatives (`passeMaturite`, `filtreMaturite`, `badgeMaturite`, `effacerMaturite`) : la page publiée n'en a rien. Les tests remplacent Mongo par mongomock et le réseau par une session factice.

La vérification part aussi seule : `verification_due` (fonction pure) décide entre une vérification complète (base vide, jamais faite, ou date de la dernière, gardée dans la collection `pap_etat`, plus vieille que l'intervalle), une vérification des seules URL nouvelles, ou rien. `Atelier.planifier` l'applique ; `planifier_en_continu` l'appelle toutes les heures dans un fil de fond (activé par la CLI, éteint par défaut dans `creer_serveur`), et chaque reconstruction de la liste aussi. Les logs passent par le module `logging` : chaque module écrit dans son logger (`logging.getLogger(__name__)`, sous `lmelp_pap`), et `logs.configurer()` (`src/lmelp_pap/logs.py`, appelé par la CLI et par `tests/conftest.py`) dirige ce logger vers la sortie d'erreur, au format `horodatage niveau module : message`. Le gestionnaire relit `sys.stderr` à chaque ligne, ce qui suit les captures de pytest (`capfd`). Le serveur journalise ses requêtes dans le logger `lmelp_pap.http` (`log_request`, sauf les couples `SILENCIEUSES` : `/health` et les sondages d'avancement) ; `_sans_panne` enveloppe `do_GET` et `do_POST` : une exception imprévue va aux logs avec sa trace (`log.exception`) et donne une 500 JSON tant que la réponse n'est pas partie.

**Accueil.** `GET /` sert `src/lmelp_pap/accueil.html`, page autonome qui lit `GET /api/donnees` (avec `maturite` et `maturite_depuis`) et calcule l'état de chaque émission (`lmelp` si lmelp l'atteste ou si `dans_lmelp`, sinon la maturité, sinon `sans`). Accueil et pages d'état vivent dans le même document ; l'état ouvert et l'année filtrée sont dans l'adresse (`#etat=…&annee=…`). Le registre `ACTIONS` (état → `{libelle, lot, executer}`, et `confirmer` facultatif) est le point d'accroche des actions : la colonne Action et le bouton de lot n'apparaissent que pour un état qui en a une. La liste en mode arbitrage est servie sur `GET /liste`.

**Favicon.** Les icônes de pap (`src/lmelp_pap/icones/` : `favicon.ico` en 16, 32 et 48 px, `favicon-32x32.png`, `apple-touch-icon.png` en 180 px) suivent l'identité de la famille lmelp : le masque doré et la plume blanche de l'icône historique, plus une marque propre derrière la plume sur un fond propre (back-office : base de données sur fond vert ; lmelp-mobile : smartphone sur fond bleu nuit ; pap : bobine de bande magnétique sur fond sépia). `scripts/generer_favicon.py` les produit à partir de `scripts/icone/source_lmelp_green.png` (`uv run scripts/generer_favicon.py`, dépendances déclarées dans le script). Le serveur les sert à la racine (`ICONES` dans `arbitrer.py`) et `accueil.html` les déclare (`<link rel="icon">`, `apple-touch-icon`). `page.html` embarque `favicon-32x32.png` en data URI (`__FAVICON__`, remplacé par `construire_page`) : la page publiée sur GitHub Pages et la page ouverte hors ligne ont leur icône sans serveur.

**Rapatriement.** `rapatrier` (`src/lmelp_pap/maturite.py`) télécharge en flux l'intégral retenu (`retenu` : m4a, puis mp3) vers `<année>/<nom>.part`, calcule SHA-256 et taille, renomme à la fin, et rend l'enregistrement rapatrié (`fichier`, `sha256`, `taille`). Il retente les `requests.RequestException` (`ESSAIS`, `PAUSES`), pas les statuts HTTP, et accepte deux rappels : `progres(reçus, total)` et `arreter()`. Côté serveur, `Tache` (`arbitrer.py`) porte les tâches de fond (vérification des URL, rapatriement) : avancement, bilan, arrêt, une tâche à la fois. Un échec est mémorisé sur l'enregistrement (`echec`) et ressort dans `/api/donnees` (`echec_rapatriement`). Dans l'accueil, le panneau flottant suit `GET /api/rapatriements` par sondage d'une seconde ; il ne dépend d'aucun état du navigateur sauf la fermeture du bilan (`localStorage`).

**Écoute et qualification.** `qualifier(enregistrement, verdict, motif, maintenant)` (`src/lmelp_pap/maturite.py`, fonction pure) n'accepte qu'un enregistrement `rapatrie` et rend l'enregistrement et sa `Qualification` (`enregistrement` : l'URL, `emission_id`, `verdict` `favorable` ou `ecarte`, `motif`, `date`) : favorable, il passe à `qualifie` (`entrees["qualifie"]`) et perd son écart ; écarté (motif obligatoire, sinon `QualificationError`), il reste `rapatrie` avec `ecart` (la qualification). `Depot.ajouter_qualification` / `qualifications()` tiennent la collection `pap_qualifications`, un document par qualification ; `ecrire_qualifications` réécrit `qualifications.csv` dans le dossier de sortie à chaque qualification. `Atelier.qualifier` (`arbitrer.py`) choisit l'enregistrement rapatrié de l'émission, applique, conserve, exporte et journalise ; `POST /api/qualifications` la sert (400, 503). `/api/donnees` donne par émission `fichier_audio` et `ecart` (de l'enregistrement le plus avancé). `GET /audios/<fichier>` sert le dossier audio (module `src/lmelp_pap/audio.py`) : `fichier_audio` résout le chemin décodé et refuse tout ce qui sort du dossier ou n'est pas un fichier (404), `plage` lit l'en-tête `Range` (`bytes=a-b`, `a-`, `-n` ; 206, ou 416 hors du fichier ; une plage illisible ou multiple sert le fichier entier), et `servir` envoie le corps par morceaux de `MORCEAU` octets. Dans l'accueil, `ACTIONS.rapatrie` (sans lot) ouvre une ligne `tr.ecoute` sous l'émission (`vue.ecoute`) avec le `<audio>`, les sauts ±30 s, « Favorable », le motif et « Écarter » ; la réponse de `POST /api/qualifications` remplace les données, puis `notifier` donne les compteurs changés.

**Open API Radio France.** `lire_diffusion(jour, pages, jeton, session)` (`src/lmelp_pap/radiofrance_api.py`) est le seul client de l'API GraphQL (`POST https://openapi.radiofrance.fr/v1/graphql`, en-tête `x-token`). L'API n'a pas de requête par identifiant : le client lit `diffusions(station: FRANCEINTER, start, end, first: 100)` sur le jour de l'émission (minuit à 23:59:59, heure de Paris), page suivante par `after` (curseur du dernier bord) tant qu'une page est pleine, trois pages au plus. L'API rend ses URL sous `https://www.franceinter.fr/…`, pap connaît les pages sous `https://www.radiofrance.fr/…` : seuls les chemins se comparent. Le client retient la diffusion dont l'`url` a le chemin d'une des `pages` radiofrance.fr de l'émission (`Emission.pages_radiofrance` : ses attestations `radiofrance` qui ne sont pas des extraits), sinon la première du Masque (chemin de `show.url` égal à `/franceinter/podcasts/le-masque-et-la-plume`, ou chemin de `url` en dessous), sinon `None`. Il rend une `Diffusion` (`titre`, `resume` : `standFirst`, `url`, `animateurs` : `producer`, `equipe` : `staff`, `invites` : `guest`, chacun une `Personnalite` `nom`, `role` : `info`) ; les `tag` sont ignorés. Toute erreur (réseau, HTTP ≠ 200, `errors` GraphQL, JSON illisible) lève `ApiRadioFranceError`, dont le message ne dit que la nature (`HTTP 403`, `Timeout`, `erreur GraphQL`), jamais le contenu reçu. Les CGU (art. 5.3) interdisent de stocker les données : rien n'en est écrit sur disque, en base ni dans les logs. `LecteurDiffusions(session, duree=3600)` garde, pour ménager le quota de 1 000 requêtes par jour, la diffusion lue pour une émission (ou son absence) dans la mémoire du processus seulement, une heure au plus ; une erreur n'est pas gardée. `lire(cle, jour, pages, jeton)` rend une `Lecture` : `diffusion`, `cache` (vrai si elle vient du cache), `requetes` (requêtes HTTP de cette lecture) et `du_jour` (compteur des requêtes de la journée, heure de Paris, en mémoire, remis à zéro au changement de jour ; `QUOTA` = 1 000). Les requêtes se comptent par une session enveloppe (`_SessionComptee`) ; une `ApiRadioFranceError` levée par le lecteur porte aussi `requetes` et `du_jour`. `jeton()` est le seul lecteur de `RADIOFRANCE_API_TOKEN`.

**Écoute : page radiofrance.fr et diffusion de l'API.** `Atelier.diffusion_radiofrance(emission_id)` passe par `Atelier._diffusion(emission, contexte)`, que la mise à disposition partage : clé lue au moment de l'appel (`jeton()`), lecture par le `LecteurDiffusions` de l'atelier hors du verrou, et ligne de log de l'appel (`api radiofrance <id>[ (mise à disposition)] : trouvée|introuvable|erreur <nature>, <n> requête(s) (<du jour>/1000 aujourd'hui), <durée>`, `trouvée (cache), 0 requête (…)`, `pas de clé` ou `émission inconnue`). `GET /api/radiofrance/<emission_id>` la sert : `{emission_id, statut, diffusion, detail?}`, `statut` valant `trouvee`, `introuvable`, `sans_cle` ou `erreur` (toujours 200), 404 pour une émission inconnue. Dans l'accueil, `preparer` garde pour chaque émission ses `pages` (attestations `radiofrance` avec `url`) ; le lecteur `tr.ecoute` affiche un lien `target="_blank"` par page et un bloc `.radiofrance .api` que `chargerDiffusion` remplit par `GET /api/radiofrance/<id>` à la première ouverture. La réponse est gardée dans `DIFFUSIONS`, en mémoire de la page seulement, pour ne pas rappeler l'API à chaque rendu.

**Mise à disposition de lmelp.** `mettre_a_disposition(enregistrement, emission, audios, audios_lmelp, maintenant, api)` (`src/lmelp_pap/remise.py`, `api` : la `Diffusion` de l'API ou `None`) n'accepte qu'un enregistrement `qualifie` dont le fichier existe ; un fichier de même chemin dans `audios_lmelp` lève `RemiseError` avant toute écriture, sauf s'il a l'empreinte SHA-256 de l'enregistrement : c'est une mise à disposition interrompue après la copie, qui se termine sans recopier (`reprise`). La copie passe par `<nom>.part` (ouvert en création exclusive), vérifie l'empreinte SHA-256 du rapatriement, puis renomme ; en cas d'échec, ni `.part` ni dossier d'année créé pour l'occasion ne restent. La fonction rend une `Remise` : l'enregistrement `valide` (`entrees["valide"]`), la fiche `pap_remises` (contrat ci-dessous) et `reprise`. `duree_du_fichier` lit la durée d'un m4a dans sa boîte `moov/mvhd`, sans dépendance. La description prend dans la `Diffusion` l'animateur (`animateurs`), le résumé (`resume`), l'équipe (`equipe`, par les noms) et les invités (`invites`, chaque nom suivi de son rôle, comme dans le flux RSS). `Atelier.mettre_a_disposition` (`arbitrer.py`) traite les émissions une par une sous un verrou propre : garde-fou « déjà dans lmelp », choix de l'enregistrement qualifié, diffusion lue par `Atelier._diffusion` (cache partagé avec l'écoute ; sans clé ou en erreur, `None`), écriture de la fiche (`Depot.ajouter_remise`) puis de l'enregistrement, ligne de log de chaque mise à disposition, refus et bilan ; `POST /api/remises` la sert (400, 503) et renvoie les données avec `remise` (`mises`, `refus`). `Depot.dans_lmelp(fichiers)` cherche ces fichiers dans la collection `episodes` de lmelp (`audio_rel_filename`). `Maturites(depot)` (`arbitrer.py`) lit une fois par requête les enregistrements par émission et les fichiers valides présents dans `episodes` ; sa méthode `dans_lmelp(emission)` (attestation lmelp, ou enregistrement valide dont le fichier est dans `episodes`) sert à la fois `/api/donnees` et le garde-fou de la mise à disposition. Dans l'accueil, `ACTIONS.qualifie` (lot, `confirmer`) appelle `POST /api/remises` ; une action qui a `confirmer` pose sa question par ligne, par sélection et pour tout. Les refus vivent dans `vue.refus` et s'affichent en tête de page (`.alerte.refus`) jusqu'à fermeture ; `etatDe` classe « lmelp » une émission `dans_lmelp`.

**Publication.** Elle suit les CSV : un push sur `main` qui modifie `data/processed/` (ou `docs/`, `src/`) déclenche la workflow `docs.yml`. Elle lance `lmelp-pap page` (`src/lmelp_pap/page.py`), qui génère `docs/emissions/index.html`, une page autonome embarquant les données en JSON, puis construit la documentation MkDocs et la déploie sur GitHub Pages. La page générée n'est pas versionnée (`.gitignore`) ; en local, `lmelp-pap page` sert seulement à la prévisualiser avec `mkdocs serve`.

Cycle type après une séance d'arbitrage ou une nouvelle collecte :

```bash
uv run --active lmelp-pap emissions --source lmelp --refresh   # ou arbitrer
git diff --stat data/processed
git add data/processed && git commit -m "docs(liste): mettre la liste à jour"
git push   # sur main, ou via une PR : la CI régénère et publie la page
```

Le détail des commandes, des fichiers produits et des règles de construction est dans la documentation utilisateur, [Liste des émissions](../user/liste-des-emissions.md).

## Contrat `pap_remises`

La collection `pap_remises`, dans la base `masque_et_la_plume`, est écrite par pap à chaque mise à disposition et lue par back-office-lmelp. Le back-office n'y écrit rien. Une fiche par enregistrement mis à disposition ; une fiche ne se retire pas. Chaque fiche est prête à devenir un document `episodes` de lmelp.

| Champ | Type | Contenu |
|---|---|---|
| `_id` | chaîne | Identifiant de l'enregistrement dans pap : son URL (celle de `pap_enregistrements`). |
| `emission_id` | chaîne | L'émission dans la liste pap : sa date de première diffusion, `AAAA-MM-JJ`. |
| `titre` | chaîne | « Le Masque et la Plume du 28 septembre 2014 » (« 1er » pour le premier du mois). |
| `date` | date | Date de première diffusion, à 00:00 UTC. |
| `type` | chaîne | `livres`. |
| `duree` | entier ou `null` | Durée en secondes : lue dans le fichier (m4a), sinon donnée par la page radiofrance.fr ou la notice INA. |
| `description` | chaîne | Au format des descriptions du flux RSS du Masque (`rss_14007.xml`), morceaux absents omis : `durée : HH:MM:SS  - Le Masque et la Plume - par : <animateur> - <résumé> - équipe : <noms> - invités : <nom> <rôle>, …`. Comme dans le flux, deux espaces suivent la durée et chaque invité est suivi de son rôle quand l'API le donne (« Arnaud Viviant Critique littéraire (Revue Regards) ») ; l'équipe n'a que les noms. Le renvoi « Vous aimez ce podcast ? … » du flux n'est pas repris. |
| `sources_description` | objet | La source de chaque morceau présent de la description : clés `duree`, `animateur`, `resume`, `equipe`, `invites` ; valeurs `fichier`, `radiofrance` (page radiofrance.fr), `api_radiofrance`, `ina`, `deduit` (animateur déduit de la date). |
| `episode_page_url` | chaîne ou `null` | Page radiofrance.fr de l'émission, si une fiche radiofrance l'atteste. |
| `url` | chaîne ou `null` | URL d'origine du fichier audio, si l'enregistrement en a une. |
| `audio_rel_filename` | chaîne | Chemin du fichier, relatif au dossier audio du back-office : `<année>/<nom>`, le nom d'origine du fichier. C'est par ce champ que pap reconnaît l'entrée de l'émission dans lmelp (collection `episodes`). |
| `sha256` | chaîne | Empreinte SHA-256 (hexadécimale) du fichier copié. |
| `date_remise` | date | Date et heure de la mise à disposition (UTC). |

Les morceaux venus de l'API Radio France ne figurent que dans `description` ; ils ne sont ni conservés ailleurs dans pap, ni publiés sur la page publique.

Le fichier est copié, avant l'écriture de la fiche, dans `<dossier audio du back-office>/<audio_rel_filename>` ; pap n'écrase jamais un fichier existant. Un fichier déjà présent avec la même empreinte SHA-256 (mise à disposition interrompue après la copie) termine la mise à disposition : la fiche est écrite sans recopie.
