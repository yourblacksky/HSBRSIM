"""
Combat attack-order regression tests.

These tests pin the authoritative Battlegrounds rule that an attack deals
simultaneous bidirectional combat damage: a defender that is killed by the
incoming hit still deals its combat damage back during that attack.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions  # noqa: F401 - register examples
from hsrl.core.actions import Attack
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag
from hsrl.core.game import Game
from hsrl.core.player import Player


class TestCombatAttackOrder(unittest.TestCase):
    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.p2 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players.extend([self.p1, self.p2])

    def _minion(self, atk, health):
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.set_tag(GameTag.BASE_ATK, atk)
        minion.set_tag(GameTag.BASE_HEALTH, health)
        minion.set_tag(GameTag.HEALTH, health)
        return minion

    def test_lethal_defender_still_retaliates_because_damage_is_simultaneous(self):
        attacker = self._minion(5, 1)
        defender = self._minion(1, 5)
        self.game.summon(self.p1, attacker)
        self.game.summon(self.p2, defender)

        self.game.queue_action(Attack(attacker, defender))
        self.game.resolve_queue()

        self.assertTrue(attacker.dead)
        self.assertTrue(defender.dead)

    def test_nonlethal_defender_retaliates(self):
        attacker = self._minion(2, 5)
        defender = self._minion(1, 5)
        self.game.summon(self.p1, attacker)
        self.game.summon(self.p2, defender)

        self.game.queue_action(Attack(attacker, defender))
        self.game.resolve_queue()

        self.assertFalse(attacker.dead)
        self.assertFalse(defender.dead)
        self.assertEqual(attacker.health, 4)
        self.assertEqual(defender.health, 3)

    def test_zero_attack_defender_does_not_retaliate(self):
        attacker = self._minion(2, 5)
        defender = self._minion(0, 5)
        self.game.summon(self.p1, attacker)
        self.game.summon(self.p2, defender)

        self.game.queue_action(Attack(attacker, defender))
        self.game.resolve_queue()

        self.assertFalse(attacker.dead)
        self.assertFalse(defender.dead)
        self.assertEqual(attacker.health, 5)
        self.assertEqual(defender.health, 3)

    def test_divine_shield_target_can_retaliate_if_alive(self):
        attacker = self._minion(5, 5)
        defender = self._minion(1, 1)
        defender.set_tag(GameTag.DIVINE_SHIELD, True)
        defender.set_tag(GameTag.DIVINE_SHIELD_INTACT, True)
        self.game.summon(self.p1, attacker)
        self.game.summon(self.p2, defender)

        self.game.queue_action(Attack(attacker, defender))
        self.game.resolve_queue()

        self.assertFalse(attacker.dead)
        self.assertFalse(defender.dead)
        self.assertEqual(attacker.health, 4)
        self.assertEqual(defender.health, 1)
        self.assertFalse(defender.divine_shield)


if __name__ == "__main__":
    unittest.main()
