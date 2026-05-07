"""
HSRL Anomaly Card Definitions

Auto-registers anomalies from bg_anomalies.json.
Anomalies are game-wide modifiers applied at the start of a match.
"""

import json
import os

from hsrl.core.enums import CardType, GameTag, Race, Rarity
from hsrl.core.card_db import register_card
from hsrl.cards.anomalies.scripts import ANOMALY_SCRIPT_REGISTRY

# ── Load anomaly data ────────────────────────────────────────────────────────

_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
_anomalies_path = os.path.join(_data_dir, "bg_anomalies.json")

try:
    with open(_anomalies_path) as f:
        _anomalies = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _anomalies = []

_registered = 0

for anomaly_data in _anomalies:
    card_id = anomaly_data["id"]
    name = anomaly_data.get("name", card_id)
    script_class = ANOMALY_SCRIPT_REGISTRY.get(card_id)

    register_card(
        card_id=card_id,
        name=name,
        text="",
        cardtype=CardType.ANOMALY,
        race=Race.INVALID,
        tech_level=1,
        rarity=Rarity.COMMON,
        script_class=script_class,
    )
    _registered += 1

# ── Standard Example Anomaly ─────────────────────────────────────────────────

register_card(
    card_id="EXAMPLE_ANOMALY",
    name="Example Anomaly",
    text="Start of Game: All players start with 10 Gold.",
    cardtype=CardType.ANOMALY,
    race=Race.INVALID,
    tech_level=1,
    rarity=Rarity.COMMON,
    script_class=ANOMALY_SCRIPT_REGISTRY.get("EXAMPLE_ANOMALY"),
)
