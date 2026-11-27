"""
plateau.py — Plateau de Queen's Blood : état du jeu + affichage pygame.

La partie « logique » (Carte, Case, Plateau) ne dépend pas de pygame :
on peut tester le bot sans interface. La partie « affichage » ne sert
qu'à dessiner (fenêtre pygame ou image PNG pour Discord).

Utilisation rapide :
    plateau = Plateau()
    plateau.poser(Carte("Chocobo", cout=1, puissance=2, image="chocobo.png"), 0, 0, ROUGE)
    image = rendre_image(plateau, main=[...], pioche=12, defausse=[...])   # BytesIO PNG
    python plateau.py   -> ouvre une fenêtre de démonstration
"""

from __future__ import annotations

import io
import math
import os
from dataclasses import dataclass, field

try:  # pygame n'est nécessaire que pour l'affichage
    import pygame
except ImportError:  # pragma: no cover
    pygame = None


# =====================================================================
#  LOGIQUE DU PLATEAU
# =====================================================================

LIGNES, COLONNES = 3, 5
ROUGE, BLEU = "rouge", "bleu"          # joueur à gauche, bot à droite
MAX_PIONS = 3
BASE_AFFICHAGE = 1   # numéros affichés à l'écran : 1 = « 1 à 5 », 0 = « 0 à 4 »
                     # (à aligner avec ce qu'attend /poser dans discord_bot.py)

DOSSIER_IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "cartes")


def adversaire(camp: str) -> str:
    return BLEU if camp == ROUGE else ROUGE


@dataclass
class Carte:
    """Une carte. Le motif est donné du point de vue du joueur rouge
    (décalages (ligne, colonne) ; colonne positive = vers l'adversaire).
    Il est automatiquement inversé pour le camp bleu."""
    nom: str
    cout: int = 1
    puissance: int = 1
    motif: list = field(default_factory=lambda: [(-1, 0), (1, 0), (0, 1)])
    image: str | None = None


@dataclass
class Case:
    proprietaire: str | None = None   # ROUGE, BLEU ou None
    pions: int = 0                    # 0 à MAX_PIONS
    carte: Carte | None = None

    @property
    def libre(self) -> bool:
        return self.carte is None


class Plateau:
    def __init__(self):
        self.cases = [[Case() for _ in range(COLONNES)] for _ in range(LIGNES)]
        for l in range(LIGNES):
            self.cases[l][0] = Case(ROUGE, 1)
            self.cases[l][COLONNES - 1] = Case(BLEU, 1)
        self.dernier_coup: tuple[int, int] | None = None

    # --- consultation -------------------------------------------------
    def dans_plateau(self, ligne: int, colonne: int) -> bool:
        return 0 <= ligne < LIGNES and 0 <= colonne < COLONNES

    def case(self, ligne: int, colonne: int) -> Case:
        return self.cases[ligne][colonne]

    def peut_poser(self, carte: Carte, ligne: int, colonne: int, camp: str) -> bool:
        if not self.dans_plateau(ligne, colonne):
            return False
        c = self.cases[ligne][colonne]
        return c.libre and c.proprietaire == camp and c.pions >= carte.cout

    def coups_possibles(self, main: list[Carte], camp: str) -> list[tuple[int, int, int]]:
        """Liste des (indice_carte, ligne, colonne) jouables."""
        return [(i, l, c)
                for i, carte in enumerate(main)
                for l in range(LIGNES)
                for c in range(COLONNES)
                if self.peut_poser(carte, l, c, camp)]

    def cases_du_motif(self, carte: Carte, ligne: int, colonne: int, camp: str):
        sens = 1 if camp == ROUGE else -1
        for dl, dc in carte.motif:
            l, c = ligne + dl, colonne + dc * sens
            if self.dans_plateau(l, c):
                yield l, c

    # --- action -------------------------------------------------------
    def poser(self, carte: Carte, ligne: int, colonne: int, camp: str) -> bool:
        """Pose la carte si c'est légal. Renvoie True si la carte a été posée.
        Effet SIMPLIFIÉ (à remplacer par les vraies règles) : +1 pion sur chaque
        case du motif si elle est libre et neutre ou déjà à nous."""
        if not self.peut_poser(carte, ligne, colonne, camp):
            return False
        self.cases[ligne][colonne].carte = carte
        for l, c in self.cases_du_motif(carte, ligne, colonne, camp):
            cible = self.cases[l][c]
            if cible.libre and cible.proprietaire in (None, camp):
                cible.proprietaire = camp
                cible.pions = min(MAX_PIONS, cible.pions + 1)
        self.dernier_coup = (ligne, colonne)
        return True

    # --- scores -------------------------------------------------------
    def score_ligne(self, ligne: int) -> dict[str, int]:
        scores = {ROUGE: 0, BLEU: 0}
        for c in self.cases[ligne]:
            if c.carte is not None and c.proprietaire in scores:
                scores[c.proprietaire] += c.carte.puissance
        return scores

    def gagnant_ligne(self, ligne: int) -> str | None:
        s = self.score_ligne(ligne)
        if s[ROUGE] == s[BLEU]:
            return None
        return ROUGE if s[ROUGE] > s[BLEU] else BLEU

    def scores_finaux(self) -> dict[str, int]:
        """Le camp qui gagne une ligne marque son score de ligne."""
        total = {ROUGE: 0, BLEU: 0}
        for l in range(LIGNES):
            g = self.gagnant_ligne(l)
            if g:
                total[g] += self.score_ligne(l)[g]
        return total


