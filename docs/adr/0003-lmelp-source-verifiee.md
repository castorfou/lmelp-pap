# lmelp est une source vérifiée : elle atteste comme une source et fait foi comme un arbitrage

Les émissions retenues dans lmelp (2014-2026) ont toutes été vérifiées à la main, en amont, dans cette application. lmelp devient une **source vérifiée** : ses attestations entrent dans la liste comme celles de toute source, mais ce qu'elles affirment fait foi. Une émission vérifiée est dans la liste, son thème est exactement « livres », et ses doutes d'existence et de thème sont levés. lmelp donne une date de publication (podcast), pas de première diffusion : elle ne date pas l'émission et ne crée pas de désaccord de date. Une attestation lmelp se rattache à l'émission par l'URL de sa fiche radiofrance.fr, pas par la date, et son identifiant est le slug de cette fiche. Comme lmelp est complet pour les émissions littéraires depuis 2017, une émission de la liste absente de lmelp sur cette période est un doute (une émission au thème hommage, hors de la liste, le garde : son thème explique l'absence) ; avant 2017, son absence ne prouve rien.

## Considered Options

- **Source ordinaire** : ses thèmes se cumuleraient avec ceux des autres sources, et une erreur de classement (une émission littéraire classée « cinéma ; livres ; théâtre ») resterait dans la liste malgré la vérification.
- **185 arbitrages** : un arbitrage s'attache à une attestation existante et n'atteste aucune émission. Une émission que seul lmelp connaîtrait ne pourrait pas entrer dans la liste, et les arbitrages humains de lmelp-pap se mêleraient à des vérifications faites ailleurs.

## Consequences

La base Mongo de lmelp n'est accessible que depuis le devcontainer : la collecte copie les émissions vérifiées dans le cache, et la construction de la liste reste possible hors ligne. Une contradiction entre lmelp et un arbitrage de lmelp-pap n'est pas tranchée en silence : c'est un doute.
