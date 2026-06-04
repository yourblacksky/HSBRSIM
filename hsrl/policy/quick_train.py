"""Quick training loop — tracks board_score improvement per round."""
import sys, time, numpy as np, torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0,'/home/glt/HrSRL')
import hsrl.cards.minions, hsrl.cards.heroes, hsrl.cards.spells
from hsrl.core.card_db import CARDS; from hsrl.core.game import Game
from hsrl.core.enums import GameTag, CardType
from hsrl.rl_env.observation import build_observation_v2
from hsrl.rl_env.reward.board_score import compute_board_score_v2
from hsrl.env.action import build_action_mask, END_TURN, REFRESH
from hsrl.agents.agent_utils import save_player_state, restore_player_state, simulate_action, populate_tavern
from hsrl.policy.model_5m import ScaledModel, EMBED_DIM

SEED=42; T=10; GAMES=10; ROUNDS=10; DEVICE='cuda'
torch.manual_seed(SEED); np.random.seed(SEED)
torch.backends.cudnn.benchmark=True

def ap(p):
    bc=len([m for m in p.board if not m.dead])
    for m in [c for c in p.hand if c.get_tag(GameTag.CARDTYPE,0)==CardType.MINION]:
        if bc>=7: break; p.hand.remove(m); p.board.append(m); bc+=1

print("="*60)
print(f"  QUICK TRAIN: {ROUNDS}r × {GAMES}g, T={T}, 5.25M params")
print("="*60)

model=ScaledModel().to(DEVICE)
opt=torch.optim.Adam(model.parameters(),lr=3e-4)
print(f"Model: {model.count_parameters()/1e6:.2f}M | GPU: {torch.cuda.get_device_name(0)}")

def value_guided_action(model, game, player):
    """Select best action using trained value head."""
    mask=build_action_mask(game,player)
    legal=[a for a in range(50) if mask[a]]
    if not legal: return END_TURN
    saved=save_player_state(player); qv={}
    for a in legal:
        restore_player_state(player,saved)
        if not simulate_action(player,a): continue
        if a==REFRESH:populate_tavern(player,game.rng);ap(player)
        obs=build_observation_v2(game,player)
        N=37; B=1
        bt={
            'entity_stats':torch.from_numpy(obs['entity_stats'][:N]).unsqueeze(0).to(DEVICE),
            'entity_mask':torch.from_numpy(obs['entity_mask'][:N]).unsqueeze(0).to(DEVICE),
            'entity_groups':torch.from_numpy(obs['entity_groups'][:N]).unsqueeze(0).to(DEVICE),
            'card_indices':torch.from_numpy(obs['card_indices'][:N]).unsqueeze(0).to(DEVICE),
            'global_features':torch.from_numpy(obs['global_features'][:16]).unsqueeze(0).to(DEVICE),
            'hero_features':torch.from_numpy(obs['hero_features'][:12]).unsqueeze(0).to(DEVICE),
            'opponent_features':torch.from_numpy(obs.get('opponent_features',np.zeros((7,12),dtype=np.float32))).unsqueeze(0).to(DEVICE),
            'history_features':torch.from_numpy(obs.get('history_features',np.zeros((4,8),dtype=np.float32))).unsqueeze(0).to(DEVICE),
        }
        with torch.no_grad():
            out=model(bt); qv[a]=out['value']['value'].item()
    restore_player_state(player,saved)
    valid={a:q for a,q in qv.items() if q>-1e9}
    return max(valid.items(),key=lambda x:x[1])[0] if valid else END_TURN

