"""
AlphaZero-style MCTS Agent for Hearthstone Battlegrounds Recruit Phase.

Uses deep state snapshot/restore for safe tree search, BoardEvalNetwork
for fast combat outcome prediction, and GameValueNetwork for leaf evaluation.

Natural language:
  At each recruit step, run MCTS over legal action sequences. Each node
  stores visit counts N(s,a) and action values Q(s,a). Search is guided
  by PUCT: Q + c_puct * P * sqrt(N_parent) / (1 + N_child).

  After search, return the action with the most visits (or sample from
  visit distribution for exploration during self-play).

Architecture:
  State snapshot → MCTS tree (per-turn) → best action → execute in real game

Usage:
  from hsrl.agents.az_agent import AZAgent
  agent = AZAgent(game_value_path=..., board_eval_path=...)
  action = agent.act(game, player)  # returns action index or END_TURN
"""

from __future__ import annotations

import math
import random
import time
from typing import Optional

import numpy as np

from hsrl.core.enums import CardType, GameTag
from hsrl.env.action import (
    BUY_OFFSET, END_TURN, FREEZE, HERO_POWER, NUM_ACTIONS,
    PLAY_OFFSET, REFRESH, SELL_OFFSET, UPGRADE,
    build_action_mask, decode_action, get_action_name,
)


# ── MCTS Node ────────────────────────────────────────────────────────────────

class MCTSNode:
    """A node in the MCTS tree representing a game state and an action edge."""

    __slots__ = (
        "state_snapshot", "action", "parent", "children",
        "visit_count", "value_sum", "prior", "is_terminal",
    )

    def __init__(self, state_snapshot: dict, action: int = -1,
                 parent: Optional["MCTSNode"] = None, prior: float = 1.0):
        self.state_snapshot = state_snapshot  # from game.snapshot_player_state()
        self.action = action       # action that led to this node (-1 = root)
        self.parent = parent
        self.children: list[MCTSNode] = []
        self.visit_count = 0
        self.value_sum = 0.0       # sum of backpropagated values
        self.prior = prior         # policy prior P(s,a) from network
        self.is_terminal = False   # END_TURN or max depth reached

    @property
    def q_value(self) -> float:
        if self.visit_count == 0:
            return 0.0
        return self.value_sum / self.visit_count

    def ucb_score(self, parent_visit: int, c_puct: float = 1.4) -> float:
        """PUCT score: Q + c_puct * P * sqrt(N_parent) / (1 + N_child)."""
        if self.visit_count == 0:
            return float("inf")  # Ensure unvisited children are explored first
        exploration = c_puct * self.prior * math.sqrt(parent_visit) / (1 + self.visit_count)
        return self.q_value + exploration


# ── AlphaZero Agent ──────────────────────────────────────────────────────────

