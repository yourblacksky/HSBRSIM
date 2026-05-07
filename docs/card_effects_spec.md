# 卡牌效果规格说明

本文档定义酒馆战棋卡牌效果的**格式化描述语言 (Formal Description Language)**，用于将中文卡牌描述精确翻译为 `card_effects.json` 中的效果定义。每条卡牌的效果定义必须可追溯到卡牌原文，消除自动解析产生的歧义。

## 1. 格式化描述语言 (FDL)

### 1.1 语法

```
[触发时机] → 效果类型(目标选择器, 参数...)
```

多效果卡牌用 `;` 分隔：

```
[触发时机] → 效果1(目标, 参数); 效果2(目标, 参数)
```

### 1.2 触发时机 (Trigger)

| FDL 标记 | Trigger 值 | 中文关键词 | 触发点 |
|----------|-----------|-----------|--------|
| `[战吼]` | `battlecry` | 战吼 | 随从进场后 |
| `[亡语]` | `deathrattle` | 亡语 | 战斗中死亡时 |
| `[回合结束]` | `end_of_turn` | 在你的回合结束时 | 推进到下一回合前 |
| `[战斗开始]` | `start_of_combat` | 战斗开始时 | 战斗 clone 前 |
| `[进击]` | `rally` | 进击 | 随从攻击时，伤害结算前触发 |
| `[复仇(N)]` | `avenge` | 复仇(N) | N 个友方死亡后 |
| `[光环]` | `aura` | (持续效果) | 战斗中常驻 |
| `[法术]` | `spell` | 酒馆法术 | 法术打出时 |

### 1.3 效果类型 (Effect Type)

| FDL 函数 | EffectType | 描述 |
|----------|-----------|------|
| `stat_buff` | `stat_buff` | 改变攻击力/生命值 |
| `summon` | `summon` | 召唤 token 随从 |
| `gain_keyword` | `gain_keyword` | 获得关键词 |
| `deal_damage` | `deal_damage` | 造成伤害 |
| `gain_gold` | `gain_gold` | 获得金币 |
| `add_to_hand` | `add_to_hand` | 将卡牌加入手牌 |
| `tavern_buff` | `tavern_buff` | 酒馆中随从获得属性 |
| `health` | `health` | 治疗/恢复生命值 |
| `discover` | `discover` | 发现机制 |
| `double_stats` | `double_stats` | 属性值翻倍 |
| `set_stats` | `set_stats` | 设为固定属性值 |
| `gain_blood_gem` | `gain_blood_gem` | 获得鲜血宝石 |
| `add_random_card` | `add_random_card` | 随机获取卡牌 (可过滤) |
| `make_golden` | `make_golden` | 变为金色 (当前属性三倍) |
| `eat_tavern` | `eat_tavern` | 吞食酒馆随从并吸收属性 |
| `cast_specific_spell` | `cast_specific_spell` | 施放指定名称的酒馆法术 |
| `copy_minion` | `copy_minion` | 深度复制随从 (self/left/opponent → board/hand/transform) |
| `hero_damage` | `hero_damage` | 对英雄造成伤害 |
| `grant_effect` | `grant_effect` | 给其他随从附加亡语/战吼效果 |
| `combat_summon_from_hand` | `combat_summon_from_hand` | 战斗中从手牌召唤最高攻击力随从 |
| `trigger_chain` | `trigger_chain` | 重新触发相邻/全体友方指定类型效果 |
| `copy_last_spell` | `copy_last_spell` | 获取上一个施放法术的复制 |
| `summon_random_pirates` | `summon_random_pirates` | 召唤 4 个随机海盗 |
| `resurrect_dead_mechs` | `resurrect_dead_mechs` | 复活本场战斗最先死亡的机械 |
| `summon_random_deathrattle` | `summon_random_deathrattle` | 召唤随机亡语随从 |
| `add_health_cost_spells` | `add_health_cost_spells` | 将消耗生命值的法术加入手牌 |
| `magnetic_attach` | `magnetic_attach` | 为目标随从磁力吸附随机磁力机械 (+stats/+keywords) |
| `adapt` | `adapt` | 随机进化 (DS/Taunt/Reborn/Windfury/Poisonous/+3atk/+3hp) |
| `random_bonus_self` | `random_bonus_self` | 按随从类型数从奖励池随机抽取加成 |
| `change_tavern_type` | `change_tavern_type` | 将酒馆随从类型改为场上多数种族 |
| `summon_random_minion` | `summon_random_minion` | 按稀有度/等级/种族从池中召唤随机随从 |

