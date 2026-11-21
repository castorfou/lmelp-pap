# Rapatriement d'un intégral sur le NAS, et son suivi (#68)

Troisième brique du jalon « MVP : premier enregistrement valide » (carte #48). Deux tours : le rapatriement, puis, après l'essai de l'utilisateur, les tentatives, la progression, l'arrêt et les échecs visibles.

## Ce qui est livré

- **`src/lmelp_pap/maturite.py`** :
  - `retenu(enregistrements)` : l'intégral à rapatrier parmi les téléchargeables d'une émission (m4a, puis mp3, puis le reste) ;
  - `rapatrier(enregistrement, dossier, session, maintenant, progres, arreter, attendre)` : fichier `<année>/<nom d'origine>` dans le dossier audio, via `<nom>.part` renommé (`os.replace`) à la fin ; SHA-256 et taille au fil du flux ; un fichier déjà là à la bonne empreinte n'est pas retéléchargé ; jusqu'à `ESSAIS = 3` essais sur échec passager (`requests.RequestException`, pauses `PAUSES = (5, 15)` s), aucun sur un statut ≠ 200 (`RapatriementError`) ; `progres(reçus, total)` (total = `Content-Length`) ; `arreter()` vrai → `RapatriementInterrompuError` ; tout échec supprime le `.part` (et le dossier de l'année s'il reste vide) ;
  - `Enregistrement` gagne `fichier`, `sha256`, `taille` et `echec` (dernier échec de rapatriement, `Verification`, effacé au succès).
- **`src/lmelp_pap/arbitrer.py`** :
  - `Tache` : tâche de fond générique (avancement, bilan, `arreter()` / `arret_demande()`, `refuser` → `TacheEnCoursError`), utilisée par la vérification des URL et par le rapatriement ;
  - `POST /api/rapatriements` `{"emissions": [...]}` (400 sans intégral téléchargeable ou liste vide, 409 si un lot tourne, 503 sans Mongo), `GET /api/rapatriements` (`faites`, `total`, `en_cours_sur`, `octets`, `fichier_octets`, `fichier_total`, `debut`, `arrete`, `bilan` `{rapatries, deja_la, echecs}`, `erreurs`), `POST /api/rapatriements/arret` ;
  - un échec mémorise `echec` sur l'enregistrement ; `/api/donnees` donne `echec_rapatriement` par émission.
- **CLI / image** : `--audios` / `PAP_AUDIOS` (local `data/raw/audios`, ignoré par git ; image `/data/audios`, soit `pap/audios/` sur le NAS).
- **`src/lmelp_pap/accueil.html`** :
  - `ACTIONS.telechargeable` : « Télécharger » par ligne, cases, « sélection (N) », « tout (N) » avec confirmation ; la sélection se vide au lancement ;
  - **panneau flottant en haut à droite, façon DSM** (demande explicite de l'utilisateur, après un premier bandeau pleine largeur) : suit `GET /api/rapatriements` chaque seconde, retrouvé après un rechargement ; replié : titre et barre globale ; déplié : Mo reçus, temps restant, fichier en cours (%, Mo/s), erreurs ; Arrêter pendant le lot ; à la fin, bilan jusqu'à ✕ (mémorisé par lot, `localStorage`) ; notifications (`#toast`) déplacées en bas à droite ;
  - l'échec d'une émission s'affiche en rouge sous son titre ;
  - « pap » en haut à gauche ramène à l'accueil.

## Mesures réelles (local, 21/11/2026)

Un intégral pèse 70 à 90 Mo (≈ 11 Go pour les 160 téléchargeables), débit 5 Mo/s environ. Un `Read timed out` observé sur 1980-02-24 était passager (le fichier est passé en 16 s juste après) : d'où les tentatives.

## Correctif de production découvert en chemin (PR #94)

`accueil.html` (#89) manquait au paquet installé (`package-data` listait les HTML un à un) : `/` levait `FileNotFoundError` dans l'image, pas en local (paquet éditable). Correctif : `lmelp_pap = ["*.html"]` et `tests/test_paquet.py`. Prévention plus large : issue #95, test de fumée de l'image Docker dans la CI avant publication.

## Leçons

- Un test navigateur qui attend un élément déjà présent au chargement (`#bandeau` alors que l'API simulée dit « en cours ») passe avant l'effet du clic : attendre le résultat attendu (`get_by_role(...).wait_for(timeout=...)`), et vérifier que le test échoue sans le correctif.
- Les tests qui provoquent des échecs passagers doivent passer `attendre=` une pause nulle, sinon les vraies pauses (5 + 15 s) ralentissent la suite.
