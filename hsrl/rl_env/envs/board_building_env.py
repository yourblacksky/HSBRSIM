"""
BoardBuildingEnv — fast board evaluator training without full combat.

Runs T turns of pure recruiting for 8 players, ranks by board_score.
Each turn is an episode for TurnRecruitEnv. Used for rapid iteration
on recruit strategy before integrating combat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable

import numpy as np

from hsrl.core.card_db import CARDS
from hsrl.core.game import Game
from hsrl.core.enums import GameTag, CardType
from hsrl.rl_env.envs.turn_recruit_env import TurnRecruitEnv
from hsrl.rl_env.core.turn_trajectory import TurnTrajectory
from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.rl_env.reward.rank_labels import compute_rank_labels


@dataclass
class BoardBuildingEpisode:
    """Result of a full board-building game (T turns, 8 players)."""
    turns: int = 0
    player_scores: list[float] = field(default_factory=list)
    player_ranks: list[int] = field(default_factory=list)
    trajectories: list[TurnTrajectory] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BoardBuildingEnv:
    """No-combat board building for fast recruit strategy training.

    Runs T turns of pure recruiting. Each turn has 8 players who
    independently build their boards. After T turns, players are
    ranked by board_score.

    Usage:
        env = BoardBuildingEnv(turn_limit=10)
        episode = env.run_episode(policy_fns)
        # episode.trajectories contains 8*10 trajectories for training
    """

    def __init__(self, turn_limit: int = 8, seed: int | None = None):
        self.turn_limit = turn_limit
        self._seed = seed
        self._game: Game | None = None

    def run_episode(
        self,
        policy_fns: list[Callable],
    ) -> BoardBuildingEpisode:
        """Run a full board-building game.

        Args:
            policy_fns: list of 8 callable(obs, mask) → AtomicAction | int.
                       One per player. Use lambda for heuristic fallback.
        """
        if len(policy_fns) != 8:
            raise ValueError(f"Need 8 policy functions, got {len(policy_fns)}")

        seed = self._seed or int(np.random.randint(0, 99999))
        game = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=seed)
        self._game = game
        all_trajectories = []

        for turn in range(1, self.turn_limit + 1):
            # Start of turn: give gold, refresh, auto-play hand
            for p in game.players:
                p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
                p.set_tag(GameTag.HERO_POWER_USED, False)
                p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
                cost = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
                if cost > 0:
                    p.set_tag(GameTag.TAVERN_UPGRADE_COST, cost - 1)
            for p in game.players:
                game.refresh_tavern(p)
                self._auto_play_hand(p)

            # Each player takes their turn
            for idx in range(8):
                env = TurnRecruitEnv(game, player_id=idx)
                traj = env.collect_trajectory(policy_fns[idx])
                traj.source = "board_building"
                all_trajectories.append(traj)

                # Auto-play hand after turn
                self._auto_play_hand(game.players[idx])

        # Rank by final board scores
        scores = [compute_board_score_v2(p).total for p in game.players]
        ranks = np.array(scores).argsort()[::-1].argsort() + 1

        # Fill rank labels for all trajectories
        for traj in all_trajectories:
            player_rank = int(ranks[traj.player_id])
            traj.final_rank_if_game_finished = player_rank
            traj.placement_if_terminal = player_rank
            traj.top4 = player_rank <= 4
            traj.top1 = player_rank == 1

        return BoardBuildingEpisode(
            turns=self.turn_limit,
            player_scores=[float(s) for s in scores],
            player_ranks=[int(r) for r in ranks],
            trajectories=all_trajectories,
            metadata={"seed": seed, "turn_limit": self.turn_limit},
        )

    def run_episodes(
        self, policy_fns: list[Callable], num_episodes: int,
    ) -> list[BoardBuildingEpisode]:
        """Run multiple episodes with different seeds."""
        episodes = []
        for i in range(num_episodes):
            self._seed = (self._seed or 0) + i + 1
            episodes.append(self.run_episode(policy_fns))
        return episodes

    @staticmethod
    def _auto_play_hand(player):
        bc = len([m for m in player.board if not m.dead])
        for m in [c for c in player.hand
                  if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION]:
            if bc >= 7: break
            player.hand.remove(m); player.board.append(m); bc += 1
