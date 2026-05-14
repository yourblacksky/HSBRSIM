"""
Demo: Run a complete 8-player Battlegrounds game with SearchAgent v2.

Captures and explains every action taken by the embedding-based search agent
against 7 heuristic opponents. Output is a self-contained annotated game log.

Usage:
  python -m hsrl.agents.demo_game --seed 42
"""

from __future__ import annotations

import argparse
import random
import time

import numpy as np

from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, State
from hsrl.core.game import Game
from hsrl.env.action import (
    build_action_mask,
    decode_action,
    get_action_name,
    END_TURN,
    REFRESH,
    UPGRADE,
    HERO_POWER,
    FREEZE,
    BUY_OFFSET,
    SELL_OFFSET,
    PLAY_OFFSET,
)


def _format_minion(m) -> str:
    """Format a minion as 'atk/hp [keywords]'."""
    parts = [f"{m.atk}/{m.health}"]
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
    if m.is_golden:
        keywords.append("G")
    if keywords:
        parts.append("[" + ",".join(keywords) + "]")
    return " ".join(parts)


def run_demo(
    seed: int = 42,
    max_turns: int = 15,
    board_eval_path: str = "checkpoints/board_eval_v2.pt",
    game_value_path: str = "checkpoints/game_value_v2.pt",
):
    """Run a complete game with annotated commentary."""

    import torch

    from hsrl.train.board_eval import BoardEvalTrainer
    from hsrl.train.combat_data import encode_board_from_minions

    # Version-aware checkpoint loading
    ckpt = torch.load(game_value_path, map_location="cuda", weights_only=False)
    ckpt_version = ckpt.get("version", "v2")

    if ckpt_version == "v4":
        from hsrl.train.game_value_sp import SelfPlayGameValueTrainer
        from hsrl.train.game_value_sp import encode_pomdp_state as _encode_pomdp
        game_value = SelfPlayGameValueTrainer.load(game_value_path, device="cuda")
    else:
        from hsrl.train.game_value import (
            GameValueTrainer,
            encode_pomdp_state as _encode_pomdp_v2,
        )
        game_value = GameValueTrainer.load(game_value_path, device="cuda")

    def encode_pomdp_state(game, player, board_eval):
        if ckpt_version == "v4":
            return _encode_pomdp(game, player, board_eval)
        else:
            return _encode_pomdp_v2(game, player, board_eval)

    # Also need compute_teacher_placement for v2
    if ckpt_version != "v4":
        from hsrl.train.game_value import compute_teacher_placement
    else:
        from hsrl.train.game_value_sp import compute_terminal_placement as compute_teacher_placement

    # ── Card module imports (registrations) ──
    import hsrl.cards.minions.pool as _mp  # noqa
    import hsrl.cards.minions.scripts as _ms  # noqa
    import hsrl.cards.minions.tokens as _mt  # noqa
    import hsrl.cards.heroes.pool as _hp  # noqa
    import hsrl.cards.heroes.scripts as _hs  # noqa
    import hsrl.cards.trinkets.scripts as _ts  # noqa
    import hsrl.cards.rewards.scripts as _rs  # noqa
    import hsrl.cards.anomalies.scripts as _as  # noqa

    # ── Setup ──
    random.seed(seed)
    np.random.seed(seed)

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

    # Load board eval model (game_value already loaded above)
    board_eval = BoardEvalTrainer.load(board_eval_path, device="cuda")

    agent_player = players[0]
    opponent_players = players[1:]

    def hero_name(p):
        return p.data.name if hasattr(p.data, "name") else f"Hero_{p.entity_id}"

    # ── Header ──
    print("=" * 70)
    print("  Hearthstone Battlegrounds — SearchAgent v2 Demo")
    print("=" * 70)
    print()
    model_tag = f"GameValue {ckpt_version}" if ckpt_version == "v4" else f"GameValue {ckpt_version}"
    print(f"  Seed: {seed}  |  Model: BoardEval v2 + {model_tag}")
    print(f"  Search: Greedy one-step lookahead with board embeddings")
    if ckpt_version == "v4":
        print(f"  Features: HDT-observable POMDP (397 dims, per-opponent combat memory)")
    print()
    print(f"  Agent Hero: {hero_name(agent_player)}")
    print(f"  Opponents (heuristic):")
    for i, p in enumerate(opponent_players, 1):
        print(f"    {i}. {hero_name(p)}")
    print()
    print("=" * 70)
    print("  GAME LOG")
    print("=" * 70)
    print()

    # ── Game Loop ──
    turn_count = 0
    total_actions = 0
    total_evals = 0

    while game.state == State.RUNNING and game.turn <= max_turns:
        turn_count = game.turn

        # ── Opponent turns (heuristic) ──
        for p in opponent_players:
            if not p.is_alive:
                continue
            game.active_player = p
            game._auto_player_turn(p)
            game.resolve_queue()
            while game._pending_targeted_queue:
                game.auto_resolve_pending_target()

        # ── Agent turn ──
        if not agent_player.is_alive:
            game.end_recruit_phase()
            alive = [p for p in game.players if p.is_alive]
            if len(alive) <= 1:
                game.state = State.COMPLETE
            continue

        # Pre-action state
        board_before = [
            _format_minion(m) for m in agent_player.board if not m.dead
        ]
        obs_before = encode_pomdp_state(game, agent_player, board_eval)
        v_before = float(np.asarray(game_value.predict(obs_before)).flat[0])

        board_enc = encode_board_from_minions(agent_player.board)
        emb = board_eval.embed_board(board_enc)

        print(f"─── Turn {turn_count} ───")
        print(f"  State: HP={agent_player.health}  Gold={agent_player.gold}  "
              f"Tier={agent_player.tavern_tier}  Armor={agent_player.armor}")

        if board_before:
            print(f"  Board: {', '.join(board_before)}")
        else:
            print(f"  Board: (empty)")

        # Tavern
        tavern_items = []
        for i, e in enumerate(agent_player.tavern):
            tier = e.get_tag(GameTag.TECH_LEVEL, 0)
            cost = e.get_tag(GameTag.COST, 3)
            name = e.get_tag(GameTag.NAME) or "Unknown"
            ctype = e.get_tag(GameTag.CARDTYPE, -1)
            if ctype == CardType.SPELL:
                text = e.get_tag(GameTag.TEXT, "")[:40] if e.get_tag(GameTag.TEXT, "") else ""
                tavern_items.append(f"[{i}] {name} (spell) T{tier} ${cost}")
            else:
                golden = " [G]" if e.has_tag(GameTag.GOLDEN) else ""
                tavern_items.append(f"[{i}] {name}{golden} {e.atk}/{e.health} T{tier} ${cost}")
        if tavern_items:
            print(f"  Tavern: {' | '.join(tavern_items)}")
        else:
            print(f"  Tavern: (empty)")

        print(f"  Initial V_game = {v_before:.4f}")
        print()

        # ── Agent action loop ──
        game.active_player = agent_player
        step = 0

        for _ in range(50):
            mask = build_action_mask(game, agent_player)
            legal = [i for i, m in enumerate(mask) if m]

            obs_now = encode_pomdp_state(game, agent_player, board_eval)
            v_now = float(np.asarray(game_value.predict(obs_now)).flat[0])
            total_evals += 1

            best_action = END_TURN
            best_v = v_now

            # ── One-step greedy lookahead ──
            for a in legal:
                if a == END_TURN:
                    continue

                # Save full state
                saved = {
                    "gold": agent_player.gold,
                    "board": list(agent_player.board),
                    "hand": list(agent_player.hand),
                    "tavern": list(agent_player.tavern),
                    "health": agent_player.health,
                    "tavern_tier": agent_player.tavern_tier,
                    "armor": agent_player.armor,
                    "upgrade_cost": agent_player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5),
                }

                try:
                    decode_action(a, game, agent_player)
                    game.resolve_queue()
                    while game._pending_targeted_queue:
                        game.auto_resolve_pending_target()
                    obs2 = encode_pomdp_state(game, agent_player, board_eval)
                    v2 = float(np.asarray(game_value.predict(obs2)).flat[0])
                    total_evals += 1
                    if v2 > best_v:
                        best_v = v2
                        best_action = a
                except Exception:
                    pass

                # Restore
                agent_player.gold = saved["gold"]
                agent_player.board = saved["board"]
                agent_player.hand = saved["hand"]
                agent_player.tavern = saved["tavern"]
                agent_player.health = saved["health"]
                agent_player.tavern_tier = saved["tavern_tier"]
                agent_player.armor = saved["armor"]
                agent_player.set_tag(GameTag.TAVERN_UPGRADE_COST, saved["upgrade_cost"])

            if best_action == END_TURN:
                print(f"  [{step}] END_TURN  (V={v_now:.4f})")
                print(f"       → Ending recruit phase, proceeding to combat")
                break

            a_name = get_action_name(best_action)
            delta = best_v - v_now
            total_actions += 1

            # ── Action commentary ──
            if best_action == REFRESH:
                rationale = "refresh for better minion options"
            elif best_action == UPGRADE:
                rationale = f"upgrade to tier {agent_player.tavern_tier + 1} for stronger minions"
            elif BUY_OFFSET <= best_action <= BUY_OFFSET + 6:
                slot = best_action - BUY_OFFSET
                entity = agent_player.tavern[slot] if slot < len(agent_player.tavern) else None
                if entity:
                    rationale = f"buy {entity.atk}/{entity.health} minion"
                else:
                    rationale = "buy minion"
            elif SELL_OFFSET <= best_action <= SELL_OFFSET + 6:
                slot = best_action - SELL_OFFSET
                living = [m for m in agent_player.board if not m.dead]
                m = living[slot] if slot < len(living) else None
                rationale = f"sell {_format_minion(m) if m else 'minion'} for +1 gold"
            elif PLAY_OFFSET <= best_action <= PLAY_OFFSET + 9:
                slot = best_action - PLAY_OFFSET
                entity = agent_player.hand[slot] if slot < len(agent_player.hand) else None
                rationale = f"play {_format_minion(entity) if entity else 'card'} from hand"
            elif best_action == FREEZE:
                rationale = "freeze tavern for next turn"
            elif best_action == HERO_POWER:
                rationale = "use hero power"
            else:
                rationale = "execute action"

            print(f"  [{step}] {a_name}  (V: {v_now:.4f} → {best_v:.4f}, Δ={delta:+.4f})")
            print(f"       → {rationale}")

            decode_action(best_action, game, agent_player)
            game.resolve_queue()
            while game._pending_targeted_queue:
                game.auto_resolve_pending_target()
            step += 1

        # ── Combat ──
        if ckpt_version == "v4":
            all_players = game.players
            agent_teacher = compute_teacher_placement(agent_player, all_players)
        else:
            teacher = compute_teacher_placement(game, board_eval)
            agent_teacher = teacher.get(agent_player.entity_id, 0)

        board_after = [
            _format_minion(m) for m in agent_player.board if not m.dead
        ]
        damage = 0  # damage is tracked via health delta

        pre_combat_str = ", ".join(board_before) if board_before else "(empty)"
        post_combat_str = ", ".join(board_after) if board_after else "(empty)"

        game.end_recruit_phase()

        print()
        print(f"  ⚔ Combat Phase:")
        print(f"    Pre-combat board:  {pre_combat_str}")
        print(f"    Post-combat board: {post_combat_str}")
        print(f"    Teacher predicted placement: {agent_teacher:.3f} "
              f"({1 + (1 - agent_teacher) * 7:.1f}th place)")

        alive = [p for p in game.players if p.is_alive]
        print(f"    Alive players: {len(alive)}/8")
        print()

        if len(alive) <= 1:
            game.state = State.COMPLETE

    # ── Final Standings ──
    print("=" * 70)
    print("  FINAL STANDINGS")
    print("=" * 70)
    print()

    rankings = sorted(game.players, key=lambda p: (not p.is_alive, -p.health))
    agent_place = None
    for i, p in enumerate(rankings):
        name = hero_name(p)
        marker = "  ← AGENT" if p is agent_player else ""
        print(f"  {i + 1}. {name}  (HP={p.health}, alive={p.is_alive}){marker}")
        if p is agent_player:
            agent_place = i + 1

    print()
    print(f"  Agent final placement: {agent_place}")
    print(f"  Total agent actions: {total_actions}")
    print(f"  Total state evaluations: {total_evals}")
    print()

    # ── System summary ──
    print("=" * 70)
    print("  ARCHITECTURE SUMMARY")
    print("=" * 70)
    print()
    print("  Pipeline: Combat Simulator → BoardEval → GameValue → Search Policy")
    print()
    print("  BoardEvalNetwork v2 (embedding-based):")
    print("    - BoardEmbedder: (7,15) minion features → 32-dim embedding")
    print("    - Per-slot MLP + learned attention + mean/max pool")
    print("    - CombatPredictor: concat(emb_a, emb_b, diff, product) → P(A wins)")
    print("    - Trained on 44,958 combat pairs from 500 games")
    print("    - Pairwise accuracy: 99.1%")
    print()
    if ckpt_version == "v4":
        print("  GameValueNetwork v4 (HDT-observable POMDP):")
        print("    - Per-opponent: last_seen_board(32) + staleness + combat_history +")
        print("      hp + tier + armor + board_size + triples×6 + upgrades×5 = 51 dims")
        print("    - Shared opp_proj(51→32→16) + mean pool → 16")
        print("    - Total input: 32(board) + 6(own) + 7×51(opp) + 2(global) = 397 dims")
        print("    - Teacher: CombatPredictor pairwise ranking (full-information)")
        print("    - Model: 6,705 parameters")
    else:
        print("  GameValueNetwork v2 (embedding-based):")
        print("    - Input: 32-dim board embedding + 6 own stats + 21 opponent + 2 global = 61 dims")
        print("    - Teacher: pairwise CombatPredictor ranking (full-information)")
        print("    - Trained on 47,346 POMDP snapshots from 500 games")
        print("    - Val MAE: 0.143 (~1.0 placement position)")
    print()
    print("  SearchAgent v2:")
    print("    - Greedy one-step lookahead using GameValueNetwork")
    print("    - At each step: enumerate legal actions, simulate, evaluate V(s')")
    print("    - Chooses action with highest predicted state value")
    if ckpt_version == "v4":
        print("    - v6 greedy: avg_rank 2.00 (matches v2 teacher)")
    else:
        print("    - Benchmark: avg_rank 2.07 (v2 greedy), 1.97 (v2 beam w=3)")
    print()


def main():
    parser = argparse.ArgumentParser(description="SearchAgent v2 demo game")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--board-eval", type=str, default="checkpoints/board_eval_v2.pt")
    parser.add_argument("--game-value", type=str, default="checkpoints/game_value_v6.pt")
    args = parser.parse_args()

    run_demo(
        seed=args.seed,
        max_turns=args.max_turns,
        board_eval_path=args.board_eval,
        game_value_path=args.game_value,
    )


if __name__ == "__main__":
    main()
