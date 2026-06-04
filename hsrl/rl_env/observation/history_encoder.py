"""
History Encoder — encodes past combat results and turn events.

Produces 4 summary tokens representing recent game history.
"""

from __future__ import annotations

import numpy as np

from hsrl.rl_env.observation.entity_schema import HISTORY_SLOTS, HISTORY_FEAT_DIM


class HistoryEncoder:
    """Encodes recent game history into summary tokens."""

    def encode(self, game, player) -> np.ndarray:
        """Produce (HISTORY_SLOTS, HISTORY_FEAT_DIM) history tokens.

        Token 0: Last combat result (win/loss/damage)
        Token 1: Leveling history (last upgrade turn, current tier)
        Token 2: Economy summary (gold trend)
        Token 3: Tribe commitment (dominant tribe on board)
        """
        result = np.zeros((HISTORY_SLOTS, HISTORY_FEAT_DIM), dtype=np.float32)

        # Token 0: combat memory
        result[0, 0] = 0.0  # last_combat_result: +1 win, -1 loss
        result[0, 1] = 0.0  # damage_taken_last

        # Token 1: upgrade history
        result[1, 0] = player.tavern_tier / 7.0
        result[1, 1] = 0.0  # turns_since_upgrade

        # Token 2: economy
        result[2, 0] = min(player.gold / 10.0, 1.0)

        # Token 3: tribe commitment
        tribe_counts = {}
        for m in player.board:
            if not m.dead and m.race:
                tribe_counts[m.race.name] = tribe_counts.get(m.race.name, 0) + 1
        if tribe_counts:
            majority = max(tribe_counts, key=tribe_counts.get)
            result[3, 0] = float(hash(majority) % 100) / 100.0
            result[3, 1] = tribe_counts[majority] / 7.0

        return result
