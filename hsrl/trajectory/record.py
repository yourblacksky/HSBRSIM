"""
HSRL Trajectory Data Structures

Trajectory = one winning player's full game history.
Each turn snapshot captures board, trinkets, and player state before recruit phase.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from hsrl.core.enums import Race

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.minion import Minion
    from hsrl.core.player import Player


@dataclasses.dataclass
class MinionSnapshot:
    """Serializable snapshot of a single minion's state."""
    card_id: str
    atk: int
    health: int
    max_health: int
    race: int  # Race enum value
    is_golden: bool = False
    taunt: bool = False
    divine_shield: bool = False
    poisonous: bool = False
    venomous: bool = False
    reborn: bool = False
    windfury: bool = False
    cleave: bool = False
    position: int = 0

    @classmethod
    def from_minion(cls, minion: Minion, position: int = 0) -> "MinionSnapshot":
        from hsrl.core.enums import GameTag
        return cls(
            card_id=minion.get_tag(GameTag.CARD_ID) or "",
            atk=minion.atk,
            health=minion.health,
            max_health=minion.max_health,
            race=int(minion.race),
            is_golden=minion.is_golden,
            taunt=minion.taunt,
            divine_shield=minion.divine_shield,
            poisonous=minion.poisonous,
            venomous=minion.venomous,
            reborn=minion.reborn,
            windfury=minion.windfury,
            cleave=minion.cleave,
            position=position,
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MinionSnapshot":
        return cls(**d)


@dataclasses.dataclass
class TurnSnapshot:
    """Player state snapshot at the start of a turn (before recruit)."""
    turn: int
    health: int
    armor: int
    tavern_tier: int
    gold: int
    board: List[MinionSnapshot] = dataclasses.field(default_factory=list)
    trinkets: List[str] = dataclasses.field(default_factory=list)
    hero_power_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["board"] = [m.to_dict() for m in self.board]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TurnSnapshot":
        board_data = d.get("board", [])
        board = [MinionSnapshot.from_dict(m) for m in board_data]
        # Build kwargs excluding "board" to avoid duplicate keyword
        kwargs = {k: v for k, v in d.items() if k != "board"}
        return cls(**kwargs, board=board)


@dataclasses.dataclass
class Trajectory:
    """Full winning trajectory for a single player."""
    game_id: str
    hero_id: str
    hero_name: str
    seed: int
    active_tribes: List[str]  # e.g. ["BEAST", "MECH", "DEMON"]
    placement: int
    final_health: int
    final_tier: int
    turns: List[TurnSnapshot] = dataclasses.field(default_factory=list)
    anomaly_id: Optional[str] = None  # If an anomaly was active

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["turns"] = [t.to_dict() for t in self.turns]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Trajectory":
        turns_data = d.get("turns", [])
        turns = [TurnSnapshot.from_dict(t) for t in turns_data]
        kwargs = {k: v for k, v in d.items() if k != "turns"}
        return cls(**kwargs, turns=turns)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "Trajectory":
        import json
        return cls.from_dict(json.loads(json_str))


def snapshot_board(minions: List["Minion"]) -> List[MinionSnapshot]:
    """Capture board state as a list of MinionSnapshot."""
    return [MinionSnapshot.from_minion(m, i) for i, m in enumerate(minions)]


def snapshot_player(player: "Player", turn: int) -> TurnSnapshot:
    """Capture a player's state at the start of a turn."""
    board_snaps = snapshot_board(
        [m for m in player.board if not m.dead]
    )
    from hsrl.core.enums import GameTag
    trinket_ids = [
        t.get_tag(GameTag.CARD_ID) or ""
        for t in getattr(player, "trinkets", [])
        if not t.dead
    ]
    return TurnSnapshot(
        turn=turn,
        health=player.health,
        armor=player.armor,
        tavern_tier=player.tavern_tier,
        gold=player.gold,
        board=board_snaps,
        trinkets=trinket_ids,
        hero_power_used=bool(player.get_tag(GameTag.HERO_POWER_USED, False)),
    )


class TrajectoryRecorder:
    """Records per-turn snapshots for all alive players during a game.

    Use as a context manager or call snapshot_all() at each turn start.
    """

    def __init__(self, game: "Game", seed: int = 0):
        self.game = game
        self.seed = seed
        self._snapshots: Dict[int, List[TurnSnapshot]] = {}  # player_idx → turns

    def snapshot_all(self) -> None:
        """Record current turn state for all alive players."""
        g = self.game
        for i, p in enumerate(g.players):
            if not p.is_alive:
                continue
            snap = snapshot_player(p, g.turn)
            self._snapshots.setdefault(i, []).append(snap)

    def get_trajectories(self) -> List[Trajectory]:
        """After game ends, produce one Trajectory per winning player.

        Uses the player(s) who survived longest (most snapshots). If all players
        died simultaneously, uses the one with the most snapshots / highest health.
        """
        from hsrl.core.enums import GameTag
        g = self.game
        active_tribe_names = [
            Race(t).name for t in (g.active_tribes or [])
        ]

        # Pick players with recorded snapshots
        candidates = [
            (i, g.players[i]) for i in self._snapshots
            if self._snapshots[i]  # has at least one snapshot
        ]
        if not candidates:
            return []

        # Winner = player with most snapshot entries (survived longest),
        # tie-broken by health then tier
        candidates.sort(key=lambda x: (
            len(self._snapshots[x[0]]),
            x[1].health,
            x[1].tavern_tier,
        ), reverse=True)

        results = []
        # Return trajectory for the top player (primary winner)
        idx, p = candidates[0]
        # Also include any other players who survived equally long
        max_snaps = len(self._snapshots[idx])
        for idx, p in candidates:
            if len(self._snapshots[idx]) < max_snaps:
                break
            turns = self._snapshots[idx]
            placement = 1 if idx == candidates[0][0] else len(candidates)
            traj = Trajectory(
                game_id=f"traj_{self.seed:06d}",
                hero_id=p.get_tag(GameTag.CARD_ID) or "",
                hero_name=p.get_tag(GameTag.NAME) or "",
                seed=self.seed,
                active_tribes=active_tribe_names,
                placement=placement,
                final_health=p.health,
                final_tier=p.tavern_tier,
                turns=turns,
                anomaly_id=(
                    g.active_anomaly.get_tag(GameTag.CARD_ID)
                    if g.active_anomaly and not isinstance(g.active_anomaly, bool)
                    else None
                ),
            )
            results.append(traj)
        return results


# Re-export for convenience
__all__ = [
    "TrajectoryRecorder",
    "Trajectory",
    "TurnSnapshot",
    "MinionSnapshot",
    "snapshot_board",
    "snapshot_player",
]
