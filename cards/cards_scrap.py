"""
class Card:
    def __init__(self):
        self.name =

"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

base_url = "https://www.gamerguides.com/final-fantasy-vii-rebirth"
cards_collection = (
    base_url + "/guide/minigames/queens-blood/all-queens-blood-card-locations"
)

cards_regex = re.compile(r"(\d{3})-(^[a-zA-Z0-9 -]+)$")


# a class abilities for the cards
class Abilities:
    def __init__(
        self, description, effect_type, value=None, trigger=None, conditions=None
    ):
        self.description = description
        self.effect_type = effect_type
        self.value = value
        self.trigger = trigger
        self.conditions = conditions


# a class card
class Card:
    def __init__(
        self, name, number, pawns, base_power, position, rarity="STANDARD", ability=None
    ):
        self.name = name
        self.number = number
        self.rarity = rarity
        self.base_power = base_power
        self.pawns = pawns
        self.abilities = abilities or []
        self.image = image
        self.location = location
        self.destroyed = False
        self.modifiers = []

    def boost(self, value):
        self.modifiers.append(value)

    def weaken(self, value):
        self.modifiers.append(-abs(value))

    def power_calcul(self):
        return self.base_power + sum(self.modifiers)


"""
For regex:
    ^   : for start of the text
    \d  : for decimal numbers so 0-9
    {X} : for numbers of times it should be written
    $   : for end of the text
    ()  : for what will be 'examined'
    []  : for matching the character inside
    +   : for one or more times
"""

response = requests.get(cards_collection)

soup = BeautifulSoup(response.text, "html.parser")
card_urls = []

# find all button in the html of the website and when it has the href attribute
for link in soup.find_all("a", href=True):
    # get the value of the href attribute (the part link of the card)
    href = link["href"]
    # how each cards url start after the base_url and check if its the format wished
    if "/database/queens-blood/" in href:
        card_url = urljoin(base_url, href)
        # make the whole url for the card
        card_urls.append(card_url)
        # add the urls to a list to browse in later

# loop into the cards urtl to get their info


for card_url in card_urls:
    response = requests.get(card_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # div attribute in html where all stats
    stats_field = soup.find("div", id="sidebar-fields")

    stats = stats_field.find_all("div", class_="db-field")
    card_stats = {}
    for stat in stats:
        element = stat.find("h3")  # get the key
        sub_element = stat.find_all("span")  # get the value
        # put them into a dict
        card_stats[element.get_text(strip=True)] = sub_element[-1].get_text(strip=True)

    print(card_stats)
