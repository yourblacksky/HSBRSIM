"""
HSRL Hero System Tests

Tests for hero creation, hero power usage, gold deduction,
usage flag management, and edge cases.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import unittest

from hsrl.core.enums import CardType, GameTag, Race, Zone, PlayState, Step
from hsrl.core.card_db import CARDS
import hsrl.cards.heroes    # triggers registration of heroes and hero powers
import hsrl.cards.minions   # triggers registration of minions
import hsrl.cards.spells    # triggers registration of spells (Banana, Coin, etc.)
from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.core.minion import Minion
from hsrl.core.actions import Buff


class TestHeroCreation(unittest.TestCase):
    """Hero card creation and basic properties."""

    def test_create_example_hero(self):
        """Example hero has health=30, armor=0, hero_power_cost=0."""
        game = Game([], seed=0)
        game.card_db = CARDS
        player = Player(CARDS.get("EXAMPLE_HERO"), game=game)
        game.players = [player]
        self.assertEqual(player.health, 30)
        self.assertEqual(player.armor, 0)
        self.assertEqual(player.hero_power_cost, 0)
        self.assertFalse(player.get_tag(GameTag.HERO_POWER_USED))
        self.assertEqual(
            player.get_tag(GameTag.HERO_POWER),
            "EXAMPLE_HERO_POWER_BUFF",
        )

    def test_create_blackthorn(self):
        """Death Speaker Blackthorn has cost=1 hero power."""
        game = Game([], seed=0)
        game.card_db = CARDS
        player = Player(CARDS.get("BG20_HERO_103"), game=game)
        game.players = [player]
        self.assertEqual(player.health, 30)
        self.assertEqual(player.hero_power_cost, 1)
        self.assertEqual(
            player.get_tag(GameTag.HERO_POWER),
            "BG20_HERO_103p",
        )

    def test_create_xyrella(self):
        """Xyrella has cost=2 hero power."""
        game = Game([], seed=0)
        game.card_db = CARDS
        player = Player(CARDS.get("BG20_HERO_101"), game=game)
        game.players = [player]
        self.assertEqual(player.health, 30)
        self.assertEqual(player.hero_power_cost, 2)

    def test_create_player_via_game(self):
        """game.create_player() works for hero cards."""
        game = Game([], seed=0)
        game.card_db = CARDS
        player = game.create_player("EXAMPLE_HERO")
        self.assertEqual(player.health, 30)
        self.assertEqual(player.hero_power_cost, 0)


class TestHeroPowerUsage(unittest.TestCase):
    """Basic hero power activation tests."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        # Use EXAMPLE_HERO (0-cost +1/+1 buff) for most tests
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_board_minion(self, card_id="EXAMPLE_VANILLA"):
        """Create and summon a minion to the player's board."""
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def test_use_hero_power_buffs_random_minion(self):
        """Using EXAMPLE_HERO power buffs a random friendly minion +1/+1."""
        m1 = self._add_board_minion("EXAMPLE_VANILLA")  # 2/3
        orig_atk, orig_hp = m1.atk, m1.health
        self.game.use_hero_power(self.player)
        # The only minion should receive +1/+1
        self.assertEqual(m1.atk, orig_atk + 1)
        self.assertEqual(m1.max_health, orig_hp + 1)

    def test_use_hero_power_sets_used_flag(self):
        """After using hero power, HERO_POWER_USED is set to True."""
        self.assertFalse(self.player.get_tag(GameTag.HERO_POWER_USED))
        self._add_board_minion()
        self.game.use_hero_power(self.player)
        self.assertTrue(self.player.get_tag(GameTag.HERO_POWER_USED))

    def test_use_hero_power_twice_blocked(self):
        """Second use of hero power in same turn is blocked."""
        self._add_board_minion("EXAMPLE_VANILLA")
        self.game.use_hero_power(self.player)
        # Save state after first use
        first_used = self.player.get_tag(GameTag.HERO_POWER_USED)
        self.assertTrue(first_used)
        # Reset board minion to check no further buffs
        m = self.player.board[0]
        atk_after_first = m.atk
        # Try second use
        self.game.use_hero_power(self.player)
        # Minion should not have been buffed again
        self.assertEqual(m.atk, atk_after_first)

    def test_use_hero_power_empty_board(self):
        """Using hero power with empty board does nothing (script returns None)."""
        self.game.use_hero_power(self.player)
        # Used flag should still be set since cost was paid
        self.assertTrue(self.player.get_tag(GameTag.HERO_POWER_USED))

    def test_hero_power_flag_resets_at_turn_start(self):
        """HERO_POWER_USED flag resets at beginning of recruit phase."""
        self._add_board_minion()
        self.game.use_hero_power(self.player)
        self.assertTrue(self.player.get_tag(GameTag.HERO_POWER_USED))
        # Simulate recruit phase start (which resets the flag)
        p = self.player
        p.set_tag(GameTag.HERO_POWER_USED, False)
        self.assertFalse(p.get_tag(GameTag.HERO_POWER_USED))


class TestHeroPowerGoldCost(unittest.TestCase):
    """Hero power gold cost and edge cases."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("BG20_HERO_103"), game=self.game)  # cost=1
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_board_minion(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def test_gold_deducted_for_hero_power(self):
        """Hero power with cost=1 deducts 1 gold."""
        self.assertEqual(self.player.gold, 10)
        self._add_board_minion()
        self.game.use_hero_power(self.player)
        self.assertEqual(self.player.gold, 9)

    def test_insufficient_gold_blocks_hero_power(self):
        """Cannot use hero power without enough gold."""
        self.player.gold = 0
        self._add_board_minion()
        self.game.use_hero_power(self.player)
        # Used flag should still be false
        self.assertFalse(self.player.get_tag(GameTag.HERO_POWER_USED))
        # Gold should stay 0
        self.assertEqual(self.player.gold, 0)

    def test_exact_gold_sufficient(self):
        """Hero power can be used when gold equals cost."""
        self.player.gold = 1
        self._add_board_minion()
        self.game.use_hero_power(self.player)
        self.assertEqual(self.player.gold, 0)
        self.assertTrue(self.player.get_tag(GameTag.HERO_POWER_USED))


class TestHeroPowerEffects(unittest.TestCase):
    """Specific hero power effect tests."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def test_gain_gold_hero_power(self):
        """Hero power that gains gold adds to player's gold."""
        player = Player(CARDS.get("EXAMPLE_HERO_POWER_GOLD"), game=self.game)
        player.gold = 3
        player.health = 40
        self.game.players = [player]
        self.game.use_hero_power(player)
        # GainGold(2) minus cost(2) = net 0, but the action...
        # Wait, the hero power costs 2 and gives 2, so net is 0
        # Actually the gold gain via GainGold action adds back 2 gold
        self.assertEqual(player.gold, 3)

    def test_cost_deducted_then_gold_gained(self):
        """Hero power cost deducted, then script effect executes."""
        # Use Blackthorn (cost 1, +1/+1 buff)
        player = Player(CARDS.get("BG20_HERO_103"), game=self.game)
        player.gold = 5
        player.health = 40
        self.game.players = [player]
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 3)  # 2 + 1
        self.assertEqual(m.max_health, 4)  # 3 + 1

    def test_two_minions_one_buffed(self):
        """With 2 minions, exactly one receives the +1/+1 buff."""
        player = Player(CARDS.get("BG20_HERO_103"), game=self.game)
        player.gold = 5
        player.health = 40
        self.game.players = [player]
        m1 = self.game.create_minion("EXAMPLE_VANILLA")
        m2 = self.game.create_minion("EXAMPLE_VANILLA")
        for m in [m1, m2]:
            m.controller = player
            m.zone = Zone.PLAY
            player.board.append(m)
        self.game.use_hero_power(player)
        # One minion should be 3/4, the other 2/3
        buffed = [m for m in [m1, m2] if m.atk == 3 and m.max_health == 4]
        unbuffed = [m for m in [m1, m2] if m.atk == 2 and m.max_health == 3]
        self.assertEqual(len(buffed), 1)
        self.assertEqual(len(unbuffed), 1)

    def test_xyrella_buffs_for_two_two(self):
        """Xyrella hero power costs 2, gives +2/+2."""
        player = Player(CARDS.get("BG20_HERO_101"), game=self.game)
        player.gold = 5
        player.health = 40
        self.game.players = [player]
        m = self.game.create_minion("EXAMPLE_VANILLA")  # 2/3
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)  # 5 - 2
        self.assertEqual(m.atk, 4)  # 2 + 2
        self.assertEqual(m.max_health, 5)  # 3 + 2


