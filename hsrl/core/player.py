"""
HSRL Player Class

Represents a Battlegrounds player (hero).
Manages health, armor, gold, tavern tier, board, hand, and hero power.
"""

from typing import Any, Dict, List, Optional

from hsrl.core.entity import BaseEntity, CardData
from hsrl.core.enums import GameTag, Zone, State, PlayState


class Player(BaseEntity):
    """
    A Battlegrounds player.
    Inherits from BaseEntity because a hero is also an entity with tags.
    """

    def __init__(self, data: CardData, game=None):
        super().__init__(data, game)
        self.board: List["Minion"] = []       # Minions in play (combat board)
        self.hand: List["Minion"] = []        # Minions/spells in hand
        self.tavern: List["Minion"] = []      # Bob's tavern offerings
        self.graveyard: List["Minion"] = []   # Dead minions this combat
        self._start_of_combat_board: List["Minion"] = []  # Snapshot for combat
        self.auras: list = []                    # List[GlobalAura] — persistent "this game" auras
        self.tavern_buffs: list = []             # List[TavernBuff] — buffs applied to future tavern offerings
        self.trinkets: list = []                # List[Trinket] — purchased trinket items
        self._pending_trinket_offers: list[str] = []  # Card IDs offered for selection
        self.active_quest: Optional["Quest"] = None  # Current active quest
        self.rewards: list = []                 # List[QuestReward] — unlocked quest rewards

        # ── Buddy system ──
        self._buddy_card_id: Optional[str] = None  # Hero-specific buddy card
        self._buddy_meter: int = 0                  # Progress toward buddy (0-100)
        self._buddy_meter_max: int = 100             # Meter target value
        self._buddy_cost: int = 3                    # Gold cost to purchase buddy
        self._buddy_obtained: bool = False           # Buddy already acquired
        self._buddy_golden_available: bool = False   # Golden buddy upgrade available

        # Default player tags
        self.set_tag(GameTag.GOLD, 0)
        self.set_tag(GameTag.MAX_GOLD, 99)
        self.set_tag(GameTag.TAVERN_TIER, 1)
        self.set_tag(GameTag.TAVERN_UPGRADE_COST, 5)
        self.set_tag(GameTag.HEALTH, 30)
        self.set_tag(GameTag.MAX_HEALTH, 30)
        if GameTag.ARMOR not in self.tags:
            self.set_tag(GameTag.ARMOR, 0)
        self.set_tag(GameTag.PLAYSTATE, PlayState.PLAYING)
        self.set_tag(GameTag.HERO_POWER_USED, False)
        self.set_tag(GameTag.PLAGUERUNNER_SCALE, 3)

    @property
    def health(self) -> int:
        return self.get_tag(GameTag.HEALTH, 30)

    @health.setter
    def health(self, value: int) -> None:
        self.set_tag(GameTag.HEALTH, max(0, value))
        if self.health <= 0:
            self.set_tag(GameTag.PLAYSTATE, PlayState.LOST)

    @property
    def armor(self) -> int:
        return self.get_tag(GameTag.ARMOR, 0)

    @armor.setter
    def armor(self, value: int) -> None:
        self.set_tag(GameTag.ARMOR, value)

    @property
    def gold(self) -> int:
        return self.get_tag(GameTag.GOLD, 0)

    @gold.setter
    def gold(self, value: int) -> None:
        self.set_tag(GameTag.GOLD, max(0, value))

    @property
    def tavern_tier(self) -> int:
        return self.get_tag(GameTag.TAVERN_TIER, 1)

    @tavern_tier.setter
    def tavern_tier(self, value: int) -> None:
        self.set_tag(GameTag.TAVERN_TIER, min(7, max(1, value)))

    @property
    def is_alive(self) -> bool:
        return self.get_tag(GameTag.PLAYSTATE, PlayState.PLAYING) == PlayState.PLAYING

    @property
    def hero_power_cost(self) -> int:
        return self.get_tag(GameTag.HERO_POWER_COST, 0)

    @property
    def secondary_hero_power_cost(self) -> int:
        return self.get_tag(GameTag.SECONDARY_HERO_POWER_COST, 0)

    @property
    def has_secondary_hero_power(self) -> bool:
        hp_id = self.get_tag(GameTag.SECONDARY_HERO_POWER_ID, 0)
        return bool(hp_id and hp_id != 0)

    # ── Board helpers ──

    def get_board_minions(self) -> List["Minion"]:
        """Return living minions on the board."""
        return [m for m in self.board if not m.dead]

    def get_board_count(self) -> int:
        return len(self.get_board_minions())

    def get_hand_minions(self) -> List["Minion"]:
        return [m for m in self.hand]

    def get_tavern_minions(self) -> List["Minion"]:
        return [m for m in self.tavern]

    def get_global_aura_bonus(self, minion: "Minion") -> tuple:
        """Return (atk_bonus, health_bonus) from global auras matching this minion."""
        from hsrl.core.enums import Race
        atk_bonus = 0
        health_bonus = 0
        minion_race = minion.get_tag(GameTag.RACE, Race.NONE)
        for aura in self.auras:
            if aura.race_filter is None:
                atk_bonus += aura.atk
                health_bonus += aura.health
            elif minion_race == aura.race_filter:
                atk_bonus += aura.atk
                health_bonus += aura.health
            elif minion_race == Race.ALL:
                # "All" type minions match any race filter
                atk_bonus += aura.atk
                health_bonus += aura.health
        return atk_bonus, health_bonus

    @property
    def board_hash(self) -> int:
        """Order-independent hash of board state for REARRANGE gating.

        Captures: minion count, atk/health, and combat keywords.
        Changes after any buff, death, summon, or purchase — but NOT after
        a pure position swap.
        """
        living = [m for m in self.board if not m.dead]
        parts = []
        for m in living:
            keywords = (
                int(m.has_tag(GameTag.TAUNT)),
                int(m.has_tag(GameTag.DIVINE_SHIELD)),
                int(m.has_tag(GameTag.POISONOUS)),
                int(m.has_tag(GameTag.VENOMOUS)),
                int(m.has_tag(GameTag.REBORN)),
                int(m.has_tag(GameTag.WINDFURY)),
                int(m.has_tag(GameTag.CLEAVE)),
                int(m.has_tag(GameTag.GOLDEN)),
            )
            parts.append((m.atk, m.health, keywords))
        return hash(frozenset(parts))

    def __repr__(self) -> str:
        return f"<Player {self.get_tag(GameTag.NAME, 'Unknown')} HP={self.health} Gold={self.gold}>"


def random_heroes(count: int = 8, exclude: list[str] | None = None,
                  card_db=None) -> list[str]:
    """Pick random hero card IDs from the card database.

    Args:
        count: Number of heroes to return.
        exclude: Hero IDs to exclude from selection.
        card_db: CardDB instance (uses global CARDS if None).
    """
    import random
    from hsrl.core.card_db import CARDS
    from hsrl.core.enums import CardType

    db = card_db or CARDS
    exclude_set = set(exclude or [])
    hero_ids = [
        cid for cid, data in db._cards.items()
        if getattr(data, 'cardtype', None) is not None
        and data.cardtype == CardType.HERO
        and not cid.startswith("EXAMPLE")
        and cid not in exclude_set
    ]
    if len(hero_ids) < count:
        hero_ids = [
            cid for cid, data in db._cards.items()
            if getattr(data, 'cardtype', None) is not None
            and data.cardtype == CardType.HERO
            and cid not in exclude_set
        ]
    return random.sample(hero_ids, min(count, len(hero_ids)))
