"""
PlanSearchTeacher — generates and evaluates candidate RecruitPlans.

The teacher:
  1. Saves turn-start snapshot
  2. Generates candidate plans (policy samples, heuristics, mutations)
  3. For each plan: restore snapshot, execute, score
  4. Returns ranked plans with scores for distillation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

from hsrl.agents.agent_utils import save_player_state, restore_player_state
from hsrl.rl_env.action.recruit_plan import RecruitPlan, PlanExecutionResult, empty_plan
from hsrl.rl_env.action.plan_executor import PlanExecutor
from hsrl.rl_env.reward.board_score import compute_board_score_v2

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


@dataclass
class PlanEvaluationResult:
    """Score and diagnostics for a candidate plan."""
    plan: RecruitPlan
    score: float = 0.0
    board_after: float = 0.0
    board_delta: float = 0.0
    gold_spent: int = 0
    gold_remaining: int = 0
    is_legal: bool = True
    diagnostics: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return (f"PlanEval(score={self.score:.1f}, board→{self.board_after:.0f}, "
                f"delta={self.board_delta:+.1f}, gold={self.gold_spent}, legal={self.is_legal})")


class PlanSearchTeacher:
    """Generates candidate plans and evaluates them via snapshot rollback.

    Sources of candidates:
      - Policy sampled plans (from the current policy)
      - Heuristic plans (from game engine auto-play)
      - Mutated plans (random perturbations of high-scoring historical plans)

    Scoring formula:
      score = w_board * board_after + w_delta * board_delta
            + w_econ * gold_efficiency - w_invalid * is_invalid
    """

    def __init__(
        self,
        w_board: float = 1.0,
        w_delta: float = 0.3,
        w_econ: float = 0.1,
        w_invalid: float = 10.0,
        temperature: float = 0.5,
        max_candidates: int = 20,
    ):
        self.w_board = w_board
        self.w_delta = w_delta
        self.w_econ = w_econ
        self.w_invalid = w_invalid
        self.temperature = temperature
        self.max_candidates = max_candidates
        self.executor = PlanExecutor()

    def generate_candidates(
        self, game: "Game", player: "Player",
        policy_fn: Optional[Callable] = None,
    ) -> list[RecruitPlan]:
        """Generate candidate plans from multiple sources.

        Args:
            game, player: current game state
            policy_fn: optional callable(obs, mask) → action. If None,
                      only heuristic plans are generated.
        """
        candidates = []

        # 1. Heuristic baseline: empty plan (just END_TURN)
        candidates.append(empty_plan(player.game.players.index(player), game.turn))

        # 2. Policy-sampled plans (if policy provided)
        if policy_fn is not None:
            for _ in range(min(3, self.max_candidates)):
                plan = self._sample_plan_from_policy(game, player, policy_fn)
                if plan and plan.action_count > 0:
                    candidates.append(plan)

        # 3. Heuristic from existing game auto-play
        # (Uses the game's built-in heuristic if available)

        return candidates[:self.max_candidates]

    def evaluate_candidates(
        self, game: "Game", player: "Player", plans: list[RecruitPlan],
    ) -> list[PlanEvaluationResult]:
        """Evaluate all candidate plans via snapshot rollback.

        For each plan:
          1. Save current state
          2. Execute the plan
          3. Score the resulting state
          4. Restore original state
        """
        saved = save_player_state(player)
        board_before = compute_board_score_v2(player).total
        results = []

        for plan in plans:
            restore_player_state(player, saved)

            exec_result = self.executor.execute(game, player, plan)
            board_after = compute_board_score_v2(player).total
            board_delta = board_after - board_before
            gold_efficiency = board_delta / max(exec_result.gold_spent, 1)

            if exec_result.success:
                score = (
                    self.w_board * board_after +
                    self.w_delta * board_delta +
                    self.w_econ * gold_efficiency
                )
            else:
                score = -self.w_invalid

            results.append(PlanEvaluationResult(
                plan=plan,
                score=float(score),
                board_after=float(board_after),
                board_delta=float(board_delta),
                gold_spent=exec_result.gold_spent,
                gold_remaining=exec_result.gold_remaining,
                is_legal=exec_result.success,
                diagnostics={"terminated_by": exec_result.terminated_by},
            ))

        restore_player_state(player, saved)
        return results

    def make_training_target(
        self, evaluations: list[PlanEvaluationResult],
    ) -> dict:
        """Convert evaluation results into a training target.

        Returns:
            best_plan: the highest-scoring plan
            target_distribution: softmax(score / temperature) over plans
            teacher_value: best score
            best_first_action: first action of best plan
        """
        if not evaluations:
            return {
                "best_plan": empty_plan(),
                "teacher_value": 0.0,
                "best_first_action": None,
            }

        # Sort by score descending
        evals = sorted(evaluations, key=lambda e: e.score, reverse=True)
        best = evals[0]

        # Boltzmann distribution over plans
        scores = np.array([e.score for e in evals])
        scores = np.clip(scores, -50, 50)
        scores = (scores - scores.max()) / self.temperature
        probs = np.exp(scores)
        probs /= probs.sum()

        return {
            "best_plan": best.plan,
            "teacher_value": best.score,
            "best_first_action": best.plan.first_action,
            "plan_distribution": {
                evals[i].plan.plan_id: float(probs[i])
                for i in range(len(evals))
            },
            "evaluations": evals,
        }

    # ── Internal ────────────────────────────────────────────────────────────

    def _sample_plan_from_policy(
        self, game: "Game", player: "Player", policy_fn: Callable,
    ) -> Optional[RecruitPlan]:
        """Sample one plan by running the policy until END_TURN."""
        from hsrl.rl_env.observation.observation_v2 import build_observation_v2
        from hsrl.rl_env.action.action_grammar import ActionGrammar
        from hsrl.rl_env.action.atomic_action import (
            ActionType, action_to_legacy_id, legacy_id_to_action,
        )
        from hsrl.agents.agent_utils import simulate_action, populate_tavern
        from hsrl.env.action import REFRESH, END_TURN, NUM_ACTIONS

        grammar = ActionGrammar()
        plan = RecruitPlan(
            player_id=game.players.index(player),
            turn_id=game.turn,
        )
        max_actions = 30

        for _ in range(max_actions):
            obs = build_observation_v2(game, player)
            mask = grammar.build_legacy_mask(game, player)

            try:
                action = policy_fn(obs, mask)
            except Exception:
                break

            if isinstance(action, int):
                legacy_id = action
                action_obj = legacy_id_to_action(action)
            else:
                legacy_id = action_to_legacy_id(action)
                action_obj = action

            if legacy_id is None or legacy_id == END_TURN:
                break

            plan.append(action_obj)

            if not simulate_action(player, legacy_id):
                break
            if legacy_id == REFRESH:
                populate_tavern(player, game.rng)

        return plan if plan.action_count > 0 else None
