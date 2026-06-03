"""Tests for the GameLogger system."""

import io
import unittest

import hsrl.cards.minions  # triggers registration
from hsrl.core.actions import Buff, Destroy, Hit, Summon
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag, Race
from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.utils.logger import GameLogger, _fmt_minion, _fmt_player, _action_desc


class TestEntityFormatting(unittest.TestCase):
    """Low-level entity formatting helpers."""

    def setUp(self):
        self.game = Game([])
        self.game.card_db = CARDS

    def test_fmt_minion_vanilla(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        result = _fmt_minion(m)
        self.assertIn("Vanilla", result)
        self.assertIn("2/3", result)
        self.assertIn("T1", result)
        self.assertIn("(Beast)", result)

    def test_fmt_minion_with_keywords(self):
        m = self.game.create_minion("EXAMPLE_TAUNT")
        result = _fmt_minion(m)
        self.assertIn("Taunt", result)

    def test_fmt_minion_golden(self):
        m = self.game.create_minion("EXAMPLE_GOLDEN")
        result = _fmt_minion(m)
        self.assertIn("★", result)

    def test_fmt_player(self):
        player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        player.health = 30
        player.set_tag(GameTag.GOLD, 5)
        player.set_tag(GameTag.TAVERN_TIER, 2)
        result = _fmt_player(player)
        self.assertIn("HP=30", result)
        self.assertIn("Gold=5", result)
        self.assertIn("Tier=2", result)


class TestGameLoggerBasic(unittest.TestCase):
    """Logger creation, attach/detach, basic output."""

    def setUp(self):
        self.game = Game([])
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.player]
        self.output = io.StringIO()
        self.logger = GameLogger(self.game, verbosity=2, output=self.output)

    def test_logger_creation(self):
        self.assertEqual(self.logger.verbosity, 2)
        self.assertFalse(self.logger._attached)

    def test_attach_detach(self):
        original_queue = self.game.queue_action
        self.logger.attach()
        self.assertTrue(self.logger._attached)
        # After attach, queue_action is wrapped (not the original bound method)
        self.assertIsNot(self.game.queue_action.__func__,
                         original_queue.__func__)

        self.logger.detach()
        self.assertFalse(self.logger._attached)
        # After detach, the original method is restored
        self.assertIs(self.game.queue_action.__func__,
                      original_queue.__func__)

    def test_logs_action(self):
        self.logger.attach()
        m = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, m)
        self.game.queue_action(Buff(m, atk=2, health=1))
        self.game.resolve_queue()
        self.logger.detach()

        output = self.output.getvalue()
        self.assertIn("Buff", output)
        self.assertIn("atk=+2", output)
        self.assertIn("health=+1", output)

    def test_logs_attack(self):
        self.logger.attach()
        attacker = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, attacker)
        defender = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, defender)

        self.game.queue_action(Hit(defender, 2, attacker))
        self.game.resolve_queue()
        self.logger.detach()

        output = self.output.getvalue()
        self.assertIn("Hit", output)

    def test_snapshot(self):
        m1 = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, m1)
        m2 = self.game.create_minion("EXAMPLE_TAUNT")
        self.game.summon(self.player, m2)

        self.logger.snapshot("Test Snapshot")
        output = self.output.getvalue()

        self.assertIn("Test Snapshot", output)
        self.assertIn("Player", output)
        self.assertIn("Vanilla", output)
        self.assertIn("Taunt", output)
        self.assertIn("Board (2/7)", output)

    def test_snapshot_includes_hand(self):
        token = self.game.create_minion("BLOOD_GEM")
        token.controller = self.player
        token.zone = 2  # HAND
        self.player.hand.append(token)

        self.logger.snapshot()
        output = self.output.getvalue()

        self.assertIn("Hand (1)", output)
        self.assertIn("Blood Gem", output)

    def test_snapshot_includes_auras(self):
        from hsrl.core.actions import ApplyGlobalAura
        self.game.queue_action(ApplyGlobalAura(self.player, atk=2, health=0))
        self.game.resolve_queue()

        self.logger.snapshot()
        output = self.output.getvalue()

        self.assertIn("Auras", output)
        self.assertIn("+2/+0", output)

    def test_snapshot_includes_blood_gem_bonus(self):
        self.player.set_tag(GameTag.BLOOD_GEM_BONUS_ATK, 3)
        self.player.set_tag(GameTag.BLOOD_GEM_BONUS_HEALTH, 2)

        self.logger.snapshot()
        output = self.output.getvalue()

        self.assertIn("Blood Gem Bonus", output)
        self.assertIn("+3/+2", output)

    def test_snapshot_includes_scaling_counters(self):
        self.player.set_tag(GameTag.MRRGLTON_COUNT, 3)
        self.player.set_tag(GameTag.PLAGUERUNNER_SCALE, 6)

        self.logger.snapshot()
        output = self.output.getvalue()

        self.assertIn("Mrrglton Count: 3", output)
        self.assertIn("Plaguerunner Scale: 6", output)

    def test_verbosity_0_no_action_logs(self):
        """Verbosity 0 should produce no action-level output."""
        quiet_output = io.StringIO()
        quiet_logger = GameLogger(self.game, verbosity=0, output=quiet_output)
        quiet_logger.attach()

        m = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, m)
        self.game.queue_action(Buff(m, atk=1, health=0))
        self.game.resolve_queue()
        quiet_logger.detach()

        output = quiet_output.getvalue()
        self.assertEqual(output, "")  # No action lines at verbosity 0

    def test_verbosity_1_logs_actions_only(self):
        """Verbosity 1 should log actions but not events."""
        v1_output = io.StringIO()
        v1_logger = GameLogger(self.game, verbosity=1, output=v1_output)
        v1_logger.attach()

        m = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, m)
        self.game.queue_action(Buff(m, atk=1, health=0))
        self.game.resolve_queue()
        v1_logger.detach()

        output = v1_output.getvalue()
        self.assertIn("Buff", output)
        self.assertNotIn("⚡", output)  # No event markers

    def test_logger_wrap_convenience(self):
        logger = GameLogger.wrap(self.game, verbosity=1, output=self.output)
        self.assertTrue(logger._attached)
        logger.detach()

    def test_logger_no_double_attach(self):
        self.logger.attach()
        original = self.game.queue_action
        self.logger.attach()  # Should be no-op
        self.assertIs(self.game.queue_action, original)
        self.logger.detach()

    def test_snapshot_multiple_players(self):
        p2 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        p2.set_tag(GameTag.HEALTH, 25)
        self.game.players.append(p2)

        m1 = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, m1)
        m2 = self.game.create_minion("EXAMPLE_TAUNT")
        self.game.summon(p2, m2)

        self.logger.snapshot()
        output = self.output.getvalue()

        # Both players should appear
        self.assertIn("Player 0", output)
        self.assertIn("Player 1", output)


