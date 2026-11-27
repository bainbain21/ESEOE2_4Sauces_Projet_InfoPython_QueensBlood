"""
Queen's Blood (Final Fantasy VII Rebirth) : les règles en Python.

Le fichier est découpé comme les règles :
    1. Les constantes (taille du plateau, du deck, ...)
    2. Carte    : rang, puissance, motif de pions, effet éventuel
    3. Case     : un pion (ou plus) OU une carte
    4. Plateau  : poser une carte, placer des pions, compter les points
    5. Partie   : pioche, tours, passer, fin de partie
    6. Un petit jeu en console (toi contre un adversaire qui joue au hasard)

Les cartes ci-dessous sont INVENTÉES (ce ne sont pas les vraies cartes du jeu).
Pour en ajouter, il suffit de compléter la liste CARTES_DISPONIBLES.

Hypothèses (règles dont je ne suis pas 100 % sûr) :
    - Le motif de pions d'une carte est inversé (miroir) pour le joueur 1,
      car il joue de droite à gauche.
    - Un pion qui tombe sur une case adverse change la couleur des pions de
      cette case, sans augmenter leur nombre (voir CONVERSION_AJOUTE_UN_PION).
"""

import random

# ----------------------------------------------------------------------
# 1. Constantes
# ----------------------------------------------------------------------
NB_LIGNES = 3          # 3 lignes ("lanes")
NB_COLONNES = 5        # 5 colonnes
PIONS_MAX = 3          # une case ne peut pas avoir plus de 3 pions
TAILLE_DECK = 15       # un deck = 15 cartes
COPIES_MAX = 2         # au maximum 2 exemplaires d'une même carte
TAILLE_MAIN = 5        # main de départ

# Si True : un pion posé sur une case adverse la prend ET ajoute 1 pion.
# Si False : la case est juste prise (même nombre de pions).
CONVERSION_AJOUTE_UN_PION = False


# ----------------------------------------------------------------------
# 2. Les cartes
# ----------------------------------------------------------------------
class Carte:
    """
    nom        : le nom de la carte
    rang       : nombre de pions nécessaires sur la case pour la poser (1 à 3)
    puissance  : les points qu'elle ajoute à sa ligne
    motif      : liste de (decalage_ligne, decalage_colonne) où apparaissent
                 les pions, vu depuis le joueur 0 (qui joue de gauche à droite).
                 Exemple : (0, 1) = la case juste à droite, (-1, 0) = au-dessus.
    effet      : fonction optionnelle appelée quand la carte est posée
    """

    def __init__(self, nom, rang, puissance, motif, effet=None):
        self.nom = nom
        self.rang = rang
        self.puissance_base = puissance
        self.bonus = 0              # modifié par les effets d'autres cartes
        self.motif = motif
        self.effet = effet

    @property
    def puissance(self):
        return max(0, self.puissance_base + self.bonus)

    def copie(self):
        """Chaque exemplaire doit être indépendant (à cause du bonus)."""
        return Carte(self.nom, self.rang, self.puissance_base, self.motif, self.effet)


def effet_renfort(plateau, ligne, colonne, joueur):
    """Exemple d'effet : +1 de puissance aux autres cartes alliées de la ligne."""
    for c in range(NB_COLONNES):
        if c == colonne:
            continue
        case = plateau.cases[ligne][c]
        if case.carte is not None and case.proprietaire == joueur:
            case.carte.bonus += 1


CARTES_DISPONIBLES = [
    Carte("Soldat",    1, 1, [(0, 1)]),
    Carte("Archer",    1, 2, [(0, 1), (0, 2)]),
    Carte("Garde",     1, 2, [(-1, 0), (1, 0)]),
    Carte("Cavalier",  2, 3, [(0, 1), (-1, 0), (1, 0)]),
    Carte("Mage",      2, 4, [(0, 1), (0, 2)]),
    Carte("Capitaine", 2, 2, [(0, 1), (-1, 1), (1, 1)], effet=effet_renfort),
    Carte("Golem",     3, 7, [(0, 1)]),
    Carte("Dragon",    3, 6, [(-1, 1), (0, 1), (1, 1), (0, 2)]),
]