class AZAgent:
    """AlphaZero MCTS agent for Battlegrounds recruit phase.

    At each decision point, runs MCTS simulations over legal action sequences.
    Each simulation:
      1. SELECT: descend tree using PUCT until a leaf
      2. EXPAND: add children for all legal actions at leaf
      3. EVALUATE: compute leaf value via GameValueNetwork + combat prediction
      4. BACKUP: propagate value up the tree

    After search, returns the action with the highest visit count.
    """

    def __init__(
        self,
        game_value_path: str = None,
        board_eval_path: str = "checkpoints/board_eval_v3_clean.pt",
        n_simulations: int = 200,
        c_puct: float = 1.4,
        max_depth: int = 5,
        temperature: float = 1.0,
        device: str = "auto",
        seed: int = None,
    ):
        import torch
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.device = device
        self.rng = random.Random(seed)
        self.n_simulations = n_simulations
        self.c_puct = c_puct
        self.max_depth = max_depth
        self.temperature = temperature

        # Load BoardEvalNetwork (primary evaluation)
        from hsrl.train.board_eval import BoardEvalTrainer
        self.board_eval = BoardEvalTrainer.load(board_eval_path, device=device)

        # Load value network (optional, for leaf evaluation)
        self.game_value = None
        self._encode_pomdp = None
        if game_value_path is not None:
            ckpt = torch.load(game_value_path, map_location=device, weights_only=False)
            version = ckpt.get("version", "v2")
            if version == "dense":
                from hsrl.train.value_dense import DenseValueNetwork, encode_pomdp_state as _enc
                self.game_value = DenseValueNetwork().to(device)
                self.game_value.load_state_dict(ckpt["model_state_dict"])
                self.game_value.eval()
                self._encode_pomdp = _enc
            elif version == "v4":
                from hsrl.train.game_value_sp import SelfPlayGameValueTrainer
                from hsrl.train.game_value_sp import encode_pomdp_state as _enc
                self.game_value = SelfPlayGameValueTrainer.load(game_value_path, device=device)
                self._encode_pomdp = _enc
            else:
                from hsrl.train.game_value import GameValueTrainer
                from hsrl.train.game_value import encode_pomdp_state as _enc
                self.game_value = GameValueTrainer.load(game_value_path, device=device)
                self._encode_pomdp = _enc

        # Stats
        self._sim_count = 0
        self._step_count = 0

    # ── Public API ───────────────────────────────────────────────────────

    def act(self, game, player) -> int:
        """Choose the best action via MCTS search."""
        import torch

        # Handle pending events (same as SearchAgent)
        while True:
            if getattr(game, '_pending_choice', None) is not None:
                game.resolve_pending_choice(
                    self.rng.randrange(len(game._pending_choice.options)))
                continue
            offers = getattr(player, '_pending_trinket_offers', [])
            if offers:
                affordable = [i for i, cid in enumerate(offers)
                              if player.gold >= self._get_trinket_cost(game, cid)]
                if affordable:
                    idx = self.rng.choice(affordable)
                    game.buy_trinket(player, idx)
                    game.resolve_queue()
                else:
                    player._pending_trinket_offers = []
                continue
            break

        mask = build_action_mask(game, player)
        auto_play = self._find_auto_play(player, mask)
        if auto_play is not None:
            return auto_play

        productive = [a for a in range(NUM_ACTIONS)
                      if mask[a] and a not in (END_TURN, HERO_POWER)]
        if not productive:
            return END_TURN

        self._step_count += 1

        # ── Run MCTS ──
        root_snap = game.snapshot_player_state(player)
        root = MCTSNode(state_snapshot=root_snap, action=-1)
        root.visit_count = 1  # Root counts as visited

        # Pre-expand root so children always exist if productive is non-empty
        self._expand(root, game, player, mask)

        if not root.children:
            return END_TURN

        for _ in range(self.n_simulations):
            self._sim_count += 1
            # Restore to root state before each simulation
            game.restore_player_state(player, root_snap)

            # SELECT → EXPAND → EVALUATE → BACKUP
            leaf = self._select(root, game, player, mask)
            if leaf is None:
                continue
            value = self._evaluate_leaf(leaf, game, player)
            self._backup(leaf, value)

        # Restore to root state before returning (engine state untouched)
        game.restore_player_state(player, root_snap)

        # Select action from root
        if self.temperature > 0 and self.temperature < 0.01:
            # Deterministic: most visits
            best_child = max(root.children, key=lambda c: c.visit_count)
            return best_child.action
        elif self.temperature > 0:
            # Stochastic: sample from visit distribution
            visits = np.array([c.visit_count for c in root.children], dtype=np.float64)
            visits = visits ** (1.0 / self.temperature)
            probs = visits / visits.sum()
            idx = self.rng.choices(range(len(root.children)), weights=probs)[0]
            return root.children[idx].action
        else:
            best_child = max(root.children, key=lambda c: c.visit_count)
            return best_child.action

    # ── MCTS phases ──────────────────────────────────────────────────────

    def _select(self, node: MCTSNode, game, player, mask) -> Optional[MCTSNode]:
        """Select a leaf node by descending the tree using PUCT."""
        depth = 0

        while node.children and depth < self.max_depth:
            # Find child with best UCB score
            best_child = None
            best_score = -float("inf")

            for child in node.children:
                score = child.ucb_score(node.visit_count, self.c_puct)
                if score > best_score:
                    best_score = score
                    best_child = child

            if best_child is None:
                return node

            # Restore to child's state
            game.restore_player_state(player, best_child.state_snapshot)
            mask = build_action_mask(game, player)
            node = best_child
            depth += 1

        # EXPAND this node if not terminal
        if not node.is_terminal and depth < self.max_depth:
            self._expand(node, game, player, mask)

        return node

    def _expand(self, node: MCTSNode, game, player, mask) -> None:
        """Expand a node by creating children for all legal actions.

        END_TURN is treated as a special terminal action — when selected,
        the resulting state is evaluated directly (no further expansion).
        """
        productive = [a for a in range(NUM_ACTIONS)
                      if mask[a] and a not in (HERO_POWER, FREEZE)]

        n = max(len(productive), 1)
        for action in productive:
            # Restore to node state before each simulation
            game.restore_player_state(player, node.state_snapshot)

            if action == END_TURN:
                # END_TURN: snapshot current state, node is terminal
                child_snap = game.snapshot_player_state(player)
                child = MCTSNode(
                    state_snapshot=child_snap,
                    action=action,
                    parent=node,
                    prior=1.0 / n,
                )
                child.is_terminal = True
                node.children.append(child)
                continue

            # Simulate the action
            if not self._sim_action(game, player, action):
                continue

            # Snapshot resulting state
            child_snap = game.snapshot_player_state(player)
            child = MCTSNode(
                state_snapshot=child_snap,
                action=action,
                parent=node,
                prior=1.0 / n,
            )
            node.children.append(child)

        # If no productive actions, mark as terminal
        if not node.children:
            node.is_terminal = True

    def _evaluate_leaf(self, node: MCTSNode, game, player) -> float:
        """Evaluate a leaf node.

        Uses dense value network (survival + board strength) if available,
        otherwise falls back to BoardEval pairwise combat prediction.

        Returns value where higher = better.
        """
        from hsrl.train.combat_data import encode_board_from_minions

        # If dense value network is available, use it
        if self.game_value is not None and self._encode_pomdp is not None:
            try:
                import torch as _torch
                obs = self._encode_pomdp(game, player, self.board_eval)
                t = _torch.as_tensor(obs, dtype=_torch.float32, device=self.device).unsqueeze(0)
                val = self.game_value(t)
                return float(val.item())
            except Exception:
                pass  # Fall through to BoardEval

        # Fallback: BoardEval pairwise combat prediction
        living = [m for m in player.board if not m.dead]
        if not living:
            return -1.0  # empty board is bad

        own_enc = encode_board_from_minions(player.board)

        # Collect opponent boards from combat memory
        opponents = [p for p in game.players if p is not player and p.is_alive]
        if not opponents:
            return 0.8  # only one alive = winning

        win_probs = []
        for opp in opponents:
            # Prefer combat memory (last-seen board), fall back to current board
            opp_board = None
            pid = player.entity_id
            oid = opp.entity_id
            if hasattr(game, 'combat_memory') and pid in game.combat_memory:
                if oid in game.combat_memory[pid]:
                    opp_board = game.combat_memory[pid][oid].board

            # Use current board if no combat memory (e.g. Turn 1)
            if not opp_board:
                opp_board = [m for m in opp.board if not m.dead]

            if opp_board:
                opp_enc = encode_board_from_minions(opp_board)
                try:
                    p_win = self.board_eval.predict_win_prob(own_enc, opp_enc)
                    win_probs.append(p_win)
                except Exception:
                    win_probs.append(0.5)
            else:
                win_probs.append(0.5)  # both boards empty → tie

        if not win_probs:
            return 0.5

        return sum(win_probs) / len(win_probs)

    def _backup(self, node: MCTSNode, value: float) -> None:
        """Backpropagate value up the tree."""
        while node is not None:
            node.visit_count += 1
            node.value_sum += value
            node = node.parent

    # ── Helpers ───────────────────────────────────────────────────────────

    def _compute_priors(self, game, player, mask, productive) -> dict:
        """Compute policy priors for each action.

        Currently uniform over productive actions. Can be replaced with
        a learned policy network (Phase 3.2).
        """
        n = len(productive)
        return {a: 1.0 / n for a in productive}

    def _sim_action(self, game, player, action: int) -> bool:
        """Simulate a single action via direct state manipulation.

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
            # Auto-play minion to board if space
            ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct == CardType.MINION and len(player.get_board_minions()) < 7:
                player.hand.remove(entity)
                player.board.append(entity)
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
            if len(player.get_board_minions()) >= 7:
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
            # Plausible tavern regeneration: keep entities but mark for eval
            return True

        if action == UPGRADE:
            cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
            if player.gold < cost or player.tavern_tier >= 7:
                return False
            player.gold -= cost
            player.tavern_tier += 1
            _BASE = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10}
            player.set_tag(GameTag.TAVERN_UPGRADE_COST,
                          _BASE.get(player.tavern_tier + 1, 10))
            return True

        return False

    def _find_auto_play(self, player, mask) -> Optional[int]:
        """Auto-play minions from hand (same as SearchAgent)."""
        hand_plays = [a for a in range(PLAY_OFFSET, PLAY_OFFSET + 10) if mask[a]]
        for a in hand_plays:
            slot = a - PLAY_OFFSET
            if slot < len(player.hand):
                ct = player.hand[slot].get_tag(GameTag.CARDTYPE, CardType.INVALID)
                if ct == CardType.MINION:
                    return a
        return None

    @staticmethod
    def _get_trinket_cost(game, card_id: str) -> int:
        data = game.card_db.get(card_id) if game.card_db else None
        return data.tags.get(GameTag.COST, 3) if data and data.tags else 99

    def get_stats(self) -> dict:
        return {
            "sim_count": self._sim_count,
            "step_count": self._step_count,
            "sims_per_step": self._sim_count / max(self._step_count, 1),
        }
