"""PROTOTYPE jetable (ticket #87) : les écrans de travail « sans enregistrement »
et « localisé » de l'appli pap, en trois variantes basculables par
``?variant=A|B|C`` et la barre flottante en bas.

La page est la vraie page d'accueil (``src/lmelp_pap/accueil.html``), servie
telle quelle avec ``prototype.js`` en plus : ce script remplace les pages des
deux états et simule en mémoire toutes les écritures (piste, échange, URL,
fichier). Rien n'est écrit en base. Les données viennent d'un serveur pap
local (``scripts/start-dev.sh``), lu une fois au démarrage ; les autres
requêtes GET lui sont relayées. Quelques pistes de passionnés et un journal
d'échanges sont ajoutés par simulation.

Lancer :  scripts/start-dev.sh   (dans un autre terminal)
          uv run python src/lmelp_pap/prototype_ecrans/generer.py
puis ouvrir http://localhost:8093/#etat=localise  (?variant=A, B ou C)
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ICI = Path(__file__).parent
PAP = os.environ.get("PAP_URL", "http://localhost:8765")
PORT = 8093


def page() -> bytes:
    html = (ICI.parent / "accueil.html").read_text(encoding="utf-8")
    # les données dans un fichier à part : en ligne, un « <!-- » du JSON
    # dérègle l'analyse HTML du script
    avant = '<script src="/prototype-donnees.js"></script><script src="/prototype-fetch.js"></script>'

    apres = '<script src="/prototype.js"></script>'
    html = html.replace("<script>\n// Les états", avant + "\n<script>\n// Les états", 1)
    html = html.replace("</body>", apres + "\n</body>", 1)
    return html.encode()


class Gestion(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        chemin = self.path.split("?")[0]
        if chemin == "/prototype-donnees.js":
            donnees = urllib.request.urlopen(PAP + "/api/donnees").read()
            corps, type_ = (
                b"window.PROTO_DONNEES = " + donnees + b";",
                "text/javascript",
            )
        elif chemin == "/":
            corps, type_ = page(), "text/html; charset=utf-8"
        elif chemin in ("/prototype.js", "/prototype-fetch.js"):
            corps = (ICI / chemin.lstrip("/")).read_bytes()
            type_ = "text/javascript; charset=utf-8"
        else:
            try:
                with urllib.request.urlopen(PAP + self.path) as r:
                    corps, type_ = r.read(), r.headers.get("Content-Type", "")
            except OSError as erreur:  # le prototype ne sert que la lecture
                self.send_error(502, str(erreur))
                return
        self.send_response(200)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


if __name__ == "__main__":
    json.loads(urllib.request.urlopen(PAP + "/api/donnees").read())  # pap répond ?
    print(
        f"PROTOTYPE écrans : http://localhost:{PORT}/#etat=localise  (?variant=A|B|C)"
    )
    ThreadingHTTPServer(("0.0.0.0", PORT), Gestion).serve_forever()
