"""
TurnTrajectory — a complete turn's worth of training data.

Replaces raw transition buffers with turn-level samples.
Each TurnTrajectory captures a full recruit phase from start to end,
including per-step observations, actions, and final labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class TurnTrajectory:
    """A complete recruit phase trajectory for one player.

    This is the primary training sample for plan-level policy learning.
    Contains start/end observations, full action sequence, and labels
    computed after the turn is complete.

    Labels include:
      - Board score deltas
      - Combat predictions (if combat occurred)
      - Rank/placement info (if game is over)
      - Economy metrics
    """
    # Identity
    game_id: str = ""
    player_id: int = 0
    turn_id: int = 0

    # Start state
    start_observation: dict = field(default_factory=dict)
    start_global_features: dict = field(default_factory=dict)

    # Option selected for this turn (may be None)
    option_type: str | None = None

    # Action sequence
    action_sequence: list = field(default_factory=list)  # AtomicAction or dict
    per_step_observations: list = field(default_factory=list)
    per_step_legal_masks: list = field(default_factory=list)

    # End state
    end_observation: dict = field(default_factory=dict)

    # ── Labels ──
    # Board
    board_score_before: float = 0.0
    board_score_after: float = 0.0
    board_score_delta: float = 0.0

    # Combat (if combat occurred after this turn)
    combat_win_prob: float = 0.0
    combat_tie_prob: float = 0.0
    combat_loss_prob: float = 0.0
    expected_damage_dealt: float = 0.0
    expected_damage_taken: float = 0.0
    health_after_combat: float = 0.0
    death_next_combat: float = 0.0

    # Economy
    gold_spent: int = 0
    gold_remaining: int = 0
    rolls_used: int = 0

    # Terminal (if game ended)
    placement_if_terminal: int | None = None
    final_rank_if_game_finished: int | None = None
    top4: bool = False
    top1: bool = False

    # Reward decomposition
    reward_info: dict = field(default_factory=dict)
    labels: dict = field(default_factory=dict)

    # Metadata
    source: str = "unknown"        # heuristic / search / policy / population
    patch_version: str = ""
    diagnostics: dict = field(default_factory=dict)

    @property
    def action_count(self) -> int:
        return len(self.action_sequence)

    @property
    def is_valid(self) -> bool:
        return self.action_count > 0 and not self.diagnostics.get("invalid", False)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict for dataset storage."""
        return {
            "game_id": self.game_id,
            "player_id": self.player_id,
            "turn_id": self.turn_id,
            "option_type": self.option_type,
            "action_count": self.action_count,
            "actions": [
                a.to_dict() if hasattr(a, 'to_dict') else str(a)
                for a in self.action_sequence
            ],
            "board_score_before": self.board_score_before,
            "board_score_after": self.board_score_after,
            "board_score_delta": self.board_score_delta,
            "gold_spent": self.gold_spent,
            "gold_remaining": self.gold_remaining,
            "rolls_used": self.rolls_used,
            "placement": self.placement_if_terminal,
            "final_rank": self.final_rank_if_game_finished,
            "top4": self.top4,
            "top1": self.top1,
            "reward_info": self.reward_info,
            "labels": self.labels,
            "source": self.source,
            "diagnostics": self.diagnostics,
        }

    def __repr__(self) -> str:
        return (f"TurnTrajectory(game={self.game_id}, turn={self.turn_id}, "
                f"player={self.player_id}, actions={self.action_count}, "
                f"board={self.board_score_before:.0f}→{self.board_score_after:.0f})")
