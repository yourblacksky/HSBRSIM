"""
HSRL Minion Class

Extends BaseEntity with minion-specific logic for Battlegrounds.
"""

from typing import Any, Dict, List, Optional

from hsrl.core.entity import BaseEntity, CardData
from hsrl.core.enums import GameTag, Zone


class Minion(BaseEntity):
    """
    A Battlegrounds minion.
    Lives on a Player's board during combat, or in hand/tavern during recruit.
    """

    def __init__(self, data: CardData, game=None):
        super().__init__(data, game)
        self.zone = Zone.SETASIDE
        # Initialize combat stats from card data base tags
        self.set_tag(GameTag.HEALTH, self.max_health)
        self.set_tag(GameTag.WINDFURY_ATTACKS, 0)
        self.set_tag(GameTag.DIVINE_SHIELD_INTACT, self.divine_shield)
        self.set_tag(GameTag.REBORN_USED, False)
        self.set_tag(GameTag.AVENGE_COUNTER, 0)
        self.set_tag(GameTag.EXHAUSTED, False)

    # ── Minion-specific properties ──

    @property
    def can_attack(self) -> bool:
        """Check if this minion can still attack this combat."""
        if self.dead:
            return False
        if self.atk <= 0:
            return False
        if self.has_tag(GameTag.EXHAUSTED):
            return False
        max_attacks = 2 if self.windfury else 1
        return self.get_tag(GameTag.WINDFURY_ATTACKS, 0) < max_attacks

    def reset_combat_state(self) -> None:
        """Reset transient combat state at start of combat."""
        self.set_tag(GameTag.WINDFURY_ATTACKS, 0)
        self.set_tag(GameTag.EXHAUSTED, False)
        if self.divine_shield:
            self.set_tag(GameTag.DIVINE_SHIELD_INTACT, True)

    def __repr__(self) -> str:
        name = self.get_tag(GameTag.NAME, "Unknown")
        golden = " [G]" if self.is_golden else ""
        return f"<Minion {name}{golden} {self.atk}/{self.health}>"
