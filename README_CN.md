# HSBRSIM — 炉石传说酒馆战棋模拟器

[English](README.md) | [中文文档](README_CN.md)

一个干净、可扩展的 Python 引擎，用于以机制精度模拟**《炉石传说》酒馆战棋单打模式**。每个关键词、触发器和战斗规则均与官方描述完全一致。

> **范围限定**：仅支持单打模式。双打（Duos）模式不在项目范围内。

## 架构设计

### Action 驱动架构

所有状态变更必须通过 Action 系统：

```
Action → 队列 → 广播事件 → 结算 → 触发后续效果 → 检查死亡
```

无隐藏状态，无魔法数字。每个属性均在 `hsrl/core/enums.py` 中显式声明。

### 核心引擎

| 模块 | 行数 | 职责 |
|--------|-------|---------------|
| `hsrl/core/enums.py` | 295 | GameTag (180+), CardType (9种), Race, Zone, Step, State |
| `hsrl/core/entity.py` | 345 | BaseEntity — 标签存储、buff、脚本钩子 |
| `hsrl/core/actions.py` | 1,897 | 60+ Action 类 — 全部游戏机制 |
| `hsrl/core/game.py` | 1,424 | Game 引擎 — 回合流程、战斗、死亡、伤害 |
| `hsrl/core/events.py` | 145 | EventListener + 40+ 标准事件常量 |
| `hsrl/core/player.py` | 123 | Player — 金币、血量、棋盘、手牌、饰品 |
| `hsrl/core/card_db.py` | 157 | CardDB 单例 + `register_card()` |
| `hsrl/core/minion.py` | 54 | Minion — 战斗状态、can_attack |
| `hsrl/core/minion_pool.py` | 188 | 共享随从池 + `remove_all_copies` |
| `hsrl/core/spell_pool.py` | 101 | 共享法术池 |

## 已实现机制

### 战斗关键词

| 关键词 | 描述 | 状态 |
|---------|-------------|--------|
| 嘲讽（Taunt） | 强迫攻击者优先攻击此随从 | ✅ |
| 圣盾（Divine Shield） | 抵挡第一次伤害 | ✅ |
| 剧毒（Poisonous） | 消灭任何受此随从伤害的随从 | ✅ |
| 烈毒（Venomous） | 战斗期间消灭任何受此随从伤害的随从 | ✅ |
| 复生（Reborn） | 首次死亡后以1点生命值重新召唤 | ✅ |
| 风怒（Windfury） | 每回合可攻击两次 | ✅ |
| 顺劈（Cleave） | 同时伤害相邻随从 | ✅ |

### 卡牌效果

| 机制 | 描述 | 状态 |
|-----------|-------------|--------|
| 战吼（Battlecry） | 从手牌打出时触发 | ✅ |
| 亡语（Deathrattle） | 随从死亡时触发 | ✅ |
| 战斗开始时（Start of Combat） | 战斗开始时触发 | ✅ |
| 回合结束时（End of Turn） | 招募阶段结束时触发 | ✅ |
| 回合开始时（Start of Turn） | 招募阶段开始时触发 | ✅ |
| 复仇（Avenge） | N个友方随从死亡后触发 | ✅ |
| 进击（Rally） | 此随从攻击时触发 | ✅ |
| 磁力（Magnetic） | 吸附到棋盘上的机械随从 | ✅ |
| 塑造法术（Spellcraft） | 手牌中一次性法术效果 | ✅ |

### 子系统

| 系统 | 描述 | 状态 |
|--------|-------------|--------|
| 金色/三连 | 凑齐3张 → 金色 + 发现 | ✅ |
| 鲜血宝石 | 获取 / 使用 / 强化宝石 | ✅ |
| 发现（Discover） | 从3张卡牌中选择1张 | ✅ |
| 变形（Transform） | 将一个随从替换为另一个 | ✅ |
| 吞噬（FodderConsume） | 吞噬一个随从获得属性值 | ✅ |
| 全局光环（Global Aura） | 持续棋盘范围 buff | ✅ |
| 酒馆 Buff | 对酒馆中的随从施加 buff | ✅ |
| 战斗召唤 | 战斗中召唤随从 | ✅ |
| 免费刷新 | 获得免费酒馆刷新次数 | ✅ |
| 法术折扣 | 降低下一张法术的费用 | ✅ |
| 伙伴系统 | 英雄专属伙伴随从 | ✅ |
| 饰品（Trinkets） | 小型/大型饰品选择 | ✅ |
| 异变（Anomalies） | 改变游戏规则 (64/105 已实现) | ✅ |
| 任务（Quests） | 任务 + 奖励系统 (66/76 已实现) | ✅ |

