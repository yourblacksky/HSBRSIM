"""
HSRL Anomaly Entity

Anomalies are game-wide modifiers applied at the start of a game.
They affect all players equally and persist for the entire game.

Examples:
  - Money Match (start with 10 gold)
  - Big League (only Tiers 3-6 available)
  - Oops All Beasts! (only Beast minions in pool)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hsrl.core.entity import BaseEntity
from hsrl.core.enums import GameTag, CardType

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.actions import Action


class Anomaly(BaseEntity):
    """A game-wide anomaly that modifies rules for all players."""

    def __init__(self, data, game=None):
        super().__init__(data, game)
        self.set_tag(GameTag.CARDTYPE, CardType.ANOMALY)

    # ── Script hooks ──

    @property
    def on_apply(self):
        """Called once when the anomaly is applied at game start."""
        return self._call_script_method("on_apply")

    @property
    def start_of_combat(self):
        """Called for each player at start of combat."""
        return self._call_script_method("start_of_combat")

    @property
    def on_start_game(self):
        """Called once when the game starts (before turn 1)."""
        return self._call_script_method("on_start_game")

    def __repr__(self) -> str:
        name = self.get_tag(GameTag.NAME, "Unknown Anomaly")
        return f"<Anomaly {name}>"
