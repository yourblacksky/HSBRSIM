"""
Search Agent — greedy or beam-search lookahead using GameValueNetwork.

Phase 3 of the search+value architecture. Replaces the BC policy network
with explicit forward simulation + value evaluation for each legal action.

Natural language:
  At each step in the recruit phase, enumerate all legal actions, simulate
  each one forward, encode the resulting POMDP state, and evaluate it with
  the GameValueNetwork. With beam search, explores multi-step sequences
  (e.g. refresh→buy, sell→buy→play) to escape the one-step greedy ceiling.

Formal spec:
  Greedy (beam_width=0):
    For each legal action a:
      s' = simulate(s, a)           # simplified forward model
      v = V_game(encode_pomdp(s'))  # GameValueNetwork evaluation
    Choose a* = argmax v

  Beam search (beam_width=W, max_depth=D):
    beam = [(s, [], V_game(s))]     # (state, action_seq, value)
    For depth in 1..D:
      For each state in beam:
        For each legal action a:
          s' = simulate(s, a)
          beam' += (s', seq+[a], V_game(s'))
      beam = top-W beam' by value
    Return first action of best sequence, or END_TURN if none improve V_game.

Architecture:
  Combat Simulator → BoardEvalNetwork → GameValueNetwork → Search Policy
     (Phase 1)           (Phase 1)          (Phase 2)         (Phase 3)

Test:
  python -m hsrl.agents.search_agent --benchmark --games 30 --beam-width 3 --beam-depth 3 \\
      --game-value checkpoints/game_value_v2.pt --board-eval checkpoints/board_eval_v2.pt
"""

from __future__ import annotations

import copy
import random
import time
from typing import Optional

import numpy as np

from hsrl.core.enums import CardType, GameTag
from hsrl.env.action import (
    BUY_OFFSET,
    END_TURN,
    FREEZE,
    HERO_POWER,
    NUM_ACTIONS,
    PLAY_OFFSET,
    REFRESH,
    SELL_OFFSET,
    UPGRADE,
    build_action_mask,
    get_action_name,
)

# ── State save/restore (same pattern as nn_mcts_agent) ──────────────────────

_SAVE_TAGS = [
    GameTag.HERO_POWER_USED,
    GameTag.HERO_POWER_EXTRA_USES,
    GameTag.FREE_REFRESH_REMAINING,
    GameTag.FROZEN,
    GameTag.TAVERN_UPGRADE_COST,
]


def _save_player(player):
    return {
        "gold": player.gold,
        "board": list(player.board),
        "hand": list(player.hand),
        "tavern": list(player.tavern),
        "tags": {tag: player.get_tag(tag, 0) for tag in _SAVE_TAGS},
        "health": player.health,
        "tavern_tier": player.tavern_tier,
        "armor": player.armor,
    }


def _restore_player(player, saved):
    player.gold = saved["gold"]
    player.board = list(saved["board"])
    player.hand = list(saved["hand"])
    player.tavern = list(saved["tavern"])
    player.health = saved["health"]
    player.tavern_tier = saved["tavern_tier"]
    player.armor = saved["armor"]
    for tag, val in saved["tags"].items():
        player.set_tag(tag, val)


# ── Simplified action simulation (greedy mode) ──────────────────────────────

