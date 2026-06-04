"""
CombatLabels — combat outcome predictions from simulation rollouts.

When a full combat simulator is available, run multiple combat rollouts
from the current board state to estimate win/tie/loss probabilities
and expected damage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


@dataclass
class CombatLabels:
    """Probabilistic combat outcome estimates.

    Computed by running multiple combat rollouts from the same board state.
    """
    win_prob: float = 0.0
    tie_prob: float = 0.0
    loss_prob: float = 0.0
    expected_damage_dealt: float = 0.0
    expected_damage_taken: float = 0.0
    lethal_risk: float = 0.0  # P(damage_taken >= current_health)

    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "win_prob": self.win_prob,
            "tie_prob": self.tie_prob,
            "loss_prob": self.loss_prob,
            "expected_damage_dealt": self.expected_damage_dealt,
            "expected_damage_taken": self.expected_damage_taken,
            "lethal_risk": self.lethal_risk,
        }


def compute_combat_labels(
    game: "Game", player: "Player", num_rollouts: int = 4,
) -> CombatLabels:
    """Compute combat labels by running sim rollouts.

    For each rollout: clone the board, run combat against a random
    opponent board, record results.

    NOTE: Full implementation requires board cloning and combat
    simulation. Returns neutral defaults when combat is disabled
    (board-building mode).
    """
    # In board-building mode: return neutral labels
    return CombatLabels(
        win_prob=0.5,
        tie_prob=0.0,
        loss_prob=0.5,
        expected_damage_dealt=5.0,
        expected_damage_taken=5.0,
        lethal_risk=0.0,
        metadata={"mode": "neutral_default"},
    )
