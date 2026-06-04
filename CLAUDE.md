# HrSRL — 酒馆战棋强化学习环境

## 项目概述

HrSRL 是一个干净、可扩展的 Python 引擎，用于模拟《炉石传说》酒馆战棋**单打（Solo）**模式。

- **机制准确性**：每个关键词、触发器和战斗规则与官方描述一致
- **强化学习就绪**：快速模拟、完整状态可观察性、多智能体环境
- **数据驱动开发**：卡牌从结构化定义注册，定义从自然语言卡牌文本推导

> **范围限制：仅支持单打模式。双打（Duos）模式不在项目范围内。**

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 卡牌数据 | hsdata (CardDefs.xml) → `data/` JSON |
| 神经网络 | PyTorch |
| RL 框架 | Gymnasium + 自定义 PPO/MCTS |
| 测试 | pytest (772 passed, 1 skipped) |

## 项目结构

```
HrSRL/
├── docs/                              # 规则手册 + Demo 输出
│   ├── BATTLEGROUNDS_RULES.md         # ★ 权威规则手册
│   ├── MECHANICS_REFERENCE.md         # ★ 机制实现参考
│   ├── CARD_REGISTRATION_GUIDE.md     # ★ 卡牌注册指南
│   └── demo_*.md                      # Demo 对局审计输出
│
├── data/                              # 卡牌数据 + 轨迹
│   ├── bg_cards.json                  # 全量 BG 卡牌 (5,189 张)
│   ├── bg_pool_minions.json           # 可购买随从池
│   ├── bg_pool_spells.json            # 可购买法术池
│   ├── bg_heroes.json                 # 英雄定义 (119 位)
│   ├── bg_hero_powers.json            # 英雄技能 (164 个)
│   ├── bg_trinkets.json               # 饰品 (326 个)
│   ├── bg_anomalies.json              # 异变 (104 个)
│   ├── bg_quest_rewards.json          # 任务奖励 (73 个)
│   ├── combat_pairs/                  # 战斗对训练数据
│   └── trajectories/                  # 轨迹对手数据 (1,100+)
│
├── hsrl/                              # 主代码包
│   ├── core/                          # ★ 游戏引擎核心
│   │   ├── enums.py                   # GameTag (310+), CardType, Race, Zone, Step
│   │   ├── entity.py                  # BaseEntity — 标签 + buff + deep snapshot
│   │   ├── player.py                  # Player — 金币/血量/board/hand/tavern
│   │   ├── actions.py                 # ★ Action 系统 (60+ Action 类)
│   │   ├── game.py                    # ★ Game 引擎 — 回合/战斗/快照/战斗记忆
│   │   ├── minion_pool.py             # MinionPool — 共享随从池 + 种族过滤
│   │   ├── spell_pool.py              # SpellPool — 共享法术池
│   │   └── card_db.py                 # CardDB + register_card()
│   ├── cards/                         # 卡牌定义 (805 CORRECT, 15 OOS)
│   │   ├── minions/                   # 随从 (pool, scripts, tokens)
│   │   ├── heroes/                    # 英雄 (pool, scripts)
│   │   ├── spells/                    # 法术
│   │   ├── rewards/                   # 任务奖励
│   │   ├── trinkets/                  # 饰品
│   │   └── anomalies/                 # 异变
│   ├── env/                           # RL 环境 (legacy, gitignored)
│   │   ├── action.py                  # Discrete(50) 动作空间 + mask + 解码
│   │   ├── observation.py             # 观察空间 (374-dim flat)
│   │   ├── reward.py                  # 奖励 (v4 per-action + v5 dense)
│   │   └── multi_agent_env.py         # 多智能体环境 + 轨迹对手
│   ├── rl_env/                        # ★ 新一代 RL 环境 (entity-centric)
│   │   ├── action/                    # 分层动作: 原子动作 + 语法 + 宏观选项
│   │   ├── observation/               # ObservationV2: 37-entity token 布局
│   │   │   ├── entity_schema.py       # TokenGroup, 槽位偏移, 特征维度定义
│   │   │   ├── observation_v2.py      # build_observation_v2() — 37 实体槽
│   │   │   └── opponent_public_encoder.py
│   │   ├── reward/
│   │   │   └── board_score.py         # compute_board_score_v2() — 多维度场面评分
│   │   ├── core/                      # RL 状态管理
│   │   ├── envs/                      # BoardBuildingEnv, TurnRecruitEnv
│   │   ├── teachers/                  # 教师策略
│   │   └── data/                      # 回合数据集
│   ├── policy/                        # ★ Entity-Token Transformer 策略 (5.25M)
│   │   ├── model_5m.py                # ScaledModel: d=256, h=4, 6层 Transformer
│   │   ├── transformer.py             # EntityTransformer — MHA over entity tokens
│   │   ├── heads.py                   # HierarchicalActionHead: type + pointer
│   │   ├── value_head.py              # DistributionalValueHead: P(rank) → V(s)
│   │   ├── entity_tokenizer_v2.py     # 37-slot tokenizer w/ card embeddings
│   │   ├── bc_train.py                # Phase 0: BC from heuristic teacher
│   │   ├── iter_train.py              # ★ 迭代 BC: 多轮 self-improvement
│   │   ├── gpu_train.py               # GPU 训练脚本
│   │   └── quick_train.py             # 快速训练脚本
│   ├── agents/                        # AI 智能体
│   │   ├── search_agent.py            # ★ 混合 SearchAgent (avg_rank 2.17)
│   │   ├── az_agent.py                # ★ AlphaZero MCTS Agent
│   │   ├── agent_utils.py             # 动作模拟 + 酒馆刷新工具
│   │   ├── heuristic_demo.py          # 全启发式 8 人对战 demo
│   │   ├── self_play_demo.py          # 8 混合 agent 自对弈 demo
│   │   └── agent_vs_heuristic_demo.py # 1 agent vs 7 启发式审计 demo
│   ├── advisor/                       # HDT 插件 + 数据收集
│   │   ├── overlay_protocol.py        # C# ↔ Python 协议
│   │   ├── state_mapper.py            # HDT 状态 → 观察向量
│   │   ├── server.py                  # WebSocket 服务器
│   │   ├── collector.py               # 真实对局数据收集
│   │   └── trajectory_converter.py    # HDT 数据 → Trajectory 格式
│   ├── trajectory/                    # 轨迹对手系统
│   │   ├── record.py                  # MinionSnapshot, TurnSnapshot, Trajectory
│   │   ├── generate.py                # 批量生成轨迹
│   │   ├── opponent.py                # 轨迹对手加载 + 棋盘注入
│   │   ├── group.py                   # 按种族兼容性分组
│   │   └── pool.py                    # 轨迹池采样
│   ├── train/                         # 训练脚本 (legacy, gitignored)
│   │   ├── network.py                 # Dual-Head Network (policy + value, 374-dim)
│   │   ├── board_eval.py              # BoardEvalNetwork — 战斗预测 98.4%
│   │   ├── combat_data.py             # 战斗数据收集
│   │   ├── game_value.py              # GameValueNetwork v2 (61-dim)
│   │   ├── game_value_sp.py           # GameValueNetwork v4 (397-dim POMDP)
│   │   ├── value_dense.py             # DenseValueNetwork
│   │   ├── bc_collector_v3.py         # BC 数据收集
│   │   ├── bc_trainer_v3.py           # BC 策略训练
│   │   ├── ppo_trainer_v2.py          # PPO 微调
│   │   └── self_play_trainer.py       # 自对弈 PPO 训练器
│   └── tests/                         # 测试 (772 passed, 1 skipped)
│
├── hsrl_advisor/plugin/               # HDT C# 插件
│   ├── GameStateExtractor.cs          # 游戏状态提取 (含 card_id)
│   └── AdviserPlugin.cs               # 插件入口
├── checkpoints/                       # 模型检查点
├── hsdata/                            # HearthSim CardDefs.xml (submodule)
└── CLAUDE.md                          # 本文件
```

