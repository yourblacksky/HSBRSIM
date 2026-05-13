# HrSRL — 酒馆战棋强化学习环境

## 项目概述

HrSRL 是一个干净、可扩展的 Python 引擎，用于模拟《炉石传说》酒馆战棋**单打（Solo）**模式。从零开始设计，目标：
- **机制准确性**：每个关键词、触发器和战斗规则与官方描述完全一致
- **强化学习就绪**：快速模拟、完整状态可观察性
- **数据驱动开发**：卡牌从结构化定义注册，定义直接从自然语言卡牌文本推导

> **范围限制：本项目仅支持单打模式。双打（Duos）模式的所有内容（传递机制、队伍交互、双打专属卡牌/饰品/英雄）均不在项目范围内，不实现、不维护。**

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 卡牌数据 | hsdata (CardDefs.xml) + Amalgadon API → `data/` JSON |
| 参考代码 | fireplace (HearthSim 的炉石引擎，仅参考) |
| 测试 | pytest / unittest |
| 构建 | setuptools (pyproject.toml) |

## 项目结构

```
HrSRL/
├── docs/                              # 冻结的规则手册（不依赖网络访问）
│   ├── BATTLEGROUNDS_RULES.md         # ★ 权威规则手册
│   ├── MECHANICS_REFERENCE.md         # ★ 机制实现参考
│   ├── CARD_REGISTRATION_GUIDE.md     # ★ 卡牌注册指南
│   └── wiki_crawls/                   # 本地缓存的 wiki 爬取结果
│
├── data/                              # 清洗后的卡牌数据 (JSON)
│   ├── bg_cards.json                  # 全量 BG 卡牌 (5,189 张)
│   ├── bg_pool_minions.json           # 可购买随从池 (270 种)
│   ├── bg_pool_spells.json            # 可购买法术池 (71 种)
│   ├── bg_heroes.json                 # 英雄定义 (119 位)
│   ├── bg_hero_powers.json            # 英雄技能 (164 个)
│   ├── bg_quest_rewards.json          # 任务奖励 (73 个)
│   ├── bg_anomalies.json              # 异变 (104 个)
│   └── bg_trinkets.json               # 饰品 (326 个)
│
├── hsrl/                              # 主代码包
│   ├── core/                          # ★ 游戏引擎核心
│   │   ├── enums.py                   # GameTag (310+), CardType, Race, Zone, Step
│   │   ├── entity.py                  # BaseEntity + CardData — 标签存储 + buff
│   │   ├── minion.py                  # Minion — 战斗状态
│   │   ├── player.py                  # Player — 金币/血量/酒馆等级/board/hand
│   │   ├── actions.py                 # ★ Action 系统 (1,980 行, 60+ Action 类)
│   │   ├── events.py                  # EventListener + 40+ 标准事件常量
│   │   ├── game.py                    # ★ Game 引擎 (2,077 行)
│   │   ├── minion_pool.py             # MinionPool — 共享随从池 + 种族过滤
│   │   ├── spell_pool.py              # SpellPool — 共享法术池
│   │   ├── card_db.py                 # CardDB 单例 + register_card()
│   │   ├── quest.py                   # Quest + QuestReward 实体
│   │   ├── anomaly.py                 # Anomaly 实体
│   │   └── trinket.py                 # Trinket 实体
│   ├── cards/                         # 卡牌定义 (805 CORRECT, 0 DEFERRED, 15 OOS)
│   │   ├── minions/                   # 随从卡牌 (pool, scripts, tokens)
│   │   ├── heroes/                    # 英雄卡牌 (pool, scripts)
│   │   ├── spells/                    # 法术卡牌
│   │   ├── rewards/                   # 任务奖励卡牌
│   │   ├── trinkets/                  # 饰品卡牌
│   │   └── anomalies/                 # 异变卡牌
│   ├── env/                           # RL 环境 (Gymnasium)
│   │   ├── battlegrounds_env.py       # 单智能体环境
│   │   ├── multi_agent_env.py         # 多智能体环境
│   │   ├── action.py                  # Discrete(50) 动作空间 + mask + 解码
│   │   ├── observation.py             # 观察空间构建
│   │   ├── reward.py                  # 奖励计算 (v4: per-action recruit + combat + terminal)
│   │   └── shared_observation.py      # 共享观察编码
│   ├── agents/                        # AI 智能体
│   │   ├── __init__.py
│   │   ├── mcts_agent.py              # Beam Search 备战阶段规划智能体
│   │   ├── nn_mcts_agent.py           # BC 策略网络智能体 (avg rank 4.28, 击败贪心)
│   │   ├── search_agent.py            # ★ SearchAgent v2 — 贪心/束搜索前瞻 (avg_rank 1.97)
│   │   ├── demo_game.py               # 实战演示脚本 (完整对局 + 解说)
│   │   └── benchmark_nn_mcts.py       # BC 智能体 vs 贪心基准测试
│   ├── trajectory/                    # 轨迹对手系统
│   │   ├── record.py                  # 数据结构 (MinionSnapshot, TurnSnapshot, Trajectory)
│   │   ├── generate.py                # 批量生成启发式轨迹 (1,100+ 场)
│   │   ├── group.py                   # 按兼容种族集分组
│   │   └── opponent.py                # 轨迹对手加载器
│   ├── train/                         # 训练脚本
│   │   ├── network.py                 # Dual-Head Network (Policy + Value)
│   │   ├── board_eval.py              # ★ BoardEvalNetwork v2 — 嵌入架构, 99.1% pairwise acc
│   │   ├── combat_data.py             # 战斗数据收集 (44,958 样本/500局)
│   │   ├── game_value.py              # ★ GameValueNetwork v2 — POMDP 价值评估, MAE 0.143
│   │   ├── bc_collector_v2.py         # BC 数据收集: 10K局 → 10.77M triplets
│   │   ├── bc_trainer_v2.py           # BC 训练: joint policy CE + value MSE
│   │   ├── value_trainer.py            # GAE 价值网络重训 (on-policy, bootstrap targets)
│   │   ├── ppo_trainer.py               # ★ 完整 PPO 微调 (unfreeze trunk+policy+value)
│   │   ├── trajectory_trainer.py      # PPO 训练入口
│   │   ├── self_play_trainer.py       # 自对弈训练
│   │   ├── self_play_config.py        # 自对弈配置
│   │   ├── opponent_selector.py       # 对手选择策略
│   │   ├── model_pool.py              # 模型池管理
│   │   └── wrappers.py                # 环境 Wrapper
│   └── tests/                         # 测试 (696 passed, 1 skipped)
│
├── hsdata/                            # HearthSim 官方 XML 数据 (git submodule)
├── fireplace/                         # fireplace 引擎 (参考代码，不修改)
├── AGENTS.md                          # AI 开发助手规范
├── README.md                          # 用户文档
├── pyproject.toml                     # 项目配置
└── CLAUDE.md                          # 本文件
```

