# Liste des émissions en CSV liés, identifiés par la date de première diffusion

La liste des émissions est livrée sous forme de plusieurs CSV versionnés dans `data/processed/` : émissions, enregistrements, attestations. Ils sont reliés par un identifiant d'émission égal à sa date de première diffusion (`1967-01-01`), suivie d'un suffixe en cas de collision (`1957-10-24-b`). Plusieurs CSV plutôt qu'un seul, parce qu'une émission a plusieurs thèmes, sources et enregistrements, et que les livres et les critiques viendront s'y rattacher. Des CSV plutôt que SQLite, pour garder des diffs git lisibles qui montrent ce que chaque source apporte. La date plutôt qu'un identifiant arbitraire, pour un identifiant stable d'une génération à l'autre et lisible par un humain, sans registre d'identifiants à maintenir.

## Considered Options

- **Un seul CSV avec des cellules à valeurs multiples** : simple, mais les enregistrements (URL, type, format) y deviennent illisibles, et ce format ne s'étend pas aux livres et aux critiques.
- **SQLite** : pratique pour les requêtes, mais le diff git est illisible. On pourra le générer à partir des CSV si le besoin se présente.
- **UUID** : stable seulement si on le conserve d'une génération à l'autre, ce qui impose un état persistant en plus des sources.

## Consequences

Corriger la date d'une émission change son identifiant. Les fichiers qui la référencent doivent alors être régénérés ensemble. Ces corrections sont rares et restent visibles dans l'historique git.
