"""Le service des fichiers audio de l'appli : ``GET /audios/<fichier>``,
entier ou par plage (``Range``, 206), pour l'écoute et le saut dans le fichier.
Rien ne se lit hors du dossier audio."""

import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lmelp_pap.maturite import MORCEAU


TYPES_AUDIO = {".m4a": "audio/mp4", ".mp3": "audio/mpeg"}


def fichier_audio(dossier: Path, chemin_url: str) -> Path | None:
    """Le fichier que désigne ``/audios/<chemin>`` dans le dossier audio, ou
    ``None`` s'il n'existe pas ou sort du dossier."""
    relatif = unquote(urlsplit(chemin_url).path.removeprefix("/audios/"))
    racine = dossier.resolve()
    chemin = (racine / relatif).resolve()
    if not relatif or not chemin.is_relative_to(racine) or not chemin.is_file():
        return None
    return chemin


def plage(entete: str | None, taille: int) -> tuple[int, int] | None:
    """Les bornes (incluses) d'une plage ``bytes=a-b``, ``bytes=a-`` ou
    ``bytes=-n`` ; ``None`` sans plage lisible (tout le fichier) ;
    ``ValueError`` pour une plage hors du fichier (416)."""
    if not entete or not entete.startswith("bytes=") or "," in entete:
        return None
    debut, _, fin = entete.removeprefix("bytes=").strip().partition("-")
    if not (debut.isdigit() or fin.isdigit()) or not (debut + fin).isdigit():
        return None
    if not debut:  # les n derniers octets
        n = int(fin)
        if n == 0 or taille == 0:
            raise ValueError("plage vide")
        return max(0, taille - n), taille - 1
    a = int(debut)
    b = min(int(fin), taille - 1) if fin else taille - 1
    if a >= taille or a > b:
        raise ValueError("plage hors du fichier")
    return a, b


def type_audio(chemin: Path) -> str:
    """Le type MIME d'un fichier audio, d'après son extension."""
    return TYPES_AUDIO.get(chemin.suffix.lower()) or (
        mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    )


def servir(requete: BaseHTTPRequestHandler, chemin: Path) -> None:
    """Envoie le fichier ``chemin`` en réponse à ``requete`` : entier (200),
    la plage demandée (206), ou 416 pour une plage hors du fichier."""
    taille = chemin.stat().st_size
    try:
        bornes = plage(requete.headers.get("Range"), taille)
    except ValueError:
        requete.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        requete.send_header("Content-Range", f"bytes */{taille}")
        requete.send_header("Content-Length", "0")
        requete.end_headers()
        return
    debut, fin = bornes or (0, taille - 1)
    requete.send_response(HTTPStatus.PARTIAL_CONTENT if bornes else HTTPStatus.OK)
    requete.send_header("Content-Type", type_audio(chemin))
    requete.send_header("Accept-Ranges", "bytes")
    requete.send_header("Content-Length", str(fin - debut + 1))
    if bornes:
        requete.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
    requete.end_headers()
    reste = fin - debut + 1
    try:
        with chemin.open("rb") as f:
            f.seek(debut)
            while reste > 0 and (morceau := f.read(min(MORCEAU, reste))):
                requete.wfile.write(morceau)
                reste -= len(morceau)
    except (BrokenPipeError, ConnectionResetError):
        pass  # le lecteur a sauté ailleurs : il abandonne la plage