## 核心设计哲学

### 1. Action 驱动架构

所有状态变更必须通过 Action 系统：

```
Action → queue → broadcast events → resolve → trigger follow-ups → check deaths
```

### 2. 语义精确性原则

- **代码实现必须与卡牌文本的操作语义精确一致**
- **每个脚本类使用三段式文档注释**: Natural language / Formal spec / Test
- **卡牌只有两种状态**: CORRECT（精确匹配卡牌文本）或 DEFERRED（返回 None + 依赖说明）
- **禁止"简化实现"**: 语义不同的近似行为是 bug，不是简化
- 关键动词区分："Get" ≠ "Play"、"Summon" ≠ "Add to hand"

### 3. 所有可见属性预声明

每个 GameTag 必须在 `core/enums.py` 中显式声明。禁止魔术数字、禁止隐藏状态。

### 4. 文档冻结

所有外部规则已冻结在 `docs/` 中。开发**不依赖网络访问**。

## 当前实现状态

### 引擎核心

| 文件 | 行数 | 职责 |
|------|------|------|
| `enums.py` | 311 | GameTag (310+), CardType (11 types), Race, Zone, Step, State |
| `entity.py` | 356 | BaseEntity (tags + buff + _script_overrides + 11 script hooks) |
| `actions.py` | 1,980 | ★ 60+ Action 类 — 全部游戏机制 |
| `game.py` | 2,077 | Game 引擎 — 回合/战斗/死亡/伤害/任务/异变/饰品/调度/种族过滤 |
| `events.py` | 148 | EventListener + 40+ 标准事件常量 |
| `minion_pool.py` | 198 | MinionPool — 共享随从池 + remove_all_copies + 种族过滤 |
| `spell_pool.py` | 107 | SpellPool — 共享法术池 |
| `player.py` | 131 | Player — 金币/血量/board/hand/tavern/trinkets/auras |
| `card_db.py` | 157 | CardDB + register_card() + create_trinket/quest/anomaly |
| `minion.py` | 54 | Minion — can_attack, reset_combat_state |
| `quest.py` | 98 | Quest + QuestReward 实体 |
| `anomaly.py` | 51 | Anomaly 实体 |
| `trinket.py` | 73 | Trinket 实体 |

