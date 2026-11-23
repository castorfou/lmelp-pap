# Le journal des échanges vit dans sa propre collection, `pap_echanges`, jamais exportée

Un enregistrement localisé (une piste) garde le journal des échanges qui mènent à lui : courriels, appels, messages de forum avec son détenteur, et la prochaine relance. C'est du travail humain qu'on ne peut pas recalculer : il vit dans Mongo, qui fait foi (ADR 0004).

Chaque échange est un document de la collection `pap_echanges` : `enregistrement` (l'identifiant de la piste, `_id` de `pap_enregistrements`), `emission_id`, `date`, `canal`, `interlocuteur`, `texte`, `relance` et `note_le` (l'heure de la saisie, qui départage deux échanges du même jour). La collection ne reçoit que des insertions.

Le journal n'est ni exporté en CSV ni publié : il contient des noms de particuliers. Il n'a donc pas de pendant dans `data/processed/`, contrairement aux arbitrages et aux qualifications ; sa seule sauvegarde est celle de la base (`mongodump`).

## Considered Options

- **Un champ `journal` dans le document de l'enregistrement** (`pap_enregistrements`) : tout est au même endroit, mais chaque écriture de l'enregistrement remplace le document entier (`replace_one`). Un rapatriement ou une vérification lancés en fond, qui écrivent un enregistrement lu avant la saisie d'un échange, effaceraient cet échange. Le modèle `Enregistrement` grossirait aussi d'une liste que ni la vérification, ni le rapatriement, ni la qualification n'utilisent.
- **Une collection `pap_echanges`** (retenue) : une insertion par échange, sans conflit avec les écritures des tâches de fond ; le journal reste lisible quand l'enregistrement monte à rapatrié, et s'écarte de toute exportation sans filtrer de champ.

## Consequences

Les données de la page (`GET /api/donnees`) joignent les deux collections : chaque enregistrement localisé porte son journal et sa relance (celle de son dernier échange), chaque émission sa relance (la plus proche de ses pistes) et son dernier échange. Noter un échange ne touche pas `pap_enregistrements` : ni la maturité ni la date d'entrée dans le niveau ne changent.
