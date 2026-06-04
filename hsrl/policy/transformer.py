"""
Entity Transformer — 2-layer MHA encoder over entity tokens.

Processes the flat entity-token sequence with self-attention so that
board minions, hand cards, tavern entities, and the global context token
can attend to each other. The output is a contextualized representation
where each entity "knows about" other entities on the board/hand/tavern.

Architecture:
  Input:  (batch, 1+N, 24) — [global_token, entity_1, ..., entity_N]
  Project: Linear(24→48)
  Encode:  2 × TransformerEncoderLayer(d=48, h=4, d_ff=96, dropout=0.1)
  Output:  (batch, 1+N, 48)

Key design decisions:
  - d_model=48 is intentionally small (see parameter budget)
  - 4 heads gives head_dim=12 per head
  - d_ff=96 = 2× expansion (standard)
  - 2 layers is enough for ~25 token sequences
  - GELU activation (modern default)
  - Pre-norm architecture (better training stability)

Total params: ~38,544
"""

from __future__ import annotations

import torch
import torch.nn as nn


class TransformerEncoderLayer(nn.Module):
    """Single transformer encoder layer with pre-norm and GELU."""

    def __init__(self, d_model: int = 48, n_heads: int = 4,
                 d_ff: int = 96, dropout: float = 0.1):
        super().__init__()

        self.self_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout),
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor,
                key_padding_mask: torch.Tensor | None = None) -> torch.Tensor:
        # Pre-norm self-attention with residual
        residual = x
        x_norm = self.norm1(x)
        attn_out, _ = self.self_attn(
            x_norm, x_norm, x_norm,
            key_padding_mask=key_padding_mask,
        )
        x = residual + attn_out

        # Pre-norm FF with residual
        residual = x
        x = residual + self.ff(self.norm2(x))
        return x


class EntityTransformer(nn.Module):
    """2-layer transformer encoder over entity tokens + global context.

    Input: entity_tokens (B, N, 24), entity_mask (B, N), global_token (B, 1, 24)
    Output: pooled_entities (B, N, 48), global_rep (B, 48)
    """

    def __init__(self, d_model: int = 48, n_heads: int = 4,
                 n_layers: int = 2, d_ff: int = 96, dropout: float = 0.1):
        super().__init__()

        self.d_model = d_model

        # Input projection: 24 → d_model
        self.input_proj = nn.Linear(24, d_model)

        # Transformer layers
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(d_model, n_heads, d_ff, dropout)
            for _ in range(n_layers)
        ])

        self.final_norm = nn.LayerNorm(d_model)

    def forward(self, entity_tokens: torch.Tensor,
                entity_mask: torch.Tensor,
                global_token: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            entity_tokens: (B, N, 24) — entity representations
            entity_mask: (B, N) — True where entity exists
            global_token: (B, 1, 24) — global context token

        Returns:
            entity_reps: (B, N, d_model) — contextualized entity tokens
            global_rep: (B, d_model) — pooled global representation
        """
        B, N, _ = entity_tokens.shape

        # Project to d_model
        entities = self.input_proj(entity_tokens)       # (B, N, d)
        glob_tok = self.input_proj(global_token)         # (B, 1, d)

        # Concatenate: [global, entity_1, ..., entity_N]
        seq = torch.cat([glob_tok, entities], dim=1)    # (B, 1+N, d)

        # Build padding mask for transformer:
        # global token is never masked; entity slots are masked if empty
        pad_mask = torch.cat([
            torch.zeros(B, 1, dtype=torch.bool, device=entity_mask.device),
            ~entity_mask,
        ], dim=1)  # (B, 1+N) — True = MASKED (skip in attention)

        # Apply transformer layers
        x = seq
        for layer in self.layers:
            x = layer(x, key_padding_mask=pad_mask)

        x = self.final_norm(x)

        # Split back: global_rep is position 0, entity_reps are positions 1..N
        global_rep = x[:, 0, :]          # (B, d)
        entity_reps = x[:, 1:, :]        # (B, N, d)

        return entity_reps, global_rep

    def count_parameters(self) -> int:
        """Return total trainable parameter count."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