### 1.4 目标选择器 (Target)

| FDL 参数 | Target 值 | 含义 |
|----------|----------|------|
| `self` | `self` | 自身 |
| `random_friendly` | `friendly_random` | 随机友方 |
| `all_friendly` | `friendly_all` | 全体友方 |
| `other_friendly` | `friendly_other` | 除自身外的友方 |
| `adjacent_friendly` | `friendly_adjacent` | 相邻友方 |
| `friendly_type(种族)` | `friendly_type` | 指定种族的友方 |
| `leftmost` | `friendly_left` | 最左侧友方 |
| `rightmost` | `friendly_right` | 最右侧友方 |
| `one_per_type` | `friendly_one_per_type` | 每种随从类型各一个 |
| `random_enemy` | `enemy_random` | 随机敌方 |
| `all_enemy` | `enemy_all` | 全体敌方 |
| `tavern` | `tavern` | 酒馆中的随从 |
| `hero` | `hero` | 英雄（玩家） |

### 1.5 完整效果参数

```
stat_buff(target, atk=X, hp=Y, count=N)            # count 仅对 random/type 有效
stat_buff(target, value_from=source_attack)         # 动态值: 等同于来源攻击力
stat_buff(target, value_from=hand_highest_attack)   # 动态值: 手牌最高攻击力
summon(target, dbf_id=X, count=N)                   # 召唤 token
gain_keyword(target, keyword=X)                  # 关键词: taunt/ds/reborn/poisonous/windfury/cleave
deal_damage(target, dmg=X, count=N)              # 伤害 (可用 value_from=source_attack)
gain_gold(target=hero, amount=X)                 # 金币
add_to_hand(target=hero, dbf_id=X)               # 加到手牌
tavern_buff(target=tavern, atk=X, hp=Y, count=N) # 酒馆 buff
health(target, hp=X)                             # 治疗
discover()                                       # 发现 (暂不建模)
double_stats(target)                             # 属性值翻倍
set_stats(target, atk=X, hp=Y)                   # 设为固定属性值
gain_blood_gem(target=hero, count=N)             # 获得血宝石到手中
add_random_card(target=hero, tier=X, race=Y, keyword=Z)  # 随机获取卡牌
make_golden(target)                              # 变为金色 (三倍当前属性)
```

## 2. 中文 → FDL 翻译规则

### 2.1 属性值解析

| 中文模式 | FDL | 示例 |
|---------|-----|------|
| `+X/+Y` | `atk=X, hp=Y` | `+2/+2` → `atk=2, hp=2` |
| `获得+X攻击力` | `atk=X, hp=0` | `获得+3攻击力` → `atk=3, hp=0` |
| `获得+Y生命值` | `atk=0, hp=Y` | `获得+2生命值` → `atk=0, hp=2` |
| `属性值翻倍` | `use double_stats` | Phase 3 已实现 |
| `变为金色` | `use make_golden` | Phase 3 已实现 |
| `设为X/Y` | `use set_stats` | Phase 3 已实现 |
| `等同于来源攻击力` | `value_from=source_attack` | Phase 3 动态值 |
| `等同于你的酒馆等级` | `atk=tier, hp=tier` | — |

### 2.2 目标解析

| 中文模式 | FDL 目标 | 额外参数 |
|---------|---------|---------|
| `使一个友方随从` | `random_friendly` | `count=1` |
| `使一个随从` (不限敌我) | `random_friendly` (默认友方) | — |
| `使你的随从` / `使所有友方` | `all_friendly` | — |
| `使另一个友方随从` | `other_friendly` | — |
| `使一个(种族)` | `friendly_type(种族)` | `race=X` |
| `对相邻随从` | `adjacent_friendly` | — |
| `随机对一个敌方随从` | `random_enemy` | `count=1` |
| `对所有敌人` | `all_enemy` | — |
| `使酒馆中的随从` | `tavern` | — |

