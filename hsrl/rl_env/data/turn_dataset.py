"""
TurnDataset — turn-level training data storage and loading.

Supports:
  - Append-only writing of TurnTrajectory records
  - Filtering by source, turn, agent type
  - Shuffling by game or by turn
  - Streaming iteration for large datasets
  - Export to .jsonl for portability
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from typing import Iterator, Optional

import numpy as np


@dataclass
class TurnDatasetRecord:
    """One record in the turn dataset (serializable version of TurnTrajectory)."""
    record_id: str = ""
    source: str = "unknown"
    patch_version: str = "35.6.0"
    game_id: str = ""
    seed: int = 0
    player_id: int = 0
    turn_id: int = 0

    # Observations (serialized as numpy arrays or lists)
    start_observation: dict = field(default_factory=dict)

    # Action sequence
    action_sequence: list[dict] = field(default_factory=list)
    option_label: dict | None = None

    # Labels
    board_score_before: float = 0.0
    board_score_after: float = 0.0
    board_score_delta: float = 0.0
    gold_spent: int = 0
    placement: int | None = None
    final_rank: int | None = None
    top4: bool = False
    top1: bool = False

    labels: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "source": self.source,
            "game_id": self.game_id,
            "player_id": self.player_id,
            "turn_id": self.turn_id,
            "board_score_before": self.board_score_before,
            "board_score_after": self.board_score_after,
            "board_score_delta": self.board_score_delta,
            "gold_spent": self.gold_spent,
            "placement": self.placement,
            "top4": self.top4,
            "top1": self.top1,
            "action_count": len(self.action_sequence),
            "labels": self.labels,
        }


class TurnDataset:
    """In-memory turn-level training dataset.

    Stores records from multiple sources (heuristic, policy, search, population).
    Supports filtering, shuffling, and iteration for training loops.
    """

    def __init__(self, max_size: int = 100000):
        self._records: list[TurnDatasetRecord] = []
        self.max_size = max_size

    # ── Write ──

    def add_trajectory(self, traj) -> TurnDatasetRecord:
        """Add a TurnTrajectory to the dataset. Returns the created record."""
        record = TurnDatasetRecord(
            record_id=f"{traj.game_id}_{traj.player_id}_{traj.turn_id}",
            source=traj.source,
            game_id=traj.game_id,
            player_id=traj.player_id,
            turn_id=traj.turn_id,
            start_observation=traj.start_observation,
            action_sequence=[
                a.to_dict() if hasattr(a, 'to_dict') else str(a)
                for a in traj.action_sequence
            ],
            board_score_before=traj.board_score_before,
            board_score_after=traj.board_score_after,
            board_score_delta=traj.board_score_delta,
            gold_spent=traj.gold_spent,
            placement=traj.placement_if_terminal,
            final_rank=traj.final_rank_if_game_finished,
            top4=traj.top4,
            top1=traj.top1,
            labels=traj.labels,
        )
        self._records.append(record)
        if len(self._records) > self.max_size:
            self._records.pop(0)
        return record

    def add_game(self, game_traj) -> list[TurnDatasetRecord]:
        """Add all trajectories from a GameTrajectory."""
        records = []
        for traj in game_traj.trajectories:
            records.append(self.add_trajectory(traj))
        return records

    # ── Read ──

    def filter(
        self,
        source: str | None = None,
        min_turn: int | None = None,
        max_turn: int | None = None,
        min_board_delta: float | None = None,
        top4_only: bool = False,
    ) -> list[TurnDatasetRecord]:
        """Filter records by criteria."""
        result = []
        for r in self._records:
            if source is not None and r.source != source: continue
            if min_turn is not None and r.turn_id < min_turn: continue
            if max_turn is not None and r.turn_id > max_turn: continue
            if min_board_delta is not None and r.board_score_delta < min_board_delta: continue
            if top4_only and not r.top4: continue
            result.append(r)
        return result

    def shuffle(self, seed: int = 0) -> None:
        """Shuffle records in-place."""
        rng = random.Random(seed)
        rng.shuffle(self._records)

    def sample(self, n: int, seed: int = 0) -> list[TurnDatasetRecord]:
        """Sample n records without replacement."""
        rng = random.Random(seed)
        return rng.sample(self._records, min(n, len(self._records)))

    def iter_batches(self, batch_size: int) -> Iterator[list[TurnDatasetRecord]]:
        """Iterate over batches of records."""
        for i in range(0, len(self._records), batch_size):
            yield self._records[i:i + batch_size]

    # ── Stats ──

    @property
    def size(self) -> int:
        return len(self._records)

    @property
    def avg_board_delta(self) -> float:
        if not self._records: return 0.0
        return np.mean([r.board_score_delta for r in self._records])

    @property
    def avg_gold_spent(self) -> float:
        if not self._records: return 0.0
        return np.mean([r.gold_spent for r in self._records])

    @property
    def top4_rate(self) -> float:
        if not self._records: return 0.0
        return np.mean([1.0 if r.top4 else 0.0 for r in self._records])

    def stats(self) -> dict:
        """Return summary statistics."""
        return {
            "size": self.size,
            "avg_board_delta": self.avg_board_delta,
            "avg_gold_spent": self.avg_gold_spent,
            "top4_rate": self.top4_rate,
            "sources": self._source_counts(),
            "turn_distribution": self._turn_counts(),
        }

    # ── Export ──

    def to_jsonl(self, path: str) -> None:
        """Export records to a JSONL file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, 'w') as f:
            for r in self._records:
                f.write(json.dumps(r.to_dict()) + '\n')

    @classmethod
    def from_jsonl(cls, path: str) -> "TurnDataset":
        """Load records from a JSONL file."""
        ds = cls()
        valid_fields = set(TurnDatasetRecord.__dataclass_fields__.keys())
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                # Filter to only valid fields
                filtered = {k: v for k, v in d.items() if k in valid_fields}
                record = TurnDatasetRecord(**filtered)
                ds._records.append(record)
        return ds

    def clear(self) -> None:
        self._records.clear()

    # ── Internal ──

    def _source_counts(self) -> dict:
        counts = {}
        for r in self._records:
            counts[r.source] = counts.get(r.source, 0) + 1
        return counts

    def _turn_counts(self) -> dict:
        counts = {}
        for r in self._records:
            counts[r.turn_id] = counts.get(r.turn_id, 0) + 1
        return dict(sorted(counts.items()))