### 已实现机制

| 机制 | 状态 |
|------|------|
| 基础关键词 (Taunt/DS/Poisonous/Venomous/Reborn/Windfury/Cleave) | ✅ |
| 战吼/亡语 | ✅ |
| 战斗开始时 (Start of Combat) | ✅ |
| 复仇 (Avenge) | ✅ |
| Rally (进击) + Rally 传播 + RALLY_DOUBLED | ✅ |
| 回合结束时/回合开始时 (EoT/SoT) | ✅ |
| 出售时 (On Sell) | ✅ |
| 全局光环 (GlobalAura) + ApplyGlobalAura | ✅ |
| 鲜血宝石 (Get/Play/Improve) | ✅ |
| 发现 (DiscoverMinion/DiscoverSpell/DiscoverReward) | ✅ |
| 变形 (Transform) | ✅ |
| 吞噬 (FodderConsume) | ✅ |
| Spellcraft + PERMANENT_SPELLCRAFT | ✅ |
| 磁力 (Magnetic) + MAGNETIC_COST_OVERRIDE | ✅ |
| 金色/三连 (Golden/Triple) + NEXT_PURCHASE_GOLDEN | ✅ |
| 酒馆 Buff (TavernBuff/BuffTavern) | ✅ |
| 战斗召唤 (Combat Summon) | ✅ |
| Improves 增强追踪 (IncrementImproveCounter) | ✅ |
| 酒馆刷新后 (After Refresh) + TAVERN_REFRESH 事件 | ✅ |
| 战吼触发后 (BATTLECRY_TRIGGER) | ✅ |
| 酒馆法术施放 (TAVERN_SPELL_CAST) | ✅ |
| 光环翻倍 (BC Doubler/EoT Doubler/DR Doubler) | ✅ |
| 临时 Buff (Temporary Buff) | ✅ |
| 免费刷新 (GainFreeRefresh/FREE_REFRESH_REMAINING) | ✅ |
| 法术折扣 (NEXT_SPELL_COST_REDUCTION) | ✅ |
| 额外英雄技能 (HERO_POWER_EXTRA_USES) | ✅ |
| 生命值购买 (HEALTH_COST_DEMON/SPELL) | ✅ |
| 战斗持久化 (_persist_combat_stats) | ✅ |
| 回合调度 (schedule_turn_action) | ✅ |
| 金币跨回合保留 (gold carryover) | ✅ |
| Eleventh Hour 致命伤害防止 | ✅ |
| 池移除 (minion_pool.remove_all_copies) | ✅ |
| Yogg 命运之轮 (CastYoggWheel) | ✅ |
| 随从教学 (TAUGHT_SPELL_ID + _script_overrides) | ✅ |
| Buddy 系统 (160+ 伙伴卡牌注册) | ✅ |
| 猜测随从 (GuessMinion) | ✅ |
| 英雄技能 — 主动/被动 (94/94 CORRECT) | ✅ |

### 卡牌注册状态

| 子系统 | CORRECT | DEFERRED | OUT_OF_SCOPE |
|--------|---------|----------|-------------|
| Hero Powers (94) | 94 | 0 | — |
| Minions (218) | 218 | 0 | — |
| Trinkets (327) | 316 | 0 | 11 (Duos) |
| Anomalies (105) | 101 | 0 | 4 (Duos) |
| Quest Rewards (76) | 76 | 0 | — |
| **Total** | **805** | **0** | **15** |

范围完成率: 100%。剩余 15 张 OOS: 4 张双打异变 + 11 张双打饰品。