### 2.3 数量/次数

- `使N个...` → `count=N, random=True`
- `使所有...` → `count=99` 或 `random=False`
- `召唤一个X/Y的...` → `count=1`
- `召唤N个...` → `count=N`

### 2.4 特殊关键词

| 中文 | keyword 值 |
|------|-----------|
| 嘲讽 | `taunt` |
| 圣盾 | `divine_shield` |
| 复生 | `reborn` |
| 风怒 | `windfury` |
| 烈毒/剧毒 | `poisonous` |
| 顺劈 | `cleave` |

## 3. 翻译示例

### 示例 1: 标准战吼

```
原文: <b>战吼：</b>使一个友方随从获得+2/+2。
FDL:  [战吼] → stat_buff(random_friendly, atk=2, hp=2, count=1)
JSON: {"type":"stat_buff","trigger":"battlecry","target":"friendly_random","attack":2,"health":2,"count":1}
```

### 示例 2: 亡语召唤

```
原文: <b>亡语：</b>召唤一个2/2的机械袋鼠。
FDL:  [亡语] → summon(self, dbf_id=57336)
JSON: {"type":"summon","trigger":"deathrattle","target":"self","dbf_id":57336,"count":1}
```

### 示例 3: 回合结束全体 buff

```
原文: 在你的回合结束时，使你的其他恶魔获得+1/+1。
FDL:  [回合结束] → stat_buff(friendly_type(Demon), atk=1, hp=1, count=99)
JSON: {"type":"stat_buff","trigger":"end_of_turn","target":"friendly_type","race":"Demon","attack":1,"health":1,"count":99}
```

### 示例 4: 复仇召唤

```
原文: <b>复仇（3）：</b>召唤一个5/5的恶魔。
FDL:  [复仇(3)] → summon(self, dbf_id=XXXXX)
JSON: {"type":"summon","trigger":"avenge","target":"self","dbf_id":XXXXX,"avenge_count":3}
```

### 示例 5: 战吼给金币

```
原文: <b>战吼：</b>获得1枚铸币。
FDL:  [战吼] → gain_gold(hero, amount=1)
JSON: {"type":"gain_gold","trigger":"battlecry","target":"hero","gold":1}
```

### 示例 6: 双效果卡牌

```
原文: <b>战吼：</b>使一个友方野兽获得+2/+2，并使其获得<b>嘲讽</b>。
FDL:  [战吼] → stat_buff(friendly_type(Beast), atk=2, hp=2, count=1); gain_keyword(same_target, keyword=taunt)
JSON: {"effects":[{"type":"stat_buff","trigger":"battlecry","target":"friendly_type","race":"Beast","attack":2,"health":2,"count":1}]}
注: 第二个效果 (获得嘲讽) 需要 target 指向相同目标，当前系统不支持，仅实现 stat_buff 部分。
```

### 示例 7: 属性值翻倍 (Phase 3)

```
原文: <b>战斗开始时：</b>使本随从的属性值翻倍。
FDL:  [战斗开始] → double_stats(self)
JSON: {"type":"double_stats","trigger":"start_of_combat","target":"self"}
```

### 示例 8: 动态值 — 等于攻击力 (Phase 3)

```
原文: <b>亡语：</b>对一个敌方随从造成等同于本随从攻击力的伤害。
FDL:  [亡语] → deal_damage(random_enemy, value_from=source_attack)
JSON: {"type":"deal_damage","trigger":"deathrattle","target":"enemy_random","value_from":"source_attack"}
```

### 示例 9: 鲜血宝石 (Phase 3)

```
原文: <b>在你的回合结束时：</b>获得2张鲜血宝石。
FDL:  [回合结束] → gain_blood_gem(hero, count=2)
JSON: {"type":"gain_blood_gem","trigger":"end_of_turn","target":"hero","blood_gem_count":2}
```

