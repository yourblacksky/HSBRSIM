"""
HSRL Entity Base Classes

All game objects (minions, heroes, spells) inherit from BaseEntity.
Properties are stored in a tag dictionary and accessed via descriptors.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from hsrl.core.enums import GameTag, Race, Zone

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


class BaseEntity:
    """
    Root class for all game objects.

    Every visible property is stored in `tags` (a dict mapping GameTag -> value).
    Subclasses define typed property accessors that read from tags.
    """

    def __init__(self, data: "CardData", game: Optional["Game"] = None):
        self.data = data                          # CardData template (immutable)
        self.game: Optional["Game"] = game        # Parent game
        self.controller: Optional["Player"] = None  # Owning player
        self.uuid = uuid.uuid4().hex[:16]         # Runtime unique id
        self.tags: Dict[GameTag, Any] = {}        # All visible state lives here
        self._events: List[Any] = []              # Registered event listeners
        self._buffs: List[Any] = []               # Active buffs/enchantments
        self._script_overrides: Dict[str, Any] = {}  # Per-instance script method overrides

        # Initialize base tags from card data
        for tag, value in data.tags.items():
            self.tags[tag] = value

        self.tags[GameTag.CARD_ID] = data.id
        self.tags[GameTag.NAME] = data.name
        self.tags[GameTag.TEXT] = data.text
        self.tags[GameTag.CARDTYPE] = data.cardtype
        self.tags[GameTag.RACE] = data.race
        self.tags[GameTag.TECH_LEVEL] = data.tech_level
        self.tags[GameTag.RARITY] = data.rarity
        self.tags[GameTag.ZONE] = Zone.INVALID
        self.tags[GameTag.ZONE_POSITION] = 0

    # ── Tag access helpers ──

    def get_tag(self, tag: GameTag, default: Any = 0) -> Any:
        """Get tag value, returning default if missing."""
        return self.tags.get(tag, default)

    def set_tag(self, tag: GameTag, value: Any) -> None:
        """Set tag value directly."""
        self.tags[tag] = value

    def has_tag(self, tag: GameTag) -> bool:
        """Check if boolean tag is truthy."""
        return bool(self.tags.get(tag, False))

    def clear_tag(self, tag: GameTag) -> None:
        """Remove a tag."""
        self.tags.pop(tag, None)

    # ── Properties (typed accessors) ──

    @property
    def entity_id(self) -> int:
        return self.get_tag(GameTag.ENTITY_ID, 0)

    @entity_id.setter
    def entity_id(self, value: int) -> None:
        self.set_tag(GameTag.ENTITY_ID, value)

    @property
    def zone(self) -> Zone:
        return Zone(self.get_tag(GameTag.ZONE, Zone.INVALID))

    @zone.setter
    def zone(self, value: Zone) -> None:
        self.set_tag(GameTag.ZONE, value)

    @property
    def zone_position(self) -> int:
        return self.get_tag(GameTag.ZONE_POSITION, 0)

    @zone_position.setter
    def zone_position(self, value: int) -> None:
        self.set_tag(GameTag.ZONE_POSITION, value)

    @property
    def atk(self) -> int:
        """Current attack (base + buffs + global auras). Computed dynamically."""
        base = self.get_tag(GameTag.BASE_ATK, 0)
        # Buff contributions
        for buff in self._buffs:
            base += buff.get_tag(GameTag.ATK, 0)
        # Global aura contribution from controller
        if self.controller is not None and hasattr(self.controller, "get_global_aura_bonus"):
            aura_atk, _ = self.controller.get_global_aura_bonus(self)
            base += aura_atk
        # Script-defined atk override (e.g. health-based minions)
        if self.data.scripts is not None:
            atk_fn = getattr(self.data.scripts, "atk", None)
            if callable(atk_fn):
                result = atk_fn(self)
                if result is not None:
                    return max(0, result)
        return max(0, base)

    @atk.setter
    def atk(self, value: int) -> None:
        """Setting atk updates base attack."""
        delta = value - self.atk
        self.set_tag(GameTag.BASE_ATK, self.get_tag(GameTag.BASE_ATK, 0) + delta)

    @property
    def health(self) -> int:
        """Current health."""
        return self.get_tag(GameTag.HEALTH, 0)

    @health.setter
    def health(self, value: int) -> None:
        self.set_tag(GameTag.HEALTH, max(0, value))
        if self.health <= 0:
            self.set_tag(GameTag.DEAD, True)

    @property
    def max_health(self) -> int:
        """Current max health (base + buffs + global auras)."""
        base = self.get_tag(GameTag.BASE_HEALTH, 0)
        for buff in self._buffs:
            base += buff.get_tag(GameTag.HEALTH, 0)
        # Global aura contribution from controller
        if self.controller is not None and hasattr(self.controller, "get_global_aura_bonus"):
            _, aura_health = self.controller.get_global_aura_bonus(self)
            base += aura_health
        # Anomaly health bonus (Prudence of Amitus)
        if self.controller is not None:
            base += self.controller.get_tag(GameTag.ANOMALY_MINION_HEALTH_BONUS, 0)
        return max(1, base)

    @max_health.setter
    def max_health(self, value: int) -> None:
        delta = value - self.max_health
        self.set_tag(GameTag.BASE_HEALTH, self.get_tag(GameTag.BASE_HEALTH, 0) + delta)

    @property
    def damage(self) -> int:
        return self.max_health - self.health

    @property
    def dead(self) -> bool:
        return self.has_tag(GameTag.DEAD) or self.health <= 0

    @property
    def is_golden(self) -> bool:
        return self.has_tag(GameTag.GOLDEN)

    @property
    def tech_level(self) -> int:
        return self.get_tag(GameTag.TECH_LEVEL, 1)

    @property
    def race(self):
        r = self.get_tag(GameTag.RACE, 0)
        # Anomaly: No-type minions have ALL types
        if r == Race.NONE and self.game is not None:
            anomaly = getattr(self.game, 'active_anomaly', None)
            if (anomaly is not None
                    and not isinstance(anomaly, bool)
                    and getattr(anomaly, '_no_type_has_all', False)):
                return Race.ALL
        return r

    # ── Keyword helpers ──

    @property
    def taunt(self) -> bool:
        return self.has_tag(GameTag.TAUNT)

    @property
    def divine_shield(self) -> bool:
        return self.has_tag(GameTag.DIVINE_SHIELD)

    @property
    def poisonous(self) -> bool:
        return self.has_tag(GameTag.POISONOUS)

    @property
    def venomous(self) -> bool:
        return self.has_tag(GameTag.VENOMOUS)

    @property
    def reborn(self) -> bool:
        return self.has_tag(GameTag.REBORN)

    @property
    def windfury(self) -> bool:
        return self.has_tag(GameTag.WINDFURY)

    @property
    def cleave(self) -> bool:
        return self.has_tag(GameTag.CLEAVE)

    @property
    def magnetic(self) -> bool:
        return self.has_tag(GameTag.MAGNETIC)

    def _call_script_method(self, method_name: str):
        """Call a script method with (self, game) and return the Action."""
        # 0. Silenced minions cannot trigger any script method
        if self.has_tag(GameTag.SILENCED):
            return None
        # 1. Check per-instance overrides first (for dynamic keyword propagation)
        override = self._script_overrides.get(method_name)
        if override is not None:
            if callable(override):
                return override(self, self.game)
            return override

        # 2. Fall back to static script class
        if not self.data.scripts:
            return None
        fn = getattr(self.data.scripts, method_name, None)
        if fn is None:
            return None
        if callable(fn):
            # Lazy import to avoid circular dependency
            from hsrl.core.actions import Action
            if not isinstance(fn, Action):
                return fn(self, self.game)
        return fn

    @property
    def deathrattle(self):
        """Returns the resolved deathrattle Action(s)."""
        return self._call_script_method("deathrattle")

    @property
    def battlecry(self):
        """Returns the resolved battlecry Action(s)."""
        return self._call_script_method("battlecry")

    @property
    def start_of_combat(self):
        """Returns the resolved start-of-combat Action(s)."""
        return self._call_script_method("start_of_combat")

    @property
    def avenge(self):
        """Returns the resolved avenge Action(s)."""
        return self._call_script_method("avenge")

    @property
    def rally(self):
        """Returns the resolved rally Action(s)."""
        return self._call_script_method("rally")

    @property
    def end_of_turn(self):
        """Returns the resolved end-of-turn Action(s)."""
        return self._call_script_method("end_of_turn")

    @property
    def start_of_turn(self):
        """Returns the resolved start-of-turn Action(s)."""
        return self._call_script_method("start_of_turn")

    @property
    def on_sell(self):
        """Returns the resolved on-sell Action(s)."""
        return self._call_script_method("on_sell")

    @property
    def on_summon(self):
        """Called when this minion is summoned to the board.
        Returns an Action to be queued, or None."""
        return self._call_script_method("on_summon")

    @property
    def on_play(self):
        """Called when this entity (spell or minion) is played from hand.
        Returns an Action to be queued, or None.
        Used primarily for Spellcraft spell effects."""
        return self._call_script_method("on_play")

    # ── Buff management ──

    def add_buff(self, buff_entity) -> None:
        """Apply a buff (enchantment) to this entity."""
        self._buffs.append(buff_entity)
        # Health buffs also increase current health by the same amount
        hp_buff = buff_entity.get_tag(GameTag.HEALTH, 0)
        if hp_buff > 0:
            self.set_tag(GameTag.HEALTH, self.health + hp_buff)

    def remove_buff(self, buff_entity) -> None:
        if buff_entity in self._buffs:
            self._buffs.remove(buff_entity)

    def clear_buffs(self) -> None:
        self._buffs.clear()

    # ── Event helpers ──

    def add_event(self, event_listener) -> None:
        self._events.append(event_listener)

    def remove_event(self, event_listener) -> None:
        if event_listener in self._events:
            self._events.remove(event_listener)

    def clear_events(self) -> None:
        self._events.clear()

    # ── Representation ──

    def __repr__(self) -> str:
        name = self.get_tag(GameTag.NAME, "Unknown")
        return f"<{name} ({self.uuid})>"


class CardData:
    """
    Immutable template data for a card.
    This is the 'blueprint' from which entities are instantiated.
    """

    def __init__(
        self,
        id: str,
        name: str,
        text: str = "",
        cardtype: "CardType" = None,
        race: "Race" = None,
        tech_level: int = 1,
        rarity: "Rarity" = None,
        tags: Optional[Dict[GameTag, Any]] = None,
        scripts=None,
    ):
        self.id = id
        self.name = name
        self.text = text
        self.cardtype = cardtype
        self.race = race
        self.tech_level = tech_level
        self.rarity = rarity
        self.tags = tags or {}
        self.scripts = scripts          # Card behavior script class/object

    def __repr__(self) -> str:
        return f"<CardData {self.id}: {self.name}>"
