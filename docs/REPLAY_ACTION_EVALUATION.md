# P4 Replay 动作级评测契约

## 结论

现有两种轨迹都不能直接当作高手动作数据：

- `hsrl/trajectory/record.py` 只保存每回合最终棋盘，没有招募阶段逐动作记录。
- Advisor JSONL 的 `action_taken` 当前来自模型 `best_action`；collect-only 模式写入固定值 `0`。它不是玩家实际执行动作。
- `TurnTrajectory` 在内存中有逐步 observation/mask，但 `to_dict()` 没有导出这些字段，也没有动作前的完整可恢复引擎状态/RNG 状态。

因此，现有 replay 只能可靠计算最终名次、Top-4 和回合级棋盘变化。下一动作一致率、Top-3、动作 regret 等必须使用下面的 P4 schema 重新采集。

## JSONL schema v1

一个文件包含若干 `decision`，最后是一个 `game_end`：

```json
{"type":"decision","schema_version":1,"game_id":"g1","turn":6,"step":3,"patch_version":"35.6.0.243002","expert_action":{"action":"buy","slot":1,"legacy_id":1},"model_topk":[{"action":"refresh","probability":0.5},{"action":"buy","slot":1,"legacy_id":1,"probability":0.3}],"legal_actions":[1,24,28],"labels":{"expert_board_score_after":20.0,"model_board_score_after":17.0,"avoidable_gold_waste":0,"premature_commit":false,"meaningless_refresh":true,"enabler_opportunity":true,"missed_enabler":true}}
{"type":"game_end","schema_version":1,"game_id":"g1","placement":3}
```

动作一致必须比较完整参数：`action + slot + position + target_slot + order`。只比较 legacy ID 会错误地把不同站位或磁力目标当成相同动作。

CardGameAI 的 `hsb_bridge.py --replay-dir` 已按该版本写入自有模拟对局。
其中实际执行动作位于 `behavior_action`，`state_before/state_after` 分别包含
完整可观察状态、合法 mask、动作模式、剩余动作数和 board-score 分解；LLM transition
还带 `turn_plan` 与 `plan_action_index`。Beam 可作为 teacher 数据，但不会自动被
标记成真人 `expert_action`。后续离线对同一 `state_before` 生成候选和反事实标签
后，才能计算一致率与 regret。

## 指标定义

| 指标 | 定义 | 必需数据 |
|---|---|---|
| 下一动作一致率 | 模型 Top-1 与高手完整动作完全一致 | `expert_action`, `model_topk[0]` |
| 高手动作 Top-3 | 高手完整动作出现在模型前三候选中 | `expert_action`, `model_topk[:3]` |
| board-score regret | `max(0, expert_after - model_after)`；另报有符号差值，避免模型优于高手时被隐藏 | 两动作的反事实执行结果 |
| 金币浪费 | 回合结束时仍可执行有效强化动作的未花金币；不能简单把所有剩余金币算浪费 | `avoidable_gold_waste` |
| 过早定阵容 | 模型声明 commit，但 P3 commit 最小组件/回合/等级门槛未满足 | `premature_commit` |
| 无意义刷新 | 模型付费刷新，未命中目标且相对保留/购买方案无正收益 | `meaningless_refresh`，且 Top-1 是 refresh |
| 错过 enabler | 商店存在当前候选方向 enabler，模型没有购买且不存在更高价值动作 | `enabler_opportunity`, `missed_enabler` |
| 升本后预计掉血 | 选择 upgrade 后，对下一对手的反事实预计伤害 | `upgrade_expected_damage` |
| 站位胜率损失 | `max(0, expert_position_win_prob - model_position_win_prob)` | 同一双方阵容、多 RNG rollouts |
| 最终名次/Top-4 | 实际结算 | `placement` |

## Coverage 规则

每项指标必须同时输出 `n / eligible / coverage`：

- 缺少反事实字段时结果为 `N/A`，不能按 0 处理。
- 无意义刷新只以模型实际首选 refresh 的决策为 eligible。
- 升本掉血只以模型实际首选 upgrade 的决策为 eligible。
- 错过 enabler 只以存在经过 P3 知识库确认的 enabler 机会为 eligible。
- 最终名次只统计有合法 1–8 名结算的游戏。

## 反事实复现要求

要让 board regret、升本掉血和站位胜率可信，每个决策点还应保存：

1. patch/card vocabulary/schema version；
2. 完整玩家、商店、手牌、对手和 pending choice 状态；
3. 合法动作 mask 和动作模式；
4. 游戏 seed，以及决策点 RNG state 或可恢复 snapshot；
5. 高手实际动作事件，而不是模型建议；
6. 模型候选、分数/概率、模型版本和 prompt/策略库版本。

站位评测应在相同双方阵容上使用相同成组种子进行多次战斗，比较模型站位和高手站位。单次战斗结果噪声太大，不能当胜率变化。

## 使用

```bash
python -m hsrl.evaluation.replay_action_eval replay.jsonl --format markdown
python -m hsrl.evaluation.replay_action_eval data/replays/ --format json
python -m hsrl.evaluation.replay_action_eval data/replays/ --policy llm
```

当前实现位于 `hsrl/evaluation/replay_action_eval.py`。
