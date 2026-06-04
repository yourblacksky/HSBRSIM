"""
HSRL Spell Pool

Shared pool of purchasable Tavern Spells. Each spell appears at most
once in the pool (unlike minions which have 7-16 copies each).
"""

import random
from typing import List, Optional, Set

from hsrl.core.enums import CardType


class SpellPool:
    """Manages the shared tavern spell pool across all players.

    Unlike MinionPool, each spell has only 1 copy (spells are unique).
    """

    POOL_SIZES = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}

    def __init__(self, card_db, rng=None):
        self._card_db = card_db
        self.rng = rng if rng is not None else random
        self._pools: dict[int, List[str]] = {tier: [] for tier in range(1, 8)}
        self._active: Set[str] = set()

        for card_id in card_db.all_ids():
            data = card_db.get(card_id)
            if data is None:
                continue
            if data.cardtype != CardType.SPELL:
                continue
            # Only include pool spells (skip tokens like Blood Gems,
            # The Goldenizer, Siren's Song, etc.)
            if not data.tags.get("is_pool_spell", False):
                continue
            tier = data.tech_level
            if tier not in self.POOL_SIZES:
                continue
            # Skip example/test cards
            if card_id.startswith("EXAMPLE_"):
                continue
            self._pools[tier].append(card_id)
            self._active.add(card_id)

    def draw(self, tavern_tier: int, count: int = 1) -> List[str]:
        """Draw up to `count` spells from pool tiers <= tavern_tier.

        Returns a list of unique card_ids. Each spell is removed from
        the pool when drawn.
        """
        candidates = []
        for tier in range(1, tavern_tier + 1):
            candidates.extend(self._pools.get(tier, []))

        if not candidates:
            return []

        drawn = []
        for _ in range(min(count, len(candidates))):
            card_id = self.rng.choice(candidates)
            self._remove_from_pool(card_id)
            drawn.append(card_id)
            candidates.remove(card_id)

        return drawn

    def _remove_from_pool(self, card_id: str) -> None:
        """Remove a spell from its tier pool."""
        data = self._card_db.get(card_id)
        if data is None:
            return
        tier = data.tech_level
        pool = self._pools.get(tier, [])
        if card_id in pool:
            pool.remove(card_id)

    def return_card(self, card_id: str) -> bool:
        """Return a spell to the pool (e.g., when sold or player dies)."""
        data = self._card_db.get(card_id)
        if data is None:
            return False
        tier = data.tech_level
        if tier not in self._pools:
            return False
        # Don't exceed the 1-per-type limit
        if card_id in self._pools[tier]:
            return False
        self._pools[tier].append(card_id)
        return True

    def is_pool_spell(self, card_id: str) -> bool:
        """Check whether a card_id is a pool spell."""
        return card_id in self._active

    def available_count(self, tavern_tier: int) -> int:
        """Total number of spells still available at or below tier."""
        count = 0
        for tier in range(1, tavern_tier + 1):
            count += len(self._pools.get(tier, []))
        return count

    def tier_count(self, tier: int) -> int:
        """Number of spells remaining at a specific tier."""
        return len(self._pools.get(tier, []))

    def get_random(self) -> Optional[str]:
        """Return a random spell card_id from the full active pool."""
        if not self._active:
            return None
        return self.rng.choice(list(self._active))
