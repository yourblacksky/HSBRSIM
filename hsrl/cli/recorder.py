"""Human-play trajectory recorder.

Records (observation, action) pairs during the recruit phase and saves them
in the standard HSRL Trajectory format compatible with the trajectory system.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from hsrl.core.enums import GameTag
from hsrl.rl_env.observation.observation_v2 import build_observation_v2
from hsrl.trajectory.record import MinionSnapshot, TurnSnapshot, Trajectory


class GameRecorder:
    """Records player actions and builds a Trajectory for a single game."""

    def __init__(self, hero_id: str = "", hero_name: str = "", output_dir: str = "data/trajectories_cli/"):
        self.hero_id = hero_id
        self.hero_name = hero_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.game_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.actions: list[tuple[int, dict, int]] = []  # (turn, obs_dict, action_id)
        self.turn_snapshots: list[TurnSnapshot] = []
        self.start_time = time.time()

    def record_action(self, turn: int, observation: dict, action_id: int):
        self.actions.append((turn, observation, action_id))

    def record_turn_end(self, player):
        """Snapshot board state at end of turn."""
        board = []
        for m in [m for m in player.board if not m.dead]:
            card_id = m.get_tag(GameTag.CARD_ID, "")
            board.append(MinionSnapshot(
                card_id=card_id,
                is_golden=m.get_tag(12, 0) > 0,
                atk=m.atk,
                health=m.health,
                max_health=m.health + m.get_tag(GameTag.DAMAGE, 0),
                race=_race_str(m.get_tag(GameTag.RACE, 0)),
                taunt=getattr(m, "taunt", False),
                divine_shield=getattr(m, "divine_shield", False),
                poisonous=getattr(m, "poisonous", False),
                venomous=getattr(m, "venomous", False),
                reborn=getattr(m, "reborn", False),
                windfury=getattr(m, "windfury", False),
                cleave=False,
                position=0,
            ))

        trinket_ids = [t.get_tag(GameTag.CARD_ID, "") for t in getattr(player, "trinkets", [])]

        self.turn_snapshots.append(TurnSnapshot(
            turn=len(self.turn_snapshots) + 1,
            health=player.health,
            armor=player.armor,
            tavern_tier=player.tavern_tier,
            gold=player.gold,
            board=board,
            trinkets=trinket_ids,
            hero_power_used=False,
        ))

    def build_trajectory(self, placement: int = 0) -> Trajectory:
        if not self.turn_snapshots:
            return Trajectory(
                game_id=self.game_id, hero_id=self.hero_id,
                hero_name=self.hero_name, seed=0, active_tribes=[], placement=placement,
                final_health=0, final_tier=1, turns=[],
            )
        last = self.turn_snapshots[-1]
        return Trajectory(
            game_id=self.game_id,
            hero_id=self.hero_id,
            hero_name=self.hero_name,
            seed=0,
            active_tribes=[],
            placement=placement,
            final_health=last.health,
            final_tier=last.tavern_tier,
            turns=self.turn_snapshots,
        )

    def save(self, placement: int = 0):
        traj = self.build_trajectory(placement)
        out_path = self.output_dir / f"{self.game_id}.json"
        with open(out_path, "w") as f:
            json.dump(traj.to_dict(), f, indent=2, ensure_ascii=False)

        # Update index
        index_file = self.output_dir / "index.jsonl"
        with open(index_file, "a") as idx:
            idx.write(json.dumps({
                "game_id": self.game_id,
                "hero_id": self.hero_id,
                "placement": placement,
                "turns": len(self.turn_snapshots),
                "actions": len(self.actions),
                "duration_s": int(time.time() - self.start_time),
                "timestamp": datetime.now().isoformat(),
            }, ensure_ascii=False) + "\n")

        print(f"\n  轨迹已保存: {out_path}")
        print(f"  回合数: {len(self.turn_snapshots)} | 动作数: {len(self.actions)}")


def _race_str(race_val: int) -> str:
    mapping = {
        14: "MURLOC", 15: "DEMON", 17: "MECH", 18: "ELEMENTAL",
        20: "BEAST", 21: "TOTEM", 23: "PIRATE", 24: "DRAGON",
        28: "QUILBOAR", 30: "NAGA", 11: "UNDEAD", 22: "NERUBIAN",
    }
    return mapping.get(race_val, "INVALID")
