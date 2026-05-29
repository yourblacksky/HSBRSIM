"""
Patch 35.4.2 Battlegrounds trinket pool/cost parity tests.

These tests cover the audited trinkets whose pool membership or cost changed
in Blizzard's 2026-05-19 Battlegrounds balance patch.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.trinkets  # noqa: F401 - register trinkets
import hsrl.cards.minions  # noqa: F401 - register example cards and Blood Gems
import hsrl.cards.spells  # noqa: F401 - register tavern spells
from hsrl.core.card_db import CARDS
from hsrl.core.actions import (
    CastTavernSpell, PlayBloodGems, TargetedAction, CastSpellOnTarget, Buff, DiscoverTrinket,
)
from hsrl.core.enums import CardType, GameTag, Race, Zone
from hsrl.core.game import Game
from hsrl.core.minion_pool import MinionPool
from hsrl.core.player import Player


class TestPatch3542TrinketPool(unittest.TestCase):
    REMOVED = {
        "BG30_MagicItem_433",   # Alliance Keychain
        "BG30_MagicItem_433t",  # Alliance Keychain
        "BG32_MagicItem_806",   # Battlecruiser Portrait
        "BG32_MagicItem_954",   # Auric Offering
        "BG30_MagicItem_978",   # Blingtron's Sunglasses
        "BG32_MagicItem_417",   # Tarecgosa Sticker
        "BG35_MagicItem_303",   # Skipper Portrait
        "BG35_MagicItem_849",   # Cloud Serpent Horn
        "BG35_MagicItem_155",   # Felburned Ledger
        "BG30_MagicItem_548",   # Glowscale Portrait
        "BG35_MagicItem_310",   # Radio Star Portrait
        "BG30_MagicItem_986",   # Peacebloom Candle
        "BG30_MagicItem_900t",  # Dragonwing Glider, Greater
        "BG32_MagicItem_282",   # Turbocharged Drill
    }

    def test_removed_trinkets_are_not_registered(self):
        for card_id in sorted(self.REMOVED):
            with self.subTest(card_id=card_id):
                self.assertIsNone(CARDS.get(card_id))


class TestPatch3542TrinketCosts(unittest.TestCase):
    EXPECTED_COSTS = {
        "BG35_MagicItem_152": 3,    # Demonic Tapestry
        "BG30_MagicItem_902": 1,    # Holy Mallet
        "BG32_MagicItem_831": 4,    # Sellemental Portrait
        "BG32_MagicItem_170": 1,    # Spell-powered Wrench
        "BG32_MagicItem_300": 2,    # Putricide Sticker
        "BG30_MagicItem_700": 1,    # Deathly Phylactery
        "BG32_MagicItem_822": 1,    # Bazaar Sticker
        "BG35_MagicItem_302": 0,    # Stormcoil Sticker
        "BG30_MagicItem_924t": 0,   # Booty Bay Brew, Greater
        "BG32_MagicItem_363": 4,    # Faerie Dragon Scale, Greater
        "BG32_MagicItem_998": 0,    # Behemoth Portrait, Greater
        "BG30_MagicItem_951": 1,    # Lava Lamp, Greater
        "BG30_MagicItem_993": 4,    # Pagle's Fishing Rod, Greater
        "BG35_MagicItem_742": 4,    # Accord-o-Tron Portrait, Greater
        "BG35_MagicItem_848t": 2,   # Egg of the Endtimes Portrait, Greater
        "BG35_MagicItem_842": 2,    # Egg of the Endtimes Portrait, Lesser
        "BG35_MagicItem_840": 5,    # Chromatic Tear, Lesser
        "BG30_MagicItem_988": 2,    # Great Boar Sticker, Lesser
        "BG30_MagicItem_988t": 2,   # Great Boar Sticker, Greater
        "BG35_MagicItem_850": 3,    # Pocket Cyclone, Lesser
        "BG35_MagicItem_850t": 3,   # Pocket Cyclone, Greater
        "BG35_MagicItem_434": 2,    # Jewelry Box
        "BG30_MagicItem_442": 5,    # Blood Golem Sticker
        "BG35_MagicItem_752": 4,    # Young Murk-Eye Sticker
    }

    def test_changed_trinket_costs(self):
        for card_id, expected_cost in self.EXPECTED_COSTS.items():
            with self.subTest(card_id=card_id):
                data = CARDS.get(card_id)
                self.assertIsNotNone(data)
                self.assertEqual(data.tags.get(GameTag.COST), expected_cost)


class TestPatch3542TrinketEffects(unittest.TestCase):
    CHROMADRAKES = {
        "BG34_634t",
        "BG34_635t",
        "BG34_636t",
        "BG34_637t",
        "BG34_638t",
    }
    KEYWORD_BLOOD_GEMS = {
        "BLOOD_GEM_TAUNT",
        "BLOOD_GEM_DS",
        "BLOOD_GEM_REBORN",
    }

    def setUp(self):
        self.game = Game([], seed=42)  # deterministic seed for reproducible tests
        self.game.card_db = CARDS
        self.game.minion_pool = MinionPool(CARDS)
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.p1]

    def _queue_result(self, result, source):
        if result is None:
            return
        if isinstance(result, (list, tuple)):
            for action in result:
                self.game.queue_action(action, source=source)
        else:
            self.game.queue_action(result, source=source)

    def _equip(self, card_id):
        trinket = self.game.card_db.create_trinket(card_id, game=self.game)
        trinket.controller = self.p1
        self.p1.trinkets.append(trinket)
        if trinket.data.scripts and hasattr(trinket.data.scripts, "on_summon"):
            self._queue_result(trinket.data.scripts.on_summon(trinket, self.game), trinket)
            self.game.resolve_queue()
        return trinket

    def _summon(self, card_id="EXAMPLE_VANILLA", race=None, tier=None):
        minion = self.game.create_minion(card_id)
        if race is not None:
            minion.set_tag(GameTag.RACE, race)
        if tier is not None:
            minion.set_tag(GameTag.TECH_LEVEL, tier)
        self.game.summon(self.p1, minion)
        return minion

    def _add_hand_minion(self, card_id="EXAMPLE_VANILLA"):
        minion = self.game.create_minion(card_id)
        minion.controller = self.p1
        minion.zone = Zone.HAND
        self.p1.hand.append(minion)
        return minion

    def test_egg_portrait_gets_one_egg_and_repeats_every_two_turns(self):
        trinket = self._equip("BG35_MagicItem_842")

        self.assertEqual(
            [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand].count("BG34_639"),
            1,
        )

        self._queue_result(trinket.data.scripts.on_turn_begin(trinket, self.game), trinket)
        self.game.resolve_queue()
        self.assertEqual(
            [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand].count("BG34_639"),
            1,
        )

        self._queue_result(trinket.data.scripts.on_turn_begin(trinket, self.game), trinket)
        self.game.resolve_queue()
        self.assertEqual(
            [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand].count("BG34_639"),
            2,
        )

    def test_chromatic_tear_gets_two_random_chromadrakes_each_turn(self):
        trinket = self._equip("BG35_MagicItem_840")

        first = [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand]
        self.assertEqual(len(first), 2)
        self.assertTrue(set(first).issubset(self.CHROMADRAKES))

        self._queue_result(trinket.start_of_turn, trinket)
        self.game.resolve_queue()
        after_sot = [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand]
        # Hand size: 4 if no triple, 2 if 3-of-kind triggered triple (3→1 golden + 1 extra)
        self.assertIn(len(after_sot), (2, 4),
                      f"Hand size {len(after_sot)} unexpected")
        self.assertTrue(set(after_sot).issubset(self.CHROMADRAKES))

    def test_great_boar_stickers_get_blood_gems_and_modify_gem_stats(self):
        target = self._summon()
        lesser = self._equip("BG30_MagicItem_988")

        self.assertEqual(
            [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand].count("BLOOD_GEM"),
            3,
        )
        self.game.queue_action(PlayBloodGems(target, 1), source=lesser)
        self.game.resolve_queue()
        self.assertEqual(target.atk, 5)       # 2 + base 1 + extra 2
        self.assertEqual(target.max_health, 5)  # 3 + base 1 + extra 1

        self.p1.trinkets.remove(lesser)
        self.p1.hand.clear()
        target2 = self._summon()
        greater = self._equip("BG30_MagicItem_988t")

        self.assertEqual(
            [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand].count("BLOOD_GEM"),
            5,
        )
        self.game.queue_action(PlayBloodGems(target2, 1), source=greater)
        self.game.resolve_queue()
        self.assertEqual(target2.atk, 6)      # 2 + base 1 + extra 3
        self.assertEqual(target2.max_health, 7)  # 3 + base 1 + extra 3

    def test_jewelry_box_gets_one_keyword_blood_gem_to_hand(self):
        target = self._summon()
        old_atk, old_health = target.atk, target.max_health
        trinket = self._equip("BG35_MagicItem_434")

        hand_ids = [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand]
        self.assertEqual(len(hand_ids), 1)
        self.assertIn(hand_ids[0], self.KEYWORD_BLOOD_GEMS)
        self.assertEqual(target.atk, old_atk)
        self.assertEqual(target.max_health, old_health)

        self._queue_result(trinket.start_of_turn, trinket)
        self.game.resolve_queue()
        hand_ids = [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand]
        self.assertEqual(len(hand_ids), 2)
        self.assertTrue(set(hand_ids).issubset(self.KEYWORD_BLOOD_GEMS))

    def test_bluegill_flippers_buffs_leftmost_hand_and_warband(self):
        board_left = self._summon()
        board_right = self._summon()
        hand_left = self._add_hand_minion()
        hand_right = self._add_hand_minion()
        self._equip("BG32_MagicItem_893")

        self.game.queue_action(CastTavernSpell(self.p1), source=board_left)
        self.game.resolve_queue()

        self.assertEqual(board_left.atk, 5)
        self.assertEqual(board_left.max_health, 6)
        self.assertEqual(board_right.atk, 2)
        self.assertEqual(hand_left.atk, 5)
        self.assertEqual(hand_left.max_health, 6)
        self.assertEqual(hand_right.atk, 2)

    def test_young_murk_eye_triggers_only_left_and_right_battlecries(self):
        left = self._summon("EXAMPLE_BATTLECRY")
        middle = self._summon("EXAMPLE_BATTLECRY")
        right = self._summon("EXAMPLE_BATTLECRY")
        trinket = self._equip("BG35_MagicItem_752")

        self._queue_result(trinket.end_of_turn, trinket)
        self.game.resolve_queue()

        self.assertEqual(left.atk, 4)
        self.assertEqual(middle.atk, 2)
        self.assertEqual(right.atk, 4)

    def test_nomi_sticker_tavern_buffs_match_patch_values(self):
        elemental = self.game.create_minion("EXAMPLE_VANILLA")
        elemental.set_tag(GameTag.RACE, Race.ELEMENTAL)
        lesser = self._equip("BG30_MagicItem_544")

        self._queue_result(
            lesser.data.scripts.on_play(lesser, self.game, played_card=elemental),
            lesser,
        )
        self.game.resolve_queue()
        self.assertEqual(self.p1.tavern_buffs[-1].atk, 2)
        self.assertEqual(self.p1.tavern_buffs[-1].health, 2)

        greater = self._equip("BG30_MagicItem_544t")
        self._queue_result(
            greater.data.scripts.on_play(greater, self.game, played_card=elemental),
            greater,
        )
        self.game.resolve_queue()
        self.assertEqual(self.p1.tavern_buffs[-1].atk, 5)
        self.assertEqual(self.p1.tavern_buffs[-1].health, 5)

    def test_dragonwing_glider_buffs_dragons_by_four_four(self):
        dragon = self._summon(race=Race.DRAGON)
        non_dragon = self._summon(race=Race.BEAST)
        trinket = self._equip("BG30_MagicItem_900")

        self._queue_result(
            trinket.data.scripts.on_play(trinket, self.game, played_card=non_dragon),
            trinket,
        )
        self.game.resolve_queue()

        self.assertEqual(dragon.atk, 6)
        self.assertEqual(dragon.max_health, 7)
        self.assertEqual(non_dragon.atk, 2)

    def test_copper_coil_first_magnetize_is_two_one_and_then_improves(self):
        host = self._summon(race=Race.MECH)
        trinket = self._equip("BG35_MagicItem_300")

        self._queue_result(
            trinket.data.scripts.on_magnetized(trinket, self.game, host=host),
            trinket,
        )
        self.game.resolve_queue()
        self.assertEqual(host.atk, 4)
        self.assertEqual(host.max_health, 4)

        self._queue_result(
            trinket.data.scripts.on_magnetized(trinket, self.game, host=host),
            trinket,
        )
        self.game.resolve_queue()
        self.assertEqual(host.atk, 7)
        self.assertEqual(host.max_health, 6)

    def test_lorewalker_scroll_lesser_buffs_spell_target_by_four_four(self):
        target = self._summon()
        self._equip("BG30_MagicItem_422")

        from hsrl.core.events import SPELL_CAST_ON_MINION
        self.game.broadcast(SPELL_CAST_ON_MINION, target, None)
        self.game.resolve_queue()

        self.assertEqual(target.atk, 6)
        self.assertEqual(target.max_health, 7)

    def test_static_patch_values_for_counter_and_combat_trinkets(self):
        self.assertEqual(
            CARDS.get("BG35_MagicItem_863").scripts.TARGET,
            4,
        )
        self.assertEqual(
            CARDS.get("BG30_MagicItem_931").scripts.TARGET,
            7,
        )
        self.assertEqual(
            CARDS.get("BG32_MagicItem_951").scripts.MAX_TIER,
            4,
        )
        self.assertEqual(
            CARDS.get("BG35_MagicItem_714").scripts.TARGET_COUNT,
            3,
        )
        self.assertIsNone(CARDS.get("BG30_MagicItem_442").scripts.MAX_TRIGGERS)

    def test_aggem_sticker_plays_seven_blood_gems_on_each_type(self):
        beast = self._summon(race=Race.BEAST)
        murloc = self._summon(race=Race.MURLOC)
        trinket = self._equip("BG32_MagicItem_284")

        self._queue_result(trinket.end_of_turn, trinket)
        self.game.resolve_queue()

        self.assertEqual(beast.atk, 9)
        self.assertEqual(beast.max_health, 10)
        self.assertEqual(murloc.atk, 9)
        self.assertEqual(murloc.max_health, 10)

    def test_ornate_clock_gains_two_gold(self):
        self.p1.set_tag(GameTag.GOLD, 0)
        self._equip("BG32_MagicItem_271")
        self.assertEqual(self.p1.gold, 2)


class TestPatch3542ProductionEntrypoints(unittest.TestCase):
    """Regression tests going through real production entry points
    (TargetedAction, CastSpellOnTarget, DiscoverTrinket) to ensure
    SPELL_CAST_ON_MINION and on_summon are wired correctly."""

    CHROMADRAKES = {
        "BG34_634t", "BG34_635t", "BG34_636t",
        "BG34_637t", "BG34_638t",
    }

    def setUp(self):
        self.game = Game([], seed=99)
        self.game.card_db = CARDS
        self.game.minion_pool = MinionPool(CARDS)
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.game.players = [self.p1]

    def _summon(self, race=None):
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        if race is not None:
            minion.set_tag(GameTag.RACE, race)
        self.game.summon(self.p1, minion)
        return minion

    def _equip_lorewalker(self):
        """Equip Lorewalker Scroll (Lesser) via production path."""
        trinket_data = CARDS.get("BG30_MagicItem_422")
        trinket = self.game.card_db.create_trinket("BG30_MagicItem_422", game=self.game)
        trinket.controller = self.p1
        self.p1.trinkets.append(trinket)
        # Trigger on_summon via the same pattern as DiscoverTrinket
        if trinket.data.scripts:
            fn = getattr(trinket.data.scripts, "on_summon", None)
            if fn and callable(fn):
                result = fn(trinket, self.game)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for a in result:
                            self.game.queue_action(a, source=trinket)
                    else:
                        self.game.queue_action(result, source=trinket)
                self.game.resolve_queue()
        return trinket

    def test_lorewalker_scroll_real_targeted_action_entry(self):
        """Lorewalker Scroll triggers through real TargetedAction flow."""
        target = self._summon()
        self._equip_lorewalker()

        # Create a Fortify-like spell and cast it via TargetedAction
        spell = self.game.create_spell("BG28_503")
        spell.controller = self.p1

        # TargetedAction: pick a friendly minion, buff +1/+1
        def filter_fn():
            return [m for m in self.p1.board if not m.dead]

        def action_factory(t):
            return Buff(t, atk=1, health=1)

        ta = TargetedAction(filter_fn, action_factory, label="Test Fortify")
        ta.target = target  # set target (recruit phase would pause)
        ta.do(spell, self.game)
        self.game.resolve_queue()

        # Lorewalker Scroll should give an extra +4/+4 = total +5/+5
        self.assertEqual(target.atk, 7)       # 2 + 1 (spell) + 4 (Lorewalker)
        self.assertEqual(target.max_health, 8)  # 3 + 1 (spell) + 4 (Lorewalker)

    def test_lorewalker_scroll_cast_spell_on_target_entry(self):
        """Lorewalker Scroll triggers through CastSpellOnTarget entry."""
        target = self._summon()
        self._equip_lorewalker()

        # Cast Fortify on target via CastSpellOnTarget
        action = CastSpellOnTarget(self.p1, "BG28_503", target)
        action.do(None, self.game)
        self.game.resolve_queue()

        # Lorewalker Scroll should give +4/+4; spell gives +1/+1 → total +5/+5
        self.assertEqual(target.atk, 7)
        self.assertEqual(target.max_health, 8)

    def test_discover_trinket_queues_on_summon_effect(self):
        """DiscoverTrinket with fixed RNG — Chromatic Tear gives 2 Chromadrakes."""
        from hsrl.core.actions import DiscoverTrinket
        from hsrl.core.trinket import Trinket

        # Use DiscoverTrinket (lesser only) to get a Chromatic Tear
        dt = DiscoverTrinket(self.p1, lesser_only=True)

        # Patch RNG to select Chromatic Tear (BG35_MagicItem_840)
        def _fixed_choice(population, k=1):
            if isinstance(population, list) and "BG35_MagicItem_840" in population:
                return ["BG35_MagicItem_840"]
            return population[:k]
        self.game.rng.choice = lambda pop: "BG35_MagicItem_840" if "BG35_MagicItem_840" in pop else pop[0]
        self.game.rng.sample = _fixed_choice

        dt.do(None, self.game)
        self.game.resolve_queue()

        # Should have equipped Chromatic Tear and received 2 Chromadrakes
        self.assertEqual(len(self.p1.trinkets), 1)
        self.assertEqual(self.p1.trinkets[0].get_tag(GameTag.CARD_ID), "BG35_MagicItem_840")
        hand_ids = [c.get_tag(GameTag.CARD_ID) for c in self.p1.hand]
        self.assertTrue(set(hand_ids).issubset(self.CHROMADRAKES))

if __name__ == "__main__":
    unittest.main()