### 卡牌注册状态

| 类别 | 数量 | CORRECT | DEFERRED |
|----------|-------|---------|----------|
| 随从池 | 244 | 218 | 0 |
| 法术池 | 71 | 71 | 0 |
| 衍生物 | ~200 | ~200 | 0 |
| 英雄 | 120 | 120 | 0 |
| 英雄技能 | 94 | 94 | 0 |
| 饰品 | 327 | 311 | 5（OOS 双打） |
| 异变 | 105 | 64 | 41 |
| 任务奖励 | 76 | 66 | 10 |
| **合计** | **~1,237** | **~1,144** | **56** |

## 项目结构

```
HSBRSIM/
├── hsrl/                              # 主 Python 包
│   ├── core/                          # 游戏引擎 (5,581 行)
│   │   ├── enums.py                   # GameTag, CardType, Race, Zone, Step
│   │   ├── entity.py                  # BaseEntity — 标签、buff、钩子
│   │   ├── minion.py                  # Minion — 战斗状态
│   │   ├── player.py                  # Player — 金币、血量、棋盘
│   │   ├── actions.py                 # Action 系统 (60+ Action 类)
│   │   ├── events.py                  # EventListener + 40+ 事件常量
│   │   ├── game.py                    # Game 引擎 — 回合、战斗、死亡
│   │   ├── minion_pool.py             # 共享随从池
│   │   ├── spell_pool.py              # 共享法术池
│   │   ├── card_db.py                 # CardDB + register_card()
│   │   ├── quest.py                   # Quest + QuestReward 实体
│   │   ├── anomaly.py                 # Anomaly 实体
│   │   └── trinket.py                 # Trinket 实体
│   ├── cards/                         # 卡牌定义 (20 个文件)
│   │   ├── minions/                   # 随从卡牌 (池、脚本、衍生物)
│   │   ├── heroes/                    # 英雄卡牌 (池、脚本)
│   │   ├── spells/                    # 法术卡牌
│   │   ├── rewards/                   # 任务奖励卡牌
│   │   ├── trinkets/                  # 饰品卡牌
│   │   └── anomalies/                 # 畸变卡牌
│   ├── agents/                        # AI 智能体 (Search, AZ MCTS, 启发式)
│   │   ├── search_agent.py            # 混合搜索 + 价值网络智能体
│   │   ├── az_agent.py                # AlphaZero MCTS 智能体
│   │   ├── agent_utils.py             # 动作模拟工具
│   │   └── *_demo.py                  # Demo 脚本
│   ├── policy/                        # Entity-Token Transformer 策略 (5.25M)
│   │   ├── model_5m.py                # ScaledModel: d=256, 6层 Transformer
│   │   ├── entity_tokenizer_v2.py     # 37槽位 tokenizer + 卡牌嵌入
│   │   ├── transformer.py             # 多头注意力 over entity tokens
│   │   ├── heads.py                   # 分层动作头 (类型 + 指针)
│   │   ├── value_head.py              # 分布价值头 P(排名)→V(s)
│   │   ├── bc_train.py                # BC 训练 (启发式教师)
│   │   └── iter_train.py              # 迭代 BC: 多轮自我提升
│   ├── rl_env/                        # 新一代 RL 环境 (entity-centric)
│   │   ├── observation/               # ObservationV2: 37 实体槽布局
│   │   ├── action/                    # 分层动作空间语法
│   │   ├── reward/                    # 场面评分 v2 + 奖励组件
│   │   ├── envs/                      # BoardBuildingEnv, TurnRecruitEnv
│   │   └── teachers/                  # 规划搜索教师
│   ├── advisor/                       # HDT 插件后端
│   │   ├── server.py                  # WebSocket 服务器
│   │   ├── state_mapper.py            # 游戏状态 → 特征向量
│   │   ├── collector.py               # 轨迹记录器 (JSONL)
│   │   ├── overlay_protocol.py        # C# ↔ Python 消息协议
│   │   ├── inference.py               # 模型推理 (需 sb3-contrib)
│   │   └── cli.py                     # 命令行接口
│   ├── trajectory/                    # 轨迹对手系统
│   │   ├── record.py                  # MinionSnapshot, TurnSnapshot, Trajectory
│   │   ├── generate.py                # 批量生成轨迹
│   │   ├── opponent.py                # 轨迹对手加载
│   │   └── pool.py                    # 轨迹池采样
│   └── tests/                         # 测试套件 (772 个测试)
│       ├── test_core_mechanics.py      # 核心机制测试
│       ├── test_token_cards.py        # 衍生卡牌测试
│       ├── test_heroes.py             # 英雄技能测试
│       ├── test_advisor.py            # Advisor 流水线测试
│       └── test_logger.py             # Logger 测试
├── hsrl_advisor/                      # HDT 插件 (C#)
│   └── plugin/                        # HDT 插件源码
│       ├── plugin.json                # 插件清单
│       ├── HrSRLAdviser.csproj        # .NET 4.7.2 项目
│       ├── AdviserPlugin.cs           # 插件入口
│       ├── GameStateExtractor.cs      # 游戏状态提取 (~617 行)
│       ├── SuggestionOverlay.cs        # WPF 覆盖层
│       └── WebSocketClient.cs         # WebSocket 客户端
├── data/                              # 卡牌数据 (JSON)
│   ├── bg_cards.json                  # 全量酒馆战棋卡牌 (5,189)
│   ├── bg_pool_minions.json           # 随从池 (270)
│   ├── bg_pool_spells.json            # 法术池 (71)
│   ├── bg_heroes.json                 # 英雄定义 (119)
│   ├── bg_hero_powers.json            # 英雄技能 (164)
│   ├── bg_trinkets.json               # 饰品 (326)
│   ├── bg_anomalies.json              # 异变 (104)
│   └── bg_quest_rewards.json          # 任务奖励 (73)
├── docs/                              # 参考文档
│   ├── BATTLEGROUNDS_RULES.md         # 权威规则手册
│   ├── MECHANICS_REFERENCE.md         # 机制实现参考
│   ├── CARD_REGISTRATION_GUIDE.md     # 卡牌注册指南
│   └── wiki_crawls/                   # 缓存的 wiki 数据
├── hsdata/                            # CardDefs.xml (git 子模块)
├── pyproject.toml                     # 构建配置
├── README.md                          # 本文件（英文）
└── README_CN.md                       # 中文文档
```

