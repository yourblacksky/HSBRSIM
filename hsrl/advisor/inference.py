"""
HSRL Adviser — Model Inference

Loads a trained MaskablePPO model and provides action suggestions for
a given observation and action mask.
"""

from __future__ import annotations

import numpy as np
import torch

from hsrl.advisor.state_mapper import BOARD_DIM, MAX_BOARD_SLOTS
from hsrl.advisor.action_constants import get_action_name, NUM_ACTIONS

# Board section offset in the flat observation vector
_BOARD_OFFSET = 239  # GLOBAL(20) + PLAYER(15) + TAVERN(84) + HAND(120)


class ModelInference:
    """Load and run inference with a trained MaskablePPO policy.

    Args:
        model_path: Path to a .zip checkpoint saved by sb3 MaskablePPO.
        device: Torch device (auto-detected if None).
    """

    def __init__(self, model_path: str, device: str | None = None):
        from sb3_contrib import MaskablePPO

        self.model = MaskablePPO.load(model_path)
        self.policy = self.model.policy

        if device is None:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device

        self.policy.to(self._device)
        self.policy.set_training_mode(False)

    @property
    def device(self) -> str:
        return self._device

    def predict(
        self,
        obs: np.ndarray,
        action_mask: np.ndarray | None = None,
        top_k: int = 5,
    ) -> tuple[int, list[tuple[int, str, float]], float]:
        """Return the best action, top-K suggestions, and state value.

        Args:
            obs: Flat observation vector (360,) float32.
            action_mask: Boolean mask (NUM_ACTIONS,) of valid actions.
            top_k: Number of top suggestions to return.

        Returns:
            (best_action, [(action, name, probability), ...], value_estimate)
        """
        obs_tensor = torch.as_tensor(obs, dtype=torch.float32, device=self._device)
        if obs_tensor.ndim == 1:
            obs_tensor = obs_tensor.unsqueeze(0)

        if action_mask is None:
            action_mask = np.ones(NUM_ACTIONS, dtype=bool)

        mask_tensor = torch.as_tensor(action_mask, dtype=torch.bool, device=self._device)
        if mask_tensor.ndim == 1:
            mask_tensor = mask_tensor.unsqueeze(0)

        with torch.no_grad():
            # Get action distribution
            dist = self.policy.get_distribution(obs_tensor)
            logits = dist.distribution.logits

            # Apply action mask (set invalid actions to -inf)
            masked_logits = logits.clone()
            masked_logits[~mask_tensor] = float("-inf")

            # Get probs from masked logits
            probs = torch.nn.functional.softmax(masked_logits, dim=-1)
            best_action = int(probs.argmax(dim=-1).item())
            value = float(self.policy.predict_values(obs_tensor).item())

        # Top-K
        probs_np = probs.cpu().numpy().flatten()
        top_indices = np.argsort(-probs_np)[:top_k]
        suggestions = []
        for idx in top_indices:
            prob = float(probs_np[idx])
            if prob <= 0.0:
                break
            suggestions.append((int(idx), get_action_name(idx), prob))

        return best_action, suggestions, value

    def predict_batch(
        self,
        obs_batch: np.ndarray,
        action_masks: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Batch inference for multiple observations.

        Returns:
            (best_actions: np.ndarray (N,), values: np.ndarray (N,))
        """
        obs_tensor = torch.as_tensor(obs_batch, dtype=torch.float32, device=self._device)
        if action_masks is None:
            action_masks = np.ones((obs_batch.shape[0], NUM_ACTIONS), dtype=bool)

        mask_tensor = torch.as_tensor(action_masks, dtype=torch.bool, device=self._device)

        with torch.no_grad():
            dist = self.policy.get_distribution(obs_tensor)
            logits = dist.distribution.logits

            masked_logits = logits.clone()
            masked_logits[~mask_tensor] = float("-inf")

            best_actions = masked_logits.argmax(dim=-1).cpu().numpy()
            values = self.policy.predict_values(obs_tensor).squeeze(-1).cpu().numpy()

        return best_actions, values

    # ── Board arrangement ─────────────────────────────────────────────────

    def _value(self, obs: np.ndarray) -> float:
        """Compute scalar state-value for a single observation."""
        t = torch.as_tensor(obs, dtype=torch.float32, device=self._device)
        if t.ndim == 1:
            t = t.unsqueeze(0)
        with torch.no_grad():
            return float(self.policy.predict_values(t).item())

    @staticmethod
    def _find_occupied_slots(obs: np.ndarray) -> list[int]:
        """Return list of board slot indices that contain a minion."""
        occupied = []
        for i in range(MAX_BOARD_SLOTS):
            start = _BOARD_OFFSET + i * BOARD_DIM
            # Slot is occupied if atk>0, health>0, or tier>0
            if obs[start] > 0 or obs[start + 1] > 0 or obs[start + 3] > 0:
                occupied.append(i)
        return occupied

    @staticmethod
    def _swap_board_slots(obs: np.ndarray, i: int, j: int) -> np.ndarray:
        """Return a new observation with board slots i and j swapped."""
        new = obs.copy()
        si, sj = _BOARD_OFFSET + i * BOARD_DIM, _BOARD_OFFSET + j * BOARD_DIM
        new[si:si + BOARD_DIM], new[sj:sj + BOARD_DIM] = (
            obs[sj:sj + BOARD_DIM].copy(),
            obs[si:si + BOARD_DIM].copy(),
        )
        return new

    def suggest_arrangement(
        self,
        obs: np.ndarray,
        max_iterations: int = 10,
    ) -> tuple[list[int], float, float]:
        """Suggest an optimal board arrangement via pairwise-swap hill-climbing.

        Uses the model's value function to evaluate different board layouts.
        Tries all pairwise swaps of occupied slots, greedily picks the best
        value-improving swap, and repeats until convergence.

        Args:
            obs: Flat observation vector (360,) float32.
            max_iterations: Maximum hill-climbing iterations.

        Returns:
            (suggested_order, value_before, value_after)

            suggested_order[i] = the original board slot index that should
            occupy position i after rearrangement.
        """
        occupied = self._find_occupied_slots(obs)
        n = len(occupied)

        if n <= 1:
            return list(occupied), 0.0, 0.0

        current_obs = obs.copy()
        value_before = self._value(current_obs)
        best_value = value_before

        # Map: position in occupied list → original board slot index
        current_order = list(occupied)

        for _ in range(max_iterations):
            improved = False
            best_swap = None

            for a in range(n):
                for b in range(a + 1, n):
                    sa, sb = current_order[a], current_order[b]
                    candidate = self._swap_board_slots(current_obs, sa, sb)
                    val = self._value(candidate)
                    if val > best_value:
                        best_value = val
                        best_swap = (a, b)
                        improved = True

            if not improved or best_swap is None:
                break

            a, b = best_swap
            sa, sb = current_order[a], current_order[b]
            current_obs = self._swap_board_slots(current_obs, sa, sb)
            current_order[a], current_order[b] = current_order[b], current_order[a]

        return current_order, value_before, best_value
