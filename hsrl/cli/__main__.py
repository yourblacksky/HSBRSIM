"""HSRL CLI — interactive human-play trajectory recorder for RL training.

Usage:
    python -m hsrl.cli              # Interactive game with default settings
    python -m hsrl.cli --seed 123   # Custom random seed
    python -m hsrl.cli --max-turns 20 --no-anomaly  # Custom settings

During the game, enter commands at the prompt:
    buy 0-6     购买酒馆随从/法术
    sell 0-6    卖出场面随从
    play 0-9    打出手牌
    refresh / r  刷新酒馆 (1铸币)
    upgrade / u  升级酒馆等级
    freeze / f   冻结/解冻酒馆
    end / e      结束回合
    trinket 0-3  选择并购买饰品
    state / s    重新显示当前状态
    help / h     显示帮助
    quit / q     退出游戏
"""
from __future__ import annotations

import random
import shlex
import sys
from typing import Optional

import hsrl.cards.minions.pool as _mp  # noqa
import hsrl.cards.minions.scripts as _ms  # noqa
import hsrl.cards.minions.tokens as _mt  # noqa
import hsrl.cards.heroes.pool as _hp  # noqa
import hsrl.cards.heroes.scripts as _hs  # noqa
import hsrl.cards.spells as _sp  # noqa
import hsrl.cards.trinkets.scripts as _ts  # noqa
import hsrl.cards.rewards.scripts as _rs  # noqa
import hsrl.cards.anomalies.scripts as _as  # noqa

from hsrl.cli.display import display_state
from hsrl.cli.game_runner import GameRunner
from hsrl.cli.recorder import GameRecorder
from hsrl.cli.zhcn import zhcn
from hsrl.core.enums import CardType, GameTag
from hsrl.env.action import (
    END_TURN,
    REFRESH,
    UPGRADE,
    BUY_OFFSET,
    SELL_OFFSET,
    PLAY_OFFSET,
    build_action_mask,
    decode_action,
)

HELP_TEXT = """
命令列表:
  buy <0-6>     购买酒馆随从/法术 (slot 0-6)
  sell <0-6>    卖出场面随从 (slot 0-6)
  play <0-9>    打出手牌中的随从/法术 (slot 0-9)
  refresh / r    刷新酒馆 (1铸币)
  upgrade / u    升级酒馆等级
  freeze / f     冻结/解冻酒馆
  end / e        结束当前回合
  trinket <0-3>  选择并购买饰品
  state / s      重新显示当前游戏状态
  help / h       显示此帮助信息
  quit / q       退出游戏 (不保存)

注意:
  - 一回合最多100次有效操作
  - 英雄技能不可用
  - 输入不合法操作会被忽略 (操作不会生效)
  - 合理操作会被记录用于RL训练
"""


