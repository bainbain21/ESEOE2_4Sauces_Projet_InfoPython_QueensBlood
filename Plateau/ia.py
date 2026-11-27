"""
ia.py — Cerveau du bot.

Interface à respecter (utilisée par partie.py) :
    choisir_coup(plateau, main, camp) -> (indice_carte, ligne, colonne) ou None pour passer
Les indices commencent à 0. Le plateau et la main ne doivent pas être modifiés ici.

Version provisoire : coup légal au hasard, en préférant un peu les cartes fortes.
"""

import random

from plateau import Plateau


def choisir_coup(plateau: Plateau, main, camp):
    coups = plateau.coups_possibles(main, camp)
    if not coups:
        return None
    # léger avantage aux cartes puissantes, sans être prévisible
    poids = [1 + main[i].puissance for i, _, _ in coups]
    return random.choices(coups, weights=poids, k=1)[0]
