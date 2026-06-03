"""
Patch 35.4.2 Battlegrounds parity tests for audited minion and spell changes.

Official source: Blizzard 35.4.2 Patch Notes, Battlegrounds Updates,
published 2026-05-19.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions  # noqa: F401 - register pool and tokens
import hsrl.cards.spells  # noqa: F401 - register tavern spells
from hsrl.core.actions import AddToHand, CastTavernSpell, Destroy
from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, Race, Zone
from hsrl.core.game import Game
from hsrl.core.player import Player


class Patch3542TestCase(unittest.TestCase):
    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players.append(self.player)

    def _minion(self, card_id, player=None):
        minion = self.game.create_minion(card_id)
        self.assertIsNotNone(minion, card_id)
        if player is not None:
            self.game.summon(player, minion)
        return minion

    def _vanilla(self, atk=2, health=3, race=Race.BEAST):
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.set_tag(GameTag.BASE_ATK, atk)
        minion.set_tag(GameTag.BASE_HEALTH, health)
        minion.set_tag(GameTag.HEALTH, health)
        minion.set_tag(GameTag.RACE, race)
        return minion

    def _trigger_battlecry(self, source):
        action = source.battlecry
        if isinstance(action, (list, tuple)):
            for item in action:
                self.game.queue_action(item, source=source)
        elif action is not None:
            self.game.queue_action(action, source=source)
        self.game.resolve_queue()

    def _play_spell_action(self, spell_id):
        spell = self.game.create_spell(spell_id)
        spell.controller = self.player
        spell.zone = Zone.HAND
        self.player.hand.append(spell)
        action = spell.on_play
        if isinstance(action, (list, tuple)):
            for item in action:
                self.game.queue_action(item, source=spell)
        elif action is not None:
            self.game.queue_action(action, source=spell)
        self.game.resolve_queue()
        return spell


class TestPatch3542MinionData(Patch3542TestCase):
    EXPECTED = {
        # BG33_371 (P-0UL-TR-0N) — removed in patch 35.6
        # BG33_840 (Stomping Stegodon) — removed in patch 35.6
        "BG35_155": ("Twisted Wrathguard", 8, 8, 6, Race.DEMON, None),
        "BG21_005": ("Famished Felbat", 6, 3, 5, Race.DEMON, None),
        "BG35_340": ("Alert Alarmist", 2, 2, 2, Race.MECH, None),
        "BG32_170": ("Metallic Hunter", 4, 2, 2, Race.MECH, None),
        "BG31_178": ("Marquee Ticker", 3, 7, 4, Race.MECH, None),
        "BG31_175": ("Holo Rover", 4, 4, 4, Race.MECH, None),
        "BG28_741": ("Charging Czarina", 4, 1, 5, Race.MECH, None),
        "BG31_171": ("Moonsteel Juggernaut", 8, 8, 6, Race.MECH, None),
        "BG26_137": ("Bream Counter", 5, 5, 4, Race.MURLOC, None),
        "BG30_122": ("Mrglin' Burglar", 10, 10, 5, Race.MURLOC, None),
        "BGS_030": ("King Bagurgle", 4, 4, 4, Race.MURLOC, None),
        "BG35_701": ("Brazen Buccaneer", 6, 6, 5, Race.PIRATE, None),
        "BG33_823": ("Sky Admiral Rogers", 4, 5, 6, Race.PIRATE, None),
        "BG32_234": ("Dastardly Drust", 5, 4, 6, Race.PIRATE, None),
        "BG32_433": ("Dreaming Thornweaver", 2, 8, 4, Race.QUILBOAR, 3),
        "BG32_324": ("Drustfallen Butcher", 2, 7, 5, Race.UNDEAD, 3),
        "BG28_551": ("Nalaa the Redeemer", 5, 6, 5, Race.NONE, None),
    }

    def test_patch_35_4_2_minion_stats_tiers_and_avenge_targets(self):
        for card_id, (name, atk, health, tier, race, avenge_target) in self.EXPECTED.items():
            with self.subTest(card_id=card_id):
                data = CARDS.get(card_id)
                self.assertIsNotNone(data)
                self.assertEqual(data.name, name)
                self.assertEqual(data.tags.get(GameTag.BASE_ATK), atk)
                self.assertEqual(data.tags.get(GameTag.BASE_HEALTH), health)
                self.assertEqual(data.tech_level, tier)
                self.assertEqual(data.race, race)
                if avenge_target is not None:
                    self.assertEqual(data.tags.get(GameTag.AVENGE_TARGET), avenge_target)


class TestPatch3542MinionScripts(Patch3542TestCase):
    @unittest.skip("Card BG33_840 removed in patch 35.6")
    def test_stomping_stegodon_rally_gives_other_beasts_plus_3_attack(self):
        stegodon = self._minion("BG33_840", self.player)
        beast = self._vanilla(atk=2, health=3, race=Race.BEAST)
        self.game.summon(self.player, beast)

        action = stegodon.rally
        for item in action:
            self.game.queue_action(item, source=stegodon)
        self.game.resolve_queue()

        self.assertEqual(beast.atk, 5)
        self.assertTrue(beast.has_tag(GameTag.RALLY))

    def test_king_bagurgle_battlecry_gives_other_murlocs_plus_4_plus_4(self):
        king = self._minion("BGS_030", self.player)
        board_murloc = self._vanilla(atk=1, health=1, race=Race.MURLOC)
        hand_murloc = self._vanilla(atk=1, health=1, race=Race.MURLOC)
        hand_murloc.controller = self.player
        hand_murloc.zone = Zone.HAND
        self.game.summon(self.player, board_murloc)
        self.player.hand.append(hand_murloc)

        self._trigger_battlecry(king)

        self.assertEqual(board_murloc.atk, 5)
        self.assertEqual(board_murloc.max_health, 5)
        self.assertEqual(hand_murloc.atk, 5)
        self.assertEqual(hand_murloc.max_health, 5)

    def test_charging_czarina_spell_cast_gives_divine_shield_minions_plus_4_attack(self):
        czarina = self._minion("BG28_741", self.player)
        shielded = self._vanilla(atk=1, health=3, race=Race.MECH)
        shielded.set_tag(GameTag.DIVINE_SHIELD, True)
        self.game.summon(self.player, shielded)

        self.game.queue_action(CastTavernSpell(self.player), source=czarina)
        self.game.resolve_queue()

        self.assertEqual(czarina.atk, 8)
        self.assertEqual(shielded.atk, 5)

    def test_nalaa_spell_cast_gives_one_friendly_minion_of_each_type_plus_4_plus_3(self):
        nalaa = self._minion("BG28_551", self.player)
        murloc = self._vanilla(atk=1, health=1, race=Race.MURLOC)
        beast = self._vanilla(atk=2, health=2, race=Race.BEAST)
        self.game.summon(self.player, murloc)
        self.game.summon(self.player, beast)

        self.game.queue_action(CastTavernSpell(self.player), source=nalaa)
        self.game.resolve_queue()

        self.assertEqual(murloc.atk, 5)
        self.assertEqual(murloc.max_health, 4)
        self.assertEqual(beast.atk, 6)
        self.assertEqual(beast.max_health, 5)

    def test_bream_counter_gains_plus_5_plus_5_after_you_play_murloc(self):
        self.game.queue_action(AddToHand(self.player, "BG26_137"))
        self.game.resolve_queue()
        bream = self.player.hand[0]
        played = self._vanilla(atk=1, health=1, race=Race.MURLOC)

        self.game.summon(self.player, played)
        self.game.resolve_queue()

        self.assertEqual(bream.atk, 10)
        self.assertEqual(bream.max_health, 10)

    def test_mrglin_burglar_gives_board_and_hand_minions_plus_5_plus_5(self):
        burglar = self._minion("BG30_122", self.player)
        hand_target = self._vanilla(atk=1, health=1, race=Race.BEAST)
        hand_target.controller = self.player
        hand_target.zone = Zone.HAND
        self.player.hand.append(hand_target)
        played = self._vanilla(atk=1, health=1, race=Race.MURLOC)

        self.game.broadcast("MINION_PLAYED", played, self.player)
        self.game.resolve_queue()

        self.assertEqual(burglar.atk, 15)
        self.assertEqual(burglar.max_health, 15)
        self.assertEqual(hand_target.atk, 6)
        self.assertEqual(hand_target.max_health, 6)

    def test_moonsteel_juggernaut_first_end_of_turn_gets_two_6_6_satellites(self):
        moonsteel = self._minion("BG31_171", self.player)

        action = moonsteel.end_of_turn
        for item in action:
            self.game.queue_action(item, source=moonsteel)
        self.game.resolve_queue()

        satellites = [card for card in self.player.hand
                      if card.get_tag(GameTag.CARD_ID) == "BG31_171t"]
        self.assertEqual(len(satellites), 2)
        for satellite in satellites:
            self.assertEqual(satellite.atk, 6)
            self.assertEqual(satellite.max_health, 6)
            self.assertTrue(satellite.magnetic)

    def test_sky_admiral_rogers_triggers_after_spending_9_gold(self):
        rogers = self._minion("BG33_823", self.player)

        with patch.object(self.game.rng, "choice", return_value="BG33_811"):
            self.game.broadcast("GOLD_SPENT", self.player, 8)
            self.game.resolve_queue()
            self.assertEqual(len(self.player.hand), 0)
            self.game.broadcast("GOLD_SPENT", self.player, 1)
            self.game.resolve_queue()

        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].get_tag(GameTag.CARD_ID), "BG33_811")

    def test_dastardly_drust_get_pirate_buffs_minions_and_golden_minions(self):
        drust = self._minion("BG32_234", self.player)
        golden = self._vanilla(atk=1, health=1, race=Race.BEAST)
        golden.set_tag(GameTag.GOLDEN, True)
        self.game.summon(self.player, golden)
        pirate = self._vanilla(atk=1, health=1, race=Race.PIRATE)
        pirate.controller = self.player

        self.game.broadcast("ADD_TO_HAND", self.player, pirate)
        self.game.resolve_queue()

        self.assertEqual(drust.atk, 7)
        self.assertEqual(drust.max_health, 6)
        self.assertEqual(golden.atk, 7)
        self.assertEqual(golden.max_health, 7)

    def test_dreaming_thornweaver_avenge_improves_blood_gem_health(self):
        thornweaver = self._minion("BG32_433", self.player)

        for _ in range(3):
            victim = self._vanilla(atk=1, health=1, race=Race.BEAST)
            self.game.summon(self.player, victim)
            self.game.queue_action(Destroy(victim))
            self.game.resolve_queue()

        self.assertEqual(self.player.get_tag(GameTag.BLOOD_GEM_BONUS_HEALTH, 0), 1)
        self.assertEqual(self.player.get_tag(GameTag.BLOOD_GEM_BONUS_ATK, 0), 0)


class TestPatch3542SpellScripts(Patch3542TestCase):
    def test_healthy_bounty_gives_four_friendly_minions_plus_4_health_only(self):
        minions = [self._vanilla(atk=1, health=1) for _ in range(5)]
        for minion in minions:
            self.game.summon(self.player, minion)

        with patch.object(self.game.rng, "sample", return_value=minions[:4]):
            self._play_spell_action("BG33_811")

        for minion in minions[:4]:
            self.assertEqual(minion.atk, 1)
            self.assertEqual(minion.max_health, 5)
        self.assertEqual(minions[4].max_health, 1)

    def test_hostile_bounty_gives_four_friendly_minions_plus_4_attack_only(self):
        minions = [self._vanilla(atk=1, health=1) for _ in range(5)]
        for minion in minions:
            self.game.summon(self.player, minion)

        with patch.object(self.game.rng, "sample", return_value=minions[:4]):
            self._play_spell_action("BG33_812")

        for minion in minions[:4]:
            self.assertEqual(minion.atk, 5)
            self.assertEqual(minion.max_health, 1)
        self.assertEqual(minions[4].atk, 1)

    def test_queens_command_gives_all_minions_plus_2_plus_2_and_naga_repeat(self):
        naga = self._vanilla(atk=1, health=1, race=Race.NAGA)
        beast = self._vanilla(atk=1, health=1, race=Race.BEAST)
        self.game.summon(self.player, naga)
        self.game.summon(self.player, beast)

        self._play_spell_action("BG35_922")

        self.assertEqual(naga.atk, 5)
        self.assertEqual(naga.max_health, 5)
        self.assertEqual(beast.atk, 3)
        self.assertEqual(beast.max_health, 3)


if __name__ == "__main__":
    unittest.main()
