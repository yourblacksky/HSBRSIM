"""
OpponentPublicEncoder — encodes opponent information using ONLY public data.

Rules:
  - CAN read: opponent.health, opponent.armor, opponent.tavern_tier,
             opponent.board (as public last_seen_board),
             opponent.last_combat_result (from combat log)
  - CANNOT read: opponent.hand, opponent.tavern (current shop),
                opponent.unseen board mutations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hsrl.rl_env.observation.entity_schema import OPPONENT_SLOTS, OPPONENT_FEAT_DIM

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


class OpponentPublicEncoder:
    """Encode each opponent using only publicly visible information.

    For each opponent, produces a 12-dim summary vector:
      [hp/40, armor/20, tier/7, board_size/7, board_strength/100,
       last_seen_turn/20, last_combat_result, is_alive,
       triple_hint, tribe_hint, damage_dealt_avg/15, turns_since_fought/20]
    """

    def __init__(self):
        self.feat_dim = OPPONENT_FEAT_DIM

    def encode_all(
        self, game: "Game", current_player: "Player",
    ) -> np.ndarray:
        """Encode all 7 opponents as (OPPONENT_SLOTS, OPPONENT_FEAT_DIM).

        Opponents are ordered by player index, with current_player's slot
        zeroed out (since you don't play against yourself).
        """
        result = np.zeros((OPPONENT_SLOTS, OPPONENT_FEAT_DIM), dtype=np.float32)
        opponent_idx = 0

        for idx, p in enumerate(game.players):
            if p is current_player or opponent_idx >= OPPONENT_SLOTS:
                continue
            result[opponent_idx] = self._encode_one(game, p)
            opponent_idx += 1

        return result

    def _encode_one(self, game: "Game", player: "Player") -> np.ndarray:
        """Encode a single opponent from public info."""
        arr = np.zeros(OPPONENT_FEAT_DIM, dtype=np.float32)

        # Public basic stats
        arr[0] = min(player.health / 40.0, 1.0)
        arr[1] = min(player.armor / 20.0, 1.0)
        arr[2] = player.tavern_tier / 7.0

        # Board info (public: board is visible at combat time)
        living = [m for m in player.board if not m.dead]
        arr[3] = min(len(living) / 7.0, 1.0)
        # Board strength: sum of atk+health as proxy
        board_str = sum(m.atk + m.health for m in living)
        arr[4] = min(board_str / 100.0, 1.0)

        # Last seen info (from combat memory if available)
        arr[5] = 0.0  # last_seen_turn placeholder
        arr[6] = 0.0  # last_combat_result: +1=win, 0=tie, -1=loss
        arr[7] = 1.0 if player.is_alive else 0.0

        # Tribe hint: majority tribe on board (public info)
        tribe_counts = {}
        for m in living:
            r = m.race
            if r and r.name not in ("NONE", "ALL"):
                tribe_counts[r.name] = tribe_counts.get(r.name, 0) + 1
        if tribe_counts:
            majority_tribe = max(tribe_counts, key=tribe_counts.get)
            # Simple hash of tribe name to [0,1]
            arr[8] = hash(majority_tribe) % 100 / 100.0

        # Combat history placeholders
        arr[9] = 0.0   # damage_dealt_avg / 15
        arr[10] = 0.0  # turns_since_fought / 20
        arr[11] = 0.0  # win_streak hint

        return arr


# ═══════════════════════════════════════════════════════════════════════════════
# Hidden information validator
# ═══════════════════════════════════════════════════════════════════════════════

class HiddenInfoValidator:
    """Validates that observation does not leak opponent private information."""

    @staticmethod
    def check_no_hand_leakage(obs: dict) -> list[str]:
        """Verify observation contains no opponent hand data."""
        violations = []
        if "opponent_hand" in obs:
            violations.append("opponent_hand present in observation")
        if "opponent_current_shop" in obs:
            violations.append("opponent_current_shop present in observation")
        return violations

    @staticmethod
    def check_zone_consistency(obs: dict, expected_zones: set) -> list[str]:
        """Verify all entity tokens have valid zone assignments."""
        violations = []
        entity_types = obs.get("entity_types")
        if entity_types is not None:
            unique_zones = set(entity_types.flatten().tolist())
            for z in unique_zones:
                if z not in expected_zones and z != 0:
                    violations.append(f"unknown zone type: {z}")
        return violations

    @staticmethod
    def check_shape(obs: dict, expected_shapes: dict) -> list[str]:
        """Verify observation tensors have expected shapes."""
        violations = []
        for key, expected in expected_shapes.items():
            if key in obs:
                actual = obs[key].shape
                if actual != expected:
                    violations.append(
                        f"{key}: expected shape {expected}, got {actual}")
        return violations