### 测试覆盖

- **测试总数**: 696 passed, 1 skipped
- 核心机制: ~350 个测试用例 — 攻击/伤害/关键词/战斗/随从池/战吼/亡语/复仇/Rally/光环/鲜血宝石/发现/变型/吞噬/Spellcraft/酒馆Buff/三连/任务/异变/饰品/子系统
- 令牌卡牌: 77 个测试用例
- 英雄技能: 145 个测试用例

## 开发命令

```bash
# 运行全部测试
python -m pytest hsrl/tests/ -v

# 运行核心机制测试
python -m pytest hsrl/tests/test_core_mechanics.py -v

# 代码行数统计
find hsrl/core -name "*.py" | xargs wc -l
```

## 禁止事项

- 不要在 `tags` 之外添加隐藏状态
- 不要将机制逻辑硬编码在卡牌脚本中（应放在 `actions.py`）
- 不要创建"简化实现" — 卡牌只有 CORRECT 或 DEFERRED 两种状态
- 不要修改 `fireplace/`（仅参考）
- 不要依赖外部 wiki 访问
- **不要实现双打（Duos）系统** — 本项目仅限单打模式
- 每个脚本类必须使用三段式文档注释 (Natural language / Formal spec / Test)

## 轨迹对手系统

用于 RL 训练的冻结战斗对手 —— 从历史获胜对局中提取棋盘快照。

| 组件 | 文件 | 职责 |
|------|------|------|
| 数据结构 | `hsrl/trajectory/record.py` | MinionSnapshot, TurnSnapshot, Trajectory — 可序列化状态快照 |
| 批量生成 | `hsrl/trajectory/generate.py` | 运行 N 场启发式对局，每回合记录棋盘状态 |
| 分组 | `hsrl/trajectory/group.py` | 按兼容种族集分组 (Jaccard ≥ 0.6)，保证每组 ≥7 条 |
| 对手加载 | `hsrl/trajectory/opponent.py` | 从 JSON 重建 Minion 对象，注入到 Player.board |

存储: `data/trajectories/traj_{seed:06d}.json` + `index.jsonl`

## 种族过滤系统

每局从 10 个种族中随机选 5 个，酒馆仅刷新选中种族的随从。

- `Game.active_tribes`: `Optional[set[Race]]` — 当前局的活跃种族
- `Game._select_active_tribes()`: 在 `start_game()` 中调用，随机选择 5/10 种族 (异变可覆写)
- `MinionPool._matches_race()`: 接受单值或 set，`Race.ALL` 始终匹配
- `refresh_tavern()`: 所有 5 处 `minion_pool.draw()` 调用均传入 `race_filter=self.active_tribes`

## 数据文件说明

| 文件 | 内容 | 条目数 |
|------|------|--------|
| `bg_cards.json` | 全量酒馆战棋卡牌 | 5,189 |
| `bg_pool_minions.json` | 可购买随从池 | 270 |
| `bg_pool_spells.json` | 可购买法术池 | 71 |
| `bg_heroes.json` | 英雄定义 | 119 |
| `bg_hero_powers.json` | 英雄技能 | 164 |
| `bg_trinkets.json` | 饰品定义 | 326 |
| `bg_anomalies.json` | 异变定义 | 104 |
| `bg_quest_rewards.json` | 任务奖励 | 73 |

数据版本: Patch 35.2.2.241135 | 赛季: Season 13 "Cataclysm Calls"

## 强化学习接口设计

### 设计原则

1. **标准化接口**: 遵循 Gymnasium (gym) 标准 `env.step(action) → (obs, reward, terminated, truncated, info)`
2. **单智能体训练**: 每个玩家独立训练，对手使用冻结模型或启发式策略
3. **自对弈 (Self-Play)**: 训练后期使用自对弈提升上限
4. **可向量化**: 支持并行环境加速训练

### 技术选型

| 层级 | 技术 |
|------|------|
| RL 框架 | Gymnasium (gym) |
| 神经网络 | PyTorch |
| 并行化 | Ray / multiprocessing |
| 实验追踪 | TensorBoard / WandB |

### 观察空间 (Observation Space)

