"""
RLState — environment-level state wrapper for RL training.

RLState wraps game engine state into an RL-compatible view with
observation, action mask, metadata, and labels. It does NOT hold
mutable game objects — those are managed internally by the env.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class RLState:
    """Environment-level state for RL training.

    Contains only observation data, masks, and metadata.
    Game objects are NOT referenced — all data is copied at construction time.
    """
    # Identity
    game_id: str = ""
    turn_id: int = 0
    player_id: int = 0
    phase: str = "recruit"

    # Observation (numpy arrays / dicts, copied from engine)
    observation: dict = field(default_factory=dict)

    # Action masks
    legal_atomic_mask: np.ndarray | None = None
    legal_option_mask: np.ndarray | None = None
    legal_pointer_mask: np.ndarray | None = None

    # History (action logs)
    public_history: list = field(default_factory=list)
    private_action_history: list = field(default_factory=list)
    turn_action_history: list = field(default_factory=list)

    # Terminal info
    is_terminal: bool = False
    placement: int | None = None
    reward_info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to a serializable dict (for dataset storage)."""
        return {
            "game_id": self.game_id,
            "turn_id": self.turn_id,
            "player_id": self.player_id,
            "phase": self.phase,
            "is_terminal": self.is_terminal,
            "placement": self.placement,
            "reward_info": self.reward_info,
        }

    @property
    def action_history_length(self) -> int:
        return len(self.turn_action_history)

    def __repr__(self) -> str:
        return (f"RLState(game={self.game_id}, turn={self.turn_id}, "
                f"player={self.player_id}, terminal={self.is_terminal})")
