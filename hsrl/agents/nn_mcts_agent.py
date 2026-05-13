"""
BC Policy Agent for Battlegrounds Recruit Phase.

Uses a BC-pretrained dual-head network (policy π + value V).

Current approach (2026-05-13):
  - Policy argmax for action selection (π alone, no MCTS by default)
  - Auto-play minions from hand after buying (matches heuristic's buy→play pattern)
  - MCTS available via --mcts flag but does NOT outperform policy argmax

Why MCTS doesn't help (even with improved value network):

  The BC value network V(s) has MAE ~4.68 (BC) / ~3.90 (GAE-finetuned), but
  action-value differences in Battlegrounds are only ~0.5-1.0 in normalized space.
  Even with an MLP value head and unfrozen last trunk layer, the GAE training
  plateaued at MAE ~3.90 — still above the ~1.0 signal threshold.

  Root cause: the BC-pretrained trunk features encode correlational patterns from
  heuristic data (e.g. "refresh → winning" because heuristic refreshes when board
  is already strong). Fine-tuning only the last trunk layer + value head can't
  unlearn these correlations — the features themselves are confounded.

  Critical bug fix (2026-05-13): _evaluate_state was denormalizing V(s) to raw
  scale (-20..+20), while PUCT exploration bonus is ~[0, c_puct]. This 10x
  scale mismatch caused Q-values to dominate policy priors. Fix: keep values
  normalized so Q and exploration are on the same scale. Before fix: MCTS avg
  rank 7.70 (catastrophic). After fix: MCTS ≈ policy argmax (4.80 vs 4.37).

Benchmark results (30 games, vs 7 greedy opponents):

  | Method                       | avg_rank | win%  | top4% | time/game |
  |------------------------------|----------|-------|-------|-----------|
  | BC Policy argmax (original)  | 4.37     | 13.3% | 53.3% | 0.9s      |
  | BC Policy argmax (GAE model) | 4.80     | 10.0% | 40.0% | 0.7s      |
  | MCTS (original BC, 100 iter) | 5.23     | 0.0%  | 43.3% | 4.3s      |
  | MCTS (GAE model, 50 iter)    | 4.80     | 6.7%  | 53.3% | 4.0s      |
  | Greedy heuristic             | ~4.5     | ~10%  | ~50%  | 0.4s      |

  MCTS with normalized values no longer hurts (before fix: 7.70 avg rank), but
  it doesn't beat policy argmax. The value network noise (MAE 3.90) is still
  larger than action-value differences (~1.0), so MCTS can't reliably identify
  better-than-greedy actions.

Path forward:
  - Full PPO fine-tuning unfreezing trunk + policy + value on on-policy data
  - This lets the trunk learn causal features (actions → state transitions)
    rather than correlational ones (actions → final placement correlation)
  - Once V(s) MAE drops below ~2.0 raw / ~0.2 normalized, MCTS may help
"""

from __future__ import annotations

import math
import random
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
)
from hsrl.env.observation import build_observation
from hsrl.train.wrappers import FLAT_OBS_KEYS

_SAVE_TAGS = [
    GameTag.HERO_POWER_USED,
    GameTag.HERO_POWER_EXTRA_USES,
    GameTag.FREE_REFRESH_REMAINING,
]


# ═════════════════════════════════════════════════════════════════════════════
# State save/restore
# ═════════════════════════════════════════════════════════════════════════════

def _save_player(player):
    return {
        "gold": player.gold,
        "board": list(player.board),
        "hand": list(player.hand),
        "tavern": list(player.tavern),
        "tags": {tag: player.get_tag(tag, 0) for tag in _SAVE_TAGS},
        "health": player.health,
        "tavern_tier": player.tavern_tier,
    }


