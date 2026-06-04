"""Curses panel rendering for Battlegrounds game state.

Each panel is a function that takes game state and returns a list of
(content, color_pair) tuples to be drawn in the curses window.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from hsrl.cli.zhcn import zhcn
from hsrl.core.enums import CardType, GameTag

if TYPE_CHECKING:
    from hsrl.core.player import Player
    from hsrl.core.game import Game

# ── Color pair constants (defined in app.py) ──
GOLD = 1
KEYWORD = 2
SPELL = 3
ERROR = 4
INFO = 5
HEADER = 6
DIM = 7


def render_all(win, game: "Game", player: "Player", y: int, w: int, log_lines: list[str]):
    """Render the full game state into the curses window starting at row y."""
    y = _render_status(win, game, player, y, w)
    y = _render_buffs(win, player, y, w)
    y = _render_sep(win, y, w, "酒馆")
    y = _render_tavern(win, player, y, w)
    y = _render_sep(win, y, w, "手牌")
    y = _render_hand(win, player, y, w)
    y = _render_sep(win, y, w, "场面")
    y = _render_board(win, player, y, w)
    y = _render_trinkets(win, game, player, y, w)
    if log_lines:
        y = _render_sep(win, y, w, "日志")
        y = _render_log(win, log_lines, y, w)
    return y


def _render_status(win, game, player, y, w) -> int:
    turn = game.turn
    gold = player.gold
    max_gold = player.get_tag(GameTag.MAX_GOLD, min(3 + turn - 1, 10))
    tier = player.tavern_tier
    upgrade_cost = player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
    if upgrade_cost <= 0:
        upgrade_cost = {1: 5, 2: 7, 3: 8, 4: 9, 5: 10, 6: 11}.get(tier + 1, 11)
    tier_str = f"T{tier}→T{tier+1}(${upgrade_cost})" if tier < 6 else f"T{tier}(满级)"

    line = f" 第{turn}回合 | 金币:{gold}/{max_gold} | 等级:{tier_str}"
    _addstr(win, y, 0, line[:w - 1], HEADER)
    y += 1

    anomaly = _get_anomaly(game)
    if anomaly:
        _addstr(win, y, 0, f" 畸变: {anomaly}"[:w - 1], DIM)
        y += 1
    return y


def _render_buffs(win, player, y, w) -> int:
    parts = []
    gem_atk = player.get_tag(120, 0)
    gem_hp = player.get_tag(121, 0)
    if gem_atk > 0 or gem_hp > 0:
        parts.append(f"鲜血宝石+{gem_atk}/+{gem_hp}")
    spell_disc = player.get_tag(138, 0)
    if spell_disc > 0:
        parts.append(f"法术减{spell_disc}费")
    free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
    if free > 0:
        parts.append(f"免费刷新×{free}")
    if parts:
        _addstr(win, y, 0, " " + " | ".join(parts), DIM)
        y += 1
    return y


def _render_sep(win, y, w, label: str) -> int:
    line = f"── {label} " + "─" * (w - len(label) - 4)
    _addstr(win, y, 0, line[:w - 1], DIM)
    return y + 1


def _render_tavern(win, player, y, w) -> int:
    entities = list(player.tavern[:7])
    if not entities:
        _addstr(win, y, 0, "  (空)", DIM)
        return y + 1
    for i, e in enumerate(entities):
        card_id = e.get_tag(GameTag.CARD_ID, "")
        name = zhcn.name(card_id) or "?"
        ct = e.get_tag(GameTag.CARDTYPE, 0)
        is_spell = ct in (CardType.SPELL, 42)
        frozen = " ❄" if e.get_tag(GameTag.FROZEN, 0) > 0 else ""
        golden = "★" if e.get_tag(12, 0) > 0 else ""

        if is_spell:
            header = f" [{i}] {golden}{name} (法术) T{e.tech_level} ${e.get_tag(GameTag.COST, 0)}{frozen}"
            _addstr(win, y, 0, header[:w - 1], SPELL)
        else:
            header = f" [{i}] {golden}{name} {e.atk}/{e.health} T{e.tech_level} ${e.get_tag(GameTag.COST, 3)}{frozen}"
            _addstr(win, y, 0, header[:w - 1], 0)
        y += 1

        text = zhcn.text(card_id)
        if text:
            cleaned = _clean(text)
            cleaned = _resolve_refs(cleaned, player)
            _addstr(win, y, 0, f"     {cleaned}"[:w - 1], DIM)
            y += 1
    return y


def _render_hand(win, player, y, w) -> int:
    entities = [c for c in player.hand[:10] if c is not None]
    if not entities:
        _addstr(win, y, 0, "  (空)", DIM)
        return y + 1
    for i, e in enumerate(entities):
        card_id = e.get_tag(GameTag.CARD_ID, "")
        name = zhcn.name(card_id) or "?"
        ct = e.get_tag(GameTag.CARDTYPE, 0)
        is_spell = ct in (CardType.SPELL, 42)
        golden = "★" if e.get_tag(12, 0) > 0 else ""

        if is_spell:
            header = f" [{i}] {golden}{name} (法术) T{e.tech_level} ${e.get_tag(GameTag.COST, 0)}"
            _addstr(win, y, 0, header[:w - 1], SPELL)
        else:
            kws = _fmt_keywords(e, card_id)
            header = f" [{i}] {golden}{name} {e.atk}/{e.health} T{e.tech_level}{kws}"
            _addstr(win, y, 0, header[:w - 1], 0)
        y += 1

        text = zhcn.text(card_id)
        if text:
            cleaned = _clean(text)
            cleaned = _resolve_refs(cleaned, player)
            _addstr(win, y, 0, f"     {cleaned}"[:w - 1], DIM)
            y += 1
    return y


def _render_board(win, player, y, w) -> int:
    board = [m for m in player.board if not m.dead]
    if not board:
        _addstr(win, y, 0, "  (空)", DIM)
        return y + 1
    for i, m in enumerate(board):
        card_id = m.get_tag(GameTag.CARD_ID, "")
        name = zhcn.name(card_id) or (m.data.name if hasattr(m, "data") and m.data else "?")
        golden = "★" if m.get_tag(12, 0) > 0 else ""
        kws = _fmt_keywords(m, card_id)
        header = f" [{i}] {golden}{name}({m.atk}/{m.health}T{m.tech_level}){kws}"
        _addstr(win, y, 0, header[:w - 1], 0)
        y += 1
    return y


def _render_trinkets(win, game, player, y, w) -> int:
    offers = getattr(player, "_pending_trinket_offers", [])
    if offers:
        _addstr(win, y, 0, f"── 选择饰品 (t <0-3>) {'─' * (w - 23)}"[:w - 1], DIM)
        y += 1
        for i, cid in enumerate(offers):
            name, text = zhcn.card(cid)
            cost = _trinket_cost(game, cid)
            _addstr(win, y, 0, f" [{i}] {name} (${cost})"[:w - 1], SPELL)
            y += 1
            if text:
                _addstr(win, y, 0, f"     {_clean(text)}"[:w - 1], DIM)
                y += 1

    trinkets = getattr(player, "trinkets", [])
    if trinkets:
        _addstr(win, y, 0, f"── 已装备饰品 {'─' * (w - 14)}"[:w - 1], DIM)
        y += 1
        for t in trinkets:
            cid = t.get_tag(GameTag.CARD_ID, "")
            name, text = zhcn.card(cid)
            _addstr(win, y, 0, f" {name}"[:w - 1], 0)
            y += 1
    return y


def _render_log(win, log_lines, y, w) -> int:
    for line in log_lines[-6:]:
        attr = ERROR if "⚠" in line else INFO
        _addstr(win, y, 0, f" {line}"[:w - 1], attr)
        y += 1
    return y


def render_cmdline(win, y, w, input_buf: str, shortcuts: str):
    """Render the command line at the bottom."""
    prompt = f"> {input_buf}_"
    _addstr(win, y, 0, prompt[:w - len(shortcuts) - 1], 0)
    _addstr(win, y, w - len(shortcuts) - 1, shortcuts, DIM)


# ── Helpers ───────────────────────────────────────────────────────

def _addstr(win, y, x, text: str, attr: int):
    """Safe addstr that clips to window bounds."""
    try:
        if attr:
            win.addstr(y, x, text, attr)
        else:
            win.addstr(y, x, text)
    except Exception:
        pass


def _clean(text: str) -> str:
    text = (text.replace("<b>", "").replace("</b>", "")
                .replace("<i>", "").replace("</i>", "")
                .replace("[x]", "").replace("&lt;", "<").replace("&gt;", ">")
                .replace("\n", " ").replace("\r", " "))
    return " ".join(text.split())


def _resolve_refs(text: str, player) -> str:
    gem_atk = 1 + player.get_tag(120, 0)
    gem_hp = 1 + player.get_tag(121, 0)
    text = text.replace("鲜血宝石", f"鲜血宝石(+{gem_atk}/+{gem_hp})")
    for token, (atk, hp) in [("甲虫", (1, 1)), ("雏龙", (1, 1)),
                              ("微型机器人", (1, 1)), ("触须", (2, 2))]:
        if token in text:
            text = text.replace("{0}/{1}", f"{atk}/{hp}")
    return text


def _fmt_keywords(m, card_id: str) -> str:
    parts = []
    if getattr(m, "taunt", False): parts.append("嘲讽")
    if getattr(m, "divine_shield", False): parts.append("圣盾")
    if getattr(m, "poisonous", False): parts.append("剧毒")
    if getattr(m, "venomous", False): parts.append("烈毒")
    if getattr(m, "reborn", False): parts.append("复生")
    if getattr(m, "windfury", False): parts.append("风怒")
    if card_id in _CLEAVE_IDS: parts.append("顺劈")
    return " [" + "|".join(parts) + "]" if parts else ""


_CLEAVE_IDS = {"BGS_022", "BG21_046", "BG24_306", "BG25_022", "BG26_158", "BG27_029"}


def _get_anomaly(game) -> str:
    anomaly = getattr(game, "active_anomaly", None)
    if anomaly is None or anomaly is True or anomaly is False:
        return ""
    cid = anomaly.get_tag(GameTag.CARD_ID, "")
    name, text = zhcn.card(cid)
    if name:
        return f"{name} — {_clean(text)}" if text else name
    return cid


def _trinket_cost(game, card_id: str) -> int:
    data = game.card_db.get(card_id) if game.card_db else None
    if data and data.tags:
        return data.tags.get(GameTag.COST, 3)
    return 3
