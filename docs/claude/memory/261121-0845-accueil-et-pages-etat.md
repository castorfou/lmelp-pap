# Accueil et pages d'état de l'appli pap (#89)

Deuxième brique du jalon « MVP : premier enregistrement valide » (carte #48), réécriture propre de la variante B du prototype validé (`prototype/85-accueil`). Validée par l'utilisateur à l'essai (« c'est trop bien »).

## Ce qui est livré

- **Routes** (`src/lmelp_pap/arbitrer.py`) : `GET /` sert `src/lmelp_pap/accueil.html` (ressource du paquet, page autonome) ; la liste en mode arbitrage passe sur `GET /liste` ; `/health` et l'API ne changent pas.
- **`/api/donnees`** : avec un dépôt Mongo, chaque émission porte `maturite` et `maturite_depuis` (date d'entrée dans le niveau de son meilleur enregistrement). `meilleur()` dans `src/lmelp_pap/maturite.py`.
- **`accueil.html`** (tout en JS, données de `/api/donnees`) :
  - état d'une émission : `lmelp` si lmelp l'atteste, sinon sa maturité, sinon `sans` ;
  - haut fixe : histogramme SVG empilé par état (colonnes `rect.zone[data-annee]` pour le survol et le clic), légende, 7 compteurs `.compteur[data-etat]` sans mention de rôle ;
  - `#frise` : son propre ascenseur (hauteur recalculée au redimensionnement), blocs `.annee[data-annee]` ; survol d'une année → `frise.scrollTop = bloc.offsetTop` ;
  - clic sur une année : filtre tout (compteurs, frise, page d'état) ; « 1987 × » (`#effacer-annee`) ;
  - page d'état dans le même document, adresse `#etat=…&annee=…` (rechargeable) ; colonnes triables ; « dans lmelp » : Date, Titre, Thèmes ;
  - registre `ACTIONS` vide : la colonne Action et le bouton de lot n'apparaissent que pour un état qui a une action (à remplir par #68, #69, #81) ; `notifier(message, avant)` prêt pour les toasts « rapatrié 12→15 » ;
  - thème clair (prototype) et sombre (`prefers-color-scheme`, `data-theme`), mêmes couleurs d'états ;
  - sans Mongo : bandeau « Maturité indisponible ».
- **`/liste`** : lien « ← Accueil » ajouté par `src/lmelp_pap/arbitrage.html` (absent de la page publiée).

## Tests

`tests/test_accueil_navigateur.py` (Playwright, données simulées, 1280×1000) : compteurs, absence de rôles, frise qui défile seule, survol, clic d'année, page d'état filtrée, tri dans les deux sens (ancienneté comparée en nombre), colonnes de « dans lmelp », pas de colonne Action, retour, thème sombre. Captures comparées au prototype : fidèles, écarts voulus (localisé à 0 tant que #86 n'existe pas, pas de boutons d'action).

## Découvert en chemin

- **NAS sans maturité** : l'image à jour tourne, mais le service `pap` de docker-lmelp ne passe pas `MONGO_URI` / `MONGO_DB` (503 « MONGO_URI absent »). Issue [docker-lmelp#97](https://github.com/castorfou/docker-lmelp/issues/97) ; après le changement du compose : `docker compose up -d pap` (Watchtower ne change que l'image). Leçon : quand l'image demande une nouvelle variable, ouvrir l'issue dans docker-lmelp en même temps.
- Issues ouvertes pendant le travail : logs du conteneur (#91 : logs presque vides, URL `localhost:8090` fausse dans le conteneur), favicon dans l'identité lmelp (#92).
