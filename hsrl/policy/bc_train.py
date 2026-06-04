"""Phase 0: Behavior Cloning from BUY-biased heuristic."""
import sys, time, numpy as np, torch, torch.nn.functional as F
sys.path.insert(0, '/home/glt/HrSRL')
import hsrl.cards.minions, hsrl.cards.heroes, hsrl.cards.spells
from hsrl.core.card_db import CARDS
from hsrl.core.game import Game
from hsrl.core.enums import GameTag, CardType
from hsrl.rl_env.observation import build_observation_v2
from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.env.action import build_action_mask, END_TURN, REFRESH, BUY_OFFSET
from hsrl.agents.agent_utils import simulate_action, populate_tavern
from hsrl.policy.model_5m import ScaledModel

BUY_O, SELL_O, PLAY_O, REF, UPG, FRZ, HP, ET = 0, 7, 14, 24, 25, 26, 27, 28

def d2h(a):
    if BUY_O <= a < BUY_O + 7: return (0, a - BUY_O)
    if SELL_O <= a < SELL_O + 7: return (1, a - SELL_O)
    if PLAY_O <= a < PLAY_O + 10: return (2, a - PLAY_O)
    if a == REF: return (3, 0)
    if a == UPG: return (4, 0)
    if a == FRZ: return (5, 0)
    if a == HP: return (6, 0)
    return (7, 0)

def fast_heuristic_action(game, player):
    """Fast: buy if affordable, upgrade on curve, else random."""
    mask = build_action_mask(game, player)
    legal = [a for a in range(50) if mask[a]]
    if not legal:
        return ET
    buy_a = [a for a in legal if BUY_O <= a < BUY_O + 7]
    if buy_a and player.gold >= 3:
        return int(np.random.choice(buy_a))
    if UPG in legal and player.gold >= 5 and player.tavern_tier < 6:
        return UPG
    return int(np.random.choice(legal))

def ap(p):
    bc = len([m for m in p.board if not m.dead])
    for m in [c for c in p.hand if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION]:
        if bc >= 7: break
        p.hand.remove(m)
        p.board.append(m)
        bc += 1

SEED = 42
DEVICE = 'cuda'
N = 37
GAMES = 20
torch.manual_seed(SEED)
np.random.seed(SEED)

model = ScaledModel().to(DEVICE)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
print(f"{model.count_parameters()/1e6:.2f}M | BC from fast heuristic | {GAMES} games")

# ── Collect BC data ──
bc_obs = []
bc_act = []
t0 = time.time()
for gi in range(GAMES):
    g = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=SEED * 100 + gi)
    for turn in range(1, 8):
        for p in g.players:
            p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
            p.set_tag(GameTag.HERO_POWER_USED, False)
            p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
            c = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
            if c > 0:
                p.set_tag(GameTag.TAVERN_UPGRADE_COST, c - 1)
        for p in g.players:
            g.refresh_tavern(p)
            ap(p)
        for idx in range(8):
            p = g.players[idx]
            for _ in range(6):
                mask = build_action_mask(g, p)
                legal = [a for a in range(50) if mask[a]]
                if not legal:
                    break
                bc_obs.append(build_observation_v2(g, p))
                a = fast_heuristic_action(g, p)
                bc_act.append(a)
                if a == ET:
                    break
                simulate_action(p, a)
                if a == REF:
                    populate_tavern(p, g.rng)
                    ap(p)
            ap(p)
n = len(bc_obs)
print(f"  {n} states, {time.time() - t0:.0f}s CPU")
# Debug: check action distribution
act_counts = {}
for a in bc_act: act_counts[a] = act_counts.get(a, 0) + 1
print(f"  Action distribution: {dict(sorted(act_counts.items())[:10])}")
print(f"  Action range: {min(bc_act)}-{max(bc_act)}")