# =====================================================================
#  AFFICHAGE (pygame)
# =====================================================================

LARGEUR, HAUTEUR = 1280, 820
CASE_L, CASE_H, ECART = 118, 144, 10
PLATEAU_L = COLONNES * CASE_L + (COLONNES - 1) * ECART
PLATEAU_H = LIGNES * CASE_H + (LIGNES - 1) * ECART
X0 = (LARGEUR - PLATEAU_L) // 2
Y0 = 124
CARTE_MAIN = (100, 138)

# Palette
OR = (214, 178, 98)
OR_CLAIR = (246, 222, 150)
OR_SOMBRE = (128, 98, 46)
PIERRE = (44, 46, 60)
PIERRE_CLAIRE = (64, 67, 86)
ENCRE = (14, 15, 24)
TEXTE = (236, 230, 214)
TEXTE_DOUX = (168, 162, 150)
CAMPS = {
    ROUGE: {"vif": (222, 72, 70), "clair": (255, 150, 136), "sombre": (96, 24, 30)},
    BLEU:  {"vif": (66, 140, 232), "clair": (150, 200, 255), "sombre": (22, 44, 98)},
}

_polices: dict = {}
_images: dict = {}
_fond_cache: dict = {}


def _police(taille: int, gras: bool = False):
    cle = (taille, gras)
    if cle not in _polices:
        _polices[cle] = pygame.font.SysFont(
            "georgia,palatinolinotype,bookantiqua,cambria,dejavuserif,serif", taille, bold=gras)
    return _polices[cle]


def _texte(surf, txt, taille, couleur, centre=None, gauche=None, gras=False, ombre=True, largeur_max=None):
    """Écrit du texte centré (centre=(x, y)) ou aligné à gauche (gauche=(x, y_centre))."""
    p = _police(taille, gras)
    while largeur_max and taille > 9 and p.size(txt)[0] > largeur_max:
        taille -= 1
        p = _police(taille, gras)
    rendu = p.render(txt, True, couleur)
    w, h = rendu.get_size()
    if centre:
        x, y = centre[0] - w // 2, centre[1] - h // 2
    else:
        x, y = gauche[0], gauche[1] - h // 2
    if ombre:
        surf.blit(p.render(txt, True, ENCRE), (x + 1, y + 2))
    surf.blit(rendu, (x, y))


def _rect_alpha(surf, couleur, rect, rayon=0, epaisseur=0):
    """Rectangle (éventuellement transparent) avec coins arrondis."""
    x, y, w, h = rect
    calque = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(calque, couleur, (0, 0, w, h), epaisseur, border_radius=rayon)
    surf.blit(calque, (x, y))


def _halo(surf, couleur, rect, rayon, taille=10, intensite=90):
    """Lueur douce autour d'un rectangle."""
    x, y, w, h = rect
    for i in range(taille, 0, -2):
        a = int(intensite * (1 - i / taille) ** 2) + 6
        _rect_alpha(surf, (*couleur, a), (x - i, y - i, w + 2 * i, h + 2 * i), rayon + i, 2)


