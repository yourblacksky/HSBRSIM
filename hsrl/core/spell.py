"""
HSRL Spell Entity

Represents a Tavern Spell card. Unlike Minions, spells have no ATK,
Health, or race — they are purchased from Bob's Tavern, held in hand,
and cast to trigger effects.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from hsrl.core.entity import BaseEntity, CardData
from hsrl.core.enums import GameTag

if TYPE_CHECKING:
    from hsrl.core.game import Game


class Spell(BaseEntity):
    """A purchasable/castable Tavern Spell.

    Inherits from BaseEntity (not Minion) — spells lack combat stats.
    Key tags: COST, TECH_LEVEL, CARDTYPE=SPELL.
    """

    def __init__(self, data: CardData, game: Optional[Game] = None):
        super().__init__(data, game)
        # Spells don't need the combat-related properties (ATK/Health/race)
        # that Minion has. All behavior is via tags and engine methods.

    @property
    def cost(self) -> int:
        """Gold cost to buy this spell from the tavern."""
        return self.get_tag(GameTag.COST, 0)

    @property
    def tech_level(self) -> int:
        """Tavern tier this spell belongs to."""
        return self.get_tag(GameTag.TECH_LEVEL, 1)

    def __repr__(self) -> str:
        name = self.get_tag(GameTag.NAME, "Spell")
        return f"<Spell {name} cost={self.cost}>"