# ── BC Training ──
bc_act_t = torch.tensor(bc_act, dtype=torch.long)
t0 = time.time()
for ep in range(30):
    perm = np.random.permutation(n)
    ls = 0.0
    ct = 0
    for bi in range(0, n, 256):
        idxs = perm[bi:min(bi + 256, n)]
        B = len(idxs)
        es = torch.zeros(B, N, 8, device=DEVICE)
        em = torch.zeros(B, N, dtype=torch.bool, device=DEVICE)
        eg = torch.zeros(B, N, dtype=torch.long, device=DEVICE)
        ci = torch.zeros(B, N, dtype=torch.long, device=DEVICE)
        gf = torch.zeros(B, 16, device=DEVICE)
        hf = torch.zeros(B, 12, device=DEVICE)
        of_ = torch.zeros(B, 7, 12, device=DEVICE)
        hif = torch.zeros(B, 4, 8, device=DEVICE)
        for j, i in enumerate(idxs):
            o = bc_obs[i]
            es[j] = torch.from_numpy(o['entity_stats'][:N])
            em[j] = torch.from_numpy(o['entity_mask'][:N])
            eg[j] = torch.from_numpy(o['entity_groups'][:N])
            ci[j] = torch.from_numpy(o['card_indices'][:N])
            gf[j] = torch.from_numpy(o['global_features'][:16])
            hf[j] = torch.from_numpy(o['hero_features'][:12])
            of_[j] = torch.from_numpy(o.get('opponent_features', np.zeros((7, 12), dtype=np.float32)))
            hif[j] = torch.from_numpy(o.get('history_features', np.zeros((4, 8), dtype=np.float32)))
        bt = {'entity_stats': es, 'entity_mask': em, 'entity_groups': eg, 'card_indices': ci,
              'global_features': gf, 'hero_features': hf, 'opponent_features': of_, 'history_features': hif}
        out = model(bt)
        tl = out['type_logits']
        ps = out['pointer_scores']
        batch_a = bc_act_t[idxs]
        batch_at = torch.tensor([d2h(int(a))[0] for a in batch_a], dtype=torch.long, device=DEVICE)
        # Safety: clamp type indices to [0,7]
        batch_at = batch_at.clamp(0, 7)
        type_lp = F.log_softmax(tl, dim=-1).gather(1, batch_at.unsqueeze(1)).squeeze(1)
        ptr_s = torch.tensor([d2h(int(a))[1] if d2h(int(a))[0] in (0, 1, 2) else -1 for a in batch_a], device=DEVICE)
        pv = (ptr_s >= 0).float()
        pi = ptr_s.clamp(0, 23)  # pointer range is 0-23
        ptr_lp = F.log_softmax(ps, dim=-1).gather(1, pi.unsqueeze(1)).squeeze(1) * pv
        # Only add pointer for BUY/SELL/PLAY
        # Only use type loss for BC — pointer loss needs proper mask
        ploss = -type_lp.mean()
        if ep == 0 and ct == 0:
            print(f"  DEBUG: batch_at range={batch_at.min().item()}-{batch_at.max().item()}")
            print(f"  DEBUG: type_lp range={type_lp.min().item():.3f}-{type_lp.max().item():.3f}")
            print(f"  DEBUG: ptr_lp range={ptr_lp.min().item():.3f}-{ptr_lp.max().item():.3f}")
            print(f"  DEBUG: ploss={ploss.item():.3f}")
        opt.zero_grad()
        ploss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        ls += ploss.item()
        ct += 1
    if ep % 10 == 0:
        print(f"  ep {ep:3d}: loss={ls / max(ct, 1):.4f}")
torch.cuda.synchronize()
print(f"  BC done, {time.time() - t0:.0f}s GPU")

