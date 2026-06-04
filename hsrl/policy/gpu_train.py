"""
GPU Training Script — 5.25M model, board-building environment.

Single seed=42, iterative data collection + GPU training.
Tracks value loss, board scores, and eval rank over rounds.
"""

import sys, time, numpy as np, torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, '.' if '.' not in sys.path else '.')

import hsrl.cards.minions, hsrl.cards.heroes, hsrl.cards.spells
from hsrl.core.card_db import CARDS
from hsrl.core.game import Game
from hsrl.core.enums import GameTag, CardType
from hsrl.rl_env.observation import build_observation_v2
from hsrl.rl_env.observation.entity_schema import NUM_ENTITY_SLOTS
from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.env.action import build_action_mask, END_TURN, REFRESH, NUM_ACTIONS
from hsrl.agents.agent_utils import save_player_state, restore_player_state, simulate_action, populate_tavern
from hsrl.policy.transformer import EntityTransformer
from hsrl.policy.heads import HierarchicalActionHead
from hsrl.policy.value_head import DistributionalValueHead

# ── Config ──
SEED = 42
T = 8               # turns per game
GAMES_PER_ROUND = 20
ROUNDS = 10
GPU_EPOCHS = 50
GPU_BATCH = 512
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

torch.manual_seed(SEED); np.random.seed(SEED)

# ── Scaled 5.25M model ──
EMBED_DIM = 128; D_MODEL = 256; N_HEADS = 4; N_LAYERS = 6; D_FF = 1024

class ScaledTokenizerV2(nn.Module):
    def __init__(self):
        super().__init__()
        self.card_emb = nn.Embedding(1500, EMBED_DIM, padding_idx=0)
        self.entity_mlp = nn.Sequential(nn.Linear(8, 64), nn.ReLU(), nn.Linear(64, EMBED_DIM))
        self.global_proj = nn.Sequential(nn.Linear(16, EMBED_DIM), nn.ReLU())
        self.hero_proj = nn.Sequential(nn.Linear(12, EMBED_DIM), nn.ReLU())
        self.opp_proj = nn.Sequential(nn.Linear(12, EMBED_DIM), nn.ReLU())
        self.hist_proj = nn.Sequential(nn.Linear(8, EMBED_DIM), nn.ReLU())

    def forward(self, batch):
        B = batch['entity_stats'].shape[0]; N = NUM_ENTITY_SLOTS
        tokens = torch.zeros(B, N, EMBED_DIM, device=batch['entity_stats'].device)
        tokens[:,0,:] = self.global_proj(batch['global_features'])
        tokens[:,1,:] = self.hero_proj(batch['hero_features'])
        for slot in range(2, 26):
            tokens[:,slot,:] = (self.card_emb(batch['card_indices'][:,slot]) +
                               self.entity_mlp(batch['entity_stats'][:,slot]))
        for i in range(7): tokens[:,26+i,:] = self.opp_proj(batch['opponent_features'][:,i,:])
        for i in range(4): tokens[:,33+i,:] = self.hist_proj(batch['history_features'][:,i,:])
        return tokens[:,1:,:], batch['entity_mask'][:,1:]


# ── Game helpers ──
def auto_play(p):
    bc = len([m for m in p.board if not m.dead])
    for m in [c for c in p.hand if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION]:
        if bc >= 7: break; p.hand.remove(m); p.board.append(m); bc += 1

def run_turn(game, turn):
    for p in game.players:
        p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
        p.set_tag(GameTag.HERO_POWER_USED, False); p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
        c = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
        if c > 0: p.set_tag(GameTag.TAVERN_UPGRADE_COST, c - 1)
    for p in game.players: game.refresh_tavern(p); auto_play(p)


# ── Init model ──
print("=" * 60)
print(f"  GPU TRAINING — 5.25M model, seed={SEED}")
print(f"  {GAMES_PER_ROUND} games/round × {ROUNDS} rounds")
print("=" * 60)

tokenizer = ScaledTokenizerV2().to(DEVICE)
transformer = EntityTransformer(D_MODEL, N_HEADS, N_LAYERS, D_FF).to(DEVICE)
transformer.input_proj = nn.Linear(EMBED_DIM, D_MODEL).to(DEVICE)
action_head = HierarchicalActionHead(D_MODEL, EMBED_DIM).to(DEVICE)
value_head = DistributionalValueHead(D_MODEL).to(DEVICE)
value_head.combiner = nn.Sequential(nn.Linear(D_MODEL * 3, D_MODEL), nn.ReLU()).to(DEVICE)

all_params = (list(tokenizer.parameters()) + list(transformer.parameters()) +
             list(action_head.parameters()) + list(value_head.parameters()))
total_params = sum(p.numel() for p in all_params)
opt = torch.optim.Adam(all_params, lr=3e-4)
print(f"Model: {total_params/1e6:.2f}M params | GPU: {torch.cuda.get_device_name(0)}")

# ── Training loop ──
history = []
total_cpu_time = 0; total_gpu_time = 0

