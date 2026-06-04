# AGENTS.md — HSRL Development Guide

This file contains conventions and instructions for AI coding agents working on HSRL.

## Important Reference Documents

Before making any code changes, read these documents in order:

1. **`docs/BATTLEGROUNDS_RULES.md`** — Complete rules of Hearthstone Battlegrounds Solo Mode. This is the **authoritative source** for all game mechanics and interactions.
2. **`docs/MECHANICS_REFERENCE.md`** — Developer-facing reference for how each mechanism is implemented in the engine.
3. **`docs/CARD_REGISTRATION_GUIDE.md`** — Step-by-step guide for registering new cards from natural language descriptions.
4. This file (`AGENTS.md`) — Project conventions and development workflow.

> **Why these documents exist**: The external wiki (hearthstone.wiki.gg) is protected by Cloudflare and cannot be reliably accessed. All rules have been extracted, cross-referenced, and frozen in `docs/BATTLEGROUNDS_RULES.md` so development never depends on live web access.

---

## Architecture Overview

HSRL is an **action-centric** game engine inspired by `fireplace` but stripped down and focused exclusively on Battlegrounds Solo Mode.

### Core Concepts

- **Entity**: Everything is a `BaseEntity`. Tags (from `GameTag` enum) hold all visible state.
- **Action**: Every state change is an `Action` instance. Actions are queued and resolved by `Game.resolve_queue()`.
- **Event**: Actions broadcast events (e.g. `"DEATH"`, `"AFTER_ATTACK"`). `EventListener` objects subscribe and trigger follow-up Actions.
- **CardData**: Immutable blueprint. `CardDB` merges data with Python script classes.

### Key Files

| File | Purpose |
|------|---------|
| `core/enums.py` | **Single source of truth** for all visible properties. Add new `GameTag` values here before using them anywhere else. |
| `core/entity.py` | `BaseEntity`, `CardData`. Tags dict + buff stacking. |
| `core/minion.py` | `Minion` subclass. Combat state (exhausted, windfury attacks). |
| `core/player.py` | `Player` subclass. Gold, health, tavern tier, board, hand, tavern. |
| `core/actions.py` | All `Action` subclasses. This is where mechanics like Divine Shield, Poisonous, Cleave are actually implemented. |
| `core/events.py` | `EventListener` and event name constants. |
| `core/game.py` | `Game` class. Turn flow, combat loop, death processing, damage calculation. |
| `core/card_db.py` | `CardDB` singleton (`CARDS`) and `register_card()` helper. |

---

## Development Workflow

### Adding a New Mechanic

**DO NOT** jump straight to implementing a real card. Follow this strict order:

1. **Read the official description** in `docs/BATTLEGROUNDS_RULES.md` Section 5.
2. **Add the keyword tag** to `GameTag` in `core/enums.py` if it doesn't exist.
3. **Implement the mechanic logic** in `core/actions.py` (or modify existing actions like `Hit`, `Attack`).
4. **Create a standard example minion** in `cards/minions/__init__.py` (or a new standard-examples file).
5. **Write a test** in `hsrl/tests/test_core_mechanics.py`.
6. **Run `pytest`** and fix until it passes.
7. **Only then** add real cards that use the mechanic.

### Adding a New Card

Follow the pipeline from `docs/CARD_REGISTRATION_GUIDE.md`:

```
Natural Language → Formal Spec → register_card() → Semantic Match Test → Pass
```

**CRITICAL**: The code implementation must match the **exact operational semantics** of the card text. See `docs/CARD_REGISTRATION_GUIDE.md` Section 2 ("语义精确性原则") for the complete methodology and the "Get vs Play" case study (Section 2.2).

### Script Documentation Convention

Every script class must use the **three-stage docstring** format:

```python
class MyCardScript:
    """
    Natural language: <exact card text from the game>

    Formal spec:
      1. <step-by-step precise operations>
      2. <what entities are created/modified>
      3. <what the expected state is after resolution>

    Test: <one sentence describing how the test verifies the formal spec>
    """

    @staticmethod
    def battlecry(source, game):
        ...
```