### 示例 10: 随机获取卡牌 (Phase 3)

```
原文: <b>战吼：</b>随机将一张鱼人牌置入你的手牌。
FDL:  [战吼] → add_random_card(hero, race=Murloc)
JSON: {"type":"add_random_card","trigger":"battlecry","target":"hero","card_race":"Murloc"}
```

## 4. 当前系统状态

**状态 (2026-04-30)**: 605 条效果定义，100% 精确实现，0 条近似，0 条未实现。32 种效果类型全覆盖。

### Phase 5 新增效果类型

| 卡牌效果类型 | 实现方式 | Phase |
|------------|---------|-------|
| "磁力吸附" | `magnetic_attach` 效果类型 (all/amplifier 池, 可选加入手牌) | P5 |
| "进化" | `adapt` 效果类型 (DS/Taunt/Reborn/Windfury/Poisonous/+3atk/+3hp 随机) | P5 |
| "按类型随机加成" | `random_bonus_self` 效果类型 (bonus_options 池, 按种族数采样) | P5 |
| "酒馆类型变更" | `change_tavern_type` 效果类型 (场上多数种族 → tavern slots) | P5 |
| "按稀有度召唤" | `summon_random_minion` 效果类型 (rarity/tier/race 过滤) | P5 |
| "间隔触发" | `every_n_turns` 字段 (每 N 回合触发一次) | P5 |
| "金色条件" | `requires_golden_count` 字段 (场上金色随从数 ≥ N 才触发) | P5 |
| "伤害翻倍" | `damage_multiplier` 战斗随从字段 (target_damage_multiplier) | P5 |
| "回合持有缩放" | `counter_name` on_sell + advance_turn 增量 (turns_held) | P5 |
| "金色状态区分" | `golden_attack`/`golden_health` 字段 (金色随从用不同数值) | P5 |
| "摧毁后复制" | `destroy_before_copy` 字段 (copy_minion 扩展) | P5 |
| "双重目的地" | `copy_destination: "board_and_hand"` (同时召唤+加入手牌) | P5 |
| "重复触发" | `repeat` 字段 (效果应用 N 次) | P5 |

### 未实现 (架构排除)

| 卡牌效果类型 | 示例 | 说明 |
|------------|------|------|
| 进化 | 温顺的巨壳龙 | 需要进化选择池 (1 张卡, 排除) |
| 酒馆类型操控 | 大德鲁伊哈缪尔 | 需要酒馆刷新操控 (排除) |
| 双打机制 | 转运反应堆/堕落者信使 | 双打系统 (排除) |
| 出售触发 | 时空扭曲侦查员 | 需要 on_sell 触发 (排除) |
| 完整磁力附着 | 摇晃的修理机器人等 | 需要用磁力池 + 自动附着系统 (当前用 stat_buff 近似) |
| "每当你使用一张X牌" | 愤怒编织者 | 需要 on_card_played 触发 |
| 塑造法术 | 多种纳迦 | 需要 spellcraft 系统 |
| 变形/复制 (复杂) | 大巫妖克尔苏加德 | 需要消灭+精确重建 (当前用简化版) |

## 5. 效果录入规范

新增或修改卡牌效果时，必须遵循以下流程：

1. **读取原文**: 从 `cache/cards.json` 查询卡牌的 `text` 字段
2. **编写 FDL**: 按本文档第2节的规则将中文翻译为 FDL
3. **生成 JSON**: 按第3节的映射生成 JSON 效果定义
4. **交叉验证**: 确保 JSON 参数与 FDL 参数一致

### 5.1 不可建模的卡牌处理

如果卡牌效果超出当前系统能力：
- 在 `card_effects.json` 中添加带有 `"_note"` 注释字段的条目，诚实标注 `not_implemented: <原因>`
- **禁止使用近似数值**：不再使用虚假 stat 值伪装未实现的效果
- 在本文档第4节的限制表中记录
- 效果验证: `python scripts/demo_render.py --test-effects`
