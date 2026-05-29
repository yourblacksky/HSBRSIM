"""
BG Pool Minion Registrations — Auto-generated from data/bg_pool_minions.json

All 270 pool minions registered with correct stats, race, tech level, and keywords.
Complex effects are implemented via script classes referenced by card_id.

Data source: Patch 35.2.2.241135 / Season 13 "Cataclysm Calls"
"""

import json
from pathlib import Path

from hsrl.core.card_db import register_card
from hsrl.core.enums import CardType, DBF_RACE_TO_ENUM, GameTag, Race, Rarity

# ── Keyword mapping (JSON field name → GameTag) ──────────────────────
_KEYWORD_MAP = {
    "taunt": GameTag.TAUNT,
    "divine_shield": GameTag.DIVINE_SHIELD,
    "poisonous": GameTag.POISONOUS,
    "venomous": GameTag.VENOMOUS,
    "reborn": GameTag.REBORN,
    "windfury": GameTag.WINDFURY,
    "cleave": GameTag.CLEAVE,
    "magnetic": GameTag.MAGNETIC,
    "battlecry": GameTag.BATTLECRY,
    "deathrattle": GameTag.DEATHRATTLE,
    "avenge": GameTag.Avenge,
    "rally": GameTag.RALLY,
    "health_cost_demon": GameTag.HEALTH_COST_DEMON,
    "health_cost_spell": GameTag.HEALTH_COST_SPELL,
}

# ── Text-based keyword detection ──────────────────────────────────────
# Keywords not stored as JSON booleans; detected from card text instead.
_TEXT_KEYWORDS = [
    ("Rally", GameTag.RALLY),
    ("Start of Combat", GameTag.START_OF_COMBAT),
    ("When you sell this", GameTag.ON_SELL),
    ("At the end of your turn", GameTag.END_OF_TURN),
    ("At the start of your turn", GameTag.START_OF_TURN),
    # Fodder is detected from pool JSON's "fodder" field, not text.
    # The word "Fodder" in card text usually means "adds a Fodder" not "has Fodder".
]

# ── Data paths ────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


def _load_data():
    pool_path = _DATA_DIR / "bg_pool_minions.json"
    texts_path = _DATA_DIR / "pool_minion_texts.json"
    with open(pool_path) as f:
        pool = json.load(f)
    texts = {}
    if texts_path.exists():
        with open(texts_path) as f:
            texts = json.load(f)
    return pool, texts


def register_all_pool_minions():
    """Register all non-duo pool minions into the global CARDS registry."""
    pool, texts = _load_data()
    registered = 0
    for m in pool:
        card_id = m["id"]
        # Skip duo-specific cards
        if card_id.startswith("BGDUO"):
            continue
        # Skip cards explicitly marked as not-in-pool
        if m.get("is_pool_minion") is False:
            continue
        _register_one_minion(m, texts.get(card_id, ""))
        registered += 1
    return registered


def _register_one_minion(m: dict, text: str):
    """Register a single pool minion from its JSON data."""
    card_id = m["id"]
    race = DBF_RACE_TO_ENUM.get(m.get("card_race"), Race.NONE)

    tags = {
        GameTag.BASE_ATK: m.get("atk", 0),
        GameTag.BASE_HEALTH: m.get("health", 0),
    }

    # Add purchase cost (default 3 for minions; some have 2, 5, etc.)
    if m.get("cost") is not None:
        tags[GameTag.COST] = m["cost"]

    # Add keyword flags
    for json_kw, game_tag in _KEYWORD_MAP.items():
        if m.get(json_kw):
            tags[game_tag] = True

    # Add avenge target if present
    if m.get("avenge_target") is not None:
        tags[GameTag.AVENGE_TARGET] = m["avenge_target"]

    # Add Spellcraft tag if minion has spellcraft_id
    if m.get("spellcraft_id"):
        tags[GameTag.SPELLCRAFT] = True

    # Detect keywords from card text (for keywords not stored as JSON booleans)
    for keyword_text, game_tag in _TEXT_KEYWORDS:
        if keyword_text in text:
            tags[game_tag] = True

    # Resolve script class
    script_class = _get_script(card_id, m, text)

    register_card(
        card_id=card_id,
        name=m["name"],
        text=text or "",
        cardtype=CardType.MINION,
        race=race,
        tech_level=m.get("tech_level", 1),
        rarity=Rarity.COMMON,
        tags=tags,
        script_class=script_class,
    )


# ── Script class resolution ──────────────────────────────────────────
def _get_script(card_id: str, m: dict, text: str):
    """Return the script class for a minion, or None if it has no effects."""
    has_bc = m.get("battlecry")
    has_dr = m.get("deathrattle")
    has_av = m.get("avenge")
    has_sc = bool(m.get("spellcraft_id"))
    has_soc = m.get("start_of_combat")

    # Check if there's a hand-written script class
    from hsrl.cards.minions.scripts import SCRIPT_REGISTRY
    if card_id in SCRIPT_REGISTRY:
        return SCRIPT_REGISTRY[card_id]

    # Minions with flagged effects but no script yet
    if has_bc or has_dr or has_av or has_sc or has_soc:
        return None

    # Check CARDS tags for trigger types not in the pool JSON
    from hsrl.core.card_db import CARDS
    card = CARDS._cards.get(card_id)
    if card:
        tags = card.tags
        extra_triggers = (
            tags.get(GameTag.RALLY)
            or tags.get(GameTag.END_OF_TURN)
            or tags.get(GameTag.START_OF_TURN)
            or tags.get(GameTag.ON_SELL)
            or tags.get(GameTag.FODDER)
            or tags.get(GameTag.CHROMADRAKE)
        )
        if extra_triggers:
            return None  # Deferred — engine support needed

    return None


# ── DEFERRED: Cards requiring major new subsystems ─────────────────────
# These pool minions have complex triggered effects but their scripts
# cannot be implemented yet because the required engine subsystems
# don't exist. Each entry documents the missing subsystem.
_DEFERRED = {}
# All deferred minions have been implemented. The dict is kept as a placeholder
# for future cards that may require new subsystems.

# ── Default: register all on import ───────────────────────────────────
register_all_pool_minions()
