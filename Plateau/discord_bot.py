"""
discord_bot.py — Jouer à Queen's Blood contre le bot sur Discord.

Lancement (le token ne doit jamais être écrit dans un fichier) :
    PowerShell        : $env:DISCORD_TOKEN="TON_TOKEN" ; python discord_bot.py
    Invite de cmd     : set DISCORD_TOKEN=TON_TOKEN   puis python discord_bot.py
    Mac / Linux       : export DISCORD_TOKEN="TON_TOKEN" ; python discord_bot.py
Optionnel : DISCORD_GUILD_ID=<id du serveur> pour que les commandes apparaissent tout de suite.

Comment jouer :
    /jouer       lance une partie : le plateau s'affiche avec deux menus
                 1) choisir une carte de la main  2) choisir la case → la carte est posée,
                 puis le bot joue et le plateau se met à jour dans le même message.
    /poser carte ligne colonne   même chose en commande (la carte se choisit dans une liste)
    /passer, /abandonner, /plateau (réafficher), /regles
"""

from __future__ import annotations

import os

import discord
from discord import app_commands

from partie import Partie, position
from plateau import BASE_AFFICHAGE, COLONNES, LIGNES, ROUGE

TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID")
B = BASE_AFFICHAGE


class BotQueensBlood(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.parties: dict[int, Partie] = {}     # une partie par joueur (id Discord)

    async def setup_hook(self):
        if GUILD_ID:
            serveur = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=serveur)
            await self.tree.sync(guild=serveur)
        else:
            await self.tree.sync()   # global : peut mettre un moment à apparaître

    async def on_ready(self):
        print(f"Connecté en tant que {self.user} — prêt à jouer.")


client = BotQueensBlood()


# ---------------------------------------------------------------------
#  Envoi du plateau
# ---------------------------------------------------------------------

def _texte(partie: Partie, lignes: list[str]) -> str:
    lignes = list(lignes)
    if partie.terminee:
        lignes.append(partie.texte_resultat())
    elif partie.tour == ROUGE and not partie.coups_joueur():
        lignes.append("⚠️ Aucune carte ne peut être posée : tu dois **passer**.")
    elif not lignes:
        lignes.append("À toi de jouer : choisis une carte, puis une case.")
    return "\n".join(lignes)[:1900]


async def afficher(interaction: discord.Interaction, partie: Partie, lignes: list[str],
                   modifier: bool, selection: int | None = None):
    """Envoie (ou met à jour, si modifier=True) le message avec l'image du plateau."""
    fichier = discord.File(partie.image(selection), filename="plateau.png")
    contenu = _texte(partie, lignes)
    vue = None if partie.terminee else VuePartie(partie, interaction.user.id, selection)
    if partie.terminee:
        client.parties.pop(interaction.user.id, None)

    if modifier:
        await interaction.response.edit_message(content=contenu, attachments=[fichier], view=vue)
    elif vue is not None:
        await interaction.response.send_message(contenu, file=fichier, view=vue)
    else:
        await interaction.response.send_message(contenu, file=fichier)


async def apres_action(interaction, partie: Partie, erreur: str | None, modifier: bool):
    """Après un coup du joueur : signale l'erreur, ou fait jouer le bot puis affiche."""
    if erreur:
        await interaction.response.send_message(f"❌ {erreur}", ephemeral=True)
        return
    partie.faire_jouer_bot()
    await afficher(interaction, partie, partie.prendre_journal(), modifier)


# ---------------------------------------------------------------------
#  Menus et boutons sous l'image
# ---------------------------------------------------------------------

class VuePartie(discord.ui.View):
    def __init__(self, partie: Partie, joueur_id: int, carte: int | None = None):
        super().__init__(timeout=None)
        self.partie, self.joueur_id, self.carte = partie, joueur_id, carte
        self.version = partie.version
        main = partie.mains[ROUGE]

        # 1) choix de la carte
        if main:
            options = [
                discord.SelectOption(
                    label=f"{i + B}. {c.nom}"[:100],
                    description=f"Coût {c.cout} · Puissance {c.puissance}",
                    value=str(i), default=(i == carte))
                for i, c in enumerate(main[:25])
            ]
            self.menu_carte = discord.ui.Select(placeholder="① Choisis une carte", options=options, row=0)
        else:
            self.menu_carte = discord.ui.Select(placeholder="Ta main est vide", disabled=True, row=0,
                                                options=[discord.SelectOption(label="—", value="-1")])
        self.menu_carte.callback = self.choisir_carte
        self.add_item(self.menu_carte)

        # 2) choix de la case (seulement les cases où la carte peut aller)
        cases = []
        if carte is not None and carte < len(main):
            cases = [(l, c) for l in range(LIGNES) for c in range(COLONNES)
                     if partie.plateau.peut_poser(main[carte], l, c, ROUGE)]
        if cases:
            options = [discord.SelectOption(label=position(l, c).capitalize(), value=f"{l},{c}")
                       for l, c in cases]
            self.menu_case = discord.ui.Select(placeholder="② Choisis la case", options=options, row=1)
        else:
            texte = ("Aucune case possible pour cette carte" if carte is not None
                     else "② Choisis d'abord une carte")
            self.menu_case = discord.ui.Select(placeholder=texte, disabled=True, row=1,
                                               options=[discord.SelectOption(label="—", value="-")])
        self.menu_case.callback = self.choisir_case
        self.add_item(self.menu_case)

        # boutons
        bouton_passer = discord.ui.Button(label="Passer", emoji="⏭️", style=discord.ButtonStyle.secondary, row=2)
        bouton_passer.callback = self.passer
        bouton_abandon = discord.ui.Button(label="Abandonner", emoji="🏳️", style=discord.ButtonStyle.danger, row=2)
        bouton_abandon.callback = self.abandonner
        self.add_item(bouton_passer)
        self.add_item(bouton_abandon)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message(
                "Ce n'est pas ta partie : lance la tienne avec `/jouer`.", ephemeral=True)
            return False
        if client.parties.get(self.joueur_id) is not self.partie or self.partie.version != self.version:
            await interaction.response.send_message(
                "Ce plateau n'est plus à jour : utilise le message le plus récent (ou `/plateau`).",
                ephemeral=True)
            return False
        return True

    async def choisir_carte(self, interaction: discord.Interaction):
        carte = int(self.menu_carte.values[0])
        await afficher(interaction, self.partie, [f"Carte choisie : **{self.partie.mains[ROUGE][carte].nom}**. "
                                                  "Choisis maintenant la case."], modifier=True, selection=carte)

    async def choisir_case(self, interaction: discord.Interaction):
        ligne, colonne = map(int, self.menu_case.values[0].split(","))
        erreur = self.partie.jouer(ROUGE, self.carte, ligne, colonne)
        await apres_action(interaction, self.partie, erreur, modifier=True)

    async def passer(self, interaction: discord.Interaction):
        erreur = self.partie.passer(ROUGE)
        await apres_action(interaction, self.partie, erreur, modifier=True)

    async def abandonner(self, interaction: discord.Interaction):
        self.partie.abandonner(ROUGE)
        await afficher(interaction, self.partie, self.partie.prendre_journal(), modifier=True)