def _restore_player(player, saved):
    player.gold = saved["gold"]
    player.board = list(saved["board"])
    player.hand = list(saved["hand"])
    player.tavern = list(saved["tavern"])
    player.health = saved["health"]
    player.tavern_tier = saved["tavern_tier"]
    for tag, val in saved["tags"].items():
        player.set_tag(tag, val)


# ═════════════════════════════════════════════════════════════════════════════
# Observation encoding (matches training data)
# ═════════════════════════════════════════════════════════════════════════════

def _encode_state(game, player) -> np.ndarray:
    """Encode current state as flat 360-dim vector for network input."""
    obs = build_observation(game, player)
    parts = []
    for key in FLAT_OBS_KEYS:
        val = obs.get(key)
        if val is not None:
            parts.append(np.asarray(val, dtype=np.float32).ravel())
    return np.concatenate(parts)


# ═════════════════════════════════════════════════════════════════════════════
# Simplified actions (direct state manipulation, no engine events)
# ═════════════════════════════════════════════════════════════════════════════

def _sim_buy(player, tavern_slot: int) -> bool:
    if tavern_slot >= len(player.tavern):
        return False
    entity = player.tavern.pop(tavern_slot)
    cost = entity.get_tag(GameTag.COST, 3)
    if player.gold < cost:
        player.tavern.insert(tavern_slot, entity)
        return False
    player.gold -= cost
    player.hand.append(entity)
    return True


def _sim_play_from_hand(player, hand_slot: int) -> bool:
    if hand_slot >= len(player.hand):
        return False
    board_living = player.get_board_minions()
    if len(board_living) >= 7:
        return False
    entity = player.hand.pop(hand_slot)
    ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
    if ct != CardType.MINION:
        player.hand.insert(hand_slot, entity)
        return False
    player.board.append(entity)
    return True


def _sim_sell(player, board_slot: int) -> bool:
    living = [m for m in player.board if not m.dead]
    if board_slot >= len(living):
        return False
    entity = living.pop(board_slot)
    if entity in player.board:
        player.board.remove(entity)
    player.gold += 1
    return True


def _sim_refresh(player, rng) -> bool:
    """Simulate a tavern refresh with plausible minions."""
    if player.gold < 1 and player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) <= 0:
        return False

    if player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) > 0:
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        player.set_tag(GameTag.FREE_REFRESH_REMAINING, free - 1)
    else:
        player.gold -= 1

    player.tavern.clear()
    tier = player.tavern_tier
    _TIER_STATS = {
        1: (2, 3), 2: (3, 4), 3: (4, 5),
        4: (5, 6), 5: (6, 7), 6: (7, 8),
    }
    base_atk, base_hp = _TIER_STATS.get(tier, (4, 4))
    variance = tier

    from hsrl.core.entity import BaseEntity, CardData
    for i in range(min(7, 3 + tier)):
        atk = max(1, base_atk + rng.randint(-variance, variance))
        hp = max(1, base_hp + rng.randint(-variance, variance))
        data = CardData(
            id=f"_sim_t{tier}_{i}",
            name=f"SimTier{tier}",
            text="",
            tags={
                GameTag.BASE_ATK: atk,
                GameTag.BASE_HEALTH: hp,
                GameTag.COST: 3,
                GameTag.TECH_LEVEL: tier,
            },
        )
        entity = BaseEntity(data, game=None)
        player.tavern.append(entity)
    return True


# ═════════════════════════════════════════════════════════════════════════════
# MCTS Node & Search
# ═════════════════════════════════════════════════════════════════════════════

class _MCTSNode:
    __slots__ = ('state_save', 'parent_action', 'visit_count', 'total_value',
                 'prior', 'children', 'is_expanded', 'is_terminal', 'priors')

    def __init__(self, state_save, parent_action=None, prior=0.0, is_terminal=False):
        self.state_save = state_save
        self.parent_action = parent_action
        self.visit_count = 0
        self.total_value = 0.0
        self.prior = prior
        self.children: dict[int, _MCTSNode] = {}
        self.is_expanded = False
        self.is_terminal = is_terminal
        self.priors: dict[int, float] = {}  # action→prior for unexpanded children

    @property
    def q(self) -> float:
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count


