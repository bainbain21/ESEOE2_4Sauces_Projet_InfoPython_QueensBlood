"""
partie.py — Déroulement d'une partie joueur (ROUGE, à gauche) contre bot (BLEU, à droite).

Règles du déroulement :
- chaque camp a un deck de 15 cartes et en pioche 5 au départ ;
- le joueur commence ; à partir du 2e tour, chaque camp pioche 1 carte au début de son tour ;
- à son tour on pose une carte ou on passe ;
- la partie s'arrête quand les deux camps passent l'un après l'autre (ou sur abandon) ;
- chaque ligne rapporte son score au camp qui la gagne ; le plus gros total gagne.

Aucune dépendance à Discord : la partie peut être testée seule (python partie.py).
"""

from __future__ import annotations

import random
from dataclasses import replace

import ia
from plateau import (BASE_AFFICHAGE, BLEU, ROUGE, Carte, Plateau, adversaire, rendre_image)

# Cartes PROVISOIRES : à remplacer par les vraies cartes du jeu
# (nom, coût, puissance, motif, image). Le motif est vu du joueur rouge :
# (décalage de ligne, décalage de colonne), colonne positive = vers l'adversaire.
MODELES = [
    Carte("Soldat", 1, 1, [(-1, 0), (1, 0), (0, 1)]),
    Carte("Chocobo", 1, 2, [(0, 1), (-1, 0)], image="chocobo.png"),
    Carte("Mog", 1, 1, [(-1, 1), (0, 1), (1, 1)]),
    Carte("Cactuar", 1, 2, [(0, 1)]),
    Carte("Gobelin", 1, 1, [(1, 0), (0, 1), (-1, 0)]),
    Carte("Bombo", 2, 3, [(-1, 1), (1, 1)]),
    Carte("Grangalan", 2, 3, [(0, 1), (0, 2)]),
    Carte("Garde royal", 2, 4, [(-1, 0), (1, 0)]),
    Carte("Béhémoth", 3, 6, [(0, 1), (-1, 1), (1, 1), (0, 2)]),
    Carte("Archidémon", 3, 5, [(-1, 0), (1, 0), (0, 1), (0, -1)]),
]

TAILLE_DECK = 15
TAILLE_MAIN = 5
NOMS_CAMPS = {ROUGE: "Joueur", BLEU: "Bot"}


def position(ligne: int, colonne: int) -> str:
    return f"ligne {ligne + BASE_AFFICHAGE}, colonne {colonne + BASE_AFFICHAGE}"


