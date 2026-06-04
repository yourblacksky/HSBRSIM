"""
Distributional Value Head — placement distribution prediction.

Predicts P(placement = k) for k = 1..8 using the entity-level encoded state.
The value V(s) = -expected_placement(s), negated so that higher is better
for GAE advantage computation.

Architecture:
  entity_reps(N, 48) → mean_pool + max_pool → (96,)
  concat(global_rep(48), pooled(96)) → (144,)
  → Linear(144→48) → ReLU
  → Linear(48→24) → ReLU
  → Linear(24→8)  → ReLU
  → Linear(8→8)   → placement_logits (softmax over ranks 1-8)
  → expected_placement = sum(k * P(k))
  → value = -expected_placement

Total params: ~9,500
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_PLACEMENTS = 8  # ranks 1-8


class DistributionalValueHead(nn.Module):
    """Predicts P(placement=k) for k=1..8, returns scalar value for GAE."""

    def __init__(self, d_model: int = 48):
        super().__init__()

        # Combiner: global_rep(48) + pooled_entities(96) = 144 → 48
        self.combiner = nn.Sequential(
            nn.Linear(d_model * 3, d_model),  # 3*48 = 144: global + mean + max
            nn.ReLU(),
        )

        # Value trunk
        self.trunk = nn.Sequential(
            nn.Linear(d_model, 24),
            nn.ReLU(),
            nn.Linear(24, 8),
            nn.ReLU(),
        )

        # Placement distribution: 8-way logits over ranks 1-8
        self.placement_head = nn.Linear(8, NUM_PLACEMENTS)

        # Pre-computed rank tensor for expected value
        self.register_buffer(
            'ranks',
            torch.arange(1, NUM_PLACEMENTS + 1, dtype=torch.float32),
            persistent=False,
        )

    def forward(self, global_rep: torch.Tensor,
                entity_reps: torch.Tensor,
                entity_mask: torch.Tensor) -> dict:
        """Forward pass.

        Args:
            global_rep: (B, d_model) — contextualized global representation
            entity_reps: (B, N, d_model) — contextualized entity tokens
            entity_mask: (B, N) — True where entity exists

        Returns:
            placement_logits: (B, 8) — raw logits over ranks 1-8
            placement_probs:  (B, 8) — softmax probabilities
            expected_placement: (B,) — E[rank] ∈ [1, 8]
            value: (B,) — -expected_placement (higher = better)
        """
        # Pool entity tokens: mean and max over non-masked entities
        mask_expanded = entity_mask.unsqueeze(-1).float()  # (B, N, 1)
        masked_reps = entity_reps * mask_expanded

        # Mean pool (masked)
        entity_count = entity_mask.float().sum(dim=-1, keepdim=True).clamp(min=1)
        entity_mean = masked_reps.sum(dim=1) / entity_count  # (B, d)

        # Max pool (masked)
        entity_max = masked_reps.masked_fill(~entity_mask.unsqueeze(-1), -1e9)
        entity_max = entity_max.max(dim=1).values  # (B, d)

        # Combine
        pooled = torch.cat([global_rep, entity_mean, entity_max], dim=-1)  # (B, 3d)
        h = self.combiner(pooled)
        h = self.trunk(h)

        placement_logits = self.placement_head(h)  # (B, 8)
        placement_probs = F.softmax(placement_logits, dim=-1)

        expected_placement = (placement_probs * self.ranks).sum(dim=-1)
        value = -expected_placement  # negate: rank 1 = best = highest value

        return {
            "placement_logits": placement_logits,
            "placement_probs": placement_probs,
            "expected_placement": expected_placement,
            "value": value,
        }

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
