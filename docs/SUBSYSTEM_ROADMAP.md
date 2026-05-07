# HSRL 子系统路线图

> 本文档规划 HSRL 引擎尚未实现的子系统、剩余需脚本化的卡牌、优先级及依赖关系。
>
> **版本**: 1.0 | **更新日期**: 2026-05-02 | **基线**: 498 tests, 134 脚本化池随从, 50 脚本化英雄技能

---

## ⚠️ Git 备份规则

**每完成一个 Phase 后，必须执行 git 备份：**

```bash
# 在 Phase 完成后:
git add -A
git commit -m "Phase N: <简述>"
# 如需要推送:
# git push origin master
```

备份确保任意阶段出问题时可以回退，不会丢失全部工作。每个 Phase 应是自包含的提交。

---

## 目录

1. [当前状态](#1-当前状态)
2. [缺失引擎系统](#2-缺失引擎系统)
3. [实施路线图 (Phase 10–18)](#3-实施路线图)
4. [DEFERRED 卡牌清单](#4-deferred-卡牌清单)
5. [完整未脚本化卡牌分类](#5-完整未脚本化卡牌分类)
6. [长期规划](#6-长期规划)

---

## 1. 当前状态

### 1.1 已完成子系统（历史 Phase 回顾）

| Phase | 内容 | 测试 |
|-------|------|------|
| 1 | 战斗核心 (攻击/伤害/嘲讽/圣盾/剧毒/复生/风怒/顺劈/亡语) | 230 |
| 2 | 战吼 + 复仇 + Rally + 全局光环 + 鲜血宝石 + 发现 | ~280 |
| 3 | 回合结束 + 回合开始 + 出售时 + 变形 + 吞噬 + Spellcraft | ~330 |
| 4 | 酒馆 Buff + 战斗召唤 + Improve 增强追踪 | ~350 |
| 5 | 三连/金色系统 + 酒馆法术系统 (Spell Buy/Play/Pool) + 法术折扣 | ~380 |
| 6 | 光环翻倍 (Brann/Drakkari) + 临时 Buff + Rally 传播 + 免费刷新 | ~400 |
| 7 | 英雄技能 (主动 43 + 被动 7) + 英雄批量注册 (120 heroes, 122 powers) | ~440 |
| 8 | Tavern Spell Buff Modifier (ImproveTavernSpellBuff) | 478 |
| 9 | 引擎修复 (MINION_BOUGHT/GOLD_GAINED) + On-Sell (7) + End-of-Turn (6) + Baller 累加器 | 498 |

### 1.2 当前统计

| 指标 | 数值 |
|------|------|
| Action 类 | 43+ |
| GameTag 枚举值 | 100+ |
| 脚本化池随从 | 134/241 (56%) |
| 脚本化英雄技能 | 50/164 (30%) |
| CARDS 注册总数 | ~325 |
| 测试总数 | 498 (全部通过) |
| 未脚本化池随从 | 107 |
| 未脚本化英雄技能 | 114 |

---

## 2. 缺失引擎系统

按解锁卡牌数和实现复杂度评估优先级。

| 优先级 | 系统 | 解锁卡牌 | 复杂度 | 说明 |
|--------|------|---------|--------|------|
| **P0** | 未广播事件修复 (3 行) | ~3 | 1 | `END_OF_COMBAT`, `TURN_BEGIN`, `TURN_END` |
| **P0** | 简单英雄技能批量实现 | ~27 | 1 | 零新引擎，纯 Buff/Get/Race 类 |
| **P1** | Start-of-Turn 简单卡牌 | ~5 | 1 | SOT tag + `_trigger_start_of_turn()` 已就绪 |
| **P1** | 回合结束剩余卡牌 (简单) | ~5 | 2 | `END_OF_TURN` tag 已就绪，部分需小引擎 |
| **P1** | Magnetic 磁力系统 | 6 | 3 | 附加 + 属性合并逻辑 |
| **P2** | Consume Tavern 吞噬酒馆 | 4 | 3 | 从 `player.tavern` 选择目标并吞噬 |
| **P2** | Bounty 悬赏系统 | 5 | 4 | 全新子系统：悬赏生成/选择/奖励 |
| **P2** | Spell 系统完善 (SpellCraft + 法术触发) | ~10 | 3 | SC 随从 + 施放法术后触发 |
| **P3** | Per-Card-ID 追踪 (回合/打出计数) | ~5 | 2 | Patient Scout, Brazen Buccaneer 等 |
| **P3** | Last Spell 追踪 | ~3 | 2 | Cataclysmic Harbinger 等 |
| **P3** | Reborn Blood Gem 变体 | 1 | 2 | Redtusk Thornraiser |
| **P3** | Avenge→Improve EOT 双层 | 1 | 3 | Skeletal Strafer |
| **P4** | Silence 沉默系统 | ~3 | 3 | 移除关键词 + buff |
| **P4** | Trinket 饰品系统 | 20+ | 5 | Season 13 完整机制 (第 6/9 回合选购) |
| **P4** | Duos 双打模式 | 29 | 5 | 全部 BGDUO 卡牌 + 双打规则 |

### 2.1 未广播的事件 (3 行修复)

`events.py` 中定义但从未 broadcast:

| 事件 | 定义位置 | 应广播位置 | 影响 |
|------|---------|-----------|------|
| `END_OF_COMBAT` | `events.py:84` | `game.py` `_end_combat_phase()` | "At end of combat" 效果 |
| `TURN_BEGIN` | `events.py:94` | `game.py` `start_turn()` | "At the start of each turn" 效果 |
| `TURN_END` | `events.py:95` | `game.py` `end_turn()` | "At the end of each turn" 效果 |

---

## 3. 实施路线图

### Phase 10 — 事件修复 + Start-of-Turn 批量脚本 (预计 ~5 新测试)

**引擎**: 广播 `END_OF_COMBAT`, `TURN_BEGIN`, `TURN_END` (3 行)

**池随从** — Start-of-Turn 简单类 (~5 张):
- 使用 `START_OF_TURN` tag + `_trigger_start_of_turn()` 引擎 (已就绪)
- 效果包含: Buff 自身、获得金币、触发战斗召唤等

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 10: 事件修复 + Start-of-Turn 批量脚本"
```

---

### Phase 11 — 批量简单英雄技能 (预计 ~30 新测试)

**引擎**: 零新引擎 (复用 Buff/GainGold/GetRandomMinion/Improve 等已有 Action)

**英雄技能** (~27 个):
- Patched Up, Avalanche, Banshee's Blessing, Battle Brand, Broodmother, Clairvoyance, Demon Hunter Training, Dream Portal, Embrace the Elements, Expedition Plans, Friendly Wager, Frostwolf Fervor, Growing Collection, Heroic Inspiration, Honorable Warband, Menagerist, Murloc King, Natural Balance, Nefarious Fire, Prestidigitation, Sign a New Artist, Skilled Bartender, Snicker-snack, Sprout It Out!, Stir the Pot, Stormpike Strength, Swap Lock & Shop It, Twice as Nice

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 11: 批量简单英雄技能"
```

---

### Phase 12 — Magnetic 磁力引擎 (预计 ~8 新测试)

**引擎**: 
- 新建 `AttachMagnetic` Action
- 磁力随从可从手牌附加到友方 Mech 随从上
- 附加时合并属性 (ATK + Health) 和关键词 (圣盾/嘲讽/复生/风怒)
- 添加 `EXAMPLE_MAGNETIC_ATTACH` 标准示例

**解锁卡牌 (6)**:
| ID | 名称 | 效果 |
|------|------|------|
| BG31_171 | Moonsteel Juggernaut | 战斗开始时: 召唤磁力衍生物 |
| BGS_030 | King Bagurgle | (已实现战吼，Magnetic 仅标签) |
| — | Accord-o-Tron, Annoy-o-Module, Technical Element, Enchanted Sentinel, Prosthetic Hand, Lullabot | 磁力附加 |

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 12: Magnetic 磁力引擎"
```

---

### Phase 13 — Consume Tavern 引擎 (预计 ~8 新测试)

**引擎**:
- 新建 `ConsumeTavernMinion` Action
- 从 `player.tavern` 中随机选择目标并吞噬
- 被吞噬随从的属性转移至吞噬者
- 添加 `EXAMPLE_CONSUME_TAVERN` 标准示例

**解锁卡牌 (4)**:
| ID | 名称 | 效果 |
|------|------|------|
| BG34_500 | Flaming Enforcer | 回合结束: 吞噬酒馆随从, +2/+2 |
| BG21_005 | Famished Felbat | 回合结束: 吞噬酒馆随从, 获得属性 |
| BG35_155 | Batty Terrorguard | 吞噬酒馆随从 |
| BG35_155 | Consummate Conqueror | Avenge(4): 吞噬酒馆随从 |

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 13: Consume Tavern 引擎"
```

---

### Phase 14 — Bounty 悬赏系统 (预计 ~12 新测试)

**引擎**:
- 新建 `GenerateBounty` / `ClaimBounty` Action
- 悬赏法术 (BGS_078 Bounty Spells) — 5 种标准悬赏
- 悬赏生成: 随机获得一个悬赏任务，完成后获得奖励
- 添加 `EXAMPLE_BOUNTY` 标准示例

**解锁卡牌 (5+)**:
| ID | 名称 | 效果 |
|------|------|------|
| BG33_820 | Lost City Looter | Start of Combat: 获得随机悬赏 |
| BGS_078 | Monstrous Macaw | (已部分实现) |
| — | Shipwrecked Rascal | Deathrattle: 获得悬赏 |
| — | Bigwig Bandit | Rally: 获得悬赏 |
| — | Sky Admiral Rogers | 悬赏联动 |

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 14: Bounty 悬赏系统"
```

---

### Phase 15 — Spell 系统完善 (预计 ~15 新测试)

**引擎**:
- 完善 Spellcraft 触发 (已有基础)
- "每次施放法术后" 触发 (TAVERN_SPELL_CAST 事件已实现)
- 法术触发后 Buff/Get/Improve 效果

**解锁卡牌 (~10)**:
- SpellCraft 随从 (5): Surf n' Surf, Lava Lurker, Deep Blue Crooner, Zesty Shaker, Sea Witch Zar'jira
- 法术施放后 (5): Pufferquil, Nalaa the Redeemer, Living Azerite, Charging Czarina, Tidemistress Athissa
- 法术触发 (1): Cataclysmic Harbinger

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 15: Spell 系统完善"
```

---

### Phase 16 — Per-Card 追踪 + 剩余 End-of-Turn (预计 ~12 新测试)

**引擎**:
- Per-card-ID 玩家级计数器 (回合追踪/打出计数)
- Last Spell 追踪

**解锁卡牌 (~7)**:
| ID | 名称 | 效果 | 依赖 |
|------|------|------|------|
| BG24_715 | Patient Scout | On-Sell: 获得随机 minion, N 随回合递增 | 回合追踪 |
| BG35_701 | Brazen Buccaneer | EOT: +1/+1 每本回合打出的牌 | 打出计数 |
| BG35_123 | Cataclysmic Harbinger | EOT: 施放上次法术的复制 | Last Spell 追踪 |
| BG35_334 | Skeletal Strafer | Avenge→Improve EOT | 双层计数器 |
| BG35_433 | Redtusk Thornraiser | EOT: 复生随从获得血宝石 | Reborn BG 变体 |
| BG26_147 | Legion Overseer | SOT: Buff | Start-of-Turn |

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 16: Per-Card 追踪 + 剩余 EOT"
```

---

### Phase 17 — Silence 沉默系统 (预计 ~8 新测试)

**引擎**:
- 新建 `Silence` Action
- 移除所有关键词和 Buff (保留基础属性)
- 添加 `EXAMPLE_SILENCE` 标准示例

**解锁卡牌**:
- 约 3 张使用沉默效果的卡牌

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 17: Silence 沉默系统"
```

---

### Phase 18 — Trinket 饰品系统 (预计 ~25 新测试)

**引擎**:
- 新建 `hsrl/core/trinkets.py`
- Trinket 实体类 (继承 BaseEntity)
- 第 6 回合 Lesser Trinket / 第 9 回合 Greater Trinket 选择阶段
- Trinket 效果在 Start of Combat / End of Turn 等时机触发
- 添加 `EXAMPLE_TRINKET` 标准示例

**解锁卡牌**:
- ~20 张直接依赖 Trinket 系统的卡牌

**验证**: `python -m pytest hsrl/tests/ -v`

**备份**:
```bash
git add -A
git commit -m "Phase 18: Trinket 饰品系统"
```

---

## 4. DEFERRED 卡牌清单

以下卡牌被标记为 DEFERRED（需特定引擎支持后才能实现）：

| 卡牌 ID | 名称 | 阻塞 | 预计 Phase |
|---------|------|------|-----------|
| BG24_715 | Patient Scout | 回合追踪 | 16 |
| BG35_433 | Redtusk Thornraiser | Reborn Blood Gem 变体 | 16 |
| BG35_334 | Skeletal Strafer | Avenge→Improve EOT 双层 | 16 |
| BG34_500 | Flaming Enforcer | Consume Tavern | 13 |
| BG21_005 | Famished Felbat | Consume Tavern | 13 |
| BG35_123 | Cataclysmic Harbinger | Last Spell 追踪 | 16 |
| BG35_701 | Brazen Buccaneer | 打出计数 | 16 |
| BG33_820 | Lost City Looter | Bounty 系统 | 14 |
| BG31_171 | Moonsteel Juggernaut | Magnetic 衍生物 | 12 |
| 全部 Duos 卡牌 (29) | — | 双打模式引擎 | P4 |

---

## 5. 完整未脚本化卡牌分类

### 5.1 池随从 (107 张未脚本化)

| 类别 | 数量 | Phase |
|------|------|-------|
| 无关键词 (纯身材/特殊触发) | 36 | 17-18 |
| 圣盾 | 13 | 低优先 |
| 回合结束 (剩余) | 9 | 13, 16 |
| 打出后触发 (after_play) | 9 | 16 |
| 嘲讽 | 8 | 低优先 |
| 亡语 (简单) | 6 | 可批量 |
| 磁力 | 6 | 12 |
| 法术施放后触发 | 6 | 15 |
| 复生 | 5 | 低优先 |
| Spellcraft | 5 | 15 |
| 吞噬酒馆 | 4 | 13 |
| Rally | 4 | 15-16 |
| 关键词保留 (Tarecgosa 类) | 4 | 16 |
| 金币消耗触发 | 3 | 15 |
| 风怒 | 3 | 低优先 |
| 复仇 | 2 | 16 |
| 相邻触发 | 2 | 15 |
| 友方触发 | 2 | 15 |
| 手中效果 | 2 | 16 |
| 生命值消耗 | 2 | 待评估 |
| 烈毒 | 2 | 低优先 |
| 其他 | 8 | 待评估 |

### 5.2 英雄技能 (114 个未脚本化)

| 类别 | 数量 | Phase |
|------|------|-------|
| 简单 Buff/Get/Race | ~27 | 11 |
| 复杂/独立引擎 | ~22 | 待评估 |
| 被动触发 | ~50 | 分批 |
| Duos 专属 | ~5 | P4 |

---

## 6. 长期规划

### 6.1 版本路线

| 版本 | Phase 范围 | 预计测试 |
|------|-----------|---------|
| **v0.7** | Phase 10-11 (事件修复 + SOT + 简单英雄技能) | ~530 |
| **v0.8** | Phase 12-13 (Magnetic + Consume Tavern) | ~550 |
| **v0.9** | Phase 14-15 (Bounty + Spell 完善) | ~580 |
| **v1.0** | Phase 16-18 (追踪 + Silence + Trinket) | ~630 |

### 6.2 RL 集成准备

引擎充分成熟后的工作：

1. **环境包装**: 实现 `gymnasium.Env` 接口
2. **观察空间**: board 状态、手牌、金币、血量 的 `Dict`/`Box` 表示
3. **动作空间**: 招募阶段所有合法动作的离散/复合空间
4. **奖励函数**: 排名 → 奖励映射
5. **向量化**: 批量并行运行多场游戏
6. **日志系统**: 记录每步状态用于离线训练

---

*文档版本：1.0 | 最后更新：2026-05-02 | 基线：498 tests*
