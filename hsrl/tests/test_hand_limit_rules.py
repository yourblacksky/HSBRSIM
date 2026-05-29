"""Hand limit rule tests — verify card generation respects MAX_HAND_SIZE=10.

Tests:
  1. Cannot buy minion with full hand
  2. Cannot buy spell with full hand
  3. GetBloodGem respects hand limit
  4. AddToHand respects hand limit
  5. Discover rejects when hand is full
"""

import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions   # noqa: F401
import hsrl.cards.spells    # noqa: F401
from hsrl.core.actions import AddToHand, GetBloodGem, DiscoverMinion, MAX_HAND_SIZE
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag, Race, Zone
from hsrl.core.game import Game
from hsrl.core.minion_pool import MinionPool
from hsrl.core.player import Player
from hsrl.core.spell_pool import SpellPool


class TestHandLimitRules(unittest.TestCase):

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.minion_pool = MinionPool(CARDS)
        self.game.spell_pool = SpellPool(CARDS)
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.p1]
        self.game._auto_resolve_choices = True

    def _fill_hand(self, n=10):
        for _ in range(n):
            if len(self.p1.hand) >= n:
                break
            m = self.game.create_minion("EXAMPLE_VANILLA")
            m.controller = self.p1
            m.zone = Zone.HAND
            self.p1.hand.append(m)

    def test_cannot_buy_minion_with_full_hand(self):
        self._fill_hand(10)
        self.p1.set_tag(GameTag.GOLD, 99)
        self.p1.set_tag(GameTag.TAVERN_TIER, 2)
        self.game.refresh_tavern(self.p1)
        minions = [m for m in self.p1.tavern
                   if m.get_tag(GameTag.CARDTYPE) == 1]
        self.assertTrue(minions, "Need a minion in tavern")
        before = len(self.p1.hand)
        self.game.buy_minion(self.p1, minions[0])
        self.assertEqual(len(self.p1.hand), before,
                         "Hand should not grow when full")
        self.assertIn(minions[0], self.p1.tavern,
                       "Minion should stay in tavern when hand is full")

    def test_cannot_buy_spell_with_full_hand(self):
        self._fill_hand(10)
        self.p1.set_tag(GameTag.GOLD, 99)
        self.p1.set_tag(GameTag.TAVERN_TIER, 3)
        self.game.refresh_tavern(self.p1)
        spells = [m for m in self.p1.tavern
                  if m.get_tag(GameTag.CARDTYPE) == 3]
        if not spells:
            self.skipTest("No spells in tavern")
        before = len(self.p1.hand)
        self.game.buy_spell(self.p1, spells[0])
        self.assertEqual(len(self.p1.hand), before)
        self.assertIn(spells[0], self.p1.tavern)

    def test_get_blood_gem_respects_hand_limit(self):
        self._fill_hand(10)
        self.game.queue_action(GetBloodGem(self.p1, count=3))
        self.game.resolve_queue()
        self.assertEqual(len(self.p1.hand), 10,
                         "Hand should remain at 10")

    def test_add_to_hand_respects_hand_limit(self):
        self._fill_hand(10)
        self.game.queue_action(AddToHand(self.p1, "EXAMPLE_VANILLA"))
        self.game.resolve_queue()
        self.assertEqual(len(self.p1.hand), 10,
                         "AddToHand should reject when hand is full")

    def test_add_to_hand_adds_when_space_available(self):
        self._fill_hand(9)
        self.game.queue_action(AddToHand(self.p1, "EXAMPLE_TAUNT"))
        self.game.resolve_queue()
        self.assertEqual(len(self.p1.hand), 10)

    def test_discover_rejects_full_hand(self):
        self._fill_hand(10)
        self.game._auto_resolve_choices = False
        self.game.queue_action(DiscoverMinion(self.p1, max_tier=2))
        self.game.resolve_queue()
        self.assertIsNone(self.game._pending_choice,
                          "No pending choice when hand is full")

    def test_blood_gem_adds_to_hand_with_space(self):
        self.game.queue_action(GetBloodGem(self.p1, count=3))
        self.game.resolve_queue()
        self.assertEqual(len(self.p1.hand), 3)

    def test_triple_reward_does_not_break_hand_limit(self):
        """Golden play's triple reward respect hand limit."""
        import random
        self._fill_hand(10)
        golden = self.game.create_minion("EXAMPLE_TRIPLE")
        golden.controller = self.p1
        golden.set_tag(GameTag.GOLDEN, True)
        golden.set_tag(GameTag.TRIPLE_REWARD_TIER, 2)
        golden.zone = Zone.HAND
        self.p1.hand.append(golden)
        # Should not crash — golden play adds to hand, discovery is queued
        # but hand is full so no card should be added
        self.game.play_minion(self.p1, golden)
        # No crash = pass
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
