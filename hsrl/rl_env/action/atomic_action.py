"""
Structured atomic actions for the Battlegrounds recruit phase.

Replaces raw integer action IDs with typed, validated action objects.
Supports bidirectional mapping to legacy Discrete(50) action space.

Action types:
  BUY, SELL, PLAY, ROLL, LEVEL, FREEZE, UNFREEZE,
  HERO_POWER, SECOND_HERO_POWER, DISCOVER_CHOOSE,
  REORDER, END_TURN, NOOP, CAST_SPELL, SELECT_TARGET,
  TRINKET_CHOOSE, BUDDY_GET
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class ActionType(StrEnum):
    """Structured action types for the recruit phase."""
    BUY = "buy"
    SELL = "sell"
    PLAY = "play"
    ROLL = "roll"
    LEVEL = "level"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    HERO_POWER = "hero_power"
    SECOND_HERO_POWER = "second_hero_power"
    DISCOVER_CHOOSE = "discover_choose"
    REORDER = "reorder"
    END_TURN = "end_turn"
    NOOP = "noop"
    CAST_SPELL = "cast_spell"
    SELECT_TARGET = "select_target"
    TRINKET_CHOOSE = "trinket_choose"
    BUDDY_GET = "buddy_get"


class ZoneType(StrEnum):
    """Source/target zones for pointer actions."""
    SHOP = "shop"
    BOARD = "board"
    HAND = "hand"
    DISCOVER = "discover"
    OPPONENT = "opponent"
    HERO_SELF = "hero_self"
    HERO_OPPONENT = "hero_opponent"
    NONE = "none"


@dataclass(frozen=True)
class AtomicAction:
    """A single atomic action in the recruit phase.

    Immutable (frozen=True) so it can be used as dict key and cached.
    Use action_to_legacy_id() to get the legacy 0-49 integer for old env compat.
    """
    action_type: ActionType
    source_zone: ZoneType = ZoneType.NONE
    source_index: int = -1
    target_zone: ZoneType = ZoneType.NONE
    target_index: int = -1
    choice_index: int = -1
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        parts = [self.action_type.value]
        if self.source_zone != ZoneType.NONE and self.source_index >= 0:
            parts.append(f"{self.source_zone.value}[{self.source_index}]")
        if self.target_zone != ZoneType.NONE and self.target_index >= 0:
            parts.append(f"→{self.target_zone.value}[{self.target_index}]")
        if self.choice_index >= 0:
            parts.append(f"choice={self.choice_index}")
        return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy 50-way action mapping (backward compatibility with hsrl/env/action.py)
# ═══════════════════════════════════════════════════════════════════════════════

# Legacy action space constants (must match hsrl/env/action.py)
BUY_OFFSET = 0       # 0-6
SELL_OFFSET = 7      # 7-13
PLAY_OFFSET = 14     # 14-23
REFRESH = 24
UPGRADE = 25
FREEZE = 26
HERO_POWER = 27
END_TURN = 28
GET_BUDDY = 29
REARRANGE = 30
SECOND_HERO_POWER = 31

def action_to_legacy_id(action: AtomicAction) -> int | None:
    """Map a structured AtomicAction to legacy 0-49 action id.
    Returns None if the action has no legacy equivalent.
    """
    at = action.action_type
    si = action.source_index

    if at == ActionType.BUY and 0 <= si <= 6:
        return BUY_OFFSET + si
    if at == ActionType.SELL and 0 <= si <= 6:
        return SELL_OFFSET + si
    if at == ActionType.PLAY and 0 <= si <= 9:
        return PLAY_OFFSET + si
    if at == ActionType.ROLL:
        return REFRESH
    if at == ActionType.LEVEL:
        return UPGRADE
    if at in (ActionType.FREEZE, ActionType.UNFREEZE):
        return FREEZE
    if at == ActionType.HERO_POWER:
        return HERO_POWER
    if at == ActionType.SECOND_HERO_POWER:
        return SECOND_HERO_POWER
    if at == ActionType.END_TURN:
        return END_TURN
    if at == ActionType.BUDDY_GET:
        return GET_BUDDY
    if at == ActionType.REORDER:
        return REARRANGE

    # DISCOVER_CHOOSE, CAST_SPELL, SELECT_TARGET, TRINKET_CHOOSE, NOOP
    # have no simple legacy equivalent; maps to END_TURN as safe default.
    return None


def legacy_id_to_action(action_id: int) -> AtomicAction:
    """Convert a legacy 0-49 action id to a structured AtomicAction.
    This is a lossy conversion for backward compatibility.
    """
    if BUY_OFFSET <= action_id < BUY_OFFSET + 7:
        return AtomicAction(ActionType.BUY, source_zone=ZoneType.SHOP,
                           source_index=action_id - BUY_OFFSET)
    if SELL_OFFSET <= action_id < SELL_OFFSET + 7:
        return AtomicAction(ActionType.SELL, source_zone=ZoneType.BOARD,
                           source_index=action_id - SELL_OFFSET)
    if PLAY_OFFSET <= action_id < PLAY_OFFSET + 10:
        return AtomicAction(ActionType.PLAY, source_zone=ZoneType.HAND,
                           source_index=action_id - PLAY_OFFSET)
    if action_id == REFRESH:
        return AtomicAction(ActionType.ROLL)
    if action_id == UPGRADE:
        return AtomicAction(ActionType.LEVEL)
    if action_id == FREEZE:
        return AtomicAction(ActionType.FREEZE)
    if action_id == HERO_POWER:
        return AtomicAction(ActionType.HERO_POWER)
    if action_id == SECOND_HERO_POWER:
        return AtomicAction(ActionType.SECOND_HERO_POWER)
    if action_id == END_TURN:
        return AtomicAction(ActionType.END_TURN)
    if action_id == GET_BUDDY:
        return AtomicAction(ActionType.BUDDY_GET)
    if action_id == REARRANGE:
        return AtomicAction(ActionType.REORDER)

    return AtomicAction(ActionType.NOOP)


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience constructors
# ═══════════════════════════════════════════════════════════════════════════════

def buy(slot: int) -> AtomicAction:
    return AtomicAction(ActionType.BUY, source_zone=ZoneType.SHOP, source_index=slot)

def sell(slot: int) -> AtomicAction:
    return AtomicAction(ActionType.SELL, source_zone=ZoneType.BOARD, source_index=slot)

def play(slot: int, target_zone: ZoneType = ZoneType.NONE, target_index: int = -1) -> AtomicAction:
    return AtomicAction(ActionType.PLAY, source_zone=ZoneType.HAND, source_index=slot,
                       target_zone=target_zone, target_index=target_index)

def roll() -> AtomicAction:
    return AtomicAction(ActionType.ROLL)

def level() -> AtomicAction:
    return AtomicAction(ActionType.LEVEL)

def freeze() -> AtomicAction:
    return AtomicAction(ActionType.FREEZE)

def end_turn() -> AtomicAction:
    return AtomicAction(ActionType.END_TURN)

def discover_choose(choice_index: int) -> AtomicAction:
    return AtomicAction(ActionType.DISCOVER_CHOOSE, choice_index=choice_index)

def hero_power() -> AtomicAction:
    return AtomicAction(ActionType.HERO_POWER)

def noop() -> AtomicAction:
    return AtomicAction(ActionType.NOOP)