for rnd in range(ROUNDS):
    t_cpu = time.time()

    # ── CPU: collect data ──
    all_obs = []; all_scores = []
    for gi in range(GAMES_PER_ROUND):
        game = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=SEED * 100 + rnd * GAMES_PER_ROUND + gi)
        for turn in range(1, T + 1):
            run_turn(game, turn)
            for idx in range(8):
                p = game.players[idx]
                for _ in range(6):
                    mask = build_action_mask(game, p); legal = [a for a in range(50) if mask[a]]
                    if not legal: break
                    all_obs.append(build_observation_v2(game, p))
                    a = int(np.random.choice(legal))
                    if a == END_TURN: break
                    simulate_action(p, a)
                    if a == REFRESH: populate_tavern(p, game.rng); auto_play(p)
                auto_play(p)
        scores = [compute_board_score_v2(p).total for p in game.players]
        all_scores.extend([float(s) for _ in range(8) for s in scores])

    all_scores = all_scores[:len(all_obs)]
    while len(all_scores) < len(all_obs): all_scores.append(0.0)

    n_states = len(all_obs)
    dt_cpu = time.time() - t_cpu; total_cpu_time += dt_cpu

    # ── GPU: train ──
    t_gpu = time.time()
    score_t = torch.tensor(all_scores, device=DEVICE, dtype=torch.float32) / 10.0

    for ep in range(GPU_EPOCHS):
        perm = torch.randperm(n_states, device=DEVICE)
        for bi in range(0, n_states, GPU_BATCH):
            idxs = perm[bi:min(bi + GPU_BATCH, n_states)]
            BA = len(idxs); N = NUM_ENTITY_SLOTS

            es = torch.zeros(BA, N, 8, device=DEVICE); em = torch.zeros(BA, N, dtype=torch.bool, device=DEVICE)
            eg = torch.zeros(BA, N, dtype=torch.long, device=DEVICE); ci = torch.zeros(BA, N, dtype=torch.long, device=DEVICE)
            gf = torch.zeros(BA, 16, device=DEVICE); hf = torch.zeros(BA, 12, device=DEVICE)
            of_ = torch.zeros(BA, 7, 12, device=DEVICE); hif = torch.zeros(BA, 4, 8, device=DEVICE)

            for j, i in enumerate(idxs):
                o = all_obs[i]; es[j] = torch.from_numpy(o['entity_stats'][:N]); em[j] = torch.from_numpy(o['entity_mask'][:N])
                eg[j] = torch.from_numpy(o['entity_groups'][:N]); ci[j] = torch.from_numpy(o['card_indices'][:N])
                gf[j] = torch.from_numpy(o['global_features'][:16]); hf[j] = torch.from_numpy(o['hero_features'][:12])
                of_[j] = torch.from_numpy(o.get('opponent_features', np.zeros((7, 12), dtype=np.float32)))
                hif[j] = torch.from_numpy(o.get('history_features', np.zeros((4, 8), dtype=np.float32)))

            bt = {'entity_stats': es, 'entity_mask': em, 'entity_groups': eg, 'card_indices': ci,
                  'global_features': gf, 'hero_features': hf, 'opponent_features': of_, 'history_features': hif}

            et, em2 = tokenizer(bt)
            er, gr = transformer(et, em2, torch.zeros(BA, 1, EMBED_DIM, device=DEVICE))
            vo = value_head(gr, er, em2)
            vloss = F.mse_loss(vo['value'].squeeze(-1), score_t[idxs])

            opt.zero_grad(); vloss.backward()
            torch.nn.utils.clip_grad_norm_(all_params, 1.0); opt.step()

    torch.cuda.synchronize()
    dt_gpu = time.time() - t_gpu; total_gpu_time += dt_gpu

    # ── Quick eval ──
    eval_scores_t = []; eval_scores_u = []
    for gi in range(3):
        game = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=SEED * 7777 + rnd * 3 + gi)
        for turn in range(1, T + 1):
            run_turn(game, turn)
            for idx in range(8):
                p = game.players[idx]
                for _ in range(6):
                    mask = build_action_mask(game, p); legal = [a for a in range(50) if mask[a]]
                    if not legal: break; a = int(np.random.choice(legal))
                    if a == END_TURN: break
                    simulate_action(p, a)
                    if a == REFRESH: populate_tavern(p, game.rng); auto_play(p)
                auto_play(p)
        scores = [compute_board_score_v2(p).total for p in game.players]
        for i in range(8):
            if i in (0, 2, 4, 6): eval_scores_t.append(scores[i])
            else: eval_scores_u.append(scores[i])

    t_avg = np.mean(eval_scores_t); u_avg = np.mean(eval_scores_u)
    gap = t_avg - u_avg
    history.append((rnd + 1, t_avg, u_avg, n_states, dt_cpu, dt_gpu))

    print(f"  R{rnd+1:2d}: T_sc={t_avg:5.1f} U_sc={u_avg:5.1f} Δ={gap:+5.1f} | "
          f"CPU {dt_cpu:.0f}s GPU {dt_gpu:.0f}s | {n_states} states")

# ── Summary ──
print(f"\n{'='*60}")
print(f"  TRAINING COMPLETE ({total_cpu_time:.0f}s CPU + {total_gpu_time:.0f}s GPU)")
print(f"{'='*60}")
print(f"  {'Rd':>3s} {'T_sc':>6s} {'U_sc':>6s} {'Gap':>6s} {'States':>7s}")
for r, ts, us, n, cpu, gpu in history:
    print(f"  {r:3d} {ts:6.1f} {us:6.1f} {ts-us:+6.1f} {n:7d}")

gaps = [ts - us for _, ts, us, _, _, _ in history]
first3 = np.mean(gaps[:3]); last3 = np.mean(gaps[-3:])
print(f"\n  First 3 avg gap: {first3:+.1f}")
print(f"  Last 3 avg gap:  {last3:+.1f}")
print(f"  Trend:           {'IMPROVING ↑' if last3 > first3 + 0.5 else 'FLAT →'}")
