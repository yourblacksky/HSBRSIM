"""
Game Value Network v2 — POMDP state value prediction with board embeddings.

Phase 2 of the search+value architecture. The student learns to predict
full-information expected placement from only the player's partial observation.

v1 (scalar):  V_game([board_score, own_stats, opp_stats, global]) → placement
  Problem: scalar board_score can't distinguish "6 big vanilla" from "7 small poison."

v2 (embedding):  V_game([board_emb(32), own_stats, opp_stats, global]) → placement
  Board embedding preserves compositional features (keywords, stat distributions).
  Teacher uses pairwise CombatPredictor for more accurate ranking.

Natural language:
  Encode the player's board into a 32-dim embedding that preserves minion-level
  features. Train a network to predict the player's expected placement from this
  partial observation, using a full-information teacher that ranks players by
  pairwise combat predictions.

Formal spec:
  Teacher:  pairwise_predictions = CombatPredictor(emb_i, emb_j) ∀ i≠j
            score_i = Σ_j P(i beats j)  → rank by score → placement
  Student:  V_game(obs) → predicted_placement ∈ [0,1]  (1 = 1st place)
  Loss:     MSE(V_game(obs), teacher_placement)
  Obs dim:  61 (32 embed + 6 own + 21 opponents + 2 global)

Test:
  python -m hsrl.train.game_value --games 500 --epochs 50 --board-eval checkpoints/board_eval_v2.pt
"""

from __future__ import annotations

import argparse
import os
import random
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
_CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints")


# ── POMDP Observation Encoding ──────────────────────────────────────────────

EMBED_DIM = 32
OBS_DIM = EMBED_DIM + 6 + 21 + 2  # 32 embed + 6 own + 21 opp + 2 global = 61


def encode_pomdp_state(game, player, board_eval_trainer) -> np.ndarray:
    """Encode the recruit-phase POMDP observation for a single player.

    Returns float32 array of shape (OBS_DIM,).

    Board embedding (32):
      embed_board(encode_board_from_minions(board)) → R^32
    Own features (6):
      hp, gold, tier, armor, board_size, hand_size
    Opponent features (7 × 3 = 21):
      hp, tier, is_alive — for each of up to 7 opponents (zero-padded)
    Global features (2):
      turn, alive_count
    """
    from hsrl.train.combat_data import encode_board_from_minions

    # ── Board embedding (replaces scalar board_score) ──
    board_enc = encode_board_from_minions(player.board)
    board_emb = board_eval_trainer.embed_board(board_enc)

    # ── Own state (6 scalars) ──
    own_hp = player.health / 40.0
    own_gold = player.gold / 10.0
    own_tier = player.tavern_tier / 7.0
    own_armor = player.armor / 20.0
    board_size = len([m for m in player.board if not m.dead]) / 7.0
    hand_size = len(player.hand) / 10.0

    # ── Opponent features (7 × 3) ──
    opponents = [p for p in game.players if p is not player]
    opp_feats = []
    for opp in opponents[:7]:
        if opp.is_alive:
            opp_feats.extend([opp.health / 40.0, opp.tavern_tier / 7.0, 1.0])
        else:
            opp_feats.extend([0.0, 0.0, 0.0])
    while len(opp_feats) < 21:
        opp_feats.extend([0.0, 0.0, 0.0])

    # ── Global features (2) ──
    turn = min(game.turn, 30) / 30.0
    alive_count = sum(1 for p in game.players if p.is_alive) / 8.0

    feats = np.concatenate([
        board_emb,
        np.array([own_hp, own_gold, own_tier, own_armor, board_size, hand_size], dtype=np.float32),
        np.array(opp_feats, dtype=np.float32),
        np.array([turn, alive_count], dtype=np.float32),
    ])

    return feats