def creer_deck():
    """Deck aléatoire : 15 cartes, max 2 exemplaires de chaque."""
    pool = []
    for carte in CARTES_DISPONIBLES:
        for _ in range(COPIES_MAX):
            pool.append(carte.copie())
    random.shuffle(pool)
    return pool[:TAILLE_DECK]


# ----------------------------------------------------------------------
# 3. Une case
# ----------------------------------------------------------------------
class Case:
    def __init__(self):
        self.proprietaire = None   # None, 0 ou 1
        self.pions = 0             # de 0 à PIONS_MAX
        self.carte = None          # la carte posée ici (ou None)


# ----------------------------------------------------------------------
# 4. Le plateau
# ----------------------------------------------------------------------
class Plateau:
    def __init__(self):
        self.cases = [[Case() for _ in range(NB_COLONNES)] for _ in range(NB_LIGNES)]
        # Départ : 1 pion par joueur au bord de chaque ligne
        for l in range(NB_LIGNES):
            gauche = self.cases[l][0]
            gauche.proprietaire, gauche.pions = 0, 1
            droite = self.cases[l][NB_COLONNES - 1]
            droite.proprietaire, droite.pions = 1, 1

    def dans_le_plateau(self, ligne, colonne):
        return 0 <= ligne < NB_LIGNES and 0 <= colonne < NB_COLONNES

    def peut_jouer(self, carte, ligne, colonne, joueur):
        """Case vide de carte, à moi, avec assez de pions pour le rang."""
        if not self.dans_le_plateau(ligne, colonne):
            return False
        case = self.cases[ligne][colonne]
        return (case.carte is None
                and case.proprietaire == joueur
                and case.pions >= carte.rang)

    def ajouter_pion(self, ligne, colonne, joueur):
        """Ajoute un pion du joueur sur la case (en respectant les règles)."""
        if not self.dans_le_plateau(ligne, colonne):
            return                          # le motif sort du plateau : ignoré
        case = self.cases[ligne][colonne]
        if case.carte is not None:
            return                          # une case avec une carte ne reçoit rien
        if case.proprietaire is None:       # case vide
            case.proprietaire = joueur
            case.pions = 1
        elif case.proprietaire == joueur:   # ma case : +1, max 3
            case.pions = min(case.pions + 1, PIONS_MAX)
        else:                               # case adverse : elle change de camp
            case.proprietaire = joueur
            if CONVERSION_AJOUTE_UN_PION:
                case.pions = min(case.pions + 1, PIONS_MAX)

    def poser(self, carte, ligne, colonne, joueur):
        """Pose la carte, place les pions du motif, déclenche l'effet."""
        case = self.cases[ligne][colonne]
        case.carte = carte
        case.proprietaire = joueur
        case.pions = 0
        sens = 1 if joueur == 0 else -1     # miroir pour le joueur 1
        for dl, dc in carte.motif:
            self.ajouter_pion(ligne + dl, colonne + dc * sens, joueur)
        if carte.effet is not None:
            carte.effet(self, ligne, colonne, joueur)

    # --- Score ---
    def score_ligne(self, ligne, joueur):
        total = 0
        for case in self.cases[ligne]:
            if case.carte is not None and case.proprietaire == joueur:
                total += case.carte.puissance
        return total

    def scores(self):
        """
        Renvoie [points_joueur0, points_joueur1].
        Sur chaque ligne, seul le gagnant marque (le total de sa ligne).
        Égalité sur une ligne : personne ne marque.
        """
        totaux = [0, 0]
        for l in range(NB_LIGNES):
            s0 = self.score_ligne(l, 0)
            s1 = self.score_ligne(l, 1)
            if s0 > s1:
                totaux[0] += s0
            elif s1 > s0:
                totaux[1] += s1
        return totaux

    # --- Affichage ---
    def afficher(self):
        lettres = ["A", "B"]
        for l in range(NB_LIGNES):
            morceaux = []
            for case in self.cases[l]:
                if case.carte is not None:
                    texte = "[%s%d]" % (lettres[case.proprietaire], case.carte.puissance)
                elif case.proprietaire is None:
                    texte = " . "
                else:
                    texte = " %s%d" % (lettres[case.proprietaire], case.pions)
                morceaux.append(texte.center(6))
            s0, s1 = self.score_ligne(l, 0), self.score_ligne(l, 1)
            print("".join(morceaux) + "   | A:%d  B:%d" % (s0, s1))


