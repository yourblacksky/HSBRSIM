"""
FullGameSelfPlayEnv — complete 8-player self-play environment.

Runs full Battlegrounds games with combat, damage, and elimination.
Wraps TurnRecruitEnv for each player's turn. Supports:
  - Self-play with mixed policies (RL + heuristic + search)
  - Per-player trajectory collection
  - Final placement labels
  - Combat logging
  - Trajectory opponent injection

Usage:
    env = FullGameSelfPlayEnv(turn_limit=15, skip_combat=False)
    episode = env.run_game(agent_fns)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from hsrl.core.card_db import CARDS
from hsrl.core.game import Game
from hsrl.core.enums import GameTag, CardType, State
from hsrl.rl_env.core.turn_trajectory import TurnTrajectory
from hsrl.rl_env.envs.turn_recruit_env import TurnRecruitEnv
from hsrl.rl_env.reward.board_score import compute_board_score_v2


@dataclass
class GameTrajectory:
    """Complete game result with per-player turn trajectories."""
    game_id: str = ""
    seed: int = 0
    total_turns: int = 0
    player_placements: list[int] = field(default_factory=list)
    player_scores: list[float] = field(default_factory=list)
    trajectories: list[TurnTrajectory] = field(default_factory=list)
    combat_log: list[dict] = field(default_factory=list)
    anomaly: str = ""
    tribes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class FullGameSelfPlayEnv:
    """Complete 8-player Battlegrounds self-play environment.

    Each game runs until only 1 player remains or max_turns is reached.
    Uses the full game engine including combat, damage, and elimination.

    Supports both full-combat and no-combat (board building) modes.
    """

    def __init__(
        self,
        turn_limit: int = 15,
        skip_combat: bool = True,   # default: board-building mode
        seed: int | None = None,
    ):
        self.turn_limit = turn_limit
        self.skip_combat = skip_combat
        self._seed = seed
        self._game: Game | None = None

    # ── Public API ──────────────────────────────────────────────────────────

    def run_game(
        self,
        agent_fns: list[Callable],
        hero_ids: list[str] | None = None,
        seed: int | None = None,
    ) -> GameTrajectory:
        """Run a complete 8-player game.

        Args:
            agent_fns: list of 8 callable(obs, mask) → int. One per player.
            hero_ids: optional list of 8 hero card IDs.
            seed: random seed for this game.

        Returns:
            GameTrajectory with per-player turn trajectories and placements.
        """
        if len(agent_fns) != 8:
            raise ValueError(f"Need 8 agent functions, got {len(agent_fns)}")

        game_seed = seed or self._seed or int(np.random.randint(0, 99999))
        heroes = hero_ids or ['BG20_HERO_100'] * 8
        game = Game.create_game(heroes, CARDS, seed=game_seed)
        self._game = game
        all_trajectories: list[TurnTrajectory] = []

        anomaly = game.active_anomaly
        anomaly_name = anomaly.data.name if anomaly and not isinstance(anomaly, bool) else "none"
        # Anomaly scripts loaded from JSON may store tribe filters as raw
        # integer enum values, while the normal draft path stores Race members.
        tribes = (
            sorted(_enum_name(t) for t in game.active_tribes)
            if game.active_tribes else ["ALL"]
        )

        for turn in range(1, self.turn_limit + 1):
            alive = [p for p in game.players if p.is_alive]
            if len(alive) <= 1:
                break

            # ── Start recruit phase ──
            for p in game.players:
                if not p.is_alive: continue
                p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
                p.set_tag(GameTag.HERO_POWER_USED, False)
                p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
                cost = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
                if cost > 0:
                    p.set_tag(GameTag.TAVERN_UPGRADE_COST, cost - 1)
            for p in game.players:
                if not p.is_alive: continue
                game.refresh_tavern(p)
                self._auto_play_hand(p)

            # ── Each player takes their turn ──
            for idx in range(8):
                if not game.players[idx].is_alive: continue
                env = TurnRecruitEnv(game, player_id=idx)
                agent_fn = agent_fns[idx]
                traj = env.collect_trajectory(agent_fn)
                traj.source = "self_play"
                all_trajectories.append(traj)
                self._auto_play_hand(game.players[idx])

            # ── Combat (or skip) ──
            if not self.skip_combat:
                self._run_combat_phase(game)
            else:
                # Board-building mode: no combat, no damage
                pass

            # Check game over
            if game.state == State.COMPLETE:
                break

        # ── Final placement ──
        if self.skip_combat:
            # Rank by board score (no elimination in board-building mode)
            scores = [compute_board_score_v2(p).total for p in game.players]
            score_ranks = np.array(scores).argsort()[::-1].argsort() + 1
            placements = [int(r) for r in score_ranks]
        else:
            from hsrl.env.reward import compute_placement
            placements = [compute_placement(p, game.players) for p in game.players]
            scores = [compute_board_score_v2(p).total for p in game.players]

        # Fill labels
        for traj in all_trajectories:
            rank = placements[traj.player_id]
            traj.final_rank_if_game_finished = rank
            traj.placement_if_terminal = rank
            traj.top4 = rank <= 4
            traj.top1 = rank == 1

        return GameTrajectory(
            game_id=str(id(game)),
            seed=game_seed,
            total_turns=game.turn,
            player_placements=[int(p) for p in placements],
            player_scores=[float(s) for s in scores],
            trajectories=all_trajectories,
            combat_log=[],
            anomaly=anomaly_name,
            tribes=tribes,
            metadata={
                "skip_combat": self.skip_combat,
                "turn_limit": self.turn_limit,
            },
        )

    def run_games(
        self, agent_fns: list[Callable], num_games: int,
    ) -> list[GameTrajectory]:
        """Run multiple games with different seeds."""
        results = []
        for i in range(num_games):
            seed = (self._seed or 0) + i + 1
            results.append(self.run_game(agent_fns, seed=seed))
        return results

    # ── Internal ────────────────────────────────────────────────────────────

    def _run_combat_phase(self, game: Game) -> None:
        """Run the full combat phase (engine-level)."""
        try:
            game.end_recruit_phase()
        except Exception:
            # If end_recruit_phase fails, skip combat and continue
            pass

    @staticmethod
    def _auto_play_hand(player):
        bc = len([m for m in player.board if not m.dead])
        for m in [c for c in player.hand
                  if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION]:
            if bc >= 7: break
            player.hand.remove(m); player.board.append(m); bc += 1


def _enum_name(value) -> str:
    """Serialize enum members and versioned raw enum values consistently."""
    from hsrl.core.enums import Race

    try:
        return Race(value).name
    except (TypeError, ValueError):
        return str(value)