def compute_teacher_placement(game, board_eval_trainer) -> dict:
    """Compute full-information teacher placement via pairwise combat predictions.

    Uses CombatPredictor to predict P(i beats j) for all alive player pairs,
    then ranks by expected win count. This captures non-linear interactions
    (poison > stats, DS blocks poison) that scalar ranking misses.

    Returns dict mapping player.entity_id → normalized_value ∈ [0, 1]
    where 1.0 = 1st place.
    """
    from hsrl.train.combat_data import encode_board_from_minions

    alive = [p for p in game.players if p.is_alive]
    dead = [p for p in game.players if not p.is_alive]

    n_total = len(game.players)
    values = {}

    # Score alive players by pairwise expected wins
    if len(alive) >= 2:
        # Encode all boards
        encodings = {}
        for p in alive:
            encodings[p.entity_id] = encode_board_from_minions(p.board)

        # Pairwise predictions
        eids = list(encodings.keys())
        win_counts = {eid: 0.0 for eid in eids}

        for i in range(len(eids)):
            for j in range(i + 1, len(eids)):
                eid_a, eid_b = eids[i], eids[j]
                p_a_wins = board_eval_trainer.predict_win_prob(
                    encodings[eid_a], encodings[eid_b])
                win_counts[eid_a] += p_a_wins
                win_counts[eid_b] += 1.0 - p_a_wins

        ranked = sorted(eids, key=lambda e: win_counts[e], reverse=True)
        for rank, eid in enumerate(ranked):
            placement = rank + 1
            values[eid] = (n_total - placement) / (n_total - 1)
    elif len(alive) == 1:
        values[alive[0].entity_id] = 1.0

    # Dead players: assigned by death order
    for i, p in enumerate(dead):
        placement = len(alive) + i + 1
        values[p.entity_id] = (n_total - placement) / (n_total - 1)

    return values


# ── Data Collection ─────────────────────────────────────────────────────────

def collect_game_value_data(
    n_games: int = 500,
    board_eval_path: str = "checkpoints/board_eval.pt",
    seed_start: int = 0,
    device: str = "auto",
    verbose: bool = True,
):
    """Run games and collect (POMDP_obs, teacher_value) pairs.

    Returns:
        observations: (n_samples, OBS_DIM)
        targets: (n_samples,) normalized teacher values
    """
    from hsrl.train.board_eval import BoardEvalTrainer
    from hsrl.core.card_db import CARDS
    from hsrl.core.enums import CardType, State
    from hsrl.core.game import Game

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    board_eval = BoardEvalTrainer.load(board_eval_path, device=device)

    # Ensure card modules loaded
    import hsrl.cards.minions.pool as _mp  # noqa
    import hsrl.cards.minions.scripts as _ms  # noqa
    import hsrl.cards.minions.tokens as _mt  # noqa
    import hsrl.cards.heroes.pool as _hp  # noqa
    import hsrl.cards.heroes.scripts as _hs  # noqa
    import hsrl.cards.trinkets.scripts as _ts  # noqa
    import hsrl.cards.rewards.scripts as _rs  # noqa
    import hsrl.cards.anomalies.scripts as _as  # noqa

    hero_ids = [
        cid for cid, data in CARDS._cards.items()
        if data.cardtype == CardType.HERO
        and not cid.startswith("EXAMPLE_")
    ]

    all_obs = []
    all_targets = []

    t_start = time.time()

    for game_idx in range(n_games):
        seed = seed_start + game_idx
        random.seed(seed)
        np.random.seed(seed)

        chosen = random.sample(hero_ids, min(8, len(hero_ids)))

        game = Game([])
        game.card_db = CARDS
        game.init_pool()
        players = [game.create_player(hid) for hid in chosen]
        game.players = players
        for p in players:
            p.game = game
        game.active_anomaly = True
        game.start_game()

        game_samples = 0

        while game.state == State.RUNNING and game.turn <= 30:
            for p in players:
                if not p.is_alive:
                    continue
                game.active_player = p
                game._auto_player_turn(p)
                game.resolve_queue()
                while game._pending_targeted_queue:
                    game.auto_resolve_pending_target()

            # ── Pre-combat: snapshot POMDP observations + teacher values ──
            teacher_values = compute_teacher_placement(game, board_eval)
            for p in players:
                if not p.is_alive:
                    continue
                obs = encode_pomdp_state(game, p, board_eval)
                target = teacher_values[p.entity_id]
                all_obs.append(obs)
                all_targets.append(target)
                game_samples += 1

            game.end_recruit_phase()

            alive = [p for p in game.players if p.is_alive]
            if len(alive) <= 1:
                game.state = State.COMPLETE

        if verbose and (game_idx + 1) % 50 == 0:
            elapsed = time.time() - t_start
            total = len(all_targets)
            print(f"  {game_idx + 1}/{n_games} games, {total} samples "
                  f"({elapsed:.0f}s, {total / max(elapsed, 1):.1f} samples/s)", flush=True)

    elapsed = time.time() - t_start
    obs = np.array(all_obs, dtype=np.float32)
    targets = np.array(all_targets, dtype=np.float32)

    if verbose:
        print(f"\nCollected {len(targets)} samples from {n_games} games in {elapsed:.0f}s")
        print(f"  obs: {obs.shape}, targets: {targets.shape}")
        print(f"  target mean={targets.mean():.3f}, std={targets.std():.3f}")
        print(f"  target distribution:")
        for pct in [0, 10, 25, 50, 75, 90, 100]:
            print(f"    p{pct}: {np.percentile(targets, pct):.3f}")

    return obs, targets