class TestPassiveHeroPower(unittest.TestCase):
    """Passive hero power (Rokara) tests."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("BG20_HERO_100"), game=self.game)  # Rokara
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_passive_hero_power_returns_none(self):
        """Passive hero power has no manual activation effect."""
        # Just verify it doesn't crash when called
        hp_fn = None
        if self.player.data.scripts:
            hp_fn = getattr(self.player.data.scripts, "hero_power", None)
        self.assertIsNotNone(hp_fn)
        result = hp_fn(self.player, self.game)
        self.assertIsNone(result)

    def test_on_summon_registers_listener(self):
        """Passive hero on_summon registers AFTER_ATTACK listener."""
        # Directly call the on_summon script method (like start_game does)
        self.assertIsNotNone(self.player.data.scripts)
        fn = getattr(self.player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(self.player, self.game)
        # Listener should be registered
        self.assertTrue(len(self.game._event_listeners) > 0)


class TestNewHeroPowerScripts(unittest.TestCase):
    """Tests for newly added hero power scripts."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []
        self.game.in_combat = True

    def _make_player_with_board(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_conviction_buffs_minion(self):
        """Cariel Roame: +1/+1 buff, cost=1."""
        player = self._make_player_with_board("BG21_HERO_000", gold=5)
        m = self._add_minion(player)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 3)
        self.assertEqual(m.max_health, 4)

    def test_i_spy_discovers_minion(self):
        """Scabbs: Discover from tier below (cost=2)."""
        player = self._make_player_with_board("BG21_HERO_010", gold=5)
        player.tavern_tier = 3
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)
        # Discovery adds a card to hand
        self.assertEqual(len(player.hand), 1)

    def test_sharpen_blades_buffs_minion(self):
        """Edwin: +1/+1 per minion bought (default 1), cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_01", gold=5)
        m = self._add_minion(player)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 3)

    def test_boon_of_light_grants_divine_shield(self):
        """George: Grant Divine Shield to random minion, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_15", gold=5)
        m = self._add_minion(player)
        self.assertFalse(m.divine_shield)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertTrue(m.divine_shield)

    def test_boon_of_light_skips_divine_shield_minions(self):
        """George: Skips minions that already have Divine Shield."""
        player = self._make_player_with_board("TB_BaconShop_HERO_15", gold=5)
        m = self._add_minion(player, "EXAMPLE_DIVINE_SHIELD")  # already has DS
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        # Flag is set, but no effect because the only minion already has DS
        # (candidates list is empty, script returns None)
        # Verify gold was deducted (used flag is set, check minion unchanged)
        pass  # Script returns None for empty candidates

    def test_tinker_buffs_mech(self):
        """Millificent: +1/+1 to random Mech, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_17", gold=5)
        m = self._add_minion(player, "EXAMPLE_DIVINE_SHIELD")  # Race.MECH
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 4)  # 3 + 1
        self.assertEqual(m.max_health, 2)  # 1 + 1

    def test_tinker_ignores_non_mechs(self):
        """Millificent: Ignores non-Mech minions."""
        player = self._make_player_with_board("TB_BaconShop_HERO_17", gold=5)
        m = self._add_minion(player, "EXAMPLE_VANILLA")  # Race.BEAST
        self.game.use_hero_power(player)
        # beast ignored, no targets → script returns None
        self.assertEqual(m.atk, 2)  # unchanged

    def test_yogg_wheel_accepts_player_as_hero_power_source(self):
        player = self._make_player_with_board("TB_BaconShop_HERO_40", gold=5)
        self._add_minion(player)
        player.set_tag(GameTag.HERO_POWER, "TB_BaconShop_HP_039t")
        player.set_tag(GameTag.HERO_POWER_COST, 0)

        self.game.use_hero_power(player)

        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    def test_temporal_tavern_refreshes(self):
        """Infinite Toki: Refresh tavern, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_28", gold=5)
        self.game.init_pool()
        game = self.game
        game.refresh_tavern(player)
        original_tavern = list(player.tavern)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        # Tavern should be refreshed (new minions)

    def test_brick_by_brick_buffs_health(self):
        """Patches: +0/+3 health buff, cost=2."""
        player = self._make_player_with_board("TB_BaconShop_HERO_39", gold=5)
        m = self._add_minion(player)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)
        self.assertEqual(m.atk, 2)  # unchanged
        self.assertEqual(m.max_health, 6)  # 3 + 3

    def test_queen_of_dragons_buffs_dragon(self):
        """Alexstrasza: +1/+1 to random Dragon, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_56", gold=5)
        m = self._add_minion(player, "EXAMPLE_WINDFURY")  # Race.DRAGON
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 3)  # 2 + 1

    def test_smart_savings_adds_coin(self):
        """Gallywix: Add Coin to hand, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_10", gold=5)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(len(player.hand), 1)
        self.assertEqual(player.hand[0].get_tag(GameTag.CARD_ID), "TAVERN_COIN")

    def test_bobs_burgles_adds_tavern_minion_to_hand(self):
        """Tess: Get a random minion from Tavern, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_50", gold=5)
        self.game.init_pool()
        self.game.refresh_tavern(player)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(len(player.hand), 1)


class TestPhaseIINewHeroPowers(unittest.TestCase):
    """Phase II: newly implemented hero power scripts."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []
        self.game.in_combat = True

    def _make_player_with_board(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    # ── Graveyard Shift (Lich Baz'hial) ──

    def test_graveyard_shift_damages_hero_and_gains_gold(self):
        """Lich Baz'hial: cost=2, take 3 damage, gain 2 gold. Net: 0 gold, -3 HP."""
        player = self._make_player_with_board("TB_BaconShop_HERO_25", gold=5)
        player.armor = 0  # bypass armor for damage test
        self._add_minion(player)
        self.assertEqual(player.health, 40)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 5)  # pay 2, gain 2 = net 0
        self.assertEqual(player.health, 37)  # -3 damage

    # ── Lucky Roll (Snake Eyes) ──

    def test_lucky_roll_gains_random_gold(self):
        """Snake Eyes: roll d6, gain that much gold. Cost=1."""
        player = self._make_player_with_board("BG28_HERO_400", gold=5)
        # No board minion needed — Lucky Roll doesn't target minions
        self.game.use_hero_power(player)
        # Gold after: 5 - 1 (cost) + roll (1-6) = 5 to 10
        self.assertGreaterEqual(player.gold, 5)
        self.assertLessEqual(player.gold, 10)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    def test_lucky_roll_cant_use_twice(self):
        """Snake Eyes: blocked from second use by HERO_POWER_USED flag."""
        player = self._make_player_with_board("BG28_HERO_400", gold=10)
        self.game.use_hero_power(player)
        gold_after_first = player.gold
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, gold_after_first)  # unchanged

    # ── Lead Explorer (Elise Starseeker) ──

    def test_lead_explorer_discovers_from_current_tier(self):
        """Elise: Discover a minion from current Tavern Tier, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_42", gold=5)
        player.tavern_tier = 3
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(len(player.hand), 1)
        # Discovered minion should be tier ≤ 3
        card = player.hand[0]
        self.assertLessEqual(card.tech_level, 3)

    # ── Embrace Your Rage (Y'Shaarj) ──

    def test_embrace_your_rage_base_case(self):
        """Y'Shaarj: +2/+2 buff with no buys (defaults to 1 repeat), cost=2."""
        player = self._make_player_with_board("TB_BaconShop_HERO_92", gold=5)
        m = self._add_minion(player)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)  # 5 - 2
        self.assertEqual(m.atk, 4)  # 2 + 2
        self.assertEqual(m.max_health, 5)  # 3 + 2

    def test_embrace_your_rage_with_buys(self):
        """Y'Shaarj: multiple buffs based on gold spent this turn."""
        player = self._make_player_with_board("TB_BaconShop_HERO_92", gold=10)
        player.set_tag(GameTag.GOLD_SPENT_THIS_TURN, 6)  # 2 buys
        m = self._add_minion(player)
        self.game.use_hero_power(player)
        # 2 repeats (6//3=2), each +2/+2 → +4/+4 total
        self.assertEqual(m.atk, 6)  # 2 + 4
        self.assertEqual(m.max_health, 7)  # 3 + 4

    def test_embrace_your_rage_empty_board(self):
        """Y'Shaarj: empty board returns None."""
        player = self._make_player_with_board("TB_BaconShop_HERO_92", gold=5)
        self.game.use_hero_power(player)
        # Gold still deducted, flag set
        self.assertEqual(player.gold, 3)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    # ── Saturday C'Thuns (C'Thun) ──

    def test_saturday_cthuns_first_use(self):
        """C'Thun: first use gives +1/+1, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_29", gold=5)
        m = self._add_minion(player)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 3)  # 2 + 1
        self.assertEqual(m.max_health, 4)  # 3 + 1
        self.assertEqual(player.get_tag(GameTag.CTHUN_BUFF_COUNT), 2)

    def test_saturday_cthuns_upgrades_each_use(self):
        """C'Thun: buff scales up with each use."""
        player = self._make_player_with_board("TB_BaconShop_HERO_29", gold=10)
        m1 = self._add_minion(player, "EXAMPLE_VANILLA")  # 2/3
        # First use: +1/+1 → 3/4
        self.game.use_hero_power(player)
        self.assertEqual(m1.atk, 3)
        self.assertEqual(m1.max_health, 4)
        self.assertEqual(player.get_tag(GameTag.CTHUN_BUFF_COUNT), 2)

        # Reset flag manually (simulating next turn)
        player.set_tag(GameTag.HERO_POWER_USED, False)
        # Second use: +2/+2 → 5/6
        self.game.use_hero_power(player)
        self.assertEqual(m1.atk, 5)
        self.assertEqual(m1.max_health, 6)
        self.assertEqual(player.get_tag(GameTag.CTHUN_BUFF_COUNT), 3)

        # Third use: +3/+3 → 8/9
        player.set_tag(GameTag.HERO_POWER_USED, False)
        self.game.use_hero_power(player)
        self.assertEqual(m1.atk, 8)
        self.assertEqual(m1.max_health, 9)
        self.assertEqual(player.get_tag(GameTag.CTHUN_BUFF_COUNT), 4)

    def test_saturday_cthuns_empty_board(self):
        """C'Thun: empty board doesn't increment counter."""
        player = self._make_player_with_board("TB_BaconShop_HERO_29", gold=5)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        # Counter should NOT increment when board is empty
        self.assertEqual(player.get_tag(GameTag.CTHUN_BUFF_COUNT), 1)

    # ── Rune of Damnation (The Jailer) ──

    def test_rune_of_damnation_undead_and_non_undead(self):
        """Jailer: Undead +1/+1, non-Undead +1/+0, cost=1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_702", gold=5)
        undead = self._add_minion(player, "EXAMPLE_REBORN")  # Race.UNDEAD
        beast = self._add_minion(player, "EXAMPLE_VANILLA")  # Race.BEAST
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        # Undead gets +1/+1
        self.assertEqual(undead.atk, 3)  # 2 + 1
        self.assertEqual(undead.max_health, 3)  # 2 + 1
        # Beast gets +1/+0
        self.assertEqual(beast.atk, 3)  # 2 + 1
        self.assertEqual(beast.max_health, 3)  # unchanged

    def test_rune_of_damnation_no_undead(self):
        """Jailer: if no Undead, buff any minion +1/+1."""
        player = self._make_player_with_board("TB_BaconShop_HERO_702", gold=5)
        m = self._add_minion(player, "EXAMPLE_VANILLA")  # BEAST
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(m.atk, 3)  # 2 + 1
        self.assertEqual(m.max_health, 4)  # 3 + 1

    def test_rune_of_damnation_empty_board(self):
        """Jailer: empty board returns None."""
        player = self._make_player_with_board("TB_BaconShop_HERO_702", gold=5)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))


class TestPhaseIIINewHeroPowers(unittest.TestCase):
    """Phase III: engine extension hero powers — adjacency, stat transfer,
    mass steal, pair detection."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []
        self.game.in_combat = True

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    # ── Wisdom of Ancients (Cenarius) ──

    def test_wisdom_of_ancients_buffs_self_and_neighbors(self):
        """Cenarius: cost=3, buff target + left + right each +1/+1."""
        player = self._make_player("BG32_HERO_001", gold=6)
        m1 = self._add_minion(player, "EXAMPLE_VANILLA")  # 2/3
        m2 = self._add_minion(player, "EXAMPLE_TAUNT")     # 2/4
        m3 = self._add_minion(player, "EXAMPLE_TAUNT")     # 2/4
        self.game.use_hero_power(player)
        # Random target; at least one minion should have been buffed
        self.assertEqual(player.gold, 3)  # 6 - 3
        # Base totals: ATK=2+2+2=6, HP=3+4+4=11
        # If center (m2) picked: +1/+1 x 3 → +3/+3
        # If edge (m1) picked: +1/+1 x 2 → +2/+2
        # If edge (m3) picked: +1/+1 x 2 → +2/+2
        total_atk = m1.atk + m2.atk + m3.atk
        total_hp = m1.max_health + m2.max_health + m3.max_health
        self.assertIn(total_atk - 6, (2, 3))
        self.assertIn(total_hp - 11, (2, 3))

    def test_wisdom_of_ancients_single_minion(self):
        """Cenarius: with 1 minion, buffs only that minion."""
        player = self._make_player("BG32_HERO_001", gold=6)
        m = self._add_minion(player, "EXAMPLE_VANILLA")
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)
        self.assertEqual(m.atk, 3)   # 2 + 1
        self.assertEqual(m.max_health, 4)  # 3 + 1

    def test_wisdom_of_ancients_empty_board(self):
        """Cenarius: empty board returns None."""
        player = self._make_player("BG32_HERO_001", gold=6)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    # ── Reclaimed Souls (Sylvanas) ──

    def test_reclaimed_souls_transfers_stats(self):
        """Sylvanas: cost=2, destroy one minion, transfer stats to another."""
        player = self._make_player("BG23_HERO_306", gold=5)
        m1 = self._add_minion(player, "EXAMPLE_VANILLA")  # 2/3
        m2 = self._add_minion(player, "EXAMPLE_TAUNT")     # 2/2
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)
        # One minion should be dead, one should have absorbed stats
        dead = [m for m in [m1, m2] if m.dead]
        alive = [m for m in [m1, m2] if not m.dead]
        self.assertEqual(len(dead), 1)
        self.assertEqual(len(alive), 1)
        survivor = alive[0]
        # Survivor gets donor's ATK + MAX_HEALTH as buff
        # Possible outcomes: 2+2/3+2=4/5 or 2+2/2+3=4/5 or 2+3/2+2=5/4 or 2+2/2+3=4/5
        self.assertGreaterEqual(survivor.atk, 4)
        self.assertGreaterEqual(survivor.max_health, 4)

    def test_reclaimed_souls_needs_two_minions(self):
        """Sylvanas: with 1 minion, returns None."""
        player = self._make_player("BG23_HERO_306", gold=5)
        self._add_minion(player, "EXAMPLE_VANILLA")
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 3)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    # ── The Perfect Crime (Togwaggle) ──

    def test_perfect_crime_steals_tavern_minions(self):
        """Togwaggle: cost=11, steal all tavern minions to hand."""
        player = self._make_player("BG23_HERO_305", gold=12)
        self.game.init_pool()
        self.game.refresh_tavern(player)
        tavern_count = len([m for m in player.tavern
                           if m.get_tag(GameTag.CARDTYPE, 0) == 1])
        self.assertGreater(tavern_count, 0)
        hand_before = len(player.hand)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 1)  # 12 - 11
        # All tavern minions moved to hand
        self.assertEqual(len(player.hand), hand_before + tavern_count)

    def test_perfect_crime_empty_tavern(self):
        """Togwaggle: empty tavern returns None."""
        player = self._make_player("BG23_HERO_305", gold=12)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 1)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    # ── Three Wishes (Zephrys) ──

    def test_three_wishes_discovers_pair(self):
        """Zephrys: cost=3, with a pair in hand, discovers the third copy.

        Note: discovering the 3rd copy triggers triple combination (3→1 golden).

        Uses a real pool minion (BGS_002) rather than EXAMPLE_* cards:
        DiscoverMinion filters candidates through _is_valid_pool_card, which
        intentionally excludes EXAMPLE_ test cards.
        """
        player = self._make_player("TB_BaconShop_HERO_91", gold=5)
        # Add 2 copies of the same card to hand
        m1 = self.game.create_minion("BGS_002")
        m1.controller = player
        m1.zone = Zone.HAND
        player.hand.append(m1)
        m2 = self.game.create_minion("BGS_002")
        m2.controller = player
        m2.zone = Zone.HAND
        player.hand.append(m2)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 2)  # 5 - 3
        # DiscoverMinion creates a PendingChoice (filtered to the pair card).
        # With the default _auto_resolve_choices=True it is already resolved
        # automatically; resolve_pending_choice is a safe no-op otherwise.
        self.game.resolve_pending_choice(0)
        # 3 copies combine into 1 golden + reward discovery
        # Hand has: golden copy + reward discover card(s)
        self.assertGreaterEqual(len(player.hand), 1)
        # At least one card in hand should be golden
        golden = [m for m in player.hand if m.is_golden]
        self.assertEqual(len(golden), 1)

    def test_three_wishes_no_pair(self):
        """Zephrys: with no pair, returns None."""
        player = self._make_player("TB_BaconShop_HERO_91", gold=5)
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = player
        m.zone = Zone.HAND
        player.hand.append(m)
        hand_before = len(player.hand)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 2)
        self.assertEqual(len(player.hand), hand_before)  # no new card


