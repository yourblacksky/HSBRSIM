"""
Demo: Run a single game with 1 SearchAgent vs 7 heuristic opponents.
Detailed turn-by-turn log for auditing agent behavior.

Usage:
  python -m hsrl.agents.agent_vs_heuristic_demo --seed 42 [--output path/to/file.md]
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, State
from hsrl.core.game import Game
from hsrl.env.action import END_TURN, decode_action, get_action_name


def _format_minion(m) -> str:
    parts = []
    parts.append(f"{m.atk}/{m.health}")
    keywords = []
    if m.taunt: keywords.append("Taunt")
    if m.divine_shield: keywords.append("DS")
    if m.poisonous: keywords.append("Poison")
    if m.venomous: keywords.append("Venom")
    if m.reborn: keywords.append("Reborn")
    if m.windfury: keywords.append("WF")
    if m.cleave: keywords.append("Cleave")
    if m.is_golden: keywords.append("G")
    if keywords: parts.append("[" + ",".join(keywords) + "]")
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


def run_agent_vs_heuristic_demo(
    seed: int = 42,
    max_turns: int = 15,
    output_path: str = None,
    game_value_path: str = "checkpoints/game_value_v3_clean.pt",
    board_eval_path: str = "checkpoints/board_eval_v3_clean.pt",
    beam_width: int = 0,
    beam_depth: int = 3,
):
    random.seed(seed)
    np.random.seed(seed)

    import hsrl.cards.minions.pool as _mp  # noqa
    import hsrl.cards.minions.scripts as _ms  # noqa
    import hsrl.cards.minions.tokens as _mt  # noqa
    import hsrl.cards.heroes.pool as _hp  # noqa
    import hsrl.cards.heroes.scripts as _hs  # noqa
    import hsrl.cards.trinkets.scripts as _ts  # noqa
    import hsrl.cards.rewards.scripts as _rs  # noqa
    import hsrl.cards.anomalies.scripts as _as  # noqa

    from hsrl.agents.search_agent import SearchAgent

    hero_ids = [
        cid for cid, data in CARDS._cards.items()
        if data.cardtype == CardType.HERO and not cid.startswith("EXAMPLE_")
    ]
    chosen = random.sample(hero_ids, 8)

    game = Game([], seed=seed)
    game.card_db = CARDS
    game.init_pool()
    players = [game.create_player(hid) for hid in chosen]
    game.players = players
    for p in players:
        p.game = game
    game.active_anomaly = True
    game.start_game()

    # Player 0 is the RL agent, players 1-7 are heuristic
    agent_player = players[0]
    opponent_players = players[1:]

    agent = SearchAgent(
        game_value_path=game_value_path,
        board_eval_path=board_eval_path,
        beam_width=beam_width,
        beam_depth=beam_depth,
        seed=seed,
    )

    lines = []
    def out(s=""):
        lines.append(s)

    out("# 1 SearchAgent vs 7 Heuristic — Detailed Audit")
    out()
    out(f"**Seed**: {seed}  |  **Max Turns**: {max_turns}")
    out(f"**Agent**: {_hero_name(agent_player)} (SearchAgent greedy)")
    out(f"**Opponents**: 7× Greedy Q-Score Heuristic")
    out()
    out("| # | Role | Hero | HP | Armor | Tier |")
    out("|---|---|---|---|---|---|")
    for i, p in enumerate(players):
        role = "**RL Agent**" if p is agent_player else f"Heuristic #{i}"
        out(f"| {i+1} | {role} | {_hero_name(p)} | {p.health} | {p.armor} | {p.tavern_tier} |")
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

        # ── Process all players in order ──
        # Heuristic opponents first, then RL agent
        for p in players:
            if not p.is_alive:
                continue
            game.active_player = p
            is_agent = (p is agent_player)

            # Snapshot before
            board_before = [_format_minion(m) for m in p.board if not m.dead]
            hp_before = p.health
            armor_before = p.armor
            gold_before = p.gold
            tier_before = p.tavern_tier
            hand_before = len(p.hand)
            trinkets_before = len(p.trinkets)
            board_count_before = len([m for m in p.board if not m.dead])

            # Format tavern
            tavern_strs = [_format_tavern_item(e) for e in p.tavern]

            label = "RL AGENT" if is_agent else "Heuristic"
            out(f"**{_hero_name(p)}** [{label}]  "
                f"HP={hp_before} Armor={armor_before} Gold={gold_before} Tier={tier_before}")
            out()
            if board_before:
                out(f"  Board ({board_count_before}/7): {', '.join(board_before)}")
            else:
                out(f"  Board: (empty)")
            out(f"  Tavern ({len(p.tavern)} items): {' | '.join(tavern_strs) if tavern_strs else '(empty)'}")
            out(f"  Hand: {len(p.hand)} cards")
            out()

            actions_taken = []

            if is_agent:
                # ── RL Agent turn (act() handles trinkets/choices internally) ──
                for _ in range(50):
                    action = agent.act(game, p)
                    if action == END_TURN:
                        break
                    gold_before_a = p.gold
                    board_before_a = len([m for m in p.board if not m.dead])
                    actions_taken.append(get_action_name(action))
                    decode_action(action, game, p)
                    game.resolve_queue()
                    while game._pending_targeted_queue:
                        game.auto_resolve_pending_target()
                    # Stuck detection
                    gold_after_a = p.gold
                    board_after_a = len([m for m in p.board if not m.dead])
                    if gold_before_a == gold_after_a and board_before_a == board_after_a:
                        break
            else:
                # ── Heuristic turn ──
                game._auto_player_turn(p)
                game.resolve_queue()
                while game._pending_targeted_queue:
                    game.auto_resolve_pending_target()
                actions_taken.append("(auto)")

            # Snapshot after
            board_after = [_format_minion(m) for m in p.board if not m.dead]
            hp_after = p.health
            armor_after = p.armor
            gold_after = p.gold
            tier_after = p.tavern_tier
            board_count_after = len([m for m in p.board if not m.dead])

            changes = []
            if tier_after != tier_before:
                changes.append(f"Tier {tier_before}→{tier_after}")
            if gold_after != gold_before:
                changes.append(f"Gold {gold_before}→{gold_after}")
            if hp_after != hp_before:
                changes.append(f"HP {hp_before}→{hp_after}")
            if armor_after != armor_before:
                changes.append(f"Armor {armor_before}→{armor_after}")
            if len(p.trinkets) > trinkets_before:
                t_name = p.trinkets[-1].get_tag(GameTag.NAME) or "?"
                changes.append(f"Trinket: {t_name}")
            if len(p.hand) != hand_before:
                changes.append(f"Hand {hand_before}→{len(p.hand)}")

            if board_after != board_before:
                out(f"  → Board ({board_count_after}/7): {', '.join(board_after)}")
            if changes:
                out(f"  → {' | '.join(changes)}")
            out(f"  → Actions: {', '.join(str(a) for a in actions_taken)}")
            out()

        # ── Combat phase ──
        game.end_recruit_phase()

        out(f"**Combat Phase**")
        out()

        combat_events = game._combat_event_log
        for evt in combat_events:
            if evt['event'] == 'combat_start':
                p1_label = "AGENT" if evt['p1'] == _hero_name(agent_player) else "heur"
                p2_label = "AGENT" if evt['p2'] == _hero_name(agent_player) else "heur"
                out(f"  [{p1_label}] {evt['p1']} vs [{p2_label}] {evt['p2']} (first: {evt['first_attacker']})")
                out(f"     {evt['p1']}: [{', '.join(evt['p1_board'])}]")
                out(f"     {evt['p2']}: [{', '.join(evt['p2_board'])}]")
            elif evt['event'] == 'attack':
                atk = f"{evt['attacker']} {evt['atk_before']}→{evt['atk_after']}"
                if evt['atk_dead']: atk += " DEAD"
                df = f"{evt['defender']} {evt['def_before']}→{evt['def_after']}"
                if evt['def_dead']: df += " DEAD"
                out(f"     {atk}  |  {df}")
            elif evt['event'] == 'combat_end':
                winner_label = "AGENT" if evt['winner'] == _hero_name(agent_player) else (
                    "draw" if evt['winner'] == "draw" else "heur")
                out(f"     Result: {evt['survivors_p1']} vs {evt['survivors_p2']} — {winner_label}")
        game._combat_event_log.clear()
        out()

        # Report damage
        for p in list(players):
            if p not in eliminated and not p.is_alive:
                eliminated[p] = turn_count
                role = "AGENT" if p is agent_player else "Heuristic"
                out(f"  **{_hero_name(p)} [{role}] eliminated!** (Turn {turn_count})")

        still_alive = [p for p in players if p.is_alive]
        if len(still_alive) > 1:
            standings = sorted(still_alive, key=lambda p: p.health, reverse=True)
            out(f"  Alive: {len(still_alive)}/8")
            out(f"  HP: " + " | ".join(
                f"{_hero_name(p)} (HP={p.health}, Tier={p.tavern_tier})"
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
    out("| # | Hero | Role | HP | Tier | Eliminated |")
    out("|---|---|---|---|---|---|")
    rankings = sorted(
        game.players,
        key=lambda p: (not p.is_alive,
                       -(eliminated.get(p, 999) if not p.is_alive else 0),
                       -p.health,)
    )
    for i, p in enumerate(rankings):
        role = "AGENT" if p is agent_player else "Heuristic"
        elim_turn = eliminated.get(p, "—")
        out(f"| {i+1} | {_hero_name(p)} | {role} | {p.health} | {p.tavern_tier} | {elim_turn} |")

    result = "\n".join(lines)
    if output_path:
        Path(output_path).write_text(result)
        print(f"Written to {output_path}")
    else:
        print(result)


def main():
    parser = argparse.ArgumentParser(description="1 Agent vs 7 Heuristic audit demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--game-value", type=str, default="checkpoints/game_value_v3_clean.pt")
    parser.add_argument("--board-eval", type=str, default="checkpoints/board_eval_v3_clean.pt")
    parser.add_argument("--beam-width", type=int, default=0)
    parser.add_argument("--beam-depth", type=int, default=3)
    args = parser.parse_args()

    run_agent_vs_heuristic_demo(
        seed=args.seed,
        max_turns=args.max_turns,
        output_path=args.output,
        game_value_path=args.game_value,
        board_eval_path=args.board_eval,
        beam_width=args.beam_width,
        beam_depth=args.beam_depth,
    )


if __name__ == "__main__":
    main()
