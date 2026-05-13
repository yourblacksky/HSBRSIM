"""
Combat Board Evaluation Network v2 — embedding-based pairwise combat prediction.

v1 (scalar):  f(board) → score,  P(A wins) = sigmoid(score_a - score_b)
  Problem: scalar compresses board composition, loses keyword interactions.
  Example: 6 big vanilla minions vs 7 small poisonous → scalar can't express
  "poison beats stats."

v2 (embedding):  embed(board) → R^32,  CombatPredictor(emb_a, emb_b) → P(A wins)
  Embedding preserves compositional features (keywords, stat distributions).
  CombatPredictor captures non-linear interactions (poison > stats, DS blocks poison).

Natural language:
  Encode each board into a 32-dimensional embedding that preserves minion-level
  features. Predict combat outcomes by passing both boards' embeddings through
  a learned interaction network that captures how board compositions counter
  each other.

Formal spec:
  BoardEmbedder: (7×15) → R^32
  CombatPredictor(emb_a, emb_b):
    combined = [emb_a; emb_b; emb_a-emb_b; emb_a⊙emb_b]  ∈ R^128
    logit = MLP(combined)  ∈ R
  Loss: BCEWithLogitsLoss(logit, label)  where label=1 if A wins

Test:
  python -m hsrl.train.board_eval --data data/combat_pairs/combats.npz --epochs 50
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

_EMBED_DIM = 32
_CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints")


# ── Board Embedder ──────────────────────────────────────────────────────────

class BoardEmbedder(nn.Module):
    """Encode a (7, 15) board into a 32-dim embedding.

    Architecture:
      Per-slot MLP (15→64→32) → learned attention weights → weighted pool
      + max pool → concat → output projection → 32-dim embedding.

    Attention pooling preserves which minions matter most (e.g. taunt,
    divine shield carriers) rather than blindly averaging.
    """

    def __init__(self, slot_dim: int = 15, embed_dim: int = _EMBED_DIM):
        super().__init__()
        self.embed_dim = embed_dim

        # Per-slot encoder: minion stats → rich representation
        self.slot_mlp = nn.Sequential(
            nn.Linear(slot_dim, 64),
            nn.ReLU(),
            nn.Linear(64, embed_dim),
        )

        # Learned attention: which slots are most important?
        self.attn = nn.Sequential(
            nn.Linear(embed_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

        # Output projection: concat(weighted_mean, max) → embed
        self.output = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, embed_dim),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=0.5)
                nn.init.zeros_(m.bias)

    def forward(self, board: torch.Tensor) -> torch.Tensor:
        """board: (batch, 7, 15) → embedding: (batch, embed_dim)"""
        b, s, _ = board.shape

        # Per-slot encoding
        slots = self.slot_mlp(board.view(b * s, -1))  # (b*s, embed_dim)
        slots = slots.view(b, s, -1)                   # (b, s, embed_dim)

        # Attention weights (softmax over slots)
        raw_weights = self.attn(slots.view(b * s, -1)).view(b, s, 1)
        weights = F.softmax(raw_weights, dim=1)        # (b, s, 1)

        # Weighted mean pool
        weighted = (slots * weights).sum(dim=1)        # (b, embed_dim)

        # Max pool (captures strongest features regardless of position)
        max_pooled = slots.max(dim=1).values           # (b, embed_dim)

        # Combine and project
        combined = torch.cat([weighted, max_pooled], dim=-1)  # (b, 2*embed_dim)
        return self.output(combined)                           # (b, embed_dim)


# ── Combat Predictor ────────────────────────────────────────────────────────

class CombatPredictor(nn.Module):
    """Predict P(A beats B) from two board embeddings.

    Uses multilinear interaction features to capture how board
    compositions counter each other:

      combined = [emb_a; emb_b; emb_a - emb_b; emb_a ⊙ emb_b]

    This allows learning:
      - Absolute strength: "board with high stats generally wins"
      - Relative difference: "how much stronger is A than B"
      - Multiplicative interaction: "poison × big_stats → poison wins"
    """

    def __init__(self, embed_dim: int = _EMBED_DIM):
        super().__init__()
        input_dim = embed_dim * 4  # [a; b; a-b; a*b]

        self.mlp = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 1),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=0.5)
                nn.init.zeros_(m.bias)
        # Final layer: small weights for calibrated sigmoid
        nn.init.orthogonal_(self.mlp[-1].weight, gain=0.01)

    def forward(self, emb_a: torch.Tensor, emb_b: torch.Tensor) -> torch.Tensor:
        """emb_a, emb_b: (batch, embed_dim) → logit: (batch, 1)"""
        combined = torch.cat([
            emb_a,
            emb_b,
            emb_a - emb_b,
            emb_a * emb_b,
        ], dim=-1)
        return self.mlp(combined)


# ── Joint Model (for training convenience) ──────────────────────────────────

class BoardEvalModel(nn.Module):
    """Joint model: BoardEmbedder + CombatPredictor.

    Train end-to-end: the embedder learns representations that are
    useful for the combat prediction task.
    """

    def __init__(self, slot_dim: int = 15, embed_dim: int = _EMBED_DIM):
        super().__init__()
        self.embedder = BoardEmbedder(slot_dim, embed_dim)
        self.predictor = CombatPredictor(embed_dim)
        self.embed_dim = embed_dim

    def forward(self, board_a: torch.Tensor, board_b: torch.Tensor) -> torch.Tensor:
        """board_a, board_b: (batch, 7, 15) → logit: (batch, 1)"""
        emb_a = self.embedder(board_a)
        emb_b = self.embedder(board_b)
        return self.predictor(emb_a, emb_b)

    @torch.no_grad()
    def embed_board(self, board: torch.Tensor) -> torch.Tensor:
        """Extract board embedding without combat prediction."""
        if board.dim() == 2:
            board = board.unsqueeze(0)
        return self.embedder(board)

    @torch.no_grad()
    def predict_win(self, board_a: torch.Tensor, board_b: torch.Tensor) -> float:
        """P(board_a beats board_b)."""
        if board_a.dim() == 2:
            board_a = board_a.unsqueeze(0)
        if board_b.dim() == 2:
            board_b = board_b.unsqueeze(0)
        logit = self.forward(board_a, board_b)
        return torch.sigmoid(logit).squeeze().item()


# ── Trainer ─────────────────────────────────────────────────────────────────

class BoardEvalTrainer:
    """Train BoardEvalModel (embedder + predictor) jointly."""

    def __init__(
        self,
        embed_dim: int = _EMBED_DIM,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        device: str = "auto",
        seed: int = 42,
    ):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        torch.manual_seed(seed)
        self.device = device
        self.model = BoardEvalModel(embed_dim=embed_dim).to(device)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=lr, weight_decay=weight_decay,
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=50,
        )

    def train(
        self,
        data_path: str,
        epochs: int = 50,
        batch_size: int = 512,
        val_split: float = 0.1,
        verbose: bool = True,
    ):
        data = np.load(data_path)
        boards_a = torch.as_tensor(data["boards_a"], dtype=torch.float32)
        boards_b = torch.as_tensor(data["boards_b"], dtype=torch.float32)
        labels = torch.as_tensor(data["labels"], dtype=torch.float32)

        n = len(labels)
        n_val = max(1, int(n * val_split))
        n_train = n - n_val

        perm = torch.randperm(n)
        boards_a, boards_b, labels = boards_a[perm], boards_b[perm], labels[perm]

        train_ds = TensorDataset(boards_a[:n_train], boards_b[:n_train], labels[:n_train])
        val_ds = TensorDataset(boards_a[n_train:], boards_b[n_train:], labels[n_train:])
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

        n_params = sum(p.numel() for p in self.model.parameters())
        if verbose:
            print(f"Loaded {n} samples: {n_train} train, {n_val} val")
            print(f"  Embedder params: {sum(p.numel() for p in self.model.embedder.parameters()):,}")
            print(f"  Predictor params: {sum(p.numel() for p in self.model.predictor.parameters()):,}")
            print(f"  Total params: {n_params:,}")
            print(f"  Device: {self.device}")

        best_val_acc = 0.0
        t_start = time.time()

        for epoch in range(epochs):
            # ── Train ──
            self.model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for ba, bb, lbl in train_loader:
                ba, bb, lbl = ba.to(self.device), bb.to(self.device), lbl.to(self.device)

                logit = self.model(ba, bb).squeeze(-1)
                loss = F.binary_cross_entropy_with_logits(logit, lbl)

                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()

                train_loss += loss.item()
                preds = (torch.sigmoid(logit) > 0.5).float()
                correct = ((preds == lbl) | (lbl == 0.5)).sum().item()
                train_correct += correct
                train_total += len(lbl)

            self.scheduler.step()

            # ── Val ──
            self.model.eval()
            val_loss = 0.0
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                for ba, bb, lbl in val_loader:
                    ba, bb, lbl = ba.to(self.device), bb.to(self.device), lbl.to(self.device)
                    logit = self.model(ba, bb).squeeze(-1)
                    loss = F.binary_cross_entropy_with_logits(logit, lbl)
                    val_loss += loss.item()
                    preds = (torch.sigmoid(logit) > 0.5).float()
                    correct = ((preds == lbl) | (lbl == 0.5)).sum().item()
                    val_correct += correct
                    val_total += len(lbl)

            train_acc = train_correct / max(train_total, 1)
            val_acc = val_correct / max(val_total, 1)

            if val_acc >= best_val_acc:
                best_val_acc = val_acc
                self.save("checkpoints/board_eval_v2.pt", epoch, val_acc)

            if verbose and (epoch + 1) % 10 == 0:
                elapsed = time.time() - t_start
                print(f"  epoch {epoch + 1:3d}/{epochs}  "
                      f"train_loss={train_loss / max(len(train_loader), 1):.4f}  "
                      f"train_acc={train_acc:.3f}  "
                      f"val_loss={val_loss / max(len(val_loader), 1):.4f}  "
                      f"val_acc={val_acc:.3f}  "
                      f"lr={self.scheduler.get_last_lr()[0]:.2e}  "
                      f"({elapsed:.0f}s)", flush=True)

        elapsed = time.time() - t_start
        if verbose:
            print(f"\nTraining complete: {epochs} epochs in {elapsed:.0f}s")
            print(f"  Best val_acc: {best_val_acc:.3f}")
            print(f"  Model saved to: checkpoints/board_eval_v2.pt")

        return best_val_acc

    def save(self, path: str, epoch: int = 0, val_acc: float = 0.0):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "val_acc": val_acc,
            "embed_dim": self.model.embed_dim,
        }, path)

    @classmethod
    def load(cls, path: str, device: str = "auto"):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        ckpt = torch.load(path, map_location=device, weights_only=False)
        embed_dim = ckpt.get("embed_dim", _EMBED_DIM)
        trainer = cls(embed_dim=embed_dim, device=device)
        trainer.model.load_state_dict(ckpt["model_state_dict"])
        trainer.model.to(device)
        trainer.model.eval()
        return trainer

    @torch.no_grad()
    def embed_board(self, board_enc: np.ndarray) -> np.ndarray:
        """Encode a (7, 15) board into 32-dim embedding."""
        t = torch.as_tensor(board_enc, dtype=torch.float32, device=self.device)
        if t.dim() == 2:
            t = t.unsqueeze(0)
        emb = self.model.embedder(t)
        if emb.shape[0] == 1:
            return emb.squeeze(0).cpu().numpy()
        return emb.cpu().numpy()

    @torch.no_grad()
    def predict_win_prob(self, board_a: np.ndarray, board_b: np.ndarray) -> float:
        """P(board_a beats board_b)."""
        t_a = torch.as_tensor(board_a, dtype=torch.float32, device=self.device)
        t_b = torch.as_tensor(board_b, dtype=torch.float32, device=self.device)
        return self.model.predict_win(t_a, t_b)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train board evaluation network v2")
    parser.add_argument("--data", type=str, default="data/combat_pairs/combats.npz")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--embed-dim", type=int, default=_EMBED_DIM)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    trainer = BoardEvalTrainer(
        embed_dim=args.embed_dim,
        lr=args.lr,
        device=args.device,
        seed=args.seed,
    )
    trainer.train(
        data_path=args.data,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
