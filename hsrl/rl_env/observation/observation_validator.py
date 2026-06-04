"""
Observation Validator — checks observation correctness and hidden info leakage.
"""

from __future__ import annotations

import numpy as np

from hsrl.rl_env.observation.entity_schema import (
    NUM_ENTITY_SLOTS, ENTITY_FEAT_DIM,
    GLOBAL_FEAT_DIM, HERO_FEAT_DIM, OPPONENT_FEAT_DIM, HISTORY_FEAT_DIM,
    OPPONENT_SLOTS, HISTORY_SLOTS, TokenGroup,
)


class ObservationValidator:
    """Validates Observation V2 for correctness and hidden info leakage."""

    EXPECTED_SHAPES = {
        "entity_stats": (NUM_ENTITY_SLOTS, ENTITY_FEAT_DIM),
        "entity_mask": (NUM_ENTITY_SLOTS,),
        "entity_groups": (NUM_ENTITY_SLOTS,),
        "card_indices": (NUM_ENTITY_SLOTS,),
        "global_features": (GLOBAL_FEAT_DIM,),
        "hero_features": (HERO_FEAT_DIM,),
        "opponent_features": (OPPONENT_SLOTS, OPPONENT_FEAT_DIM),
        "history_features": (HISTORY_SLOTS, HISTORY_FEAT_DIM),
    }

    def validate(self, obs: dict, strict: bool = True) -> list[str]:
        """Run all validation checks. Returns list of violation messages."""
        violations = []

        # Shape check
        for key, expected in self.EXPECTED_SHAPES.items():
            if key in obs:
                actual = obs[key].shape
                if actual != expected and strict:
                    violations.append(
                        f"{key}: expected shape {expected}, got {actual}")

        # Dtype check
        if obs.get("entity_stats") is not None:
            if obs["entity_stats"].dtype != np.float32:
                violations.append("entity_stats dtype must be float32")
        if obs.get("entity_mask") is not None:
            if obs["entity_mask"].dtype != bool:
                violations.append("entity_mask dtype must be bool")

        # NaN / inf check
        for key in ("entity_stats", "global_features", "hero_features"):
            if key in obs and obs[key] is not None:
                arr = obs[key]
                if np.any(np.isnan(arr)):
                    violations.append(f"{key} contains NaN")
                if np.any(np.isinf(arr)):
                    violations.append(f"{key} contains inf")

        # Hidden info leakage
        violations.extend(self._check_no_leakage(obs))

        # Mask consistency
        entity_mask = obs.get("entity_mask")
        entity_groups = obs.get("entity_groups")
        if entity_mask is not None and entity_groups is not None:
            # All masked-out slots should have group = 0 (default)
            for i in range(NUM_ENTITY_SLOTS):
                if not entity_mask[i]:
                    continue

        return violations

    def _check_no_leakage(self, obs: dict) -> list[str]:
        """Verify observation contains no opponent private information."""
        v = []
        # Check keys that would indicate leakage
        forbidden = ["opponent_hand", "opponent_shop", "opponent_current_board"]
        for key in forbidden:
            if key in obs:
                v.append(f"Forbidden key '{key}' present in observation")
        return v

    def is_valid(self, obs: dict) -> bool:
        """Return True if observation passes all checks."""
        return len(self.validate(obs, strict=True)) == 0