class Partie:
    def __init__(self, nom_joueur: str = "Joueur", graine=None):
        self.rng = random.Random(graine)
        self.plateau = Plateau()
        self.noms = {ROUGE: nom_joueur, BLEU: NOMS_CAMPS[BLEU]}
        self.pioches = {camp: self._nouveau_deck() for camp in (ROUGE, BLEU)}
        self.mains = {ROUGE: [], BLEU: []}
        self.defausses = {ROUGE: [], BLEU: []}
        for camp in (ROUGE, BLEU):
            for _ in range(TAILLE_MAIN):
                self._piocher(camp)
        self.tour = ROUGE
        self.passes_consecutives = 0
        self.terminee = False
        self.abandon: str | None = None
        self.version = 0          # augmente à chaque coup (sert à repérer les vieux messages)
        self._journal: list[str] = []

    # --- préparation --------------------------------------------------
    def _nouveau_deck(self) -> list[Carte]:
        deck = [replace(self.rng.choice(MODELES)) for _ in range(TAILLE_DECK)]
        self.rng.shuffle(deck)
        return deck

    def _piocher(self, camp: str) -> Carte | None:
        if not self.pioches[camp]:
            return None
        carte = self.pioches[camp].pop()
        self.mains[camp].append(carte)
        return carte

    # --- déroulement --------------------------------------------------
    def _fin_de_tour(self):
        self.version += 1
        if self.passes_consecutives >= 2:
            self.terminee = True
            return
        self.tour = adversaire(self.tour)
        carte = self._piocher(self.tour)
        if carte and self.tour == ROUGE:
            self._journal.append(f"Tu pioches **{carte.nom}**.")

    def raison_refus(self, camp: str, indice: int, ligne: int, colonne: int) -> str | None:
        """Explique pourquoi un coup est refusé (None si le coup est légal)."""
        if self.terminee:
            return "La partie est terminée."
        if camp != self.tour:
            return "Ce n'est pas ton tour."
        main = self.mains[camp]
        if not 0 <= indice < len(main):
            return f"Il n'y a pas de carte n°{indice + BASE_AFFICHAGE} dans ta main."
        if not self.plateau.dans_plateau(ligne, colonne):
            return "Cette case n'existe pas."
        carte, case = main[indice], self.plateau.case(ligne, colonne)
        if case.carte is not None:
            return "Il y a déjà une carte sur cette case."
        if case.proprietaire != camp:
            return "Tu ne contrôles pas cette case."
        if case.pions < carte.cout:
            return f"**{carte.nom}** coûte {carte.cout} pion(s) et la case n'en a que {case.pions}."
        return None

    def jouer(self, camp: str, indice: int, ligne: int, colonne: int) -> str | None:
        """Pose une carte. Renvoie un message d'erreur, ou None si tout s'est bien passé."""
        erreur = self.raison_refus(camp, indice, ligne, colonne)
        if erreur:
            return erreur
        carte = self.mains[camp].pop(indice)
        self.plateau.poser(carte, ligne, colonne, camp)
        self.passes_consecutives = 0
        qui = "Tu poses" if camp == ROUGE else "Le bot pose"
        self._journal.append(f"{qui} **{carte.nom}** ({position(ligne, colonne)}).")
        self._fin_de_tour()
        return None

    def passer(self, camp: str) -> str | None:
        if self.terminee:
            return "La partie est terminée."
        if camp != self.tour:
            return "Ce n'est pas ton tour."
        self.passes_consecutives += 1
        self._journal.append("Tu passes ton tour." if camp == ROUGE else "Le bot passe son tour.")
        self._fin_de_tour()
        return None

    def abandonner(self, camp: str):
        self.terminee = True
        self.abandon = camp
        self.version += 1
        self._journal.append("Tu abandonnes la partie." if camp == ROUGE else "Le bot abandonne.")

    def faire_jouer_bot(self):
        """Fait jouer le bot tant que c'est son tour."""
        while not self.terminee and self.tour == BLEU:
            try:
                coup = ia.choisir_coup(self.plateau, list(self.mains[BLEU]), BLEU)
            except Exception as e:  # une IA qui plante ne doit pas bloquer la partie
                print("Erreur dans ia.choisir_coup :", e)
                coup = None
            if coup is None or self.jouer(BLEU, *coup) is not None:
                self.passer(BLEU)

    # --- informations -------------------------------------------------
    def coups_joueur(self):
        return self.plateau.coups_possibles(self.mains[ROUGE], ROUGE)

    def prendre_journal(self) -> list[str]:
        lignes, self._journal = self._journal, []
        return lignes

    def gagnant(self) -> str | None:
        if self.abandon:
            return adversaire(self.abandon)
        s = self.plateau.scores_finaux()
        if s[ROUGE] == s[BLEU]:
            return None
        return ROUGE if s[ROUGE] > s[BLEU] else BLEU

    def texte_resultat(self) -> str:
        s = self.plateau.scores_finaux()
        g = self.gagnant()
        titre = {ROUGE: "🏆 Victoire !", BLEU: "💀 Défaite…", None: "🤝 Égalité"}[g]
        return f"{titre}  Score final : **{s[ROUGE]}** à **{s[BLEU]}**"

    def image(self, selection: int | None = None):
        if self.terminee:
            message = {ROUGE: "Victoire !", BLEU: "Défaite…", None: "Égalité"}[self.gagnant()]
        else:
            message = ""
        return rendre_image(
            self.plateau,
            main=self.mains[ROUGE],
            pioche=len(self.pioches[ROUGE]),
            defausse=self.defausses[ROUGE],
            camp_actif=None if self.terminee else self.tour,
            noms=(self.noms[ROUGE], self.noms[BLEU]),
            cartes_bot=len(self.mains[BLEU]),
            selection=selection,
            message=message,
        )


if __name__ == "__main__":
    # Partie de test dans le terminal : le joueur joue aussi au hasard.
    p = Partie(graine=1)
    while not p.terminee:
        coup = ia.choisir_coup(p.plateau, p.mains[ROUGE], ROUGE)
        p.jouer(ROUGE, *coup) if coup else p.passer(ROUGE)
        p.faire_jouer_bot()
        print("\n".join(p.prendre_journal()))
    print(p.texte_resultat())
