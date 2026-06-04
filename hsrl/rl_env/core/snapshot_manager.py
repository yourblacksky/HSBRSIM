"""
SnapshotManager — lightweight game state save/restore for plan execution.

Wraps agent_utils save_player_state / restore_player_state.
Provides a higher-level interface for the PlanExecutor.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from hsrl.agents.agent_utils import save_player_state, restore_player_state

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


class SnapshotManager:
    """Manages game state snapshots for plan execution and rollback."""

    def __init__(self):
        self._snapshots: dict[str, dict] = {}
        self._player_refs: dict[str, "Player"] = {}

    def save(self, game: "Game", player: "Player") -> str:
        """Save player state and return a snapshot ID."""
        snap_id = uuid.uuid4().hex[:12]
        self._snapshots[snap_id] = save_player_state(player)
        self._player_refs[snap_id] = player
        return snap_id

    def restore(self, snap_id: str) -> bool:
        """Restore player state from a snapshot ID. Returns True on success."""
        saved = self._snapshots.get(snap_id)
        player = self._player_refs.get(snap_id)
        if saved is None or player is None:
            return False
        restore_player_state(player, saved)
        return True

    def forget(self, snap_id: str) -> None:
        """Release a snapshot."""
        self._snapshots.pop(snap_id, None)
        self._player_refs.pop(snap_id, None)

    def clear(self) -> None:
        """Release all snapshots."""
        self._snapshots.clear()
        self._player_refs.clear()

    def __len__(self) -> int:
        return len(self._snapshots)
