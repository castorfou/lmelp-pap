# Une archive aussi longue qu'une émission est un intégral (#57)

## Problème

80 émissions de 2006 à 2011 avaient un fichier `media.radiofrance-podcast.net` de 48 à 57 min typé `extrait`, parce que son code de publication porte la lettre `E` (`2007F4007E0027`). La règle de requalification des archives entières (`_archives_entieres`, `src/lmelp_pap/liste.py`) ne s'appliquait qu'avec une durée de diffusion INA (90 %), absente de ces notices. Trouvé par la recherche « sources en ligne d'intégraux anciens » de la carte wayfinder #48.

## Correction

- Sans durée INA, une archive `E` d'au moins 45 min (`_DUREE_MIN_ENTIERE`) est l'émission entière ; avec durée INA, la règle des 90 % (`_PART_MIN_ENTIERE`) reste.
- Choix du seuil sur les données : les fichiers `extrait` durent tous moins de 35 min (les plus longs, 24-30 min, sont des archives 1958-1978), puis aucun avant 45 min, puis 86 fichiers de 48 à 57 min.
- L'extension du type `intégral` se fait par **segment** d'archive (`_segment`), plus par ITEMA (`_itema`) : une même archive ITEMA porte parfois l'émission entière et de vrais extraits dans d'autres segments (2006-09-17 : `E0051` de 6 min, `E0081` de 11 min). Par ITEMA, 18 fichiers courts basculaient à tort. Le segment couvre les autres encodages (`-22.mp3`, `-27.m4a`) et les autres sources (Wayback).

## Effet sur la liste

- Émissions sans intégral : 516 → 436 ; 86 fichiers basculent, tous ≥ 48 min.
- Une émission requalifiée prend le titre et la durée de la fiche radiofrance (la durée ne vient jamais d'un extrait).
- Doute levé : `attestation fragile` du 1995-01-28 (archive cinéma de 52 min, prix des auditeurs 1995), hors liste.

## Tests

`tests/test_liste.py`, fixture `_archive_aout_2007` : archive longue sans durée INA → intégral ; archive de 30 min → extrait ; sans notice INA → intégral ; extrait court d'un autre segment de la même archive → reste extrait.

## Leçon

Vérifier une règle de données sur la liste reconstruite (`uv run lmelp-pap emissions`, depuis le cache) et pas seulement sur les tests : c'est la distribution des durées des fichiers basculés qui a révélé l'extension par ITEMA trop large.
