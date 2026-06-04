"""
HSRL RL Environment v2 — turn-level recruit plan training.

Layers:
  Level 0: TurnRecruitEnv      — single turn as episode
  Level 1: BoardBuildingEnv    — T turns, no combat, rank by board_score
  Level 2: FullGameSelfPlayEnv — 8-player self-play with combat
  Level 3: PopulationLeagueEnv — diverse strategy pool
  Level 4: PlanSearchEvaluationEnv — plan scoring teacher
"""

from hsrl.rl_env.action.atomic_action import (
    AtomicAction, ActionType, ZoneType,
    action_to_legacy_id, legacy_id_to_action,
    buy, sell, play, roll, level, freeze, end_turn,
    hero_power, discover_choose, noop,
)
from hsrl.rl_env.action.action_grammar import ActionGrammar
from hsrl.rl_env.action.macro_option import (
    MacroOption, OptionType, RiskProfile,
    ALL_OPTIONS, ALL_OPTIONS_COUNT,
)
from hsrl.rl_env.action.recruit_plan import (
    RecruitPlan, PlanValidationResult, PlanExecutionResult,
)
from hsrl.rl_env.action.plan_executor import PlanExecutor
from hsrl.rl_env.core.rl_state import RLState
from hsrl.rl_env.core.turn_trajectory import TurnTrajectory
from hsrl.rl_env.core.snapshot_manager import SnapshotManager
from hsrl.rl_env.observation.observation_v2 import build_observation_v2
from hsrl.rl_env.observation.observation_validator import ObservationValidator
from hsrl.rl_env.reward.board_score import BoardScore, compute_board_score_v2
from hsrl.rl_env.reward.rank_labels import RankLabels, compute_rank_labels
from hsrl.rl_env.reward.reward_components import RewardComponents, compute_turn_reward
from hsrl.rl_env.envs.turn_recruit_env import TurnRecruitEnv
from hsrl.rl_env.envs.board_building_env import BoardBuildingEnv, BoardBuildingEpisode
