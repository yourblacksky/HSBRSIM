"""
HSRL Adviser — Data Collector

Records full game trajectories from real Battlegrounds matches and saves
them as JSONL files for offline training (offline RL / imitation learning).

Output structure:
  data/real_games/YYYYMMDD/
    <game_id>.jsonl
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class DataCollector:
    """Collects and persists real match trajectories.

    Each game produces one JSONL file with one JSON object per line:
      - game_start: metadata (hero, MMR, timestamp)
      - step: state + action taken + action mask
      - game_end: placement, MMR change

    Args:
        data_dir: Root directory for collected data.
        enabled: If False, no data is written (opt-out).
    """

    def __init__(self, data_dir: str = "data/real_games", enabled: bool = True):
        self.data_dir = Path(data_dir)
        self.enabled = enabled
        self._current_game_id: Optional[str] = None
        self._current_file: Optional[Path] = None
        self._buffer: list[str] = []
        self._game_start_data: dict = {}

    # ── Public API ────────────────────────────────────────────────────────

    def start_game(self, game_id: str, meta: Optional[dict] = None) -> None:
        """Begin recording a new game."""
        if not self.enabled:
            return

        self._current_game_id = game_id
        self._buffer = []

        entry = {
            "type": "game_start",
            "game_id": game_id,
            "hero": meta.get("hero_card_id", "") if meta else "",
            "mmr": meta.get("mmr", 0) if meta else 0,
            "timestamp": datetime.now().isoformat(),
        }
        self._buffer.append(json.dumps(entry, ensure_ascii=False))
        self._game_start_data = meta or {}

    def record_step(
        self,
        state: dict,
        action_taken: int,
        action_mask: Any = None,
        turn: int = 0,
    ) -> None:
        """Record a single step in the current game."""
        if not self.enabled or self._current_game_id is None:
            return

        entry = {
            "type": "step",
            "turn": turn,
            "state": state,
            "action_taken": action_taken,
        }
        if action_mask is not None:
            import numpy as np

            if isinstance(action_mask, np.ndarray):
                entry["action_mask"] = action_mask.tolist()
            else:
                entry["action_mask"] = list(action_mask)

        self._buffer.append(json.dumps(entry, ensure_ascii=False))

    def end_game(self, placement: int, mmr_change: int = 0) -> Optional[str]:
        """Finalize and write the game trajectory to disk.

        Returns the file path, or None if disabled.
        """
        if not self.enabled or self._current_game_id is None:
            return None

        entry = {
            "type": "game_end",
            "game_id": self._current_game_id,
            "placement": placement,
            "mmr_change": mmr_change,
            "timestamp": datetime.now().isoformat(),
        }
        self._buffer.append(json.dumps(entry, ensure_ascii=False))

        # Write to disk
        filepath = self._make_filepath()
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            for line in self._buffer:
                f.write(line + "\n")

        self._current_game_id = None
        self._buffer = []
        return str(filepath)

    def cancel_game(self) -> None:
        """Discard the current game (e.g., player conceded early)."""
        self._current_game_id = None
        self._buffer = []

    # ── Internal ──────────────────────────────────────────────────────────

    def _make_filepath(self) -> Path:
        date_str = datetime.now().strftime("%Y%m%d")
        return self.data_dir / date_str / f"{self._current_game_id}.jsonl"

    # ── Stats ─────────────────────────────────────────────────────────────

    def total_games_collected(self) -> int:
        """Count how many game files exist in the data directory."""
        count = 0
        if self.data_dir.exists():
            for root, dirs, files in os.walk(self.data_dir):
                count += sum(1 for f in files if f.endswith(".jsonl"))
        return count
