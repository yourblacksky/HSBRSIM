"""
HSRL Adviser — State Mapper

Maps HDT JSON game state to the HrSRL flat observation vector (360 dims).

The mapping mirrors hsrl/env/observation.py precisely so the trained policy
receives the same input format it was trained on.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from hsrl.advisor.overlay_protocol import (
    BoardSlot,
    GameStateMessage,
    HandSlot,
    OpponentSummary,
    PlayerState,
    TavernSlot,
    TrinketSlot,
)

# ── Feature dimensions (must match observation.py) ───────────────────────

GLOBAL_DIM = 20
PLAYER_DIM = 15
TAVERN_DIM = 12
HAND_DIM = 12
BOARD_DIM = 15
TRINKET_DIM = 8

MAX_TAVERN_SLOTS = 7
MAX_HAND_SLOTS = 10
MAX_BOARD_SLOTS = 7
MAX_TRINKET_SLOTS = 2

FLAT_OBS_DIM = (
    GLOBAL_DIM
    + PLAYER_DIM
    + MAX_TAVERN_SLOTS * TAVERN_DIM
    + MAX_HAND_SLOTS * HAND_DIM
    + MAX_BOARD_SLOTS * BOARD_DIM
    + MAX_TRINKET_SLOTS * TRINKET_DIM
)

# Race name (from HDT C# RaceToString) → HSRL internal Race enum (1-12).
# Must match hsrl/core/enums.py Race values for training observation parity.
_RACE_MAP: dict[str, int] = {
    "INVALID": 0,
    "BEAST": 1,
    "DEMON": 2,
    "DRAGON": 3,
    "ELEMENTAL": 4,
    "MECH": 5,
    "MURLOC": 6,
    "NAGA": 7,
    "PIRATE": 8,
    "QUILBOAR": 9,
    "UNDEAD": 11,
    # Aliases from older HDT race strings
    "MECHANICAL": 5,
    "SCOURGE": 11,
}

# Max race enum value for normalization
_RACE_NORM = 12.0


class StateMapper:
    """Map HDT JSON game state to HrSRL flat observation vector (360,)."""

    def map(self, msg: GameStateMessage) -> np.ndarray:
        """Convert a GameStateMessage to a flat float32 observation array."""
        parts = [
            self._map_global(msg),
            self._map_player_full(msg.player, msg.hand, msg.board),
            self._map_tavern(msg.tavern),
            self._map_hand(msg.hand),
            self._map_board(msg.board),
            self._map_trinkets(msg.trinkets),
        ]
        flat = np.concatenate([p.ravel() for p in parts])
        return flat.astype(np.float32)

    def map_dict(self, data: dict) -> np.ndarray:
        """Shorthand: parse JSON dict and map in one call."""
        from hsrl.advisor.overlay_protocol import parse_game_state

        msg = parse_game_state(data)
        return self.map(msg)

    # ── Global (20,) ──────────────────────────────────────────────────────

    @staticmethod
    def _map_global(msg: GameStateMessage) -> np.ndarray:
        arr = np.zeros(GLOBAL_DIM, dtype=np.float32)

        arr[0] = min(msg.turn / 20.0, 1.0)
        arr[1] = 1.0 if msg.phase == "recruit" else 0.0
        arr[2] = msg.alive_count / 8.0

        # Compute damage cap from turn + alive_count (mirrors Game._get_damage_cap()).
        # Official BG: Turn 1-3 → 5, Turn 4-7 → 10, Turn 8+ → 15, removed at top 4.
        if msg.alive_count <= 4:
            cap = None
        elif msg.turn <= 3:
            cap = 5
        elif msg.turn <= 7:
            cap = 10
        else:
            cap = 15
        arr[3] = (cap / 15.0) if cap is not None else 0.0

        # Anomaly id hash
        if msg.anomaly_card_id:
            from hsrl.env.card_encoder import encode_card_id
            arr[4] = encode_card_id(msg.anomaly_card_id)

        # Player's rank among alive (by health)
        player_hp = msg.player.health
        if msg.alive_count > 0:
            better = sum(
                1 for o in msg.opponents
                if o.alive and o.health > player_hp
            )
            arr[5] = (better + 1) / 8.0

        return arr

    # ── Player (15,) ──────────────────────────────────────────────────────

    @staticmethod
    def _map_player(ps: PlayerState) -> np.ndarray:
        arr = np.zeros(PLAYER_DIM, dtype=np.float32)

        arr[0] = min(ps.health / 40.0, 1.0)
        arr[1] = min(ps.armor / 20.0, 1.0)
        arr[2] = min(ps.gold / 10.0, 1.0)
        arr[3] = ps.tavern_tier / 7.0
        arr[4] = min(ps.upgrade_cost / 10.0, 1.0)
        arr[5] = min(
            sum(1 for s in [ps] if s is not None) / float(MAX_HAND_SLOTS),
            1.0,
        )  # placeholder: hand size comes from GameStateMessage.hand
        arr[6] = 0.0  # placeholder: board size from GameStateMessage.board
        arr[7] = min(ps.hero_power_cost / 10.0, 1.0)
        arr[8] = 0.0 if ps.hero_power_used else 1.0
        arr[9] = float(ps.hero_power_extra_uses)
        arr[10] = ps.pending_triple_reward_tier / 7.0
        arr[11] = min(ps.free_refresh_remaining / 5.0, 1.0)
        arr[12] = min(ps.next_spell_cost_reduction / 10.0, 1.0)
        arr[13] = min(ps.blood_gem_atk_bonus / 50.0, 1.0)
        arr[14] = min(ps.blood_gem_health_bonus / 50.0, 1.0)

        return arr

    def _map_player_full(
        self, ps: PlayerState, hand: list, board: list
    ) -> np.ndarray:
        """Map player state with actual hand/board sizes from slots."""
        arr = self._map_player(ps)
        # Patch hand size from actual hand slots
        hand_count = sum(1 for s in hand if s is not None)
        arr[5] = min(hand_count / float(MAX_HAND_SLOTS), 1.0)
        # Patch board size from actual board slots
        board_count = sum(1 for s in board if s is not None)
        arr[6] = min(board_count / float(MAX_BOARD_SLOTS), 1.0)
        return arr

    # ── Tavern (7, 12) ────────────────────────────────────────────────────

    @staticmethod
    def _map_tavern(slots: list[Optional[TavernSlot]]) -> np.ndarray:
        arr = np.zeros((MAX_TAVERN_SLOTS, TAVERN_DIM), dtype=np.float32)
        for i, slot in enumerate(slots[:MAX_TAVERN_SLOTS]):
            if slot is not None:
                arr[i] = StateMapper._map_tavern_slot(slot)
        return arr

    @staticmethod
    def _map_tavern_slot(s: TavernSlot) -> np.ndarray:
        arr = np.zeros(TAVERN_DIM, dtype=np.float32)
        if s.is_minion:
            arr[0] = min(s.atk / 100.0, 1.0)
            arr[1] = min(s.health / 100.0, 1.0)
        arr[2] = s.tier / 7.0
        arr[3] = min(s.cost / 10.0, 1.0)
        arr[4] = _RACE_MAP.get(s.race, 0) / _RACE_NORM
        arr[5] = 1.0 if s.is_minion else 0.0
        arr[6] = 1.0 if s.is_spell else 0.0
        arr[7] = 1.0 if s.taunt else 0.0
        arr[8] = 1.0 if s.divine_shield else 0.0
        arr[9] = 1.0 if s.poisonous else 0.0
        arr[10] = 1.0 if s.reborn else 0.0
        arr[11] = 1.0 if s.frozen else 0.0
        return arr

    # ── Hand (10, 12) ─────────────────────────────────────────────────────

    @staticmethod
    def _map_hand(slots: list[Optional[HandSlot]]) -> np.ndarray:
        arr = np.zeros((MAX_HAND_SLOTS, HAND_DIM), dtype=np.float32)
        for i, slot in enumerate(slots[:MAX_HAND_SLOTS]):
            if slot is not None:
                arr[i] = StateMapper._map_hand_slot(slot)
        return arr

    @staticmethod
    def _map_hand_slot(s: HandSlot) -> np.ndarray:
        arr = np.zeros(HAND_DIM, dtype=np.float32)
        if s.is_minion:
            arr[0] = min(s.atk / 100.0, 1.0)
            arr[1] = min(s.health / 100.0, 1.0)
        arr[2] = s.tier / 7.0
        arr[3] = min(s.cost / 10.0, 1.0)
        arr[4] = _RACE_MAP.get(s.race, 0) / _RACE_NORM
        arr[5] = 1.0 if s.is_minion else 0.0
        arr[6] = 1.0 if s.is_spell else 0.0
        arr[7] = 1.0 if s.golden else 0.0
        arr[8] = 1.0 if s.battlecry else 0.0
        arr[9] = min(s.turns_in_hand / 5.0, 1.0)
        from hsrl.env.card_encoder import encode_card_id
        arr[10] = encode_card_id(s.card_id)
        arr[11] = 1.0 if s.spellcraft else 0.0
        return arr

    # ── Board (7, 15) ─────────────────────────────────────────────────────

    @staticmethod
    def _map_board(slots: list[Optional[BoardSlot]]) -> np.ndarray:
        arr = np.zeros((MAX_BOARD_SLOTS, BOARD_DIM), dtype=np.float32)
        for i, slot in enumerate(slots[:MAX_BOARD_SLOTS]):
            if slot is not None:
                arr[i] = StateMapper._map_board_slot(slot)
        return arr

    @staticmethod
    def _map_board_slot(s: BoardSlot) -> np.ndarray:
        arr = np.zeros(BOARD_DIM, dtype=np.float32)
        arr[0] = min(s.atk / 100.0, 1.0)
        arr[1] = min(s.health / 100.0, 1.0)
        arr[2] = min(s.max_health / 100.0, 1.0)
        arr[3] = s.tier / 7.0
        arr[4] = _RACE_MAP.get(s.race, 0) / _RACE_NORM
        arr[5] = 1.0 if s.taunt else 0.0
        arr[6] = 1.0 if s.divine_shield else 0.0
        arr[7] = 1.0 if s.poisonous else 0.0
        arr[8] = 1.0 if s.venomous else 0.0
        arr[9] = 1.0 if s.reborn else 0.0
        arr[10] = 1.0 if s.windfury else 0.0
        arr[11] = 1.0 if s.cleave else 0.0
        arr[12] = 1.0 if s.golden else 0.0
        arr[13] = 1.0 if s.exhausted else 0.0
        arr[14] = 1.0 if s.divine_shield_intact else 0.0
        return arr

    # ── Trinkets (2, 8) ───────────────────────────────────────────────────

    @staticmethod
    def _map_trinkets(slots: list[Optional[TrinketSlot]]) -> np.ndarray:
        arr = np.zeros((MAX_TRINKET_SLOTS, TRINKET_DIM), dtype=np.float32)
        for i, slot in enumerate(slots[:MAX_TRINKET_SLOTS]):
            if slot is not None:
                arr[i] = StateMapper._map_trinket_slot(slot)
        return arr

    @staticmethod
    def _map_trinket_slot(s: TrinketSlot) -> np.ndarray:
        arr = np.zeros(TRINKET_DIM, dtype=np.float32)
        arr[0] = 1.0
        arr[1] = min(s.cost / 10.0, 1.0)
        arr[2] = s.tier / 7.0
        arr[3] = 1.0 if s.has_start_of_combat else 0.0
        arr[4] = 1.0 if s.has_end_of_turn else 0.0
        arr[5] = 1.0 if s.has_start_of_turn else 0.0
        from hsrl.env.card_encoder import encode_card_id
        arr[6] = encode_card_id(s.card_id)
        return arr
