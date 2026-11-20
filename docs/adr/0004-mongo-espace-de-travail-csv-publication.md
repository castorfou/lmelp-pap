# Mongo est l'espace de travail de l'appli pap, les CSV versionnés en sont la publication

L'appli pap tourne sur le NAS, dans docker-lmelp. Le travail humain qu'on ne peut pas recalculer (arbitrages, qualifications des enregistrements, métadonnées saisies après écoute, maturité des enregistrements) y vit dans Mongo, qui fait foi. La liste des émissions reste calculée à chaque construction, à partir du cache des sources et de ces décisions. À la publication, l'appli exporte décisions et liste en CSV versionnés (`arbitrages.csv`, `qualifications.csv`, émissions, attestations, enregistrements) : l'ADR 0001 tient pour ce qui est publié, et git sert de seconde sauvegarde du travail humain.

Les collections de pap vivent dans la base de lmelp (`masque_et_la_plume`), préfixées `pap_`. Une seule base simplifie l'exploitation : la sauvegarde existante (`mongodump --db=masque_et_la_plume`) les couvre sans changement. Le préfixe garde les collections de pap indépendantes de celles de lmelp : pap n'écrit que dans les siennes, et le projet peut être repris seul avec elles.

Le cache des sources (pages radiofrance.fr, notices INA, index Wayback, environ 900 Mo) reste en fichiers dans `/volume1/docker/lmelp/pap/cache/`, ni dans Mongo ni dans git, et suit la sauvegarde des fichiers du NAS.

## Considered Options

- **Tout en CSV versionnés, comme aujourd'hui** : une appli web sur le NAS, utilisée au fil de l'eau, réécrirait des fichiers d'un dépôt git ; l'état intermédiaire (rapatrié, qualifié) n'a pas sa place dans l'historique.
- **Tout dans Mongo, sans CSV** : perd les diffs git lisibles de l'ADR 0001 et la publication de la liste sur GitHub Pages.
- **Une base `lmelp_pap` séparée** : propriétaires distincts, mais une sauvegarde à adapter et deux bases à exploiter.

## Consequences

Une décision prise sur le NAS n'est dans git qu'après une publication : entre deux publications, Mongo (et sa sauvegarde) est la seule copie. Le devcontainer travaille sur une copie, ou pointe ponctuellement vers le Mongo du NAS ; seul le NAS publie.
