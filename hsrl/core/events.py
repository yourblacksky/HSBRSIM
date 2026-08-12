"""
HSRL Event System

Events are broadcast by Actions and listened to by card scripts.
This follows the philosophy: every mechanism must be registered and triggered
through a standardized event pipeline.

Card scripts declare event listeners like:
    events = [EventListener("AFTER_ATTACK", self_controller, my_effect)]
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, List, Optional

from hsrl.core.enums import GameTag


class EventScope(str, Enum):
    """Where a listener is allowed to observe an event."""

    AUTO = "auto"
    OWNER = "owner"
    COMBAT_PAIR = "combat_pair"
    GLOBAL = "global"


class EventListener:
    """
    Listens for a specific event and triggers an action when matched.

    Attributes:
        event_name: The event string to listen for (e.g. "DEATH", "AFTER_ATTACK")
        condition: Optional callable (event_args -> bool) to filter events
        action: The Action to trigger when the event fires and condition passes
        once: If True, remove after first trigger
    """

    def __init__(
        self,
        event_name: str,
        action: "Action",
        condition: Optional[Callable[[Any], bool]] = None,
        once: bool = False,
        scope: EventScope = EventScope.AUTO,
    ):
        self.event_name = event_name
        self.action = action
        self.condition = condition
        self.once = once
        self.scope = EventScope(scope)

    def check(self, event_name: str, event_args: tuple) -> bool:
        if event_name != self.event_name:
            return False
        if self.condition is not None:
            return self.condition(*event_args)
        return True

    def __repr__(self) -> str:
        return f"EventListener({self.event_name})"


# ── Standard Event Constants ──
# These are the strings broadcast by the Game engine.

# Lifecycle
ENTITY_CREATED = "ENTITY_CREATED"
ZONE_CHANGE = "ZONE_CHANGE"

# Combat
BEFORE_ATTACK = "BEFORE_ATTACK"
AFTER_ATTACK = "AFTER_ATTACK"
BEFORE_HIT = "BEFORE_HIT"
AFTER_HIT = "AFTER_HIT"
DAMAGE = "DAMAGE"
HEAL = "HEAL"
DIVINE_SHIELD_LOST = "DIVINE_SHIELD_LOST"
POISON_KILL = "POISON_KILL"
VENOM_KILL = "VENOM_KILL"

# Death & Summon
BEFORE_DESTROY = "BEFORE_DESTROY"
DEATH = "DEATH"
DEATHRATTLE_TRIGGER = "DEATHRATTLE_TRIGGER"
REBORN_TRIGGER = "REBORN_TRIGGER"
SUMMON = "SUMMON"

# Mechanics
BUFF = "BUFF"
KEYWORD_GAINED = "KEYWORD_GAINED"
KEYWORD_LOST = "KEYWORD_LOST"
AVENGE_TRIGGER = "AVENGE_TRIGGER"
START_OF_COMBAT = "START_OF_COMBAT"
END_OF_COMBAT = "END_OF_COMBAT"

# Economy / Tavern
TAVERN_UPGRADED = "TAVERN_UPGRADED"
GOLD_SPENT = "GOLD_SPENT"
GOLD_GAINED = "GOLD_GAINED"
MINION_BOUGHT = "MINION_BOUGHT"
MINION_SOLD = "MINION_SOLD"

# Turn
TURN_BEGIN = "TURN_BEGIN"
TURN_END = "TURN_END"
RECRUIT_BEGIN = "RECRUIT_BEGIN"
RECRUIT_END = "RECRUIT_END"
COMBAT_BEGIN = "COMBAT_BEGIN"
COMBAT_END = "COMBAT_END"

# Improve / Scaling
ELEMENTAL_PLAYED = "ELEMENTAL_PLAYED"
TAVERN_SPELL_CAST = "TAVERN_SPELL_CAST"
BATTLECRY_TRIGGER = "BATTLECRY_TRIGGER"

# Tavern
TAVERN_REFRESH = "TAVERN_REFRESH"

# Player
PLAYER_DAMAGE_TAKEN = "PLAYER_DAMAGE_TAKEN"
PLAYER_DEFEATED = "PLAYER_DEFEATED"

# Hero
HERO_POWER_USED = "HERO_POWER_USED"

# Triple
TRIPLE_COMBINED = "TRIPLE_COMBINED"
TRIPLE_REWARD_DISCOVERED = "TRIPLE_REWARD_DISCOVERED"

# Spell
DISCOVER_SPELL = "DISCOVER_SPELL"

# Tavern Freeze
TAVERN_MINION_FROZEN = "TAVERN_MINION_FROZEN"

# Silence
SILENCED = "SILENCED"

# Consume
FODDER_CONSUME = "FODDER_CONSUME"

# ── Step 2 new events ──
MINION_DAMAGED = "MINION_DAMAGED"
MINION_ATTACKED = "MINION_ATTACKED"
BLOOD_GEM_PLAYED = "BLOOD_GEM_PLAYED"
MINION_PLAYED = "MINION_PLAYED"
ADD_TO_HAND = "ADD_TO_HAND"       # broadcast by AddToHand.do() (already existed)
MAGNETIZED = "MAGNETIZED"           # broadcast by AttachMagnetic.do()
PRE_COMBAT_CLEANUP = "PRE_COMBAT_CLEANUP"  # before temp buff removal

# ── Spellcraft ──
SPELLCRAFT_CAST = "SPELLCRAFT_CAST"  # when a spellcraft spell is played from hand

# ── Trinket events ──
SPELL_CAST_ON_MINION = "SPELL_CAST_ON_MINION"  # when a spell targets a specific minion
FIRST_MINION_KILLED_IN_COMBAT = "FIRST_MINION_KILLED_IN_COMBAT"  # first friendly minion killed
FIRST_MINION_SUMMONED_IN_COMBAT = "FIRST_MINION_SUMMONED_IN_COMBAT"  # first friendly summoned
LAST_FRIENDLY_DEATH = "LAST_FRIENDLY_DEATH"  # last friendly minion dies
MINION_OVERFLOW = "MINION_OVERFLOW"  # summon failed due to full board