## 快速开始

### 安装

```bash
pip install -e .
# 或包含开发依赖：
pip install -e ".[dev]"
```

### 基础用法 — 1v1 战斗沙盒

```python
from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.core.card_db import CARDS
import hsrl.cards.minions  # 注册标准示例卡牌

# 创建 2 人沙盒游戏
game = Game([])
game.card_db = CARDS

p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=game)
p2 = Player(CARDS.get("EXAMPLE_VANILLA"), game=game)
game.players = [p1, p2]

# 将随从召唤到各自棋盘上
m1 = game.create_minion("EXAMPLE_TAUNT")
m2 = game.create_minion("EXAMPLE_POISONOUS")
game.summon(p1, m1)
game.summon(p2, m2)

# 运行一场战斗
game._run_combat(p1, p2)
print(f"玩家1 血量: {p1.health}, 玩家2 血量: {p2.health}")
```

### 运行完整八人对局

酒馆战棋本质上是八人游戏。引擎内置了启发式 AI 代理，提供一行 API 即可模拟完整对局：

```python
# 导入即触发卡牌注册（英雄、随从、法术、饰品等）
import hsrl.cards.heroes
import hsrl.cards.minions
import hsrl.cards.spells

from hsrl.core.game import Game
from hsrl.core.enums import GameTag

# 八人对局：一行运行，内置启发式 AI
# 每个 AI 使用贪心策略：买属性最好的随从 → 打出 → 升级 → 刷新
game = Game.run_game(
    hero_ids=[
        "BG20_HERO_100",  # 洛卡拉
        "BG20_HERO_101",  # 泽瑞拉
        "BG20_HERO_103",  # 死亡语者布莱克松
        "EXAMPLE_HERO",
        "EXAMPLE_HERO_FREEZE",
        "EXAMPLE_HERO_COPY",
        "EXAMPLE_HERO_SPELL",
        "EXAMPLE_HERO_AURA",
    ],
    max_turns=50,
)

# 输出结果
print(f"游戏结束，共 {game.turn} 回合")
for i, p in enumerate(game.players):
    name = p.get_tag(GameTag.NAME, f"玩家 {i}")
    status = "冠军" if p.health > 0 else "已淘汰"
    board = p.get_board_minions()
    print(f"  {name}: HP={p.health} 酒馆等级={p.tavern_tier} "
          f"棋盘={len(board)} [{status}]")
```

如需逐步控制，可使用 `Game.create_game()` + `game.run_turn()`：

