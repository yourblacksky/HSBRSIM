"""
HSRL Minion Pool — Shared pool system for Battlegrounds.

Every minion in the tavern comes from a shared pool across all 8 players.
When a player buys a minion, a copy is removed from the pool. When sold or
the player is eliminated, copies return to the pool.

Pool sizes per tier (current as of Patch 35.x):
  Tier 1: 16 copies  |  Tier 2: 15 copies  |  Tier 3: 13 copies
  Tier 4: 11 copies  |  Tier 5: 9 copies   |  Tier 6: 7 copies
  Tier 7: 5 copies
"""

import random
from collections import defaultdict
from typing import Dict, List, Optional, Set

from hsrl.core.enums import CardType, Race


class MinionPool:
    """Shared minion pool across all players in a Battlegrounds match."""

    POOL_SIZES = {
        1: 16,
        2: 15,
        3: 13,
        4: 11,
        5: 9,
        6: 7,
        7: 5,
    }

    def __init__(self, card_db, rng=None):
        """Initialize the shared pool from a CardDB registry.

        Only pool minions (MINION type, known tech_level, non-token) are added.
        Token minions (summoned by effects) are NOT in the shared pool.
        """
        self.card_db = card_db
        self.rng = rng if rng is not None else random
        # _pools[tier] = list of card_id strings (one per copy)
        self._pools: Dict[int, List[str]] = {t: [] for t in range(1, 8)}
        # _pool_minions = set of card_ids that are part of the shared pool
        self._pool_minions: Set[str] = set()

        for card_id, data in card_db._cards.items():
            if data.cardtype != CardType.MINION:
                continue
            tech_level = data.tech_level
            if tech_level not in self.POOL_SIZES:
                continue
            # Tokens and examples don't go in the pool
            if card_id.startswith("EXAMPLE_") or card_id.startswith("TOKEN_"):
                continue
            # Derived tokens (card_id ends with 't' or 't'+digit, e.g. BG19_010t, BG27_004t2)
            # are not pool minions
            import re
            if re.search(r't\d*$', card_id) and len(card_id) > 3:
                continue
            # Buddy cards (e.g. BG20_HERO_100_Buddy, BG20_HERO_100_Buddy_G) are not pool minions
            if "Buddy" in card_id or "buddy" in card_id.lower():
                continue
            # Golden-only minions (card_id ends with _G) are not in the pool
            if card_id.endswith("_G"):
                continue
            count = self.POOL_SIZES[tech_level]
            self._pools[tech_level].extend([card_id] * count)
            self._pool_minions.add(card_id)

    # ── Public API ──────────────────────────────────────────────────────

    def draw(self, tavern_tier: int, count: int = 1,
             race_filter=None, min_tier: int = 1) -> List[str]:
        """Draw *count* random minion card_ids from tiers ≤ tavern_tier.

        Returns fewer than *count* if the pool is exhausted.
        If min_tier > 1, only draw from tiers ≥ min_tier.
        """
        valid = []
        for tier in range(min_tier, tavern_tier + 1):
            valid.extend(self._pools.get(tier, []))

        if race_filter is not None:
            valid = [cid for cid in valid
                     if self._matches_race(cid, race_filter)]

        drawn = self.rng.sample(valid, min(count, len(valid)))
        for card_id in drawn:
            tier = self._get_tier(card_id)
            if tier:
                self._pools[tier].remove(card_id)
        return drawn

    def return_card(self, card_id: str, count: int = 1) -> None:
        """Return *count* copies of a minion to the pool.

        Caps at the max pool size for that minion's tier.
        """
        tier = self._get_tier(card_id)
        if tier is None:
            return
        max_copies = self.POOL_SIZES.get(tier, 0)
        current = self.available_count(card_id)
        to_return = min(count, max_copies - current)
        self._pools[tier].extend([card_id] * to_return)

    def remove_card(self, card_id: str, count: int = 1) -> int:
        """Remove *count* copies from the pool. Returns how many were removed."""
        tier = self._get_tier(card_id)
        if tier is None:
            return 0
        removed = 0
        for _ in range(count):
            try:
                self._pools[tier].remove(card_id)
                removed += 1
            except ValueError:
                break
        return removed

    def remove_all_copies(self, card_id: str) -> int:
        """Remove ALL copies of a card from the pool. Returns count removed."""
        tier = self._get_tier(card_id)
        if tier is None:
            return 0
        removed = 0
        while True:
            try:
                self._pools[tier].remove(card_id)
                removed += 1
            except ValueError:
                break
        return removed

    def return_all_player_cards(self, player) -> None:
        """When a player is eliminated, return all their minions to the pool."""
        for m in player.board:
            cid = m.get_tag(self._game_tag("CARD_ID"))
            if cid and cid in self._pool_minions:
                if m.is_golden:
                    self.return_card(cid, 3)
                else:
                    self.return_card(cid, 1)
        for m in player.hand:
            cid = m.get_tag(self._game_tag("CARD_ID"))
            if cid and cid in self._pool_minions:
                self.return_card(cid, 1)

    def available_count(self, card_id: str) -> int:
        """How many copies of this card remain in the pool."""
        tier = self._get_tier(card_id)
        if tier is None:
            return 0
        return sum(1 for c in self._pools[tier] if c == card_id)

    def get_available_cards(self, tavern_tier: int, race_filter=None) -> List[str]:
        """List unique card_ids available from tiers ≤ tavern_tier."""
        valid = []
        for tier in range(1, tavern_tier + 1):
            valid.extend(self._pools.get(tier, []))
        unique = list(set(valid))
        if race_filter is not None:
            unique = [cid for cid in unique
                      if self._matches_race(cid, race_filter)]
        return unique

    def is_pool_minion(self, card_id: str) -> bool:
        """Check if a card_id belongs to the shared pool."""
        return card_id in self._pool_minions

    # ── Internal helpers ────────────────────────────────────────────────

    def _get_tier(self, card_id: str) -> Optional[int]:
        """Get the tech level of a card from the registry."""
        data = self.card_db.get(card_id)
        if data is None:
            return None
        return data.tech_level

    def _matches_race(self, card_id: str, race_filter) -> bool:
        """Check if a card matches a race filter.

        race_filter can be a single Race value, a set of Race values, or None.
        Race.ALL (Amalgam-type) always matches. Race.NONE (tribeless) only
        matches when race_filter is None (no filter applied).
        """
        data = self.card_db.get(card_id)
        if data is None:
            return False
        if data.race == Race.ALL:
            return True
        if race_filter is None:
            return True
        if isinstance(race_filter, (set, frozenset, list, tuple)):
            return data.race in race_filter
        return data.race == race_filter

    @staticmethod
    def _game_tag(name: str):
        """Lazy ref to GameTag to avoid circular import in non-TYPE_CHECKING."""
        from hsrl.core.enums import GameTag
        return getattr(GameTag, name)

    def __repr__(self) -> str:
        parts = []
        for tier in range(1, 7):
            parts.append(f"T{tier}={len(self._pools[tier])}")
        return f"<MinionPool {' '.join(parts)}>"
