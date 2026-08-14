"""Discover decision state tests — verify PendingChoice system.

Tests that DiscoverMinion/DiscoverSpell create PendingChoice which can be
observed and resolved by the RL agent rather than random auto-selection.
"""

import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions   # noqa: F401
import hsrl.cards.spells    # noqa: F401
from hsrl.core.actions import (
    Action, AddToHand, DiscoverMinion, DiscoverSpell, TriggerBattlecry,
    PendingChoice,
)
from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, Race
from hsrl.core.game import Game
from hsrl.core.player import Player


class TestDiscoverChoiceState(unittest.TestCase):

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.p1]
        self.game._auto_resolve_choices = False

    def _trigger_battlecry(self, source):
        bc = source.battlecry
        if bc:
            if isinstance(bc, (list, tuple)):
                for action in bc:
                    self.game.queue_action(action, source=source)
            else:
                self.game.queue_action(bc, source=source)
            self.game.resolve_queue()

    def test_discover_minion_creates_pending_choice(self):
        m = self.game.create_minion("EXAMPLE_DISCOVER")
        self.game.summon(self.p1, m)
        self._trigger_battlecry(m)

        self.assertIsNotNone(self.game._pending_choice)
        self.assertEqual(self.game._pending_choice.choice_type, "minion")
        self.assertEqual(len(self.game._pending_choice.options), 3)
        self.assertEqual(len(self.p1.hand), 0,
                         "No card added before choice is resolved")

    def test_choice_action_adds_selected_card(self):
        m = self.game.create_minion("EXAMPLE_DISCOVER")
        self.game.summon(self.p1, m)
        self._trigger_battlecry(m)

        self.game.resolve_pending_choice(0)
        self.assertEqual(len(self.p1.hand), 1,
                         "Selected card should be added to hand")
        self.assertIsNone(self.game._pending_choice)

    def test_discover_spell_creates_pending_choice(self):
        from hsrl.core.actions import DiscoverSpell
        self.game.queue_action(DiscoverSpell(self.p1))
        self.game.resolve_queue()

        self.assertIsNotNone(self.game._pending_choice)
        self.assertEqual(self.game._pending_choice.choice_type, "spell")

    def test_discover_spell_choice_adds_to_hand(self):
        from hsrl.core.actions import DiscoverSpell
        self.game.queue_action(DiscoverSpell(self.p1))
        self.game.resolve_queue()

        self.game.resolve_pending_choice(0)
        self.assertGreater(len(self.p1.hand), 0)
        self.assertEqual(
            self.p1.hand[0].get_tag(GameTag.CARDTYPE), CardType.SPELL,
        )

    def test_full_hand_discover_does_not_create_choice(self):
        from hsrl.core.actions import DiscoverSpell
        # Fill hand
        for _ in range(10):
            self.p1.hand.append(self.game.create_minion("EXAMPLE_VANILLA"))

        self.game.queue_action(DiscoverSpell(self.p1))
        self.game.resolve_queue()

        self.assertIsNone(self.game._pending_choice,
                          "No pending choice when hand is full")

    def test_auto_resolve_fills_hand_in_heuristic_mode(self):
        self.game._auto_resolve_choices = True

        from hsrl.core.actions import DiscoverMinion
        self.game.queue_action(DiscoverMinion(self.p1, max_tier=2))
        self.game.resolve_queue()

        self.assertEqual(len(self.p1.hand), 1,
                         "Auto-resolve should add card to hand")
        self.assertIsNone(self.game._pending_choice)

    def test_pending_choice_options_have_names(self):
        m = self.game.create_minion("EXAMPLE_DISCOVER")
        self.game.summon(self.p1, m)
        self._trigger_battlecry(m)

        choice = self.game._pending_choice
        for card_id, name in choice.options:
            self.assertIsInstance(card_id, str)
            self.assertIsInstance(name, str)
            self.assertIsNotNone(CARDS.get(card_id))


class TestRLActionMaskExposesDiscoverOptions(unittest.TestCase):
    """Verify RL env can observe and act on pending choices."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.p1]
        self.game._auto_resolve_choices = False

    def test_rl_can_read_pending_choice_options(self):
        from hsrl.core.actions import DiscoverSpell
        self.game.queue_action(DiscoverSpell(self.p1))
        self.game.resolve_queue()

        choice = self.game._pending_choice
        self.assertIsNotNone(choice)
        n = len(choice.options)
        self.assertGreaterEqual(n, 1, "Discover should have at least 1 option")
        # Each option is (card_id, name)
        self.assertIsInstance(choice.options[0][0], str)

    def test_resolving_all_valid_indices_works(self):
        from hsrl.core.actions import DiscoverSpell
        self.game.queue_action(DiscoverSpell(self.p1))
        self.game.resolve_queue()

        choice = self.game._pending_choice
        for i in range(len(choice.options)):
            # Create fresh game state each iteration
            g2 = Game([], seed=0)
            g2.card_db = CARDS
            p = Player(CARDS.get("EXAMPLE_VANILLA"), game=g2)
            g2.players = [p]
            g2._auto_resolve_choices = False
            from hsrl.core.actions import DiscoverSpell as DS
            g2.queue_action(DS(p))
            g2.resolve_queue()
            g2.resolve_pending_choice(i)
            self.assertEqual(len(p.hand), 1, f"Choice {i} should add card")

    def test_two_players_pending_choices_are_isolated(self):
        p2 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players.append(p2)

        self.game.active_player = self.p1
        self.game.queue_action(DiscoverSpell(self.p1))
        self.game.resolve_queue()
        first_choice = self.game.get_pending_choice(self.p1)

        self.game.active_player = p2
        self.game.queue_action(DiscoverSpell(p2))
        self.game.resolve_queue()
        second_choice = self.game.get_pending_choice(p2)

        self.assertIsNotNone(first_choice)
        self.assertIsNotNone(second_choice)
        self.assertIsNot(first_choice, second_choice)
        self.game.resolve_pending_choice(0, p2)
        self.assertIs(self.game.get_pending_choice(self.p1), first_choice)
        self.assertIsNone(self.game.get_pending_choice(p2))
        self.assertEqual(len(self.p1.hand), 0)
        self.assertEqual(len(p2.hand), 1)


if __name__ == "__main__":
    unittest.main()
