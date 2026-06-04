"""Curses application — interactive Battlegrounds with live-updating UI."""
from __future__ import annotations

import curses
import random
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

from hsrl.cli.game_runner import GameRunner
from hsrl.cli.recorder import GameRecorder
from hsrl.cli.zhcn import zhcn
from hsrl.core.enums import GameTag
from hsrl.cui.panels import (
    render_all, render_cmdline,
    GOLD, KEYWORD, SPELL, ERROR, INFO, HEADER, DIM,
)
from hsrl.env.action import (
    END_TURN, REFRESH, UPGRADE, BUY_OFFSET, SELL_OFFSET, PLAY_OFFSET,
    build_action_mask, decode_action,
)
from hsrl.rl_env.observation.observation_v2 import build_observation_v2


class CursesApp:
    def __init__(self, seed: int = 42, max_turns: int = 15, output_dir: str = "data/trajectories_cli/"):
        self.seed = seed
        self.max_turns = max_turns
        self.output_dir = output_dir
        self.runner = GameRunner(seed=seed, max_turns=max_turns)
        self.log: list[str] = []
        self.input_buf = ""
        self.running = True
        self.quit_confirm = False

    def run(self, stdscr):
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        self._init_colors()

        # Create game
        game, human_idx = self.runner.create_game()
        player = game.players[human_idx]
        hero_id = player.data.id if player.data else ""
        hero_name = zhcn.name(hero_id) or hero_id
        recorder = GameRecorder(hero_id=hero_id, hero_name=hero_name, output_dir=self.output_dir)

        # Disable auto-resolve so we can show discover UI to the user
        game._auto_resolve_choices = False

        self._log(f"英雄: {hero_name} | 种子: {self.seed}", INFO)

        # Main game loop
        for turn in range(1, self.max_turns + 1):
            if not player.is_alive:
                self._log(f"你在第 {turn} 回合被淘汰!", ERROR)
                break

            game.turn = turn
            game._auto_resolve_choices = False  # human turn: manual discover UI
            self.runner.start_turn()

            action_count = 0
            turn_done = False
            self._log(f"── 第 {turn} 回合开始 ──", INFO)

            while not turn_done and action_count < 100:
                mask = build_action_mask(game, player)
                legal = set(a for a in range(50) if mask[a])

                if not legal:
                    self._log("无可用操作，自动结束回合", ERROR)
                    break

                # Redraw
                stdscr.clear()
                h, w = stdscr.getmaxyx()
                y = render_all(stdscr, game, player, 0, w, self.log)

                # Command area
                shortcuts = "b<0-6> s<0-6> p<0-9> r=刷新 u=升级 f=冻结 e=结束 ?=帮助 q=退出"
                cmd_y = max(y + 1, h - 2)
                render_cmdline(stdscr, cmd_y, w, self.input_buf, shortcuts)
                stdscr.refresh()

                # Get input
                self.input_buf = ""
                curses.curs_set(1)
                curses.echo()
                try:
                    stdscr.move(cmd_y, 2)
                    self.input_buf = stdscr.getstr(cmd_y, 2, 40).decode("utf-8", "ignore").strip()
                except Exception:
                    self.input_buf = ""
                curses.noecho()
                curses.curs_set(0)

                if not self.input_buf:
                    continue

                # Parse single-key shortcuts
                cmd, action_id = self._parse_input(self.input_buf, legal)

                if cmd == "quit":
                    return
                elif cmd == "help":
                    self._show_help(stdscr)
                    continue
                elif cmd == "trinket":
                    offers = getattr(player, "_pending_trinket_offers", [])
                    choice = action_id  # action_id is used as trinket choice here
                    if not offers:
                        self._log("⚠ 当前没有饰品可选", ERROR)
                    elif 0 <= choice < len(offers):
                        cid = offers[choice]
                        cost = self._trinket_cost(game, cid)
                        name, _ = zhcn.card(cid)
                        if player.gold >= cost:
                            game.buy_trinket(player, choice)
                            self._log(f"✓ 购买饰品: {name}", INFO)
                        else:
                            self._log(f"⚠ 金币不足: {name} ${cost}", ERROR)
                    continue
                elif cmd == "unknown":
                    self._log(f"⚠ 未知命令: '{self.input_buf}'", ERROR)
                    continue
                elif action_id is None:
                    continue

                # Validate
                if action_id not in legal:
                    self._log(f"⚠ 不合法操作", ERROR)
                    continue

                # Record + Execute
                obs = build_observation_v2(game, player)
                recorder.record_action(turn, obs, action_id)

                result = decode_action(action_id, game, player)
                action_count += 1

                # Handle pending choice for human player
                choice = game._pending_choice
                if choice is not None and choice.player is player:
                    choice = game._pending_choice
                    stdscr.clear()
                    h, w = stdscr.getmaxyx()
                    # Show game state + discover options
                    y = render_all(stdscr, game, player, 0, w, self.log)
                    _addstr(stdscr, y, 0, f"── 发现: {choice.choice_type} {'─' * (w - 10)}"[:w - 1],
                            curses.color_pair(HEADER))
                    y += 1
                    for i, (cid, name) in enumerate(choice.options):
                        cn_name = zhcn.name(cid) or name
                        cn_text = zhcn.text(cid)
                        _addstr(stdscr, y, 0, f" [{i}] {cn_name}", curses.color_pair(SPELL))
                        y += 1
                        if cn_text:
                            cleaned = cn_text.replace('<b>','').replace('</b>','').replace('\n',' ')[:w-5]
                            _addstr(stdscr, y, 0, f"     {cleaned}"[:w - 1], curses.color_pair(DIM))
                            y += 1
                    _addstr(stdscr, y + 1, 0, " 选择 0-2: ", 0)
                    stdscr.refresh()

                    # Get choice
                    curses.echo()
                    curses.curs_set(1)
                    try:
                        ch = stdscr.getstr(y + 1, 12, 2).decode("utf-8", "ignore").strip()
                        idx = int(ch) if ch.isdigit() and 0 <= int(ch) < len(choice.options) else 0
                    except (ValueError, TypeError):
                        idx = 0
                    curses.noecho()
                    curses.curs_set(0)
                    game.resolve_pending_choice(idx)
                    resolved_name = zhcn.name(choice.options[idx][0]) or choice.options[idx][1]
                    self._log(f"  发现: 选择了 {resolved_name}", INFO)

                action_name = self._action_name(action_id)
                self._log(f"  {action_name}", INFO)

                if action_id == REFRESH:
                    self.runner._auto_play_hand(player)
                elif action_id == END_TURN:
                    turn_done = True
                    self.runner._auto_play_hand(player)
                    recorder.record_turn_end(player)
                elif action_id == UPGRADE:
                    self._log(f"  → 升级到 T{player.tavern_tier}", INFO)

            if not turn_done:
                self.runner.human_end_turn(human_idx)

            self._log(f"✓ 第 {turn} 回合结束 ({action_count} 次操作)", INFO)

            # Auto-play opponents + combat
            self.runner.auto_play_opponents()
            self.runner.run_combat()

            # Show combat result
            hp = player.health
            self._log(f"  战斗后血量: {hp}", INFO if hp > 15 else ERROR)

        # Game over
        placement = 1 + sum(1 for p in game.players if p is not player and p.is_alive)
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        _addstr(stdscr, h // 2, (w - 40) // 2, f"═══ 游戏结束 ═══", HEADER)
        _addstr(stdscr, h // 2 + 1, (w - 40) // 2,
                f"  英雄: {hero_name} | 排名: {placement}/8 | 回合: {game.turn}")
        _addstr(stdscr, h // 2 + 3, (w - 40) // 2, "  按任意键退出...", DIM)
        stdscr.refresh()
        stdscr.getch()

        recorder.save(placement=placement)

    def _parse_input(self, raw: str, legal: set) -> tuple[str, Optional[int]]:
        """Parse command string. Returns (command_type, action_id_or_choice)."""
        s = raw.strip().lower()
        parts = s.split()

        # Single-key shortcuts
        if len(s) == 2 and s[0] in 'bsp' and s[1].isdigit():
            cmd = s[0]
            digit = int(s[1])
            if cmd == 'b' and 0 <= digit <= 6:
                return ("action", BUY_OFFSET + digit)
            elif cmd == 's' and 0 <= digit <= 6:
                return ("action", SELL_OFFSET + digit)
            elif cmd == 'p' and 0 <= digit <= 9:
                return ("action", PLAY_OFFSET + digit)

        # Single-key non-digit shortcuts
        if s == 'r':
            return ("action", REFRESH)
        if s == 'u':
            return ("action", UPGRADE)
        if s == 'f':
            return ("action", 26)  # FREEZE
        if s in ('e', ''):
            return ("action", END_TURN)
        if s == 'q':
            return ("quit", None)
        if s == '?':
            return ("help", None)

        # Full commands
        if parts[0] in ('buy', 'b') and len(parts) >= 2 and parts[1].isdigit():
            slot = int(parts[1])
            if 0 <= slot <= 6:
                return ("action", BUY_OFFSET + slot)
        if parts[0] in ('sell', 's') and len(parts) >= 2 and parts[1].isdigit():
            slot = int(parts[1])
            if 0 <= slot <= 6:
                return ("action", SELL_OFFSET + slot)
        if parts[0] in ('play', 'p') and len(parts) >= 2 and parts[1].isdigit():
            slot = int(parts[1])
            if 0 <= slot <= 9:
                return ("action", PLAY_OFFSET + slot)
        if parts[0] in ('refresh', 'r'):
            return ("action", REFRESH)
        if parts[0] in ('upgrade', 'u'):
            return ("action", UPGRADE)
        if parts[0] in ('freeze', 'f'):
            return ("action", 26)
        if parts[0] in ('end', 'e', 'done'):
            return ("action", END_TURN)
        if parts[0] in ('quit', 'q', 'exit'):
            return ("quit", None)
        if parts[0] in ('help', 'h', '?'):
            return ("help", None)
        if parts[0] in ('trinket', 't') and len(parts) >= 2 and parts[1].isdigit():
            return ("trinket", int(parts[1]))

        return ("unknown", None)

    def _action_name(self, action_id: int) -> str:
        if BUY_OFFSET <= action_id < BUY_OFFSET + 7:
            return f"buy[{action_id - BUY_OFFSET}]"
        if SELL_OFFSET <= action_id < SELL_OFFSET + 7:
            return f"sell[{action_id - SELL_OFFSET}]"
        if PLAY_OFFSET <= action_id < PLAY_OFFSET + 10:
            return f"play[{action_id - PLAY_OFFSET}]"
        names = {REFRESH: "refresh", UPGRADE: "upgrade", 26: "freeze", END_TURN: "end"}
        return names.get(action_id, f"action[{action_id}]")

    def _log(self, msg: str, attr: int = 0):
        self.log.append(msg)
        if len(self.log) > 100:
            self.log = self.log[-50:]

    def _trinket_cost(self, game, card_id: str) -> int:
        data = game.card_db.get(card_id) if game.card_db else None
        if data and data.tags:
            return data.tags.get(GameTag.COST, 3)
        return 3

    def _show_help(self, stdscr):
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        lines = [
            "═══ 帮助 ═══",
            "",
            "快捷键:",
            "  b0-b6  购买酒馆随从/法术",
            "  s0-s6  卖出场面随从",
            "  p0-p9  打出手牌",
            "  r      刷新酒馆 ($1)",
            "  u      升级酒馆等级",
            "  f      冻结/解冻酒馆",
            "  e/回车  结束回合",
            "  t0-t3  选择饰品",
            "  q      退出游戏",
            "  ?      显示帮助",
            "",
            "完整命令: buy/sell/play/refresh/upgrade/freeze/end/trinket",
            "",
            "按任意键返回...",
        ]
        for i, line in enumerate(lines):
            _addstr(stdscr, (h - len(lines)) // 2 + i, (w - len(line)) // 2,
                    line, HEADER if i == 0 else DIM)
        stdscr.refresh()
        stdscr.getch()

    def _init_colors(self):
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(GOLD, curses.COLOR_YELLOW, -1)
        curses.init_pair(KEYWORD, curses.COLOR_GREEN, -1)
        curses.init_pair(SPELL, curses.COLOR_CYAN, -1)
        curses.init_pair(ERROR, curses.COLOR_RED, -1)
        curses.init_pair(INFO, curses.COLOR_WHITE, -1)
        curses.init_pair(HEADER, curses.COLOR_YELLOW, -1)
        curses.init_pair(DIM, 8, -1)  # dark grey


def _addstr(win, y, x, text: str, attr: int = 0):
    try:
        win.addstr(y, x, text, curses.color_pair(attr) if attr else curses.A_NORMAL)
    except Exception:
        pass