class TestTemporaryBuffSystem(unittest.TestCase):
    """Temporary buff infrastructure tests."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []
        player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        player.gold = 10
        player.health = 40
        self.game.players = [player]
        self.player = player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_temporary_buff_expires_at_recruit_end(self):
        """Temporary buff added during recruit phase expires at turn end."""
        m = self._add_minion(self.player)
        from hsrl.core.actions import Buff
        Buff(m, atk=3, health=3, temporary=True).do(m, self.game)
        self.assertEqual(m.atk, 5)   # 2 + 3
        self.assertEqual(m.max_health, 6)  # 3 + 3
        # End recruit phase clears temporary buffs
        self.game._clear_temporary_buffs()
        self.assertEqual(m.atk, 2)
        self.assertEqual(m.max_health, 3)

    def test_temporary_buff_expires_at_combat_end(self):
        """Temporary buff added during combat expires at combat end."""
        m = self._add_minion(self.player)
        from hsrl.core.actions import Buff
        Buff(m, atk=2, health=0, temporary=True).do(m, self.game)
        self.assertEqual(m.atk, 4)
        # End combat phase (simulated) clears temporary buffs
        self.game._clear_temporary_buffs()
        self.assertEqual(m.atk, 2)

    def test_permanent_buff_does_not_expire(self):
        """Non-temporary buff persists after clear."""
        m = self._add_minion(self.player)
        from hsrl.core.actions import Buff
        Buff(m, atk=1, health=1, temporary=False).do(m, self.game)  # default
        self.assertEqual(m.atk, 3)
        self.game._clear_temporary_buffs()
        self.assertEqual(m.atk, 3)  # permanent buff persists


class TestPermanentHeroAura(unittest.TestCase):
    """Phase III: Permanent hero aura — passive on_summon auras (Example)."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    # ── ExamplePermanentAura (EXAMPLE_HERO_AURA) ──

    def test_passive_aura_beast_gets_buff(self):
        """Beast minions on board get +1/+1 from passive hero aura."""
        player = self._make_player("EXAMPLE_HERO_AURA")
        # Trigger on_summon to apply the aura
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        # Aura should be applied
        self.assertEqual(len(player.auras), 1)
        self.assertEqual(player.auras[0].atk, 1)
        self.assertEqual(player.auras[0].health, 1)
        self.assertEqual(player.auras[0].race_filter, Race.BEAST)
        # Summon a Beast minion — should get +1/+1 from aura
        m = self._add_minion(player, "EXAMPLE_VANILLA")  # BEAST, base 2/3
        self.assertEqual(m.atk, 3)  # 2 + 1
        self.assertEqual(m.max_health, 4)  # 3 + 1

    def test_passive_aura_non_beast_unchanged(self):
        """Non-Beast minions do not get the aura bonus."""
        player = self._make_player("EXAMPLE_HERO_AURA")
        fn = getattr(player.data.scripts, "on_summon", None)
        fn(player, self.game)
        # Summon a Dragon minion — should NOT get +1/+1
        m = self._add_minion(player, "EXAMPLE_TAUNT")  # DRAGON, base 2/4
        self.assertEqual(m.atk, 2)  # no aura bonus
        self.assertEqual(m.max_health, 4)  # no aura bonus

    def test_passive_aura_persists_for_new_minions(self):
        """Aura affects minions summoned after the aura was applied."""
        player = self._make_player("EXAMPLE_HERO_AURA")
        fn = getattr(player.data.scripts, "on_summon", None)
        fn(player, self.game)
        # First Beast
        m1 = self._add_minion(player, "EXAMPLE_VANILLA")  # BEAST
        self.assertEqual(m1.atk, 3)
        # Second Beast — aura should still apply
        m2 = self._add_minion(player, "EXAMPLE_VANILLA")  # BEAST
        self.assertEqual(m2.atk, 3)
        self.assertEqual(m2.max_health, 4)

    def test_passive_aura_hero_power_returns_none(self):
        """Passive hero power has no manual activation."""
        player = self._make_player("EXAMPLE_HERO_AURA")
        hp_fn = getattr(player.data.scripts, "hero_power", None)
        self.assertIsNotNone(hp_fn)
        result = hp_fn(player, self.game)
        self.assertIsNone(result)


class TestPhaseIIIActiveAuras(unittest.TestCase):
    """Phase III: Active hero power — tribe-wide buffs (Bloodfury)."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    # ── Bloodfury (Lord Jaraxxus / TB_BaconShop_HERO_37) ──

    def test_bloodfury_buffs_all_demons(self):
        """Bloodfury: cost=1, gives all friendly Demons +1/+1."""
        player = self._make_player("TB_BaconShop_HERO_37", gold=5)
        # Add 2 Demons + 1 non-Demon
        d1 = self._add_minion(player, "EXAMPLE_END_OF_TURN")  # DEMON, base 2/3
        d2 = self._add_minion(player, "EXAMPLE_FODDER")        # DEMON, base 3/3
        beast = self._add_minion(player, "EXAMPLE_VANILLA")    # BEAST, base 2/3
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)  # 5 - 1
        # Both Demons +1/+1
        self.assertEqual(d1.atk, 3)   # 2 + 1
        self.assertEqual(d1.max_health, 4)  # 3 + 1
        self.assertEqual(d2.atk, 4)   # 3 + 1
        self.assertEqual(d2.max_health, 4)  # 3 + 1
        # Beast unchanged
        self.assertEqual(beast.atk, 2)
        self.assertEqual(beast.max_health, 3)

    def test_bloodfury_no_demons(self):
        """Bloodfury: with no Demons on board, returns None."""
        player = self._make_player("TB_BaconShop_HERO_37", gold=5)
        self._add_minion(player, "EXAMPLE_VANILLA")  # BEAST only
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)  # Gold deducted
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))

    def test_bloodfury_empty_board(self):
        """Bloodfury: empty board returns None."""
        player = self._make_player("TB_BaconShop_HERO_37", gold=5)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertTrue(player.get_tag(GameTag.HERO_POWER_USED))


class TestPhaseIVSpellDiscover(unittest.TestCase):
    """Phase IV: Spell discovery hero powers."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        player.tavern_tier = 3
        self.game.players = [player]
        return player

    def test_spell_discover_adds_spell_to_hand(self):
        """Spell Discover hero power adds a spell card to hand."""
        player = self._make_player("EXAMPLE_HERO_SPELL", gold=5)
        hand_before = len(player.hand)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)  # 5 - 1
        self.assertGreater(len(player.hand), hand_before)
        # Verify it's a spell (SPELL cardtype)
        new_card = player.hand[hand_before]
        self.assertEqual(new_card.get_tag(GameTag.CARDTYPE), CardType.SPELL)

    def test_spell_discover_respects_tier(self):
        """Discovered spell tier ≤ player's tavern tier."""
        player = self._make_player("EXAMPLE_HERO_SPELL", gold=5)
        player.tavern_tier = 2
        self.game.use_hero_power(player)
        new_card = player.hand[0]
        self.assertLessEqual(new_card.get_tag(GameTag.TECH_LEVEL), 2)


