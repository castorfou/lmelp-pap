# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Génère le favicon de l'appli pap, dans l'identité graphique de lmelp.

Les icônes de la famille lmelp partent toutes de l'icône verte historique
(masque doré + plume blanche, ``scripts/icone/source_lmelp_green.png``, copie
de ``frontend/public/gimp_favicon/favicon.png`` de castorfou/back-office-lmelp)
et y ajoutent, derrière la plume, une marque propre sur un fond propre :

- back-office-lmelp : base de données carmin, fond vert ;
- lmelp-mobile : smartphone, fond bleu nuit ;
- pap : bobine de bande magnétique (l'archive radio), fond sépia.

Le détourage du masque et de la plume reprend celui de
``scripts/generate_launcher_icon.py`` de castorfou/lmelp-mobile.

Fichiers produits dans ``src/lmelp_pap/icones/`` (livrés avec le paquet) :

- ``favicon.ico`` (16, 32 et 48 px) ;
- ``favicon-32x32.png`` (aussi embarqué en data URI dans la page de la liste) ;
- ``apple-touch-icon.png`` (180 px, carré plein : iOS arrondit lui-même).

Usage (les dépendances sont déclarées en tête du script) :
    uv run scripts/generer_favicon.py
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


RACINE = Path(__file__).resolve().parent.parent
SOURCE = Path(__file__).resolve().parent / "icone" / "source_lmelp_green.png"
SORTIE = RACINE / "src" / "lmelp_pap" / "icones"

# Fond sépia (dégradé vertical) : le papier jauni des archives, assez clair
# pour que le masque doré ressorte autant que sur le vert du back-office
SEPIA = (0xA8, 0x6E, 0x3A)
SEPIA_FIN = (0x7A, 0x4E, 0x2A)
# Bobine : flasques argentées, bande magnétique brun foncé
FLASQUE = (0xE3, 0xE6, 0xEA)
FLASQUE_BORD = (0x9A, 0xA3, 0xAE)
BANDE = (0x3A, 0x26, 0x18)

# Bobine dans le repère de la source (1327×1328) : en bas à droite, derrière
# la plume, là où les autres icônes de la famille placent leur marque
_BOBINE_CENTRE = (975, 900)
_BOBINE_RAYON = 310

_TRAVAIL = 1024

# Pixels « verts » (fond + ombre) : G dépasse max(R, B)
_VERT_OPAQUE_SOUS = 5
_VERT_TRANSPARENT_AU_DESSUS = 35
_MARGE_MAGENTA = 10
_PELAGES = 25

TAILLES_ICO = [(16, 16), (32, 32), (48, 48)]


def detourer(img: Image.Image) -> Image.Image:
    """Masque et plume détourés : les pixels verts deviennent transparents.

    L'alpha décroît avec la « verdeur » (G - max(R, B)) pour garder des bords
    anti-aliasés ; seul le plus grand ensemble connexe (masque + plume) reste,
    ce qui élimine l'ombre vert foncé.
    """
    rgba = np.asarray(img.convert("RGBA")).astype(np.int32)
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    verdeur = g - np.maximum(r, b)

    etendue = _VERT_TRANSPARENT_AU_DESSUS - _VERT_OPAQUE_SOUS
    garde = np.clip((_VERT_TRANSPARENT_AU_DESSUS - verdeur) / etendue, 0.0, 1.0)
    alpha = (a * garde).round().astype(np.int32)

    # Pelage des pixels teintés (vert résiduel, liseré rose) qui touchent la
    # transparence ; les yeux et la bouche, enclos dans le masque, restent.
    magenta = np.minimum(r, b) - g > _MARGE_MAGENTA
    teinte = (verdeur > 0) | magenta
    for _ in range(_PELAGES):
        bord = ndimage.binary_dilation(alpha == 0) & (alpha > 0) & teinte
        if not bord.any():
            break
        alpha[bord] = 0

    etiquettes, nombre = ndimage.label(alpha > 0)
    if nombre > 1:
        tailles = ndimage.sum_labels(
            np.ones_like(etiquettes), etiquettes, index=range(1, nombre + 1)
        )
        alpha[etiquettes != int(np.argmax(tailles)) + 1] = 0

    out = rgba.copy()
    out[..., 1] = np.where(verdeur > 0, np.maximum(r, b), g)
    out[..., 3] = alpha
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def dessiner_bobine(taille: tuple[int, int]) -> Image.Image:
    """Bobine de bande magnétique vue de face : bande enroulée brun foncé
    entre la jante et le moyeu argentés, reliés par trois rayons."""
    calque = Image.new("RGBA", taille, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    cx, cy = _BOBINE_CENTRE
    rayon = _BOBINE_RAYON

    def disque(r: float, couleur: tuple[int, int, int]) -> tuple[float, ...]:
        boite = (cx - r, cy - r, cx + r, cy + r)
        d.ellipse(boite, fill=couleur + (255,))
        return boite

    disque(rayon, FLASQUE_BORD)
    disque(rayon * 0.96, FLASQUE)
    # bande enroulée, vue à travers trois larges fenêtres de la flasque
    disque(rayon * 0.86, BANDE)
    interieur = (
        cx - rayon * 0.87,
        cy - rayon * 0.87,
        cx + rayon * 0.87,
        cy + rayon * 0.87,
    )
    for depart in (-90, 30, 150):
        d.pieslice(interieur, depart - 11, depart + 11, fill=FLASQUE + (255,))
    disque(rayon * 0.30, FLASQUE)
    disque(rayon * 0.12, FLASQUE_BORD)
    disque(rayon * 0.06, BANDE)
    return calque


def motif() -> Image.Image:
    """Bobine, puis masque et plume par-dessus (repère de la source)."""
    masque_plume = detourer(Image.open(SOURCE))
    return Image.alpha_composite(dessiner_bobine(masque_plume.size), masque_plume)


def fond(taille: int) -> Image.Image:
    """Dégradé sépia vertical, opaque."""
    t = np.linspace(0.0, 1.0, taille)[:, None]
    debut, fin = np.array(SEPIA), np.array(SEPIA_FIN)
    lignes = (debut + (fin - debut) * t).round().astype(np.uint8)
    rgb = np.repeat(lignes[:, None, :], taille, axis=1)
    alpha = np.full((taille, taille, 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA")


def icone_carree() -> Image.Image:
    """Fond sépia plein, motif cadré comme dans l'icône source (``_TRAVAIL`` px
    de côté) : masque et plume ont la même taille que dans celle du
    back-office, et la bobine tient dans le carré."""
    m = motif()
    icone = fond(m.width)
    icone.alpha_composite(m)
    return icone.resize((_TRAVAIL, _TRAVAIL), Image.Resampling.LANCZOS)


def arrondir(icone: Image.Image) -> Image.Image:
    """Coins arrondis (rayon d'un sixième du côté), comme les autres icônes
    lmelp."""
    forme = Image.new("L", icone.size, 0)
    ImageDraw.Draw(forme).rounded_rectangle(
        (0, 0, icone.width - 1, icone.height - 1), radius=icone.width // 6, fill=255
    )
    arrondie = icone.copy()
    arrondie.putalpha(forme)
    return arrondie


def generer(sortie: Path = SORTIE) -> None:
    """Écrit les icônes de pap dans ``sortie``."""
    sortie.mkdir(parents=True, exist_ok=True)
    carree = icone_carree()
    arrondie = arrondir(carree)

    def reduite(img: Image.Image, cote: int) -> Image.Image:
        return img.resize((cote, cote), Image.Resampling.LANCZOS)

    reduite(arrondie, 32).save(sortie / "favicon-32x32.png", optimize=True)
    reduite(carree, 180).save(sortie / "apple-touch-icon.png", optimize=True)
    reduite(arrondie, 48).save(sortie / "favicon.ico", format="ICO", sizes=TAILLES_ICO)
    for f in sorted(sortie.iterdir()):
        print(f"{f.relative_to(RACINE)} ({f.stat().st_size} octets)")


if __name__ == "__main__":
    generer()
