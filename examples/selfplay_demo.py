"""Minimal self-play demo on FullGameSelfPlayEnv (random policies, full combat).

Run from the repository root:

    PYTHONPATH=. python3 examples/selfplay_demo.py

The agent interface is `callable(obs, mask) -> int` (legacy 50-way action id,
28 = END_TURN). Replace `random_agent`/`greedy_agent` with your own policy
(e.g. a trained network) to run self-play training.
"""
import time

import numpy as np

# Card registration must happen before any Game is created.
import hsrl.cards.heroes  # noqa: F401
import hsrl.cards.minions  # noqa: F401
import hsrl.cards.spells  # noqa: F401

from hsrl.rl_env.envs.full_game_env import FullGameSelfPlayEnv

END_TURN = 28


def random_agent(obs, mask):
    if mask is None:
        return END_TURN
    legal = [i for i, m in enumerate(mask) if m]
    if not legal:
        return END_TURN
    if np.random.rand() < 0.2 and mask[END_TURN]:
        return END_TURN
    return int(np.random.choice(legal))


def greedy_agent(obs, mask):
    """Heuristic: buy slots first, then refresh, upgrade, end turn."""
    if mask is None:
        return END_TURN
    legal = [i for i, m in enumerate(mask) if m]
    if not legal:
        return END_TURN
    for pref in (0, 1, 2, 3, 24, 25, 28):  # buy 0-3, refresh, upgrade, end
        if pref < len(mask) and mask[pref]:
            return pref
    return int(np.random.choice(legal))


if __name__ == "__main__":
    # turn_limit=50 so a full 8-player game can actually finish (random
    # policies deal small damage per combat; 15 turns is not enough).
    env = FullGameSelfPlayEnv(turn_limit=50, skip_combat=False, seed=42)
    for g in range(3):
        t0 = time.time()
        traj = env.run_game([random_agent] * 8, seed=100 + g)
        dt = time.time() - t0
        ranks = sorted(
            (t.final_rank_if_game_finished, t.player_id) for t in traj.trajectories
        )
        print(
            f"game {g}: {len(traj.trajectories)} turns recorded, {dt:.2f}s, "
            f"placements={[r[0] for r in ranks]}"
        )
    print("self-play demo OK")