# ── Eval ──
bc_scores = []
rnd_scores = []
for gi in range(6):
    g = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=SEED * 9999 + gi)
    for turn in range(1, 11):
        for p in g.players:
            p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
            p.set_tag(GameTag.HERO_POWER_USED, False)
            p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
            c = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
            if c > 0:
                p.set_tag(GameTag.TAVERN_UPGRADE_COST, c - 1)
        for p in g.players:
            g.refresh_tavern(p)
            ap(p)
        for idx in range(8):
            p = g.players[idx]
            for _ in range(6):
                mask = build_action_mask(g, p)
                legal = [a for a in range(50) if mask[a]]
                if not legal:
                    break
                if idx < 4:
                    # BC policy: sample from model output
                    obs = build_observation_v2(g, p)
                    bt = {
                        'entity_stats': torch.from_numpy(obs['entity_stats'][:N]).unsqueeze(0).to(DEVICE),
                        'entity_mask': torch.from_numpy(obs['entity_mask'][:N]).unsqueeze(0).to(DEVICE),
                        'entity_groups': torch.from_numpy(obs['entity_groups'][:N]).unsqueeze(0).to(DEVICE),
                        'card_indices': torch.from_numpy(obs['card_indices'][:N]).unsqueeze(0).to(DEVICE),
                        'global_features': torch.from_numpy(obs['global_features'][:16]).unsqueeze(0).to(DEVICE),
                        'hero_features': torch.from_numpy(obs['hero_features'][:12]).unsqueeze(0).to(DEVICE),
                        'opponent_features': torch.from_numpy(obs.get('opponent_features', np.zeros((7, 12), dtype=np.float32))).unsqueeze(0).to(DEVICE),
                        'history_features': torch.from_numpy(obs.get('history_features', np.zeros((4, 8), dtype=np.float32))).unsqueeze(0).to(DEVICE),
                    }
                    out = model(bt)
                    tl = out['type_logits']
                    ps = out['pointer_scores']
                    type_probs = F.softmax(tl, dim=-1)
                    type_probs[:, [a for a in range(8) if not any(a == d2h(l)[0] for l in legal)]] = 0
                    at = int(type_probs.argmax(dim=-1).item())
                    if at in (0, 1, 2):
                        start = 0 if at == 0 else 7 if at == 1 else 14
                        end = 7 if at == 0 else 14 if at == 1 else 24
                        ptr_probs = F.softmax(ps[0, start:end], dim=-1)
                        sl = int(ptr_probs.argmax().item())
                        a = BUY_O + sl if at == 0 else (7 + sl if at == 1 else PLAY_O + sl)
                    else:
                        a = {3: REF, 4: UPG, 5: FRZ, 6: HP, 7: ET}.get(at, ET)
                else:
                    a = int(np.random.choice(legal))
                if a == ET:
                    break
                simulate_action(p, a)
                if a == REF:
                    populate_tavern(p, g.rng)
                    ap(p)
            ap(p)
    scores = [compute_board_score_v2(p).total for p in g.players]
    bc_scores.extend(scores[:4])
    rnd_scores.extend(scores[4:8])
    if gi < 2:
        print(f"  G{gi+1}: BC={[f'{s:.0f}' for s in scores[:4]]}  RND={[f'{s:.0f}' for s in scores[4:]]}")
        # Show detailed board for best BC and best random player
        best_bc_idx = np.argmax(scores[:4])
        best_rnd_idx = 4 + np.argmax(scores[4:])
        for label, idx in [("Best BC", best_bc_idx), ("Best RND", best_rnd_idx)]:
            p = g.players[idx]
            board = [m for m in p.board if not m.dead]
            raw_sum = sum(m.atk + m.health for m in board)
            detail = ", ".join(f"{m.data.name}({m.atk}/{m.health}T{m.tech_level})" for m in board[:8])
            print(f"    {label}(P{idx}): tier={p.tavern_tier} gold={p.gold} board=[{detail}]")
            print(f"      raw_sum={raw_sum}, minions={len(board)}, score={scores[idx]:.1f}")

print(f"\n── 10-Turn Results ({len(bc_scores)} BC + {len(rnd_scores)} RND boards) ──")
print(f"  BC-trained: avg_score={np.mean(bc_scores):.2f} max={max(bc_scores):.0f}")
print(f"  Random:     avg_score={np.mean(rnd_scores):.2f} max={max(rnd_scores):.0f}")
bc_raw = np.mean(bc_scores)
rnd_raw = np.mean(rnd_scores)
print(f"  Gap: {bc_raw-rnd_raw:+.2f}  {'✓ BC POLICY BETTER' if bc_raw > rnd_raw + 0.5 else '→ similar'}")
