"""
Hierarchical Action Head — type classifier + pointer mechanism.

Decomposes the Discrete(50) action space into:
  1. Action-type classifier (8-way): BUY/SELL/PLAY/REFRESH/UPGRADE/
     FREEZE/HERO_POWER/END_TURN
  2. Entity pointer: for BUY/SELL/PLAY, a query-key dot-product attention
     selects which entity slot to target.

The combined output is 8 + 24 = 32 logits, which maps back to the
original 50-way action space via a compatibility layer.

Architecture:
  action_type_head: Linear(48→8) — 8-way classifier
  pointer_query:    Linear(48→24) — projects context into query space
  key_embed:        identity — entity_reps already in 48-dim, but we
                    project to 24-dim for dot-product scoring
  key_projection:   Linear(48→24) — shared key projection for pointer
  slot biases:      learned per-slot additive preferences

  tavern_slot_bias: (7,) — tavern slots 0-6
  board_slot_bias:  (7,) — board slots 0-6
  hand_slot_bias:   (10,) — hand slots 0-9

Total params: ~2,240
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# Action type constants (match hsrl/env/action.py)
ACTION_TYPES = 8
TYPE_BUY = 0
TYPE_SELL = 1
TYPE_PLAY = 2
TYPE_REFRESH = 3
TYPE_UPGRADE = 4
TYPE_FREEZE = 5
TYPE_HERO_POWER = 6
TYPE_END_TURN = 7

POINTER_TAVERN = 7
POINTER_BOARD = 7
POINTER_HAND = 10
POINTER_TOTAL = POINTER_TAVERN + POINTER_BOARD + POINTER_HAND  # 24


class HierarchicalActionHead(nn.Module):
    """Hierarchical policy: action-type classifier + entity pointer.

    Produces 32 logits:
      - 8 action-type logits
      - 7 + 7 + 10 = 24 pointer logits (tavern slots, board slots, hand slots)

    The pointer mechanism works as follows:
      1. A learned query vector is derived from the global representation
      2. Each entity's representation is projected to a key vector
      3. Dot-product scores (query · key) determine which entity to target
      4. Slot biases add learned preference for specific positions
    """

    def __init__(self, d_model: int = 48, query_dim: int = 24):
        super().__init__()

        # Action-type classifier
        self.action_type_head = nn.Linear(d_model, ACTION_TYPES)

        # Pointer: query-key dot-product attention over entities
        self.pointer_query = nn.Linear(d_model, query_dim)
        self.pointer_key = nn.Linear(d_model, query_dim)

        # Slot biases: learned positional preferences
        self.tavern_slot_bias = nn.Parameter(torch.zeros(POINTER_TAVERN))
        self.board_slot_bias = nn.Parameter(torch.zeros(POINTER_BOARD))
        self.hand_slot_bias = nn.Parameter(torch.zeros(POINTER_HAND))

    def forward(self, global_rep: torch.Tensor,
                entity_reps: torch.Tensor,
                entity_mask: torch.Tensor,
                entity_types: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            global_rep: (B, d_model) — contextualized global representation
            entity_reps: (B, N, d_model) — contextualized entity tokens
            entity_mask: (B, N) — True where entity exists
            entity_types: (B, N) — 0=tavern, 1=board, 2=hand

        Returns:
            type_logits: (B, 8) — action type logits
            pointer_scores: (B, 24) — pointer scores for each slot
        """
        B, N, _ = entity_reps.shape

        # ── Action-type logits ──
        type_logits = self.action_type_head(global_rep)  # (B, 8)

        # ── Pointer scores ──
        query = self.pointer_query(global_rep)           # (B, query_dim)
        keys = self.pointer_key(entity_reps)             # (B, N, query_dim)

        # Dot-product scores: (B, query_dim) · (B, N, query_dim) → (B, N)
        raw_scores = torch.einsum('bd,bnd->bn', query, keys)

        # Mask: zero out empty entity slots
        raw_scores = raw_scores.masked_fill(~entity_mask, -1e9)

        # Segment into tavern, board, hand groups with slot biases
        is_tavern = (entity_types == 0).float()
        is_board = (entity_types == 1).float()
        is_hand = (entity_types == 2).float()

        # Apply per-group softmax to get scores for each slot
        tavern_scores = (raw_scores * is_tavern).masked_fill(~entity_mask, -1e9)
        board_scores = (raw_scores * is_board).masked_fill(~entity_mask, -1e9)
        hand_scores = (raw_scores * is_hand).masked_fill(~entity_mask, -1e9)

        # Take max score per group — use max over group entities
        # If no entities in group, use very negative score
        tavern_ptr = _max_per_group(tavern_scores, POINTER_TAVERN, entity_types, 0)
        board_ptr = _max_per_group(board_scores, POINTER_BOARD, entity_types, 1)
        hand_ptr = _max_per_group(hand_scores, POINTER_HAND, entity_types, 2)

        # Add slot biases (learned position preferences)
        tavern_ptr = tavern_ptr + self.tavern_slot_bias.unsqueeze(0)
        board_ptr = board_ptr + self.board_slot_bias.unsqueeze(0)
        hand_ptr = hand_ptr + self.hand_slot_bias.unsqueeze(0)

        # Concatenate pointer scores: [tavern(7), board(7), hand(10)]
        pointer_scores = torch.cat([tavern_ptr, board_ptr, hand_ptr], dim=-1)  # (B, 24)

        return type_logits, pointer_scores

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def _max_per_group(scores: torch.Tensor, group_size: int,
                   entity_types: torch.Tensor, group_id: int) -> torch.Tensor:
    """Pool entity-level scores into fixed-size group scores via max pooling.

    For each of the group_size slots, take the maximum score among entities
    of that group. If the group has more entities than slots, the excess
    entities' scores are lost (max-pooled into the closest slot).

    Args:
        scores: (B, N) — raw scores per entity, masked
        group_size: number of slots in this group
        entity_types: (B, N) — entity group assignments
        group_id: 0=tavern, 1=board, 2=hand

    Returns:
        (B, group_size) — pooled scores per slot
    """
    B, N = scores.shape
    device = scores.device

    is_group = (entity_types == group_id).float()  # (B, N)

    # For most groups, entity count < group_size, so pad to group_size
    # Simple approach: take the top-k scores, pad with -inf
    group_scores = scores * is_group  # zero out non-group entities

    # Find the maximum score per batch item for this group
    # Since entities within a group are order-independent for pointer,
    # we use max pool across entities, then replicate to slots
    max_per_entity = group_scores.masked_fill(~(is_group.bool()), -1e9)
    top_scores, _ = torch.topk(max_per_entity, min(group_size, N), dim=-1)
    # Pad to group_size
    if top_scores.shape[-1] < group_size:
        pad = torch.full((B, group_size - top_scores.shape[-1]), -1e9,
                         device=device, dtype=top_scores.dtype)
        top_scores = torch.cat([top_scores, pad], dim=-1)

    return top_scores