class TestGameLoggerRealScenario(unittest.TestCase):
    """Integration test: logger captures a full combat scenario."""

    def setUp(self):
        self.game = Game([])
        self.game.card_db = CARDS
        self.output = io.StringIO()

        # Two players
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.p2 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.p1, self.p2]

        self.logger = GameLogger(self.game, verbosity=2, output=self.output)
        self.logger.attach()

    def tearDown(self):
        self.logger.detach()

    def test_combat_logging(self):
        """Full combat should produce rich log output."""
        self.game.turn = 1  # Set turn so phase_begin shows "Turn 1"
        attacker = self.game.create_minion("EXAMPLE_VANILLA")  # 2/3 Beast
        self.game.summon(self.p1, attacker)
        defender = self.game.create_minion("EXAMPLE_TAUNT")     # 1/4 Taunt
        self.game.summon(self.p2, defender)

        # Run combat
        self.logger.phase_begin("COMBAT")
        self.game._run_combat(self.p1, self.p2)
        self.logger.phase_end("COMBAT")

        output = self.output.getvalue()
        self.assertIn("Turn 1", output)
        self.assertIn("COMBAT", output)
        self.assertIn("Attack", output)
        self.assertIn("Hit", output)

    @unittest.skip("Card BG19_010 removed in patch 35.6")
    def test_deathrattle_logging(self):
        """Deathrattle chain should be visible in logs."""
        dr_minion = self.game.create_minion("BG19_010")  # Sewer Rat
        self.game.summon(self.p1, dr_minion)

        self.game.queue_action(Destroy(dr_minion))
        self.game.resolve_queue()

        output = self.output.getvalue()
        self.assertIn("Destroy", output)

    def test_blood_gem_logging(self):
        """Blood Gem actions should show details."""
        # Trigger an ImproveBloodGem
        from hsrl.core.actions import ImproveBloodGem
        self.game.queue_action(ImproveBloodGem(self.p1, atk_bonus=1, health_bonus=1))
        self.game.resolve_queue()

        output = self.output.getvalue()
        self.assertIn("ImproveBloodGem", output)
        self.assertIn("atk_bonus=+1", output)


class TestActionDesc(unittest.TestCase):
    """Unit tests for _action_desc helper."""

    def setUp(self):
        self.game = Game([])
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)

    def test_buff_desc(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        desc = _action_desc(Buff(m, atk=3, health=2))
        self.assertIn("atk=+3", desc)
        self.assertIn("health=+2", desc)

    def test_hit_desc(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        desc = _action_desc(Hit(m, 5))
        self.assertIn("amount=5", desc)

    def test_summon_desc(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        desc = _action_desc(Summon(self.player, m))
        self.assertIn("Summon", desc)

    def test_gain_gold_desc(self):
        from hsrl.core.actions import GainGold
        desc = _action_desc(GainGold(self.player, 3))
        self.assertIn("amount=3", desc)
