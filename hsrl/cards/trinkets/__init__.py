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

# Patch 35.4.2 Battlegrounds trinket pool updates.
# Keep this as a registration-layer override until the upstream generated
# bg_trinkets.json cache is regenerated from current CardDefs.
_REMOVED_PATCH_35_4_2 = {
    "BG30_MagicItem_433",   # Alliance Keychain
    "BG30_MagicItem_433t",  # Alliance Keychain
    "BG32_MagicItem_806",   # Battlecruiser Portrait
    "BG32_MagicItem_954",   # Auric Offering
    "BG30_MagicItem_978",   # Blingtron's Sunglasses
    "BG32_MagicItem_417",   # Tarecgosa Sticker
    "BG35_MagicItem_303",   # Skipper Portrait
    "BG35_MagicItem_849",   # Cloud Serpent Horn
    "BG35_MagicItem_155",   # Felburned Ledger
    "BG30_MagicItem_548",   # Glowscale Portrait
    "BG35_MagicItem_310",   # Radio Star Portrait
    "BG30_MagicItem_986",   # Peacebloom Candle
    "BG30_MagicItem_900t",  # Dragonwing Glider, Greater
    "BG32_MagicItem_282",   # Turbocharged Drill
}

_COST_OVERRIDES_PATCH_35_4_2 = {
    "BG35_MagicItem_152": 3,   # Demonic Tapestry
    "BG30_MagicItem_902": 1,   # Holy Mallet
    "BG32_MagicItem_831": 4,   # Sellemental Portrait
    "BG32_MagicItem_170": 1,   # Spell-powered Wrench
    "BG32_MagicItem_300": 2,   # Putricide Sticker
    "BG30_MagicItem_700": 1,   # Deathly Phylactery
    "BG32_MagicItem_822": 1,   # Bazaar Sticker
    "BG35_MagicItem_302": 0,   # Stormcoil Sticker
    "BG30_MagicItem_924t": 0,  # Booty Bay Brew, Greater
    "BG32_MagicItem_363": 4,   # Faerie Dragon Scale, Greater
    "BG32_MagicItem_998": 0,   # Behemoth Portrait, Greater
    "BG30_MagicItem_951": 1,   # Lava Lamp, Greater
    "BG30_MagicItem_993": 4,   # Pagle's Fishing Rod, Greater
    "BG35_MagicItem_742": 4,   # Accord-o-Tron Portrait, Greater
    "BG35_MagicItem_848t": 2,  # Egg of the Endtimes Portrait, Greater
    "BG35_MagicItem_842": 2,   # Egg of the Endtimes Portrait
    "BG35_MagicItem_840": 5,   # Chromatic Tear, Lesser
    "BG30_MagicItem_988": 2,   # Great Boar Sticker, Lesser
    "BG30_MagicItem_988t": 2,  # Great Boar Sticker, Greater
    "BG35_MagicItem_850": 3,   # Pocket Cyclone, Lesser
    "BG35_MagicItem_850t": 3,  # Pocket Cyclone, Greater
    "BG35_MagicItem_434": 2,   # Jewelry Box
    "BG30_MagicItem_442": 5,   # Blood Golem Sticker
    "BG35_MagicItem_752": 4,   # Young Murk-Eye Sticker
}

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
    if card_id in _REMOVED_PATCH_35_4_2:
        continue
    name = trinket_data.get("name", card_id)
    cost = _COST_OVERRIDES_PATCH_35_4_2.get(
        card_id,
        trinket_data.get("cost", 0),
    )
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

# ── Token cards referenced by trinket scripts ──────────────────────────────

_tokens = [
    ("BG26_813t", "The Goldenizer", "Make a friendly minion Golden.", CardType.SPELL),
    ("BG28_601", "Cloning Conch", "Discover a copy of a friendly minion.", CardType.SPELL),
    ("BG35_MagicItem_817t", "Duplicating Lens", "Get a copy of the first minion you summon each combat.", CardType.TRINKET),
]
for _tid, _tname, _ttext, _ttype in _tokens:
    if _tid not in [t["id"] for t in _trinkets]:
        token_script = TRINKET_SCRIPT_REGISTRY.get(_tid, None)
        register_card(
            card_id=_tid,
            name=_tname,
            text=_ttext,
            cardtype=_ttype,
            race=Race.INVALID,
            tech_level=1,
            rarity=Rarity.COMMON,
            tags={GameTag.COST: 0},
            script_class=token_script,
        )
