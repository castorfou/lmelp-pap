# Vérification automatique des URL d'intégral, et premiers logs utiles (#97)

Issue ajoutée au jalon MVP après une question de l'utilisateur : sur le NAS, base Mongo neuve, l'accueil restait sans téléchargeable tant que personne ne cliquait « Vérifier les URL des intégraux » sur `/liste`.

## Ce qui est livré

- **`src/lmelp_pap/maturite.py`** :
  - `verification_due(a_verifier, connues, derniere, maintenant, intervalle)` (pure) : complète si base vide, jamais vérifiée ou dernière vérification complète plus vieille que l'intervalle ; « nouvelles » pour les URL d'intégral absentes de `pap_enregistrements` ; sinon rien ;
  - `Depot.derniere_verification()` / `noter_verification(date)` : collection `pap_etat`, document `{_id: "verification", derniere}` ;
  - `rapatrier(..., relance=)` : rappel avant chaque nouvel essai (pour les logs).
- **`src/lmelp_pap/arbitrer.py`** :
  - `journal(message)` : une ligne horodatée sur stderr, en un seul `write` (sinon les lignes de deux fils se mêlent) ; c'est la base des logs tant que #91 n'a pas posé `logging` ;
  - `lancer_verification(a_verifier=None, origine="manuelle")` : complète (note la date à la fin) ou partielle ; trace le lancement et la fin (durée, ok, mortes, échecs passagers) ;
  - `planifier()` : lance la vérification due, jamais deux à la fois ; raison tracée (« jamais vérifiée », « base vide », « dernière le JJ/MM/AAAA à HH:MM », « nouvelles URL ») ; appelée par `planifier_en_continu()` (fil horaire, `PLANIFICATION = 3600`, exceptions imprimées dans les logs) et après chaque reconstruction de la liste (`_apres_reconstruction`) ;
  - `/api/verifications` porte `derniere` et `prochaine` ; `serveur.atelier` est exposé ;
  - rapatriement tracé : début du lot, chaque fichier (chemin, Mo, durée), chaque nouvel essai, chaque échec, l'arrêt, le bilan avec la durée.
- **CLI** : planification active ; `--verification-jours` / `PAP_VERIFICATION_JOURS` (défaut 7). `creer_serveur` la laisse éteinte par défaut, pour que les tests gardent la main.
- **`/liste`** (`arbitrage.html`) : « dernière vérification le … · prochaine le … » à côté du bouton.

## Préférence de l'utilisateur

L'utilisateur veut des **logs utiles** dans l'appli : c'est désormais un critère d'acceptation permanent (mémoire Claude « logs-utiles-critere »). Chaque fonctionnalité prévoit et teste ses lignes de log.

## Leçons de test

- La vérification automatique part dès le démarrage du serveur, donc pendant la mise en place de la fixture : pytest range cette sortie à part et `capfd` peut la manquer. Tester les logs en déclenchant l'action dans le corps du test (`capfd.readouterr()` pour oublier le démarrage, puis `atelier.planifier()`).
- Attendre une tâche lancée par un fil de fond : attendre que `bilan` existe, pas seulement « pas en cours » (le fil peut ne pas avoir démarré).
- Vérifier la stabilité d'un test de concurrence en le lançant plusieurs fois.