def _degrade_vertical(w, h, haut, bas, alpha=False):
    s = pygame.Surface((w, h), pygame.SRCALPHA) if alpha else pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        col = tuple(int(haut[i] + (bas[i] - haut[i]) * t) for i in range(len(haut)))
        pygame.draw.line(s, col, (0, y), (w, y))
    return s


def _losange(surf, couleur, centre, rx, ry, epaisseur=0):
    cx, cy = centre
    pygame.draw.polygon(surf, couleur, [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)], epaisseur)


def _image_carte(fichier, w, h):
    cle = (fichier, w, h)
    if cle not in _images:
        chemin = fichier if os.path.isabs(fichier) else os.path.join(DOSSIER_IMAGES, fichier)
        try:
            _images[cle] = pygame.transform.smoothscale(pygame.image.load(chemin), (w, h))
        except (FileNotFoundError, pygame.error):
            _images[cle] = None
    return _images[cle]


# ---------------------------------------------------------------------
#  Décor
# ---------------------------------------------------------------------

def _fond():
    if "fond" in _fond_cache:
        return _fond_cache["fond"]
    fond = _degrade_vertical(LARGEUR, HAUTEUR, (24, 22, 36), (12, 12, 20))
    # treillis de losanges très discret
    motif = pygame.Surface((LARGEUR, HAUTEUR), pygame.SRCALPHA)
    pas = 46
    for k in range(-HAUTEUR, LARGEUR + HAUTEUR, pas):
        pygame.draw.line(motif, (255, 230, 180, 9), (k, 0), (k + HAUTEUR, HAUTEUR))
        pygame.draw.line(motif, (255, 230, 180, 9), (k, HAUTEUR), (k + HAUTEUR, 0))
    fond.blit(motif, (0, 0))
    # tapis de jeu sous le plateau
    tapis = (X0 - 120, Y0 - 44, PLATEAU_L + 240, PLATEAU_H + 88)
    _rect_alpha(fond, (70, 40, 52, 70), tapis, 26)
    _rect_alpha(fond, (*OR_SOMBRE, 90), tapis, 26, 2)
    # vignette
    vignette = pygame.Surface((LARGEUR, HAUTEUR), pygame.SRCALPHA)
    for i in range(0, 90, 3):
        pygame.draw.rect(vignette, (0, 0, 0, int(3 + (90 - i) * 0.9)), (i, i, LARGEUR - 2 * i, HAUTEUR - 2 * i), 3)
    fond.blit(vignette, (0, 0))
    _fond_cache["fond"] = fond
    return fond


def _ornement_coin(surf, x, y, sx, sy):
    """Petit ornement doré dans un coin (sx, sy = ±1 pour l'orientation)."""
    pygame.draw.line(surf, OR, (x, y), (x + 34 * sx, y), 3)
    pygame.draw.line(surf, OR, (x, y), (x, y + 34 * sy), 3)
    pygame.draw.line(surf, OR_SOMBRE, (x + 8 * sx, y + 8 * sy), (x + 24 * sx, y + 8 * sy), 2)
    pygame.draw.line(surf, OR_SOMBRE, (x + 8 * sx, y + 8 * sy), (x + 8 * sx, y + 24 * sy), 2)
    _losange(surf, OR_CLAIR, (x, y), 7, 7)
    _losange(surf, OR_SOMBRE, (x, y), 7, 7, 1)


def _titre(surf, camp_actif, message):
    cx = LARGEUR // 2
    _texte(surf, "QUEEN'S BLOOD", 34, OR_CLAIR, centre=(cx, 34), gras=True)
    for sens in (-1, 1):
        x1 = cx + sens * 160
        pygame.draw.line(surf, OR_SOMBRE, (x1, 34), (x1 + sens * 170, 34), 2)
        pygame.draw.line(surf, OR, (x1, 31), (x1 + sens * 110, 31), 1)
        _losange(surf, OR, (x1 + sens * 178, 34), 6, 6)
    if message:
        _texte(surf, message, 17, TEXTE_DOUX, centre=(cx, 66))
    elif camp_actif:
        txt = "À vous de jouer" if camp_actif == ROUGE else "Le bot réfléchit…"
        _texte(surf, txt, 17, CAMPS[camp_actif]["clair"], centre=(cx, 66))