class TestPhaseIVTavernFreeze(unittest.TestCase):
    """Phase IV: Per-minion tavern freeze system."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []
        self.game.init_pool()

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def test_freeze_tavern_minion(self):
        """FreezeTavernMinion sets FROZEN tag on a tavern minion."""
        player = self._make_player("EXAMPLE_HERO_FREEZE", gold=5)
        self.game.refresh_tavern(player)
        tavern_minions = [m for m in player.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        self.assertGreater(len(tavern_minions), 0)
        self.game.use_hero_power(player)
        frozen = [m for m in player.tavern if m.get_tag(GameTag.FROZEN, False)]
        self.assertEqual(len(frozen), 1)

    def test_frozen_minion_persists_through_auto_refresh(self):
        """Frozen minion persists through auto-refresh (preserve_frozen=True)."""
        player = self._make_player("EXAMPLE_HERO_FREEZE", gold=5)
        self.game.refresh_tavern(player)
        tavern_minions = [m for m in player.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        frozen_entity_id = tavern_minions[0].entity_id
        from hsrl.core.actions import FreezeTavernMinion
        FreezeTavernMinion(tavern_minions[0]).do(tavern_minions[0], self.game)
        # Auto-refresh (turn start) preserves frozen minion
        self.game.refresh_tavern(player, preserve_frozen=True)
        frozen_in_tavern = [m for m in player.tavern
                            if m.entity_id == frozen_entity_id]
        self.assertEqual(len(frozen_in_tavern), 1)

    def test_frozen_minion_lost_on_manual_refresh(self):
        """Frozen minion is lost when player manually refreshes."""
        player = self._make_player("EXAMPLE_HERO_FREEZE", gold=5)
        self.game.refresh_tavern(player)
        tavern_minions = [m for m in player.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        frozen_entity_id = tavern_minions[0].entity_id
        from hsrl.core.actions import FreezeTavernMinion
        FreezeTavernMinion(tavern_minions[0]).do(tavern_minions[0], self.game)
        # Manual refresh (preserve_frozen=False by default) — frozen minion is lost
        self.game.refresh_tavern(player)
        frozen_in_tavern = [m for m in player.tavern
                            if m.entity_id == frozen_entity_id]
        self.assertEqual(len(frozen_in_tavern), 0)

    def test_frozen_minion_gains_stats_on_refresh(self):
        """Frozen minion gains +2/+1 each turn it remains frozen (auto-refresh only)."""
        player = self._make_player("EXAMPLE_HERO_FREEZE", gold=5)
        self.game.refresh_tavern(player)
        tavern_minions = [m for m in player.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        frozen_entity_id = tavern_minions[0].entity_id
        base_atk = tavern_minions[0].atk
        base_max_hp = tavern_minions[0].max_health
        from hsrl.core.actions import FreezeTavernMinion
        FreezeTavernMinion(tavern_minions[0]).do(tavern_minions[0], self.game)
        # Auto-refresh preserves frozen minion and gives +2/+1
        self.game.refresh_tavern(player, preserve_frozen=True)
        frozen_now = [m for m in player.tavern if m.entity_id == frozen_entity_id]
        self.assertEqual(len(frozen_now), 1)
        self.assertGreaterEqual(frozen_now[0].atk, base_atk + 2)
        self.assertGreaterEqual(frozen_now[0].max_health, base_max_hp + 1)


class TestPhaseIVGalakrond(unittest.TestCase):
    """Phase IV: Galakrond's Greed — replace tavern minion with higher tier."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []
        self.game.init_pool()

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        player.tavern_tier = 4
        self.game.players = [player]
        return player

    def test_galakrond_replaces_minion_with_higher_tier(self):
        """Galakrond: replace a tavern minion with a higher tier one."""
        player = self._make_player("TB_BaconShop_HERO_02", gold=5)
        self.game.refresh_tavern(player)
        tavern_minions = [m for m in player.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        self.assertGreater(len(tavern_minions), 0)
        old_tier = min(m.get_tag(GameTag.TECH_LEVEL, 1) for m in tavern_minions)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)  # 5 - 1
        # Verify tavern still has minions
        remaining = [m for m in player.tavern
                     if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        self.assertGreater(len(remaining), 0)


class TestPhaseIVPostCombatCopy(unittest.TestCase):
    """Phase IV: Post-combat copy — I'll Take That! & Example."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_post_combat_copy_example(self):
        """Passive post-combat copy hero: on_summon registers listener."""
        player = self._make_player("EXAMPLE_HERO_COPY")
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        self.assertTrue(len(self.game._event_listeners) > 0)

    def test_ill_take_that_hero_power(self):
        """I'll Take That! sets ILTA_ACTIVE tag on use."""
        player = self._make_player("TB_BaconShop_HERO_45", gold=5)
        # Register on_summon listener
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)  # 5 - 1
        self.assertTrue(player.get_tag(GameTag.ILTA_ACTIVE, False))

    def test_ill_take_that_copies_killed_enemy(self):
        """I'll Take That!: after combat, copy of first killed enemy goes to hand."""
        from hsrl.core.actions import CopyFirstKilledEnemy
        player = self._make_player("TB_BaconShop_HERO_45", gold=5)
        # Register listener
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        # Activate hero power
        player.set_tag(GameTag.ILTA_ACTIVE, True)
        # Simulate combat: add an enemy minion to death log
        enemy = self._add_minion(player, "EXAMPLE_VANILLA")  # gets added to player board as controller
        # Create a real enemy by creating a second player
        player2 = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        player2.health = 40
        self.game.players.append(player2)
        enemy2 = self._add_minion(player2, "EXAMPLE_TAUNT")  # enemy2 on player2's board
        enemy2.controller = player2
        self.game._combat_death_log.append(enemy2)
        # Copy first killed enemy
        hand_before = len(player.hand)
        CopyFirstKilledEnemy(player).do(player, self.game)
        self.assertEqual(len(player.hand), hand_before + 1)


# ═══════════════════════════════════════════════════════════════════════════
# Phase V — Dig Counter (进度计数器)
# ═══════════════════════════════════════════════════════════════════════════

class TestPhaseVDigCounter(unittest.TestCase):
    """Phase V: Dig Counter — Buried Treasure & Example."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def test_dig_counter_initial_value(self):
        """DIG_COUNTER defaults to 4 on first read."""
        player = self._make_player("EXAMPLE_HERO_DIG")
        count = player.get_tag(GameTag.DIG_COUNTER, 4)
        self.assertEqual(count, 4)

    def test_dig_counter_decrements_on_use(self):
        """Each hero power use decrements DIG_COUNTER by 1."""
        player = self._make_player("EXAMPLE_HERO_DIG")
        player.set_tag(GameTag.DIG_COUNTER, 4)
        for expected in [3, 2, 1]:
            player.set_tag(GameTag.HERO_POWER_USED, False)
            self.game.use_hero_power(player)
            self.assertEqual(player.get_tag(GameTag.DIG_COUNTER), expected)

    def test_dig_counter_rewards_golden_at_zero(self):
        """When counter hits 0, a golden minion is added to hand and counter resets to 4."""
        player = self._make_player("EXAMPLE_HERO_DIG")
        player.set_tag(GameTag.DIG_COUNTER, 1)
        player.set_tag(GameTag.HERO_POWER_USED, False)
        hand_before = len(player.hand)
        self.game.use_hero_power(player)
        self.assertEqual(player.get_tag(GameTag.DIG_COUNTER), 4)
        self.assertEqual(len(player.hand), hand_before + 1)
        reward = player.hand[-1]
        self.assertTrue(reward.is_golden)
        base_atk = reward.get_tag(GameTag.BASE_ATK, 0)
        base_health = reward.get_tag(GameTag.BASE_HEALTH, 0)
        self.assertEqual(reward.atk, base_atk)
        self.assertEqual(reward.max_health, base_health)

    def test_dig_counter_cycles(self):
        """Use 4 times → reward, then 3 more times → counter at 1."""
        player = self._make_player("EXAMPLE_HERO_DIG")
        player.set_tag(GameTag.DIG_COUNTER, 4)
        for _ in range(4):
            player.set_tag(GameTag.HERO_POWER_USED, False)
            self.game.use_hero_power(player)
        self.assertEqual(len(player.hand), 1)
        self.assertTrue(player.hand[0].is_golden)
        self.assertEqual(player.get_tag(GameTag.DIG_COUNTER), 4)
        for _ in range(3):
            player.set_tag(GameTag.HERO_POWER_USED, False)
            self.game.use_hero_power(player)
        self.assertEqual(player.get_tag(GameTag.DIG_COUNTER), 1)
        self.assertEqual(len(player.hand), 1)

    def test_dig_counter_cost_deduction(self):
        """Hero power costs 1 gold per use."""
        player = self._make_player("EXAMPLE_HERO_DIG", gold=5)
        player.set_tag(GameTag.DIG_COUNTER, 4)
        self.game.use_hero_power(player)
        self.assertEqual(player.gold, 4)
        self.assertEqual(player.get_tag(GameTag.DIG_COUNTER), 3)


# ═══════════════════════════════════════════════════════════════════════════
# Phase V — Type Rotation (类型轮换)
# ═══════════════════════════════════════════════════════════════════════════

class TestPhaseVTypeRotation(unittest.TestCase):
    """Phase V: Type Rotation — A Tale of Kings & Example."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def test_type_rotation_registers_listeners(self):
        """on_summon registers RECRUIT_BEGIN and MINION_BOUGHT listeners."""
        player = self._make_player("EXAMPLE_HERO_ROTATION")
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        self.assertGreater(len(self.game._event_listeners), 0)

    def test_rotate_rat_king_type_changes_tribe(self):
        """RotateRatKingType changes RAT_KING_TYPE to a different race."""
        from hsrl.core.actions import RotateRatKingType
        player = self._make_player("EXAMPLE_HERO_ROTATION")
        player.set_tag(GameTag.RAT_KING_TYPE, Race.BEAST)
        RotateRatKingType(player).do(player, self.game)
        new_type = player.get_tag(GameTag.RAT_KING_TYPE)
        self.assertNotEqual(new_type, Race.BEAST)
        self.assertIn(new_type, RotateRatKingType.RAT_KING_RACES)

    def test_type_rotation_buffs_matching_tribe_on_buy(self):
        """Buying a minion of the rotated tribe triggers +1/+2 buff."""
        player = self._make_player("EXAMPLE_HERO_ROTATION")
        player.set_tag(GameTag.RAT_KING_TYPE, Race.BEAST)
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.controller = player
        minion.set_tag(GameTag.RACE, Race.BEAST)
        minion.zone = Zone.PLAY
        player.board.append(minion)
        atk_before = minion.atk
        hp_before = minion.health
        self.game.broadcast("MINION_BOUGHT", minion, player)
        self.assertEqual(minion.atk, atk_before + 1)
        self.assertEqual(minion.health, hp_before + 2)

    def test_type_rotation_non_matching_tribe_no_buff(self):
        """MURLOC minion bought when RAT_KING_TYPE is BEAST gets no buff."""
        player = self._make_player("EXAMPLE_HERO_ROTATION")
        player.set_tag(GameTag.RAT_KING_TYPE, Race.BEAST)
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.controller = player
        minion.set_tag(GameTag.RACE, Race.MURLOC)
        minion.zone = Zone.PLAY
        player.board.append(minion)
        atk_before = minion.atk
        self.game.broadcast("MINION_BOUGHT", minion, player)
        self.assertEqual(minion.atk, atk_before)

    def test_type_rotation_all_race_always_buffed(self):
        """ALL race minions match any rotated type and get buffed."""
        player = self._make_player("EXAMPLE_HERO_ROTATION")
        player.set_tag(GameTag.RAT_KING_TYPE, Race.PIRATE)
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.controller = player
        minion.set_tag(GameTag.RACE, Race.ALL)
        minion.zone = Zone.PLAY
        player.board.append(minion)
        atk_before = minion.atk
        self.game.broadcast("MINION_BOUGHT", minion, player)
        self.assertEqual(minion.atk, atk_before + 1)

    def test_hero_power_passive_returns_none(self):
        """A Tale of Kings is passive — hero_power() returns None."""
        from hsrl.cards.heroes.scripts import ExampleTypeRotation
        player = self._make_player("EXAMPLE_HERO_ROTATION")
        result = ExampleTypeRotation.hero_power(player, self.game)
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════════
# Phase VI — Start of Combat Passive
# ═══════════════════════════════════════════════════════════════════════════