```python
# 逐回合手动控制
game = Game.create_game(hero_ids, card_db=None, apply_anomaly=False)

while game.state == game.state.RUNNING:
    game.run_turn()  # 一整个回合：招募 → 战斗 → 伤害
    print(f"第 {game.turn} 回合完成")

winner = [p for p in game.players if p.health > 0][0]
```

## 测试接口

### 运行测试

```bash
# 运行全部测试
python -m pytest hsrl/tests/ -v

# 运行特定测试类别
python -m pytest hsrl/tests/test_core_mechanics.py -v
python -m pytest hsrl/tests/test_token_cards.py -v
python -m pytest hsrl/tests/test_heroes.py -v

# 运行单个测试
python -m pytest hsrl/tests/test_core_mechanics.py::TestCombat::test_taunt_attracts_attacks -v

# 带覆盖率报告
pip install pytest-cov
python -m pytest hsrl/tests/ --cov=hsrl --cov-report=html
```

### 测试统计

- **772 个测试** 通过，1 个跳过
- 分类：核心机制 (352)、英雄技能 (145)、衍生卡牌 (77)、advisor、logger
- 覆盖目标：每个机制和卡牌脚本都有对应的测试用例

### 编写测试

测试遵循 Arrange-Act-Assert（准备-执行-断言）模式：

```python
def test_圣盾抵挡伤害(self):
    # Arrange 准备
    game = Game([])
    p1 = Player(...)
    p2 = Player(...)
    m1 = game.create_minion("EXAMPLE_DIVINE_SHIELD")
    m2 = game.create_minion("EXAMPLE_TAUNT")
    game.summon(p1, m1)
    game.summon(p2, m2)

    # Act 执行
    game._run_combat(p1, p2)

    # Assert 断言
    assert m1.get_tag(GameTag.DIVINE_SHIELD) == 0  # 圣盾已消耗
    assert m1.health == m1.get_tag(GameTag.HEALTH)  # 未损失生命值
```

## 卡牌注册流程

添加新卡牌遵循标准流水线：

1. **阅读官方卡牌文本** — 理解精确语义
2. **定义脚本类**，使用三段式文档注释：
   ```python
   class BGS_999_Script:
       """自然语言：战吼：使一个友方随从获得+2/+2。

       形式化规格：
         Battlecry → choose friendly minion → Buff(+2 ATK, +2 HP, permanent)

       测试用例: BGS_999_GivesBuff
       """
       battlecry = BuffFriendly(target=TARGET_SELF, atk=2, health=2)
   ```
3. **注册卡牌** 通过 `register_card()`：
   ```python
   register_card(
       card_id="BGS_999",
       card_type=CardType.MINION,
       name="示例增强者",
       attack=3, health=3, tier=2, race=Race.NEUTRAL,
       script_class=BGS_999_Script,
   )
   ```
4. **编写测试** 验证精确语义
5. **运行测试** 直至通过

**卡牌正确性标准**：卡牌只有两种状态 — CORRECT（与官方文本精确匹配）或 DEFERRED（返回 None + 说明依赖）。不允许近似的实现。

## HDT 插件 — 游戏内行为轨迹监控

`hsrl_advisor/plugin/` 目录包含一个用于 **Hearthstone Deck Tracker** (HDT) 的 C# 插件，可实时捕获酒馆战棋游戏状态。配合 Python 后端服务器，可将完整的对局轨迹记录为 JSONL 文件进行分析。

### 架构

```
[C# HDT 插件] ──WebSocket──> [Python 服务器] ──> data/real_games/<日期>/<game_id>.jsonl
     127.0.0.1:9777
```

### 构建插件

**前置条件**：.NET Framework 4.7.2 SDK、已安装 Hearthstone Deck Tracker。

```bash
# 命令行构建
cd hsrl_advisor/plugin
dotnet build HrSRLAdviser.csproj

# 或在 Visual Studio / JetBrains Rider 中打开 HrSRLAdviser.csproj
```

