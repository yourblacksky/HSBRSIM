"""
Benchmark NN-MCTS Agent vs Greedy Heuristic Baseline.

Runs N games where one player uses NN-MCTS and the other 7 use the
greedy Q-score heuristic. Reports average placement and win rate.

Usage:
    python -m hsrl.agents.benchmark_nn_mcts --games 50 --checkpoint checkpoints/bc_dual_head.pt
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from typing import Optional

import numpy as np

from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, State
from hsrl.core.game import Game
from hsrl.env.action import END_TURN, decode_action
from hsrl.env.reward import compute_placement


def run_benchmark(
    model_path: str = "checkpoints/bc_dual_head.pt",
    n_games: int = 50,
    mcts_iterations: int = 100,
    c_puct: float = 1.5,
    temperature: float = 0.0,
    use_mcts: bool = False,
    seed_start: int = 0,
    max_turns: int = 50,
    max_actions_per_turn: int = 50,
    verbose: bool = True,
    device: str = "auto",
) -> dict:
    """Run benchmark comparing NN-MCTS vs greedy heuristic.

    Player 0 uses NN-MCTS. Players 1-7 use greedy Q-score heuristic.

    Returns dict with: avg_rank, win_pct, top4_pct, placements, times.
    """
    import torch

    # ── Load model ──
    from hsrl.train.bc_trainer_v2 import load_checkpoint
    model, ckpt = load_checkpoint(model_path, device=device)
    value_mean = ckpt.get("value_mean", 0.0)
    value_std = ckpt.get("value_std", 1.0)
    print(f"Loaded checkpoint: value_mean={value_mean:.2f}, value_std={value_std:.2f}")

    from hsrl.agents.nn_mcts_agent import NNMCTSAgent

    # ── Load card data ──
    import hsrl.cards.minions.pool as _mp  # noqa: F401
    import hsrl.cards.minions.scripts as _ms  # noqa: F401
    import hsrl.cards.minions.tokens as _mt  # noqa: F401
    import hsrl.cards.heroes.pool as _hp  # noqa: F401
    import hsrl.cards.heroes.scripts as _hs  # noqa: F401
    import hsrl.cards.trinkets.scripts as _ts  # noqa: F401
    import hsrl.cards.rewards.scripts as _rs  # noqa: F401
    import hsrl.cards.anomalies.scripts as _as  # noqa: F401

    hero_ids = [
        cid for cid, data in CARDS._cards.items()
        if data.cardtype == CardType.HERO
        and not cid.startswith("EXAMPLE_")
    ]
    if not hero_ids:
        raise RuntimeError("No hero cards found")

    placements = []
    game_times = []
    wins = 0
    top4 = 0

    for game_idx in range(n_games):
        seed = seed_start + game_idx
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

        # Create agent with fresh RNG
        agent = NNMCTSAgent(
            model=model,
            value_mean=value_mean,
            value_std=value_std,
            n_iterations=mcts_iterations,
            c_puct=c_puct,
            temperature=temperature,
            use_mcts=use_mcts,
            seed=seed,
        )

        t_start = time.time()

        # ── Create game ──
        game = Game([])
        game.card_db = CARDS
        game.init_pool()

        chosen = random.sample(hero_ids, min(8, len(hero_ids)))
        players = [game.create_player(hid) for hid in chosen]
        game.players = players
        for p in players:
            p.game = game

        agent_player = players[0]
        opponent_players = players[1:]

        game.active_anomaly = True  # Block _apply_anomaly (already True)
        game.start_game()

        try:
            while game.state == State.RUNNING and game.turn <= max_turns:
                # ── Opponent auto-play (heuristic) ──
                for p in opponent_players:
                    if not p.is_alive:
                        continue
                    game.active_player = p
                    game._auto_player_turn(p)
                    game.resolve_queue()
                    # Auto-resolve pending targets randomly
                    while game._pending_targeted_queue:
                        game.auto_resolve_pending_target()

                # ── Agent MCTS play ──
                if agent_player.is_alive:
                    game.active_player = agent_player
                    for _ in range(max_actions_per_turn):
                        action = agent.act(game, agent_player)
                        if action == END_TURN:
                            break
                        result = decode_action(action, game, agent_player)
                        game.resolve_queue()
                        # Auto-resolve pending targets randomly
                        while game._pending_targeted_queue:
                            game.auto_resolve_pending_target()
                        agent.observe(action)

                # ── Combat ──
                game.end_recruit_phase()

                # Check for game over
                alive = [p for p in game.players if p.is_alive]
                if len(alive) <= 1:
                    game.state = State.COMPLETE

        except Exception as e:
            if verbose:
                print(f"  Game {game_idx + 1} (seed={seed}) ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

        elapsed = time.time() - t_start
        game_times.append(elapsed)

        placement = compute_placement(agent_player, game.players)
        placements.append(placement)
        if placement == 1:
            wins += 1
        if placement <= 4:
            top4 += 1

        if verbose:
            hero_name = agent_player.get_tag(GameTag.NAME) or "?"
            print(f"  Game {game_idx + 1:3d}/{n_games}: "
                  f"rank={placement} hero={hero_name} "
                  f"turns={game.turn} time={elapsed:.1f}s "
                  f"[wins={wins}, top4={top4}]")

    # ── Summary ──
    n_completed = len(placements)
    avg_rank = np.mean(placements) if placements else 0.0
    win_pct = wins / n_completed * 100 if n_completed else 0.0
    top4_pct = top4 / n_completed * 100 if n_completed else 0.0
    avg_time = np.mean(game_times) if game_times else 0.0

    print(f"\n{'='*60}")
    print(f"NN-MCTS Benchmark Results ({n_completed} games)")
    print(f"{'='*60}")
    print(f"  Avg Rank:     {avg_rank:.2f}  (greedy baseline ~4.5)")
    print(f"  Win %:        {win_pct:.1f}%")
    print(f"  Top4 %:       {top4_pct:.1f}%")
    print(f"  Avg Time:     {avg_time:.1f}s/game")
    print(f"  Placements:   {dict(sorted((p, placements.count(p)) for p in range(1, 9)))}")

    return {
        "avg_rank": avg_rank,
        "win_pct": win_pct,
        "top4_pct": top4_pct,
        "placements": placements,
        "avg_time": avg_time,
        "n_games": n_completed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark NN-MCTS vs Greedy")
    parser.add_argument("--checkpoint", type=str, default="checkpoints/bc_dual_head.pt")
    parser.add_argument("--games", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=100,
                       help="MCTS iterations per decision")
    parser.add_argument("--c-puct", type=float, default=1.5)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--mcts", action="store_true", default=False,
                       help="Use MCTS search (default: policy argmax)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    run_benchmark(
        model_path=args.checkpoint,
        n_games=args.games,
        mcts_iterations=args.iterations,
        c_puct=args.c_puct,
        temperature=args.temperature,
        use_mcts=args.mcts,
        seed_start=args.seed,
        device=args.device,
    )