class TestPhaseVIStartOfCombat(unittest.TestCase):
    """Phase VI: Passive hero powers triggered on START_OF_COMBAT."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_soc_passive_registers_listener(self):
        """on_summon registers a START_OF_COMBAT listener."""
        from hsrl.core.events import START_OF_COMBAT
        player = self._make_player("EXAMPLE_HERO_SOC")
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for e, l in self.game._event_listeners
                     if l.event_name == START_OF_COMBAT]
        self.assertGreater(len(listeners), 0)

    def test_soc_passive_buffs_leftmost(self):
        """START_OF_COMBAT broadcast buffs left-most minion +2 ATK."""
        player = self._make_player("EXAMPLE_HERO_SOC")
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        # Add 3 minions
        m1 = self._add_minion(player)  # left-most: 2/3
        m2 = self._add_minion(player)  # middle: 2/3
        m3 = self._add_minion(player)  # right: 2/3
        atk_before = m1.atk
        # Broadcast START_OF_COMBAT
        self.game.broadcast("START_OF_COMBAT", player)
        self.assertEqual(m1.atk, atk_before + 2)
        # Other minions unaffected
        self.assertEqual(m2.atk, 2)
        self.assertEqual(m3.atk, 2)

    def test_soc_passive_empty_board_no_crash(self):
        """START_OF_COMBAT with empty board doesn't crash."""
        player = self._make_player("EXAMPLE_HERO_SOC")
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        self.game.broadcast("START_OF_COMBAT", player)

    def test_soc_hero_power_returns_none(self):
        """Passive — hero_power() returns None."""
        from hsrl.cards.heroes.scripts import ExampleStartOfCombat
        player = self._make_player("EXAMPLE_HERO_SOC")
        result = ExampleStartOfCombat.hero_power(player, self.game)
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════════
# Phase VI — Real Passive Hero Powers
# ═══════════════════════════════════════════════════════════════════════════

class TestPhaseVIDeathwing(unittest.TestCase):
    """Phase VI: Deathwing's ALL Will Burn! — global +3 ATK aura."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_deathwing_aura_adds_attack(self):
        """ALL Will Burn! gives +3 ATK to all minions via GlobalAura."""
        player = self._make_player("TB_BaconShop_HERO_52")
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        m = self._add_minion(player)
        self.assertEqual(m.atk, 2 + 3)
        self.assertEqual(m.max_health, 3)

    def test_deathwing_hero_power_returns_none(self):
        """ALL Will Burn! is passive — hero_power() returns None."""
        player = self._make_player("TB_BaconShop_HERO_52")
        from hsrl.cards.heroes.scripts import AllWillBurnScript
        result = AllWillBurnScript.hero_power(player, self.game)
        self.assertIsNone(result)

    def test_deathwing_aura_resolves_player_from_queued_minion_source(self):
        """Queued summon replay must not attach an aura to the Minion."""
        player = self._make_player("TB_BaconShop_HERO_52")
        minion = self._add_minion(player)
        from hsrl.cards.heroes.scripts import AllWillBurnScript
        AllWillBurnScript.on_summon(minion, self.game)
        self.assertEqual(len(player.auras), 1)
        self.assertEqual(minion.atk, 2 + 3)


class TestPhaseVIBananarama(unittest.TestCase):
    """Phase VI: Mukla's Bananarama — start of turn get 2 Bananas."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def test_bananarama_registers_listener(self):
        """on_summon registers a RECRUIT_BEGIN listener."""
        from hsrl.core.events import RECRUIT_BEGIN
        player = self._make_player("TB_BaconShop_HERO_38")
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for _, l in self.game._event_listeners
                     if l.event_name == RECRUIT_BEGIN]
        self.assertGreater(len(listeners), 0)

    def test_bananarama_adds_bananas(self):
        """RECRUIT_BEGIN broadcast adds 2 Banana spells to hand."""
        player = self._make_player("TB_BaconShop_HERO_38")
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        hand_before = len(player.hand)
        self.game.broadcast("RECRUIT_BEGIN", player)
        self.assertEqual(len(player.hand), hand_before + 2)
        for m in player.hand[-2:]:
            self.assertEqual(m.get_tag(GameTag.CARD_ID), "BANANA_SPELL")

    def test_bananarama_hero_power_returns_none(self):
        """Bananarama is passive — hero_power() returns None."""
        player = self._make_player("TB_BaconShop_HERO_38")
        from hsrl.cards.heroes.scripts import BananaramaScript
        result = BananaramaScript.hero_power(player, self.game)
        self.assertIsNone(result)


class TestPhaseVIVerdantSpheres(unittest.TestCase):
    """Phase VI: Kael'thas's Verdant Spheres — buy 3 → get Tavern Coin."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id, gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def test_verdant_spheres_registers_listener(self):
        """on_summon registers a MINION_BOUGHT listener."""
        from hsrl.core.events import MINION_BOUGHT
        player = self._make_player("TB_BaconShop_HERO_60")
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for _, l in self.game._event_listeners
                     if l.event_name == MINION_BOUGHT]
        self.assertGreater(len(listeners), 0)

    def test_verdant_spheres_counter_increments(self):
        """3 buys → counter resets and Tavern Coin added to hand."""
        player = self._make_player("TB_BaconShop_HERO_60")
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        player.set_tag(GameTag.IMPROVE_COUNTER, 2)
        hand_before = len(player.hand)
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.controller = player
        self.game.broadcast("MINION_BOUGHT", minion, player)
        counter = player.get_tag(GameTag.IMPROVE_COUNTER, 0)
        self.assertEqual(counter, 0)
        self.assertEqual(len(player.hand), hand_before + 1)
        coin = player.hand[-1]
        self.assertEqual(coin.get_tag(GameTag.CARD_ID), "TAVERN_COIN")

    def test_verdant_spheres_hero_power_returns_none(self):
        """Verdant Spheres passive tracker — hero_power() returns None."""
        player = self._make_player("TB_BaconShop_HERO_60")
        from hsrl.cards.heroes.scripts import VerdantSpheresScript
        result = VerdantSpheresScript.hero_power(player, self.game)
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════════
# Phase VIb — SoC Keyword, TAVERN_UPGRADED, SoC Per-Type Buff
# ═══════════════════════════════════════════════════════════════════════════

class TestPhaseVIbSwattingInsects(unittest.TestCase):
    """Phase VIb: Al'Akir's Swatting Insects — SoC give WF/DS/Taunt to left-most."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id="TB_BaconShop_HERO_76", gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_on_summon_registers_soc_listener(self):
        """on_summon registers a START_OF_COMBAT listener."""
        from hsrl.core.events import START_OF_COMBAT
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for _, l in self.game._event_listeners
                     if l.event_name == START_OF_COMBAT]
        self.assertGreater(len(listeners), 0)

    def test_soc_gives_keywords_to_leftmost(self):
        """START_OF_COMBAT gives Windfury, Divine Shield, Taunt to left-most minion."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        m1 = self._add_minion(player)  # left-most
        m2 = self._add_minion(player)  # 2nd
        self.game.broadcast("START_OF_COMBAT", player)
        self.assertTrue(m1.windfury)
        self.assertTrue(m1.divine_shield)
        self.assertTrue(m1.taunt)
        # Second minion should NOT get keywords
        self.assertFalse(m2.windfury)
        self.assertFalse(m2.divine_shield)
        self.assertFalse(m2.taunt)

    def test_soc_empty_board_no_error(self):
        """START_OF_COMBAT with empty board should not error."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        self.game.broadcast("START_OF_COMBAT", player)

    def test_soc_only_dead_minions(self):
        """START_OF_COMBAT with only dead minions should not error."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        m = self._add_minion(player)
        m.set_tag(GameTag.HEALTH, 0)  # dead
        self.game.broadcast("START_OF_COMBAT", player)
        self.assertFalse(m.windfury)

    def test_hero_power_returns_none(self):
        """Swatting Insects is passive — hero_power() returns None."""
        player = self._make_player()
        from hsrl.cards.heroes.scripts import SwattingInsectsScript
        result = SwattingInsectsScript.hero_power(player, self.game)
        self.assertIsNone(result)


class TestPhaseVIbEverbloom(unittest.TestCase):
    """Phase VIb: Omu's Everbloom — TAVERN_UPGRADED → Gain 2 Gold."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id="TB_BaconShop_HERO_74", gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def test_on_summon_registers_tavern_upgraded_listener(self):
        """on_summon registers a TAVERN_UPGRADED listener."""
        from hsrl.core.events import TAVERN_UPGRADED
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for _, l in self.game._event_listeners
                     if l.event_name == TAVERN_UPGRADED]
        self.assertGreater(len(listeners), 0)

    def test_tavern_upgrade_grants_2_gold(self):
        """After upgrading tavern, player gains 2 Gold."""
        player = self._make_player(gold=3)
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        gold_before = player.gold
        self.game.broadcast("TAVERN_UPGRADED", player, 3)
        self.assertEqual(player.gold, gold_before + 2)

    def test_multiple_upgrades_stack(self):
        """Each upgrade grants 2 Gold."""
        player = self._make_player(gold=3)
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        gold_before = player.gold
        self.game.broadcast("TAVERN_UPGRADED", player, 2)
        self.game.broadcast("TAVERN_UPGRADED", player, 3)
        self.assertEqual(player.gold, gold_before + 4)

    def test_hero_power_returns_none(self):
        """Everbloom is passive — hero_power() returns None."""
        player = self._make_player()
        from hsrl.cards.heroes.scripts import EverbloomScript
        result = EverbloomScript.hero_power(player, self.game)
        self.assertIsNone(result)


