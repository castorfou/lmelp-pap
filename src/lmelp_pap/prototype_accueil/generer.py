"""PROTOTYPE jetable (ticket #85, second tour de #82) : la page d'accueil de
l'appli pap, variante A retenue (tableau de bord + une page par état), avec
graphique au survol et liste globale sous les compteurs.

Trois variantes de cette page, basculables par ``?variant=A|B|C`` et la
barre flottante en bas. Localisé suit la décision #84 : seule une notice INA
des Archives Radio Pro (identifiant ``PH_``) localise un enregistrement ; une
notice du dépôt légal (``RD_``, InaTHÈQUE) laisse l'émission sans
enregistrement. L'ancienneté dans l'état (date d'entrée) est simulée. Les données viennent des vrais CSV de
``data/processed/`` ; les niveaux rapatrié, qualifié et valide n'existent pas
encore dans ces CSV : quelques émissions y sont placées par simulation, et
toutes les actions sont simulées en mémoire (rien n'est écrit, rien n'est
téléchargé).

Lancer :  uv run python src/lmelp_pap/prototype_accueil/generer.py
puis ouvrir http://localhost:8092/?variant=A
"""

import csv
import json
import random
from collections import defaultdict
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ICI = Path(__file__).parent
DONNEES = ICI.parents[2] / "data" / "processed"
PORT = 8092


def lire(nom: str) -> list[dict[str, str]]:
    with (DONNEES / nom).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def emissions() -> list[dict]:
    sources = defaultdict(set)
    radio_pro = set()
    for a in lire("attestations.csv"):
        sources[a["emission_id"]].add(a["source"])
        if a["source"] == "ina" and a["source_id"].startswith("PH_"):
            radio_pro.add(a["emission_id"])
    integraux = defaultdict(list)
    for e in lire("enregistrements.csv"):
        if e["type"] == "intégral":
            integraux[e["emission_id"]].append(e["url"])
    sortie = []
    for e in lire("emissions.csv"):
        i = e["id"]
        if "lmelp" in sources[i]:
            etat = "lmelp"
        elif integraux[i]:
            etat = "telechargeable"
        elif i in radio_pro:
            etat = "localise"
        else:
            etat = "sans"
        sortie.append(
            {
                "id": i,
                "date": e["date"],
                "annee": int(e["date"][:4]),
                "titre": e["titre"],
                "themes": e["themes"].split(";") if e["themes"] else [],
                "animateur": e["animateur"],
                "duree": e["duree"],
                "sources": sorted(sources[i]),
                "integral": integraux[i][0] if integraux[i] else "",
                "etat": etat,
                "simule": False,
            }
        )
    # Simulation : quelques téléchargeables déjà plus avancés, pour peupler
    # rapatrié / qualifié / valide (absents des CSV aujourd'hui).
    hasard = random.Random(82)
    tele = [e for e in sortie if e["etat"] == "telechargeable"]
    for em, etat in zip(
        hasard.sample(tele, 22), ["rapatrie"] * 12 + ["qualifie"] * 6 + ["valide"] * 4
    ):
        em["etat"], em["simule"] = etat, True
    # Simulation de la date d'entrée dans l'état (décision #84 : chaque passage
    # est daté) : collecte en octobre-novembre 2026, avancées plus récentes.
    for em in sortie:
        em["depuis"] = hasard.randint(0, 25) if em["simule"] else hasard.randint(20, 60)
    return sortie


def main() -> None:
    gabarit = (ICI / "prototype_accueil.html").read_text(encoding="utf-8")
    donnees = json.dumps(emissions(), ensure_ascii=False).replace("</", "<\\/")
    (ICI / "index.html").write_text(gabarit.replace("__DONNEES__", donnees))
    print(f"PROTOTYPE accueil : http://localhost:{PORT}/?variant=A  (B, C)")
    gestion = partial(SimpleHTTPRequestHandler, directory=str(ICI))
    ThreadingHTTPServer(("0.0.0.0", PORT), gestion).serve_forever()


if __name__ == "__main__":
    main()
