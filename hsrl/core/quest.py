"""
HSRL Quest and QuestReward Entities

Quests are offered on Turn 4. Players choose from 3 pairs of quest+reward.
Each quest has a target (e.g. "Buy 6 minions") and a reward that unlocks on completion.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from hsrl.core.entity import BaseEntity
from hsrl.core.enums import GameTag, CardType

if TYPE_CHECKING:
    from hsrl.core.game import Game


class QuestReward(BaseEntity):
    """A reward that activates when its associated quest is completed."""

    def __init__(self, data, game: Optional[Game] = None):
        super().__init__(data, game)
        self.set_tag(GameTag.CARDTYPE, CardType.REWARD)

    @property
    def start_of_combat(self):
        if self.data.scripts and hasattr(self.data.scripts, 'start_of_combat'):
            return self.data.scripts.start_of_combat
        return None

    @property
    def end_of_turn(self):
        if self.data.scripts and hasattr(self.data.scripts, 'end_of_turn'):
            return self.data.scripts.end_of_turn
        return None

    @property
    def start_of_turn(self):
        if self.data.scripts and hasattr(self.data.scripts, 'start_of_turn'):
            return self.data.scripts.start_of_turn
        return None


class Quest(BaseEntity):
    """A quest that tracks progress and unlocks a reward on completion."""

    def __init__(self, data, game=None):
        super().__init__(data, game)
        self.set_tag(GameTag.CARDTYPE, CardType.QUEST)
        self.set_tag(GameTag.QUEST_PROGRESS, 0)

    @property
    def progress(self) -> int:
        return self.get_tag(GameTag.QUEST_PROGRESS, 0)

    @progress.setter
    def progress(self, value: int) -> None:
        self.set_tag(GameTag.QUEST_PROGRESS, value)

    @property
    def target(self) -> int:
        return self.get_tag(GameTag.QUEST_TARGET, 1)

    @target.setter
    def target(self, value: int) -> None:
        self.set_tag(GameTag.QUEST_TARGET, value)

    @property
    def is_complete(self) -> bool:
        return self.progress >= self.target

    @property
    def reward_data(self):
        """Return the associated QuestReward CardData, if stored."""
        return self.get_tag(GameTag.REWARD_UNLOCKED, None)

    def increment_progress(self, amount: int = 1) -> bool:
        """Increment progress. Returns True if quest just completed."""
        if self.is_complete:
            return False
        self.progress = min(self.target, self.progress + amount)
        return self.is_complete

    def __repr__(self) -> str:
        name = self.get_tag(GameTag.NAME, "Unknown Quest")
        return f"<Quest {name} progress={self.progress}/{self.target}>"


# Quest type definitions (type → (event_name, default_target))
QUEST_TYPE_MAP = {
    "PLAY_BATTLECRY": ("BATTLECRY_TRIGGER", 4),
    "SPEND_GOLD": ("GOLD_SPENT", 20),
    "BUY_MINIONS": ("MINION_BOUGHT", 5),
    "TRIGGER_DEATHRATTLE": ("DEATHRATTLE_TRIGGER", 5),
    "REFRESH_TAVERN": ("TAVERN_REFRESH", 8),
    "SELL_MINIONS": ("MINION_SOLD", 4),
}
