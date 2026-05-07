# 卡牌效果系统

酒馆战棋卡牌效果执行引擎的完整文档。定义了战吼、亡语、复仇、回合结束、战斗开始和光环六种触发时机的结构化效果数据与执行流程。

## 概述

`hsrhl/engine/effects.py` 提供配置驱动的卡牌效果系统，由 `config/card_effects.json` 定义每张卡牌的具体效果。效果在游戏流程的特定时机自动触发：

| 触发时机 | 触发点 | 示例 |
|---------|--------|------|
| `BATTLECRY` | `env._handle_play()` — 随从进场后 | 纳斯雷兹姆监工: 给一个友方随从 +2/+2 |
| `DEATHRATTLE` | `combat._resolve_deaths_gen_queue()` — 代际队列死亡处理中 | 巨狼戈德林: 给所有友方野兽 +4/+4 |
| `END_OF_TURN` | `env.advance_turn()` — 推进到下一回合前 | 光牙执行者: 给2个友方随从 +2/+2 |
| `AVENGE` | `combat._resolve_deaths_gen_queue()` — 累计友方死亡数达到阈值 | 鸟类的伙伴(复仇1): 给所有友方随从 +1攻击 |
| `RALLY` | `combat._resolve_battle_python()` — 随从攻击时，伤害结算前 | 伊瑞尔: 使每个类型的各一个友方随从获得 +1/+2 |
| `START_OF_COMBAT` | `combat.resolve_battle()` — 战斗克隆前 | 饥饿的憎恶: 给所有友方随从 +1/+1 |
| `AURA` | `combat._apply_aura_buffs()` — 战斗克隆后 | 持续光环效果 |

## 架构

```
config/card_effects.json       hsrhl/engine/effects.py
         │                              │
         │ EffectExecutor.load()        │
         ├──────────────────────────────┤
         │   _registry[dbf_id] = CardEffects([EffectDef, ...])
         │                              │
         │                              ├── trigger(trigger, dbf_id, source, board, ctx)
         │                              │   ├── _resolve_effect_value() → dynamic stats
         │                              │   ├── _resolve_targets() → [targets]
         │                              │   └── _apply_effect() → descriptions
         │                              │
         │                              ├── trigger_spell(dbf_id, board, ctx)
         │                              ├── get_aura_buffs(dbf_id) → [EffectDef]
         │                              └── has_effects(dbf_id) → bool
         │
         ├── env._handle_play() ──→ trigger(BATTLECRY, ...) → effect_log
         ├── env.advance_turn() ──→ trigger(END_OF_TURN, ...) → effect_log
         ├── env._handle_play_spell() ──→ trigger_spell(...) → effect_log
         └── combat.resolve_battle() ──→ trigger(START_OF_COMBAT, ...)
                                       → trigger(DEATHRATTLE, ...)     ├── collected in
                                       → trigger(AVENGE, ...)         │   CombatResult
                                       → trigger(RALLY, ...)          │   .effect_log
                                       → _apply_aura_buffs(...)       │
```

## 数据格式

### EffectDef

```python
@dataclass
class EffectDef:
    type: EffectType       # 效果类型
    trigger: str           # 触发时机
    target: Target         # 目标选择器
    attack: int = 0        # 攻击力变化
    health: int = 0        # 生命值变化
    keyword: str = ""      # 关键词
    damage: int = 0        # 伤害值
    gold: int = 0          # 金币
    dbf_id: int = 0        # 关联卡牌 (召唤/加入手牌)
    race: str = ""         # 种族过滤 (friendly_type 目标)
    count: int = 1         # 目标数量, 99 = 全体
    random: bool = False   # 随机选择 vs 全体
    avenge_count: int = 0  # 复仇触发阈值
    # 动态值 (Phase 3 新增)
    value_from: str = ""   # 动态值来源: source_attack/health, hand_highest_attack/health, hand_all_stats
    value_mult: float = 1.0 # 值倍率 (2.0 = 翻倍)
    set_attack: int = 0    # 固定攻击力 (set_stats)
    set_health: int = 0    # 固定生命值 (set_stats)
    blood_gem_count: int = 0  # 血宝石数量
    card_tier: int = 0     # 卡牌等级过滤 (add_random_card)
    card_race: str = ""    # 卡牌种族过滤
    card_keyword: str = "" # 卡牌关键词过滤 (add_random_card)
    card_source: str = ""  # "minion_pool" | "spell_pool" | "last_spell"
    permanent: bool = False # 永久效果
```