# ── Model ────────────────────────────────────────────────────────────────────


class GameValueNetwork(nn.Module):
    """Predict E[placement] from POMDP observation with board embedding.

    Architecture:
      board_emb (32) → Linear(32, 16) → ReLU → board_proj(16)
      own_stats (6)  → Linear(6, 16) → ReLU → own_proj(16)
      Each opponent (3) → opp_mlp(3→16→8) → opp_emb(8)  [shared]
      Opponent pool: mean over 7 → opp_pooled(8)
      Global (2) → identity
      concat(16 + 16 + 8 + 2) = 42 → combiner MLP → scalar
    """

    def __init__(self, obs_dim: int = OBS_DIM):
        super().__init__()
        self.obs_dim = obs_dim

        # Feature indices
        self.board_start = 0
        self.board_len = EMBED_DIM
        self.own_start = EMBED_DIM
        self.own_len = 6
        self.opp_start = EMBED_DIM + 6
        self.opp_len = 21
        self.glob_start = EMBED_DIM + 6 + 21
        self.glob_len = 2

        self.board_proj = nn.Sequential(
            nn.Linear(EMBED_DIM, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
        )
        self.own_mlp = nn.Sequential(
            nn.Linear(6, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
        )
        self.opp_mlp = nn.Sequential(
            nn.Linear(3, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
        )
        self.combiner = nn.Sequential(
            nn.Linear(16 + 16 + 8 + 2, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 1),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=0.5)
                nn.init.zeros_(m.bias)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """obs: (batch, OBS_DIM) → value: (batch, 1)"""
        board = obs[:, self.board_start:self.board_start + self.board_len]
        own = obs[:, self.own_start:self.own_start + self.own_len]
        opp = obs[:, self.opp_start:self.opp_start + self.opp_len]
        glob = obs[:, self.glob_start:self.glob_start + self.glob_len]

        board_proj = self.board_proj(board)  # (b, 16)
        own_proj = self.own_mlp(own)         # (b, 16)

        # Reshape opponents: (b, 21) → (b, 7, 3) → encode each → pool
        b = opp.shape[0]
        opp_flat = opp.reshape(b * 7, 3)
        opp_emb = self.opp_mlp(opp_flat)     # (b*7, 8)
        opp_emb = opp_emb.reshape(b, 7, 8)
        opp_pooled = opp_emb.mean(dim=1)     # (b, 8)

        combined = torch.cat([board_proj, own_proj, opp_pooled, glob], dim=-1)
        return self.combiner(combined)


# ── Trainer ──────────────────────────────────────────────────────────────────


class GameValueTrainer:
    """Train GameValueNetwork via teacher-student distillation."""

    def __init__(
        self,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        device: str = "auto",
        seed: int = 42,
    ):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        torch.manual_seed(seed)
        self.device = device
        self.model = GameValueNetwork().to(device)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=lr, weight_decay=weight_decay,
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=50,
        )

    def train(
        self,
        obs: np.ndarray,
        targets: np.ndarray,
        epochs: int = 50,
        batch_size: int = 512,
        val_split: float = 0.1,
        verbose: bool = True,
        save_path: str = "checkpoints/game_value_v2.pt",
    ):
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        targets_t = torch.as_tensor(targets, dtype=torch.float32)

        n = len(targets)
        n_val = max(1, int(n * val_split))
        n_train = n - n_val

        perm = torch.randperm(n)
        obs_t, targets_t = obs_t[perm], targets_t[perm]

        train_ds = TensorDataset(obs_t[:n_train], targets_t[:n_train])
        val_ds = TensorDataset(obs_t[n_train:], targets_t[n_train:])
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

        n_params = sum(p.numel() for p in self.model.parameters())
        if verbose:
            print(f"\nTraining GameValueNetwork v2: {n_train} train, {n_val} val")
            print(f"  Params: {n_params:,}")
            print(f"  Device: {self.device}")

        best_val_mae = float("inf")
        t_start = time.time()

        for epoch in range(epochs):
            # ── Train ──
            self.model.train()
            train_loss = 0.0
            train_mae = 0.0
            n_batches = 0

            for batch_obs, batch_targets in train_loader:
                batch_obs = batch_obs.to(self.device)
                batch_targets = batch_targets.to(self.device)

                pred = self.model(batch_obs).squeeze(-1)
                loss = nn.functional.mse_loss(pred, batch_targets)

                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()

                train_loss += loss.item()
                train_mae += (pred.detach() - batch_targets).abs().mean().item()
                n_batches += 1

            self.scheduler.step()

            # ── Val ──
            self.model.eval()
            val_loss = 0.0
            val_mae = 0.0
            n_val_batches = 0

            with torch.no_grad():
                for batch_obs, batch_targets in val_loader:
                    batch_obs = batch_obs.to(self.device)
                    batch_targets = batch_targets.to(self.device)

                    pred = self.model(batch_obs).squeeze(-1)
                    val_loss += nn.functional.mse_loss(pred, batch_targets).item()
                    val_mae += (pred - batch_targets).abs().mean().item()
                    n_val_batches += 1

            train_loss /= max(n_batches, 1)
            train_mae /= max(n_batches, 1)
            val_loss /= max(n_val_batches, 1)
            val_mae /= max(n_val_batches, 1)

            if val_mae < best_val_mae:
                best_val_mae = val_mae
                self.save(save_path, epoch, val_mae)

            if verbose and (epoch + 1) % 10 == 0:
                elapsed = time.time() - t_start
                print(f"  epoch {epoch + 1:3d}/{epochs}  "
                      f"train_loss={train_loss:.4f}  train_mae={train_mae:.4f}  "
                      f"val_loss={val_loss:.4f}  val_mae={val_mae:.4f}  "
                      f"lr={self.scheduler.get_last_lr()[0]:.2e}  "
                      f"({elapsed:.0f}s)", flush=True)

        elapsed = time.time() - t_start
        if verbose:
            print(f"\nTraining complete: {epochs} epochs in {elapsed:.0f}s")
            print(f"  Best val_mae: {best_val_mae:.4f} (~{best_val_mae * 7:.2f} placement positions)")
            print(f"  Model saved to: {save_path}")
            baseline_mae = np.abs(targets - targets.mean()).mean()
            print(f"  Baseline: constant mean prediction MAE = {baseline_mae:.4f}")

        return best_val_mae

    def save(self, path: str, epoch: int = 0, val_mae: float = 0.0):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "val_mae": val_mae,
            "obs_dim": self.model.obs_dim,
            "embed_dim": EMBED_DIM,
        }, path)

    @classmethod
    def load(cls, path: str, device: str = "auto"):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        ckpt = torch.load(path, map_location=device, weights_only=False)
        embed_dim = ckpt.get("embed_dim", EMBED_DIM)
        # Update global EMBED_DIM if checkpoint has different value
        if embed_dim != EMBED_DIM:
            import hsrl.train.game_value as gv
            gv.EMBED_DIM = embed_dim
            gv.OBS_DIM = embed_dim + 6 + 21 + 2
        trainer = cls(device=device)
        trainer.model.load_state_dict(ckpt["model_state_dict"])
        trainer.model.to(device)
        trainer.model.eval()
        return trainer

    @torch.no_grad()
    def predict(self, obs: np.ndarray) -> np.ndarray:
        """Predict value for one or more POMDP observations.

        Returns float32 array of shape (batch,) or scalar for single obs.
        """
        t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        if t.dim() == 1:
            t = t.unsqueeze(0)
        values = self.model(t).squeeze(-1)
        if values.dim() == 0:
            return values.item()
        return values.cpu().numpy()


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="GameValueNetwork v2 training (Phase 2)")
    parser.add_argument("--games", type=int, default=500,
                        help="Games for data collection")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--board-eval", type=str, default="checkpoints/board_eval_v2.pt")
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="checkpoints/game_value_v2.pt")
    args = parser.parse_args()

    # Collect data with heuristic auto-play
    print(f"Collecting data from {args.games} games...")
    obs, targets = collect_game_value_data(
        n_games=args.games,
        board_eval_path=args.board_eval,
        seed_start=args.seed,
        device=args.device,
    )

    # Train
    trainer = GameValueTrainer(
        lr=args.lr,
        device=args.device,
        seed=args.seed,
    )

    trainer.train(
        obs=obs,
        targets=targets,
        epochs=args.epochs,
        batch_size=args.batch_size,
        save_path=args.output,
    )


if __name__ == "__main__":
    main()