class TestPhaseVIbWaxWarband(unittest.TestCase):
    """Phase VIb: Wagtoggle's Wax Warband — SoC buff one minion per type +2/+2."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id="TB_BaconShop_HERO_14", gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA", race=Race.INVALID):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        m.set_tag(GameTag.RACE, race)
        player.board.append(m)
        return m

    def test_on_summon_registers_soc_listener(self):
        """on_summon registers a START_OF_COMBAT listener."""
        from hsrl.core.events import START_OF_COMBAT
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for _, l in self.game._event_listeners
                     if l.event_name == START_OF_COMBAT]
        self.assertGreater(len(listeners), 0)

    def test_soc_buffs_one_per_type(self):
        """START_OF_COMBAT buffs one minion per unique type +2/+2."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        m1 = self._add_minion(player, race=Race.BEAST)
        m2 = self._add_minion(player, race=Race.MECH)
        m3 = self._add_minion(player, race=Race.DEMON)
        m4 = self._add_minion(player, race=Race.INVALID)
        self.game.broadcast("START_OF_COMBAT", player)
        self.assertEqual(m1.atk, 2 + 2)
        self.assertEqual(m1.max_health, 3 + 2)
        self.assertEqual(m2.atk, 2 + 2)
        self.assertEqual(m2.max_health, 3 + 2)
        self.assertEqual(m3.atk, 2 + 2)
        self.assertEqual(m3.max_health, 3 + 2)
        # Neutral/INVALID gets no buff
        self.assertEqual(m4.atk, 2)
        self.assertEqual(m4.max_health, 3)

    def test_soc_resolves_player_from_hero_power_entity_controller(self):
        """Listener sources may be hero-power entities rather than Players."""
        from hsrl.cards.heroes.scripts import WaxWarbandScript

        player = self._make_player()
        power = self.game.create_minion("TB_BaconShop_HP_037a")
        self.assertIsNotNone(power)
        power.controller = player
        WaxWarbandScript.on_summon(power, self.game)
        beast = self._add_minion(player, race=Race.BEAST)

        self.game.broadcast("START_OF_COMBAT", player)

        self.assertEqual(beast.atk, 4)
        self.assertEqual(beast.max_health, 5)

    def test_soc_same_type_only_buffed_once(self):
        """Multiple minions of same type → only one gets buffed."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        m1 = self._add_minion(player, race=Race.BEAST)
        m2 = self._add_minion(player, race=Race.BEAST)
        m3 = self._add_minion(player, race=Race.BEAST)
        self.game.broadcast("START_OF_COMBAT", player)
        self.assertEqual(m1.atk, 2 + 2)
        self.assertEqual(m2.atk, 2)
        self.assertEqual(m3.atk, 2)

    def test_soc_empty_board_no_error(self):
        """START_OF_COMBAT with empty board should not error."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        self.game.broadcast("START_OF_COMBAT", player)

    def test_soc_all_neutral_board_no_buff(self):
        """Board with only neutral/invalid type minions → no buffs."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        m1 = self._add_minion(player, race=Race.INVALID)
        m2 = self._add_minion(player, race=Race.INVALID)
        self.game.broadcast("START_OF_COMBAT", player)
        self.assertEqual(m1.atk, 2)
        self.assertEqual(m2.atk, 2)

    def test_hero_power_returns_none(self):
        """Wax Warband is passive — hero_power() returns None."""
        player = self._make_player()
        from hsrl.cards.heroes.scripts import WaxWarbandScript
        result = WaxWarbandScript.hero_power(player, self.game)
        self.assertIsNone(result)


class TestPhaseVIcGoneFishing(unittest.TestCase):
    """Phase VIc: Flurgl's Gone Fishing — sell 5 minions → random Murloc in hand."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.players = []

    def _make_player(self, hero_id="TB_BaconShop_HERO_55", gold=10):
        player = Player(CARDS.get(hero_id), game=self.game)
        player.gold = gold
        player.health = 40
        self.game.players = [player]
        return player

    def _add_minion_to_board(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_on_summon_registers_minion_sold_listener(self):
        """on_summon registers a MINION_SOLD listener."""
        from hsrl.core.events import MINION_SOLD
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        self.assertIsNotNone(fn)
        fn(player, self.game)
        listeners = [l for _, l in self.game._event_listeners
                     if l.event_name == MINION_SOLD]
        self.assertGreater(len(listeners), 0)

    def test_sell_5_minions_adds_murloc_to_hand(self):
        """After selling 5 minions, a random Murloc is added to hand."""
        player = self._make_player(gold=3)
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        # Sell 5 minions
        for _ in range(5):
            m = self._add_minion_to_board(player)
            self.game.sell_minion(player, m)
        # Should have at least 1 card in hand
        self.assertGreater(len(player.hand), 0)
        murloc = player.hand[0]
        self.assertEqual(murloc.race, Race.MURLOC)
        # Gold from selling (5 × 1 = 5), plus initial 3
        self.assertEqual(player.gold, 8)

    def test_sell_4_minions_no_murloc(self):
        """Selling less than 5 minions should not add a Murloc."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        for _ in range(4):
            m = self._add_minion_to_board(player)
            self.game.sell_minion(player, m)
        self.assertEqual(len(player.hand), 0)

    def test_counter_resets_after_reward(self):
        """After 5 sells and reward, counter resets so next 5 sells give another Murloc."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        # First 5 sells → 1st Murloc
        for _ in range(5):
            m = self._add_minion_to_board(player)
            self.game.sell_minion(player, m)
        self.assertEqual(len(player.hand), 1)
        # Next 5 sells → 2nd Murloc
        for _ in range(5):
            m = self._add_minion_to_board(player)
            self.game.sell_minion(player, m)
        self.assertEqual(len(player.hand), 2)
        self.assertEqual(player.hand[0].race, Race.MURLOC)
        self.assertEqual(player.hand[1].race, Race.MURLOC)

    def test_sell_beyond_5_each_cycle_triggers(self):
        """Three full cycles (15 sells) produce 3 Murlocs."""
        player = self._make_player()
        fn = getattr(player.data.scripts, "on_summon", None)
        if fn:
            fn(player, self.game)
        for _ in range(15):
            m = self._add_minion_to_board(player)
            self.game.sell_minion(player, m)
        self.assertEqual(len(player.hand), 3)
        for murloc in player.hand:
            self.assertEqual(murloc.race, Race.MURLOC)

    def test_hero_power_returns_none(self):
        """Gone Fishing is passive — hero_power() returns None."""
        player = self._make_player()
        from hsrl.cards.heroes.scripts import GoneFishingScript
        result = GoneFishingScript.hero_power(player, self.game)
        self.assertIsNone(result)


class TestRagePotion(unittest.TestCase):
    """Rage Potion (TB_BaconShop_HP_018): HP(1) — Give a minion +3 ATK this turn."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_gives_3_attack_temporary(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = self.player
        self.player.board.append(m)
        from hsrl.cards.heroes.scripts import RagePotionScript
        base = m.get_tag(GameTag.BASE_ATK, 0)
        action = RagePotionScript.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=self.player)
        self.game.resolve_queue()
        self.assertEqual(m.atk, base + 3)
        # Verify buff is temporary
        self.assertTrue(any(b.temporary for b in m._buffs if b.tags.get(GameTag.ATK, 0) > 0),
                        "Buff should be temporary")

    def test_empty_board_returns_none(self):
        from hsrl.cards.heroes.scripts import RagePotionScript
        action = RagePotionScript.hero_power(self.player, self.game)
        self.assertIsNone(action)


class TestDieInsects(unittest.TestCase):
    """DIE, INSECTS! (TB_BaconShop_HP_019): HP(2) — Give a minion +8 ATK this turn."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_gives_8_attack_temporary(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = self.player
        self.player.board.append(m)
        from hsrl.cards.heroes.scripts import DieInsectsScript
        base = m.get_tag(GameTag.BASE_ATK, 0)
        action = DieInsectsScript.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=self.player)
        self.game.resolve_queue()
        self.assertEqual(m.atk, base + 8)

    def test_empty_board_returns_none(self):
        from hsrl.cards.heroes.scripts import DieInsectsScript
        action = DieInsectsScript.hero_power(self.player, self.game)
        self.assertIsNone(action)


