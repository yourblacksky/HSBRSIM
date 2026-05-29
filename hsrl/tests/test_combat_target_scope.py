"""
Combat target-scope regression tests.

Immediate attacks are combat effects and must only target the current combat
opponent. In an 8-player lobby, other players' boards may still exist while one
pair is resolving; those boards must not be candidates.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions  # noqa: F401 - register examples
from hsrl.core.actions import AttackImmediately
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag, Step
from hsrl.core.game import Game
from hsrl.core.player import Player


class TestCombatTargetScope(unittest.TestCase):
    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.attacker_player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.third_player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.current_opponent = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players.extend([
            self.attacker_player,
            self.third_player,
            self.current_opponent,
        ])
        self.game._current_combat_opponents = {
            self.attacker_player: self.current_opponent,
            self.current_opponent: self.attacker_player,
        }

    def _minion(self, atk, health):
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.set_tag(GameTag.BASE_ATK, atk)
        minion.set_tag(GameTag.BASE_HEALTH, health)
        minion.set_tag(GameTag.HEALTH, health)
        return minion

    def test_attack_immediately_targets_current_opponent_only(self):
        attacker = self._minion(3, 10)
        third_target = self._minion(0, 10)
        current_target = self._minion(0, 10)
        self.game.summon(self.attacker_player, attacker)
        self.game.summon(self.third_player, third_target)
        self.game.summon(self.current_opponent, current_target)
        self.game.step = Step.COMBAT

        self.game.queue_action(AttackImmediately(attacker))
        self.game.resolve_queue()

        self.assertEqual(current_target.health, 7)
        self.assertEqual(third_target.health, 10)

    def test_attack_immediately_respects_taunt_within_current_combat(self):
        attacker = self._minion(3, 10)
        third_taunt = self._minion(0, 10)
        current_taunt = self._minion(0, 10)
        current_non_taunt = self._minion(0, 10)
        third_taunt.set_tag(GameTag.TAUNT, True)
        current_taunt.set_tag(GameTag.TAUNT, True)

        self.game.summon(self.attacker_player, attacker)
        self.game.summon(self.third_player, third_taunt)
        self.game.summon(self.current_opponent, current_non_taunt)
        self.game.summon(self.current_opponent, current_taunt)
        self.game.step = Step.COMBAT

        self.game.queue_action(AttackImmediately(attacker))
        self.game.resolve_queue()

        self.assertEqual(current_taunt.health, 7)
        self.assertEqual(current_non_taunt.health, 10)
        self.assertEqual(third_taunt.health, 10)


if __name__ == "__main__":
    unittest.main()