def _simulate_action(player, action: int) -> bool:
    """Apply a single action via direct state manipulation (no engine events).

    Used for fast forward simulation in the one-step lookahead search.
    Returns True if the action was applied successfully.
    """
    if BUY_OFFSET <= action <= BUY_OFFSET + 6:
        slot = action - BUY_OFFSET
        if slot >= len(player.tavern):
            return False
        entity = player.tavern.pop(slot)
        cost = entity.get_tag(GameTag.COST, 3)
        if player.gold < cost:
            player.tavern.insert(slot, entity)
            return False
        player.gold -= cost
        player.hand.append(entity)
        return True

    if SELL_OFFSET <= action <= SELL_OFFSET + 6:
        slot = action - SELL_OFFSET
        living = [m for m in player.board if not m.dead]
        if slot >= len(living):
            return False
        entity = living[slot]
        if entity in player.board:
            player.board.remove(entity)
        player.gold += 1
        return True

    if PLAY_OFFSET <= action <= PLAY_OFFSET + 9:
        slot = action - PLAY_OFFSET
        if slot >= len(player.hand):
            return False
        board_living = player.get_board_minions()
        if len(board_living) >= 7:
            return False
        entity = player.hand.pop(slot)
        ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
        if ct != CardType.MINION:
            player.hand.insert(slot, entity)
            return False
        player.board.append(entity)
        return True

    if action == REFRESH:
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        if player.gold < 1 and free <= 0:
            return False
        if free > 0:
            player.set_tag(GameTag.FREE_REFRESH_REMAINING, free - 1)
        else:
            player.gold -= 1
        return True

    if action == UPGRADE:
        _BASE_COST = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10}
        cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
        if player.gold < cost or player.tavern_tier >= 7:
            return False
        player.gold -= cost
        player.tavern_tier += 1
        next_base = _BASE_COST.get(player.tavern_tier + 1, 10)
        player.set_tag(GameTag.TAVERN_UPGRADE_COST, next_base)
        return True

    if action == FREEZE:
        return True

    if action == HERO_POWER:
        hp_cost = player.hero_power_cost
        if player.gold < hp_cost:
            return False
        player.gold -= hp_cost
        player.set_tag(GameTag.HERO_POWER_USED, True)
        return True

    if action == END_TURN:
        return True

    return False


# ── Plausible tavern generation (for beam search REFRESH) ───────────────────

_TIER_STATS = {
    1: (2, 3), 2: (3, 4), 3: (4, 5),
    4: (5, 6), 5: (6, 7), 6: (7, 8),
}


