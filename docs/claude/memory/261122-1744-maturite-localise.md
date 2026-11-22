# Maturité des enregistrements : niveau localisé (#86)

Branche `86-maturité-des-enregistrements-niveau-localisé`. Elle s'appuie sur la collection `pap_enregistrements` (#67) et sur la décision « deux maturités » (#84). Les écrans détaillés de « sans enregistrement » et de « localisé » (journal des échanges, sorties URL et fichier) relèvent de #87.

## Critère Archives Radio Pro / Dépôt légal

- L'identifiant de la notice INA suffit, sans fiche : `PH_…` = Archives Radio Pro (demandable à INA mediapro), `RD_…` = Dépôt légal radio (InaTHÈQUE, consultation sur place seulement), `DA_…` = Archives TV Pro (rien dans la liste).
- Vérification : le champ `BASE` (`<td id="BASE">`) des 3621 fiches de `data/raw/cache/ina/fiches` correspond au préfixe sans exception. Le champ `FONDS` (INA, INA - Radio France, Club d'Essai…) ne départage pas les deux fonds.
- Code : `archives_radio_pro()` dans `src/lmelp_pap/sources/ina.py`.

## Ce qui est livré

- **`src/lmelp_pap/maturite.py`**
  - `Enregistrement.note` (persistée dans Mongo sous `note`).
  - `url` (`_id`) identifie l'enregistrement : URL audio pour radiofrance, URL de la notice pour l'INA, `piste:<uuid4 hex>` pour une saisie manuelle. Seules les URL de `integraux()` se vérifient et se rapatrient, donc les notices et les pistes n'entrent jamais dans la vérification HEAD.
  - `localisations_ina(emissions, maintenant)` (pure) : un enregistrement par notice PH_ (choix de l'utilisateur, plutôt qu'un par émission), pour les émissions sans `liste.Enregistrement` de type `intégral`.
  - `Depot.ajouter_absents()` : `update_one(..., {"$setOnInsert": doc}, upsert=True)`, compte les `upserted_id`. Il n'écrase ni une piste ni un niveau plus avancé ; une relance crée 0.
  - `piste(emission_id, source, note, maintenant)` : source libre obligatoire (`PisteError`), note facultative (`None` si vide).
- **`src/lmelp_pap/arbitrer.py`**
  - `Atelier.localiser_ina()` est appelée automatiquement (choix de l'utilisateur) dans la boucle `planifier_en_continu` (démarrage, puis toutes les heures) et dans `_apres_reconstruction`, seulement en mode planification. Log : `localisation INA : N enregistrements localisés créés (M notices des Archives Radio Pro)`, seulement s'il y a des créations.
  - `Atelier.ajouter_localise()` sert `POST /api/localisations` (`emission_id`, `source`, `note`) : 400 pour une émission inconnue ou une source vide, 503 sans Mongo. Log : `enregistrement localisé ajouté : <id> (source « … »)`.
  - `/api/donnees` : chaque émission porte `localisations` (`source`, `note`, `notice`, `depuis`), triées par date d'entrée (helper `_localisations`).
- **`src/lmelp_pap/accueil.html`**
  - `ACTIONS.sans` : « Ajouter un enregistrement localisé » ouvre la `<dialog>` `#boite` (`saisirPiste`) avec les champs Source et Note. Le bouton Ajouter reste désactivé sans source, et une erreur s'affiche dans la boîte.
  - Page « localisé » : la colonne « Sources » (en-tête inchangé, un test le vérifie) liste les détenteurs (`detenteurs` : lien vers la notice INA, ou source libre, plus la note). « Depuis » affiche la date d'entrée au survol (`title`).

## Mesures réelles (22/11/2026)

- 273 enregistrements créés, pour 267 émissions de 1956 à 1993. Aucune émission 2000-2014 n'est localisée ; la relance crée 0.
- Accueil sur le Mongo local : localisé 267, sans enregistrement 169, téléchargeable 333.

## Leçons

- Tests serveur : `_demarrer` range l'atelier dans `ATELIERS[adresse]` (`tests/test_arbitrer_maturite.py`) pour appeler ses méthodes directement.
- La fixture `tests/fixtures/ina/notices.csv` n'a que des notices PH_ : le cas RD_ est couvert par les tests unitaires (`tests/test_maturite.py`).
- `scripts/start-dev.sh --restart` reste au premier plan : le lancer en tâche de fond, puis interroger `--status`.
