"""
Trajectory Opponent Loader

Loads a winner trajectory and provides board snapshots by turn.
Trajectory opponents are frozen combat opponents — their boards are
injected at the start of each turn and combat runs normally with all
triggers (Deathrattle, Reborn, Divine Shield, etc.).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from hsrl.trajectory.record import Trajectory, TurnSnapshot, MinionSnapshot

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.minion import Minion
    from hsrl.core.player import Player


class TrajectoryOpponent:
    """Loads a winner trajectory and provides board snapshots by turn.

    Usage:
        opponent = TrajectoryOpponent("data/trajectories/traj_000042.json")
        opponent.apply_to_player(player, game, turn=3)
        # player.board now has minions matching the trajectory's turn-3 state
    """

    def __init__(self, trajectory_path: str):
        with open(trajectory_path) as f:
            data = json.load(f)
        self.data = data
        self.game_id: str = data["game_id"]
        self.hero_id: str = data.get("hero_id", "")
        self.hero_name: str = data.get("hero_name", "")
        self.active_tribes: List[str] = data.get("active_tribes", [])

        # Build turn lookup: turn_number → TurnSnapshot
        self.turns: Dict[int, dict] = {}
        for t in data.get("turns", []):
            self.turns[t["turn"]] = t

    def get_board_snapshot(self, turn: int) -> Optional[dict]:
        """Return the raw turn dict for a given turn number."""
        return self.turns.get(turn)

    def get_snapshot(self, turn: int) -> Optional[TurnSnapshot]:
        """Return a parsed TurnSnapshot for a given turn number."""
        raw = self.turns.get(turn)
        if raw is None:
            return None
        return TurnSnapshot.from_dict(raw)

    def apply_to_player(self, player: "Player", game: "Game", turn: int) -> bool:
        """Inject the trajectory's board state into a Player at the given turn.

        Creates Minion objects from the snapshot, sets their stats and
        keywords, and places them on the player's board. The player's
        health, tier, and trinkets are also synced.

        Returns True if injection succeeded, False if no snapshot for turn.
        """
        snap = self.get_snapshot(turn)
        if snap is None:
            return False

        # Clear existing board
        player.board.clear()
        player.hand.clear()
        player.graveyard.clear()

        # Set player state
        player.health = snap.health
        player.armor = snap.armor
        player.tavern_tier = snap.tavern_tier
        player.gold = 0  # Frozen opponents don't buy

        # Rebuild board from snapshot
        for ms in snap.board:
            minion = self._create_minion_from_snapshot(ms, player, game)
            player.board.append(minion)

        return True

    def apply_minimal(self, player: "Player", game: "Game", turn: int) -> bool:
        """Like apply_to_player but only sets board — doesn't touch health/armor."""
        snap = self.get_snapshot(turn)
        if snap is None:
            return False

        player.board.clear()
        player.hand.clear()

        for ms in snap.board:
            minion = self._create_minion_from_snapshot(ms, player, game)
            player.board.append(minion)

        return True

    def _create_minion_from_snapshot(
        self,
        ms: MinionSnapshot,
        player: "Player",
        game: "Game",
    ) -> "Minion":
        """Create a Minion from a MinionSnapshot, setting all keywords."""
        from hsrl.core.enums import GameTag, Zone

        minion = game.create_minion(ms.card_id)
        if minion is None:
            raise ValueError(f"Failed to create minion: {ms.card_id}")
        minion.controller = player
        minion.zone = Zone.PLAY

        # Set stats
        minion.atk = ms.atk
        minion.health = ms.health
        minion.set_tag(GameTag.HEALTH, ms.health)
        max_health_tag = getattr(GameTag, 'MAX_HEALTH', None)
        if max_health_tag:
            minion.set_tag(max_health_tag, ms.max_health)

        # Set keywords via BaseEntity tag system
        if ms.taunt:
            minion.set_tag(GameTag.TAUNT, True)
        if ms.divine_shield:
            minion.set_tag(GameTag.DIVINE_SHIELD, True)
            minion.set_tag(GameTag.DIVINE_SHIELD_INTACT, True)
        if ms.poisonous:
            minion.set_tag(GameTag.POISONOUS, True)
        if ms.venomous:
            venomous_tag = getattr(GameTag, 'VENOMOUS', None)
            if venomous_tag:
                minion.set_tag(venomous_tag, True)
        if ms.reborn:
            minion.set_tag(GameTag.REBORN, True)
            minion.set_tag(GameTag.REBORN_USED, False)
        if ms.windfury:
            minion.set_tag(GameTag.WINDFURY, True)
        if ms.cleave:
            cleave_tag = getattr(GameTag, 'CLEAVE', None)
            if cleave_tag:
                minion.set_tag(cleave_tag, True)
        if ms.is_golden:
            golden_tag = getattr(GameTag, 'IS_GOLDEN', None) or getattr(GameTag, 'GOLDEN', None)
            if golden_tag:
                minion.set_tag(golden_tag, True)

        return minion

    def __repr__(self) -> str:
        return (f"<TrajectoryOpponent {self.game_id} hero={self.hero_name} "
                f"turns={len(self.turns)} tribes={self.active_tribes}>")