`.csproj` 的 PostBuild 目标会自动将构建好的 DLL 和 `plugin.json` 复制到 `%AppData%\HearthstoneDeckTracker\Plugins\HrSRLAdviser\`。

### 手动安装

如果自动部署失败，手动复制：

```
hsrl_advisor/plugin/bin/Debug/net472/HrSRLAdviser.dll  →  %AppData%\HearthstoneDeckTracker\Plugins\HrSRLAdviser\
hsrl_advisor/plugin/plugin.json                         →  %AppData%\HearthstoneDeckTracker\Plugins\HrSRLAdviser\
```

### 启动服务器

**仅收集模式**（无需 AI 模型 — 只记录轨迹数据）：

```bash
python -m hsrl.advisor.cli --collect-only
```

**推理模式**（需要 `sb3-contrib` 和训练好的模型权重）：

```bash
pip install sb3-contrib websockets
python -m hsrl.advisor.cli --model path/to/checkpoint.zip
```

### 轨迹数据格式

每局游戏生成一个 `.jsonl` 文件（每行一个 JSON 对象）：

```jsonl
{"type": "game_start", "game_id": "abc123", "hero": "TB_BaconShop_HERO_59", "mmr": 7500, "timestamp": "2026-05-07T12:00:00"}
{"type": "step", "turn": 3, "action_taken": 0, "action_mask": [true, true, false, ...], "state": {...}}
{"type": "step", "turn": 4, "action_taken": 24, "action_mask": [...], "state": {...}}
...
{"type": "game_end", "game_id": "abc123", "placement": 3, "mmr_change": 15, "timestamp": "2026-05-07T12:15:00"}
```

`state` 对象包含从 HDT 提取的完整游戏状态：玩家状态、酒馆随从、手牌、棋盘、饰品和对手摘要。完整协议见 `hsrl/advisor/overlay_protocol.py`。

### 插件功能

- **实时状态提取**：读取 HDT 内部实体字典，捕获精确的游戏状态
- **定时更新**：招募阶段每 250ms 发送一次游戏状态
- **WPF 覆盖层**：在 HDT 覆盖层画布上显示连接状态
- **自动重连**：WebSocket 客户端在连接断开时以指数退避策略自动重连
- **优雅降级**：如果 Python 服务器未运行，插件仅不显示建议 — HDT 正常工作不受影响

## RL 训练

项目包含一个 entity-token Transformer 策略 (5.25M 参数) 和迭代 BC 训练流水线：

```bash
# Phase 0: 启发式 BC 训练 (单轮)
python hsrl/policy/bc_train.py

# Phase 1: 迭代 BC (多轮自我提升)
python hsrl/policy/iter_train.py
```

### 策略架构

```
build_observation_v2() → 37 entity slots → EntityTokenizerV2 → EntityTransformer → Heads
  ├─ EntityTokenizerV2: 卡牌嵌入 (1500×128) + 实体 MLP + 摘要投影
  ├─ EntityTransformer: d=256, h=4, 6层 — 多头注意力 over entity tokens
  ├─ HierarchicalActionHead: 8路类型 + 24路指针 → Discrete(50)
  └─ DistributionalValueHead: P(rank=1..8) → V(s)
```

动作空间是分层的 — 一个 Discrete(50) 动作 ID 分解为 8 路类型 (买/卖/打/刷新/升级/冻结/技能/结束) 和 24 路指针 (买/卖/打哪个)。

### 当前结果

| 方法 | avg board_score | avg raw (atk+hp) | vs 随机 |
|------|----------------|-------------------|---------|
| 迭代 BC (第 0 轮: 启发式) | 2.2 | 33 | +0.8 |
| 迭代 BC (第 3 轮: BC→BC) | 2.3 | 38 | +0.7 |
| 随机基线 | 1.4 | 25-39 | — |

详见 `docs/AGENT_TRAINING_STATUS.md`。

## 设计哲学

1. **语义精确性**：代码实现必须与卡牌文本的操作语义精确一致。"获取" ≠ "打出"、"召唤" ≠ "置入手牌"。
2. **无隐藏状态**：每个属性在 `enums.py` 中显式声明。无魔法数字。
3. **Action 驱动**：所有状态变更通过 Action 系统 + 事件广播完成。
4. **卡牌只有 CORRECT 或 DEFERRED**：近似的实现是 bug，不是简化。
5. **文档冻结**：规则和机制文档化在 `docs/` 中 — 不依赖网络访问。

## 数据来源

卡牌数据来源于 HearthSim 的 [hsdata](https://github.com/HearthSim/hsdata)（CardDefs.xml）和 [Amalgadon API](https://bgknowhow.com/)，经清洗后缓存为 `data/` 目录下的结构化 JSON 文件。

**数据版本**：Patch 35.6.0.243002 | 赛季 15

### Replay 动作级评测（P4）

规范化高手 replay 可用动作一致率、Top-3、board-score regret、经济/定阵容/
刷新/enabler/升本/站位以及最终名次进行离线评测：

```bash
python -m hsrl.evaluation.replay_action_eval replay.jsonl --format markdown
```

每项指标都会报告样本覆盖率；缺少实际高手动作或反事实状态时显示 `N/A`。
数据契约和现有 replay 缺口见 `docs/REPLAY_ACTION_EVALUATION.md`。

## 许可证

MIT