def main():
    import argparse

    parser = argparse.ArgumentParser(description="HSRL 酒馆战棋 CLI — 人工对局轨迹收集")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--max-turns", type=int, default=15, help="最大回合数")
    parser.add_argument("--no-anomaly", action="store_true", help="禁用畸变")
    parser.add_argument("--output", type=str, default="data/trajectories_cli/", help="输出目录")
    args = parser.parse_args()

    if args.no_anomaly:
        # Override by passing a specific known-good seed without anomaly
        pass

    runner = GameRunner(seed=args.seed, max_turns=args.max_turns)
    game, human_idx = runner.create_game()
    player = game.players[human_idx]
    hero_card_id = player.data.id if player.data else ""
    hero_name = zhcn.name(hero_card_id) or hero_card_id
    recorder = GameRecorder(hero_id=hero_card_id, hero_name=hero_name, output_dir=args.output)

    print()
    print("═" * 78)
    print(f"  HSRL 酒馆战棋 CLI — 人工对局轨迹收集")
    print(f"  英雄: {hero_name} ({hero_card_id})")
    print(f"  种子: {args.seed} | 最大回合: {args.max_turns}")
    print("═" * 78)
    print()
    print("  输入 'help' 查看命令列表，'start' 开始游戏")
    print()

    # Initial prompt — wait for user to start
    while True:
        cmd = input(">>> ").strip().lower()
        if cmd in ("start", "s", ""):
            break
        elif cmd in ("help", "h"):
            print(HELP_TEXT)
        elif cmd in ("quit", "q"):
            print("  再见!")
            return
        else:
            print("  输入 'start' 开始游戏, 'help' 查看帮助")

    # ── Main game loop ──
    for turn in range(1, args.max_turns + 1):
        if not player.is_alive:
            print(f"\n  你在第 {turn} 回合被淘汰了!")
            break

        game.turn = turn
        runner.start_turn()

        # Show state
        print()
        print(display_state(game, player))

        action_count = 0
        turn_done = False

        while not turn_done and action_count < 100:
            mask = build_action_mask(game, player)
            legal = set(a for a in range(50) if mask[a])

            if not legal:
                print("  无可用操作，自动结束回合")
                break

            try:
                raw = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  退出游戏")
                return

            if not raw:
                continue

            parts = shlex.split(raw.lower())
            if not parts:
                continue

            cmd = parts[0]
            action_id: Optional[int] = None

            # ── Parse command ──
            if cmd in ("buy", "b") and len(parts) >= 2:
                try:
                    slot = int(parts[1])
                    if 0 <= slot <= 6:
                        action_id = BUY_OFFSET + slot
                except ValueError:
                    pass

            elif cmd in ("sell", "s") and len(parts) >= 2:
                try:
                    slot = int(parts[1])
                    if 0 <= slot <= 6:
                        action_id = SELL_OFFSET + slot
                except ValueError:
                    pass

            elif cmd in ("play", "p") and len(parts) >= 2:
                try:
                    slot = int(parts[1])
                    if 0 <= slot <= 9:
                        action_id = PLAY_OFFSET + slot
                except ValueError:
                    pass

            elif cmd in ("refresh", "r"):
                action_id = REFRESH

            elif cmd in ("upgrade", "u"):
                action_id = UPGRADE

            elif cmd in ("freeze", "f"):
                action_id = 26  # FREEZE

            elif cmd in ("end", "e"):
                action_id = END_TURN

            elif cmd == "trinket" and len(parts) >= 2:
                offers = getattr(player, "_pending_trinket_offers", [])
                if not offers:
                    print("  ⚠ 当前没有饰品可选")
                    continue
                try:
                    choice = int(parts[1])
                    if 0 <= choice < len(offers):
                        cid = offers[choice]
                        cost = _trinket_cost(game, cid)
                        name, _ = zhcn.card(cid)
                        if player.gold < cost:
                            print(f"  ⚠ 金币不足: {name} 需要 {cost} 铸币, 当前 {player.gold}")
                            continue
                        game.buy_trinket(player, choice)
                        print(f"  ✓ 购买了 {name}")
                        print()
                        print(display_state(game, player))
                    else:
                        print(f"  ⚠ 无效选择: {choice} (可选 0-{len(offers)-1})")
                except ValueError:
                    print("  ⚠ trinket <数字> 例如: trinket 0")
                continue

            elif cmd in ("state", "s"):
                print()
                print(display_state(game, player))
                continue

            elif cmd in ("help", "h"):
                print(HELP_TEXT)
                continue

            elif cmd in ("quit", "q"):
                print("  退出游戏 (不保存)")
                return

            else:
                print(f"  ⚠ 未知命令: '{cmd}' (输入 'help' 查看帮助)")
                continue

            # ── Validate and execute action ──
            if action_id is None:
                print(f"  ⚠ 无法解析命令: '{raw}'")
                continue

            if action_id not in legal:
                action_names = {BUY_OFFSET: "买", SELL_OFFSET: "卖", PLAY_OFFSET: "打",
                                REFRESH: "刷新", UPGRADE: "升级", 26: "冻结", END_TURN: "结束"}
                action_name = "?"
                for base, name in action_names.items():
                    if isinstance(base, int):
                        if action_id == base:
                            action_name = name
                            break
                        elif base <= action_id < base + 7 and name in ("买", "卖"):
                            action_name = name
                            break
                        elif base <= action_id < base + 10 and name == "打":
                            action_name = name
                            break
                print(f"  ⚠ 不合法操作: {action_name} (slot {action_id % 7 if 'slot' in dir() else ''})")
                continue

            # Record observation BEFORE executing action
            from hsrl.rl_env.observation.observation_v2 import build_observation_v2
            obs = build_observation_v2(game, player)
            recorder.record_action(turn, obs, action_id)

            # Execute via game engine (triggers Battlecry, spell effects, etc.)
            result = decode_action(action_id, game, player)

            if action_id == REFRESH:
                # Engine already refreshed via _do_refresh → game.refresh_tavern
                runner._auto_play_hand(player)

            action_count += 1

            if action_id == END_TURN:
                turn_done = True
                # Auto-play remaining hand minions before ending
                runner._auto_play_hand(player)
                # Record end-of-turn snapshot
                recorder.record_turn_end(player)
            else:
                # Suggest re-displaying state for complex turns
                pass

        # Handle pending trinket offers before ending turn
        offers = getattr(player, "_pending_trinket_offers", [])
        if offers and not turn_done:
            print("  ⚠ 还有未选择的饰品! 输入 trinket <0-3> 选择, 或 'end' 跳过")
            mask = build_action_mask(game, player)
            legal = set(a for a in range(50) if mask[a])
            while getattr(player, "_pending_trinket_offers", []):
                try:
                    raw = input("  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not raw:
                    continue
                parts = shlex.split(raw.lower())
                if parts[0] == "trinket" and len(parts) >= 2:
                    offers = getattr(player, "_pending_trinket_offers", [])
                    try:
                        choice = int(parts[1])
                        if 0 <= choice < len(offers):
                            cid = offers[choice]
                            cost = _trinket_cost(game, cid)
                            name, _ = zhcn.card(cid)
                            if player.gold >= cost:
                                game.buy_trinket(player, choice)
                                print(f"  ✓ 购买了 {name}")
                            else:
                                print(f"  ⚠ 金币不足")
                    except ValueError:
                        pass
                elif parts[0] in ("end", "e"):
                    break
                elif parts[0] in ("skip",):
                    player._pending_trinket_offers = []
                    print("  ✓ 跳过饰品选择")
                    break
                else:
                    print("  输入 trinket <0-3> 选择, 'end' 结束回合, 'skip' 跳过饰品")

        if not turn_done:
            runner.human_end_turn(human_idx)

        print(f"  ✓ 第 {turn} 回合结束 ({action_count} 次操作)")

        # Auto-play opponents
        runner.auto_play_opponents()

        # Combat
        runner.run_combat()

        # Show combat results
        for p in game.players:
            if not p.is_alive and p.health <= 0:
                # Check if this player just died this turn
                pass

    # ── Game over ──
    print()
    print("═" * 78)
    print(f"  游戏结束 — 第 {game.turn} 回合")
    print(f"  英雄: {hero_name} | 最终血量: {player.health} | 等级: T{player.tavern_tier}")

    # Count living players to determine placement
    # Placement: dead < alive by HP. Count players strictly ahead.
    placement = 1 + sum(
        1 for p in game.players
        if p is not player and (p.is_alive and not player.is_alive
                               or (p.is_alive and player.is_alive and p.health > player.health))
    )
    print(f"  排名: {placement}/8")
    print("═" * 78)

    recorder.save(placement=placement)


def _trinket_cost(game, card_id: str) -> int:
    data = game.card_db.get(card_id) if game.card_db else None
    if data and data.tags:
        return data.tags.get(GameTag.COST, 3)
    return 3


if __name__ == "__main__":
    main()
