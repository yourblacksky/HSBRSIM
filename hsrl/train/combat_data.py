"""
Combat Data Collector for Board Evaluation Training.

Runs full Battlegrounds games and harvests every combat outcome as
(board_A, board_B, A_wins) training samples. Combat has randomness
(target selection, first attacker, card effects), so each pair
naturally produces different outcomes when repeated across games.

Output: data/combat_pairs/combats.npz
  - boards_a: (n_combats, 7, 15) encodings
  - boards_b: (n_combats, 7, 15) encodings
  - labels: (n_combats,) 1.0 if A won, 0.0 if B won, 0.5 if tie
"""

from __future__ import annotations

import argparse
import os
import random
import time
from typing import List, Optional, Tuple

import numpy as np

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def encode_board_from_minions(minions) -> np.ndarray:
    """Encode a list of Minion objects as (7, 15) feature matrix."""
    from hsrl.core.enums import GameTag

    arr = np.zeros((7, 15), dtype=np.float32)
    living = [m for m in minions if not m.dead]
    for i, m in enumerate(living[:7]):
        arr[i, 0] = min(m.atk / 100.0, 1.0)
        arr[i, 1] = min(m.health / 100.0, 1.0)
        arr[i, 2] = min(m.max_health / 100.0, 1.0)
        arr[i, 3] = m.tech_level / 7.0
        arr[i, 4] = float(m.get_tag(GameTag.RACE, 0) or 0) / 12.0
        arr[i, 5] = 1.0 if m.taunt else 0.0
        arr[i, 6] = 1.0 if m.divine_shield else 0.0
        arr[i, 7] = 1.0 if m.poisonous else 0.0
        arr[i, 8] = 1.0 if m.venomous else 0.0
        arr[i, 9] = 1.0 if m.reborn else 0.0
        arr[i, 10] = 1.0 if m.windfury else 0.0
        arr[i, 11] = 1.0 if m.cleave else 0.0
        arr[i, 12] = 1.0 if m.is_golden else 0.0
        arr[i, 13] = 0.0  # exhausted — all minions start fresh in combat
        arr[i, 14] = 1.0 if m.has_tag(GameTag.DIVINE_SHIELD) else 0.0
    return arr


def harvest_combat(game, player_a, player_b, boards_a, boards_b) -> Tuple[
    Optional[np.ndarray], Optional[np.ndarray], Optional[float]
]:
    """After combat, determine winner and encode boards.

    Returns (board_enc_a, board_enc_b, label) or (None, None, None) if skipped.
    """
    # Reconstruct pre-combat boards from the saved originals
    board_a = boards_a
    board_b = boards_b

    # Filter to living minions for encoding
    enc_a = encode_board_from_minions(board_a)
    enc_b = encode_board_from_minions(board_b)

    # Determine winner: compare surviving board stats
    # (board with more total surviving stats won the combat)
    living_a = [m for m in board_a if not m.dead]
    living_b = [m for m in board_b if not m.dead]

    stats_a = sum(m.atk + m.health for m in living_a)
    stats_b = sum(m.atk + m.health for m in living_b)

    if stats_a == 0 and stats_b == 0:
        label = 0.5  # tie — both boards wiped
    elif stats_a > stats_b:
        label = 1.0  # A wins
    elif stats_b > stats_a:
        label = 0.0  # B wins
    else:
        label = 0.5  # equal stats — tie

    return enc_a, enc_b, label


