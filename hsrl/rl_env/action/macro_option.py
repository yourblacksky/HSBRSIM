"""
MacroOption — turn-level intent label for plan generation.

MacroOptions sit between the policy's high-level strategic decision
and the low-level atomic action sequence. They condition the plan
decoder and guide exploration into reasonable action regions.

Design:
  - Options are always "legal" (you can always try to do them)
  - Some options are "pointless" in certain states (flag as low_value)
  - The plan decoder uses the option to bias action sampling
  - Options provide a 15-way conditioning variable for the policy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


class OptionType(StrEnum):
    """Structured turn-level intent types."""
    TEMPO_BOARD = "tempo_board"           # Play minions, maximize board presence
    BUY_BEST_MINION = "buy_best"          # Buy the objectively strongest minion
    BUY_PAIR = "buy_pair"                 # Buy a minion that creates a pair
    BUY_TRIPLE_OUT = "buy_triple"         # Complete a triple
    ROLL_FOR_PAIR = "roll_pair"           # Refresh looking for a pair
    ROLL_FOR_CORE = "roll_core"           # Refresh looking for core tribe card
    LEVEL_IF_SAFE = "level_safe"          # Upgrade tavern if HP is safe
    GREED_LEVEL = "greed_level"           # Upgrade tavern aggressively
    ECONOMY_SETUP = "economy"             # Save gold, set up for future turns
    MAKE_SPACE = "make_space"             # Sell weak minions to free board slots
    PLAY_BATTLECRY = "play_battlecry"     # Play a battlecry minion for value
    BUFF_BOARD = "buff_board"             # Use spells/hero power to buff board
    FREEZE_VALUABLE = "freeze_value"      # Freeze tavern with good minions
    REPOSITION = "reposition"             # Reorder board for combat
    END_TURN = "end_turn"                 # End the recruit phase immediately


# ── Option metadata ──────────────────────────────────────────────────────────

OPTION_META = {
    OptionType.TEMPO_BOARD: {
        "description": "Maximize board presence: buy and play as many minions as possible",
        "priority": "board_strength",
        "typical_turns": "early (1-4)",
    },
    OptionType.BUY_BEST_MINION: {
        "description": "Buy the objectively strongest minion in the tavern",
        "priority": "board_strength",
        "typical_turns": "early-mid (1-6)",
    },
    OptionType.BUY_PAIR: {
        "description": "Buy a minion that creates a pair (2 of the same card)",
        "priority": "triple_progress",
        "typical_turns": "mid (3-8)",
    },
    OptionType.BUY_TRIPLE_OUT: {
        "description": "Complete a triple: buy the 3rd copy, get golden + discover",
        "priority": "triple_reward",
        "typical_turns": "mid-late (4-10)",
    },
    OptionType.ROLL_FOR_PAIR: {
        "description": "Spend gold refreshing to find a pair",
        "priority": "triple_progress",
        "typical_turns": "mid (4-8)",
    },
    OptionType.ROLL_FOR_CORE: {
        "description": "Spend gold refreshing to find a core tribe-synergy card",
        "priority": "scaling",
        "typical_turns": "mid-late (5-10)",
    },
    OptionType.LEVEL_IF_SAFE: {
        "description": "Upgrade tavern if HP > 15 (safe to take a hit)",
        "priority": "economy",
        "typical_turns": "mid (3-6)",
    },
    OptionType.GREED_LEVEL: {
        "description": "Upgrade tavern aggressively regardless of HP",
        "priority": "scaling",
        "typical_turns": "mid (3-7)",
    },
    OptionType.ECONOMY_SETUP: {
        "description": "Save gold, minimize spending, prepare for power spike",
        "priority": "economy",
        "typical_turns": "early-mid (2-5)",
    },
    OptionType.MAKE_SPACE: {
        "description": "Sell weak minions to free board slots for new purchases",
        "priority": "board_quality",
        "typical_turns": "mid-late (5-10)",
    },
    OptionType.PLAY_BATTLECRY: {
        "description": "Play a battlecry minion to trigger its effect",
        "priority": "board_strength",
        "typical_turns": "any",
    },
    OptionType.BUFF_BOARD: {
        "description": "Cast spells or use hero power to buff the board",
        "priority": "board_strength",
        "typical_turns": "mid-late (5-10)",
    },
    OptionType.FREEZE_VALUABLE: {
        "description": "Freeze the tavern when it has a valuable minion for next turn",
        "priority": "economy",
        "typical_turns": "early-mid (1-5)",
    },
    OptionType.REPOSITION: {
        "description": "Reorder board minions for optimal combat positioning",
        "priority": "combat",
        "typical_turns": "late (8+)",
    },
    OptionType.END_TURN: {
        "description": "End the recruit phase immediately",
        "priority": "none",
        "typical_turns": "any",
    },
}


# ── Risk profiles ────────────────────────────────────────────────────────────

class RiskProfile(StrEnum):
    CONSERVATIVE = "conservative"  # minimize damage, protect HP
    BALANCED = "balanced"          # standard trade-offs
    AGGRESSIVE = "aggressive"      # sacrifice HP for scaling/economy
    DESPERATE = "desperate"        # all-in, high risk of dying


@dataclass(frozen=True)
class MacroOption:
    """A turn-level strategic intent that conditions plan generation.

    MacroOptions are NOT actions — they are conditioning variables.
    The plan decoder takes an option and generates a sequence of
    atomic actions consistent with that intent.

    Attributes:
        option_type: The strategic intent label
        target_tribes: Tribe(s) to focus on (empty = any)
        max_gold_budget: Maximum gold to spend this turn (None = no limit)
        max_rolls: Maximum refreshes this turn (None = no limit)
        risk_profile: Conservative / Balanced / Aggressive / Desperate
    """
    option_type: OptionType
    target_tribes: tuple[str, ...] = ()
    max_gold_budget: int | None = None
    max_rolls: int | None = None
    risk_profile: RiskProfile = RiskProfile.BALANCED

    @property
    def description(self) -> str:
        return OPTION_META.get(self.option_type, {}).get("description", "")

    @property
    def priority(self) -> str:
        return OPTION_META.get(self.option_type, {}).get("priority", "unknown")

    def __repr__(self) -> str:
        parts = [self.option_type.value]
        if self.target_tribes:
            parts.append(f"tribes={','.join(self.target_tribes)}")
        if self.max_gold_budget:
            parts.append(f"budget={self.max_gold_budget}")
        parts.append(self.risk_profile.value)
        return f"MacroOption({', '.join(parts)})"


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience constructors — all 15 option types
# ═══════════════════════════════════════════════════════════════════════════════

def tempo_board(risk: RiskProfile = RiskProfile.BALANCED) -> MacroOption:
    return MacroOption(OptionType.TEMPO_BOARD, risk_profile=risk)

def buy_best(risk: RiskProfile = RiskProfile.BALANCED) -> MacroOption:
    return MacroOption(OptionType.BUY_BEST_MINION, risk_profile=risk)

def buy_pair(tribes: tuple[str, ...] = (), risk: RiskProfile = RiskProfile.BALANCED) -> MacroOption:
    return MacroOption(OptionType.BUY_PAIR, target_tribes=tribes, risk_profile=risk)

def buy_triple(tribes: tuple[str, ...] = ()) -> MacroOption:
    return MacroOption(OptionType.BUY_TRIPLE_OUT, target_tribes=tribes)

def roll_for_pair(tribes: tuple[str, ...] = (), max_rolls: int | None = None) -> MacroOption:
    return MacroOption(OptionType.ROLL_FOR_PAIR, target_tribes=tribes, max_rolls=max_rolls)

def roll_for_core(tribes: tuple[str, ...] = (), max_rolls: int | None = None) -> MacroOption:
    return MacroOption(OptionType.ROLL_FOR_CORE, target_tribes=tribes, max_rolls=max_rolls)

def level_if_safe(min_hp: int = 15) -> MacroOption:
    return MacroOption(OptionType.LEVEL_IF_SAFE, max_gold_budget=min_hp)

def greed_level() -> MacroOption:
    return MacroOption(OptionType.GREED_LEVEL, risk_profile=RiskProfile.AGGRESSIVE)

def economy_setup(budget: int | None = None) -> MacroOption:
    return MacroOption(OptionType.ECONOMY_SETUP, max_gold_budget=budget)

def make_space() -> MacroOption:
    return MacroOption(OptionType.MAKE_SPACE)

def play_battlecry() -> MacroOption:
    return MacroOption(OptionType.PLAY_BATTLECRY)

def buff_board() -> MacroOption:
    return MacroOption(OptionType.BUFF_BOARD)

def freeze_valuable() -> MacroOption:
    return MacroOption(OptionType.FREEZE_VALUABLE)

def reposition() -> MacroOption:
    return MacroOption(OptionType.REPOSITION)

def end_turn_option() -> MacroOption:
    return MacroOption(OptionType.END_TURN)


# ═══════════════════════════════════════════════════════════════════════════════
# All options list (for enumeration / mask building)
# ═══════════════════════════════════════════════════════════════════════════════

ALL_OPTIONS: list[OptionType] = list(OptionType)
ALL_OPTIONS_COUNT: int = len(ALL_OPTIONS)
