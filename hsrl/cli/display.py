"""Terminal display formatter for Battlegrounds game state.

Renders Chinese card names, stats, keywords, and effect text in a compact
readable layout suitable for an interactive CLI.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from hsrl.cli.zhcn import zhcn
from hsrl.core.enums import CardType, GameTag

if TYPE_CHECKING:
    from hsrl.core.player import Player
    from hsrl.core.game import Game

# Keyword display abbreviations and order
_KEYWORDS = [
    ("taunt", "嘲讽"),
    ("divine_shield", "圣盾"),
    ("poisonous", "剧毒"),
    ("venomous", "烈毒"),
    ("reborn", "复生"),
    ("windfury", "风怒"),
    ("cleave", "顺劈"),
]

WIDTH = 80
SEP = "─" * WIDTH
DSEP = "═" * WIDTH


def display_state(game: "Game", player: "Player") -> str:
    """Render full game state for human player."""
    lines = []

    # ── Header: turn, gold, tier ──
    turn = game.turn
    gold = player.gold
    max_gold = 10
    tier = player.tavern_tier
    upgrade_cost = player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
    if upgrade_cost <= 0:
        upgrade_cost = {1: 5, 2: 7, 3: 8, 4: 9, 5: 10, 6: 11}.get(tier + 1, 11)

    lines.append(DSEP)
    lines.append(f"  第 {turn} 回合 | 金币: {gold}/{max_gold} | "
                 f"酒馆等级: T{tier}" +
                 (f" → T{tier+1} (${upgrade_cost})" if tier < 6 else " (满级)"))

    # Anomaly
    anomaly = _get_anomaly(game)
    if anomaly:
        lines.append(f"  畸变: {anomaly}")

    lines.append(DSEP)

    # Trinket offers (highest priority — need to resolve first)
    offers = getattr(player, "_pending_trinket_offers", [])
    if offers:
        lines.append("")
        lines.append("  ★ 选择饰品 (输入 trinket <0-3>):")
        for i, cid in enumerate(offers):
            name, text = zhcn.card(cid)
            cost = _trinket_cost(game, cid)
            lines.append(f"    [{i}] {name} ({cost}铸币) — {text}")
        lines.append("")

    # ── Tavern ──
    lines.append(f"  {'─'*38} {'─'*38}")
    lines.append(f"  {'酒馆随从':<38} {'手牌':<38}")
    lines.append(f"  {'─'*38} {'─'*38}")

    tavern_entities = list(player.tavern[:7])
    hand_entities = list(player.hand[:10])
    max_rows = max(len(tavern_entities), len(hand_entities), 1)

    for i in range(max_rows):
        left = _format_tavern_slot(i, tavern_entities[i] if i < len(tavern_entities) else None)
        right = _format_hand_slot(i, hand_entities[i] if i < len(hand_entities) else None)
        lines.append(f"  {left:<38} {right:<38}")

    lines.append(f"  {'─'*38} {'─'*38}")

    # ── Board ──
    board_minions = [m for m in player.board if not m.dead]
    lines.append("")
    lines.append(f"  ── 场面 ({len(board_minions)}/7 随从) ──")
    if board_minions:
        board_parts = []
        for i, m in enumerate(board_minions):
            card_id = m.get_tag(GameTag.CARD_ID, "")
            name = zhcn.name(card_id) or m.data.name if hasattr(m, "data") and m.data else "?"
            golden = "★" if m.get_tag(12, 0) > 0 else ""
            kws = _fmt_keywords(m)
            board_parts.append(f"  [{i}] {golden}{name}({m.atk}/{m.health}T{m.tech_level}){kws}")
        lines.extend(board_parts)
    else:
        lines.append("  (空)")

    # ── Trinkets (equipped) ──
    trinkets = getattr(player, "trinkets", [])
    if trinkets:
        lines.append("")
        lines.append("  ── 已装备饰品 ──")
        for t in trinkets:
            cid = t.get_tag(GameTag.CARD_ID, "")
            name, text = zhcn.card(cid)
            lines.append(f"  {name} — {text}")

    lines.append("")
    lines.append(SEP)
    lines.append("  操作: buy <0-6> | sell <0-6> | play <0-9> | refresh | upgrade | freeze | end | help")
    lines.append(SEP)

    return "\n".join(lines)


def _format_tavern_slot(idx: int, entity) -> str:
    if entity is None:
        return f"[{idx}] (空)"
    card_id = entity.get_tag(GameTag.CARD_ID, "")
    name = zhcn.name(card_id) or "?"
    ct = entity.get_tag(GameTag.CARDTYPE, 0)
    is_spell = ct in (CardType.SPELL, 42)  # BATTLEGROUND_SPELL = 42
    frozen = " ❄" if entity.get_tag(GameTag.FROZEN, 0) > 0 else ""

    if is_spell:
        cost = entity.get_tag(GameTag.COST, 0)
        text = zhcn.text(card_id)
        short = text[:40].replace("\n", " ").replace("<b>", "").replace("</b>", "")
        return f"[{idx}] {name} T{entity.tech_level} ${cost}{frozen} {short}"
    else:
        return f"[{idx}] {name} {entity.atk}/{entity.health} T{entity.tech_level} ${entity.get_tag(GameTag.COST, 3)}{frozen}"


def _format_hand_slot(idx: int, entity) -> str:
    if entity is None:
        return f"[{idx}] (空)"
    card_id = entity.get_tag(GameTag.CARD_ID, "")
    name = zhcn.name(card_id) or "?"
    ct = entity.get_tag(GameTag.CARDTYPE, 0)
    is_minion = ct == CardType.MINION
    golden = "★" if entity.get_tag(12, 0) > 0 else ""
    text = zhcn.text(card_id)
    short = text[:45].replace("\n", " ").replace("<b>", "").replace("</b>", "")
    if is_minion:
        return f"[{idx}] {golden}{name} {entity.atk}/{entity.health} T{entity.tech_level}"
    else:
        return f"[{idx}] {golden}{name} (法术) T{entity.tech_level} ${entity.get_tag(GameTag.COST, 0)}"


def _fmt_keywords(m) -> str:
    """Compact keyword display."""
    parts = []
    if getattr(m, "taunt", False):
        parts.append("嘲讽")
    if getattr(m, "divine_shield", False):
        parts.append("圣盾")
    if getattr(m, "poisonous", False):
        parts.append("剧毒")
    if getattr(m, "venomous", False):
        parts.append("烈毒")
    if getattr(m, "reborn", False):
        parts.append("复生")
    if getattr(m, "windfury", False):
        parts.append("风怒")
    # Cleave is not a standard attribute; check via card_id list
    cid = m.get_tag(GameTag.CARD_ID, "")
    if cid in _CLEAVE_IDS:
        parts.append("顺劈")
    if parts:
        return " [" + "|".join(parts) + "]"
    return ""


_CLEAVE_IDS = {
    "BGS_022", "BG21_046", "BG24_306", "BG25_022",
    "BG26_158", "BG27_029",
}


def _get_anomaly(game: "Game") -> str:
    anomaly = getattr(game, "active_anomaly", None)
    if anomaly is None or anomaly is True:
        return ""
    if anomaly is False:
        return ""
    cid = anomaly.get_tag(GameTag.CARD_ID, "")
    name, text = zhcn.card(cid)
    if name:
        return f"{name} — {text}" if text else name
    return cid


def _trinket_cost(game: "Game", card_id: str) -> int:
    data = game.card_db.get(card_id) if game.card_db else None
    if data and data.tags:
        return data.tags.get(GameTag.COST, 3)
    return 3