# ----------------------------------------------------------------------
# 5. La partie
# ----------------------------------------------------------------------
class Partie:
    def __init__(self, deck0=None, deck1=None):
        self.plateau = Plateau()
        self.decks = [deck0 or creer_deck(), deck1 or creer_deck()]
        self.mains = [[], []]
        for j in (0, 1):
            for _ in range(TAILLE_MAIN):
                self.piocher(j)
        self.joueur = 0          # le joueur 0 commence
        self.passes = 0          # nombre de "passer" d'affilée
        self.piocher(0)          # on pioche au début de chaque tour

    def piocher(self, joueur):
        if self.decks[joueur]:
            self.mains[joueur].append(self.decks[joueur].pop())

    def coups_possibles(self, joueur):
        """Liste de (index_carte_dans_la_main, ligne, colonne)."""
        coups = []
        for i, carte in enumerate(self.mains[joueur]):
            for l in range(NB_LIGNES):
                for c in range(NB_COLONNES):
                    if self.plateau.peut_jouer(carte, l, c, joueur):
                        coups.append((i, l, c))
        return coups

    def jouer(self, index_carte, ligne, colonne):
        j = self.joueur
        carte = self.mains[j][index_carte]
        if not self.plateau.peut_jouer(carte, ligne, colonne, j):
            raise ValueError("Coup impossible")
        self.mains[j].pop(index_carte)
        self.plateau.poser(carte, ligne, colonne, j)
        self.passes = 0
        self._fin_de_tour()

    def passer(self):
        self.passes += 1
        self._fin_de_tour()

    def _fin_de_tour(self):
        self.joueur = 1 - self.joueur
        if not self.terminee():
            self.piocher(self.joueur)

    def terminee(self):
        """La partie s'arrête quand les deux joueurs passent d'affilée."""
        return self.passes >= 2

    def vainqueur(self):
        """0, 1 ou None (égalité)."""
        s0, s1 = self.plateau.scores()
        if s0 > s1:
            return 0
        if s1 > s0:
            return 1
        return None


# ----------------------------------------------------------------------
# 6. Jouer en console
# ----------------------------------------------------------------------
def coup_au_hasard(partie):
    """Adversaire simple : un coup au hasard, sinon il passe."""
    coups = partie.coups_possibles(partie.joueur)
    if coups:
        i, l, c = random.choice(coups)
        partie.jouer(i, l, c)
    else:
        partie.passer()


def partie_aleatoire(afficher=False):
    """Deux joueurs au hasard (pratique pour tester le code)."""
    partie = Partie()
    while not partie.terminee():
        coup_au_hasard(partie)
    if afficher:
        partie.plateau.afficher()
    return partie


def jouer_en_console():
    partie = Partie()
    print("Tu es A (à gauche). L'ordinateur est B (à droite).")
    print("Lecture du plateau : A2 = 2 pions à toi, [B3] = carte de B de puissance 3.\n")
    while not partie.terminee():
        partie.plateau.afficher()
        if partie.joueur == 1:
            print("\nTour de l'ordinateur...\n")
            coup_au_hasard(partie)
            continue

        main = partie.mains[0]
        print("\nTa main :")
        for i, carte in enumerate(main):
            print("  %d) %-10s rang %d  puissance %d" % (i, carte.nom, carte.rang, carte.puissance))
        if not partie.coups_possibles(0):
            print("Aucun coup possible, tu passes.")
            partie.passer()
            continue
        reponse = input("Carte ligne colonne (ex: 0 1 1, lignes et colonnes à partir de 0), ou p pour passer : ").strip()
        if reponse.lower() == "p":
            partie.passer()
            continue
        try:
            i, l, c = [int(x) for x in reponse.split()]
            partie.jouer(i, l, c)
        except (ValueError, IndexError):
            print("Coup invalide, réessaie.\n")
            continue
        print()

    partie.plateau.afficher()
    s0, s1 = partie.plateau.scores()
    print("\nScore final -> toi : %d | ordinateur : %d" % (s0, s1))
    gagnant = partie.vainqueur()
    print("Égalité !" if gagnant is None else ("Tu gagnes !" if gagnant == 0 else "L'ordinateur gagne."))


if __name__ == "__main__":
    jouer_en_console()