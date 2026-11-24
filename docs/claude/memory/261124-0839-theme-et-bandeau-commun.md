# Thème clair/sombre et bandeau commun accueil / liste (#111)

## Ce qui a été fait

### Thème
- Les deux pages de l'appli (`src/lmelp_pap/accueil.html`, `src/lmelp_pap/page.html`)
  avaient déjà le CSS : variables sur `:root`, redéfinies sous
  `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` puis sous
  `:root[data-theme="dark"]`. Il manquait seulement de quoi poser `data-theme`.
- Script inline du `<head>`, **identique** dans les deux pages (test
  `tests/test_page.py` qui compare les deux) : lit `localStorage["pap.theme"]`
  (`light`/`dark`, toute autre valeur = auto) et pose l'attribut avant le rendu
  (pas de clignotement). `try/catch` : sans stockage, auto.
- Interrupteur `#interrupteur-theme` (script en fin de `<body>`) : auto ◐ → clair ☀ →
  sombre ☾ → auto. En auto la clé est supprimée. `title` = `aria-label` =
  « Thème clair. Cliquer pour passer en sombre. » Écoute `storage` pour l'autre onglet.
- **Piège** : `page.html` a déjà un `<select id="theme">` (filtre des thèmes
  d'émission). D'où l'id `interrupteur-theme`. Le CSS de l'en-tête éditorial est
  restreint à `header .tete .theme` pour ne pas fuir sur le bouton du bandeau.
- Contraste en sombre sur l'accueil : `--qualifie` (lien, 3,1:1 sur `--carte`) et
  `--lmelp` éclaircis dans les deux blocs sombres (`#5b93d6`, `#58a855`). Test WCAG
  ≥ 4,5 sur toutes les couleurs d'état dans `tests/test_theme_navigateur.py`.
- Choix de duplication : pas de fichier JS partagé, car `page.html` doit rester
  autonome en `file://` (page publiée sur GitHub Pages).

### Bandeau commun
- Même `header.app` sur `/` et `/liste` : logo « pap », sous-titre, `nav` des onglets
  « Accueil » / « Liste et arbitrages » (`aria-current="page"` sur la page courante),
  sur l'accueil le groupe `.actions` (« Collecte », puis « Publier » que le script y
  ajoute) séparé par un trait vertical (décision utilisateur : ce sont des actions de
  l'accueil, pas des onglets), et l'interrupteur de thème toujours dernier.
- Côté liste, le bandeau est inséré par `src/lmelp_pap/arbitrage.html` (donc absent de
  la page publiée) avec son CSS recopié (`--entete*`, police système, `body{margin:0}`
  et marges négatives pour la pleine largeur). Le bouton thème de l'en-tête éditorial
  y est déplacé (`append`), ses écouteurs suivent. Le lien « ← Accueil » de la section
  arbitrage a disparu.
- Sur l'accueil, « pap » et l'onglet « Accueil » remettent la vue à zéro sans recharger.
- `tests/test_bandeau_navigateur.py` compare les deux bandeaux (onglets, couleur,
  police, position, taille) : il signale toute divergence entre les deux copies.

## Tests Playwright utiles
- Servir plusieurs pages sur la même origine via `context.route` pour tester
  `localStorage` partagé et l'évènement `storage` entre onglets.
- `context.add_init_script` pour pré-remplir `localStorage`, ou le rendre inutilisable
  (`Object.defineProperty(window, "localStorage", {get() { throw … }})`).
- Thème au premier rendu : `MutationObserver` en init script qui relève
  `dataset.theme` dès que `document.body` existe.
- `page.emulate_media(color_scheme=…)` pour simuler un changement du système.

## Logs
Rien côté serveur : fonctionnalité 100 % navigateur, choix assumé dans l'issue.
