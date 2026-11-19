# Durabilité des URL d'enregistrements radiofrance

Recherche pour l'issue #50 (carte #48). Relevé du 19 novembre 2026.

## Réponse

**Les 1 111 URL de `data/processed/enregistrements.csv` répondent toutes (HTTP 200,
aucune redirection), avec le bon type MIME et une taille cohérente avec la durée.**
Cela vaut aussi pour les URL que seule la Wayback Machine connaît (473), donc pour des
fichiers que radiofrance.fr ne liste plus, et pour les 119 intégraux 2011-2016.

Radio France ne publie en revanche **aucun engagement de conservation** pour ces
fichiers. Le seul texte trouvé est une annonce de 2020 (« sans limite de durée » sur
ses propres plateformes) rapportée par la presse, et non une politique publiée. Les
fichiers ont d'ailleurs été réécrits en masse en 2024-2025 (dates `Last-Modified`),
ce qui montre que l'hébergement bouge, même si les URL ont survécu.

Conséquence pour #48 : une URL `media.radiofrance-podcast.net` peut servir de **lien**,
à condition de la revérifier régulièrement (une requête HEAD par URL suffit).
Rapatrier le fichier sur le NAS reste une précaution utile pour les intégraux que seule
la Wayback Machine atteste, puisque Radio France ne les expose plus et pourrait les
supprimer sans préavis.

## Méthode

- Une requête `HEAD` par URL, sans suivre automatiquement les redirections (pour les
  compter), concurrence 6, User-Agent générique. Repli prévu en `GET` avec
  `Range: bytes=0-0` si `HEAD` était refusé : jamais nécessaire.
- Ventilation par type, source, décennie de l'émission (`emission_id`) et extension.
- Débit apparent = `Content-Length` × 8 / durée (colonne `duree`), quand la durée est
  connue.
- Première capture de chaque URL dans la Wayback Machine (API CDX, préfixe
  `media.radiofrance-podcast.net/podcast09/14007-`, `collapse=urlkey`).
- Contrôle ponctuel de la fin de fichier (`Range: bytes=-1000`) : réponse 206 avec
  la taille totale annoncée.

## Résultats

### Statut HTTP

| Statut | URL |
|---|---|
| 200 | 1 111 |
| autre (3xx, 4xx, 5xx, erreur réseau) | 0 |

Aucune redirection. 1 110 URL sont servies par `AkamaiNetStorage`
(`media.radiofrance-podcast.net/podcast09/`) ; une seule (intégral du 2011-07-31) est
sur `cdn.radiofrance.fr/s3/cruiser-production/…`, elle répond aussi.

### Par type et par source

| Type / source | radiofrance seule | wayback seule | les deux | total | 200 |
|---|---|---|---|---|---|
| intégral | 157 | 216 | 111 | 484 | 484 |
| extrait | 173 | 257 | 197 | 627 | 627 |
| **total** | 330 | 473 | 308 | 1 111 | 1 111 |

### Par décennie de l'émission

| Décennie | intégral | extrait | 200 |
|---|---|---|---|
| 1950 | 0 | 11 | 11 |
| 1960 | 0 | 11 | 11 |
| 1970 | 0 | 14 | 14 |
| 1980 | 1 | 18 | 19 |
| 1990 | 0 | 33 | 33 |
| 2000 | 0 | 111 | 111 |
| 2010 | 187 | 70 | 257 |
| 2020 | 296 | 359 | 655 |

Intégraux 2011-2016 : 119 URL (66 radiofrance seule, 27 wayback seule, 26 les deux ;
86 m4a, 33 mp3), toutes en 200.

### Par extension

| Extension | URL | 200 | Content-Type |
|---|---|---|---|
| m4a | 616 | 616 | `audio/mp4` |
| mp3 | 495 | 495 | `audio/mpeg` |

### Taille et durée

| Extension | URL avec durée | débit min | médiane | max |
|---|---|---|---|---|
| m4a | 542 | 194 kbit/s | 194 kbit/s | 195 kbit/s |
| mp3 | 294 | 128 kbit/s | 128 kbit/s | 132 kbit/s |