def _populate_tavern(player, rng: random.Random):
    """Generate plausible minions in the tavern based on player tier.

    Used in beam search to enable evaluation of REFRESH→BUY sequences.
    Minion stats are randomized around tier-appropriate baselines.
    """
    from hsrl.core.entity import BaseEntity, CardData

    player.tavern.clear()
    tier = player.tavern_tier
    base_atk, base_hp = _TIER_STATS.get(tier, (4, 4))
    variance = tier

    num_slots = min(7, 3 + tier)
    for i in range(num_slots):
        atk = max(1, base_atk + rng.randint(-variance, variance))
        hp = max(1, base_hp + rng.randint(-variance, variance))
        cost = min(3 + tier // 2, 6)
        data = CardData(
            id=f"_beam_t{tier}_{i}",
            name=f"BeamTier{tier}",
            text="",
            tags={
                GameTag.BASE_ATK: atk,
                GameTag.BASE_HEALTH: hp,
                GameTag.COST: cost,
                GameTag.TECH_LEVEL: tier,
                GameTag.RACE: 0,
                GameTag.CARDTYPE: CardType.MINION,
                GameTag.ATK: atk,
                GameTag.HEALTH: hp,
            },
        )
        entity = BaseEntity(data, game=None)
        player.tavern.append(entity)


# ── Beam-search action simulation (smarter: auto-play, replace, tavern) ─────

def _simulate_for_beam(player, action: int, rng: random.Random) -> bool:
    """Apply action with full simulation for beam search.

    Key differences from _simulate_action:
    - BUY: auto-plays minion to board (or replaces worst if full)
    - REFRESH: populates tavern with plausible minions
    - SELL/PLAY/UPGRADE/FREEZE: same as _simulate_action
    """
    # ── BUY with auto-play / auto-replace ──
    if BUY_OFFSET <= action <= BUY_OFFSET + 6:
        slot = action - BUY_OFFSET
        if slot >= len(player.tavern):
            return False
        entity = player.tavern[slot]
        ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
        cost = entity.get_tag(GameTag.COST, 3)
        if player.gold < cost:
            return False
        if ct not in (CardType.MINION, CardType.SPELL):
            return False

        # Spell: just spend gold
        if ct == CardType.SPELL:
            player.gold -= cost
            player.tavern.pop(slot)
            return True

        # Minion: buy + auto-play to board
        board_living = player.get_board_minions()
        if len(board_living) < 7:
            # Board has space — simple buy + play
            player.gold -= cost
            player.tavern.pop(slot)
            player.board.append(entity)
            return True
        else:
            # Board full — replace the weakest minion
            # Find minion with lowest (atk + health) as proxy for weakest
            weakest_idx = min(
                range(len(board_living)),
                key=lambda i: board_living[i].atk + board_living[i].health,
            )
            old = board_living[weakest_idx]
            if old in player.board:
                player.board.remove(old)
            player.gold += 1  # sell refund
            player.gold -= cost
            player.tavern.pop(slot)
            player.board.append(entity)
            return True

    # ── SELL ──
    if SELL_OFFSET <= action <= SELL_OFFSET + 6:
        slot = action - SELL_OFFSET
        living = [m for m in player.board if not m.dead]
        if slot >= len(living):
            return False
        entity = living[slot]
        if entity in player.board:
            player.board.remove(entity)
        player.gold += 1
        return True

    # ── PLAY from hand ──
    if PLAY_OFFSET <= action <= PLAY_OFFSET + 9:
        slot = action - PLAY_OFFSET
        if slot >= len(player.hand):
            return False
        board_living = player.get_board_minions()
        if len(board_living) >= 7:
            return False
        entity = player.hand.pop(slot)
        ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
        if ct != CardType.MINION:
            player.hand.insert(slot, entity)
            return False
        player.board.append(entity)
        return True

    # ── REFRESH with plausible tavern ──
    if action == REFRESH:
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        if player.gold < 1 and free <= 0:
            return False
        if free > 0:
            player.set_tag(GameTag.FREE_REFRESH_REMAINING, free - 1)
        else:
            player.gold -= 1
        _populate_tavern(player, rng)
        return True

    # ── UPGRADE ──
    if action == UPGRADE:
        _BASE_COST = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10}
        cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
        if player.gold < cost or player.tavern_tier >= 7:
            return False
        player.gold -= cost
        player.tavern_tier += 1
        next_base = _BASE_COST.get(player.tavern_tier + 1, 10)
        player.set_tag(GameTag.TAVERN_UPGRADE_COST, next_base)
        return True

    # ── FREEZE (no-op for evaluation) ──
    if action == FREEZE:
        return True

    # ── HERO_POWER (excluded from search) ──
    if action == HERO_POWER:
        return False

    # ── END_TURN (handled separately) ──
    if action == END_TURN:
        return True

    return False


# ── Search Agent ────────────────────────────────────────────────────────────


