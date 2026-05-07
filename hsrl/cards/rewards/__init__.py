"""
HSRL Quest Reward Card Definitions

Auto-registers quest rewards from bg_quest_rewards.json.
Quest rewards are granted when their associated quest is completed.

Note: Quests themselves are offered on Turn 4 and are auto-generated from
structured quest templates (EXAMPLE_QUEST serves as the standard example).
"""

import json
import os

from hsrl.core.enums import CardType, GameTag, Race, Rarity
from hsrl.core.card_db import register_card
from hsrl.cards.rewards.scripts import QUEST_SCRIPT_REGISTRY, REWARD_SCRIPT_REGISTRY

# ── Load reward data ─────────────────────────────────────────────────────────

_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
_rewards_path = os.path.join(_data_dir, "bg_quest_rewards.json")

try:
    with open(_rewards_path) as f:
        _rewards = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _rewards = []

_registered = 0

for reward_data in _rewards:
    card_id = reward_data["id"]
    name = reward_data.get("name", card_id)
    script_class = REWARD_SCRIPT_REGISTRY.get(card_id)

    register_card(
        card_id=card_id,
        name=name,
        text="",
        cardtype=CardType.REWARD,
        race=Race.INVALID,
        tech_level=1,
        rarity=Rarity.COMMON,
        script_class=script_class,
    )
    _registered += 1

# ── Standard Example Quest ───────────────────────────────────────────────────

register_card(
    card_id="EXAMPLE_QUEST",
    name="Example Quest",
    text="Quest: Buy 3 minions.",
    cardtype=CardType.QUEST,
    race=Race.INVALID,
    tech_level=1,
    rarity=Rarity.COMMON,
    tags={
        GameTag.QUEST_TARGET: 3,
    },
    script_class=QUEST_SCRIPT_REGISTRY.get("EXAMPLE_QUEST"),
)

# ── Standard Example Quest Reward ────────────────────────────────────────────

register_card(
    card_id="EXAMPLE_QUEST_REWARD",
    name="Example Quest Reward",
    text="Reward: Give a random friendly minion +4/+4.",
    cardtype=CardType.REWARD,
    race=Race.INVALID,
    tech_level=1,
    rarity=Rarity.COMMON,
    script_class=REWARD_SCRIPT_REGISTRY.get("EXAMPLE_QUEST_REWARD"),
)