Le débit est constant par format : aucun fichier tronqué, vide ou remplacé par une page
d'erreur servie en 200. Aucun fichier ne fait moins de 100 Ko. Les 275 URL sans durée
(toutes « wayback seule ») ont des tailles du même ordre (par exemple 6,7 Mo en mp3 et
10,1 Mo en m4a pour un extrait de 2005). Les intégraux avec durée durent de 43 à
62 min (médiane 54 min).

### Ancienneté des URL

Dates de première capture par la Wayback Machine des URL du CSV :

| Source | captures avant 2020 | 2020-2023 | 2024 | 2025 | 2026 | jamais capturée |
|---|---|---|---|---|---|---|
| wayback seule | 9 | 31 | 68 | 274 | 91 | 0 |
| les deux | 6 | 32 | 33 | 213 | 24 | 0 |
| radiofrance seule | 0 | 0 | 0 | 1 | 0 | 329 |

Les 15 URL capturées avant 2020 (la plus ancienne en 2016) répondent toujours : une URL
`podcast09` peut rester stable au moins sept à dix ans.

Dates `Last-Modified` des fichiers servis :

| Année | URL |
|---|---|
| 2016-2019 | 58 |
| 2020-2023 | 98 |
| 2024 | 415 |
| 2025 | 364 |
| 2026 | 176 |

99 des 119 intégraux 2011-2016 portent un `Last-Modified` de 2024 : les fichiers ont été
réécrits sans changer d'URL. De nombreux noms d'extraits portent aussi un code de
republication (`…-1967F4007E0001-…`), signe d'une mise en ligne dans un podcast
d'archives longtemps après la diffusion.

## Politique de conservation de Radio France

- **Aucune politique publiée trouvée.** La page « Conditions générales d'utilisation »
  de radiofrance.fr
  (<https://www.radiofrance.fr/franceculture/conditions-generales-d-utilisation-7575206>)
  ne contient aucune clause sur la durée de disponibilité des podcasts.
- **Annonce de 2020, rapportée par la presse** : CB News, 15 octobre 2020
  (<https://www.cbnews.fr/medias/image-radio-france-met-ordre-sa-politique-distribution-podcasts-55560>).
  Les programmes, « auparavant conservés 3 ans », le seraient désormais « sans limite
  de durée » sur les plateformes de Radio France ; sur les plateformes tierces, une
  semaine pour les quotidiennes, un mois pour les hebdomadaires. Il s'agit d'une
  intention de distribution, pas d'un engagement d'archivage. Elle porte sur
  l'exposition des épisodes, non sur les URL de fichiers.
- **API Radio France** (fiche data.gouv.fr,
  <https://www.data.gouv.fr/dataservices/api-radio-france>) : elle donne les liens
  d'écoute des derniers épisodes, mais « n'est pas destinée » aux applications
  d'agrégation de podcasts. Elle ne dit rien sur la durée de vie des URL.
- Indice contraire : Radio France a déjà retiré des épisodes de plateformes tierces et
  supprimé des flux RSS (iGeneration, 2026,
  <https://www.igen.fr/services/2026/05/affaire-sensible-radio-france-retarde-certaines-emissions-sur-apple-podcasts-156239> ;
  LinuxFr, <https://linuxfr.org/users/micromy/journaux/radio-france-supprime-les-liens-rss-des-ses-emissions>).
  Les fichiers eux-mêmes sont restés en ligne d'après nos mesures.

## Limites

- Ce relevé n'a qu'une date : il établit que les URL répondent aujourd'hui, pas
  qu'elles répondront demain.
- Une réponse 200 de l'origine Akamai indique que le fichier existe. Seule la cohérence
  taille/durée et la lecture des derniers octets (sur deux fichiers) vérifient son
  contenu. Aucun fichier n'a été téléchargé ni écouté en entier.
- Les URL « radiofrance seule » n'ont presque jamais été capturées par la Wayback
  Machine : si Radio France les supprimait, aucune copie publique ne resterait.