## 核心设计哲学

1. **Action 驱动**: 所有状态变更通过 `Action → queue → broadcast → resolve` 流程
2. **语义精确性**: 卡牌只有 CORRECT 或 DEFERRED，禁止"简化实现"
3. **标签可见性**: 所有属性在 `core/enums.py` 的 GameTag 中显式声明
4. **文档冻结**: 外部规则冻结在 `docs/` 中，不依赖网络访问

## 当前 Agent 性能 (干净数据, vs 7 启发式对手, 30 局)

| Agent | avg_rank | top4% | 时间/局 | 方法 |
|-------|----------|-------|---------|------|
| **混合 SearchAgent** | **2.17** | 100% | 1.1s | 启发式优先级 + GameValue fallback |
| BC 策略 (argmax) | 2.23 | 100% | 1.4s | 模仿混合 agent |
| PPO + GV | 2.23 | 100% | 1.4s | BC → PPO 微调 |
| AZ MCTS + GV | 2.30 | 100% | 21s | 200 sims PUCT + GameValue |
| AZ MCTS + BoardEval | 2.30 | 100% | 139s | 200 sims PUCT + 战斗预测 |
| AZ MCTS + DenseValue | 2.30 | 100% | 27s | 200 sims PUCT + dense value |
| PPO 从头训练 | 7.81 | 0% | — | 随机初始化 |
| 纯启发式基线 | ~4.5 | ~50% | 0.4s | Q-score greedy |