**Example — correct:**

```python
class RazorfenGeomancerScript:
    """
    Natural language: Battlecry: Get 2 Blood Gems.

    Formal spec:
      1. Create 2 Blood Gem spell entities (card_id="BLOOD_GEM")
      2. Add them to source.controller.hand (Zone.HAND)
      3. Each Blood Gem can later be played on a friendly minion
         to buff it by (1 + BLOOD_GEM_BONUS_ATK) / (1 + BLOOD_GEM_BONUS_HEALTH)

    Test: verify player.hand contains 2 cards of type BLOOD_GEM_CARD
          after the Battlecry resolves.
    """
```

**Example — WRONG (semantic mismatch):**

```python
class RazorfenGeomancerScript:
    """Battlecry: Get 2 Blood Gems. (Simplified: auto-play on self.)"""
    # ❌ "Get" ≠ "Play on self" — these are different operations
    # ❌ Adds to hand vs. immediately buffs source
    # ❌ Player loses target choice agency
    return PlayBloodGems(source, count=2)
```

### Script Method Signatures

When a card script defines an effect method, use this exact signature:

```python
@staticmethod
def battlecry(source: Minion, game: Game) -> Action:
    ...

@staticmethod
def deathrattle(source: Minion, game: Game) -> Action:
    ...

@staticmethod
def start_of_combat(source: Minion, game: Game) -> Action:
    ...

@staticmethod
def avenge(source: Minion, game: Game) -> Action:
    ...
```

The engine checks `callable()` and invokes the method if needed. Return a single `Action`, a list of `Action`s, or `None`.

---

## Combat Rules (Quick Reference)

- **Attacker first**: More minions attacks first; tie → random.
- **Left-to-right attacking**.
- **Targets random**; Taunt forces selection among taunts.
- **Damage cap**: Turn 1-3 = 5, Turn 4-7 = 10, Turn 8+ = 15, removed at Top 4.
- **Player damage** = winner_tavern_tier + sum(survivor_tech_levels). Tokens = Tier 1.

For full rules, see `docs/BATTLEGROUNDS_RULES.md`.

---

## Testing Conventions

- Use `unittest` (already configured).
- Name tests descriptively: `test_<mechanic>_<scenario>`.
- Always import `hsrl.cards.minions` in test files to trigger registration.
- Create a fresh `Game` and `Player` instances in each test to avoid state leakage.
- Run full suite before committing: `python -m pytest hsrl/tests/ -v -q` (772 passed, 1 skipped as of 2026-06-04)

---

## What NOT to Do

- Do not add hidden state outside of `tags`.
- Do not hardcode mechanic logic inside card scripts; put it in `actions.py`.
- Do not skip the standard-example step when adding a new mechanism.
- Do not modify `fireplace/` (it is reference only).
- Do not rely on external wiki access; use `docs/BATTLEGROUNDS_RULES.md` as the authority.
- **Do not write long inline Python/shell scripts directly in Bash.** Write them to a script file under `/tmp/` first, then execute the script file via Bash.
- **Do not write "simplified" card implementations.** Cards have exactly two states: **CORRECT** (implementation matches card text precisely) or **DEFERRED** (not yet implemented, with a TODO listing required engine support). A "simplified" implementation that substitutes different behavior is a bug, not a simplification.
- **Do not implement Duos (双打) system or content.** This project is Solo-only. Duos cards/trinkets/heroes/mechanics are **OUT_OF_SCOPE** — mark them as such and never write scripts for them. Do not add Duos mechanics (pass, team interactions, etc.) to the engine.

## Web Access Policy

- **Single trusted external source**: https://hearthstone.wiki.gg/wiki/ (including /Tavern_Brawl subpages)
- If WebFetch is blocked by Cloudflare, use a crawler script (`/tmp/crawl_wiki.py`) to scrape pages and save results locally under `docs/wiki_crawls/` for future reference.