# ---------------------------------------------------------------------
#  Cartes
# ---------------------------------------------------------------------

def _illustration_provisoire(surf, carte, rect, camp):
    x, y, w, h = rect
    cols = CAMPS.get(camp, CAMPS[ROUGE])
    surf.blit(_degrade_vertical(w, h, cols["vif"], cols["sombre"]), (x, y))
    calque = pygame.Surface((w, h), pygame.SRCALPHA)
    for r in range(max(w, h), 0, -14):
        pygame.draw.circle(calque, (255, 255, 255, 10), (w // 2, h // 2), r, 1)
    _losange(calque, (255, 255, 255, 40), (w // 2, h // 2), w // 3, h // 3)
    _losange(calque, (255, 255, 255, 70), (w // 2, h // 2), w // 3, h // 3, 2)
    surf.blit(calque, (x, y))
    _texte(surf, carte.nom[:1].upper(), max(14, h // 3), (255, 245, 230), centre=(x + w // 2, y + h // 2), gras=True)


def _pastille_puissance(surf, centre, valeur, taille):
    r = taille
    pygame.draw.circle(surf, ENCRE, (centre[0] + 1, centre[1] + 2), r + 1)
    pygame.draw.circle(surf, OR, centre, r)
    pygame.draw.circle(surf, (40, 30, 24), centre, r - 3)
    pygame.draw.circle(surf, OR_SOMBRE, centre, r - 3, 1)
    _texte(surf, str(valeur), int(r * 1.25), OR_CLAIR, centre=(centre[0], centre[1] + 1), gras=True)


def _cout_en_pions(surf, x, y, cout, taille):
    for i in range(cout):
        cx = x + i * (taille * 2 + 3)
        _losange(surf, ENCRE, (cx + 1, y + 2), taille, int(taille * 1.35))
        _losange(surf, (250, 236, 170), (cx, y), taille, int(taille * 1.35))
        _losange(surf, OR_SOMBRE, (cx, y), taille, int(taille * 1.35), 1)


def _mini_motif(surf, carte, x, y, cellule, camp):
    """Grille 5×5 montrant où la carte ajoute des pions (centre = la carte)."""
    n = 5
    _rect_alpha(surf, (8, 8, 14, 190), (x - 3, y - 3, n * cellule + 6, n * cellule + 6), 4)
    sens = 1 if camp == ROUGE else -1
    cibles = {(dl + 2, dc * sens + 2) for dl, dc in carte.motif}
    for l in range(n):
        for c in range(n):
            r = (x + c * cellule + 1, y + l * cellule + 1, cellule - 2, cellule - 2)
            if (l, c) == (2, 2):
                pygame.draw.rect(surf, TEXTE, r)
            elif (l, c) in cibles:
                pygame.draw.rect(surf, (250, 220, 110), r)
            else:
                pygame.draw.rect(surf, (70, 70, 84), r)


def dessiner_carte(surf, carte, rect, camp, detaillee=False, numero=None):
    """Dessine une carte dans rect = (x, y, w, h)."""
    x, y, w, h = rect
    cols = CAMPS.get(camp, CAMPS[ROUGE])
    _rect_alpha(surf, (0, 0, 0, 120), (x + 3, y + 5, w, h), 9)          # ombre
    pygame.draw.rect(surf, OR, rect, border_radius=9)                     # cadre doré
    pygame.draw.rect(surf, OR_CLAIR, rect, 1, border_radius=9)
    pygame.draw.rect(surf, cols["sombre"], (x + 4, y + 4, w - 8, h - 8), border_radius=6)

    bande = max(16, h // 7)
    art = (x + 6, y + 6, w - 12, h - 12 - bande)
    img = _image_carte(carte.image, art[2], art[3]) if carte.image else None
    if img:
        surf.blit(img, art[:2])
    else:
        _illustration_provisoire(surf, carte, art, camp)
    pygame.draw.rect(surf, cols["vif"], art, 1)

    # bandeau du nom
    yb = y + h - 6 - bande
    pygame.draw.rect(surf, (22, 20, 30), (x + 6, yb, w - 12, bande))
    pygame.draw.line(surf, OR, (x + 6, yb), (x + w - 7, yb), 1)
    _texte(surf, carte.nom, max(10, bande - 5), TEXTE, centre=(x + w // 2, yb + bande // 2),
           largeur_max=w - 16, ombre=False)

    t = max(4, w // 22)
    _cout_en_pions(surf, x + 8 + t, y + 10 + t, carte.cout, t)
    _pastille_puissance(surf, (x + w - 16 - t, y + 16 + t), carte.puissance, max(10, w // 9))

    if detaillee:
        cell = max(5, w // 14)
        _mini_motif(surf, carte, x + 10, yb - 5 * cell - 8, cell, camp)
    if numero is not None:
        _rect_alpha(surf, (8, 8, 14, 210), (x + w - 28, yb - 24, 22, 20), 5)
        _texte(surf, str(numero), 14, OR_CLAIR, centre=(x + w - 17, yb - 14), gras=True, ombre=False)


def _dos_de_carte(surf, rect):
    x, y, w, h = rect
    _rect_alpha(surf, (0, 0, 0, 110), (x + 3, y + 5, w, h), 9)
    pygame.draw.rect(surf, OR, rect, border_radius=9)
    surf.blit(_degrade_vertical(w - 8, h - 8, (40, 36, 70), (18, 16, 34)), (x + 4, y + 4))
    pygame.draw.rect(surf, OR_SOMBRE, (x + 8, y + 8, w - 16, h - 16), 1, border_radius=5)
    cx, cy = x + w // 2, y + h // 2
    for k in range(3):
        _losange(surf, OR if k == 0 else OR_SOMBRE, (cx, cy), w // 3 - k * 8, h // 3 - k * 10, 2)
    _losange(surf, OR_CLAIR, (cx, cy), 6, 8)


# ---------------------------------------------------------------------
#  Plateau
# ---------------------------------------------------------------------

def _rect_case(l, c):
    return (X0 + c * (CASE_L + ECART), Y0 + l * (CASE_H + ECART), CASE_L, CASE_H)


def _pions(surf, case, rect):
    x, y, w, h = rect
    cx, cy = x + w // 2, y + h // 2
    positions = {1: [(0, 0)], 2: [(-20, 0), (20, 0)], 3: [(0, -20), (-20, 16), (20, 16)]}[case.pions]
    cols = CAMPS[case.proprietaire]
    for dx, dy in positions:
        p = (cx + dx, cy + dy)
        _losange(surf, ENCRE, (p[0] + 2, p[1] + 3), 12, 17)
        _losange(surf, cols["vif"], p, 12, 17)
        pygame.draw.polygon(surf, cols["clair"], [(p[0], p[1] - 17), (p[0] + 12, p[1]), (p[0], p[1])])
        pygame.draw.polygon(surf, cols["sombre"], [(p[0], p[1] + 17), (p[0] - 12, p[1]), (p[0], p[1])])
        _losange(surf, (255, 255, 255), p, 12, 17, 1)


def _dessiner_case(surf, plateau, l, c):
    case = plateau.cases[l][c]
    rect = _rect_case(l, c)
    x, y, w, h = rect
    # pierre biseautée
    pygame.draw.rect(surf, ENCRE, (x, y + 3, w, h), border_radius=8)
    pygame.draw.rect(surf, PIERRE, rect, border_radius=8)
    pygame.draw.rect(surf, PIERRE_CLAIRE, (x + 3, y + 3, w - 6, h - 6), 1, border_radius=6)
    if case.proprietaire:
        cols = CAMPS[case.proprietaire]
        _rect_alpha(surf, (*cols["vif"], 55), rect, 8)
        _rect_alpha(surf, (*cols["vif"], 210), rect, 8, 2)
    else:
        _losange(surf, (58, 60, 76), (x + w // 2, y + h // 2), 14, 20, 1)

    if case.carte is not None:
        dessiner_carte(surf, case.carte, (x + 5, y + 5, w - 10, h - 10), case.proprietaire)
    elif case.pions > 0 and case.proprietaire:
        _pions(surf, case, rect)

    if plateau.dernier_coup == (l, c):
        _halo(surf, OR_CLAIR, rect, 8, 10, 140)
        pygame.draw.rect(surf, OR_CLAIR, rect, 2, border_radius=8)


def _medaillon(surf, centre, valeur, camp, gagne):
    cols = CAMPS[camp]
    r = 30
    if gagne:
        for i in range(14, 0, -2):
            calque = pygame.Surface((2 * (r + i), 2 * (r + i)), pygame.SRCALPHA)
            pygame.draw.circle(calque, (*OR_CLAIR, int(70 * (1 - i / 14))), (r + i, r + i), r + i)
            surf.blit(calque, (centre[0] - r - i, centre[1] - r - i))
    pygame.draw.circle(surf, ENCRE, (centre[0] + 2, centre[1] + 3), r + 2)
    pygame.draw.circle(surf, OR if gagne else (110, 106, 100), centre, r)
    pygame.draw.circle(surf, cols["sombre"], centre, r - 5)
    pygame.draw.circle(surf, cols["vif"], centre, r - 5, 2)
    _texte(surf, str(valeur), 26, TEXTE, centre=(centre[0], centre[1] + 1), gras=True)
    if gagne:  # petite couronne
        cx, cy = centre[0], centre[1] - r - 8
        pts = [(cx - 14, cy + 6), (cx - 14, cy - 4), (cx - 7, cy + 1), (cx, cy - 8),
               (cx + 7, cy + 1), (cx + 14, cy - 4), (cx + 14, cy + 6)]
        pygame.draw.polygon(surf, ENCRE, [(px + 1, py + 2) for px, py in pts])
        pygame.draw.polygon(surf, OR_CLAIR, pts)
        pygame.draw.polygon(surf, OR_SOMBRE, pts, 1)


def _dessiner_plateau(surf, plateau):
    # cadre doré du plateau
    m = 24
    cadre = (X0 - m, Y0 - m, PLATEAU_L + 2 * m, PLATEAU_H + 2 * m)
    _rect_alpha(surf, (10, 10, 16, 200), cadre, 16)
    pygame.draw.rect(surf, OR_SOMBRE, cadre, 4, border_radius=16)
    pygame.draw.rect(surf, OR, (cadre[0] + 5, cadre[1] + 5, cadre[2] - 10, cadre[3] - 10), 1, border_radius=12)
    cx0, cy0, cx1, cy1 = cadre[0], cadre[1], cadre[0] + cadre[2], cadre[1] + cadre[3]
    for (px, py, sx, sy) in ((cx0, cy0, 1, 1), (cx1, cy0, -1, 1), (cx0, cy1, 1, -1), (cx1, cy1, -1, -1)):
        _ornement_coin(surf, px, py, sx, sy)

    # numéros de colonnes et de lignes
    for c in range(COLONNES):
        x, y, w, _ = _rect_case(0, c)
        _texte(surf, str(c + BASE_AFFICHAGE), 14, OR, centre=(x + w // 2, cadre[1] - 14))
    for l in range(LIGNES):
        x, y, _, h = _rect_case(l, 0)
        _texte(surf, str(l + BASE_AFFICHAGE), 14, OR, centre=(cadre[0] + 12, y + h // 2))

    for l in range(LIGNES):
        for c in range(COLONNES):
            _dessiner_case(surf, plateau, l, c)

    # scores de ligne
    for l in range(LIGNES):
        s = plateau.score_ligne(l)
        g = plateau.gagnant_ligne(l)
        _, y, _, h = _rect_case(l, 0)
        cy = y + h // 2
        _medaillon(surf, (X0 - 76, cy), s[ROUGE], ROUGE, g == ROUGE)
        _medaillon(surf, (X0 + PLATEAU_L + 76, cy), s[BLEU], BLEU, g == BLEU)


# ---------------------------------------------------------------------
#  Panneaux, main, pioche, défausse
# ---------------------------------------------------------------------

def _panneau_joueur(surf, x, camp, nom, total, cartes_en_main, actif):
    cols = CAMPS[camp]
    rect = (x, Y0 + 40, 170, 230)
    if actif:
        _halo(surf, cols["vif"], rect, 14, 14, 120)
    _rect_alpha(surf, (14, 14, 22, 215), rect, 14)
    _rect_alpha(surf, (*cols["vif"], 230), rect, 14, 2)
    pygame.draw.rect(surf, cols["sombre"], (x + 2, rect[1] + 2, 166, 44), border_top_left_radius=12,
                     border_top_right_radius=12)
    _texte(surf, nom, 22, TEXTE, centre=(x + 85, rect[1] + 24), gras=True, largeur_max=150)
    _texte(surf, "SCORE", 13, TEXTE_DOUX, centre=(x + 85, rect[1] + 70))
    _texte(surf, str(total), 56, OR_CLAIR, centre=(x + 85, rect[1] + 116), gras=True)
    pygame.draw.line(surf, OR_SOMBRE, (x + 24, rect[1] + 158), (x + 146, rect[1] + 158), 1)
    _losange(surf, OR, (x + 85, rect[1] + 158), 5, 5)
    _texte(surf, f"{cartes_en_main} carte{'s' if cartes_en_main > 1 else ''} en main", 15,
           TEXTE_DOUX, centre=(x + 85, rect[1] + 184))
    if actif:
        _texte(surf, "● À son tour", 14, cols["clair"], centre=(x + 85, rect[1] + 208), ombre=False)


def _emplacement_vide(surf, rect, libelle):
    _rect_alpha(surf, (255, 255, 255, 12), rect, 9)
    _rect_alpha(surf, (*OR_SOMBRE, 200), rect, 9, 2)
    _texte(surf, libelle, 13, TEXTE_DOUX, centre=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2))


def _pioche(surf, x, y, nb):
    w, h = CARTE_MAIN
    if nb <= 0:
        _emplacement_vide(surf, (x, y, w, h), "Vide")
    else:
        for k in range(min(4, nb) - 1, -1, -1):
            _dos_de_carte(surf, (x + k * 3, y - k * 3, w, h))
    _texte(surf, f"Pioche · {max(0, nb)}", 15, TEXTE_DOUX, centre=(x + w // 2, y + h + 20))


def _defausse(surf, x, y, cartes):
    w, h = CARTE_MAIN
    nb = cartes if isinstance(cartes, int) else len(cartes)
    if isinstance(cartes, int) or not cartes:
        if nb:
            _dos_de_carte(surf, (x, y, w, h))
        else:
            _emplacement_vide(surf, (x, y, w, h), "Défausse")
    else:
        for k, carte in enumerate(cartes[-3:]):
            dessiner_carte(surf, carte, (x + k * 4, y - k * 3, w, h), None)
        _rect_alpha(surf, (0, 0, 0, 90), (x + 8, y - 6, w, h), 9)
    _texte(surf, f"Défausse · {nb}", 15, TEXTE_DOUX, centre=(x + w // 2, y + h + 20))


def _main(surf, main, camp, selection):
    if not main:
        return
    w, h = CARTE_MAIN
    n = len(main)
    pas = min(w + 14, (PLATEAU_L + 120) // max(1, n))
    total = pas * (n - 1) + w
    x = (LARGEUR - total) // 2
    y = HAUTEUR - h - 40
    _texte(surf, "VOTRE MAIN", 13, OR, centre=(LARGEUR // 2, y + h + 18))
    for i, carte in enumerate(main):
        dy = -14 if i == selection else 0
        r = (x + i * pas, y + dy, w, h)
        if i == selection:
            _halo(surf, OR_CLAIR, r, 9, 12, 150)
        dessiner_carte(surf, carte, r, camp, detaillee=True, numero=i + BASE_AFFICHAGE)


# ---------------------------------------------------------------------
#  Points d'entrée
# ---------------------------------------------------------------------

def dessiner(surf, plateau: Plateau, main=(), pioche=0, defausse=(), camp_actif=ROUGE,
             noms=("Joueur", "Bot"), cartes_bot=0, selection=None, message=""):
    """Dessine toute la scène sur surf (LARGEUR × HAUTEUR).

    main       : cartes du joueur rouge (affichées en bas, numérotées)
    pioche     : nombre de cartes (ou liste) restant dans la pioche du joueur
    defausse   : liste de cartes défaussées (ou un nombre)
    camp_actif : ROUGE / BLEU / None (met en valeur le camp qui joue)
    cartes_bot : nombre de cartes dans la main du bot
    selection  : indice de la carte de la main à mettre en avant
    message    : texte sous le titre (ex. « Victoire ! »)
    """
    nb_pioche = pioche if isinstance(pioche, int) else len(pioche)
    surf.blit(_fond(), (0, 0))
    _titre(surf, camp_actif, message)
    _dessiner_plateau(surf, plateau)
    totaux = plateau.scores_finaux()
    _panneau_joueur(surf, 40, ROUGE, noms[0], totaux[ROUGE], len(main), camp_actif == ROUGE)
    _panneau_joueur(surf, LARGEUR - 40 - 170, BLEU, noms[1], totaux[BLEU], cartes_bot, camp_actif == BLEU)
    yb = HAUTEUR - CARTE_MAIN[1] - 40
    _defausse(surf, 70, yb, list(defausse) if not isinstance(defausse, int) else defausse)
    _pioche(surf, LARGEUR - 70 - CARTE_MAIN[0], yb, nb_pioche)
    _main(surf, list(main), ROUGE, selection)


def _initialiser_sans_fenetre():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()


def rendre_image(plateau: Plateau, **options) -> io.BytesIO:
    """Renvoie le plateau sous forme d'image PNG en mémoire (pour Discord) :
        fichier = discord.File(rendre_image(plateau, main=main), filename="plateau.png")
    Accepte les mêmes options que dessiner()."""
    _initialiser_sans_fenetre()
    surf = pygame.Surface((LARGEUR, HAUTEUR))
    dessiner(surf, plateau, **options)
    tampon = io.BytesIO()
    pygame.image.save(surf, tampon, "plateau.png")
    tampon.seek(0)
    return tampon


def case_sous_souris(pos) -> tuple[int, int] | None:
    """(ligne, colonne) sous la position de la souris, ou None."""
    for l in range(LIGNES):
        for c in range(COLONNES):
            x, y, w, h = _rect_case(l, c)
            if x <= pos[0] < x + w and y <= pos[1] < y + h:
                return l, c
    return None


# ---------------------------------------------------------------------
#  Démonstration : python plateau.py
# ---------------------------------------------------------------------

def _exemple():
    plateau = Plateau()
    chocobo = Carte("Chocobo", 1, 2, [(-1, 0), (1, 0), (0, 1)], image="chocobo.png")
    garde = Carte("Garde de la ville", 1, 1, [(0, 1), (-1, 1)])
    mog = Carte("Mog", 1, 1, [(0, 1), (1, 1), (-1, 1)])
    plateau.poser(chocobo, 1, 0, ROUGE)
    plateau.poser(garde, 0, 4, BLEU)
    plateau.poser(mog, 0, 0, ROUGE)
    plateau.poser(Carte("Gobelin", 1, 3, [(1, 0), (0, 1)]), 2, 4, BLEU)
    plateau.poser(Carte("Cactuar", 1, 1, [(1, 0)]), 1, 1, ROUGE)
    main = [
        Carte("Soldat", 1, 1, [(0, 1), (-1, 0), (1, 0)]),
        Carte("Moogle", 1, 2, [(-1, 1), (1, 1)]),
        Carte("Grangalan", 2, 3, [(0, 1), (0, 2), (1, 1)]),
        Carte("Archidémon", 3, 5, [(-1, 0), (1, 0), (0, 1), (0, -1)]),
        Carte("Bombo", 2, 2, [(-1, -1), (1, 1)]),
    ]
    return plateau, main, [Carte("Elfe", 1, 1)]


if __name__ == "__main__":
    pygame.init()
    ecran = pygame.display.set_mode((LARGEUR, HAUTEUR))
    pygame.display.set_caption("Queen's Blood")
    plateau, main, defausse = _exemple()
    selection, horloge = 0, pygame.time.Clock()
    en_cours = True
    while en_cours:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                en_cours = False
            elif ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_9:
                selection = min(len(main) - 1, ev.key - pygame.K_1)
            elif ev.type == pygame.MOUSEBUTTONDOWN and main:
                cible = case_sous_souris(ev.pos)
                if cible and plateau.poser(main[selection], *cible, ROUGE):
                    main.pop(selection)
                    selection = max(0, min(selection, len(main) - 1))
        dessiner(ecran, plateau, main=main, pioche=12, defausse=defausse, camp_actif=ROUGE,
                 cartes_bot=5, selection=selection if main else None,
                 message="Touches 1-9 : choisir une carte · clic : la poser")
        pygame.display.flip()
        horloge.tick(30)
    pygame.quit()
