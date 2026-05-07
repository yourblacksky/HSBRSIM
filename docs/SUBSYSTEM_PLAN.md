# HSRL 子系统实现规划

> 本文档列出所有待实现的子系统，按依赖关系和影响范围排序。
> 每个子系统包含：影响的卡牌数量、设计思路、需要修改的文件。
>
> **版本**: 0.3.0 | **日期**: 2026-04-30

---

## 目录

1. [Phase 1: Rally（集结）](#phase-1-rally集结)
2. [Phase 2: 光环/全局Buff追踪](#phase-2-光环全局buff追踪)
3. [Phase 3: Blood Gem（鲜血宝石）](#phase-3-blood-gem鲜血宝石)
4. [Phase 4: 目标选择系统](#phase-4-目标选择系统)
5. [Phase 5: Discover（发现）](#phase-5-discover发现)
6. [Phase 6: 法术/衍生物系统](#phase-6-法术衍生物系统)
7. [Phase 7: "Improved by" 计数器](#phase-7-improved-by-计数器)
8. [Phase 8: Fodder（恶魔吞噬）](#phase-8-fodder恶魔吞噬)
9. [Phase 9: Chromadrake](#phase-9-chromadrake)
10. [附录：实现顺序与依赖图](#附录实现顺序与依赖图)

---

## Phase 1: Rally（集结） ✅ 已完成

**影响卡牌**: 6 张 (已全部实现)
**状态**: ✅ 完成
**依赖**: 无

### 设计

Rally 在随从攻击宣告时触发，**在伤害结算之前**。这不同于"攻击后"触发 — Rally 效果在攻击者造成伤害之前结算。

关键实现细节：
- `Attack.do()` 在 `BEFORE_ATTACK` 广播后、`Hit` 排队前触发 Rally
- `game._last_attack_target` 在 Rally 触发前设置，供脚本引用攻击目标
- Rally 脚本无需检查 `target.dead`，因为目标在 Rally 触发时必定存活

### 已实现的卡牌

| 卡牌ID | 名称 | Rally 效果 |
|--------|------|-----------|
| BG25_016 | Sin'dorei Straight Shot | 移除目标的复生和嘲讽 |
| BG27_017 | Obsidian Ravager | 对目标和相邻随从造成等同攻击力的伤害 |
| BG33_241 | Sleepy Supporter | 使右边的随从获得 +1/+1 |
| BG33_318 | Bile Spitter | 使另一个友方鱼人获得烈毒 |
| BG33_840 | Stomping Stegodon | 使你的其他野兽获得 +1 攻击力 |
| BG34_604 | Heroic Underdog | 获得目标的攻击力 |

### 尚有脚本未实现的 Rally 卡牌 (9 张，依赖后续 Phase)

| 卡牌ID | Rally 效果 | 依赖 |
|--------|-----------|------|
| BG33_323 | 你的亡灵本局获得 +1 攻击力 | Phase 2 (光环) |
| BG33_822 | 随机获得一张悬赏牌 | Phase 6 (法术/衍生物) |
| BG34_140 | 从手牌召唤攻击力最高的随从 | Phase 4 (目标选择) |
| BG34_319 | 随机获得一张 6 星随从 (BC+DR+Rally) | Phase 5 (发现) |
| BG34_320 | 使每种类型的友方随从获得 +1/+1 | Phase 4 (目标选择) |
| BG34_925 | 对右边的随从施放 Chef's Choice | Phase 6 (法术) |
| BG34_926 | 施放 Queen's Command (BC+DR+Rally) | Phase 6 (法术) |
| BG35_700 | 召唤一个 Sky Pirate 优先攻击目标 | Phase 4+6 |
| BGS_078 | 触发最左侧亡语 | Phase 4 (目标选择) |

### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/enums.py` | `RALLY = 65` 已存在 |
| `core/entity.py` | 添加 `rally` 属性 |
| `core/actions.py` | `Attack.do()` 开头触发 Rally（伤害结算前） |
| `core/game.py` | 添加 `_last_attack_target` 字段 |
| `cards/minions/pool.py` | 添加 `_TEXT_KEYWORDS` 文本关键词检测（Rally 不在 JSON 布尔字段中） |
| `cards/minions/scripts.py` | 6 个 Rally 脚本类 |
| `cards/minions/__init__.py` | EXAMPLE_RALLY 标准示例卡牌 |
| `tests/test_core_mechanics.py` | 8 个 Rally 测试用例 |

### 重要发现

Rally 关键词不以布尔字段形式存储在 `bg_pool_minions.json` 中，仅存在于卡牌文本。
因此 `pool.py` 新增了 `_TEXT_KEYWORDS` 机制从文本中检测关键词。
同理 `Start of Combat` 也需从文本检测（已加入 `_TEXT_KEYWORDS`）。

---

## Phase 2: 光环/全局Buff追踪 ✅ 已完成（首批）

**影响卡牌**: 2 张已实现（共 ~12 张，其余需后续 Phase）
**状态**: ✅ 首批完成
**依赖**: 无

### 设计

`GlobalAura` 对象存储在 `Player.auras` 列表中，持久生效永不过期。`BaseEntity.atk` / `max_health` 每次计算时查询 `controller.get_global_aura_bonus()` 来叠加匹配的光环加成。

```
atk = BASE_ATK + sum(buffs) + sum(matching_auras) → script override → clamp
```

种族匹配规则：
- `race_filter=None` → 对所有随从生效
- `race_filter=Race.UNDEAD` → 仅匹配指定种族
- `Race.ALL` 随从匹配任何种族筛选

### 已实现的卡牌

| 卡牌ID | 名称 | 效果 | 类型 |
|--------|------|------|------|
| BG25_011 | Nerubian Deathswarmer | BC: Your Undead have +1 Attack this game | Battlecry |
| BG34_690 | Plaguerunner | DR: Your Undead have +X Attack (X=3,4,5...) | Deathrattle |

### 暂缓卡牌（依赖其他 Phase）

| 卡牌ID | 原因 |
|--------|------|
| BG25_041, BG31_815, BG27_016, BG35_152 | 需要 Tavern 酒馆系统 |
| BG26_159, BG26_160 | 需要 Phase 3 (Blood Gem) |
| BG32_880, BG34_635t, BG34_638t | 需要 Phase 6 (Tavern Spell) |
| BG34_856 | 需要 Refresh 刷新机制 |

### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/enums.py` | 添加 `PLAGUERUNNER_SCALE = 122` |
| `core/actions.py` | 添加 `GlobalAura` 类 + `ApplyGlobalAura` Action |
| `core/player.py` | 添加 `auras` 列表 + `get_global_aura_bonus()` |
| `core/entity.py` | `atk`/`max_health` 属性添加全局光环查询 |
| `cards/minions/__init__.py` | `EXAMPLE_GLOBAL_AURA` 标准示例 |
| `cards/minions/scripts.py` | 2 个脚本 + SCRIPT_REGISTRY |
| `tests/test_core_mechanics.py` | 3 个测试类，17 个测试 |

---

## Phase 3: Blood Gem（鲜血宝石） ✅ 已完成

**影响卡牌**: 11 张已实现（共 24 张，13 张暂缓）
**状态**: ✅ 完成
**依赖**: Phase 2 (全局光环, 用于Blood Gem增强)

### 设计

Blood Gem 的默认效果是 `Buff(target, atk=1, health=1)`，通过 `PlayBloodGems` Action 实现。

增强链：
- `ImproveBloodGem` Action 递增 `BLOOD_GEM_BONUS_ATK` / `BLOOD_GEM_BONUS_HEALTH`（Player tags）
- `PlayBloodGems` 读取这些 bonus 来计算有效 buff 值：`(1 + bonus_atk) * count`

"Get a Blood Gem" 在当前引擎简化为自动对自身施放（手牌法术系统需 Phase 6）。

### 已实现的卡牌 (11 张)

| 卡牌ID | 名称 | 效果 | 类型 |
|--------|------|------|------|
| BG23_017 | Sanguine Champion | BC&DR: Blood Gems give extra +1/+1 | Improver |
| BG26_159 | Moon-Bacon Jazzer | BC: Blood Gems give extra +1 Health | Improver |
| BG26_160 | Prickly Piper | DR: Blood Gems give extra +1 Attack | Improver |
| BG25_155 | Gem Smuggler | BC: Play 2 Blood Gems on all other minions | Multi-Target |
| BG26_867 | Three Lil' Quilboar | DR: Play 3 Blood Gems on all Quilboar | Multi-Target |
| BG26_157 | Bristlebach | Avenge(2): Play 2 Blood Gems on all Quilboar | Multi-Target |
| BG32_430 | Glowgullet Warlord | DR: Summon two 1/1 Quilboar, play Blood Gem on them | Combined |
| BG32_434 | Skulking Bristlemane | DR: Play permanent Blood Gem on adjacent | Combined |
| BG20_100 | Razorfen Geomancer | BC: Get 2 Blood Gems → play on self | Simplified |
| BG33_888 | Hog Watcher | BC: Get Blood Gem (DS version) → play on self + DS | Simplified |
| BG35_432 | Bristleback Bully | DR: Get Blood Gem (Taunt version) → play on self | Simplified |

### 暂缓卡牌 (13 张，依赖其他 Phase)

| 卡牌ID | 原因 |
|--------|------|
| BG20_301 (Sun-Bacon Relaxer) | "When you sell this" → 需要出售系统 |
| BG20_203 (Prophet of the Boar) | "After you play a Quilboar" → 需要招募系统 |
| BG24_707 (Bristlemane Scrapsmith) | "After friendly Taunt dies" → 需要事件系统 |
| BG30_123 (Fearless Foodie) | "Choose One" → 需要选择机制 |
| BG28_583 (Geomagus Roogug) | "Whenever Blood Gem played on this" → 需要事件监听 |
| BG35_434 (Hired Ritualist) | "Once per turn" → 需要回合系统 |
| BG35_433 (Redtusk Thornraiser) | "At end of turn" → 需要回合系统 |
| BG23_018 (Darkgaze Elder) | "Whenever spend Gold" → 需要金币事件 |
| BG30_121 (Hot-Air Surveyor) | "from hand cast twice" → Phase 6 |
| BG35_431 (Earthsong Shaman) | "At end of turn" + keyword → 复杂 |
| BG35_437 (Vinespeaker) | "After friendly DR minion dies" → 需要事件系统 |
| BGDUO_111 (Generous Geomancer) | Duos teammate → 双打系统 |
| BGDUO31_202 (Loyal Mobster) | Duos teammate → 双打系统 |

### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/actions.py` | 添加 `ImproveBloodGem` Action |
| `core/enums.py` | `BLOOD_GEM_BONUS_ATK=120`, `BLOOD_GEM_BONUS_HEALTH=121` (已存在) |
| `cards/minions/__init__.py` | 添加 `ImproveBloodGem` import |
| `cards/minions/tokens.py` | 添加 `BG32_430t` Glowgullet Soldier (1/1 Quilboar Taunt) |
| `cards/minions/scripts.py` | 9 个新脚本 + 2 个修复 + SCRIPT_REGISTRY 更新 |
| `tests/test_core_mechanics.py` | 4 个新测试类，19 个测试 |

---

## Phase 4: 目标选择系统

**影响卡牌**: ~8 张
  - BG26_814 (Lovesick Balladist): BC: Give a Pirate +X Health
  - BG28_303 (Disguised Graverobber): BC: Destroy a friendly Undead, get copy
  - BG35_702 (Roving Sailor): BC: Give a friendly minion +X/+Y
  - BG26_525 (Imposing Percussionist): BC: Discover a Demon, deal damage to hero

**难度**: 中
**依赖**: 无 (但需要"招募阶段交互"框架)

### 设计

对于 RL 环境，目标选择可以简化为"随机选择有效目标"或"选择最优目标（按启发式规则）"。

```python
# 卡牌脚本标记需要选择目标
class LovesickBalladistScript:
    TARGET_TYPE = "friendly_pirate"  # 或 "friendly_minion", "enemy_minion" 等
    
    @staticmethod
    def battlecry(source, game, target=None):
        if target is None:
            # 随机选择一个有效目标（用于 RL 快速模拟）
            targets = get_valid_targets(source, "friendly_pirate")
            if targets:
                target = random.choice(targets)
            else:
                return None
        return Buff(target, atk=0, health=source.get_tag(GameTag.TEMP_BUFF))
```

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/actions.py` | 添加 `TargetedAction` 基类 |
| `core/game.py` | 添加 `get_valid_targets(entity, target_type)` 辅助方法 |
| `cards/minions/scripts.py` | 实现目标选择卡牌脚本 |

---

## Phase 5: Discover（发现）

**影响卡牌**: ~10 张
  - BGS_020 (Primalfin Lookout): BC: If control Murloc, Discover a Murloc
  - BG26_525 (Imposing Percussionist): BC: Discover a Demon
  - BG28_550 (Rodeo Performer): BC: Discover a Tavern spell
  - BG34_523 (Hunting Tiger Shark): BC: Discover a Beast
  - BGS_123 (Tavern Tempest): BC: Get a random Elemental (简化版Discover)
  - BG34_632 (Incubation Researcher): Avenge: Get random Chromadrake

**难度**: 中
**依赖**: Phase 4 (部分Discover需要Target选择)

### 设计

对于 RL 环境，Discover 可以简化为：
1. 从符合条件的卡池中随机抽取 3 张
2. 选择"最优"的（按启发式规则）或随机选择
3. 将选中的卡牌加入手牌

```python
def discover(game, player, pool_filter, count=3):
    """简化版 Discover：随机抽取 N 张，选一张加入手牌。"""
    candidates = game.card_db.filter(pool_filter)
    if not candidates:
        return None
    offered = random.sample(candidates, min(count, len(candidates)))
    # RL 模式下自动选择"最优"的（按 tier 最高）
    chosen = max(offered, key=lambda c: c.tech_level)
    minion = game.create_minion(chosen.id)
    player.hand.append(minion)
    minion.zone = Zone.HAND
    return minion
```

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/card_db.py` | 添加 `filter(race, tier_range)` 方法 |
| `core/game.py` | 添加 `discover()` 方法 |
| `cards/minions/scripts.py` | 实现 Discover 相关脚本 |

---

## Phase 6: 法术/衍生物系统

**影响卡牌**: ~10 张
  - BG27_002 (Oozeling Gladiator): BC: Get two Slimy Shields
  - BG28_550 (Rodeo Performer): BC: Discover a Tavern spell
  - BG32_111 (Nightmare Par-tea Guest): BC&DR: Get Misplaced Tea Set
  - BG32_170 (Metallic Hunter): DR: Get Pointy Arrow
  - BG32_891 (Shadowdancer): DR: Get Staff of Enrichment
  - BG33_809 (Divine Sparkbot): DR: Get Sanctify
  - BG34_694 (Wintergrasp Ghoul): DR: Get Tomb Turning
  - BG34_926 (Ruthless Queensguard): BC&DR&Rally: Cast Queen's Command
  - BG35_881 (Leyline Surfacer): BC&DR: Get Arcane Absorption
  - BG35_882 (Firelands Fugitive): BC: Get Conflagration

**难度**: 高
**依赖**: 无

### 设计

法术是特殊的卡牌类型（CardType.SPELL），可以从手牌打出，具有一次性效果。
Tavern spells 在酒馆中刷新，1 金/回合固定出现 1 张。

```python
class Spell(BaseEntity):
    """A spell card in hand."""
    def __init__(self, data, game=None):
        super().__init__(data, game)
        self.zone = Zone.HAND
    
    def cast(self, target=None):
        """Cast this spell. Returns Action(s)."""
        if self.data.scripts:
            return self.data.scripts.cast(self, self.game, target)
        return None
```

对于简单实现，法术效果可以直接通过 `register_card` + script 的 `cast` 方法实现。

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/enums.py` | 确认 `SPELL` 卡片类型、法术相关标签 |
| `core/entity.py` | 添加 `Spell` 子类 |
| `core/actions.py` | 添加 `CastSpell` Action |
| `core/card_db.py` | 支持法术卡注册 |
| `cards/spells/` | 新目录：法术定义 |
| `data/` | bg_pool_spells.json 数据加载 |

---

## Phase 7: "Improved by" 计数器

**影响卡牌**: ~5 张
  - BG26_814 (Lovesick Balladist): Improved by each Gold spent this turn
  - BG35_140 (Mama Mrrglton): Improved by each Mrrglton you play this game
  - BG35_141 (Papa Mrrglton): Improved by each Mrrglton you play this game
  - BG35_150 (Laboratory Assistant): Add Fodder to next X Refreshes
  - BG35_702 (Roving Sailor): Improved by each Tavern spell you play this game

**难度**: 低
**依赖**: 无

### 设计

在 `Player` 上维护计数器。每局游戏开始时初始化，每次触发条件时 +1。

```python
# 在 Player 上:
self._counters = {
    "mrrgletons_played": 0,
    "gold_spent_this_turn": 0,
    "tavern_spells_played": 0,
}
```

脚本中查询计数器来决定 buff 值：

```python
class MamaMrrgltonScript:
    @staticmethod
    def battlecry(source, game):
        count = source.controller.get_counter("mrrgletons_played", 0)
        return Buff(m, atk=1 + count, health=0)
```

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/player.py` | 添加 `_counters` 字典和 `get_counter`/`increment_counter` |
| `core/game.py` | 每回合重置 `gold_spent_this_turn` |
| `cards/minions/scripts.py` | 更新 Mrrglton 脚本使用计数器 |

---

## Phase 8: Fodder（恶魔吞噬）

**影响卡牌**: ~3 张
  - BG35_150 (Laboratory Assistant): BC: Add Fodder to next X Refreshes
  - 其他具有 Fodder 的恶魔随从

**难度**: 中
**依赖**: Phase 4 (目标选择)

### 设计

Fodder 效果需要一个 "吞噬目标选择" 步骤。在 RL 环境中可以自动选择。

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `core/enums.py` | 添加 `FODDER` 标签 |
| `core/actions.py` | 添加 `FodderConsume` Action |
| `cards/minions/scripts.py` | 实现 Fodder 恶魔脚本 |

---

## Phase 9: Chromadrake

**影响卡牌**: ~5 张
  - BG34_632 (Incubation Researcher): Avenge: Get random Chromadrake
  - BG34_633 (Draconic Warden): BC&DR: Get random Chromadrake
  - BG34_634t (Blue Chromadrake): BC: Get random X-Cost Tavern spell
  - BG34_635t (Black Chromadrake): BC: Tavern spells give extra +X Health
  - BG34_636t (Green Chromadrake): BC: Give your other Dragons +X/+Y (已实现)
  - BG34_637t (Bronze Chromadrake): BC: Give your other Dragons +X/+Y (已实现)
  - BG34_638t (Red Chromadrake): BC: Tavern spells give extra +X Attack

**难度**: 中
**依赖**: Phase 2 (光环), Phase 5 (Discover), Phase 6 (法术)

### 设计

Chromadrake 不是"变形"机制——Chroma 龙是独立的 pool minion。它们通过 Discover/随机生成进入玩家手牌，在打出时触发战吼。核心是实现 Discover 和法术系统。

Green 和 Bronze Chromadrake 的战吼已实现。其余需要：
- Blue: Get random Tavern spell → 需要法术池
- Black/Red: 光环效果 → 需要 Phase 2

---

## 附录：实现顺序与依赖图

```
Phase 1: Rally ─────────────────────── (无依赖, 1h)
    ↓
Phase 2: 全局光环 ──────────────────── (无依赖, 2h)
    ↓
Phase 7: 计数器 ────────────────────── (无依赖, 1h)
    ↓
Phase 4: 目标选择 ──────────────────── (无依赖, 2h)
    ↓
Phase 3: Blood Gem ─────────────────── (需要 Phase 2, 7, 2h)
    ↓
Phase 5: Discover ──────────────────── (需要 Phase 4, 2h)
    ↓
Phase 6: 法术系统 ──────────────────── (无依赖但复杂, 3h)
    ↓
Phase 8: Fodder ─────────────────────── (需要 Phase 4, 1h)
    ↓
Phase 9: Chromadrake ───────────────── (需要 Phase 2, 5, 6; 大部分已实现)
```

**总影响**: 实现全部子系统后，可录入剩余的 ~70 张效果随从。

---

*文档版本：0.3.0 | 最后更新：2026-04-30*
