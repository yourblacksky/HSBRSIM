"""Iterative BC Training — multi-round improvement on single seed (42).

Uses SearchAgent-style strong heuristic as Round 0 teacher:
  - Q-score greedy buy (highest atk+health)
  - Fixed upgrade curve per turn
  - Sell weakest → buy stronger when board full
  - Smart refresh only when actionable
  - 15-turn games to allow scaling comp discovery
"""
import sys, time, numpy as np, torch, torch.nn.functional as F
sys.path.insert(0, '/home/glt/HrSRL')
import hsrl.cards.minions, hsrl.cards.heroes, hsrl.cards.spells
from hsrl.core.card_db import CARDS
from hsrl.core.game import Game
from hsrl.core.enums import GameTag, CardType
from hsrl.rl_env.observation import build_observation_v2
from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.env.action import build_action_mask, END_TURN, REFRESH, BUY_OFFSET, SELL_OFFSET, UPGRADE
from hsrl.agents.agent_utils import simulate_action, populate_tavern
from hsrl.policy.model_5m import ScaledModel

BUY_O, SELL_O, PLAY_O, REF, UPG, FRZ, HP, ET = 0, 7, 14, 24, 25, 26, 27, 28

# Expected tavern tier by turn (standard curve: 2→T2, 5→T3, 7→T4, 9→T5, 11→T6)
_EXPECTED_TIER = {1:1, 2:2, 3:2, 4:2, 5:3, 6:3, 7:4, 8:4, 9:5, 10:5, 11:6, 12:6, 13:6, 14:6, 15:6}

def d2h(a):
    if BUY_O <= a < BUY_O + 7: return (0, a - BUY_O)
    if SELL_O <= a < SELL_O + 7: return (1, a - SELL_O)
    if PLAY_O <= a < PLAY_O + 10: return (2, a - PLAY_O)
    if a == REF: return (3, 0)
    if a == UPG: return (4, 0)
    if a == FRZ: return (5, 0)
    if a == HP: return (6, 0)
    return (7, 0)

def ap(p):
    bc = len([m for m in p.board if not m.dead])
    for m in [c for c in p.hand if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION]:
        if bc >= 7: break
        p.hand.remove(m); p.board.append(m); bc += 1

def heuristic_action(game, player):
    """SearchAgent-style strong heuristic: Q-score buy, curve upgrade, sell-weak-buy-strong."""
    mask = build_action_mask(game, player)
    legal = [a for a in range(50) if mask[a]]
    if not legal: return ET

    board_count = len([m for m in player.board if not m.dead])
    buy_actions = [a for a in legal if BUY_O <= a < BUY_O + 7]
    sell_actions = [a for a in legal if SELL_O <= a < SELL_O + 7]

    # Priority 1: Auto-play minions from hand
    for a in legal:
        if PLAY_O <= a < PLAY_O + 10:
            slot = a - PLAY_O
            if slot < len(player.hand):
                card = player.hand[slot]
                if card.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                    return a

    # Priority 2: Buy best minion (Q-score = atk + health) when board not full
    if board_count < 7 and buy_actions:
        best_buy, best_score = None, -1
        for a in buy_actions:
            slot = a - BUY_O
            if slot < len(player.tavern):
                e = player.tavern[slot]
                if e.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                    s = e.atk + e.health
                    if s > best_score:
                        best_score = s
                        best_buy = a
        if best_buy is not None:
            return best_buy

    # Priority 3: Upgrade on curve
    expected = _EXPECTED_TIER.get(game.turn, player.tavern_tier)
    if player.tavern_tier < expected and UPG in legal:
        return UPG

    # Priority 4: Sell weakest + buy stronger when board full
    if board_count >= 7 and buy_actions and sell_actions:
        living = [m for m in player.board if not m.dead]
        weakest_idx = min(range(len(living)),
                          key=lambda i: living[i].atk + living[i].health)
        best_buy_score = -1
        for a in buy_actions:
            slot = a - BUY_O
            if slot < len(player.tavern):
                e = player.tavern[slot]
                if e.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                    s = e.atk + e.health
                    if s > best_buy_score:
                        best_buy_score = s
        weakest_score = living[weakest_idx].atk + living[weakest_idx].health
        if best_buy_score > weakest_score:
            return SELL_O + weakest_idx

    # Priority 5: Smart refresh — only if can buy after
    if REF in legal:
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        min_cost = min(
            (e.get_tag(GameTag.COST, 3) for e in player.tavern
             if e.get_tag(GameTag.CARDTYPE, 0) in (CardType.MINION, CardType.SPELL)),
            default=99)
        if free > 0 or (player.gold >= 1 + min_cost and board_count < 7):
            return REF

    # Fallback: random safe action (exclude sells to avoid blind selling)
    safe = [a for a in legal if not (SELL_O <= a < SELL_O + 7) and a != ET]
    return int(np.random.choice(safe)) if safe else ET

