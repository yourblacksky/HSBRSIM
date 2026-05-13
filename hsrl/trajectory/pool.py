"""
Trajectory Pool — random opponent sampling for RL training.

Provides a pool of winner trajectories that can be randomly sampled
to create diverse frozen combat opponents. Each env reset draws fresh
opponents to prevent overfitting to specific trajectory boards.
"""

from __future__ import annotations

import json
import os
import random
from typing import Dict, List, Optional, Set

from hsrl.trajectory.opponent import TrajectoryOpponent


class TrajectoryPool:
    """Pool of trajectory opponents with random sampling.

    Usage:
        pool = TrajectoryPool("data/trajectories")
        opponents = pool.sample(7)  # 7 random TrajectoryOpponent objects
    """

    def __init__(
        self,
        trajectories_dir: str = "data/trajectories",
        index_path: Optional[str] = None,
        cache_opponents: bool = True,
    ):
        self._dir = trajectories_dir
        self._cache_enabled = cache_opponents
        self._cache: Dict[str, TrajectoryOpponent] = {}

        # Load index
        idx_path = index_path or os.path.join(trajectories_dir, "index.jsonl")
        self._entries: List[dict] = []
        if os.path.exists(idx_path):
            with open(idx_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._entries.append(json.loads(line))
        else:
            # Scan directory for trajectory files
            for fn in sorted(os.listdir(trajectories_dir)):
                if fn.startswith("traj_") and fn.endswith(".json"):
                    self._entries.append({"game_id": fn.replace(".json", "")})

    @property
    def size(self) -> int:
        """Number of trajectories in the pool."""
        return len(self._entries)

    @property
    def entries(self) -> List[dict]:
        """Raw index entries (read-only)."""
        return list(self._entries)

    def sample(
        self,
        n: int = 7,
        exclude: Optional[Set[str]] = None,
    ) -> List[TrajectoryOpponent]:
        """Sample N random trajectory opponents (without replacement).

        Args:
            n: Number of opponents to sample.
            exclude: Optional set of game_ids to exclude.

        Returns:
            List of TrajectoryOpponent objects. May return fewer than n
            if the pool is too small after exclusions.
        """
        exclude = exclude or set()
        candidates = [e for e in self._entries if e["game_id"] not in exclude]
        if len(candidates) < n:
            selected = candidates
        else:
            selected = random.sample(candidates, n)

        opponents = []
        for entry in selected:
            opp = self._get_or_load(entry["game_id"])
            if opp is not None:
                opponents.append(opp)

        return opponents

    def _get_or_load(self, game_id: str) -> Optional[TrajectoryOpponent]:
        """Get a trajectory opponent, loading from cache or file."""
        if self._cache_enabled and game_id in self._cache:
            return self._cache[game_id]

        path = os.path.join(self._dir, f"{game_id}.json")
        if not os.path.exists(path):
            return None

        opponent = TrajectoryOpponent(path)
        if self._cache_enabled:
            self._cache[game_id] = opponent
        return opponent

    def clear_cache(self) -> None:
        """Clear the opponent cache to free memory."""
        self._cache.clear()

    def __repr__(self) -> str:
        return f"<TrajectoryPool size={self.size} dir={self._dir}>"