## Card Implementation Policy

### Two States Only

| State | Meaning | Code Convention |
|-------|---------|----------------|
| **CORRECT** | Implementation matches card text's exact operational semantics | Fully functional `@staticmethod` returning `Action` |
| **DEFERRED** | Engine support for the required mechanic doesn't exist yet | Method returns `None`, docstring clearly states dependency |

**There is no third state.** "Simplified" is not acceptable. If `GainGold(1)` replaces "Get a Tavern Coin" (a spell card that goes to hand), that is a **semantic bug** — the card should be DEFERRED until the coin spell system exists.

### DEFERRED Card Format

```python
class MyCardScript:
    """
    Natural language: <exact card text>

    Status: DEFERRED — requires <specific engine feature>
    Dependency: <what needs to be built first>
    """
    
    @staticmethod
    def battlecry(source, game):
        return None
```

### Card Text Reference

- Official card text: `data/pool_minion_texts.json` (270 pool minions, keyed by card ID)
- Original defs: `hsdata/CardDefs.xml`
- Docstring "Natural language" must match the official card text exactly

---

## File Organization

```
HSRL/
├── docs/                          # Frozen rulebooks (do not depend on web)
│   ├── BATTLEGROUNDS_RULES.md     # Complete game rules
│   ├── MECHANICS_REFERENCE.md     # Implementation reference
│   └── CARD_REGISTRATION_GUIDE.md # Card registration pipeline
├── hsrl/
│   ├── core/                      # Engine (read-only for card devs)
│   ├── cards/                     # Card definitions
│   │   ├── minions/               # Minion cards
│   │   ├── heroes/                # Hero cards
│   │   ├── spells/                # Spells (Blood Gems, etc.)
│   │   ├── trinkets/              # Trinket cards
│   │   ├── anomalies/             # Anomaly cards
│   │   └── rewards/               # Triple/quest rewards
│   ├── agents/                    # AI agents
│   │   ├── search_agent.py        # Hybrid search + value agent
│   │   ├── az_agent.py            # AlphaZero MCTS agent
│   │   └── agent_utils.py         # Action simulation + tavern helpers
│   ├── policy/                    # Entity-Token Transformer policy (5.25M)
│   │   ├── model_5m.py            # ScaledModel: d=256, 6-layer Transformer
│   │   ├── entity_tokenizer_v2.py # 37-slot tokenizer + card embeddings
│   │   ├── transformer.py         # Multi-head attention encoder
│   │   ├── heads.py               # Hierarchical action head
│   │   ├── value_head.py          # Distributional value head
│   │   ├── bc_train.py            # BC from heuristic teacher
│   │   └── iter_train.py          # Iterative BC self-improvement
│   ├── rl_env/                    # Next-gen RL environment
│   │   ├── observation/           # ObservationV2: 37 entity-slot layout
│   │   ├── action/                # Hierarchical action grammar
│   │   ├── reward/                # Board score v2 + reward components
│   │   ├── envs/                  # BoardBuildingEnv, TurnRecruitEnv
│   │   └── teachers/              # Plan search teacher
│   ├── env/                       # Legacy RL env (gitignored)
│   ├── train/                     # Legacy training scripts (gitignored)
│   ├── trajectory/                # Trajectory opponent system
│   │   ├── record.py              # MinionSnapshot, TurnSnapshot, Trajectory
│   │   ├── generate.py            # Batch heuristic game generator
│   │   ├── group.py               # Tribe-compatible grouping
│   │   └── opponent.py            # TrajectoryOpponent loader
│   ├── advisor/                   # HDT plugin Python backend
│   ├── utils/                     # Utility functions
│   └── tests/                     # All tests (772 passed)
├── AGENTS.md                      # This file
├── README.md                      # User-facing documentation (English)
├── README_CN.md                   # User-facing documentation (Chinese)
└── pyproject.toml                 # Project config
```

---

*文档版本：3.0.0 | 最后更新：2026-06-04*