class SearchAgent:
    """Lookahead agent using GameValueNetwork for state evaluation.

    Supports two modes:
    - Greedy (beam_width=0): one-step lookahead, fast, avg_rank ~2.10
    - Beam search (beam_width>0): multi-step lookahead, handles sequences
      like refresh→buy and sell→buy→play.

    Parameters
    ----------
    game_value_path : str
        Path to GameValueNetwork checkpoint.
    board_eval_path : str
        Path to BoardEvalNetwork checkpoint.
    beam_width : int
        Beam width for search (0 = greedy one-step).
    beam_depth : int
        Max lookahead depth for beam search.
    device : str
        "auto", "cuda", or "cpu".
    seed : int, optional
    """

    def __init__(
        self,
        game_value_path: str = "checkpoints/game_value_v2.pt",
        board_eval_path: str = "checkpoints/board_eval_v2.pt",
        beam_width: int = 0,
        beam_depth: int = 3,
        device: str = "auto",
        seed: int = None,
    ):
        if device == "auto":
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self.rng = random.Random(seed)
        self.beam_width = beam_width
        self.beam_depth = beam_depth

        # Load models — detect checkpoint version
        import torch
        ckpt = torch.load(game_value_path, map_location=device, weights_only=False)
        ckpt_version = ckpt.get("version", "v2")

        from hsrl.train.board_eval import BoardEvalTrainer

        if ckpt_version == "v4":
            from hsrl.train.game_value_sp import SelfPlayGameValueTrainer
            from hsrl.train.game_value_sp import encode_pomdp_state as _encode_pomdp
            self.game_value = SelfPlayGameValueTrainer.load(game_value_path, device=device)
        else:
            from hsrl.train.game_value import GameValueTrainer
            from hsrl.train.game_value import encode_pomdp_state as _encode_pomdp
            self.game_value = GameValueTrainer.load(game_value_path, device=device)

        self.board_eval = BoardEvalTrainer.load(board_eval_path, device=device)
        self._encode_pomdp = _encode_pomdp

        # v2 uses board embeddings — no scalar normalization needed

        # Stats
        self._eval_count = 0
        self._step_count = 0

    # ── Public API ───────────────────────────────────────────────────────

    def act(self, game, player) -> int:
        """Choose the best action via lookahead search."""
        self._step_count += 1

        mask = build_action_mask(game, player)

        # Auto-play minions from hand
        auto_play = self._find_auto_play(player, mask)
        if auto_play is not None:
            return auto_play

        # Enumerate productive actions
        productive = self._get_productive_actions(mask)
        if not productive:
            return END_TURN

        # Dispatch
        if self.beam_width > 0:
            return self._beam_search(game, player, productive)
        else:
            return self._greedy_search(game, player, mask, productive)

    def act_stochastic(self, game, player, temperature: float = 1.0):
        action = self.act(game, player)
        if action == END_TURN:
            return None
        return action, 0.0, 0.0

    def observe(self, action: int) -> None:
        pass

    def reset(self) -> None:
        pass

    # ── Greedy search (original one-step lookahead) ───────────────────────

    def _greedy_search(self, game, player, mask, productive: list[int]) -> int:
        baseline = self._evaluate_state(game, player)
        best_action = END_TURN
        best_value = baseline

        saved = _save_player(player)

        for action in productive:
            _restore_player(player, saved)

            if action in range(BUY_OFFSET, BUY_OFFSET + 7):
                value = self._eval_buy(game, player, action, saved)
            else:
                if not _simulate_action(player, action):
                    continue
                value = self._evaluate_state(game, player)

            if value > best_value:
                best_value = value
                best_action = action

        _restore_player(player, saved)
        return best_action

    # ── Beam search ───────────────────────────────────────────────────────

    def _beam_search(self, game, player, productive: list[int]) -> int:
        """Beam search over action sequences.

        Explores multi-step sequences up to beam_depth, keeping beam_width
        best partial sequences at each depth. Returns the first action of
        the best complete sequence, or END_TURN if none improve over baseline.
        """
        original = _save_player(player)
        baseline = self._evaluate_state(game, player)

        # Each beam element: (state_save, actions, value)
        beam = [(original.copy(), [], baseline)]

        for _depth in range(self.beam_depth):
            candidates = []

            for state_save, actions, _ in beam:
                _restore_player(player, state_save)

                # Get productive actions from this state
                mask = build_action_mask(game, player)
                prod = self._get_productive_actions(mask)

                if not prod:
                    # Dead end — keep as terminal
                    value = self._evaluate_state(game, player)
                    candidates.append((_save_player(player), actions, value))
                    continue

                # Try each productive action
                for action in prod:
                    _restore_player(player, state_save)
                    ok = _simulate_for_beam(player, action, self.rng)
                    if not ok:
                        continue
                    value = self._evaluate_state(game, player)
                    candidates.append(
                        (_save_player(player), actions + [action], value)
                    )

            if not candidates:
                break

            # Sort by value descending, keep top beam_width
            candidates.sort(key=lambda x: x[2], reverse=True)
            beam = candidates[:self.beam_width]

        _restore_player(player, original)

        if not beam:
            return END_TURN

        best_seq = beam[0][1]
        best_value = beam[0][2]

        if not best_seq or best_value <= baseline:
            return END_TURN
        return best_seq[0]

    # ── Action helpers ───────────────────────────────────────────────────

    def _find_auto_play(self, player, mask) -> Optional[int]:
        hand_plays = [a for a in range(PLAY_OFFSET, PLAY_OFFSET + 10) if mask[a]]
        for a in hand_plays:
            slot = a - PLAY_OFFSET
            if slot < len(player.hand):
                ct = player.hand[slot].get_tag(GameTag.CARDTYPE, CardType.INVALID)
                if ct == CardType.MINION:
                    return a
        return None

    def _get_productive_actions(self, mask) -> list[int]:
        actions = []
        for a in range(NUM_ACTIONS):
            if mask[a] and a not in (END_TURN, HERO_POWER):
                actions.append(a)
        return actions

    # ── Buy evaluation with auto-replace (greedy mode) ────────────────────

    def _eval_buy(self, game, player, action: int, saved: dict) -> float:
        slot = action - BUY_OFFSET
        if slot >= len(player.tavern):
            return -float("inf")

        entity = player.tavern[slot]
        ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
        cost = entity.get_tag(GameTag.COST, 3)
        if player.gold < cost:
            return -float("inf")

        board_living = player.get_board_minions()
        board_full = len(board_living) >= 7

        if ct == CardType.SPELL:
            saved2 = _save_player(player)
            player.gold -= cost
            player.tavern.pop(slot)
            value = self._evaluate_state(game, player)
            _restore_player(player, saved2)
            return value

        if ct != CardType.MINION:
            return -float("inf")

        if not board_full:
            saved2 = _save_player(player)
            player.gold -= cost
            entity_copy = player.tavern.pop(slot)
            player.hand.append(entity_copy)
            hand_slot = len(player.hand) - 1
            entity_copy2 = player.hand.pop(hand_slot)
            player.board.append(entity_copy2)
            value = self._evaluate_state(game, player)
            _restore_player(player, saved2)
            return value
        else:
            best_value = -float("inf")
            for replace_idx in range(len(board_living)):
                saved2 = _save_player(player)
                old_minion = board_living[replace_idx]
                if old_minion in player.board:
                    player.board.remove(old_minion)
                player.gold += 1
                player.gold -= cost
                entity_copy = player.tavern.pop(slot)
                player.hand.append(entity_copy)
                hand_slot = len(player.hand) - 1
                entity_copy2 = player.hand.pop(hand_slot)
                player.board.append(entity_copy2)
                value = self._evaluate_state(game, player)
                if value > best_value:
                    best_value = value
                _restore_player(player, saved2)
            return best_value

    # ── State evaluation ─────────────────────────────────────────────────

    def _evaluate_state(self, game, player) -> float:
        self._eval_count += 1

        obs = self._encode_pomdp(game, player, self.board_eval)

        value = self.game_value.predict(obs)
        if isinstance(value, np.ndarray):
            return float(value.item())
        return float(value)

    def get_stats(self) -> dict:
        return {"eval_count": self._eval_count, "step_count": self._step_count}