**所有 agent 在弱基线内部比较** — 启发式对手本身水平有限（avg_rank ~4.5 在 8 个同样弱的对手中）。真正突破需要真人轨迹对手或更强的价值信号。

## 关键检查点

| 文件 | 说明 |
|------|------|
| `checkpoints/board_eval_v3_clean.pt` | BoardEval — 战斗预测 98.4% accuracy |
| `checkpoints/game_value_sp_iter1.pt` | GameValue v4 — terminal placement 教师, val_mae 0.177 |
| `checkpoints/game_value_sp_bootstrap.pt` | GameValue v4 bootstrap |
| `checkpoints/game_value_sp_iter2.pt` | GameValue v4 iter2 |
| `checkpoints/game_value_v5_diverse.pt` | GameValue v5 — 噪声数据训练 |
| `checkpoints/value_dense.pt` | DenseValue — 存活+棋盘强度 dense reward |
| `checkpoints/bc_search_agent.pt` | BC 策略 — 模仿混合 agent, val_acc 67.4% |
| `checkpoints/ppo_finetuned.pt` | PPO 微调策略 |
| `checkpoints/ppo_gv.pt` | PPO + GameValue 策略 |
| `checkpoints/bc_iter_r0.pt` ~ `bc_iter_r5.pt` | 迭代 BC 模型 (强启发式→BC, 15 回合, 5.25M 参数) |

## 混合 SearchAgent 架构

```
act(game, player):
  1. 处理 pending choices / trinket offers
  2. Auto-play 手牌中的随从
  3. Q-score 购买 (棋盘未满时买最强随从)
  4. 曲线升级 (低于预期等级时升级)
  5. 卖弱买强 (棋盘满时替换)
  6. 有用刷新 (仅当刷新后能购买时)
  7. Value network fallback + epsilon 探索
```

## AZ MCTS Agent 架构

```
act(game, player):
  1. 处理 pending events
  2. Auto-play 手牌随从
  3. 构建 root 节点 (snapshot_player_state)
  4. 预展开 root (所有合法动作)
  5. N 次模拟:
     a. SELECT: PUCT 下降 (Q + c_puct * P * sqrt(N_parent) / (1+N_child))
     b. EXPAND: 为叶子节点创建子节点
     c. EVALUATE: DenseValue 或 GameValue 或 BoardEval 战斗预测
     d. BACKUP: 反向传播值
  6. 返回访问次数最多的动作
```

## 奖励函数

### v4: Per-action recruit + combat + terminal
- 备战增量: (board_score_delta) × 0.05
- 战斗结算: (damage_dealt - damage_taken) × 0.3 + knockout_bonus(2.0)
- 终局排名: {1:20, 2:10, ..., 8:-20}

### v5 Dense: Survival + Board Strength + Turn
- 存活回合: turn × 0.2
- 棋盘强度: sum(atk+health) × 0.01
- 战斗结果: -damage_taken × 0.5
- 终局排名: 同上

## 轨迹对手系统

用于 RL 训练的冻结战斗对手 — 从历史对局中提取棋盘快照。