### card_effects.json 示例

```json
{
  "dbf_id": 59955,
  "name": "巨狼戈德林",
  "effects": [
    {
      "type": "stat_buff",
      "trigger": "deathrattle",
      "target": "friendly_type",
      "race": "Beast",
      "attack": 4,
      "health": 4,
      "count": 99
    }
  ]
}
```

## 效果类型

| 类型 | 描述 | 关键参数 |
|------|------|---------|
| `stat_buff` | +X/+Y 属性变化 | attack, health, value_from |
| `summon` | 召唤 token 随从到场 | dbf_id, count |
| `gain_keyword` | 获得关键词 | keyword |
| `deal_damage` | 造成伤害 | damage, value_from |
| `gain_gold` | 获得金币 | gold |
| `add_to_hand` | 加入手牌 | dbf_id |
| `health` | 治疗 | health |
| `discover` | 发现机制 | — |
| `double_stats` | 属性值翻倍 | — |
| `set_stats` | 设为固定属性值 | set_attack, set_health |
| `gain_blood_gem` | 获得鲜血宝石 | blood_gem_count |
| `add_random_card` | 随机获取卡牌 | card_tier, card_race, card_keyword, card_source |
| `make_golden` | 变为金色 (三倍属性) | — |
| `tavern_buff` | 酒馆随从属性 | attack, health |

## 目标选择器

| 目标 | 描述 |
|------|------|
| `self` | 自身 |
| `friendly_random` | 随机N个友方 (count 控制数量) |
| `friendly_all` | 全体友方 |
| `friendly_other` | 除自身外的友方 |
| `friendly_adjacent` | 相邻友方 |
| `friendly_type` | 指定种族的友方 (race 过滤, count 控制数量) |
| `friendly_left` | 最左侧友方 (count 控制数量) |
| `friendly_right` | 最右侧友方 |
| `enemy_random` | 随机N个敌方 |
| `enemy_all` | 全体敌方 |
| `tavern` | 酒馆卡牌 |
| `hero` | 英雄 |

## 环境集成

### 战吼 (env.py)

随从被打出到场上后立即触发:

```python
# env._handle_play()
p.board.insert(position, combat_m)
bc_ctx = {"player": p, "pool": self.pool, "enemy_board": [], "tavern_slots": p.tavern_slots or []}
self.effect_executor.trigger(Trigger.BATTLECRY, combat_m.dbf_id, combat_m, p.board, bc_ctx)
```

### 回合结束 (env.py)

推进到下一回合前，遍历所有存活玩家的场上随从触发:

```python
# env.advance_turn()
for m in p.board:
    if m.alive:
        self.effect_executor.trigger(Trigger.END_OF_TURN, m.dbf_id, m, p.board, eot_ctx)
```

### 战斗结算 (combat.py)

```python
# combat.resolve_battle() — 参数传递 + 效果日志收集
effect_executor=self.effect_executor, minion_pool=self.pool

# 战斗开始效果 — 在战斗克隆前触发，标记 [SOC]
# 进击效果 — 随从攻击时，伤害结算前触发，标记 [Rally]
# 亡语和复仇 — 在代际队列 _resolve_deaths_gen_queue() 中触发，标记 [DR]/[Avenge]
# 光环 — 在战斗克隆后通过 _apply_aura_buffs() 应用，标记 [Aura]
# 
# 所有战斗中产生的效果描述收集到 CombatResult.effect_log，返回给调用方:
#   result = combat.resolve_battle(...)
#   for desc in result.effect_log:  # ["[SOC] 随从名: desc", "[DR] 随从名: desc", ...]
```

### 效果日志来源标记

战斗中效果按来源标记，便于调试和可视化:

| 标记 | 触发时机 | 代码位置 |
|------|---------|---------|
| `[SOC]` | Start of Combat | `resolve_battle()` — 克隆前 |
| `[Rally]` | 进击 | `_resolve_battle_python()` — 攻击时 |
| `[DR]` | Deathrattle | `_resolve_deaths_gen_queue()` — 代际队列 |
| `[Avenge]` | 复仇 | `_resolve_deaths_gen_queue()` — 代际队列 |
| `[Aura]` | 光环 | `_apply_aura_buffs()` — 克隆后 |


## 复仇机制

复仇效果在战斗中追踪友方随从死亡数，达到阈值后触发。

- `CombatMinion.avenge_deaths_seen`: 战斗中累积的友方死亡计数
- `EffectDef.avenge_count`: 触发阈值 (如复仇2需要2个友方死亡)
- 触发后计数器自动清零

代际队列中每代死亡发生后，更新所有存活友方随从的复仇计数器:

```python
for m in board:
    if m.alive:
        m.avenge_deaths_seen += dead_count
        effect_executor.trigger(Trigger.AVENGE, m.dbf_id, m, board, ctx)
        # 若触发成功 → avenge_deaths_seen = 0
```

## 效果覆盖

当前 `config/card_effects.json` 定义 **595 条**卡牌效果，覆盖全部 **519 张**具有触发关键词的随从:

| 触发时机 | 效果数量 | 说明 |
|---------|---------|------|
| `deathrattle` | 175 | 亡语效果 |
| `battlecry` | 150 | 战吼效果 |
| `end_of_turn` | 88 | 回合结束效果 |
| `rally` | 50 | 进击效果 |
| `avenge` | 50 | 复仇效果 |
| `start_of_combat` | 46 | 战斗开始效果 |
| `aura` | 36 | 光环效果 |

| 效果类型 | 数量 | 说明 |
|---------|------|------|
| `stat_buff` | 336 | 属性变化 |
| `summon` | 63 | 召唤 token |
| `add_to_hand` | 66 | 加入手牌 |
| `gain_gold` | 33 | 获得金币 |
| `gain_keyword` | 34 | 获得关键词 |
| `deal_damage` | 21 | 造成伤害 |
| `add_random_card` | 17 | 随机获取卡牌 |
| `tavern_buff` | 11 | 酒馆 buff |
| `double_stats` | 4 | 属性翻倍 |
| `make_golden` | 4 | 变为金色 |
| `gain_blood_gem` | 2 | 获得血宝石 |
| `set_stats` | 2 | 设为固定值 |
| `health` | 1 | 治疗 |
| `discover` | 1 | 发现 |

- T1-T6 卡牌效果：**全部已手动审计**（2026-04-29），引擎验证（Phase 3）
- **518/595 效果** (87%) 使用精确实现匹配卡牌文字描述
- **77 效果**标注 `_note: not_implemented`，原因包括：双倍触发(4)、磁力系统(4)、计数缩放(15+)、特定法术施放(5)、变形/复制(6)、永久效果(3)、吞食酒馆(2)、进化(1) 等——均需新子系统支持
- 无虚假近似值：所有未实现效果均诚实标注，不含误导性数值

## 效果测试与演示

### 完整对局演示

```bash
# 8人对局，含效果触发日志、战斗效果展示、终局覆盖率统计
python scripts/demo_render.py --seed 42
```

输出包括:
- 每步操作后的战吼/法术效果日志
- 回合结束效果汇总
- 战斗效果详情 (含 [SOC]/[Rally]/[DR]/[Avenge]/[Aura] 来源标记)
- 终局效果类型覆盖率统计

### 效果类型专项测试

```bash
# 直接验证各效果类型引擎实现正确性
python scripts/demo_render.py --test-effects
```

测试覆盖:
- `stat_buff`, `summon`, `gain_keyword`, `deal_damage` — 核心效果
- `double_stats`, `set_stats`, `make_golden` — Phase 3 新增
- `value_from` (source_attack/hand_all_stats 等) — 动态值解析
- `gain_gold`, `add_to_hand`, `tavern_buff`, `gain_blood_gem`, `add_random_card` — 需环境上下文

## 相关文档

- [战斗结算规则](combat_rules.md) — 完整战斗引擎规范
- [卡牌效果规格说明](card_effects_spec.md) — 格式化描述语言 (FDL) 与翻译规则