```
Dict({
    # 全局信息 (标量)
    "global": Box(shape=(20,)),   # turn, phase, alive_count, damage_cap, anomaly_id
    
    # 自身状态 (标量)
    "player": Box(shape=(15,)),   # HP, gold, tavern_tier, armor, hand_size, board_size
    
    # 酒馆 (多实体)
    "tavern": Box(shape=(7, 12)), # 7 slots × (atk, health, tier, cost, race, keywords×5, frozen)
    
    # 手牌 (多实体)
    "hand": Box(shape=(10, 12)),  # 10 slots × 实体属性
    
    # 棋盘 (多实体)
    "board": Box(shape=(7, 15)),  # 7 slots × (atk, health, tier, race, keywords×8, golden, exhausted)
    
    # 饰品/任务 (标量)
    "trinkets": Box(shape=(2, 8)), # 2 slots × 饰品属性
})
```

### 动作空间 (Action Space)

```
Discrete(50) 编码为:

0-6:   购买酒馆第 N 个实体 (随从或法术)
7-13:  出售棋盘第 N 个随从
14-23: 打出手牌第 N 张 (10 hand slots)
24:    刷新酒馆 (消耗 1 金币或免费刷新次数)
25:    升级酒馆等级
26:    冻结/解冻酒馆
27:    使用英雄技能
28:    结束回合 (进入战斗)
29:    获取 Buddy (伙伴计量器满时)
30:    重排棋盘 (Combat-aware heuristic)
31-49: 保留 (Reserved)
```

### 奖励函数 (v4: 每一步备战增量 + 战斗结算 + 终局排名)

| 组件 | 时机 | 公式 | 量级 |
|------|------|------|------|
| 备战增量 | 每个动作 | `(board_score_after - board_score_before) × 0.05 + STEP_COST(-0.001)` | ~[-0.5, +0.5]/action |
| 战斗结算 | END_TURN | `(damage_dealt - damage_taken) × 0.3 + knockout_bonus(+2.0)` | ~[-4.5, +6.5]/turn |
| 终局排名 | 游戏结束 | {1:20, 2:10, 3:5, 4:2, 5:-2, 6:-5, 7:-10, 8:-20} | [-20, 20] |

核心设计: 备战增量 (per-action recruit delta) 保证即时反馈，一个回合内的增量之和 = 回合级备战收益 (telescoping sum)。
无 ad-hoc 惩罚项，无效率税 (STEP_COST 仅用于阻止无限循环)。

### 实现路线

#### Phase 0: 引擎与数据 ✅ 已完成

- 全部 805 张在范围卡牌 CORRECT
- 696 个测试用例通过
- 启发式自动对战 (Q-score greedy heuristic, 平均排名 ~4.5)

#### Phase 1: DQN 基线 ✅ 已完成 (ceiling ~7.0)

- `hsrl/env/battlegrounds_env.py` — 单智能体 Gymnasium 环境
- `hsrl/env/action.py` — Discrete(50) 动作空间 + mask
- `hsrl/env/observation.py` — Dict→Flat 观察空间
- `hsrl/env/reward.py` — v4 奖励函数 (per-action recruit delta + combat + terminal)
- `hsrl/train/train_dqn.py` — MaskableDQN (Double DQN + Dueling + Action Masking)
- `hsrl/train/bc_dqn_trainer.py` — BC 预训练 (DuelingQNetwork 分类器, val_acc 96.7%)
- `hsrl/train/bc_dqn_finetune.py` — BC→RL 微调
- `hsrl/train/bc_guided_dqn.py` — BC 奖励引导 DQN
- `hsrl/train/eval_bc_dqn.py` — 确定性评估脚本
- 轨迹对手系统: `hsrl/trajectory/` (record, generate, group, opponent)

**结论**: 所有 DQN/BC 变体天花板 ~7.0，远低于启发式 ~4.5。DQN 的单步 TD + flat observation 无法学习备战阶段的组合动作序列。

#### Phase 2: Search + Value 架构 ✅ 已完成 (avg_rank 1.97, win% 6.7%)

**架构管线**: Combat Simulator → BoardEvalNetwork → GameValueNetwork → SearchAgent

##### BoardEvalNetwork v2 (嵌入架构) — 99.1% pairwise 准确率

v1（标量）问题: 标量 board_score 无法表达组合交互，例如"6 大型白板 vs 7 小剧毒"标量无法判断剧毒方优势。