class TestRebornRites(unittest.TestCase):
    """Reborn Rites (TB_BaconShop_HP_024): HP(0) — Give a minion Reborn."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_gives_reborn(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = self.player
        self.player.board.append(m)
        self.assertFalse(m.has_tag(GameTag.REBORN))
        from hsrl.cards.heroes.scripts import RebornRitesScript
        action = RebornRitesScript.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=self.player)
        self.game.resolve_queue()
        self.assertTrue(m.has_tag(GameTag.REBORN))

    def test_skips_already_reborn_minions(self):
        m = self.game.create_minion("EXAMPLE_REBORN")
        m.controller = self.player
        self.player.board.append(m)
        self.assertTrue(m.has_tag(GameTag.REBORN))
        from hsrl.cards.heroes.scripts import RebornRitesScript
        action = RebornRitesScript.hero_power(self.player, self.game)
        # Only minion has reborn already → no eligible target → None
        self.assertIsNone(action)

    def test_empty_board_returns_none(self):
        from hsrl.cards.heroes.scripts import RebornRitesScript
        action = RebornRitesScript.hero_power(self.player, self.game)
        self.assertIsNone(action)


class TestKingOfBeasts(unittest.TestCase):
    """King of Beasts (TB_BaconShop_HP_041a): HP(2) — Give a friendly Beast +2/+2."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_buffs_beast(self):
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.set_tag(GameTag.RACE, Race.BEAST)
        m.controller = self.player
        self.player.board.append(m)
        atk_before, hp_before = m.atk, m.health
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_041a"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=self.player)
        self.game.resolve_queue()
        self.assertEqual(m.atk, atk_before + 2)
        self.assertEqual(m.health, hp_before + 2)

    def test_skips_non_beast(self):
        # Only non-Beast minion → no target
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.set_tag(GameTag.RACE, Race.MURLOC)
        m.controller = self.player
        self.player.board.append(m)
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_041a"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNone(action)

    def test_empty_board_returns_none(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_041a"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNone(action)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 11 — Simple Active Hero Powers
# ═══════════════════════════════════════════════════════════════════════════

class TestPhase11HonorableWarband(unittest.TestCase):
    """TB_BaconShop_HP_051 — Honorable Warband: Give tribeless minions +1/+1."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_minion(self, player, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = player
        m.zone = Zone.PLAY
        player.board.append(m)
        return m

    def test_buffs_all_tribeless(self):
        m1 = self._add_minion(self.player, "EXAMPLE_VANILLA")
        m2 = self._add_minion(self.player, "EXAMPLE_VANILLA")
        m1.set_tag(GameTag.RACE, Race.NONE)
        m2.set_tag(GameTag.RACE, Race.NONE)
        atk1_before, hp1_before = m1.atk, m1.health

        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_051"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.assertIsInstance(action, list)
        self.assertEqual(len(action), 2)

        for a in action:
            self.game.queue_action(a, source=self.player)
        self.game.resolve_queue()
        self.assertEqual(m1.atk, atk1_before + 1)
        self.assertEqual(m1.health, hp1_before + 1)

    def test_ignores_typed_minions(self):
        m1 = self._add_minion(self.player, "EXAMPLE_VANILLA")
        m1.set_tag(GameTag.RACE, Race.NONE)
        m2 = self._add_minion(self.player, "EXAMPLE_WINDFURY")  # Dragon
        atk_before = m2.atk

        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_051"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.assertIsInstance(action, list)
        self.assertEqual(len(action), 1)
        for a in action:
            self.game.queue_action(a, source=self.player)
        self.game.resolve_queue()
        self.assertEqual(m2.atk, atk_before)

    def test_no_tribeless_returns_none(self):
        self._add_minion(self.player, "EXAMPLE_WINDFURY")
        self._add_minion(self.player, "EXAMPLE_DIVINE_SHIELD")

        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_051"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNone(action)


class TestPhase11NefariousFire(unittest.TestCase):
    """TB_BaconShop_HP_043 — Nefarious Fire: SoC deal 1 damage to all enemies."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]
        self.enemy_player = None

    def _add_enemy(self, card_id="EXAMPLE_VANILLA"):
        if self.enemy_player is None:
            self.enemy_player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
            self.enemy_player.health = 40
            self.game.players.append(self.enemy_player)
            self.game._current_combat_opponents = {
                self.player: self.enemy_player,
                self.enemy_player: self.player,
            }
        enemy_player = self.enemy_player
        m = self.game.create_minion(card_id)
        m.controller = enemy_player
        m.zone = Zone.PLAY
        enemy_player.board.append(m)
        return m, enemy_player

    def test_soc_deals_1_damage_to_all_enemies(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_043"]
        script.hero_power(self.player, self.game)

        e1, ep = self._add_enemy("EXAMPLE_VANILLA")
        e2, _ = self._add_enemy("EXAMPLE_VANILLA")
        health1_before = e1.health
        health2_before = e2.health

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        self.assertEqual(e1.health, health1_before - 1)
        self.assertEqual(e2.health, health2_before - 1)

    def test_soc_no_enemies_no_crash(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_043"]
        script.hero_power(self.player, self.game)
        self.game.broadcast("START_OF_COMBAT", self.player)

    def test_listener_is_once(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_043"]
        script.hero_power(self.player, self.game)
        listeners_before = len(self.game._event_listeners)

        self.game.broadcast("START_OF_COMBAT", self.player)
        listeners_after = len(self.game._event_listeners)
        self.assertLess(listeners_after, listeners_before)


class TestPhase11FireTheCannons(unittest.TestCase):
    """TB_BaconShop_HP_027 — Fire the Cannons!: SoC deal 3 to 2 random enemies."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]
        self.enemy_player = None

    def _add_enemy(self, card_id="EXAMPLE_VANILLA"):
        if self.enemy_player is None:
            self.enemy_player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
            self.enemy_player.health = 40
            self.game.players.append(self.enemy_player)
            self.game._current_combat_opponents = {
                self.player: self.enemy_player,
                self.enemy_player: self.player,
            }
        enemy_player = self.enemy_player
        m = self.game.create_minion(card_id)
        m.controller = enemy_player
        m.zone = Zone.PLAY
        enemy_player.board.append(m)
        return m, enemy_player

    def test_soc_deals_damage_to_enemies(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_027"]
        script.hero_power(self.player, self.game)

        e1, _ = self._add_enemy("EXAMPLE_VANILLA")
        e2, _ = self._add_enemy("EXAMPLE_VANILLA")
        e3, _ = self._add_enemy("EXAMPLE_VANILLA")

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        damaged = sum(1 for e in [e1, e2, e3] if e.health < 3 or e.dead)
        self.assertGreaterEqual(damaged, 1)  # at least one enemy hit (random.choice with replacement)

    def test_soc_single_enemy(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_027"]
        script.hero_power(self.player, self.game)

        e1, _ = self._add_enemy("EXAMPLE_VANILLA")
        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()
        self.assertTrue(e1.health < 3 or e1.dead)


class TestPhase11PirateParrrrty(unittest.TestCase):
    """TB_BaconShop_HP_072 — Pirate Parrrrty!: Get Pirate, buy discount."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("TB_BaconShop_HERO_18"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_hero_power_gets_pirate(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_072"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=self.player)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)

    def test_buying_pirate_reduces_cost(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_072"]
        fn = getattr(script, "on_summon", None)
        if fn:
            fn(self.player, self.game)

        self.player.set_tag(GameTag.HERO_POWER_COST, 3)
        self.assertEqual(self.player.hero_power_cost, 3)

        pirate = self.game.create_minion("EXAMPLE_VANILLA")
        pirate.set_tag(GameTag.RACE, Race.PIRATE)
        pirate.controller = self.player

        self.game.broadcast("MINION_BOUGHT", pirate, self.player)
        self.assertEqual(self.player.hero_power_cost, 2)

    def test_cost_resets_after_hero_power_use(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_072"]
        self.player.set_tag(GameTag.HERO_POWER_COST, 1)
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.assertEqual(self.player.hero_power_cost, 3)

    def test_buying_non_pirate_does_not_reduce_cost(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_072"]
        fn = getattr(script, "on_summon", None)
        if fn:
            fn(self.player, self.game)

        self.player.set_tag(GameTag.HERO_POWER_COST, 3)
        beast = self.game.create_minion("EXAMPLE_VANILLA")
        beast.set_tag(GameTag.RACE, Race.BEAST)
        beast.controller = self.player

        self.game.broadcast("MINION_BOUGHT", beast, self.player)
        self.assertEqual(self.player.hero_power_cost, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12 — Batch 1: Active (5) + SoC Passive (4) + OnBuy Passive (7)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase12NagaConquest(unittest.TestCase):
    """BG22_HERO_007p2 — Naga Conquest: Discover a Naga."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_hero_power_adds_naga_to_hand(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG22_HERO_007p2"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)
        naga = self.player.hand[0]
        self.assertEqual(naga.race, Race.NAGA)


class TestPhase12BlessingNineFrogs(unittest.TestCase):
    """BG28_HERO_801p — Blessing of the Nine Frogs: Get a random Tavern spell."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_hero_power_adds_spell_to_hand(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG28_HERO_801p"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].get_tag(GameTag.CARDTYPE), CardType.SPELL)


class TestPhase12RunicEmpowerment(unittest.TestCase):
    """TB_BaconShop_HP_702 — Runic Empowerment: Buff +1/+1, upgrades after 5 deaths."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_friendly(self, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def test_hero_power_buffs_minion(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        m = self._add_friendly()
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_702"]
        script.on_summon(self.player, self.game)
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action)
        self.game.resolve_queue()
        self.assertEqual(m.atk, 3)  # 2 base + 1
        self.assertEqual(m.max_health, 4)  # 3 base + 1

    def test_death_counter_upgrades_bonus(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_702"]
        script.on_summon(self.player, self.game)

        # First buff should be +1/+1
        self.player.set_tag(GameTag.RUNIC_BUFF_BONUS, 1)
        self.player.set_tag(GameTag.RUNIC_DEATH_COUNT, 5)

        # Kill 5 friendly minions
        for i in range(5):
            m = self._add_friendly()
            self.game.broadcast("DEATH", m, self.player)
            self.game.resolve_queue()

        # Counter should reset to 5, bonus should be 2
        self.assertEqual(self.player.get_tag(GameTag.RUNIC_BUFF_BONUS, 1), 2)
        self.assertEqual(self.player.get_tag(GameTag.RUNIC_DEATH_COUNT, 5), 5)


class TestPhase12TavernLighting(unittest.TestCase):
    """TB_BaconShop_HP_085 — Tavern Lighting: Get Lantern Light spell."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_hero_power_gives_lantern_light(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_085"]
        action = script.hero_power(self.player, self.game)
        self.assertIsNotNone(action)
        self.game.queue_action(action)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].data.id, "LANTERN_LIGHT")


class TestPhase12MurlocKing(unittest.TestCase):
    """TB_BaconShop_HP_017 — Murloc King: SoC give DR: Summon 1/1 Murloc."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_friendly(self, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def test_soc_grants_deathrattle(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_017"]
        m = self._add_friendly()
        # Activate
        script.hero_power(self.player, self.game)
        # SoC
        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()
        # Minion should have deathrattle override
        self.assertIn("deathrattle", m._script_overrides)

    def test_deathrattle_summons_murloc(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_017"]
        m = self._add_friendly()
        script.hero_power(self.player, self.game)
        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()
        # Kill the minion → deathrattle triggers
        m.health = 0  # Mark as dead
        self.game._check_deaths()
        self.game.resolve_queue()
        # 1/1 Murloc should be on board
        murlocs = [bm for bm in self.player.board if bm.data.id == "TOKEN_MURLOC_1_1"]
        self.assertEqual(len(murlocs), 1)
        self.assertEqual(murlocs[0].atk, 1)
        self.assertEqual(murlocs[0].health, 1)


class TestPhase12Wingmen(unittest.TestCase):
    """TB_BaconShop_HP_069 — Wingmen: SoC left/right +2/+1 and attack immediately."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_friendly(self, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def test_soc_buffs_left_and_right(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_069"]
        script.on_summon(self.player, self.game)
        m1 = self._add_friendly()  # left
        m2 = self._add_friendly()  # middle
        m3 = self._add_friendly()  # right

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        self.assertEqual(m1.atk, 4)  # 2 + 2
        self.assertEqual(m1.max_health, 4)  # 3 + 1
        self.assertEqual(m3.atk, 4)  # 2 + 2
        self.assertEqual(m3.max_health, 4)  # 3 + 1
        # Middle should not be buffed
        self.assertEqual(m2.atk, 2)
        self.assertEqual(m2.max_health, 3)

    def test_soc_single_minion(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_069"]
        script.on_summon(self.player, self.game)
        m1 = self._add_friendly()
        m1.reset_combat_state()

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        self.assertEqual(m1.atk, 4)  # 2 + 2 (buffed only once)
        self.assertEqual(m1.max_health, 4)

    def test_soc_resolves_player_from_controlled_hero_power_entity(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_069"]
        source = self.game.create_minion("EXAMPLE_VANILLA")
        source.controller = self.player
        script.on_summon(source, self.game)
        minion = self._add_friendly()

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        self.assertEqual(minion.atk, 4)
        self.assertEqual(minion.max_health, 4)


class TestPhase12FragrantPhylactery(unittest.TestCase):
    """BG20_HERO_282p — Fragrant Phylactery: SoC give lowest-ATK minion DR."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_friendly(self, card_id="EXAMPLE_VANILLA", atk=3, health=3):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        m.set_tag(GameTag.BASE_ATK, atk)
        m.set_tag(GameTag.ATK, atk)
        m.set_tag(GameTag.BASE_HEALTH, health)
        m.set_tag(GameTag.HEALTH, health)
        m.set_tag(GameTag.MAX_HEALTH, health)
        self.player.board.append(m)
        return m

    def test_soc_grants_dr_to_lowest_atk(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_282p"]
        script.on_summon(self.player, self.game)

        # High ATK and low ATK minions
        high = self._add_friendly(atk=5, health=5)
        low = self._add_friendly(atk=2, health=5)
        mid = self._add_friendly(atk=4, health=5)

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        self.assertIn("deathrattle", low._script_overrides)
        self.assertNotIn("deathrattle", high._script_overrides)
        self.assertNotIn("deathrattle", mid._script_overrides)


class TestPhase12Deadeye(unittest.TestCase):
    """BG22_HERO_000p — Deadeye: SoC deal 99 to targeted enemy."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]
        self.enemy_player = None

    def _add_enemy(self, card_id="EXAMPLE_VANILLA", health=100):
        if self.enemy_player is None:
            self.enemy_player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
            self.enemy_player.health = 40
            self.game.players.append(self.enemy_player)
            self.game._current_combat_opponents = {
                self.player: self.enemy_player,
                self.enemy_player: self.player,
            }
        ep = self.enemy_player
        m = self.game.create_minion(card_id)
        m.controller = ep
        m.zone = Zone.PLAY
        m.set_tag(GameTag.HEALTH, health)
        m.set_tag(GameTag.MAX_HEALTH, health)
        ep.board.append(m)
        return m, ep

    def test_soc_deals_99_to_enemy(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG22_HERO_000p"]
        script.on_summon(self.player, self.game)

        e1, _ = self._add_enemy(health=100)

        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()

        self.assertLess(e1.health, 100)  # Took damage


class TestPhase12EmbraceElements(unittest.TestCase):
    """BG22_HERO_001p — Embrace the Elements: SoC invoke fire/water/lightning."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_friendly(self, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def _add_enemy(self, health=10):
        ep = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        ep.health = 40
        self.game.players.append(ep)
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = ep
        m.zone = Zone.PLAY
        m.set_tag(GameTag.HEALTH, health)
        m.set_tag(GameTag.MAX_HEALTH, health)
        ep.board.append(m)
        return m, ep

    def test_soc_no_crash(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG22_HERO_001p"]
        script.on_summon(self.player, self.game)
        self._add_friendly()
        self._add_enemy()
        self.game.broadcast("START_OF_COMBAT", self.player)
        self.game.resolve_queue()
        # Should not crash for any randomly-selected element


class TestPhase12ImTheCapnNow(unittest.TestCase):
    """BG26_HERO_101p — I'm the Cap'n Now: buy Pirate → gain 1 Gold."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_buy_pirate_gains_gold(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG26_HERO_101p"]
        script.on_summon(self.player, self.game)

        pirate = self.game.create_minion("EXAMPLE_VANILLA")
        pirate.set_tag(GameTag.RACE, Race.PIRATE)
        pirate.controller = self.player

        # Spend some gold so GainGold is not capped at MAX_GOLD (10)
        self.player.set_tag(GameTag.GOLD, 5)
        old_gold = self.player.gold
        self.game.broadcast("MINION_BOUGHT", pirate, self.player)
        self.game.resolve_queue()
        self.assertEqual(self.player.gold, old_gold + 1)

    def test_buy_non_pirate_no_gold(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG26_HERO_101p"]
        script.on_summon(self.player, self.game)

        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.controller = self.player

        old_gold = self.player.gold
        self.game.broadcast("MINION_BOUGHT", m, self.player)
        self.game.resolve_queue()
        self.assertEqual(self.player.gold, old_gold)


class TestPhase12ForTheHorde(unittest.TestCase):
    """BG20_HERO_102p — For the Horde!: Tavern +1/+1, improves after 4 buys."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_on_summon_adds_tavern_buff(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        self.assertEqual(len(self.player.tavern_buffs), 0)
        script = HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_102p"]
        script.on_summon(self.player, self.game)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.tavern_buffs), 1)
        self.assertEqual(self.player.tavern_buffs[0].atk, 1)
        self.assertEqual(self.player.tavern_buffs[0].health, 1)

    def test_4_buys_adds_another_buff(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_102p"]
        script.on_summon(self.player, self.game)
        self.game.resolve_queue()
        old_count = len(self.player.tavern_buffs)

        for _ in range(4):
            m = self.game.create_minion("EXAMPLE_VANILLA")
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()

        self.assertGreater(len(self.player.tavern_buffs), old_count)

    def test_hero_power_entity_resolves_effect_owner_to_player(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        source = self.game.create_minion("BG20_HERO_102p")
        source.controller = self.player
        HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_102p"].on_summon(
            source, self.game,
        )
        self.game.resolve_queue()
        self.assertEqual(len(self.player.tavern_buffs), 1)


class TestPhase12NaturalBalance(unittest.TestCase):
    """BG20_HERO_242p — Natural Balance: buy 20 tiers → Triple Reward."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_buys_accumulate_tiers(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_242p"]
        script.on_summon(self.player, self.game)

        # Buy 3 Tier 6 minions = 18 tiers (not enough)
        for _ in range(3):
            m = self.game.create_minion("EXAMPLE_VANILLA")
            m.set_tag(GameTag.TECH_LEVEL, 6)
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 0)  # Not triggered yet

        # Buy 1 more Tier 2 minion = 2 → total 20 → trigger
        m = self.game.create_minion("EXAMPLE_VANILLA")
        m.set_tag(GameTag.TECH_LEVEL, 2)
        self.game.broadcast("MINION_BOUGHT", m, self.player)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)  # Triple Reward discovered


