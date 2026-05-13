"""
HSRL Trajectory Module

Pre-generates heuristic-only games, extracts winning trajectories, and
provides type-compatible snapshot opponents for RL training.
"""

from hsrl.trajectory.pool import TrajectoryPool
from hsrl.trajectory.opponent import TrajectoryOpponent
from hsrl.trajectory.record import Trajectory, TurnSnapshot, MinionSnapshot

__all__ = [
    "TrajectoryPool",
    "TrajectoryOpponent",
    "Trajectory",
    "TurnSnapshot",
    "MinionSnapshot",
]