history=[]
for rnd in range(ROUNDS):
    t0=time.time()
    
    # ── Collect training data ──
    all_obs=[]; all_sc=[]
    for gi in range(GAMES):
        g=Game.create_game(['BG20_HERO_100']*8,CARDS,seed=SEED*100+rnd*GAMES+gi)
        for turn in range(1,8):
            for p in g.players:
                p.set_tag(GameTag.GOLD,int(min(3+turn-1,10)))
                p.set_tag(GameTag.HERO_POWER_USED,False);p.set_tag(GameTag.SECONDARY_HERO_POWER_USED,False)
                c=p.get_tag(GameTag.TAVERN_UPGRADE_COST,0)
                if c>0:p.set_tag(GameTag.TAVERN_UPGRADE_COST,c-1)
            for p in g.players:g.refresh_tavern(p);ap(p)
            for idx in range(8):
                p=g.players[idx]
                for _ in range(3):
                    mask=build_action_mask(g,p);legal=[a for a in range(50) if mask[a]]
                    if not legal: break
                    all_obs.append(build_observation_v2(g,p))
                    a=int(np.random.choice(legal))
                    if a==END_TURN: break
                    simulate_action(p,a)
                    if a==REFRESH:populate_tavern(p,g.rng);ap(p)
                ap(p)
        scores=[compute_board_score_v2(p).total for p in g.players]
        # Assign scores to this game's observations
        obs_per_game=len(all_obs)-len(all_sc)
        per_player=max(1,obs_per_game//8)
        for s in scores: all_sc.extend([float(s)]*per_player)
    all_sc=all_sc[:len(all_obs)]
    while len(all_sc)<len(all_obs): all_sc.append(0.0)
    
    dc=time.time()-t0; n=len(all_obs); N=37
    
    # ── GPU train ──
    es=torch.zeros(n,N,8,device=DEVICE); em=torch.zeros(n,N,dtype=torch.bool,device=DEVICE)
    eg=torch.zeros(n,N,dtype=torch.long,device=DEVICE); ci=torch.zeros(n,N,dtype=torch.long,device=DEVICE)
    gf=torch.zeros(n,16,device=DEVICE); hf=torch.zeros(n,12,device=DEVICE)
    of_=torch.zeros(n,7,12,device=DEVICE); hif=torch.zeros(n,4,8,device=DEVICE)
    for j,o in enumerate(all_obs):
        es[j]=torch.from_numpy(o['entity_stats'][:N]); em[j]=torch.from_numpy(o['entity_mask'][:N])
        eg[j]=torch.from_numpy(o['entity_groups'][:N]); ci[j]=torch.from_numpy(o['card_indices'][:N])
        gf[j]=torch.from_numpy(o['global_features'][:16]); hf[j]=torch.from_numpy(o['hero_features'][:12])
        of_[j]=torch.from_numpy(o.get('opponent_features',np.zeros((7,12),dtype=np.float32)))
        hif[j]=torch.from_numpy(o.get('history_features',np.zeros((4,8),dtype=np.float32)))
    sc_t=torch.tensor(all_sc,device=DEVICE,dtype=torch.float32)/10.0
    bt={'entity_stats':es,'entity_mask':em,'entity_groups':eg,'card_indices':ci,
        'global_features':gf,'hero_features':hf,'opponent_features':of_,'history_features':hif}
    
    t1=time.time()
    for ep in range(30):
        perm=torch.randperm(n,device=DEVICE)
        for bi in range(0,n,512):
            idxs=perm[bi:min(bi+512,n)]; BA=len(idxs)
            b2={k:v[idxs] for k,v in bt.items()}
            out=model(b2); vo=out['value']
            loss=F.mse_loss(vo['value'].squeeze(-1),sc_t[idxs])
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); opt.step()
    torch.cuda.synchronize(); dg=time.time()-t1
    
    # ── Eval: value-guided 10-turn board building ──
    eval_scores=[]
    for gi in range(4):
        g=Game.create_game(['BG20_HERO_100']*8,CARDS,seed=SEED*8888+rnd*4+gi)
        for turn in range(1,T+1):
            for p in g.players:
                p.set_tag(GameTag.GOLD,int(min(3+turn-1,10)))
                p.set_tag(GameTag.HERO_POWER_USED,False);p.set_tag(GameTag.SECONDARY_HERO_POWER_USED,False)
                c=p.get_tag(GameTag.TAVERN_UPGRADE_COST,0)
                if c>0:p.set_tag(GameTag.TAVERN_UPGRADE_COST,c-1)
            for p in g.players:g.refresh_tavern(p);ap(p)
            for idx in range(8):
                p=g.players[idx]
                for _ in range(6):
                    mask=build_action_mask(g,p);legal=[a for a in range(50) if mask[a]]
                    if not legal: break
                    a=value_guided_action(model,g,p)
                    if a==END_TURN: break
                    simulate_action(p,a)
                    if a==REFRESH:populate_tavern(p,g.rng);ap(p)
                ap(p)
        scores=[compute_board_score_v2(p).total for p in g.players]
        eval_scores.extend(scores)
    
    bs_avg=np.mean(eval_scores); bs_max=max(eval_scores)
    history.append((rnd+1,bs_avg,bs_max,n,dc,dg))
    print(f"  R{rnd+1:2d}: score={bs_avg:5.1f} max={bs_max:5.0f} | CPU{dc:.0f}s+GPU{dg:.0f}s | {n}st")

print(f"\n{'='*60}")
print(f"  TRAINING HISTORY")
print(f"  {'Rd':>3s} {'Avg':>6s} {'Max':>6s}")
for r,avg,mx,_,_,_ in history:
    print(f"  {r:3d} {avg:6.1f} {mx:6.0f}")

scores=[s for _,s,_,_,_,_ in history]
f3=np.mean(scores[:3]); l3=np.mean(scores[-3:])
print(f"\n  First3: {f3:.1f}  Last3: {l3:.1f}  Δ: {l3-f3:+.1f}")
print(f"  {'↑ IMPROVING' if l3>f3+0.3 else '→ FLAT'}")