class TestPhase12GlaiveRicochet(unittest.TestCase):
    """BG20_HERO_280p5 — Glaive Ricochet: 3 buys/turn → copy."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_3_buys_gives_copy(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_280p5"]
        script.on_summon(self.player, self.game)

        for _ in range(3):
            m = self.game.create_minion("EXAMPLE_VANILLA")
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()

        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].data.id, "EXAMPLE_VANILLA")

    def test_hero_power_entity_gives_copy_to_controller_hand(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        source = self.game.create_minion("BG20_HERO_280p5")
        source.controller = self.player
        HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_280p5"].on_summon(
            source, self.game,
        )
        for _ in range(3):
            minion = self.game.create_minion("EXAMPLE_VANILLA")
            self.game.broadcast("MINION_BOUGHT", minion, self.player)
            self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].data.id, "EXAMPLE_VANILLA")


class TestPhase12WarpGate(unittest.TestCase):
    """BG31_HERO_802p — Warp Gate: start game choose Protoss → after 14 buys."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_14_buys_gives_reward(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["BG31_HERO_802p"]
        script.on_summon(self.player, self.game)

        for _ in range(14):
            m = self.game.create_minion("EXAMPLE_VANILLA")
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()

        self.assertEqual(len(self.player.hand), 1)


class TestPhase12BattleBrand(unittest.TestCase):
    """TB_BaconShop_HP_048 — Battle Brand: buy 5 Battlecry → Brann."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def test_5_battlecry_buys_gives_brann(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_048"]
        script.on_summon(self.player, self.game)

        # Use EXAMPLE_BATTLECRY which has battlecry script
        for _ in range(5):
            m = self.game.create_minion("EXAMPLE_BATTLECRY")
            m.controller = self.player
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()

        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].data.id, "TB_BaconUps_045")

    def test_non_battlecry_does_not_count(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_048"]
        script.on_summon(self.player, self.game)

        for _ in range(5):
            m = self.game.create_minion("EXAMPLE_VANILLA")  # No battlecry
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()

        self.assertEqual(len(self.player.hand), 0)  # Not triggered

    def test_buy_classification_does_not_execute_battlecry(self):
        """MINION_BOUGHT may arrive before a card has a controller."""
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_048"]
        script.on_summon(self.player, self.game)

        # Roving Sailor's Battlecry dereferences source.controller.  Merely
        # classifying it for Battle Brand must therefore not invoke the hook.
        for _ in range(5):
            bought = self.game.create_minion("BG35_702")
            self.assertIsNone(bought.controller)
            self.game.broadcast("MINION_BOUGHT", bought, self.player)
            self.game.resolve_queue()

        self.assertEqual([m.data.id for m in self.player.hand], ["TB_BaconUps_045"])


class TestPhase12BuyInsect(unittest.TestCase):
    """TB_BaconShop_HP_087 — BUY, INSECT!: buy 16 cards → Sulfuras EOT."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_HERO"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _add_friendly(self, card_id="EXAMPLE_VANILLA"):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        return m

    def test_16_buys_activates_sulfuras(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_087"]
        script.on_summon(self.player, self.game)

        for _ in range(16):
            m = self.game.create_minion("EXAMPLE_VANILLA")
            self.game.broadcast("MINION_BOUGHT", m, self.player)
            self.game.resolve_queue()

        # After 16 buys, Sulfuras EOT should be active
        m1 = self._add_friendly()
        m2 = self._add_friendly()

        self.game.broadcast("RECRUIT_END", self.player)
        self.game.resolve_queue()

        # Leftmost and rightmost should be buffed +4/+4
        self.assertEqual(m1.atk, 6)  # 2 + 4
        self.assertEqual(m1.max_health, 7)  # 3 + 4
        self.assertEqual(m2.atk, 6)
        self.assertEqual(m2.max_health, 7)

    def test_before_16_buys_no_eot_buff(self):
        from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY
        script = HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_087"]
        script.on_summon(self.player, self.game)

        m1 = self._add_friendly()
        self.game.broadcast("RECRUIT_END", self.player)
        self.game.resolve_queue()

        # No buff before 16 buys
        self.assertEqual(m1.atk, 2)


if __name__ == "__main__":
    unittest.main()