def collect_combat_data(
    n_games: int = 500,
    seed_start: int = 0,
    verbose: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run games and harvest all combat outcomes.

    Returns:
        boards_a: (n_combats, 7, 15)
        boards_b: (n_combats, 7, 15)
        labels: (n_combats,)
    """
    from hsrl.core.card_db import CARDS
    from hsrl.core.enums import CardType, State
    from hsrl.core.game import Game

    # Ensure card modules loaded
    import hsrl.cards.minions.pool as _mp  # noqa
    import hsrl.cards.minions.scripts as _ms  # noqa
    import hsrl.cards.minions.tokens as _mt  # noqa
    import hsrl.cards.heroes.pool as _hp  # noqa
    import hsrl.cards.heroes.scripts as _hs  # noqa
    import hsrl.cards.trinkets.scripts as _ts  # noqa
    import hsrl.cards.rewards.scripts as _rs  # noqa
    import hsrl.cards.anomalies.scripts as _as  # noqa

    hero_ids = [
        cid for cid, data in CARDS._cards.items()
        if data.cardtype == CardType.HERO
        and not cid.startswith("EXAMPLE_")
    ]

    all_boards_a = []
    all_boards_b = []
    all_labels = []

    t_start = time.time()

    for game_idx in range(n_games):
        seed = seed_start + game_idx
        random.seed(seed)
        np.random.seed(seed)

        chosen = random.sample(hero_ids, min(8, len(hero_ids)))

        game = Game([])
        game.card_db = CARDS
        game.init_pool()
        players = [game.create_player(hid) for hid in chosen]
        game.players = players
        for p in players:
            p.game = game
        game.active_anomaly = True
        game.start_game()

        # Track combat outcomes within this game
        game_combats = 0

        while game.state == State.RUNNING and game.turn <= 30:
            # All players auto-play (heuristic)
            for p in players:
                if not p.is_alive:
                    continue
                game.active_player = p
                game._auto_player_turn(p)
                game.resolve_queue()
                while game._pending_targeted_queue:
                    game.auto_resolve_pending_target()

            # Hook combat: capture pre-combat boards before end_recruit_phase
            # Save copies of all alive players' boards
            pre_combat_boards = {}
            for p in players:
                if p.is_alive:
                    pre_combat_boards[p.entity_id] = list(p.board)

            # Run combat
            game.end_recruit_phase()

            # Harvest combat outcomes
            pairs = getattr(game, '_combat_pairs', None)
            if pairs:
                for p_a, p_b in pairs:
                    if p_b is None:
                        continue  # ghost match — skip
                    boards_a = pre_combat_boards.get(p_a.entity_id, [])
                    boards_b = pre_combat_boards.get(p_b.entity_id, [])
                    if not boards_a or not boards_b:
                        continue
                    enc_a, enc_b, label = harvest_combat(
                        game, p_a, p_b, boards_a, boards_b)
                    if enc_a is not None:
                        all_boards_a.append(enc_a)
                        all_boards_b.append(enc_b)
                        all_labels.append(label)
                        game_combats += 1

            # Check game over
            alive = [p for p in game.players if p.is_alive]
            if len(alive) <= 1:
                game.state = State.COMPLETE

        if verbose and (game_idx + 1) % 50 == 0:
            elapsed = time.time() - t_start
            total_combats = len(all_labels)
            print(f"  {game_idx + 1}/{n_games} games, {total_combats} combats "
                  f"({elapsed:.0f}s, {total_combats / elapsed:.1f} combats/s)", flush=True)

    elapsed = time.time() - t_start
    boards_a = np.array(all_boards_a, dtype=np.float32)
    boards_b = np.array(all_boards_b, dtype=np.float32)
    labels = np.array(all_labels, dtype=np.float32)

    print(f"\nCollected {len(labels)} combat samples from {n_games} games in {elapsed:.0f}s")
    print(f"  boards_a: {boards_a.shape}, boards_b: {boards_b.shape}")
    print(f"  labels: {labels.shape}, win_a={labels.mean():.3f}")
    print(f"  label distribution: {dict(zip(*np.unique(labels, return_counts=True)))}")

    return boards_a, boards_b, labels


def main():
    parser = argparse.ArgumentParser(description="Collect combat training data from games")
    parser.add_argument("--games", type=int, default=500,
                        help="Number of games to run")
    parser.add_argument("--output", type=str, default="data/combat_pairs/combats.npz")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    boards_a, boards_b, labels = collect_combat_data(
        n_games=args.games,
        seed_start=args.seed,
    )

    np.savez_compressed(
        args.output,
        boards_a=boards_a,
        boards_b=boards_b,
        labels=labels,
    )
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
