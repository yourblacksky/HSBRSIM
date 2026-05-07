"""
HSRL Trinket Entity

Trinkets are passive items offered to players on Turn 6 (Lesser) and Turn 9 (Greater).
They occupy one of two trinket slots and provide ongoing effects.

Attributes:
  - cost: Gold cost to purchase (0 for free trinkets)
  - tech_level: Tier for pool classification (Not used)
  - slot: 1 (Lesser) or 2 (Greater)
  - script hooks: start_of_combat, end_of_turn, on_buy, avenge, spellcraft
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hsrl.core.entity import BaseEntity
from hsrl.core.enums import GameTag, CardType

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.actions import Action


class Trinket(BaseEntity):
    """A trinket item that provides passive/triggered effects to its owner."""

    def __init__(self, data, game=None):
        super().__init__(data, game)
        self.set_tag(GameTag.CARDTYPE, CardType.TRINKET)

    @property
    def cost(self) -> int:
        return self.get_tag(GameTag.COST, 0)

    @cost.setter
    def cost(self, value: int) -> None:
        self.set_tag(GameTag.COST, value)

    # ── Script hooks (mirrors Minion/Spell pattern) ──

    @property
    def start_of_combat(self):
        return self._call_script_method("start_of_combat")

    @property
    def start_of_turn(self):
        return self._call_script_method("start_of_turn")

    @property
    def end_of_turn(self):
        return self._call_script_method("end_of_turn")

    @property
    def on_buy(self):
        return self._call_script_method("on_buy")

    @property
    def avenge(self):
        return self._call_script_method("avenge")

    @property
    def on_play(self):
        return self._call_script_method("on_play")

    @property
    def on_spend_gold(self):
        return self._call_script_method("on_spend_gold")

    def __repr__(self) -> str:
        name = self.get_tag(GameTag.NAME, "Unknown Trinket")
        return f"<Trinket {name} cost={self.cost}>"