| 组件 | 文件 | 职责 |
|------|------|------|
| 数据结构 | `hsrl/trajectory/record.py` | MinionSnapshot, TurnSnapshot, Trajectory |
| 批量生成 | `hsrl/trajectory/generate.py` | 启发式对局轨迹 (1,100+) |
| 对手加载 | `hsrl/trajectory/opponent.py` | JSON → Minion, inject to Player.board |
| 分组 | `hsrl/trajectory/group.py` | 按种族兼容性分组 |
| HDT 转换 | `hsrl/advisor/trajectory_converter.py` | 真人数据 → Trajectory |

存储: `data/trajectories/traj_{seed:06d}.json` + `index.jsonl`

## Entity-Token Transformer 架构 (5.25M 参数)

新一代策略网络，将 ObservationV2 的 37 个实体槽编码为 token，通过多头注意力建模实体间交互。

```
ScaledModel:
  Tokenizer (EntityTokenizerV2):
    - Card embedding: 1500 × 128
    - Entity MLP: 8-dim stats → 128-dim
    - Summary projectors: global(16→128), hero(12→128), opponent(12→128), history(8→128)
  Transformer (EntityTransformer):
    - d_model=256, heads=4, layers=6, ff=1024
    - Multi-head self-attention over 37 entity tokens
  Heads:
    - HierarchicalActionHead: 8-way type + 24-way pointer → Discrete(50)
    - DistributionalValueHead: P(rank=1..8) → E[rank] → V(s)
```

### Hierarchical Action Space

```
Discrete(50) action_id → hierarchical:
  type (8-way): BUY(0) | SELL(1) | PLAY(2) | REFRESH(3) | UPGRADE(4) | FREEZE(5) | HERO_POWER(6) | END_TURN(7)
  pointer (24-way): slot 0-6 for BUY/SELL, slot 0-9 for PLAY
```

### Board Score (compute_board_score_v2)

```
total = Σ(atk+health)/50 + keyword_bonuses + scaling_potential + synergy + economy
```

## 开发命令

```bash
# 运行全部测试
python -m pytest hsrl/tests/ -v

# 运行启发式 demo
python -m hsrl.agents.heuristic_demo --seed 42

# 运行 8 混合 agent 自对弈 demo
python -m hsrl.agents.self_play_demo --seed 42 --output docs/demo.md

# 运行 1 agent vs 7 启发式审计
python -m hsrl.agents.agent_vs_heuristic_demo --seed 42

# Benchmark SearchAgent (30 局)
python -m hsrl.agents.search_agent --benchmark --games 30

# ── 新一代 Policy 训练 ──

# Phase 0: BC from heuristic (单轮)
python hsrl/policy/bc_train.py

# Phase 1: 迭代 BC (多轮 self-improvement, 强启发式 → BC)
python hsrl/policy/iter_train.py

# ── Legacy 训练脚本 (gitignored) ──

# 训练 BoardEval
python -m hsrl.train.combat_data --games 500
python -m hsrl.train.board_eval --data data/combat_pairs/combats.npz --epochs 50

# 训练 GameValue (v4 POMDP, terminal placement teacher)
python -m hsrl.train.game_value_sp --games 500 --self-play 1 --heuristic 7

# 训练 Dense Value
python -m hsrl.train.value_dense --games 500 --epochs 100

# 收集 BC 数据 + 训练策略
python -m hsrl.train.bc_collector_v3 --games 300
python -m hsrl.train.bc_trainer_v3 --data data/bc_search_agent.npz --epochs 30

# PPO 微调
python -m hsrl.train.ppo_trainer_v2 --checkpoint checkpoints/bc_search_agent.pt --epochs 50
```

## 禁止事项

- 不要在 `tags` 之外添加隐藏状态
- 不要将机制逻辑硬编码在卡牌脚本中（应放在 `actions.py`）
- 不要创建"简化实现" — 卡牌只有 CORRECT 或 DEFERRED 两种状态
- 不要修改 `fireplace/`（仅参考）
- 不要依赖外部 wiki 访问
- **不要实现双打（Duos）系统**
- 每个脚本类必须使用三段式文档注释 (Natural language / Formal spec / Test)
