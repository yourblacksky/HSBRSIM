"""
5.25M Parameter Model — Scaled Entity-Token Transformer.

Architecture:
  embed_dim=128, d_model=256, n_heads=4, n_layers=6, d_ff=1024
  Card embedding: 1500 × 128 = 192K
  Transformer: 6 layers × ~800K = 4.7M
  Total: ~5.25M params

Usage:
    model = ScaledModel()
    tokens, mask = model.tokenizer(obs_batch)
    entity_reps, global_rep = model.transformer(tokens, mask, ctx)
    value = model.value_head(global_rep, entity_reps, mask)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from hsrl.policy.transformer import EntityTransformer
from hsrl.policy.heads import HierarchicalActionHead
from hsrl.policy.value_head import DistributionalValueHead
from hsrl.rl_env.observation.entity_schema import NUM_ENTITY_SLOTS

EMBED_DIM = 128
D_MODEL = 256
N_HEADS = 4
N_LAYERS = 6
D_FF = 1024
CARD_VOCAB = 1500


class ScaledTokenizer(nn.Module):
    """37-slot tokenizer with 128-dim embeddings."""

    def __init__(self):
        super().__init__()
        self.card_emb = nn.Embedding(CARD_VOCAB, EMBED_DIM, padding_idx=0)
        self.entity_mlp = nn.Sequential(
            nn.Linear(8, 64), nn.ReLU(), nn.Linear(64, EMBED_DIM))
        self.global_proj = nn.Sequential(nn.Linear(16, EMBED_DIM), nn.ReLU())
        self.hero_proj = nn.Sequential(nn.Linear(12, EMBED_DIM), nn.ReLU())
        self.opp_proj = nn.Sequential(nn.Linear(12, EMBED_DIM), nn.ReLU())
        self.hist_proj = nn.Sequential(nn.Linear(8, EMBED_DIM), nn.ReLU())

    def forward(self, batch):
        B = batch['entity_stats'].shape[0]
        N = NUM_ENTITY_SLOTS
        t = torch.zeros(B, N, EMBED_DIM, device=batch['entity_stats'].device)

        # Summary tokens
        t[:, 0, :] = self.global_proj(batch['global_features'])
        t[:, 1, :] = self.hero_proj(batch['hero_features'])

        # Competitor entities (tavern 2-8, board 9-15, hand 16-25)
        ci = batch['card_indices'].clamp(0, CARD_VOCAB - 1)
        for s in range(2, min(26, N)):
            t[:, s, :] = self.card_emb(ci[:, s]) + self.entity_mlp(batch['entity_stats'][:, s, :])

        # Opponent summaries
        for i in range(min(7, N - 26)):
            t[:, 26 + i, :] = self.opp_proj(batch['opponent_features'][:, i, :])

        # History tokens
        for i in range(min(4, N - 33)):
            t[:, 33 + i, :] = self.hist_proj(batch['history_features'][:, i, :])

        # Return slot 1..36 (skip global slot 0) for transformer
        return t[:, 1:, :], batch['entity_mask'][:, 1:]


class ScaledModel(nn.Module):
    """5.25M parameter entity-token Transformer for Battlegrounds."""

    def __init__(self):
        super().__init__()
        self.tokenizer = ScaledTokenizer()
        self.transformer = EntityTransformer(D_MODEL, N_HEADS, N_LAYERS, D_FF)
        self.transformer.input_proj = nn.Linear(EMBED_DIM, D_MODEL)
        self.action_head = HierarchicalActionHead(D_MODEL, EMBED_DIM)
        self.value_head = DistributionalValueHead(D_MODEL)
        self.value_head.combiner = nn.Sequential(
            nn.Linear(D_MODEL * 3, D_MODEL), nn.ReLU())

    def forward(self, batch):
        """Forward pass. Returns dict with logits, representations, and value."""
        B = batch['entity_stats'].shape[0]
        tokens, mask = self.tokenizer(batch)
        entity_reps, global_rep = self.transformer(
            tokens, mask,
            torch.zeros(B, 1, EMBED_DIM, device=tokens.device))

        # Competitor only (24 slots) for action head
        comp_reps = entity_reps[:, :24, :]
        comp_mask = mask[:, :24]

        type_logits, ptr_scores = self.action_head(
            global_rep, comp_reps, comp_mask,
            batch['entity_groups'][:, 1:25])

        value_out = self.value_head(global_rep, entity_reps, mask)

        return {
            'type_logits': type_logits,
            'pointer_scores': ptr_scores,
            'global_rep': global_rep,
            'entity_reps': entity_reps,
            'value': value_out,
        }

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