class NNMCTSAgent:
    """Neural-network-guided MCTS agent for the recruit phase.

    Uses a dual-head BC network (π for prior, V for leaf evaluation)
    to search action sequences within the current gold budget.

    Parameters
    ----------
    model : BattlegroundsNetwork
        Trained dual-head network (policy + value).
    value_mean, value_std : float
        Normalization constants from BC training.
    n_iterations : int
        Number of MCTS iterations per decision.
    c_puct : float
        Exploration constant for PUCT selection.
    temperature : float
        Temperature for action probability softening (0 = argmax).
    seed : int, optional
    """

    def __init__(
        self,
        model,
        value_mean: float = 0.0,
        value_std: float = 1.0,
        n_iterations: int = 100,
        c_puct: float = 3.0,
        dirichlet_alpha: float = 0.3,
        dirichlet_frac: float = 0.25,
        temperature: float = 1.0,
        use_mcts: bool = False,
        seed: int = None,
    ):
        import torch
        self.model = model
        self.value_mean = value_mean
        self.value_std = value_std
        self.n_iterations = n_iterations
        self.c_puct = c_puct
        self.dirichlet_alpha = dirichlet_alpha
        self.dirichlet_frac = dirichlet_frac
        self.temperature = temperature
        self.use_mcts = use_mcts
        self.rng = random.Random(seed)
        self._torch = torch
        self._device = next(model.parameters()).device

    # ── Public API ───────────────────────────────────────────────────────

    def act(self, game, player) -> int:
        """Choose the best action using NN-guided MCTS.

        Uses policy argmax for action selection. The BC value network is
        too noisy (MAE ~4.68 vs action differences ~1.0) for reliable
        MCTS guidance, but the policy network (98.4% acc) faithfully
        reproduces the greedy heuristic.

        Auto-plays minions after buying, matching the heuristic's pattern
        that the BC policy was trained on (buy+play is one atomic step
        in the training data, but two separate actions in the discrete space).
        """
        mask = build_action_mask(game, player)
        valid = [int(i) for i in range(NUM_ACTIONS) if mask[i]]
        if not valid:
            return END_TURN

        # Strip HERO_POWER from search — BC value network has confound
        valid_search = [a for a in valid if a != HERO_POWER]

        # Check if there are productive non-END_TURN actions
        productive = [a for a in valid_search if a != END_TURN]
        if not productive:
            return END_TURN

        # Auto-play minions from hand first (matches heuristic's buy→play pattern)
        # This aligns the state with what the BC policy was trained on, where
        # buy and play happen atomically in the training loop.
        hand_plays = [a for a in range(14, 24) if mask[a]]
        if hand_plays:
            # Check if any hand card is a minion (not spell)
            for a in hand_plays:
                slot = a - 14
                if slot < len(player.hand):
                    ct = player.hand[slot].get_tag(GameTag.CARDTYPE, CardType.INVALID)
                    if ct == CardType.MINION:
                        return a

        # MCTS mode: use full MCTS with policy priors + value evaluation
        if self.use_mcts:
            action = self._mcts_search(game, player, valid_search)
            if action is not None:
                return action

        # Policy mode (default): argmax of policy network
        return self._policy_argmax(game, player, valid_search)

    def _policy_argmax(self, game, player, valid_actions: list[int]) -> int:
        """Argmax of policy network over valid actions."""
        obs = _encode_state(game, player)
        obs_tensor = self._torch.as_tensor(obs, dtype=self._torch.float32,
                                           device=self._device).unsqueeze(0)
        with self._torch.no_grad():
            logits, _ = self.model(obs_tensor)
            logits = logits.squeeze(0)

        # Mask invalid actions
        mask = self._torch.ones(logits.shape[0], device=self._device) * (-1e9)
        for a in valid_actions:
            mask[a] = 0.0
        masked_logits = logits + mask

        if self.temperature < 0.01:
            return int(masked_logits.argmax().item())

        probs = self._torch.softmax(masked_logits / self.temperature, dim=0)
        action = self._torch.multinomial(probs, 1).item()
        return int(action)

    def _policy_sample(self, game, player, valid_actions: list[int],
                       temperature: float = 1.0) -> tuple[int, float, float]:
        """Sample action from policy distribution (for PPO rollouts).

        Returns (action, log_prob, value_norm).
        """
        obs = _encode_state(game, player)
        obs_tensor = self._torch.as_tensor(obs, dtype=self._torch.float32,
                                           device=self._device).unsqueeze(0)
        with self._torch.no_grad():
            logits, value = self.model(obs_tensor)
            logits = logits.squeeze(0)
            value_norm = value.item()

        # Mask invalid actions
        mask = self._torch.ones(logits.shape[0], device=self._device) * (-1e9)
        for a in valid_actions:
            mask[a] = 0.0
        masked_logits = logits + mask

        probs = self._torch.softmax(masked_logits / temperature, dim=0)
        dist = self._torch.distributions.Categorical(probs)
        action = int(dist.sample().item())
        log_prob = float(dist.log_prob(
            self._torch.tensor(action, device=self._device)).item())
        return action, log_prob, value_norm

    def act_stochastic(self, game, player, temperature: float = 1.0):
        """Choose action with stochastic policy sampling (for PPO rollouts).

        Handles auto-play of minions from hand deterministically (these
        are forced moves, not learned choices), then samples from the
        policy distribution for real decisions.

        Returns (action, log_prob, value_norm) or None if turn should end.
        """
        from hsrl.env.action import END_TURN, HERO_POWER

        mask = build_action_mask(game, player)
        valid = [int(i) for i in range(NUM_ACTIONS) if mask[i]]
        if not valid:
            return None

        # Auto-play minions from hand first (deterministic — these are forced)
        hand_plays = [a for a in range(14, 24) if mask[a]]
        for a in hand_plays:
            slot = a - 14
            if slot < len(player.hand):
                ct = player.hand[slot].get_tag(GameTag.CARDTYPE, CardType.INVALID)
                if ct == CardType.MINION:
                    return a, 0.0, 0.0  # forced action, no log_prob/value needed

        # Check productive actions (exclude hero power, end turn)
        productive = [a for a in valid if a not in (HERO_POWER, END_TURN)]
        if not productive:
            return None

        return self._policy_sample(game, player, productive, temperature)

    def observe(self, action: int) -> None:
        pass

    def reset(self) -> None:
        pass

    # ── MCTS Search ──────────────────────────────────────────────────────

    def _mcts_search(self, game, player, valid_actions: list[int]) -> Optional[int]:
        root_save = _save_player(player)
        root = _MCTSNode(root_save, is_terminal=False)

        # Compute policy priors for root node (policy network guidance)
        root.priors = self._compute_priors(game, player, valid_actions)

        # Apply Dirichlet noise to root priors (AlphaZero-style exploration)
        if self.dirichlet_alpha > 0:
            noise = np.random.dirichlet(
                [self.dirichlet_alpha] * len(root.priors)
            )
            frac = self.dirichlet_frac
            for i, a in enumerate(sorted(root.priors.keys())):
                root.priors[a] = (1 - frac) * root.priors[a] + frac * noise[i]

        for _ in range(self.n_iterations):
            _restore_player(player, root_save)
            node = root
            path = [node]

            # 1. SELECT: descend tree using PUCT
            while node.is_expanded and not node.is_terminal:
                cur_valid = (valid_actions if node is root
                             else self._get_valid_actions(player, game))
                if not cur_valid:
                    break
                action = self._select_puct(node, cur_valid)
                if action is None or action not in node.children:
                    break
                self._apply_action(player, action, game)
                node = node.children[action]
                path.append(node)

            # 2. EXPAND: add one child, then check if node is fully expanded
            if not node.is_terminal:
                cur_valid = (valid_actions if node is root
                             else self._get_valid_actions(player, game))
                unexpanded = [a for a in cur_valid if a not in node.children]
                if unexpanded:
                    # Sample proportionally to policy priors (not uniform)
                    probs = [node.priors.get(a, 0.01) for a in unexpanded]
                    total_p = sum(probs)
                    probs = [p / total_p for p in probs]
                    action = self.rng.choices(unexpanded, weights=probs, k=1)[0]
                    self._apply_action(player, action, game)
                    is_terminal = (action == END_TURN)
                    child_state = _save_player(player)
                    prior = node.priors.get(action, 0.0)
                    child = _MCTSNode(child_state, parent_action=action,
                                      prior=prior, is_terminal=is_terminal)
                    node.children[action] = child
                    # Set expanded when all valid actions have been tried
                    if not [a for a in cur_valid if a not in node.children]:
                        node.is_expanded = True
                    node = child
                    path.append(node)

            # 3. EVALUATE: value network for leaf
            if node.is_terminal:
                value = 0.0
            else:
                value = self._evaluate_state(game, player)

            # 4. BACKUP
            for n in reversed(path):
                n.visit_count += 1
                n.total_value += value

        # Restore player to original state before returning
        _restore_player(player, root_save)

        # Build action distribution from root visit counts
        action_counts = {}
        for a, child in root.children.items():
            if a in valid_actions:
                action_counts[a] = child.visit_count

        if not action_counts:
            return END_TURN

        if self.temperature < 0.01:
            return max(action_counts, key=action_counts.get)

        # Softmax with temperature
        actions = list(action_counts.keys())
        counts = np.array([action_counts[a] for a in actions], dtype=np.float64)
        probs = np.exp(np.log(counts + 1e-8) / self.temperature)
        probs /= probs.sum()
        return int(self.rng.choices(actions, weights=probs, k=1)[0])

    # ── PUCT Selection ──────────────────────────────────────────────────

    def _select_puct(self, node: _MCTSNode, valid_actions: list[int]) -> Optional[int]:
        """Select action using PUCT formula with learned prior."""
        if not valid_actions:
            return END_TURN if END_TURN in node.children or not node.is_expanded else None

        total_visits = node.visit_count
        if total_visits == 0:
            # Sample from prior distribution instead of uniform
            probs = []
            for a in valid_actions:
                p = node.priors.get(a, 0.01)
                probs.append(p)
            total_p = sum(probs)
            if total_p > 0:
                probs = [p / total_p for p in probs]
            else:
                probs = [1.0 / len(valid_actions)] * len(valid_actions)
            return self.rng.choices(valid_actions, weights=probs, k=1)[0]

        best_action = None
        best_score = -float('inf')

        for a in valid_actions:
            child = node.children.get(a)
            if child is not None:
                q = child.q
                n = child.visit_count
                prior = child.prior
            else:
                q = 0.0
                n = 0
                prior = node.priors.get(a, 0.01)

            # PUCT: Q + c_puct * prior * sqrt(total_visits) / (1 + visits)
            exploration = self.c_puct * prior * math.sqrt(total_visits) / (1 + n)
            score = q + exploration

            if score > best_score:
                best_score = score
                best_action = a

        return best_action

    # ── Helpers ──────────────────────────────────────────────────────────

    def _compute_priors(self, game, player, valid_actions: list[int]) -> dict[int, float]:
        """Compute action priors from the policy network for the root state.

        Returns a dict mapping action_id → prior probability (softmax over valid).
        """
        obs = _encode_state(game, player)
        obs_tensor = self._torch.as_tensor(obs, dtype=self._torch.float32,
                                           device=self._device).unsqueeze(0)
        with self._torch.no_grad():
            policy = self.model.get_policy(obs_tensor).squeeze(0)

        # Extract probabilities for valid actions, re-normalize
        valid_probs = {a: float(policy[a].item()) for a in valid_actions}
        total = sum(valid_probs.values())
        if total > 0:
            valid_probs = {a: p / total for a, p in valid_probs.items()}
        return valid_probs

    def _get_valid_actions(self, player, game=None, exclude_hero_power: bool = True) -> list[int]:
        """Build list of valid actions using the real action mask logic."""
        valid = []
        gold = player.gold
        board_count = len(player.get_board_minions())

        # Buy
        for i, entity in enumerate(player.tavern):
            cost = entity.get_tag(GameTag.COST, 3)
            ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct in (CardType.MINION, CardType.SPELL) and gold >= cost:
                valid.append(BUY_OFFSET + i)

        # Sell
        living = [m for m in player.board if not m.dead]
        for i in range(len(living)):
            valid.append(SELL_OFFSET + i)

        # Play from hand
        if board_count < 7:
            for i, card in enumerate(player.hand):
                ct = card.get_tag(GameTag.CARDTYPE, CardType.INVALID)
                if ct in (CardType.MINION, CardType.SPELL):
                    valid.append(PLAY_OFFSET + i)

        # Refresh
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        if gold >= 1 or free > 0:
            valid.append(REFRESH)

        # Upgrade
        upgrade_cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
        if gold >= upgrade_cost and player.tavern_tier < 6:
            valid.append(UPGRADE)

        # Hero power — excluded from MCTS (BC value network has confound:
        # states with HERO_POWER_USED=True correlate with winning in training
        # data regardless of whether the HP caused the win)
        if not exclude_hero_power:
            if (not player.get_tag(GameTag.HERO_POWER_USED, False)
                    or player.get_tag(GameTag.HERO_POWER_EXTRA_USES, 0) > 0):
                hp_cost = player.hero_power_cost
                if gold >= hp_cost:
                    valid.append(HERO_POWER)

        # Freeze
        if len(player.tavern) > 0:
            valid.append(FREEZE)

        # End turn
        valid.append(END_TURN)

        return valid

    def _apply_action(self, player, action: int, game) -> bool:
        """Apply a single action using simplified state manipulation."""
        if BUY_OFFSET <= action <= BUY_OFFSET + 6:
            return _sim_buy(player, action - BUY_OFFSET)

        if SELL_OFFSET <= action <= SELL_OFFSET + 6:
            return _sim_sell(player, action - SELL_OFFSET)

        if PLAY_OFFSET <= action <= PLAY_OFFSET + 9:
            return _sim_play_from_hand(player, action - PLAY_OFFSET)

        if action == UPGRADE:
            cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
            if player.gold >= cost and player.tavern_tier < 6:
                player.gold -= cost
                player.tavern_tier += 1
                return True
            return False

        if action == REFRESH:
            return _sim_refresh(player, self.rng)

        if action == HERO_POWER:
            if not player.get_tag(GameTag.HERO_POWER_USED, False) and player.gold >= 1:
                player.gold -= 1
                player.set_tag(GameTag.HERO_POWER_USED, True)
                return True
            return False

        if action == FREEZE:
            return True

        if action == END_TURN:
            return True

        return False

    def _evaluate_state(self, game, player) -> float:
        """Evaluate state using value network V(s). Returns normalized value.

        We keep values normalized so the Q scale (~[-2,+2]) matches the
        PUCT exploration bonus scale (~[0, c_puct]), preventing value bias
        from overpowering policy priors.
        """
        obs = _encode_state(game, player)
        obs_tensor = self._torch.as_tensor(obs, dtype=self._torch.float32,
                                           device=self._device).unsqueeze(0)
        return self.model.get_value(obs_tensor).item()
