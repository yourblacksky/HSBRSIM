"""
EntityTokenizerV2 — 37-slot tokenizer for Observation V2.

Handles the extended entity layout with separate TokenGroup regions:
  GLOBAL(1) + HERO(1) + TAVERN(7) + BOARD(7) + HAND(10)
  + OPPONENT(7) + HISTORY(4) = 37 slots

Summary tokens (global, hero, opponent, history) use group-specific
encoders. Competitor tokens (tavern, board, hand) use per-entity
card embeddings + stat projections like V1.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import Optional

from hsrl.rl_env.observation.entity_schema import (
    NUM_ENTITY_SLOTS, ENTITY_FEAT_DIM,
    GLOBAL_FEAT_DIM, HERO_FEAT_DIM, OPPONENT_FEAT_DIM, HISTORY_FEAT_DIM,
    OPPONENT_SLOTS, HISTORY_SLOTS,
    TAVERN_OFFSET, BOARD_OFFSET, HAND_OFFSET, OPPONENT_OFFSET, HISTORY_OFFSET,
    TAVERN_SLOTS, BOARD_SLOTS, HAND_SLOTS,
    TokenGroup, EntityTokenLayout,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CardIndexer — deterministic card_id → int mapping
# ═══════════════════════════════════════════════════════════════════════════════

class CardIndexer:
    """Deterministic sorted card_id → integer index. Index 0 = UNKNOWN/PADDING."""

    def __init__(self):
        self._map: dict[str, int] = {}
        self._size: int = 0
        self._built: bool = False

    def build(self) -> None:
        from hsrl.core.card_db import CARDS
        self._map.clear()
        for idx, card_id in enumerate(sorted(CARDS.all_ids()), start=1):
            self._map[card_id] = idx
        self._size = len(self._map) + 1
        self._built = True

    def encode(self, card_id: str) -> int:
        if not self._built: self.build()
        return self._map.get(card_id, 0)

    def __len__(self) -> int:
        if not self._built: self.build()
        return self._size


_indexer: Optional[CardIndexer] = None


def get_card_indexer() -> CardIndexer:
    global _indexer
    if _indexer is None:
        _indexer = CardIndexer()
        _indexer.build()
    return _indexer


# ═══════════════════════════════════════════════════════════════════════════════
# EntityTokenizerV2 — 37-slot tokenizer
# ═══════════════════════════════════════════════════════════════════════════════

NUM_CARD_VOCAB = 1500
EMBED_DIM = 24


class EntityTokenizerV2(nn.Module):
    """37-slot tokenizer for Observation V2.

    Summary tokens (global, hero, opponent, history) use dedicated
    feature projectors. Competitor tokens (tavern, board, hand) use
    card embeddings + entity feature MLP like V1.
    """

    def __init__(self):
        super().__init__()

        # Card embedding (shared across tavern/board/hand)
        self.card_embedding = nn.Embedding(NUM_CARD_VOCAB, EMBED_DIM, padding_idx=0)

        # Per-entity feature MLP (8-dim stats → 24-dim)
        self.entity_mlp = nn.Sequential(
            nn.Linear(ENTITY_FEAT_DIM, 16),
            nn.ReLU(),
            nn.Linear(16, EMBED_DIM),
        )

        # Summary token projectors
        self.global_proj = nn.Sequential(
            nn.Linear(GLOBAL_FEAT_DIM, EMBED_DIM), nn.ReLU())
        self.hero_proj = nn.Sequential(
            nn.Linear(HERO_FEAT_DIM, EMBED_DIM), nn.ReLU())
        self.opponent_proj = nn.Sequential(
            nn.Linear(OPPONENT_FEAT_DIM, EMBED_DIM), nn.ReLU())
        self.history_proj = nn.Sequential(
            nn.Linear(HISTORY_FEAT_DIM, EMBED_DIM), nn.ReLU())

    def forward(self, batch: dict) -> tuple[torch.Tensor, torch.Tensor]:
        """Build entity tokens from Observation V2 batch.

        Args:
            batch: dict with keys from build_observation_v2():
              entity_stats:     (B, 37, 8)
              entity_mask:      (B, 37)
              entity_groups:    (B, 37) int
              card_indices:     (B, 37) int
              global_features:  (B, 16)
              hero_features:    (B, 12)
              opponent_features:(B, 7, 12)
              history_features: (B, 4, 8)

        Returns:
            entity_tokens: (B, 37, 24)
            entity_mask:   (B, 37) — pass-through
        """
        B = batch["entity_stats"].shape[0]
        entity_tokens = torch.zeros(B, NUM_ENTITY_SLOTS, EMBED_DIM,
                                    device=batch["entity_stats"].device)

        # ── Global token (slot 0) ──
        entity_tokens[:, 0, :] = self.global_proj(batch["global_features"])

        # ── Hero token (slot 1) ──
        entity_tokens[:, 1, :] = self.hero_proj(batch["hero_features"])

        # ── Competitor entities (tavern, board, hand) ──
        competitor_slots = list(range(TAVERN_OFFSET, HAND_OFFSET + HAND_SLOTS))
        for slot in competitor_slots:
            if slot >= NUM_ENTITY_SLOTS: break
            stats = batch["entity_stats"][:, slot, :]       # (B, 8)
            card_idx = batch["card_indices"][:, slot]       # (B,)
            ce = self.card_embedding(card_idx)              # (B, 24)
            se = self.entity_mlp(stats)                      # (B, 24)
            entity_tokens[:, slot, :] = ce + se

        # ── Opponent tokens (slots 26-32) ──
        for i in range(OPPONENT_SLOTS):
            slot = OPPONENT_OFFSET + i
            if slot >= NUM_ENTITY_SLOTS: break
            entity_tokens[:, slot, :] = self.opponent_proj(
                batch["opponent_features"][:, i, :])

        # ── History tokens (slots 33-36) ──
        for i in range(HISTORY_SLOTS):
            slot = HISTORY_OFFSET + i
            if slot >= NUM_ENTITY_SLOTS: break
            entity_tokens[:, slot, :] = self.history_proj(
                batch["history_features"][:, i, :])

        return entity_tokens, batch["entity_mask"]

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
