"""
TurnRecruitEnv — a single recruit phase as an RL episode.

Each episode is one player's turn. The environment supports:
  - step_atomic(action) → execute one AtomicAction
  - execute_plan(plan) → execute a full RecruitPlan
  - collect_trajectory(policy) → auto-play and record TurnTrajectory

Episode terminates on: END_TURN, invalid action, max_actions exceeded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

from hsrl.core.enums import GameTag, CardType
from hsrl.agents.agent_utils import save_player_state, restore_player_state, simulate_action, populate_tavern
from hsrl.env.action import REFRESH, END_TURN
from hsrl.rl_env.action.atomic_action import ActionType, action_to_legacy_id, end_turn
from hsrl.rl_env.action.action_grammar import ActionGrammar
from hsrl.rl_env.action.recruit_plan import RecruitPlan, PlanExecutionResult
from hsrl.rl_env.action.plan_executor import PlanExecutor
from hsrl.rl_env.core.rl_state import RLState
from hsrl.rl_env.core.turn_trajectory import TurnTrajectory
from hsrl.rl_env.observation.observation_v2 import build_observation_v2
from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.rl_env.reward.reward_components import compute_turn_reward

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player
    from hsrl.rl_env.action.atomic_action import AtomicAction


class TurnRecruitEnv:
    """A single recruit phase as an RL training episode.

    Created from an existing Game + Player. Reset to turn-start state.
    The episode is the player's full recruit phase.

    Usage:
        env = TurnRecruitEnv(game, player_id=0)
        state = env.reset()
        while not state.is_terminal:
            action = policy(state)
            state, reward, done = env.step_atomic(action)
    """

    MAX_ACTIONS_PER_TURN = 40

    def __init__(
        self, game: "Game", player_id: int,
        grammar: "ActionGrammar | None" = None,
    ):
        self._game = game
        self._player_id = player_id
        self._grammar = grammar or ActionGrammar()
        self._executor = PlanExecutor(self._grammar)
        self._actions_taken = 0
        self._board_before: float = 0.0
        self._gold_before: int = 0
        self._turn_id: int = 0
        self._saved_start: dict | None = None

    @property
    def game(self) -> "Game":
        return self._game

    @property
    def player(self) -> "Player":
        return self._game.players[self._player_id]

    # ── Public API ──────────────────────────────────────────────────────────

    def reset(self) -> RLState:
        """Reset to the start of this player's recruit phase."""
        p = self.player
        self._actions_taken = 0
        self._turn_id = self._game.turn
        self._board_before = compute_board_score_v2(p).total
        self._gold_before = p.gold
        self._saved_start = save_player_state(p)

        obs = build_observation_v2(self._game, p)
        mask = self._grammar.build_legacy_mask(self._game, p)

        return RLState(
            game_id=str(id(self._game)),
            turn_id=self._turn_id,
            player_id=self._player_id,
            phase="recruit",
            observation=obs,
            legal_atomic_mask=mask,
        )

    def step_atomic(
        self, action: "AtomicAction | int",
    ) -> tuple[RLState, float, bool]:
        """Execute one atomic action. Returns (state, reward, done)."""
        p = self.player
        self._actions_taken += 1

        # Convert to legacy ID if needed
        if isinstance(action, int):
            legacy_id = action
        else:
            legacy_id = action_to_legacy_id(action)
            if legacy_id is None:
                return self._build_state(), -0.5, True  # invalid

        # Check END_TURN
        if legacy_id == END_TURN:
            return self._build_state(), self._compute_reward(), True

        # Check max actions
        if self._actions_taken >= self.MAX_ACTIONS_PER_TURN:
            return self._build_state(), -0.1, True

        # Execute via simulate_action
        if not simulate_action(p, legacy_id):
            return self._build_state(), -0.5, True

        if legacy_id == REFRESH:
            # Real engine refresh (draw from the actual minion pool), NOT
            # agent_utils.populate_tavern which fabricates fake_T* placeholders
            # for beam-search evaluation and would poison the real game state.
            self._game.refresh_tavern(p)

        # Auto-play hand minions
        self._auto_play_hand(p)

        return self._build_state(), 0.0, False

    def execute_plan(self, plan: RecruitPlan) -> PlanExecutionResult:
        """Execute a full RecruitPlan. Returns execution result."""
        if self._saved_start:
            restore_player_state(self.player, self._saved_start)
        return self._executor.execute(self._game, self.player, plan)

    def collect_trajectory(
        self, policy_fn, option_type: str | None = None,
    ) -> TurnTrajectory:
        """Collect a TurnTrajectory using the given policy function.

        Args:
            policy_fn: callable(obs, mask) → AtomicAction | int
            option_type: optional MacroOption label for this turn
        """
        state = self.reset()
        trajectory = TurnTrajectory(
            game_id=str(id(self._game)),
            player_id=self._player_id,
            turn_id=self._turn_id,
            option_type=option_type,
            start_observation=state.observation,
            board_score_before=self._board_before,
            source="policy",
        )

        while not state.is_terminal and self._actions_taken < self.MAX_ACTIONS_PER_TURN:
            action = policy_fn(state.observation, state.legal_atomic_mask)
            if isinstance(action, int):
                legacy_id = action
                action_obj = self._grammar.legacy_id_to_action(action)
            else:
                legacy_id = action_to_legacy_id(action)
                action_obj = action

            trajectory.action_sequence.append(action_obj)
            trajectory.per_step_observations.append(state.observation)
            trajectory.per_step_legal_masks.append(state.legal_atomic_mask)

            state, reward, done = self.step_atomic(legacy_id)
            if done:
                break

        # Fill end-of-turn labels
        p = self.player
        board_after = compute_board_score_v2(p)
        trajectory.end_observation = state.observation
        trajectory.board_score_after = board_after.total
        trajectory.board_score_delta = board_after.total - self._board_before
        trajectory.gold_spent = self._gold_before - p.gold
        trajectory.gold_remaining = p.gold
        trajectory.labels = {
            "board_score_before": self._board_before,
            "board_score_after": board_after.total,
            "board_score_delta": trajectory.board_score_delta,
            "gold_spent": trajectory.gold_spent,
        }

        return trajectory

    # ── Internal ────────────────────────────────────────────────────────────

    def _build_state(self) -> RLState:
        p = self.player
        obs = build_observation_v2(self._game, p)
        mask = self._grammar.build_legacy_mask(self._game, p)
        is_terminal = self._actions_taken >= self.MAX_ACTIONS_PER_TURN

        return RLState(
            game_id=str(id(self._game)),
            turn_id=self._turn_id,
            player_id=self._player_id,
            phase="recruit",
            observation=obs,
            legal_atomic_mask=mask,
            is_terminal=is_terminal,
        )

    def _compute_reward(self) -> float:
        p = self.player
        board_after = compute_board_score_v2(p).total
        delta = board_after - self._board_before
        reward = delta * 0.05  # same scale as old recruit reward
        if self._actions_taken > 20:
            reward -= 0.01 * (self._actions_taken - 20)  # efficiency penalty
        return float(reward)

    @staticmethod
    def _auto_play_hand(player: "Player") -> None:
        board_count = len([m for m in player.board if not m.dead])
        for m in [c for c in player.hand
                  if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION]:
            if board_count >= 7:
                break
            player.hand.remove(m)
            player.board.append(m)
            board_count += 1
