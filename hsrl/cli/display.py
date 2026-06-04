"""Terminal display formatter for Battlegrounds game state.

Renders Chinese card names, stats, keywords, and effect text in a readable
layout suitable for an interactive CLI.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from hsrl.cli.zhcn import zhcn
from hsrl.core.enums import CardType, GameTag

if TYPE_CHECKING:
    from hsrl.core.player import Player
    from hsrl.core.game import Game

WIDTH = 80
SEP = "─" * WIDTH
DSEP = "═" * WIDTH


def display_state(game: "Game", player: "Player") -> str:
    """Render full game state for human player."""
    lines = []

    # ── Header ──
    turn = game.turn
    gold = player.gold
    max_gold = player.get_tag(GameTag.MAX_GOLD, min(3 + turn - 1, 10))
    tier = player.tavern_tier
    upgrade_cost = player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
    if upgrade_cost <= 0:
        upgrade_cost = {1: 5, 2: 7, 3: 8, 4: 9, 5: 10, 6: 11}.get(tier + 1, 11)

    lines.append(DSEP)
    lines.append(f"  第 {turn} 回合 | 金币: {gold}/{max_gold} | "
                 f"酒馆等级: T{tier}" +
                 (f" → T{tier+1} (${upgrade_cost})" if tier < 6 else " (满级)"))

    anomaly = _get_anomaly(game)
    if anomaly:
        lines.append(f"  畸变: {anomaly}")

    lines.append(DSEP)

    # ── Active buffs ──
    buffs = _get_active_buffs(player)
    if buffs:
        lines.append(f"  {', '.join(buffs)}")
        lines.append("")

    # Trinket offers (show before anything else — must resolve)
    offers = getattr(player, "_pending_trinket_offers", [])
    if offers:
        lines.append("")
        lines.append("  ★ 选择饰品 (输入 trinket <0-3>):")
        for i, cid in enumerate(offers):
            name, text = zhcn.card(cid)
            cost = _trinket_cost(game, cid)
            lines.append(f"    [{i}] {name} ({cost}铸币)")
            if text:
                lines.append(f"        {_clean(text)}")
        lines.append("")

    # ── Tavern ──
    lines.append(f"  ── 酒馆 (T{tier}·升级${upgrade_cost}) {SEP[:40]}──")
    tavern_entities = list(player.tavern[:7])
    if tavern_entities:
        for i, e in enumerate(tavern_entities):
            lines.append(_format_card(i, e, show_cost=True))
    else:
        lines.append("    (空)")
    lines.append("")

    # ── Hand ──
    hand_count = sum(1 for e in player.hand if e is not None)
    lines.append(f"  ── 手牌 ({hand_count}/10) {SEP[:55]}──")
    hand_entities = list(player.hand[:10])
    if hand_entities:
        for i, e in enumerate(hand_entities):
            if e is not None:
                lines.append(_format_card(i, e, show_cost=False))
    else:
        lines.append("    (空)")
    lines.append("")

    # ── Board ──
    board_minions = [m for m in player.board if not m.dead]
    lines.append(f"  ── 场面 ({len(board_minions)}/7) {SEP[:55]}──")
    if board_minions:
        for i, m in enumerate(board_minions):
            lines.append(_format_board_minion(i, m))
    else:
        lines.append("    (空)")
    lines.append("")

    # ── Trinkets ──
    trinkets = getattr(player, "trinkets", [])
    if trinkets:
        lines.append(f"  ── 已装备饰品 {SEP[:52]}──")
        for t in trinkets:
            cid = t.get_tag(GameTag.CARD_ID, "")
            name, text = zhcn.card(cid)
            lines.append(f"  {name}")
            if text:
                lines.append(f"    {_clean(text)}")
        lines.append("")

    lines.append(SEP)
    lines.append("  操作: buy <0-6> | sell <0-6> | play <0-9> | refresh | upgrade | freeze | end | help")
    lines.append(SEP)

    return "\n".join(lines)


def _format_card(idx: int, entity, show_cost: bool = True) -> str:
    """Format a tavern or hand card with name, stats, and effect text."""
    card_id = entity.get_tag(GameTag.CARD_ID, "")
    name = zhcn.name(card_id) or "?"
    ct = entity.get_tag(GameTag.CARDTYPE, 0)
    is_spell = ct in (CardType.SPELL, 42)
    golden = "★" if entity.get_tag(12, 0) > 0 else ""

    parts = []
    prefix = f"  [{idx}] {golden}{name}"

    if is_spell:
        cost = entity.get_tag(GameTag.COST, 0)
        tier = entity.tech_level
        prefix += f" (法术) T{tier}"
        if show_cost:
            prefix += f" ${cost}"
    else:
        prefix += f" {entity.atk}/{entity.health} T{entity.tech_level}"
        if show_cost:
            prefix += f" ${entity.get_tag(GameTag.COST, 3)}"

    frozen = entity.get_tag(GameTag.FROZEN, 0) > 0 if show_cost else False
    if frozen:
        prefix += " ❄"

    # For board minions (show_cost=False), show keywords inline
    if not show_cost:
        kws = _fmt_keywords(entity)
        prefix += kws

    parts.append(prefix)

    # Effect text
    text = zhcn.text(card_id)
    if text:
        cleaned = _clean(text)
        cleaned = _resolve_token_refs(cleaned, entity, show_cost)
        if len(cleaned) > 70:
            cleaned = cleaned[:67] + "..."
        parts.append(f"       {cleaned}")

    return "\n".join(parts)


def _format_board_minion(idx: int, m) -> str:
    """Format a board minion with stats, keywords, and effect text."""
    card_id = m.get_tag(GameTag.CARD_ID, "")
    name = zhcn.name(card_id) or (m.data.name if hasattr(m, "data") and m.data else "?")
    golden = "★" if m.get_tag(12, 0) > 0 else ""
    kws = _fmt_keywords(m)

    parts = []
    prefix = f"  [{idx}] {golden}{name}({m.atk}/{m.health}T{m.tech_level}){kws}"
    parts.append(prefix)

    text = zhcn.text(card_id)
    if text:
        cleaned = _clean(text)
        if len(cleaned) > 70:
            cleaned = cleaned[:67] + "..."
        parts.append(f"       {cleaned}")

    return "\n".join(parts)


def _resolve_token_refs(text: str, entity, show_cost: bool) -> str:
    """Resolve {0}, {1} placeholders with known token stats when possible."""
    # Blood Gem bonuses are stored on the player entity
    player = getattr(entity, 'controller', None)
    if player is not None:
        gem_atk = 1 + player.get_tag(120, 0)  # base 1 + bonus
        gem_hp = 1 + player.get_tag(121, 0)
        text = text.replace("鲜血宝石", f"鲜血宝石(+{gem_atk}/+{gem_hp})")

    # Common token references with known stats
    _TOKEN_STATS = {
        "甲虫": (1, 1),   # BG19_010t 半甲龟
        "雏龙": (1, 1),   # various whelps
        "微型机器人": (1, 1),  # microbots
        "触须": (2, 2),   # tentacles
    }
    for token, (atk, hp) in _TOKEN_STATS.items():
        if token in text:
            text = text.replace("{0}/{1}", f"{atk}/{hp}")

    return text


def _clean(text: str) -> str:
    """Clean HTML tags for terminal display, keep template placeholders."""
    text = (text.replace("<b>", "").replace("</b>", "")
                .replace("<i>", "").replace("</i>", "")
                .replace("[x]", "").replace("&lt;", "<").replace("&gt;", ">")
                .replace("\n", " ").replace("\r", " "))
    return " ".join(text.split())


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
    cid = m.get_tag(GameTag.CARD_ID, "")
    if cid in _CLEAVE_IDS:
        parts.append("顺劈")
    if parts:
        return " [" + "|".join(parts) + "]"
    return ""


_CLEAVE_IDS = {
    "BGS_022",   # Foe Reaper 4000
    "BG21_046",  # Wildfire Elemental
    "BG24_306",  # Recurring Nightmare
    "BG26_158",  # Meteor Crasher
    "BG27_029",  # Gnomelia, Polarity Ace
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
        return f"{name} — {_clean(text)}" if text else name
    return cid


def _get_active_buffs(player: "Player") -> list[str]:
    """Collect active player-level buff values for display."""
    parts = []
    gem_atk = player.get_tag(120, 0)  # BLOOD_GEM_BONUS_ATK
    gem_hp = player.get_tag(121, 0)   # BLOOD_GEM_BONUS_HEALTH
    if gem_atk > 0 or gem_hp > 0:
        parts.append(f"鲜血宝石 +{gem_atk}/+{gem_hp}")
    spell_disc = player.get_tag(138, 0)  # NEXT_SPELL_COST_REDUCTION
    if spell_disc > 0:
        parts.append(f"下一张法术减{spell_disc}费")
    free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
    if free > 0:
        parts.append(f"免费刷新×{free}")
    triple_tier = player.get_tag(111, 0)  # TRIPLE_REWARD_TIER
    if triple_tier > 0:
        parts.append(f"三连奖励等级: T{triple_tier}")
    return parts


def _trinket_cost(game: "Game", card_id: str) -> int:
    data = game.card_db.get(card_id) if game.card_db else None
    if data and data.tags:
        return data.tags.get(GameTag.COST, 3)
    return 3
