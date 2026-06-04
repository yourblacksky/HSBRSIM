"""
RecruitPlan — a complete within-turn action sequence.

A RecruitPlan represents all actions a player takes during one recruit phase.
It can be executed, validated, scored, and used as a training target for
plan-level policy learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
import uuid

from hsrl.rl_env.action.atomic_action import (
    AtomicAction, ActionType, ZoneType, end_turn, noop,
)

if TYPE_CHECKING:
    from hsrl.rl_env.action.action_grammar import ActionGrammar


@dataclass
class PlanValidationResult:
    """Result of validating a plan against the current game state."""
    is_valid: bool
    first_invalid_step: int | None = None
    reason: str | None = None
    executed_prefix_length: int = 0
    final_state_summary: dict | None = None


@dataclass
class PlanExecutionResult:
    """Result of executing a plan on a game snapshot."""
    success: bool
    actions_executed: int
    terminated_by: str  # END_TURN, INVALID_ACTION, MAX_ACTIONS, PHASE_CHANGE
    board_score_before: float = 0.0
    board_score_after: float = 0.0
    gold_spent: int = 0
    gold_remaining: int = 0
    diagnostics: dict = field(default_factory=dict)


@dataclass
class RecruitPlan:
    """A complete recruit phase action sequence.

    Must satisfy:
      - All atomic actions are legal when executed sequentially.
      - Does not cross recruit phase boundaries.
      - Terminates with END_TURN or forced termination.
      - Can be replayed via snapshot/restore.
    """
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    player_id: int = 0
    turn_id: int = 0

    actions: list[AtomicAction] = field(default_factory=list)

    # Optional: macro option that generated this plan
    option_type: str | None = None

    # Snapshot references (for replay)
    start_snapshot_id: str | None = None
    end_snapshot_id: str | None = None

    # Execution metadata
    is_legal: bool = True
    terminated_by: str = "END_TURN"

    # Labels filled after execution
    board_score_before: float = 0.0
    board_score_after: float = 0.0
    labels: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def first_action(self) -> AtomicAction | None:
        return self.actions[0] if self.actions else None

    @property
    def last_action(self) -> AtomicAction | None:
        return self.actions[-1] if self.actions else None

    @property
    def action_type_sequence(self) -> list[str]:
        return [a.action_type.value for a in self.actions]

    @property
    def board_score_delta(self) -> float:
        return self.board_score_after - self.board_score_before

    def append(self, action: AtomicAction) -> None:
        self.actions.append(action)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "player_id": self.player_id,
            "turn_id": self.turn_id,
            "actions": [
                {
                    "type": a.action_type.value,
                    "source_zone": a.source_zone.value if a.source_zone != ZoneType.NONE else None,
                    "source_index": a.source_index if a.source_index >= 0 else None,
                    "target_zone": a.target_zone.value if a.target_zone != ZoneType.NONE else None,
                    "target_index": a.target_index if a.target_index >= 0 else None,
                    "choice_index": a.choice_index if a.choice_index >= 0 else None,
                }
                for a in self.actions
            ],
            "option_type": self.option_type,
            "board_score_before": self.board_score_before,
            "board_score_after": self.board_score_after,
            "labels": self.labels,
        }

    @classmethod
    def from_legacy_sequence(
        cls, action_ids: list[int], player_id: int = 0, turn_id: int = 0,
    ) -> "RecruitPlan":
        """Build a RecruitPlan from legacy 0-49 action IDs."""
        from hsrl.rl_env.action.atomic_action import legacy_id_to_action
        plan = cls(player_id=player_id, turn_id=turn_id)
        for aid in action_ids:
            plan.append(legacy_id_to_action(aid))
        return plan

    def __repr__(self) -> str:
        n = len(self.actions)
        preview = " → ".join(a.action_type.value[:4] for a in self.actions[:5])
        if n > 5:
            preview += f" ... (+{n - 5})"
        return f"RecruitPlan({self.plan_id}, {n} actions: {preview})"


# ═══════════════════════════════════════════════════════════════════════════════
# Factory: build sample plans for testing
# ═══════════════════════════════════════════════════════════════════════════════

def empty_plan(player_id: int = 0, turn_id: int = 0) -> RecruitPlan:
    """A minimal plan: just END_TURN."""
    return RecruitPlan(
        player_id=player_id, turn_id=turn_id,
        actions=[end_turn()],
    )


def heuristic_plan(actions: list[AtomicAction]) -> RecruitPlan:
    """Build a plan from a heuristic-produced action list."""
    plan = RecruitPlan(actions=list(actions))
    return plan
