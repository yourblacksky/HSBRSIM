"""
RankLabels — final placement and rank information from completed games.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


@dataclass
class RankLabels:
    """Final game outcome for a player."""
    placement: int = 8
    top4: bool = False
    top1: bool = False
    normalized_rank_value: float = 0.0  # 1.0 for 1st, 0.0 for 8th

    @property
    def placement_reward(self) -> float:
        """Reward based on placement alone."""
        rewards = {1: 20, 2: 10, 3: 5, 4: 2, 5: -2, 6: -5, 7: -10, 8: -20}
        return rewards.get(self.placement, -20.0)

    def to_dict(self) -> dict:
        return {
            "placement": self.placement,
            "top4": self.top4,
            "top1": self.top1,
            "normalized_rank_value": self.normalized_rank_value,
        }


def compute_rank_labels(
    game: "Game", player: "Player",
) -> RankLabels:
    """Compute rank labels from a completed game."""
    from hsrl.env.reward import compute_placement

    placement = compute_placement(player, game.players)
    return RankLabels(
        placement=placement,
        top4=placement <= 4,
        top1=placement == 1,
        normalized_rank_value=1.0 - (placement - 1) / 7.0,
    )
