"""
Entity token layout for Observation V2.

Defines the slot layout, feature dimensions, and token group boundaries
for the entity-centric observation.

Core layout (26 slots, always active):
  [GLOBAL]                   1  token
  [HERO_SELF]                1  token
  [TAVERN_0..6]              7  tokens
  [BOARD_0..6]               7  tokens
  [HAND_0..9]               10  tokens

Extended layout (+11 slots, DISABLED by default):
  [OPPONENT_0..6_SUMMARY]    7  tokens  — HDT plugin exposes limited info;
                              disabled to avoid misleading at small scale
  [HISTORY]                  4  tokens  — combat/level/econ history

Design decision: opponent public info is disabled by default because:
  1. HDT plugin only exposes health/armor/tier/last_seen_board — incomplete
  2. Bad opponent estimates can mislead the model at small training scale
  3. Board-building mode (current focus) has no opponents
  Enable with build_observation_v2(include_opponents=True) when needed.
"""

from __future__ import annotations

from enum import IntEnum


class TokenGroup(IntEnum):
    """Entity token group identifiers."""
    GLOBAL = 0
    HERO_SELF = 1
    TAVERN = 2
    BOARD = 3
    HAND = 4
    OPPONENT_SUMMARY = 5
    HISTORY = 6


# Slot counts per group
GLOBAL_SLOTS = 1
HERO_SELF_SLOTS = 1
TAVERN_SLOTS = 7
BOARD_SLOTS = 7
HAND_SLOTS = 10
OPPONENT_SLOTS = 7     # one summary token per opponent (DISABLED by default)
HISTORY_SLOTS = 4      # combat/level/econ history (DISABLED by default)

# Core entity slots (always active): global + hero + tavern + board + hand
CORE_SLOTS = (
    GLOBAL_SLOTS + HERO_SELF_SLOTS + TAVERN_SLOTS +
    BOARD_SLOTS + HAND_SLOTS
)  # = 26

# Extended slots (disabled by default): opponent + history
EXTENDED_SLOTS = OPPONENT_SLOTS + HISTORY_SLOTS  # = 11

# Total slots in the full layout
NUM_ENTITY_SLOTS = CORE_SLOTS + EXTENDED_SLOTS  # = 37

# Offsets into the flat entity array
GLOBAL_OFFSET = 0
HERO_OFFSET = GLOBAL_OFFSET + GLOBAL_SLOTS                    # 1
TAVERN_OFFSET = HERO_OFFSET + HERO_SELF_SLOTS                 # 2
BOARD_OFFSET = TAVERN_OFFSET + TAVERN_SLOTS                   # 9
HAND_OFFSET = BOARD_OFFSET + BOARD_SLOTS                      # 16
OPPONENT_OFFSET = HAND_OFFSET + HAND_SLOTS                    # 26
HISTORY_OFFSET = OPPONENT_OFFSET + OPPONENT_SLOTS             # 33


# ═══════════════════════════════════════════════════════════════════════════════
# Per-entity feature dimensions
# ═══════════════════════════════════════════════════════════════════════════════

# Global token: turn, phase, alive_count, damage_cap, tribes, anomaly
GLOBAL_FEAT_DIM = 16

# Hero self: hp, armor, gold, tier, upgrade_cost, hand_size, board_size
HERO_FEAT_DIM = 12

# Tavern/Board/Hand entity: same 8-dim as obs_builder
ENTITY_FEAT_DIM = 8

# Opponent summary: hp, armor, tier, board_size, last_seen_turn, last_combat_result
OPPONENT_FEAT_DIM = 12

# History token: combat result, damage dealt/taken, leveled, tripled
HISTORY_FEAT_DIM = 8


# ═══════════════════════════════════════════════════════════════════════════════
# EntityLayout: describes which group each slot belongs to
# ═══════════════════════════════════════════════════════════════════════════════

class EntityTokenLayout:
    """Describes the layout of entity tokens for Observation V2.

    Maps each slot index to its TokenGroup, and specifies
    which slots are competitor entities (tavern/board/hand)
    vs summary tokens (opponents, history).
    """

    @staticmethod
    def group_of(slot_idx: int) -> TokenGroup:
        """Return the TokenGroup for a given slot index."""
        if slot_idx < TAVERN_OFFSET:
            if slot_idx < HERO_OFFSET:
                return TokenGroup.GLOBAL
            return TokenGroup.HERO_SELF
        if slot_idx < BOARD_OFFSET:
            return TokenGroup.TAVERN
        if slot_idx < HAND_OFFSET:
            return TokenGroup.BOARD
        if slot_idx < OPPONENT_OFFSET:
            return TokenGroup.HAND
        if slot_idx < HISTORY_OFFSET:
            return TokenGroup.OPPONENT_SUMMARY
        return TokenGroup.HISTORY

    @staticmethod
    def is_competitor_entity(slot_idx: int) -> bool:
        """True if this slot represents a buyable/playable entity."""
        g = EntityTokenLayout.group_of(slot_idx)
        return g in (TokenGroup.TAVERN, TokenGroup.BOARD, TokenGroup.HAND)

    @staticmethod
    def is_summary_token(slot_idx: int) -> bool:
        """True if this slot is a summary/context token."""
        g = EntityTokenLayout.group_of(slot_idx)
        return g in (TokenGroup.GLOBAL, TokenGroup.HERO_SELF,
                     TokenGroup.OPPONENT_SUMMARY, TokenGroup.HISTORY)

    @staticmethod
    def competitor_count() -> int:
        """Number of competitor entity slots (tavern + board + hand)."""
        return TAVERN_SLOTS + BOARD_SLOTS + HAND_SLOTS  # 24
