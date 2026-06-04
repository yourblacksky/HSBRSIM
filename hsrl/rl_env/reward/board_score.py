"""
BoardScore — evaluates board strength from multiple dimensions.

Decomposes board quality into: raw stats, keywords, tribe synergy,
scaling potential, economy value, and triple progress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hsrl.core.enums import GameTag

if TYPE_CHECKING:
    from hsrl.core.player import Player


@dataclass
class BoardScore:
    """Multi-dimensional board evaluation."""
    total: float = 0.0
    tempo: float = 0.0     # raw stats + immediate combat power
    scaling: float = 0.0   # growth potential (scaling keywords, tribes)
    economy: float = 0.0   # gold efficiency, pair/triple progress
    synergy: float = 0.0   # tribe synergy bonuses
    risk: float = 0.0      # vulnerability indicators

    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "tempo": self.tempo,
            "scaling": self.scaling,
            "economy": self.economy,
            "synergy": self.synergy,
            "risk": self.risk,
            **self.details,
        }


def compute_board_score_v2(player: "Player") -> BoardScore:
    """Compute BoardScore from a player's current board and hand state.

    Raw stats score: sum of (atk + health) / 50 for each minion
    Keyword bonuses: divine_shield, poison, reborn, taunt add multipliers
    Scaling: battlecry, deathrattle, end_of_turn effects indicate growth
    Economy: gold, hand size, upgrade cost
    Synergy: bonus for having multiple minions of the same tribe
    """
    living = [m for m in player.board if not m.dead]

    # ── Raw stats (tempo) ──
    raw_score = sum((m.atk + m.health) / 50.0 for m in living)

    # ── Keyword bonuses ──
    keyword_bonus = 0.0
    for m in living:
        if m.has_tag(GameTag.DIVINE_SHIELD): keyword_bonus += 0.5
        if m.has_tag(GameTag.POISONOUS): keyword_bonus += 1.0
        if m.has_tag(GameTag.VENOMOUS): keyword_bonus += 0.8
        if m.has_tag(GameTag.REBORN): keyword_bonus += 0.4
        if m.has_tag(GameTag.TAUNT): keyword_bonus += 0.2
        if m.has_tag(GameTag.CLEAVE): keyword_bonus += 0.6
        if m.has_tag(GameTag.WINDFURY): keyword_bonus += 0.3

    # ── Scaling potential ──
    scaling_score = 0.0
    for m in living:
        if m.has_tag(GameTag.BATTLECRY): scaling_score += 0.3
        if m.has_tag(GameTag.DEATHRATTLE): scaling_score += 0.2
        if m.has_tag(GameTag.Avenge): scaling_score += 0.5
        if m.has_tag(GameTag.START_OF_COMBAT): scaling_score += 0.4
        if m.has_tag(GameTag.RALLY): scaling_score += 0.4

    # ── Tribe synergy ──
    tribe_counts = {}
    for m in living:
        r = m.race
        if r and r.name not in ("NONE", "ALL"):
            tribe_counts[r.name] = tribe_counts.get(r.name, 0) + 1
    synergy_score = sum(max(0, c - 1) * 0.3 for c in tribe_counts.values())

    # ── Economy ──
    econ_score = 0.0
    econ_score += player.gold / 10.0
    econ_score += len(player.hand) * 0.1
    # Pairs in hand/board
    card_counts = {}
    for m in living + player.hand:
        cid = m.get_tag(GameTag.CARD_ID, "")
        if cid:
            card_counts[cid] = card_counts.get(cid, 0) + 1
    pair_score = sum(max(0, c - 1) * 0.5 for c in card_counts.values())
    econ_score += pair_score

    # ── Risk (vulnerability) ──
    risk_score = max(0.0, 7 - len(living)) * 0.3  # empty slots = vulnerable

    # ── Total ──
    # In board-building mode (no combat), empty slots aren't risky
    total = raw_score + keyword_bonus + scaling_score * 0.3 + synergy_score + econ_score * 0.2

    return BoardScore(
        total=float(total),
        tempo=float(raw_score + keyword_bonus),
        scaling=float(scaling_score),
        economy=float(econ_score),
        synergy=float(synergy_score),
        risk=float(risk_score),
        details={
            "raw_score": float(raw_score),
            "keyword_bonus": float(keyword_bonus),
            "pair_score": float(pair_score),
            "tribe_counts": tribe_counts,
        },
    )
