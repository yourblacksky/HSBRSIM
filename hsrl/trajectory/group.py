"""
Type-Compatible Trajectory Grouping

Groups trajectories by compatible tribe sets so each group contains
trajectories that could appear in the same game (same active tribes).

Real Battlegrounds selects 5 of 10 tribes per match. Two tribe sets are
"compatible" if their intersection has ≥ 3 tribes — enough that a third
game filtered to the intersection would include minions from both.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Dict, FrozenSet, List, Optional, Tuple


def _load_index(index_path: str) -> List[dict]:
    """Load trajectory index (one JSON object per line)."""
    entries = []
    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _tribe_compatibility_score(
    tribes_a: FrozenSet[str],
    tribes_b: FrozenSet[str],
) -> float:
    """Jaccard-like score: |intersection| / max(|A|, |B|)."""
    if not tribes_a or not tribes_b:
        return 0.0
    inter = len(tribes_a & tribes_b)
    denom = max(len(tribes_a), len(tribes_b))
    return inter / denom if denom > 0 else 0.0


def build_compatible_groups(
    index_path: str = "data/trajectories/index.jsonl",
    min_per_group: int = 7,
    min_compatibility: float = 0.6,
) -> List[List[str]]:
    """Group trajectories by compatible tribe sets.

    Each group is a list of trajectory game_ids that share enough tribe
    overlap to plausibly appear in the same game.

    Algorithm:
    1. Partition by exact tribe set (primary key).
    2. Merge under-sized groups with the most compatible neighbor.
    3. Ensure each final group has ≥ min_per_group trajectories.

    Returns list of groups, each group being a list of game_ids.
    """
    entries = _load_index(index_path)
    if not entries:
        return []

    # 1. Partition by exact tribe set
    by_tribes: Dict[FrozenSet[str], List[str]] = defaultdict(list)
    for e in entries:
        key = frozenset(e.get("active_tribes", []))
        by_tribes[key].append(e["game_id"])

    groups = list(by_tribes.items())  # [(frozenset, [game_ids]), ...]

    # 2. Merge groups that are smaller than min_per_group
    changed = True
    while changed:
        changed = False
        for i in range(len(groups)):
            tribes_i, ids_i = groups[i]
            if len(ids_i) >= min_per_group:
                continue
            # Find best merge partner
            best_score = -1.0
            best_j = -1
            for j in range(len(groups)):
                if j == i:
                    continue
                tribes_j, _ = groups[j]
                score = _tribe_compatibility_score(tribes_i, tribes_j)
                if score > best_score and score >= min_compatibility:
                    best_score = score
                    best_j = j
            if best_j >= 0:
                # Merge j into i: use intersection tribes as the merged key
                tribes_j, ids_j = groups[best_j]
                merged_tribes = tribes_i & tribes_j
                if not merged_tribes:
                    merged_tribes = tribes_i | tribes_j  # fallback: union
                merged_ids = ids_i + ids_j
                groups[i] = (merged_tribes, merged_ids)
                groups.pop(best_j)
                changed = True
                break

    # 3. Build result sorted by group size (largest first)
    groups.sort(key=lambda g: len(g[1]), reverse=True)
    return [ids for _, ids in groups if ids]


def print_group_stats(groups: List[List[str]]) -> None:
    """Print a summary of group sizes."""
    sizes = [len(g) for g in groups]
    print(f"Groups: {len(groups)}")
    print(f"Total trajectories: {sum(sizes)}")
    print(f"Sizes: min={min(sizes) if sizes else 0}, "
          f"max={max(sizes) if sizes else 0}, "
          f"mean={sum(sizes) / len(sizes):.1f}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Group trajectories by tribe compatibility")
    p.add_argument("--index", type=str, default="data/trajectories/index.jsonl")
    p.add_argument("--min-per-group", type=int, default=7)
    args = p.parse_args()

    groups = build_compatible_groups(
        index_path=args.index,
        min_per_group=args.min_per_group,
    )
    print_group_stats(groups)
