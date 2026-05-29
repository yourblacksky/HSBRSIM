"""Registry integrity tests — ensure active pool cards are properly implemented.

Tests:
  1. Every in-scope pool minion with effect tags has a script class.
  2. No active script contains Simplified/approximation markers.
  3. Duo-only content is not registered as active solo content.
  4. Golden minions (_G suffix) are not registered as pool minions.
"""

import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions      # noqa: F401
import hsrl.cards.spells       # noqa: F401
import hsrl.cards.trinkets     # noqa: F401
import hsrl.cards.heroes       # noqa: F401
import hsrl.cards.rewards      # noqa: F401
import hsrl.cards.anomalies    # noqa: F401
from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag

EFFECT_TAGS = {
    GameTag.BATTLECRY, GameTag.DEATHRATTLE, GameTag.Avenge,
    GameTag.RALLY, GameTag.START_OF_COMBAT, GameTag.END_OF_TURN,
    GameTag.START_OF_TURN, GameTag.ON_SELL, GameTag.SPELLCRAFT,
    GameTag.FODDER,
}

INACTIVE_PREFIXES = ("EXAMPLE_", "BGDUO_", "TOKEN_")

# Cards with effects flagged but engine support missing for scripts
KNOWN_DEFERRED = {
    "BG30_MagicItem_416",   # Token of the Old Gods
    "BG30_MagicItem_429",   # Demonblood Gourd
    "BG32_833",             # Slumber Sorcerer
}


class TestRegistryIntegrity(unittest.TestCase):

    def test_pool_minions_with_effects_have_scripts(self):
        missing = []
        for card_id, data in sorted(CARDS._cards.items()):
            if any(card_id.startswith(p) for p in INACTIVE_PREFIXES):
                continue
            if data.cardtype != CardType.MINION:
                continue
            if card_id.endswith("_G"):
                continue
            if "Buddy" in card_id:
                continue
            # Check if it's a pool minion
            if not any(card_id.startswith(p) for p in ("BG", "BGS_", "EBG_")):
                continue
            triggers = [t for t in EFFECT_TAGS if data.tags.get(t)]
            if not triggers:
                continue
            if data.scripts is None and card_id not in KNOWN_DEFERRED:
                tag_names = [t.name for t in triggers]
                missing.append((card_id, data.name, tag_names))
        self.assertEqual(missing, [],
                         f"Pool minions with effects but no scripts: {missing}")

    def test_no_duo_cards_in_active_pool(self):
        duo_cards = [cid for cid, data in CARDS._cards.items()
                     if cid.startswith("BGDUO_")
                     and data.cardtype in (CardType.MINION, CardType.SPELL, CardType.TRINKET)
                     and not cid.startswith("EXAMPLE_")]
        # DUO anomalies are registered as OOS — check they have out-of-scope scripts
        for cid in duo_cards:
            data = CARDS._cards[cid]
            if data.scripts is not None:
                ds = getattr(data.scripts, "__doc__", "") or ""
                if "OutOfScope" not in str(data.scripts.__name__) and "OUT_OF_SCOPE" not in ds:
                    self.fail(f"Duo card {cid} has active script: {data.scripts.__name__}")

    def test_golden_minions_not_in_pool(self):
        """Golden-only minions (_G suffix) should not be pool minions."""
        golden_pool = [cid for cid, data in CARDS._cards.items()
                       if cid.endswith("_G") and data.cardtype == CardType.MINION
                       and "is_pool_minion" in str(data.tags)]
        self.assertEqual(golden_pool, [],
                         f"Golden minions registered as pool: {golden_pool}")

    def test_trinket_registry_no_deferred_markers(self):
        """Active trinket scripts should not contain 'Simplified' in docstrings."""
        simplified = []
        for card_id, data in CARDS._cards.items():
            if data.cardtype != CardType.TRINKET:
                continue
            if card_id.startswith(("EXAMPLE_", "BGDUO_")):
                continue
            if card_id in KNOWN_DEFERRED:
                continue
            if data.scripts is not None:
                ds = (getattr(data.scripts, "__doc__", "") or "").lower()
                if "simplified" in ds or "approximation" in ds:
                    simplified.append((card_id, data.name, ds[:80]))
        self.assertEqual(simplified, [],
                         f"Active trinkets with simplified implementations: {simplified}")

    def test_minion_script_no_simplified_markers(self):
        """Active minion scripts should not contain 'Simplified' in docstrings."""
        simplified = []
        for card_id, data in CARDS._cards.items():
            if data.cardtype != CardType.MINION:
                continue
            if card_id in KNOWN_DEFERRED:
                continue
            if card_id.startswith(("EXAMPLE_", "BGDUO_")):
                continue
            if data.scripts is not None:
                ds = (getattr(data.scripts, "__doc__", "") or "").lower()
                if "simplified" in ds:
                    simplified.append((card_id, data.name, ds[:80]))
        self.assertEqual(simplified, [],
                         f"Active minions with simplified implementations: {simplified}")

    def test_registry_has_required_card_types(self):
        types = set(CARDS._cards[cid].cardtype for cid in CARDS._cards)
        for t in (CardType.MINION, CardType.SPELL, CardType.HERO,
                  CardType.HERO_POWER, CardType.TRINKET, CardType.REWARD,
                  CardType.ANOMALY):
            self.assertIn(t, types, f"Missing card type {t.name} in registry")


if __name__ == "__main__":
    unittest.main()
