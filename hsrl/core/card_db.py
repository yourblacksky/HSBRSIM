"""
HSRL Card Database

Registry for all card definitions.
Philosophy:
  1. Read natural language card text
  2. Convert to structured format (CardData + script class)
  3. Register in the database
  4. Only after standard examples are tested, add real cards
"""

from typing import Any, Dict, Optional, Type

from hsrl.core.entity import CardData
from hsrl.core.enums import CardType, GameTag, Race, Rarity


class CardDB:
    """In-memory registry of all card definitions."""

    def __init__(self):
        self._cards: Dict[str, CardData] = {}
        self._scripts: Dict[str, Type] = {}

    def register(
        self,
        card_id: str,
        name: str,
        text: str = "",
        cardtype: CardType = CardType.MINION,
        race: Optional[Race] = None,
        tech_level: int = 1,
        rarity: Rarity = Rarity.COMMON,
        tags: Optional[Dict[GameTag, Any]] = None,
        script_class: Optional[Type] = None,
    ) -> None:
        """
        Register a card definition.

        Args:
            card_id: Unique identifier (e.g. "BGS_001")
            name: Display name
            text: Natural language card text (from the game)
            cardtype: Type of card
            race: Minion tribe (if applicable)
            tech_level: Tavern tier (1-7)
            rarity: Card rarity
            tags: Dictionary of GameTag overrides (stats, keywords, etc.)
            script_class: Python class containing the card's behavior scripts
        """
        merged_tags = tags or {}
        # Extract base stats from tags if present
        data = CardData(
            id=card_id,
            name=name,
            text=text,
            cardtype=cardtype,
            race=race,
            tech_level=tech_level,
            rarity=rarity,
            tags=merged_tags,
            scripts=script_class,
        )
        self._cards[card_id] = data
        if script_class is not None:
            self._scripts[card_id] = script_class

    def get(self, card_id: str) -> Optional[CardData]:
        """Retrieve card data by id."""
        return self._cards.get(card_id)

    def get_script(self, card_id: str) -> Optional[Type]:
        """Retrieve script class by id."""
        return self._scripts.get(card_id)

    def create_minion(self, card_id: str, game=None):
        """Factory: create a Minion instance from a card id."""
        from hsrl.core.minion import Minion
        data = self.get(card_id)
        if data is None:
            raise KeyError(f"Unknown card id: {card_id}")
        return Minion(data, game=game)

    def create_spell(self, card_id: str, game=None):
        """Factory: create a Spell instance from a card id."""
        from hsrl.core.spell import Spell
        data = self.get(card_id)
        if data is None:
            raise KeyError(f"Unknown card id: {card_id}")
        return Spell(data, game=game)

    def create_trinket(self, card_id: str, game=None):
        """Factory: create a Trinket instance from a card id."""
        from hsrl.core.trinket import Trinket
        data = self.get(card_id)
        if data is None:
            raise KeyError(f"Unknown card id: {card_id}")
        return Trinket(data, game=game)

    def create_quest(self, card_id: str, game=None):
        """Factory: create a Quest instance from a card id."""
        from hsrl.core.quest import Quest
        data = self.get(card_id)
        if data is None:
            raise KeyError(f"Unknown card id: {card_id}")
        return Quest(data, game=game)

    def create_quest_reward(self, card_id: str, game=None):
        """Factory: create a QuestReward instance from a card id."""
        from hsrl.core.quest import QuestReward
        data = self.get(card_id)
        if data is None:
            raise KeyError(f"Unknown card id: {card_id}")
        return QuestReward(data, game=game)

    def create_anomaly(self, card_id: str, game=None):
        """Factory: create an Anomaly instance from a card id."""
        from hsrl.core.anomaly import Anomaly
        data = self.get(card_id)
        if data is None:
            raise KeyError(f"Unknown card id: {card_id}")
        return Anomaly(data, game=game)

    def all_ids(self):
        return list(self._cards.keys())

    def __contains__(self, card_id: str) -> bool:
        return card_id in self._cards


# Global singleton
CARDS = CardDB()


def register_card(
    card_id: str,
    name: str,
    text: str = "",
    cardtype: CardType = CardType.MINION,
    race: Optional[Race] = None,
    tech_level: int = 1,
    rarity: Rarity = Rarity.COMMON,
    tags: Optional[Dict[GameTag, Any]] = None,
    script_class: Optional[Type] = None,
) -> None:
    """Convenience wrapper for CARDS.register()."""
    CARDS.register(
        card_id=card_id,
        name=name,
        text=text,
        cardtype=cardtype,
        race=race,
        tech_level=tech_level,
        rarity=rarity,
        tags=tags,
        script_class=script_class,
    )