## Current Status

| 子系统 | CORRECT | DEFERRED | OUT_OF_SCOPE |
|--------|---------|----------|-------------|
| Hero Powers (94) | 94 | 0 | — |
| Minions (218) | 218 | 0 | — |
| Trinkets (327) | 316 | 0 | 11 (Duos) |
| Anomalies (105) | 101 | 0 | 4 (Duos) |
| Quest Rewards (76) | 76 | 0 | — |
| **Total** | **805** | **0** | **15** |

**In-scope completion: 100%** | Tests: 772 passed, 1 skipped

All in-scope cards are CORRECT. Remaining OOS: 4 DUO anomalies + 11 DUO trinkets.
Buddy system: full engine infrastructure (meter/assign/purchase/golden/quest).

### RL Training Status

New entity-token Transformer policy (5.25M params) with iterative BC training:
- BC from heuristic: avg raw=33, board_score=2.2 (15-turn games)
- Iterative BC (3 rounds): avg raw=38, board_score=2.3
- Random baseline: avg raw=25-39, board_score=1.4
- Best board: raw=50, T3 with murloc synergy
- See `docs/AGENT_TRAINING_STATUS.md` for detailed history

### Scope Boundaries

- **IN SCOPE**: Solo Battlegrounds — all standard heroes, minions, hero powers, trinkets, spells, anomalies, quest rewards
- **OUT OF SCOPE**: Duos mode (传递/pass, team interactions, duo-exclusive cards)
- Duos trinkets use `OutOfScopeDuosScript` (no implementation)

### Key Engine Subsystems (Built During Phase 18-31)

| 子系统 | 位置 | 用途 |
|--------|------|------|
| `schedule_turn_action()` | game.py | 回合延迟触发 (异变/奖励) |
| Anomaly SoT/SoC/on_upgrade hooks | game.py/actions.py | 异变被动效果 |
| `_combat_summon_log` / `_combat_death_log` | game.py | 战斗追踪 |
| `_persist_combat_stats()` | game.py | Tarecgosa 战斗属性保留 |
| `_deal_player_damage()` Eleventh Hour | game.py | 致命伤害防止 |
| `CastYoggWheel` | actions.py | 尤格-萨隆命运之轮 (12种随机效果) |
| `GuessMinion` | actions.py | 猜测对手随从 |
| `DiscoverReward` | actions.py | 奖励发现系统 |
| `remove_all_copies()` | minion_pool.py | 池移除 (Eject Minions) |
| `RALLY_DOUBLED` | enums.py + Attack.do() | Rally 翻倍 |
| `HEALTH_COST_DEMON/SPELL` | enums.py + buy_minion/spell | 生命值购买 |
| `NEXT_PURCHASE_GOLDEN` | enums.py + play_minion | 购买自动变金 |
| `HERO_POWER_EXTRA_USES` | enums.py + UseHeroPower | 额外英雄技能 |
| `PIRATES_NEED_2_COPIES` | enums.py + _check_for_triple | 2复制变金 |
| `_last_discovered_id` | DiscoverMinion.do() | 发现追踪 |
| Gold carryover | _start_recruit_phase | 金币跨回合保留 |
| Buddy system | tokens.py | 160+ 伙伴卡牌注册 |
| `SPELLCRAFT_CAST` event | events.py + game.py | 法术技艺施放追踪 |
| `_allowed_tiers` / `_tavern_always_7` | game.py | 酒馆等级/数量过滤引擎 |
| `_cost_equals_tier` / `_minions_cost_2` | game.py | 购买价格覆写引擎 |
| `_tavern_min_tier` (per-player) | game.py | 玩家级别最低酒馆等级 |
| `_no_type_has_all` | entity.py | 无种族→全类型转换 |
| Buddy system (meter, assign, purchase) | game.py + player.py | 伙伴计量器/分配/购买 |
| `DiscoverTrinket` | actions.py | 饰品发现 + 替换 |
| `_select_active_tribes()` | game.py | 每局随机选 5/10 种族 |
| `race_filter=` param | minion_pool.py → game.py | 酒馆刷新仅出选中种族 |
| Trajectory system | trajectory/ | 轨迹生成/分组/对手注入 |
| `trajectory_trainer.py` | train/ | Phase 1 轨迹对手 PPO 训练 |

