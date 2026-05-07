#!/usr/bin/env python3
"""
HSBRSIM Demo — 8-Player Battlegrounds with Readable Log Output

Usage:
    python -m hsrl.demo              # run with random heroes
    python -m hsrl.demo --seed 42    # reproducible run
    python -m hsrl.demo --quiet      # results only
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import List, Optional

# ── Card registrations ──────────────────────────────────────────────────────
import hsrl.cards.minions      # noqa: F401
import hsrl.cards.spells       # noqa: F401
import hsrl.cards.heroes       # noqa: F401
import hsrl.cards.trinkets     # noqa: F401
import hsrl.cards.rewards      # noqa: F401
import hsrl.cards.anomalies    # noqa: F401

from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.core.enums import GameTag, Race, State
from hsrl.core.card_db import CARDS


# ═════════════════════════════════════════════════════════════════════════════
# Formatting
# ═════════════════════════════════════════════════════════════════════════════

_RACE_ICON = {
    Race.BEAST: "\U0001f43e", Race.MECH: "⚙", Race.MURLOC: "\U0001f41f",
    Race.DEMON: "\U0001f47f", Race.DRAGON: "\U0001f409", Race.PIRATE: "\U0001f3f4",
    Race.ELEMENTAL: "\U0001f30a", Race.QUILBOAR: "\U0001f417", Race.NAGA: "\U0001f40d",
    Race.UNDEAD: "\U0001f480",
}


def _fmt_m(m) -> str:
    """Format a minion: Name(atk/hp)[keywords][race]"""
    if m is None or m.dead:
        return ""
    name = m.get_tag(GameTag.NAME, "?")
    atk = int(m.atk) if hasattr(m, "atk") else m.get_tag(GameTag.ATK, 0)
    hp = int(m.health) if hasattr(m, "health") else m.get_tag(GameTag.HEALTH, 0)
    icon = _RACE_ICON.get(m.race if hasattr(m, "race") else m.get_tag(GameTag.RACE, 0), "")
    g = "★" if (hasattr(m, "is_golden") and m.is_golden) else ""
    ds = "\U0001f6e1" if m.get_tag(GameTag.DIVINE_SHIELD, 0) else ""
    rb = "♾" if m.get_tag(GameTag.REBORN, 0) else ""
    tk = "T" if m.get_tag(GameTag.TAUNT, 0) else ""
    pos = "☠" if m.get_tag(GameTag.POISONOUS, 0) else ""
    return f"{g}{name}({atk}/{hp}){ds}{tk}{pos}{rb}{icon}"


def _fmt_p(p: Player, idx: int) -> str:
    """Format a player status line."""
    name = p.get_tag(GameTag.NAME, f"P{idx+1}")
    hp = p.health
    armor = f" +{p.armor}A" if p.armor > 0 else ""
    tier = p.tavern_tier
    board = p.get_board_minions()
    return f"P{idx+1} {name}  HP={hp}{armor}  Tier{tier}  Board={len(board)}"


# ═════════════════════════════════════════════════════════════════════════════
# Demo
# ═════════════════════════════════════════════════════════════════════════════

def _pick_heroes(n: int = 8, seed: Optional[int] = None) -> List[str]:
    if seed is not None:
        random.seed(seed)
    all_heroes = [
        cid for cid in CARDS.all_ids()
        if cid.startswith("BG20_HERO_") or cid.startswith("TB_BaconShop_HERO_")
    ]
    if len(all_heroes) < n:
        examples = [cid for cid in CARDS.all_ids() if cid.startswith("EXAMPLE_HERO")]
        all_heroes.extend(examples)
    return random.sample(all_heroes, min(n, len(all_heroes)))


def run_demo(
    hero_ids: Optional[List[str]] = None,
    seed: Optional[int] = None,
    max_turns: int = 50,
) -> Game:
    if seed is not None:
        random.seed(seed)

    if hero_ids is None:
        hero_ids = _pick_heroes(8, seed=seed)
    if len(hero_ids) != 8:
        raise ValueError(f"Need 8 hero IDs, got {len(hero_ids)}")

    out = sys.stdout

    # ── Header ─────────────────────────────────────────────────────────
    out.write("\n" + "=" * 70 + "\n")
    out.write("  HSBRSIM — 8-Player Battlegrounds Demo\n")
    out.write("=" * 70 + "\n")
    out.write(f"  Seed: {seed if seed is not None else 'random'}"
              f"  |  Max turns: {max_turns}\n\n")
    out.write("  Heroes:\n")
    for i, hid in enumerate(hero_ids):
        card = CARDS.get(hid)
        name = card.name if card else hid
        out.write(f"    [{i+1}] {name}  ({hid})\n")
    out.write("\n" + "=" * 70 + "\n")

    # ── Create game ─────────────────────────────────────────────────────
    game = Game.create_game(hero_ids, card_db=CARDS, apply_anomaly=False)
    game.card_db = CARDS
    players = game.players

    # ── Main loop ───────────────────────────────────────────────────────
    turn_start_board = {}  # player_idx → set of minion ids (for board diff)

    while game.state == State.RUNNING and game.turn <= max_turns:
        turn = game.turn
        alive = [p for p in players if p.health > 0]

        # Phase header
        out.write(f"\n{'─'*70}\n")
        out.write(f"  TURN {turn}\n")
        out.write(f"{'─'*70}\n")

        # Player summary before turn
        out.write(f"  {'Player':<28s} {'HP':>4s} {'Tier':>4s} {'Gold':>4s}  Board\n")
        out.write(f"  {'-'*26}  {'-'*4} {'-'*4} {'-'*4}  {'-'*20}\n")
        for p in alive:
            idx = players.index(p)
            board = p.get_board_minions()
            board_str = "  ".join(_fmt_m(m) for m in board[:7]) if board else "(empty)"
            out.write(f"  {_fmt_p(p, idx):<28s}  {p.gold:>3d}g  {board_str}\n")

        # Record pre-turn board
        turn_start_board = {}
        for p in alive:
            idx = players.index(p)
            turn_start_board[idx] = {id(m) for m in p.get_board_minions()}

        # Run turn
        game.run_turn()

        # Combat results
        out.write(f"\n  >>> Combat results:\n")
        for p in players:
            idx = players.index(p)
            pre = turn_start_board.get(idx, set())
            post = {id(m) for m in p.get_board_minions()}
            lost = len(pre - post)
            gained = len(post - pre)
            delta = ""
            if lost > 0:
                delta += f" -{lost}"
            if gained > 0:
                delta += f" +{gained}"

            hp = p.health
            if hp > 0:
                board = p.get_board_minions()
                board_str = "  ".join(_fmt_m(m) for m in board[:7]) if board else "(empty)"
                out.write(f"  {_fmt_p(p, idx):<28s}  {delta:<6s}  {board_str}\n")
            else:
                name = p.get_tag(GameTag.NAME, f"P{idx+1}")
                out.write(f"  \033[91m{_fmt_p(p, idx):<28s}  ELIMINATED\033[0m\n")

        if game.state == State.COMPLETE:
            break

    # ── Final standings ─────────────────────────────────────────────────
    out.write(f"\n{'='*70}\n")
    out.write(f"  FINAL STANDINGS\n")
    out.write(f"{'='*70}\n\n")

    ranked = sorted(players, key=lambda p: (-p.health, p.tavern_tier))

    for rank, p in enumerate(ranked, 1):
        idx = players.index(p)
        name = p.get_tag(GameTag.NAME, f"P{idx+1}")
        board = p.get_board_minions()
        board_str = "  ".join(_fmt_m(m) for m in board[:7]) if board else "(empty)"

        medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(rank, f"#{rank}")
        if p.health <= 0:
            medal = f"#{rank}"
        out.write(f"  {medal:<4s} {name:<25s} HP={p.health:>3d}  "
                  f"Tier={p.tavern_tier}  Board={len(board)}\n")
        if board:
            out.write(f"       {board_str}\n")
        out.write("\n")

    out.write(f"  Game over after {game.turn} turns.\n")
    out.write(f"{'='*70}\n\n")

    return game


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HSBRSIM — 8-Player Battlegrounds Demo",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--heroes", type=str, nargs=8, default=None)
    parser.add_argument("--max-turns", type=int, default=50)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.quiet:
        hs = args.heroes if args.heroes else _pick_heroes(8, seed=args.seed)
        game = Game.run_game(hs, max_turns=args.max_turns)
        ranked = sorted(game.players, key=lambda p: (-p.health, p.tavern_tier))
        for rank, p in enumerate(ranked, 1):
            idx = game.players.index(p)
            name = p.get_tag(GameTag.NAME, f"P{idx+1}")
            print(f"#{rank} {name}: HP={p.health} Tier={p.tavern_tier}")
        return

    run_demo(hero_ids=args.heroes, seed=args.seed, max_turns=args.max_turns)


if __name__ == "__main__":
    main()