# ── Benchmark ───────────────────────────────────────────────────────────────


def benchmark(
    n_games: int = 30,
    agent_path: str = "checkpoints/game_value_v2.pt",
    board_eval_path: str = "checkpoints/board_eval_v2.pt",
    beam_width: int = 0,
    beam_depth: int = 3,
    device: str = "auto",
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    from hsrl.core.card_db import CARDS
    from hsrl.core.enums import CardType, State
    from hsrl.core.game import Game

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

    mode = f"beam(w={beam_width}, d={beam_depth})" if beam_width > 0 else "greedy"
    if verbose:
        print(f"SearchAgent benchmark: {n_games} games vs 7 heuristic opponents")
        print(f"  mode: {mode}")

    agent = SearchAgent(
        game_value_path=agent_path,
        board_eval_path=board_eval_path,
        beam_width=beam_width,
        beam_depth=beam_depth,
        device=device,
        seed=seed,
    )

    rankings = []
    wins = 0
    top4 = 0
    times = []

    for game_idx in range(n_games):
        game_seed = seed + game_idx
        random.seed(game_seed)
        np.random.seed(game_seed)

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

        agent_player = players[0]
        opponent_players = players[1:]
        agent.reset()

        t_start = time.time()

        while game.state == State.RUNNING and game.turn <= 30:
            for p in opponent_players:
                if not p.is_alive:
                    continue
                game.active_player = p
                game._auto_player_turn(p)
                game.resolve_queue()
                while game._pending_targeted_queue:
                    game.auto_resolve_pending_target()

            if agent_player.is_alive:
                game.active_player = agent_player
                for _ in range(50):
                    action = agent.act(game, agent_player)
                    if action == END_TURN:
                        break
                    from hsrl.env.action import decode_action
                    decode_action(action, game, agent_player)
                    game.resolve_queue()
                    while game._pending_targeted_queue:
                        game.auto_resolve_pending_target()

            game.end_recruit_phase()

            alive = [p for p in game.players if p.is_alive]
            if len(alive) <= 1:
                game.state = State.COMPLETE

        elapsed = time.time() - t_start
        times.append(elapsed)

        placement = 1
        for p in sorted(game.players,
                        key=lambda p: (not p.is_alive, -p.health)):
            if p is agent_player:
                break
            placement += 1

        rankings.append(placement)
        if placement == 1:
            wins += 1
        if placement <= 4:
            top4 += 1

        if verbose:
            avg_rank = sum(rankings) / len(rankings)
            print(f"  game {game_idx + 1:3d}/{n_games}  "
                  f"place={placement}  avg_rank={avg_rank:.2f}  "
                  f"win%={wins / (game_idx + 1) * 100:.1f}  "
                  f"top4%={top4 / (game_idx + 1) * 100:.1f}  "
                  f"time={elapsed:.1f}s", flush=True)

    avg_rank = sum(rankings) / len(rankings)
    avg_time = sum(times) / len(times)
    win_rate = wins / n_games
    top4_rate = top4 / n_games
    total_evals = agent._eval_count

    if verbose:
        print(f"\n{'='*60}")
        print(f"SearchAgent Benchmark [{mode}] ({n_games} games)")
        print(f"  avg_rank: {avg_rank:.2f}  |  win%: {win_rate * 100:.1f}  "
              f"|  top4%: {top4_rate * 100:.1f}")
        print(f"  avg_time: {avg_time:.1f}s/game  |  total_evals: {total_evals}")
        print(f"  evals/step: {total_evals / max(agent._step_count, 1):.1f}")
        print(f"\n  Baseline comparisons:")
        print(f"    Greedy heuristic:  avg_rank ~4.5,  win% ~10%,  top4% ~50%")
        print(f"    BC Policy argmax:  avg_rank  4.37, win% 13.3%, top4% 53.3%")
        print(f"    SearchAgent greedy: avg_rank  2.10, win%  0.0%, top4% 100%")
        print(f"{'='*60}")

    return {
        "avg_rank": avg_rank,
        "win_rate": win_rate,
        "top4_rate": top4_rate,
        "avg_time": avg_time,
        "total_evals": total_evals,
        "rankings": rankings,
    }


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SearchAgent (Phase 3)")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run benchmark against heuristic opponents")
    parser.add_argument("--games", type=int, default=30)
    parser.add_argument("--game-value", type=str,
                        default="checkpoints/game_value_v2.pt")
    parser.add_argument("--board-eval", type=str,
                        default="checkpoints/board_eval_v2.pt")
    parser.add_argument("--beam-width", type=int, default=0,
                        help="Beam width for search (0 = greedy one-step)")
    parser.add_argument("--beam-depth", type=int, default=3,
                        help="Max lookahead depth for beam search")
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.benchmark:
        benchmark(
            n_games=args.games,
            agent_path=args.game_value,
            board_eval_path=args.board_eval,
            beam_width=args.beam_width,
            beam_depth=args.beam_depth,
            device=args.device,
            seed=args.seed,
        )
    else:
        mode = f"beam(w={args.beam_width}, d={args.beam_depth})" if args.beam_width > 0 else "greedy"
        print(f"SearchAgent loaded [{mode}].")
        print(f"  GameValueNetwork: {args.game_value}")
        print(f"  BoardEvalNetwork: {args.board_eval}")
        agent = SearchAgent(
            game_value_path=args.game_value,
            board_eval_path=args.board_eval,
            beam_width=args.beam_width,
            beam_depth=args.beam_depth,
            device=args.device,
            seed=args.seed,
        )
        print("  Ready.")


if __name__ == "__main__":
    main()