---

## HDT Plugin & Advisor Development

### Architecture

```
hsrl_advisor/                    # C# HDT Plugin (Windows only)
  plugin/
    HrSRLAdviser.csproj          # .NET Framework 4.7.2 Class Library
    plugin.json                  # HDT plugin manifest
    AdviserPlugin.cs             # IPlugin 生命周期 + 事件订阅
    GameStateExtractor.cs        # GameTag → JSON state 提取
    WebSocketClient.cs           # Python 后端通信
    SuggestionOverlay.cs         # WPF 建议面板 UI

hsrl/advisor/                    # Python Inference Server (Linux)
    server.py                    # WebSocket 服务器 + 消息路由
    state_mapper.py              # HDT JSON → 360-dim observation
    inference.py                 # 模型加载 + 推理
    collector.py                 # 对战数据收集 (JSONL)
    overlay_protocol.py          # 消息协议 dataclass 定义
    cli.py                       # 命令行入口

docs/HDT_INTERFACE.md            # HDT 接口参考 + 训练观察对齐表
```

### Development Workflow (Cross-Platform)

1. **编辑** — 在 Linux (`/home/glt/HrSRL/`) 编辑代码
2. **同步** — `cp` 到 Windows 挂载点 (`/mnt/c/Users/letgao/HRSRL/`)
3. **编译** — 在 Windows Visual Studio / `dotnet build` 编译 C# 插件
4. **重启** — 重启 Python 推理服务器 + HDT 加载插件
5. **日志** — C# 日志: `%LOCALAPPDATA%\HearthstoneDeckTracker\hrsrl_adviser.log`；Python 日志: 控制台输出

### File Sync Checklist

修改以下任一文件后，必须同步到 Windows:

| Linux Path | Windows Path |
|------------|-------------|
| `hsrl_advisor/plugin/GameStateExtractor.cs` | `%APPDATA%\..\..\Users\letgao\HRSRL\hsrl_advisor\plugin\GameStateExtractor.cs` |
| `hsrl/advisor/server.py` | `/mnt/c/Users/letgao/HRSRL/hsrl/advisor/server.py` |
| `hsrl/advisor/state_mapper.py` | `/mnt/c/Users/letgao/HRSRL/hsrl/advisor/state_mapper.py` |

### GameTag Mapping Convention

C# (HearthDb) 和 Python (core/enums.py) 的 GameTag 枚举名可能不同，但数值一致（均源于 Hearthstone 协议）。在 C# 中使用不常见的 GameTag 时：

```csharp
// 优先使用 HearthDb 命名
ent.GetTag(GameTag.BACON_FREE_REFRESH_COUNT);

// HearthDb 命名不确定时，使用数值 cast
ent.GetTag((GameTag)138);  // NEXT_SPELL_COST_REDUCTION
ent.GetTag((GameTag)120);  // BLOOD_GEM_BONUS_ATK
```

对照表见 `docs/HDT_INTERFACE.md` §2。

### Testing

```bash
# Python 端测试 (Linux)
python -m pytest hsrl/tests/test_advisor.py -v

# 全量回归测试
python -m pytest hsrl/tests/ -v

# 推理服务器启动
python -m hsrl.advisor.cli --model checkpoints/best_model.zip
```

### What NOT to Do

- 不要在 C# 中硬编码 GameTag 数值而不加注释说明含义
- 不要跳过跨平台同步 — Windows 端看不到 Linux 的修改
- 不要直接修改 Windows 副本再反向同步 — Linux 端是 canonical source
- 不要在生产模式下关闭数据采集（`--collect-data` 默认开启）

---

*文档版本：2.2.0 | 最后更新：2026-05-08*
