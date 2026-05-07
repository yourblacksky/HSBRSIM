"""
HSRL Trinket Card Definitions

Auto-registers trinkets from bg_trinkets.json.
Trinkets are passive items offered on Turn 6 (Lesser) and Turn 9 (Greater).

Each trinket has:
  - cost: Gold cost to purchase
  - slot: 1 (Lesser) or 2 (Greater) — determined by offering turn
  - script_class: from TRINKET_SCRIPT_REGISTRY

Note: Most trinkets do not yet have scripts assigned.
"""

import json
import os

from hsrl.core.enums import CardType, GameTag, Race, Rarity
from hsrl.core.card_db import register_card
from hsrl.cards.trinkets.scripts import TRINKET_SCRIPT_REGISTRY, ExampleTrinketScript

# ── Load trinket data ──────────────────────────────────────────────────────

_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
_trinkets_path = os.path.join(_data_dir, "bg_trinkets.json")

try:
    with open(_trinkets_path) as f:
        _trinkets = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _trinkets = []

_registered_count = 0

# Load wiki text data
_texts_path = os.path.join(_data_dir, "pool_trinket_texts.json")
_trinket_texts = {}
try:
    with open(_texts_path) as f:
        _trinket_texts = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _trinket_texts = {}

for trinket_data in _trinkets:
    card_id = trinket_data["id"]
    name = trinket_data.get("name", card_id)
    cost = trinket_data.get("cost", 0)
    script_class = TRINKET_SCRIPT_REGISTRY.get(card_id)

    tags = {GameTag.COST: cost}

    # Avenge data
    if trinket_data.get("avenge"):
        tags[GameTag.Avenge] = True
        tags[GameTag.AVENGE_TARGET] = trinket_data["avenge"]

    # Spellcraft data
    if trinket_data.get("spellcraft_id"):
        tags[GameTag.SPELLCRAFT] = True

    # Wiki card text
    text = ""
    if card_id in _trinket_texts:
        text = _trinket_texts[card_id].get("text", "")

    register_card(
        card_id=card_id,
        name=name,
        text=text,
        cardtype=CardType.TRINKET,
        race=Race.INVALID,
        tech_level=1,
        rarity=Rarity.COMMON,
        tags=tags,
        script_class=script_class,
    )
    _registered_count += 1

# ── Standard example trinket (for testing) ─────────────────────────────────

register_card(
    card_id="EXAMPLE_TRINKET",
    name="Example Trinket",
    text="Start of Combat: Give your leftmost minion +1/+1.",
    cardtype=CardType.TRINKET,
    race=Race.INVALID,
    tech_level=1,
    rarity=Rarity.COMMON,
    tags={
        GameTag.COST: 0,
    },
    script_class=ExampleTrinketScript,
)
