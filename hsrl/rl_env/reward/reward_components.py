"""
RewardComponents — decomposed reward signal for turn-level training.

Separates placement, board, combat, economy, and risk components
so the training loss can weight each independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.rl_env.reward.combat_labels import compute_combat_labels
from hsrl.rl_env.reward.rank_labels import compute_rank_labels

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player
    from hsrl.rl_env.core.turn_trajectory import TurnTrajectory


@dataclass
class RewardComponents:
    """All reward components for a single turn trajectory."""
    # Placement
    placement_reward: float = 0.0
    top4_reward: float = 0.0
    top1_reward: float = 0.0

    # Combat
    combat_win_reward: float = 0.0
    damage_dealt_reward: float = 0.0
    damage_taken_penalty: float = 0.0
    death_penalty: float = 0.0

    # Board
    board_score_delta: float = 0.0
    economy_score_delta: float = 0.0
    scaling_score_delta: float = 0.0
    pair_score_delta: float = 0.0

    # Penalties
    invalid_action_penalty: float = 0.0
    excessive_roll_penalty: float = 0.0
    unspent_gold_penalty: float = 0.0

    # Metadata
    turn_id: int = 0
    player_id: int = 0
    details: dict = field(default_factory=dict)

    @property
    def total(self) -> float:
        """Sum of all reward components."""
        return (
            self.placement_reward + self.top4_reward + self.top1_reward +
            self.combat_win_reward + self.damage_dealt_reward +
            self.damage_taken_penalty + self.death_penalty +
            self.board_score_delta + self.economy_score_delta +
            self.scaling_score_delta + self.pair_score_delta +
            self.invalid_action_penalty + self.excessive_roll_penalty +
            self.unspent_gold_penalty
        )

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "placement": self.placement_reward,
            "board_delta": self.board_score_delta,
            "econ_delta": self.economy_score_delta,
            "scaling_delta": self.scaling_score_delta,
            **self.details,
        }


def compute_turn_reward(
    game: "Game", player: "Player",
    trajectory: "TurnTrajectory | None" = None,
) -> RewardComponents:
    """Compute all reward components for a completed turn.

    Uses board score deltas (computed from engine) and placement
    info if the game has ended.
    """
    board_before = compute_board_score_v2(player)
    # board_after is computed externally after executing the turn
    board_after = board_before  # placeholder — updated after plan execution

    board_delta = board_after.total - board_before.total

    rc = RewardComponents(
        board_score_delta=board_delta,
        turn_id=game.turn,
        player_id=game.players.index(player) if player in game.players else 0,
    )

    # If game is complete, add placement rewards
    if game.state.value == 2:  # COMPLETE
        rank = compute_rank_labels(game, player)
        rc.placement_reward = rank.placement_reward if rank.placement <= 4 else 0.0
        rc.top4_reward = 5.0 if rank.top4 else 0.0
        rc.top1_reward = 10.0 if rank.top1 else 0.0

    # Add penalties
    if trajectory and trajectory.action_count > 30:
        rc.excessive_roll_penalty = -0.01 * (trajectory.action_count - 30)

    if trajectory and trajectory.action_count == 0:
        rc.invalid_action_penalty = -0.5

    return rc