v2（嵌入）方案:
- **BoardEmbedder**: `(7, 15) → R^32` — 每个槽位 MLP + 学习注意力 + weighted mean/max pool
- **CombatPredictor**: `[emb_a; emb_b; emb_a-emb_b; emb_a⊙emb_b]` → MLP → P(A wins)
- 端到端联合训练，BCEWithLogitsLoss
- 训练数据: 44,958 对战样本 (500 局)
- 模型: 17,154 参数，val_acc 99.1%
- 文件: `hsrl/train/board_eval.py`, 检查点: `checkpoints/board_eval_v2.pt`

##### GameValueNetwork v2 (POMDP 价值评估) — MAE 0.143

v1 的观察仅包含标量 board_score（特征 0），损失所有组合信息。

v2 改进:
- 输入维度: 32 (嵌入) + 6 (自身) + 21 (对手) + 2 (全局) = 61 维
- 教师信号: CombatPredictor 成对预测排名（替代 v1 标量排序）
- 模型: 4,457 参数，val_mae 0.143 (~1.0 排名位置)
- 训练数据: 47,346 快照 (500 局)
- 文件: `hsrl/train/game_value.py`, 检查点: `checkpoints/game_value_v2.pt`

##### SearchAgent (前瞻搜索) — avg_rank 1.97

基于 GameValueNetwork 的贪心前瞻搜索:
- 枚举合法动作 → 模拟 → 编码 POMDP → V(s') 评估 → 选最大值
- 支持束搜索 (beam search) 处理多步序列 (refresh→buy, sell→buy→play)
- 文件: `hsrl/agents/search_agent.py`
- 演示: `hsrl/agents/demo_game.py`

**评测结果 (2026-05-13, 30 局 vs 7 启发式对手)**:

| 方法 | avg_rank | win% | top4% | 时间/局 |
|------|----------|------|-------|---------|
| Greedy heuristic (Q-score) | ~4.5 | ~10% | ~50% | 0.4s |
| BC Policy argmax | 4.37 | 13.3% | 53.3% | 0.9s |
| SearchAgent v1 贪心 | 2.10 | 0.0% | 100% | 1.8s |
| SearchAgent v1 束搜索 (w=3,d=3) | 2.03 | 3.3% | 100% | 17.9s |
| **SearchAgent v2 贪心** | **2.07** | 0.0% | 100% | 4.4s |
| **SearchAgent v2 束搜索 (w=3,d=3)** | **1.97** | **6.7%** | 100% | 22.4s |

**分析**: 嵌入架构在束搜索中展现更大优势（1.97 vs 2.03），因为多步序列中的组合差异（剧毒 vs 大身材）逐渐累积。但 avg_rank 天花板 ~2.0 的主要原因是 **POMDP 瓶颈**——智能体仅能看到对手 HP/等级，无法观测对手棋盘。即使有完美的 CombatPredictor，GameValue 也无法利用它。

##### 已探索的死胡同

- **DQN/BC**: 天花板 ~7.0，单步 TD + flat observation 无法学习组合动作
- **MCTS + BC value**: 价值噪声 (MAE 3.90) > 动作差异 (~1.0), PUCT 无法区分动作
- **DAgger 迭代蒸馏**: 单次迭代无效 (SearchAgent 与启发式状态分布高度重叠)
- **BC 策略网络**: avg_rank 4.37 仅略优于启发式 4.5

##### 下一步方向

- **对手棋盘建模**: 根据对手 HP/等级估计其棋盘分布，用 CombatPredictor 模拟战斗
- **蒙特卡洛 END_TURN**: 采样对手棋盘 → CombatPredictor 成对预测 → 期望排名分布
- **战斗历史特征**: 记录过往战斗中的关键词/随从类型作为 POMDP 的额外信息

#### Phase 3: 自对弈训练 (规划中)

- `hsrl/train/self_play_trainer.py` — 自对弈训练循环
- `hsrl/train/model_pool.py` — 模型池管理 + ELO 评分
- `hsrl/train/opponent_selector.py` — 对手选择策略 (含轨迹对手 + MCTS 对手)

**目标**: 自对弈持续提升 + 多种对手作为多样性锚点
