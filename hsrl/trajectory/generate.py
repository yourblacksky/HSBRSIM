"""
Batch Trajectory Generator

Runs N heuristic-only games and saves winner trajectories to disk.

Usage:
    python -m hsrl.trajectory.generate --games 1000 --output data/trajectories/
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import List, Optional, Tuple

from hsrl.core.game import Game
from hsrl.trajectory.record import Trajectory, TrajectoryRecorder, snapshot_player


def _run_game_with_recording(
    hero_ids: List[str],
    seed: int,
    max_turns: int = 50,
) -> Optional[Trajectory]:
    """Run one heuristic game and return the winner's trajectory.

    Records board state after each recruit phase (pre-combat snapshot).
    """
    from hsrl.core.card_db import CARDS
    from hsrl.core.enums import GameTag, State

    game = Game([])
    game.card_db = CARDS
    game.init_pool()

    players = [game.create_player(hid) for hid in hero_ids]
    game.players = players
    for p in players:
        p.game = game

    # Disable anomaly for clean trajectory generation
    game.active_anomaly = True  # Blocks _apply_anomaly in start_game
    game.start_game()
    recorder = TrajectoryRecorder(game, seed=seed)

    while game.state == State.RUNNING:
        # Run recruit phase (heuristic auto-play for all players)
        game._auto_recruit_actions()

        # Snapshot AFTER recruit, BEFORE combat — captures the combat board
        recorder.snapshot_all()

        # Run combat
        game.end_recruit_phase()

        # Check for game over
        alive = [p for p in game.players if p.is_alive]
        if len(alive) <= 1:
            game.state = State.COMPLETE
        elif game.turn >= max_turns:
            game.state = State.COMPLETE

    # Determine winner(s)
    alive = [p for p in game.players if p.is_alive]
    if not alive:
        alive = game.players
    winner = max(alive, key=lambda p: (p.health, p.tavern_tier))
    winner_idx = game.players.index(winner)

    trajectories = recorder.get_trajectories()
    winner_card_id = winner.get_tag(GameTag.CARD_ID) or ""
    for t in trajectories:
        if t.hero_id == winner_card_id:
            t.game_id = f"traj_{seed:06d}"
            return t

    # Fallback: build trajectory from winner manually
    turns = [snapshot_player(winner, t) for t in range(1, game.turn + 1)]
    active_tribe_names = [t.name for t in (game.active_tribes or [])]
    return Trajectory(
        game_id=f"traj_{seed:06d}",
        hero_id=winner_card_id,
        hero_name=winner.get_tag(GameTag.NAME) or "",
        seed=seed,
        active_tribes=active_tribe_names,
        placement=1,
        final_health=winner.health,
        final_tier=winner.tavern_tier,
        turns=turns,
        anomaly_id=(
            game.active_anomaly.get_tag(GameTag.CARD_ID)
            if game.active_anomaly and not isinstance(game.active_anomaly, bool)
            else None
        ),
    )


def generate_trajectories(
    n_games: int = 1000,
    output_dir: str = "data/trajectories",
    seed_start: int = 0,
    max_turns: int = 50,
    verbose: bool = True,
) -> List[str]:
    """Run N heuristic games and save winner trajectories.

    Returns list of saved trajectory file paths.
    """
    from hsrl.core.card_db import CARDS
    from hsrl.core.enums import CardType

    # Ensure card modules are loaded so registry is populated
    import hsrl.cards.minions.pool as _mp  # noqa: F401
    import hsrl.cards.minions.scripts as _ms  # noqa: F401
    import hsrl.cards.minions.tokens as _mt  # noqa: F401
    import hsrl.cards.heroes.pool as _hp  # noqa: F401
    import hsrl.cards.heroes.scripts as _hs  # noqa: F401
    import hsrl.cards.trinkets.scripts as _ts  # noqa: F401
    import hsrl.cards.rewards.scripts as _rs  # noqa: F401
    import hsrl.cards.anomalies.scripts as _as  # noqa: F401

    os.makedirs(output_dir, exist_ok=True)
    index_path = os.path.join(output_dir, "index.jsonl")
    saved = []

    # Get valid hero pool (exclude example/test heroes)
    hero_ids = [
        cid for cid, data in CARDS._cards.items()
        if data.cardtype == CardType.HERO
        and not cid.startswith("EXAMPLE_")
    ]
    if not hero_ids:
        raise RuntimeError("No hero cards found in card database")

    if verbose:
        print(f"Hero pool: {len(hero_ids)} heroes")
        print(f"Generating {n_games} trajectories...")

    t_start = time.time()

    for i in range(n_games):
        seed = seed_start + i
        random.seed(seed)

        # Pick 8 random heroes
        chosen = random.sample(hero_ids, min(8, len(hero_ids)))
        if len(chosen) < 8:
            chosen = chosen * (8 // len(chosen)) + chosen[:8 % len(chosen)]

        try:
            traj = _run_game_with_recording(chosen, seed, max_turns)
        except Exception as e:
            if verbose:
                print(f"  Game {i} (seed={seed}) FAILED: {e}")
            continue

        if traj is None:
            continue

        # Save trajectory
        filepath = os.path.join(output_dir, f"traj_{seed:06d}.json")
        with open(filepath, "w") as f:
            f.write(traj.to_json())

        # Append to index
        with open(index_path, "a") as f:
            index_entry = {
                "game_id": traj.game_id,
                "hero_id": traj.hero_id,
                "hero_name": traj.hero_name,
                "active_tribes": traj.active_tribes,
                "placement": traj.placement,
                "anomaly_id": traj.anomaly_id,
            }
            f.write(json.dumps(index_entry, separators=(",", ":")) + "\n")

        saved.append(filepath)

        if verbose and (i + 1) % 100 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  {i + 1}/{n_games} games ({rate:.1f}/s)")

    elapsed = time.time() - t_start
    if verbose:
        print(f"Done: {len(saved)}/{n_games} trajectories saved in {elapsed:.1f}s")
        print(f"Output: {output_dir}/")

    return saved


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Generate HSRL trajectories")
    p.add_argument("--games", type=int, default=100,
                   help="Number of games to run")
    p.add_argument("--output", type=str, default="data/trajectories",
                   help="Output directory")
    p.add_argument("--seed", type=int, default=0,
                   help="Starting seed")
    p.add_argument("--max-turns", type=int, default=50,
                   help="Max turns per game")
    args = p.parse_args()

    generate_trajectories(
        n_games=args.games,
        output_dir=args.output,
        seed_start=args.seed,
        max_turns=args.max_turns,
    )