# ---------------------------------------------------------------------
#  Commandes slash
# ---------------------------------------------------------------------

def partie_de(interaction: discord.Interaction) -> Partie | None:
    return client.parties.get(interaction.user.id)


async def pas_de_partie(interaction: discord.Interaction):
    await interaction.response.send_message("Tu n'as pas de partie en cours : lance-la avec `/jouer`.",
                                            ephemeral=True)


@client.tree.command(name="jouer", description="Lance une partie de Queen's Blood contre le bot")
async def jouer(interaction: discord.Interaction):
    if partie_de(interaction):
        await interaction.response.send_message(
            "Tu as déjà une partie en cours : `/plateau` pour la retrouver, `/abandonner` pour l'arrêter.",
            ephemeral=True)
        return
    partie = Partie(nom_joueur=interaction.user.display_name[:16])
    client.parties[interaction.user.id] = partie
    await afficher(interaction, partie, [
        f"⚔️ **{interaction.user.display_name}** (rouge, à gauche) contre le **Bot** (bleu, à droite).",
        "Choisis une carte, puis une case. Tu commences !"], modifier=False)


@client.tree.command(name="plateau", description="Réaffiche ta partie en cours")
async def plateau_cmd(interaction: discord.Interaction):
    partie = partie_de(interaction)
    if not partie:
        return await pas_de_partie(interaction)
    await afficher(interaction, partie, [], modifier=False)


@client.tree.command(name="poser", description="Pose une carte de ta main sur le plateau")
@app_commands.describe(carte="La carte à poser", ligne="Numéro de ligne", colonne="Numéro de colonne")
async def poser(interaction: discord.Interaction, carte: int,
                ligne: app_commands.Range[int, B, LIGNES - 1 + B],
                colonne: app_commands.Range[int, B, COLONNES - 1 + B]):
    partie = partie_de(interaction)
    if not partie:
        return await pas_de_partie(interaction)
    erreur = partie.jouer(ROUGE, carte - B, ligne - B, colonne - B)
    await apres_action(interaction, partie, erreur, modifier=False)


@poser.autocomplete("carte")
async def proposer_cartes(interaction: discord.Interaction, saisie: str):
    partie = partie_de(interaction)
    if not partie:
        return []
    return [app_commands.Choice(name=f"{i + B}. {c.nom} (coût {c.cout}, puissance {c.puissance})", value=i + B)
            for i, c in enumerate(partie.mains[ROUGE]) if saisie.lower() in c.nom.lower()][:25]


@client.tree.command(name="passer", description="Passe ton tour")
async def passer(interaction: discord.Interaction):
    partie = partie_de(interaction)
    if not partie:
        return await pas_de_partie(interaction)
    await apres_action(interaction, partie, partie.passer(ROUGE), modifier=False)


@client.tree.command(name="abandonner", description="Abandonne ta partie en cours")
async def abandonner(interaction: discord.Interaction):
    partie = partie_de(interaction)
    if not partie:
        return await pas_de_partie(interaction)
    partie.abandonner(ROUGE)
    await afficher(interaction, partie, partie.prendre_journal(), modifier=False)


@client.tree.command(name="regles", description="Rappel des règles")
async def regles(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Queen's Blood — règles rapides**\n"
        "• Plateau de 3 lignes × 5 colonnes. Tu es en rouge (à gauche), le bot en bleu (à droite).\n"
        "• Une carte se pose sur une case à toi, vide, qui a au moins autant de pions que son coût.\n"
        "• En se posant, la carte ajoute des pions sur les cases de son motif (petite grille sur la carte).\n"
        "• Chaque ligne affiche le score de chaque camp ; le plus haut score gagne la ligne et marque ce score.\n"
        "• Tu pioches une carte à chaque tour. Quand les deux camps passent à la suite, la partie s'arrête.",
        ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Définis d'abord la variable DISCORD_TOKEN (voir en haut du fichier).")
    client.run(TOKEN)
