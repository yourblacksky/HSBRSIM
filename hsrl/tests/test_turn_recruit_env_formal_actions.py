"""Regression tests for formal recruit actions and deferred decisions."""

import unittest

import hsrl.cards.minions  # noqa: F401
import hsrl.cards.spells  # noqa: F401
import hsrl.cards.trinkets  # noqa: F401
from hsrl.core.actions import TargetedAction
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag, Zone
from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.env.action import ActionMode, FREEZE, REARRANGE, build_action_mask, detect_action_mode
from hsrl.rl_env.envs.turn_recruit_env import TurnRecruitEnv


class TestTurnRecruitFormalActions(unittest.TestCase):
    def setUp(self):
        self.game = Game([], card_db=CARDS, seed=0)
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.entity_id = 1
        self.game.players = [self.player]
        self.game.active_player = self.player
        self.player.gold = 10

    def test_buy_does_not_auto_play_and_play_uses_engine(self):
        existing = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, existing)
        offered = self.game.create_minion("EXAMPLE_VANILLA")
        offered.controller = self.player
        offered.zone = Zone.TAVERN
        offered.set_tag(GameTag.COST, 3)
        self.player.tavern.append(offered)
        env = TurnRecruitEnv(self.game, 0)
        env.reset()

        _state, _reward, done = env.step_atomic(0)
        self.assertFalse(done)
        self.assertEqual(self.player.hand, [offered])
        self.assertEqual(self.player.board, [existing], "buy must not move hand directly to board")

        env.step_atomic(14, position=0)
        self.assertEqual(self.player.hand, [])
        self.assertEqual(self.player.board, [offered, existing])
        self.assertEqual(offered.zone, Zone.PLAY)

    def test_target_mode_exposes_and_resolves_candidates(self):
        target = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, target)
        selected = []
        action = TargetedAction(lambda: [target], lambda chosen: selected.append(chosen))
        self.game.queue_action(action, source=target)
        self.game.resolve_queue()

        mode = detect_action_mode(self.game, self.player)
        self.assertEqual(mode, ActionMode.TARGET_SELECT)
        mask = build_action_mask(self.game, self.player, mode=mode)
        self.assertTrue(mask[0])

        env = TurnRecruitEnv(self.game, 0)
        env.reset()
        env.step_atomic(0)
        self.assertEqual(selected, [target])
        self.assertFalse(self.game.has_pending_target())

    def test_spell_and_trinket_use_formal_engine_paths(self):
        spell = self.game.create_spell("EXAMPLE_TAVERN_SPELL")
        spell.controller = self.player
        spell.zone = Zone.HAND
        self.player.hand.append(spell)
        env = TurnRecruitEnv(self.game, 0)
        env.reset()
        env.step_atomic(14)
        self.assertNotIn(spell, self.player.hand)
        self.assertEqual(
            self.player.get_tag(GameTag.TAVERN_SPELLS_CAST_THIS_TURN, 0), 1,
        )

        self.player._pending_trinket_offers = ["BG35_MagicItem_840"]
        self.player.gold = 10
        _state, _reward, done = env.step_atomic(0)
        self.assertFalse(done)
        self.assertEqual(len(self.player.trinkets), 1)
        self.assertEqual(self.player._pending_trinket_offers, [])

    def test_full_forty_normal_actions_are_allowed(self):
        offered = self.game.create_minion("EXAMPLE_VANILLA")
        self.player.tavern.append(offered)
        env = TurnRecruitEnv(self.game, 0)
        env.reset()
        for index in range(40):
            _state, _reward, done = env.step_atomic(FREEZE)
            self.assertEqual(done, index == 39)
        self.assertEqual(env._actions_taken, 40)

    def test_exact_board_order_is_applied_as_a_normal_action(self):
        minions = [self.game.create_minion("EXAMPLE_VANILLA") for _ in range(3)]
        for minion in minions:
            self.game.summon(self.player, minion)
        env = TurnRecruitEnv(self.game, 0)
        env.reset()
        env.step_atomic(REARRANGE, board_order=[2, 0, 1])
        self.assertEqual(self.player.board, [minions[2], minions[0], minions[1]])
        self.assertEqual(env._actions_taken, 1)

    def test_stale_mask_action_does_not_consume_action_allowance(self):
        env = TurnRecruitEnv(self.game, 0)
        env.reset()
        _state, _reward, done = env.step_atomic(0)  # no tavern entity to buy
        self.assertTrue(done)
        self.assertEqual(env._actions_taken, 0)


if __name__ == "__main__":
    unittest.main()