@torch.no_grad()
def bc_action(model, game, player, N, DEVICE):
    mask = build_action_mask(game, player)
    legal = [a for a in range(50) if mask[a]]
    if not legal: return ET
    obs = build_observation_v2(game, player)
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
    type_probs = F.softmax(tl, dim=-1)
    legal_types = set(d2h(a)[0] for a in legal if a != ET)
    for t in range(8):
        if t not in legal_types: type_probs[0, t] = 0
    at = int(type_probs.argmax(dim=-1).item())
    if at in (0, 1, 2):
        ps = out['pointer_scores']
        start = 0 if at == 0 else 7 if at == 1 else 14
        end = 7 if at == 0 else 14 if at == 1 else 24
        ptr_probs = F.softmax(ps[0, start:end], dim=-1)
        sl = int(ptr_probs.argmax().item())
        a = BUY_O + sl if at == 0 else (7 + sl if at == 1 else PLAY_O + sl)
    else:
        a = {3: REF, 4: UPG, 5: FRZ, 6: HP, 7: ET}.get(at, ET)
    if a not in legal: return int(np.random.choice(legal))
    return a

def collect_data(games, action_fn, seed_offset, N):
    obs_list, act_list = [], []
    for gi in range(games):
        g = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=42 * 100 + seed_offset + gi)
        for turn in range(1, 16):
            for p in g.players:
                p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
                p.set_tag(GameTag.HERO_POWER_USED, False)
                p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
                c = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
                if c > 0: p.set_tag(GameTag.TAVERN_UPGRADE_COST, c - 1)
            for p in g.players: g.refresh_tavern(p); ap(p)
            for idx in range(8):
                p = g.players[idx]
                for _ in range(6):
                    mask = build_action_mask(g, p)
                    legal = [a for a in range(50) if mask[a]]
                    if not legal: break
                    obs_list.append(build_observation_v2(g, p))
                    a = action_fn(g, p)
                    act_list.append(a)
                    if a == ET: break
                    simulate_action(p, a)
                    if a == REF: populate_tavern(p, g.rng); ap(p)
                ap(p)
    return obs_list, act_list

def train_bc(model, opt, obs_list, act_list, N, DEVICE, epochs=30):
    bc_act_t = torch.tensor(act_list, dtype=torch.long)
    n = len(obs_list)
    for ep in range(epochs):
        perm = np.random.permutation(n)
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
                o = obs_list[i]
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
            batch_a = bc_act_t[idxs]
            batch_at = torch.tensor([d2h(int(a))[0] for a in batch_a], dtype=torch.long, device=DEVICE).clamp(0, 7)
            type_lp = F.log_softmax(tl, dim=-1).gather(1, batch_at.unsqueeze(1)).squeeze(1)
            ploss = -type_lp.mean()
            opt.zero_grad()
            ploss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

def eval_round(model, rnd, N, DEVICE, eval_games=4):
    bc_sc, rnd_sc, bc_raw, rnd_raw, bc_cnt, rnd_cnt, bc_tier, rnd_tier = [], [], [], [], [], [], [], []
    for gi in range(eval_games):
        g = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=42 * 9999 + rnd * eval_games + gi)
        for turn in range(1, 16):
            for p in g.players:
                p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
                p.set_tag(GameTag.HERO_POWER_USED, False)
                p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
                c = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
                if c > 0: p.set_tag(GameTag.TAVERN_UPGRADE_COST, c - 1)
            for p in g.players: g.refresh_tavern(p); ap(p)
            for idx in range(8):
                p = g.players[idx]
                for _ in range(6):
                    mask = build_action_mask(g, p)
                    legal = [a for a in range(50) if mask[a]]
                    if not legal: break
                    a = bc_action(model, g, p, N, DEVICE) if idx < 4 else int(np.random.choice(legal))
                    if a == ET: break
                    simulate_action(p, a)
                    if a == REF: populate_tavern(p, g.rng); ap(p)
                ap(p)
        for idx in range(8):
            bs = compute_board_score_v2(g.players[idx])
            raw = sum(m.atk + m.health for m in g.players[idx].board if not m.dead)
            cnt = len([m for m in g.players[idx].board if not m.dead])
            tier = g.players[idx].tavern_tier
            if idx < 4:
                bc_sc.append(bs.total); bc_raw.append(raw); bc_cnt.append(cnt); bc_tier.append(tier)
            else:
                rnd_sc.append(bs.total); rnd_raw.append(raw); rnd_cnt.append(cnt); rnd_tier.append(tier)
    return bc_sc, rnd_sc, bc_raw, rnd_raw, bc_cnt, rnd_cnt, bc_tier, rnd_tier


