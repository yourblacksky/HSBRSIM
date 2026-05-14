"""
Demo: Run a complete 8-player Battlegrounds game with ALL heuristic agents.

Every player uses the greedy Q-score heuristic (_auto_player_turn).
Full turn-by-turn log with board states, actions, combat results, and standings.

Usage:
  python -m hsrl.agents.heuristic_demo --seed 42 [--max-turns 15] [--output path/to/file.md]
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, State
from hsrl.core.game import Game


def _format_minion(m) -> str:
    parts = []
    parts.append(f"{m.atk}/{m.health}")
    keywords = []
    if m.taunt:
        keywords.append("Taunt")
    if m.divine_shield:
        keywords.append("DS")
    if m.poisonous:
        keywords.append("Poison")
    if m.venomous:
        keywords.append("Venom")
    if m.reborn:
        keywords.append("Reborn")
    if m.windfury:
        keywords.append("WF")
    if m.cleave:
        keywords.append("Cleave")
    if m.has_tag(GameTag.GOLDEN):
        keywords.append("G")
    if keywords:
        parts.append("[" + ",".join(keywords) + "]")
    return " ".join(parts)


def _format_tavern_item(e) -> str:
    name = e.get_tag(GameTag.NAME) or "?"
    ctype = e.get_tag(GameTag.CARDTYPE, -1)
    tier = e.get_tag(GameTag.TECH_LEVEL, 0)
    cost = e.get_tag(GameTag.COST, 3)
    if ctype == CardType.SPELL:
        return f"{name} (spell) T{tier} ${cost}"
    else:
        golden = " [G]" if e.has_tag(GameTag.GOLDEN) else ""
        return f"{name}{golden} {e.atk}/{e.health} T{tier} ${cost}"


def _hero_name(p):
    return p.data.name if hasattr(p.data, "name") else f"Hero_{p.entity_id}"


def run_heuristic_demo(
    seed: int = 42,
    max_turns: int = 15,
    output_path: str = None,
):
    random.seed(seed)
    np.random.seed(seed)

    # Card module imports (registrations)
    import hsrl.cards.minions.pool as _mp  # noqa
    import hsrl.cards.minions.scripts as _ms  # noqa
    import hsrl.cards.minions.tokens as _mt  # noqa
    import hsrl.cards.heroes.pool as _hp  # noqa
    import hsrl.cards.heroes.scripts as _hs  # noqa
    import hsrl.cards.trinkets.scripts as _ts  # noqa
    import hsrl.cards.rewards.scripts as _rs  # noqa
    import hsrl.cards.anomalies.scripts as _as  # noqa

    hero_ids = [
        cid
        for cid, data in CARDS._cards.items()
        if data.cardtype == CardType.HERO and not cid.startswith("EXAMPLE_")
    ]
    chosen = random.sample(hero_ids, 8)

    game = Game([])
    game.card_db = CARDS
    game.init_pool()
    players = [game.create_player(hid) for hid in chosen]
    game.players = players
    for p in players:
        p.game = game
    game.active_anomaly = True
    game.start_game()

    # Capture output
    lines = []
    def out(s=""):
        lines.append(s)

    # Header
    out("# 8-Player Battlegrounds — All Heuristic Demo")
    out()
    out(f"**Seed**: {seed}  |  **Max Turns**: {max_turns}  |  **Agents**: 8× Greedy Q-Score Heuristic")
    out()
    out("## Players")
    out()
    out("| # | Hero | HP | Armor | Tier |")
    out("|---|---|---|---|---|")
    for i, p in enumerate(players):
        out(f"| {i+1} | {_hero_name(p)} | {p.health} | {p.armor} | {p.tavern_tier} |")
    out()

    out("---")
    out()
    out("## Game Log")
    out()

    eliminated = {}
    turn_count = 0

    while game.state == State.RUNNING and turn_count < max_turns:
        turn_count = game.turn
        out(f"### Turn {turn_count}")
        out()

        # Process each alive player
        alive_players = [p for p in players if p.is_alive]
        for p in alive_players:
            game.active_player = p

            # Snapshot before
            board_before = [_format_minion(m) for m in p.board if not m.dead]
            hp_before = p.health
            armor_before = p.armor
            gold_before = p.gold
            tier_before = p.tavern_tier

            # Format tavern
            tavern_strs = [_format_tavern_item(e) for e in p.tavern]

            out(f"**{_hero_name(p)}**  "
                f"HP={hp_before} Armor={armor_before} Gold={gold_before} Tier={tier_before}")
            out()
            if board_before:
                out(f"  Board: {', '.join(board_before)}")
            else:
                out(f"  Board: (empty)")
            out(f"  Tavern: {' | '.join(tavern_strs)}")
            out()

            # Run the heuristic turn
            game._auto_player_turn(p)
            game.resolve_queue()
            while game._pending_targeted_queue:
                game.auto_resolve_pending_target()

            # Snapshot after
            board_after = [_format_minion(m) for m in p.board if not m.dead]
            hp_after = p.health
            armor_after = p.armor
            gold_after = p.gold
            tier_after = p.tavern_tier

            # Summarize changes
            changes = []
            if gold_after != gold_before:
                changes.append(f"Gold: {gold_before}→{gold_after}")
            if tier_after != tier_before:
                changes.append(f"Tier: {tier_before}→{tier_after}")
            if hp_after != hp_before:
                changes.append(f"HP: {hp_before}→{hp_after}")
            if armor_after != armor_before:
                changes.append(f"Armor: {armor_before}→{armor_after}")

            if board_after != board_before:
                out(f"  → Board after: {', '.join(board_after)}")
            if changes:
                out(f"  → {' | '.join(changes)}")
            out()

        # End recruit phase (combat)
        game.end_recruit_phase()

        out(f"**⚔ Combat Phase**")
        out()

        # Report damage taken
        for p in alive_players:
            if p not in eliminated and not p.is_alive:
                eliminated[p] = turn_count
                out(f"  💀 **{_hero_name(p)} eliminated!** (HP=0, Turn {turn_count})")

        # Show remaining alive
        still_alive = [p for p in players if p.is_alive]
        if len(still_alive) > 1:
            standings = sorted(still_alive, key=lambda p: p.health, reverse=True)
            out(f"  Alive: {len(still_alive)}/8")
            out(f"  HP standings: " + " | ".join(
                f"{_hero_name(p)} (HP={p.health}, Armor={p.armor}, Tier={p.tavern_tier})"
                for p in standings
            ))
        out()

        if len(still_alive) <= 1:
            game.state = State.COMPLETE

    # Final standings
    out("---")
    out()
    out("## Final Standings")
    out()
    out("| # | Hero | HP | Armor | Alive | Eliminated Turn |")
    out("|---|---|---|---|---|")
    rankings = sorted(
        game.players,
        key=lambda p: (
            not p.is_alive,
            -(eliminated.get(p, 999) if not p.is_alive else 0),
            -p.health,
        )
    )
    for i, p in enumerate(rankings):
        elim_turn = eliminated.get(p, "—")
        out(f"| {i+1} | {_hero_name(p)} | {p.health} | {p.armor} | "
            f"{'Yes' if p.is_alive else 'No'} | {elim_turn} |")

    out()
    out("---")
    out()
    out("## Heuristic Strategy")
    out()
    out("The Q-score heuristic evaluates each affordable tavern minion by:")
    out()
    out("1. **Buy & Play**: Score = current_board_score + minion.atk + minion.health + aura_bonus")
    out("2. **Sell & Replace**: If board full, replace weakest minion if net score change > 0")
    out("3. **Upgrade**: If no beneficial buy is available and gold ≥ upgrade_cost, upgrade tavern tier")
    out("4. **Refresh**: If no other action is possible, refresh the tavern for 1 gold")
    out()
    out("This is a greedy one-step heuristic — no lookahead, no opponent modeling, no combat simulation.")
    out(f"Average rank in self-play: ~4.5 (random among identical strategies)")

    result = "\n".join(lines)
    if output_path:
        Path(output_path).write_text(result)
        print(f"Written to {output_path}")
    else:
        print(result)


def main():
    parser = argparse.ArgumentParser(description="All-heuristic Battlegrounds demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--output", type=str, default=None,
                        help="Output markdown file (default: print to stdout)")
    args = parser.parse_args()

    run_heuristic_demo(
        seed=args.seed,
        max_turns=args.max_turns,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
