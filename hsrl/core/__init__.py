"""
HSRL Core Module

Contains the fundamental engine: entities, actions, events, game loop, and enums.
"""

from hsrl.core.enums import (
    CardType,
    GameTag,
    PlayState,
    Race,
    Rarity,
    State,
    Step,
    Zone,
    KEYWORD_TAGS,
    STAT_TAGS,
)
from hsrl.core.entity import BaseEntity, CardData
from hsrl.core.minion import Minion
from hsrl.core.player import Player
from hsrl.core.game import Game
from hsrl.core.card_db import CardDB, CARDS, register_card
from hsrl.core.events import EventListener

__all__ = [
    "CardType",
    "GameTag",
    "PlayState",
    "Race",
    "Rarity",
    "State",
    "Step",
    "Zone",
    "KEYWORD_TAGS",
    "STAT_TAGS",
    "BaseEntity",
    "CardData",
    "Minion",
    "Player",
    "Game",
    "CardDB",
    "CARDS",
    "register_card",
    "EventListener",
]