SEED = 42; DEVICE = 'cuda'; N = 37; GAMES = 15; ROUNDS = 6
CKPT_DIR = 'checkpoints'
import os; os.makedirs(CKPT_DIR, exist_ok=True)
torch.manual_seed(SEED); np.random.seed(SEED)

model = ScaledModel().to(DEVICE)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
print(f"{model.count_parameters()/1e6:.2f}M | {ROUNDS}r x {GAMES}g | 15-turn games | seed={SEED}")
print("=" * 65)

history = []
for rnd in range(ROUNDS):
    t0 = time.time()
    mode = "HEUR" if rnd == 0 else "BC"

    # Collect data
    fn = heuristic_action if rnd == 0 else lambda g, p: bc_action(model, g, p, N, DEVICE)
    obs_list, act_list = collect_data(GAMES, fn, rnd * 100, N)

    # Train
    train_bc(model, opt, obs_list, act_list, N, DEVICE, epochs=30)
    torch.save(model.state_dict(), f'{CKPT_DIR}/bc_iter_r{rnd}.pt')

    # Eval
    bc_sc, rnd_sc, bc_raw, rnd_raw, bc_cnt, rnd_cnt, bc_tier, rnd_tier = eval_round(model, rnd, N, DEVICE)

    t_bc, t_raw, t_cnt, t_tr = np.mean(bc_sc), np.mean(bc_raw), np.mean(bc_cnt), np.mean(bc_tier)
    u_sc, u_raw, u_cnt, u_tr = np.mean(rnd_sc), np.mean(rnd_raw), np.mean(rnd_cnt), np.mean(rnd_tier)
    dt = time.time() - t0
    history.append((rnd + 1, mode, t_bc, u_sc, t_raw, u_raw, t_cnt, u_cnt, t_tr, u_tr, len(obs_list), dt))
    print(f"  R{rnd+1}[{mode}]: BCsc={t_bc:.1f} raw={t_raw:.0f} cnt={t_cnt:.1f} T{t_tr:.1f} | "
          f"Rsc={u_sc:.1f} raw={u_raw:.0f} | {len(obs_list)}st {dt:.0f}s")

print(f"\n{'='*65}")
print(f"  ITERATIVE TRAINING HISTORY")
print(f"{'='*65}")
print(f"  {'Rd':>3s} {'Mode':>4s} {'BCsc':>5s} {'BCraw':>6s} {'BCcnt':>5s} {'BCt':>4s} {'Rsc':>5s} {'Rraw':>6s} {'Gap':>5s}")
for r, mode, tsc, usc, trw, urw, tcn, ucn, ttr, utr, ns, dt in history:
    print(f"  {r:3d} {mode:>4s} {tsc:5.1f} {trw:6.0f} {tcn:5.1f} {ttr:4.1f} {usc:5.1f} {urw:6.0f} {tsc-usc:+5.1f}")

# Show best board from final round
g = Game.create_game(['BG20_HERO_100'] * 8, CARDS, seed=42 * 9999 + (ROUNDS - 1) * 4)
for turn in range(1, 16):
    for p in g.players:
        p.set_tag(GameTag.GOLD, int(min(3 + turn - 1, 10)))
        p.set_tag(GameTag.HERO_POWER_USED, False); p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
        c = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
        if c > 0: p.set_tag(GameTag.TAVERN_UPGRADE_COST, c - 1)
    for p in g.players: g.refresh_tavern(p); ap(p)
    for idx in range(8):
        p = g.players[idx]
        for _ in range(6):
            mask = build_action_mask(g, p); legal = [a for a in range(50) if mask[a]]
            if not legal: break
            a = bc_action(model, g, p, N, DEVICE) if idx < 4 else int(np.random.choice(legal))
            if a == ET: break
            simulate_action(p, a)
            if a == REF: populate_tavern(p, g.rng); ap(p)
        ap(p)

print(f"\n── Best Boards (Round {ROUNDS}) ──")
for label, idxs in [("BC-trained", range(4)), ("Random", range(4, 8))]:
    best_idx = max(idxs, key=lambda i: compute_board_score_v2(g.players[i]).total)
    p = g.players[best_idx]
    board = [m for m in p.board if not m.dead]
    raw = sum(m.atk + m.health for m in board)
    detail = ", ".join(f"{m.data.name}({m.atk}/{m.health}T{m.tech_level})" for m in board[:8])
    print(f"  {label} P{best_idx}: tier={p.tavern_tier} board=[{detail}]")
    print(f"    raw={raw}, cnt={len(board)}, score={compute_board_score_v2(p).total:.1f}")
