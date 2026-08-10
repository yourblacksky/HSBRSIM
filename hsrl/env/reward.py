"""Legacy reward helpers (compat shim over the rl_env v2 reward modules).

The old ``hsrl.env`` package only shipped ``action.py``. Several modules
(``rl_env/action/plan_executor.py``, ``rl_env/reward/rank_labels.py``,
``rl_env/envs/full_game_env.py``) still import from ``hsrl.env.reward``.
This shim re-exports equivalent functionality from the v2 implementations.
"""

from __future__ import annotations

from hsrl.rl_env.reward.board_score import compute_board_score_v2


def compute_board_strength(player) -> float:
    """Legacy API: total board strength as a single float.

    Used by PlanExecutor to compare board state before/after a plan.
    """
    return compute_board_score_v2(player).total


def compute_placement(player, players) -> int:
    """Legacy API: 1-based placement of *player* among *players*.

    Approximation of Battlegrounds placement: players still alive are
    ranked by health (descending); eliminated players are appended after
    them in health order. Used to fill rank labels for reward shaping.
    """
    if player not in players:
        return len(players)

    alive = [p for p in players if getattr(p, "health", 0) > 0]
    dead = [p for p in players if getattr(p, "health", 0) <= 0]

    def sort_key(p):
        return (getattr(p, "health", 0), -getattr(p, "tavern_tier", 0))

    ordered = sorted(alive, key=sort_key, reverse=True) + sorted(dead, key=sort_key, reverse=True)
    return ordered.index(player) + 1
