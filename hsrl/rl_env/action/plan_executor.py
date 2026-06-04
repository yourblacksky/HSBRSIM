"""
PlanExecutor — execute a RecruitPlan on a game snapshot.

Uses save_player_state / restore_player_state for rollback.
Validates legality step-by-step. Returns execution diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hsrl.agents.agent_utils import (
    save_player_state, restore_player_state,
    simulate_action, populate_tavern,
)
from hsrl.env.action import REFRESH, END_TURN
from hsrl.env.reward import compute_board_strength
from hsrl.rl_env.action.atomic_action import ActionType, action_to_legacy_id, end_turn
from hsrl.rl_env.action.recruit_plan import (
    RecruitPlan, PlanExecutionResult, PlanValidationResult,
)

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player
    from hsrl.rl_env.action.action_grammar import ActionGrammar


class PlanExecutor:
    """Execute a RecruitPlan on a game snapshot with rollback support."""

    def __init__(self, grammar: "ActionGrammar | None" = None):
        self.grammar = grammar or _default_grammar

    def validate(
        self, game: "Game", player: "Player", plan: RecruitPlan,
        max_actions: int = 40,
    ) -> PlanValidationResult:
        """Check if a plan can be legally executed from the current state.
        Does NOT modify the game state (uses snapshot/restore internally).
        """
        if not plan.actions:
            return PlanValidationResult(
                is_valid=False, reason="empty plan", first_invalid_step=0)

        saved = save_player_state(player)
        board_before = compute_board_strength(player)

        for i, action in enumerate(plan.actions):
            if i >= max_actions:
                restore_player_state(player, saved)
                return PlanValidationResult(
                    is_valid=False, first_invalid_step=i,
                    reason=f"exceeded max_actions={max_actions}",
                    executed_prefix_length=i)

            if action.action_type == ActionType.END_TURN:
                restore_player_state(player, saved)
                return PlanValidationResult(
                    is_valid=True, executed_prefix_length=i + 1,
                    final_state_summary={
                        "board_before": board_before,
                        "board_after": compute_board_strength(player),
                    })

            legacy_id = action_to_legacy_id(action)
            if legacy_id is None:
                restore_player_state(player, saved)
                return PlanValidationResult(
                    is_valid=False, first_invalid_step=i,
                    reason=f"no legacy mapping for {action}",
                    executed_prefix_length=i)

            if not simulate_action(player, legacy_id):
                restore_player_state(player, saved)
                return PlanValidationResult(
                    is_valid=False, first_invalid_step=i,
                    reason=f"simulate_action failed at step {i}: {action}",
                    executed_prefix_length=i)

            if legacy_id == REFRESH:
                populate_tavern(player, game.rng)

        # Plan ended without END_TURN
        board_after = compute_board_strength(player)
        restore_player_state(player, saved)
        return PlanValidationResult(
            is_valid=True, executed_prefix_length=len(plan.actions),
            reason="plan ended without END_TURN",
            final_state_summary={
                "board_before": board_before,
                "board_after": board_after,
            })

    def execute(
        self, game: "Game", player: "Player", plan: RecruitPlan,
        max_actions: int = 40,
    ) -> PlanExecutionResult:
        """Execute a plan on the actual game state (mutates state).
        Only call this when you want to permanently apply the plan.
        """
        board_before = compute_board_strength(player)
        gold_before = player.gold
        gold_spent = 0

        for i, action in enumerate(plan.actions):
            if i >= max_actions:
                return PlanExecutionResult(
                    success=False, actions_executed=i,
                    terminated_by="MAX_ACTIONS",
                    board_score_before=board_before,
                    board_score_after=compute_board_strength(player),
                    gold_spent=gold_spent,
                    gold_remaining=player.gold,
                    diagnostics={"reason": f"exceeded max_actions={max_actions}"})

            if action.action_type == ActionType.END_TURN:
                return PlanExecutionResult(
                    success=True, actions_executed=i + 1,
                    terminated_by="END_TURN",
                    board_score_before=board_before,
                    board_score_after=compute_board_strength(player),
                    gold_spent=gold_spent,
                    gold_remaining=player.gold)

            legacy_id = action_to_legacy_id(action)
            if legacy_id is None:
                return PlanExecutionResult(
                    success=False, actions_executed=i,
                    terminated_by="INVALID_ACTION",
                    board_score_before=board_before,
                    board_score_after=compute_board_strength(player),
                    gold_spent=gold_spent,
                    gold_remaining=player.gold,
                    diagnostics={"reason": f"no legacy mapping for {action}"})

            gold_before_step = player.gold
            if not simulate_action(player, legacy_id):
                return PlanExecutionResult(
                    success=False, actions_executed=i,
                    terminated_by="INVALID_ACTION",
                    board_score_before=board_before,
                    board_score_after=compute_board_strength(player),
                    gold_spent=gold_spent,
                    gold_remaining=player.gold,
                    diagnostics={"reason": f"simulate_action failed at step {i}"})

            gold_spent += (gold_before_step - player.gold)
            if legacy_id == REFRESH:
                populate_tavern(player, game.rng)

        return PlanExecutionResult(
            success=True, actions_executed=len(plan.actions),
            terminated_by="PLAN_END",
            board_score_before=board_before,
            board_score_after=compute_board_strength(player),
            gold_spent=gold_spent,
            gold_remaining=player.gold,
            diagnostics={"reason": "plan ended without END_TURN"})


# Module-level default (imports lazily to avoid circular deps)
_default_grammar = None
