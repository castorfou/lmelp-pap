# Architecture : de la collecte à la page publiée

Le projet produit deux livrables, qui partagent une même construction de la liste :

- **la liste publiée** : la page statique des émissions, générée par la CI à partir des CSV de `data/processed/` et publiée sur GitHub Pages ;
- **l'outil d'arbitrage** (`lmelp-pap arbitrer`) : un serveur local qui lève les doutes de la liste par des décisions humaines, enregistrées dans `arbitrages.csv`.

Les données de référence sont les CSV versionnés de `data/processed/` ; la page n'en est qu'une vue.

## Flux

```mermaid
flowchart TD
    subgraph Sources["Sources (en ligne)"]
        RF[radiofrance.fr]
        INA[catalogue INA]
        WB[Wayback Machine]
        AL[anciennes listes]
        LM[(lmelp · Mongo<br/>source vérifiée)]
    end

    Sources -->|"lmelp-pap emissions<br/>--source X --refresh"| Cache[(data/raw/cache<br/>non versionné)]

    Cache --> Construire{{"construire_liste<br/>rapprochement · arbitrages · doutes"}}
    Arb[(data/processed/<br/>arbitrages.csv)] --> Construire

    Construire --> CSV[(data/processed/<br/>emissions · attestations<br/>enregistrements · doutes .csv)]

    subgraph Appli["Outil d'arbitrage · lmelp-pap arbitrer (local)"]
        Page2[page en mode arbitrage]
        Humain([décision humaine<br/>thème · existence · date<br/>rapprochement · écoute])
        Page2 --> Humain
    end

    CSV --> Page2
    Humain -->|écrit| Arb
    Humain -.->|reconstruit aussitôt| Construire

    CSV -->|"commit + push main"| CI

    subgraph CI["CI · workflow docs.yml"]
        HTML["lmelp-pap page<br/>docs/emissions/index.html"]
        Site[mkdocs build]
        HTML --> Site
    end

    Site --> GH[[GitHub Pages<br/>liste publiée]]
```

## Étapes

**Collecte.** `lmelp-pap emissions` collecte chaque source dans `data/raw/cache/`. Une source dont la collecte est terminée est relue depuis le cache ; `--refresh` la collecte à nouveau. lmelp n'est accessible que depuis le devcontainer.

**Construction.** `construire_liste` (`src/lmelp_pap/liste.py`) rapproche les attestations des sources, applique les arbitrages de `arbitrages.csv`, fusionne chaque émission champ par champ et détecte ses doutes. `ecrire_liste` (`src/lmelp_pap/ecriture.py`) écrit les CSV liés par l'identifiant de l'émission. La commande `emissions` et l'outil d'arbitrage passent tous deux par cette construction.

**Arbitrage.** `lmelp-pap arbitrer` (`src/lmelp_pap/arbitrer.py`) sert la page de la liste avec ses contrôles d'arbitrage. Chaque décision s'ajoute à `arbitrages.csv` ; la liste est reconstruite depuis le cache, sans réseau, et ses CSV sont réécrits. Un arbitrage s'attache à une attestation, pas à l'identifiant d'une émission : il s'applique de nouveau à chaque construction, y compris après une nouvelle collecte.

**Maturité des enregistrements.** `src/lmelp_pap/maturite.py` tient, dans la collection Mongo `pap_enregistrements` (ADR 0004), un document par URL d'intégral : `_id` (l'URL), `emission_id`, `source`, `niveau` (`localise`, `telechargeable`, `rapatrie`, `qualifie`, `valide`), `entrees` (date d'entrée dans chaque niveau) et `verification` (date, résultat `ok`, `net` ou `passager`, détail). `classer` donne le verdict d'une requête `HEAD` ; `appliquer`, fonction pure, en déduit le nouveau niveau ; `verifier` interroge les URL de `enregistrements.csv` en parallèle et écrit par `Depot`. L'appli (`arbitrer.py`) lance la vérification dans un fil de fond et ajoute la maturité aux données de la page quand `MONGO_URI` est défini (`depot_depuis_env`). Les contrôles de maturité vivent dans `arbitrage.html` et s'accrochent à `page.html` par des fonctions facultatives (`passeMaturite`, `filtreMaturite`, `badgeMaturite`, `effacerMaturite`) : la page publiée n'en a rien. Les tests remplacent Mongo par mongomock et le réseau par une session factice.

**Accueil.** `GET /` sert `src/lmelp_pap/accueil.html`, page autonome qui lit `GET /api/donnees` (avec `maturite` et `maturite_depuis`) et calcule l'état de chaque émission (`lmelp`, sinon la maturité, sinon `sans`). Accueil et pages d'état vivent dans le même document ; l'état ouvert et l'année filtrée sont dans l'adresse (`#etat=…&annee=…`). Le registre `ACTIONS` (état → `{libelle, lot, executer}`) est le point d'accroche des actions : la colonne Action et le bouton de lot n'apparaissent que pour un état qui en a une. La liste en mode arbitrage est servie sur `GET /liste`.

**Publication.** Elle suit les CSV : un push sur `main` qui modifie `data/processed/` (ou `docs/`, `src/`) déclenche la workflow `docs.yml`. Elle lance `lmelp-pap page` (`src/lmelp_pap/page.py`), qui génère `docs/emissions/index.html`, une page autonome embarquant les données en JSON, puis construit la documentation MkDocs et la déploie sur GitHub Pages. La page générée n'est pas versionnée (`.gitignore`) ; en local, `lmelp-pap page` sert seulement à la prévisualiser avec `mkdocs serve`.

Cycle type après une séance d'arbitrage ou une nouvelle collecte :

```bash
uv run --active lmelp-pap emissions --source lmelp --refresh   # ou arbitrer
git diff --stat data/processed
git add data/processed && git commit -m "docs(liste): mettre la liste à jour"
git push   # sur main, ou via une PR : la CI régénère et publie la page
```

Le détail des commandes, des fichiers produits et des règles de construction est dans la documentation utilisateur, [Liste des émissions](../user/liste-des-emissions.md).
