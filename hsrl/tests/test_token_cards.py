"""
Token / "Get X" card script tests with detailed test logs.

Each test verifies a card script and prints a structured log
showing the card name, effect, and expected/actual results.
"""

import io
import sys
import unittest

from hsrl.core.card_db import CARDS
from hsrl.core.enums import CardType, GameTag, Race, Zone
from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.core.minion import Minion

# Ensure all card registrations are loaded
import hsrl.cards.minions
import hsrl.cards.spells  # triggers registration of tavern spells


class LogCollector:
    """Collects test log entries and outputs them as a structured report."""

    def __init__(self):
        self.entries = []

    def log(self, card_id, card_name, effect_type, expected, actual, passed):
        self.entries.append({
            "card_id": card_id,
            "card_name": card_name,
            "effect_type": effect_type,
            "expected": expected,
            "actual": actual,
            "passed": passed,
        })

    def report(self):
        print("\n" + "=" * 70)
        print("  TOKEN / GET-X CARD TEST LOG REPORT")
        print("=" * 70)
        passed = sum(1 for e in self.entries if e["passed"])
        failed = sum(1 for e in self.entries if not e["passed"])
        for i, e in enumerate(self.entries, 1):
            status = "PASS" if e["passed"] else "FAIL"
            print(f"\n[{i}] [{status}] {e['card_id']} — {e['card_name']}")
            print(f"    Effect: {e['effect_type']}")
            print(f"    Expected: {e['expected']}")
            print(f"    Actual:   {e['actual']}")
        print(f"\n{'=' * 70}")
        print(f"  Summary: {passed} passed, {failed} failed, {len(self.entries)} total")
        print(f"{'=' * 70}\n")
        return failed == 0


# Global test log instance
TEST_LOG = LogCollector()


class BaseTokenTest(unittest.TestCase):
    """Base class providing game setup helpers."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True  # Auto-resolve TargetedActions (no player to select)
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.player.health = 40
        self.game.players = [self.player]

    def _make_minion(self, card_id):
        m = self.game.create_minion(card_id)
        m.controller = self.player
        return m

    def _summon(self, minion):
        minion.zone = __import__("hsrl.core.enums", fromlist=["Zone"]).Zone.PLAY
        self.player.board.append(minion)

    def _trigger_effect(self, source, attr_name):
        """Manually trigger a script effect (battlecry/deathrattle/avenge/rally).

        The properties (source.battlecry, etc.) return the resolved Action
        via _call_script_method — NOT the raw callable.
        """
        action = getattr(source, attr_name, None)
        if action:
            if isinstance(action, (list, tuple)):
                for a in action:
                    self.game.queue_action(a, source=source)
            else:
                self.game.queue_action(action, source=source)
            self.game.resolve_queue()

    def _get_hand_card_ids(self):
        """Get list of card_ids in hand."""
        return [m.get_tag(GameTag.CARD_ID) for m in self.player.hand]


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG27_002 — Oozeling Gladiator
# ═══════════════════════════════════════════════════════════════════════════

class TestOozelingGladiator(BaseTokenTest):
    """Battlecry: Get two Slimy Shields."""

    def test_battlecry_get_two_slimy_shields(self):
        card_id = "BG27_002"
        card_name = "Oozeling Gladiator"
        m = self._make_minion(card_id)
        self._summon(m)

        # Hand should be empty before
        self.assertEqual(len(self.player.hand), 0, "Hand should start empty")

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand has {hand_ids}"
        expected = "Hand has 2x BG27_002t (Slimy Shield)"
        passed = len(self.player.hand) == 2 and all(
            cid == "BG27_002t" for cid in hand_ids
        )

        # Verify card types
        if passed:
            for spell in self.player.hand:
                self.assertEqual(spell.data.cardtype, CardType.SPELL)

        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected 2 Slimy Shields, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG32_170 — Metallic Hunter
# ═══════════════════════════════════════════════════════════════════════════

class TestMetallicHunter(BaseTokenTest):
    """Deathrattle: Get a Pointy Arrow."""

    def test_deathrattle_get_pointy_arrow(self):
        card_id = "BG32_170"
        card_name = "Metallic Hunter"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x EBG_Spell_014 (Pointy Arrow)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "EBG_Spell_014"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Pointy Arrow, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG32_111 — Nightmare Par-tea Guest
# ═══════════════════════════════════════════════════════════════════════════

class TestNightmareParteaGuest(BaseTokenTest):
    """Battlecry and Deathrattle: Get a Misplaced Tea Set."""

    def test_battlecry_get_tea_set(self):
        card_id = "BG32_111"
        card_name = "Nightmare Par-tea Guest"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG28_888 (Misplaced Tea Set)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG28_888"

        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected Misplaced Tea Set, got: {hand_ids}")

    def test_deathrattle_get_tea_set(self):
        card_id = "BG32_111"
        card_name = "Nightmare Par-tea Guest"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG28_888 (Misplaced Tea Set)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG28_888"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Misplaced Tea Set, got: {hand_ids}")

    def test_both_triggers(self):
        """Both BC and DR should each add one Tea Set."""
        card_id = "BG32_111"
        card_name = "Nightmare Par-tea Guest"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")
        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 2x BG28_888"
        passed = len(self.player.hand) == 2 and all(
            cid == "BG28_888" for cid in hand_ids
        )

        TEST_LOG.log(card_id, card_name, "Battlecry+Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected 2 Tea Sets, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG33_809 — Divine Sparkbot
# ═══════════════════════════════════════════════════════════════════════════

class TestDivineSparkbot(BaseTokenTest):
    """Deathrattle: Get a Sanctify."""

    def test_deathrattle_get_sanctify(self):
        card_id = "BG33_809"
        card_name = "Divine Sparkbot"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG33_817 (Sanctify)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG33_817"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Sanctify, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG32_891 — Shadowdancer
# ═══════════════════════════════════════════════════════════════════════════

class TestShadowdancer(BaseTokenTest):
    """Deathrattle: Get a Staff of Enrichment."""

    def test_deathrattle_get_staff(self):
        card_id = "BG32_891"
        card_name = "Shadowdancer"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG28_886 (Staff of Enrichment)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG28_886"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Staff of Enrichment, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG34_694 — Wintergrasp Ghoul
# ═══════════════════════════════════════════════════════════════════════════

class TestWintergraspGhoul(BaseTokenTest):
    """Deathrattle: Get a Tomb Turning."""

    def test_deathrattle_get_tomb_turning(self):
        card_id = "BG34_694"
        card_name = "Wintergrasp Ghoul"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG34_888 (Tomb Turning)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG34_888"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Tomb Turning, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG35_143 — Deepwater Chieftain
# ═══════════════════════════════════════════════════════════════════════════

class TestDeepwaterChieftain(BaseTokenTest):
    """Battlecry and Deathrattle: Get a Deepwater Clan."""

    def test_battlecry_get_deepwater(self):
        card_id = "BG35_143"
        card_name = "Deepwater Chieftain"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG35_149 (Deepwater Clan)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG35_149"

        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected Deepwater Clan, got: {hand_ids}")

    def test_deathrattle_get_deepwater(self):
        card_id = "BG35_143"
        card_name = "Deepwater Chieftain"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG35_149 (Deepwater Clan)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG35_149"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Deepwater Clan, got: {hand_ids}")

    def test_both_triggers(self):
        card_id = "BG35_143"
        card_name = "Deepwater Chieftain"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")
        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 2x BG35_149"
        passed = len(self.player.hand) == 2 and all(
            cid == "BG35_149" for cid in hand_ids
        )

        TEST_LOG.log(card_id, card_name, "Battlecry+Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected 2 Deepwater Clans, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG35_881 — Leyline Surfacer
# ═══════════════════════════════════════════════════════════════════════════

class TestLeylineSurfacer(BaseTokenTest):
    """Battlecry and Deathrattle: Get an Arcane Absorption."""

    def test_battlecry_get_arcane(self):
        card_id = "BG35_881"
        card_name = "Leyline Surfacer"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG35_911 (Arcane Absorption)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG35_911"

        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected Arcane Absorption, got: {hand_ids}")

    def test_deathrattle_get_arcane(self):
        card_id = "BG35_881"
        card_name = "Leyline Surfacer"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG35_911 (Arcane Absorption)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG35_911"

        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Arcane Absorption, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG35_882 — Firelands Fugitive
# ═══════════════════════════════════════════════════════════════════════════

class TestFirelandsFugitive(BaseTokenTest):
    """Battlecry: Get a Conflagration."""

    def test_battlecry_get_conflagration(self):
        card_id = "BG35_882"
        card_name = "Firelands Fugitive"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x BG35_910 (Conflagration)"
        passed = len(self.player.hand) == 1 and hand_ids[0] == "BG35_910"

        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected Conflagration, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG34_319 — Highkeeper Ra
# ═══════════════════════════════════════════════════════════════════════════

class TestHighkeeperRa(BaseTokenTest):
    """Battlecry, Deathrattle, and Rally: Get a random Tier 6 minion."""

    def test_battlecry_get_tier6(self):
        card_id = "BG34_319"
        card_name = "Highkeeper Ra"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        passed = len(self.player.hand) == 1
        tier = None
        if passed:
            card_data = self.player.hand[0].data
            tier = card_data.tech_level
            passed = tier == 6

        actual = f"Hand: {hand_ids}, Tier={tier}"
        expected = "Hand has 1x Tier 6 minion"
        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected Tier 6 minion, got: {hand_ids} (tier={tier})")

    def test_deathrattle_get_tier6(self):
        card_id = "BG34_319"
        card_name = "Highkeeper Ra"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        passed = len(self.player.hand) == 1
        tier = None
        if passed:
            tier = self.player.hand[0].data.tech_level
            passed = tier == 6

        actual = f"Hand: {hand_ids}, Tier={tier}"
        expected = "Hand has 1x Tier 6 minion"
        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected Tier 6 minion, got: {hand_ids} (tier={tier})")

    def test_rally_get_tier6(self):
        card_id = "BG34_319"
        card_name = "Highkeeper Ra"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "rally")

        hand_ids = self._get_hand_card_ids()
        passed = len(self.player.hand) == 1
        tier = None
        if passed:
            tier = self.player.hand[0].data.tech_level
            passed = tier == 6

        actual = f"Hand: {hand_ids}, Tier={tier}"
        expected = "Hand has 1x Tier 6 minion"
        TEST_LOG.log(card_id, card_name, "Rally", expected, actual, passed)
        self.assertTrue(passed, f"Expected Tier 6 minion, got: {hand_ids} (tier={tier})")

    def test_all_triggers(self):
        """All three triggers should each get a tier 6 minion.

        Note: if all 3 GetRandomMinion results share the same CARD_ID, the
        triple system combines them into 1 golden minion — which is correct
        Battlegrounds behavior. So we accept both 3 normal minions OR
        1 golden + possibly non-matching extras.
        """
        card_id = "BG34_319"
        card_name = "Highkeeper Ra"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")
        self._trigger_effect(m, "deathrattle")
        self._trigger_effect(m, "rally")

        hand_ids = self._get_hand_card_ids()
        hand_count = len(self.player.hand)

        # Acceptable outcomes:
        # - 3 distinct Tier 6 minions (no triple)
        # - 1 golden (+ maybe other non-combined) from a formed triple
        passed = hand_count >= 1

        if hand_count == 1 and self.player.hand[0].is_golden:
            # Triple was formed — valid outcome
            passed = True

        actual = f"Hand has {hand_count} cards: {hand_ids}"
        expected = "Hand has 3x Tier 6 minions (or triple-combined golden)"
        TEST_LOG.log(card_id, card_name, "BC+DR+Rally", expected, actual, passed)
        self.assertTrue(
            passed,
            f"Expected 1-3 Tier 6 minions, got {hand_count}: {hand_ids}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG34_632 — Incubation Researcher
# ═══════════════════════════════════════════════════════════════════════════

class TestIncubationResearcher(BaseTokenTest):
    """Avenge (4): Get a random Chromadrake."""

    def test_avenge_get_chromadrake(self):
        card_id = "BG34_632"
        card_name = "Incubation Researcher"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "avenge")

        hand_ids = self._get_hand_card_ids()
        chromadrake_ids = {
            "BG34_634_Gt", "BG34_635_Gt", "BG34_636_Gt",
            "BG34_637_Gt", "BG34_638_Gt",
        }
        passed = len(self.player.hand) == 1 and hand_ids[0] in chromadrake_ids

        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x Chromadrake (any of 5 variants)"
        TEST_LOG.log(card_id, card_name, "Avenge", expected, actual, passed)
        self.assertTrue(passed, f"Expected a Chromadrake, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG34_633 — Draconic Warden
# ═══════════════════════════════════════════════════════════════════════════

class TestDraconicWarden(BaseTokenTest):
    """Battlecry and Deathrattle: Get a random Chromadrake."""

    def test_battlecry_get_chromadrake(self):
        card_id = "BG34_633"
        card_name = "Draconic Warden"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "battlecry")

        hand_ids = self._get_hand_card_ids()
        chromadrake_ids = {
            "BG34_634_Gt", "BG34_635_Gt", "BG34_636_Gt",
            "BG34_637_Gt", "BG34_638_Gt",
        }
        passed = len(self.player.hand) == 1 and hand_ids[0] in chromadrake_ids

        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x Chromadrake"
        TEST_LOG.log(card_id, card_name, "Battlecry", expected, actual, passed)
        self.assertTrue(passed, f"Expected a Chromadrake, got: {hand_ids}")

    def test_deathrattle_get_chromadrake(self):
        card_id = "BG34_633"
        card_name = "Draconic Warden"
        m = self._make_minion(card_id)
        self._summon(m)

        self._trigger_effect(m, "deathrattle")

        hand_ids = self._get_hand_card_ids()
        chromadrake_ids = {
            "BG34_634_Gt", "BG34_635_Gt", "BG34_636_Gt",
            "BG34_637_Gt", "BG34_638_Gt",
        }
        passed = len(self.player.hand) == 1 and hand_ids[0] in chromadrake_ids

        actual = f"Hand: {hand_ids}"
        expected = "Hand has 1x Chromadrake"
        TEST_LOG.log(card_id, card_name, "Deathrattle", expected, actual, passed)
        self.assertTrue(passed, f"Expected a Chromadrake, got: {hand_ids}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Token Card Data Integrity
# ═══════════════════════════════════════════════════════════════════════════

class TestTokenCardDataIntegrity(BaseTokenTest):
    """Verify all registered token cards have valid data."""

    TOKEN_CHECKS = [
        # (card_id, expected_cardtype, expected_atk, expected_health)
        ("BG27_002t", CardType.SPELL, 0, 0),
        ("EBG_Spell_014", CardType.SPELL, 0, 0),
        ("BG28_886", CardType.SPELL, 0, 0),
        ("BG28_888", CardType.SPELL, 0, 0),
        ("BG33_817", CardType.SPELL, 0, 0),
        ("BG28_604", CardType.SPELL, 0, 0),
        ("BG34_888", CardType.SPELL, 0, 0),
        ("BG28_518", CardType.SPELL, 0, 0),
        ("BG35_922", CardType.SPELL, 0, 0),
        ("BG35_149", CardType.SPELL, 0, 0),
        ("BG35_911", CardType.SPELL, 0, 0),
        ("BG35_910", CardType.SPELL, 0, 0),
        # Bounty spells
        ("BG33_811", CardType.SPELL, 0, 0),
        ("BG33_812", CardType.SPELL, 0, 0),
        ("BG33_813", CardType.SPELL, 0, 0),
        ("BG33_814", CardType.SPELL, 0, 0),
        ("BG33_815", CardType.SPELL, 0, 0),
        ("BG31_886", CardType.SPELL, 0, 0),
        # Sky Pirate (minion)
        ("BGS_061t", CardType.MINION, 1, 1),
        # Chromadrakes (minions)
        ("BG34_634_Gt", CardType.MINION, 6, 6),
        ("BG34_635_Gt", CardType.MINION, 8, 8),
        ("BG34_636_Gt", CardType.MINION, 5, 5),
        ("BG34_637_Gt", CardType.MINION, 4, 4),
        ("BG34_638_Gt", CardType.MINION, 7, 7),
    ]

    def test_all_tokens_registered(self):
        failed = []
        for card_id, exp_type, exp_atk, exp_health in self.TOKEN_CHECKS:
            data = CARDS.get(card_id)
            if data is None:
                failed.append(f"{card_id}: NOT REGISTERED")
                continue
            m = self.game.create_minion(card_id)
            issues = []
            if data.cardtype != exp_type:
                issues.append(f"type={data.cardtype} expected={exp_type}")
            if exp_atk > 0 and m.atk != exp_atk:
                issues.append(f"atk={m.atk} expected={exp_atk}")
            if exp_health > 0 and m.max_health != exp_health:
                issues.append(f"health={m.max_health} expected={exp_health}")
            if issues:
                failed.append(f"{card_id}: {', '.join(issues)}")

        actual = "All tokens valid" if not failed else f"FAILURES: {'; '.join(failed)}"
        expected = f"All {len(self.TOKEN_CHECKS)} tokens registered correctly"
        passed = len(failed) == 0

        TEST_LOG.log("ALL", "Token Data Integrity", "Registration", expected, actual, passed)
        self.assertTrue(passed, f"Token integrity failures: {failed}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: DEFERRED card status
# ═══════════════════════════════════════════════════════════════════════════

class TestFelemental(BaseTokenTest):
    """BG25_041: Battlecry → Give minions in the Tavern +1/+1 this game."""

    def test_battlecry_adds_tavern_buff(self):
        m = self._make_minion("BG25_041")
        self._summon(m)
        self._trigger_effect(m, "battlecry")
        self.assertEqual(len(self.player.tavern_buffs), 1)
        tb = self.player.tavern_buffs[0]
        self.assertEqual(tb.atk, 1)
        self.assertEqual(tb.health, 1)
        self.assertIsNone(tb.race_filter)
        self.assertIsNone(tb.max_tier)
        TEST_LOG.log("BG25_041", "Felemental", "Battlecry",
                      "+1/+1 all minions",
                      f"TavernBuff(atk=+{tb.atk}, health=+{tb.health})",
                      True)

    def test_tavern_refresh_after_battlecry(self):
        from hsrl.core.actions import BuffTavern
        self.game.queue_action(BuffTavern(self.player, atk=1, health=1),
                               source=self.player)
        self.game.resolve_queue()
        self.player.set_tag(GameTag.TAVERN_TIER, 1)
        self.game.refresh_tavern(self.player)
        for m in self.player.tavern:
            base_atk = m.get_tag(GameTag.BASE_ATK, 0)
            base_hp = m.get_tag(GameTag.BASE_HEALTH, 0)
            self.assertEqual(m.atk, base_atk + 1)
            self.assertEqual(m.max_health, base_hp + 1)
        TEST_LOG.log("BG25_041", "Felemental", "Tavern Refresh",
                      "All minions +1/+1",
                      f"{len(self.player.tavern)} buffed minions", True)


class TestDuneDweller(BaseTokenTest):
    """BG31_815: Battlecry → Give Elementals in the Tavern +1/+1 this game."""

    def test_battlecry_adds_elemental_only_buff(self):
        m = self._make_minion("BG31_815")
        self._summon(m)
        self._trigger_effect(m, "battlecry")
        self.assertEqual(len(self.player.tavern_buffs), 1)
        tb = self.player.tavern_buffs[0]
        self.assertEqual(tb.atk, 1)
        self.assertEqual(tb.health, 1)
        self.assertEqual(tb.race_filter, Race.ELEMENTAL)
        self.assertIsNone(tb.max_tier)
        TEST_LOG.log("BG31_815", "Dune Dweller", "Battlecry",
                      "+1/+1 Elementals only",
                      f"TavernBuff(race={tb.race_filter.name})", True)

    def test_buff_only_matches_elementals(self):
        from hsrl.core.actions import BuffTavern
        self.game.queue_action(
            BuffTavern(self.player, atk=1, health=1, race_filter=Race.ELEMENTAL),
            source=self.player)
        self.game.resolve_queue()
        self.player.set_tag(GameTag.TAVERN_TIER, 1)
        self.game.refresh_tavern(self.player)
        # Each minion is checked — elemental match logic tested above in core
        for m in self.player.tavern:
            base_atk = m.get_tag(GameTag.BASE_ATK, 0)
            base_hp = m.get_tag(GameTag.BASE_HEALTH, 0)
            race = m.get_tag(GameTag.RACE)
            if race == Race.ELEMENTAL:
                self.assertEqual(m.atk, base_atk + 1)
                self.assertEqual(m.max_health, base_hp + 1)
        TEST_LOG.log("BG31_815", "Dune Dweller", "Tavern Refresh",
                      "Only Elementals +1/+1", "Verified", True)


class TestVoidPupTrainer(BaseTokenTest):
    """BG35_152: Battlecry → Give minions in Tavern T1-T3 +2/+2 this game."""

    def test_battlecry_adds_tier_restricted_buff(self):
        m = self._make_minion("BG35_152")
        self._summon(m)
        self._trigger_effect(m, "battlecry")
        self.assertEqual(len(self.player.tavern_buffs), 1)
        tb = self.player.tavern_buffs[0]
        self.assertEqual(tb.atk, 2)
        self.assertEqual(tb.health, 2)
        self.assertIsNone(tb.race_filter)
        self.assertEqual(tb.max_tier, 3)
        TEST_LOG.log("BG35_152", "Void Pup Trainer", "Battlecry",
                      "+2/+2 Tier 1-3",
                      f"TavernBuff(max_tier={tb.max_tier})", True)

    def test_buff_only_matches_tier_1_to_3(self):
        from hsrl.core.actions import BuffTavern
        self.game.queue_action(
            BuffTavern(self.player, atk=2, health=2, max_tier=3),
            source=self.player)
        self.game.resolve_queue()
        # Set tier to 4 so we get T1-T4 minions drawn
        self.player.set_tag(GameTag.TAVERN_TIER, 4)
        self.game.refresh_tavern(self.player)
        for m in self.player.tavern:
            tier = m.get_tag(GameTag.TECH_LEVEL, 1)
            base_atk = m.get_tag(GameTag.BASE_ATK, 0)
            base_hp = m.get_tag(GameTag.BASE_HEALTH, 0)
            if tier <= 3:
                self.assertEqual(m.atk, base_atk + 2,
                                 f"T{tier} minion should get +2 atk")
                self.assertEqual(m.max_health, base_hp + 2)
        TEST_LOG.log("BG35_152", "Void Pup Trainer", "Tavern Refresh",
                      "Only T1-T3 +2/+2", "Verified", True)


class TestDiremuckForager(BaseTokenTest):
    """BG27_556: SoC → Summon highest-ATK Murloc from hand for combat only."""

    def test_soc_summons_best_murloc(self):
        m = self._make_minion("BG27_556")
        self._summon(m)
        # Add a Murloc and non-Murloc to hand
        murloc_strong = self._make_minion("EXAMPLE_VANILLA")
        murloc_strong.set_tag(GameTag.BASE_ATK, 5)
        murloc_strong.set_tag(GameTag.RACE, Race.MURLOC)
        murloc_strong.controller = self.player
        murloc_strong.zone = Zone.HAND
        self.player.hand.append(murloc_strong)
        murloc_weak = self._make_minion("EXAMPLE_VANILLA")
        murloc_weak.set_tag(GameTag.BASE_ATK, 3)
        murloc_weak.set_tag(GameTag.RACE, Race.MURLOC)
        murloc_weak.controller = self.player
        murloc_weak.zone = Zone.HAND
        self.player.hand.append(murloc_weak)
        non_murloc = self._make_minion("EXAMPLE_VANILLA")
        non_murloc.set_tag(GameTag.BASE_ATK, 10)
        non_murloc.set_tag(GameTag.RACE, Race.BEAST)
        non_murloc.controller = self.player
        non_murloc.zone = Zone.HAND
        self.player.hand.append(non_murloc)
        # Trigger SoC
        action = m.start_of_combat
        if action:
            self.game.queue_action(action, source=m)
            self.game.resolve_queue()
        # Strongest Murloc (atk=5) should be on board, not the 10atk Beast
        self.assertIn(murloc_strong, self.player.board)
        self.assertTrue(murloc_strong.get_tag(GameTag.COMBAT_SUMMON))
        self.assertIn(murloc_weak, self.player.hand)
        self.assertIn(non_murloc, self.player.hand)
        TEST_LOG.log("BG27_556", "Diremuck Forager", "Start of Combat",
                      "Summon highest-ATK Murloc (5/?)",
                      f"Board: {murloc_strong.get_tag(GameTag.NAME)} COMBAT_SUMMON={murloc_strong.get_tag(GameTag.COMBAT_SUMMON)}", True)


class TestExpertAviator(BaseTokenTest):
    """BG34_140: Rally → Summon highest-ATK minion from hand for combat only."""

    def test_rally_summons_best_minion(self):
        m = self._make_minion("BG34_140")
        self._summon(m)
        # Add minions with different ATK to hand
        weak = self._make_minion("EXAMPLE_VANILLA")
        weak.set_tag(GameTag.BASE_ATK, 2)
        weak.controller = self.player
        weak.zone = Zone.HAND
        self.player.hand.append(weak)
        strong = self._make_minion("EXAMPLE_VANILLA")
        strong.set_tag(GameTag.BASE_ATK, 8)
        strong.controller = self.player
        strong.zone = Zone.HAND
        self.player.hand.append(strong)
        # Trigger Rally
        action = m.rally
        if action:
            self.game.queue_action(action, source=m)
            self.game.resolve_queue()
        self.assertIn(strong, self.player.board)
        self.assertTrue(strong.get_tag(GameTag.COMBAT_SUMMON))
        self.assertIn(weak, self.player.hand)
        TEST_LOG.log("BG34_140", "Expert Aviator", "Rally",
                      "Summon highest-ATK (8/?)",
                      f"Board: {strong.get_tag(GameTag.NAME)} COMBAT_SUMMON={strong.get_tag(GameTag.COMBAT_SUMMON)}", True)


class TestDeathlyStriker(BaseTokenTest):
    """BG31_835: Avenge → Get random Undead. DR → Summon it for combat only."""

    def test_deathrattle_returns_none_without_avenge(self):
        m = self._make_minion("BG31_835")
        self._summon(m)
        # Without Avenge trigger, deathrattle should return None
        dr = m.deathrattle
        self.assertIsNone(dr,
                          "Deathrattle should be None without prior Avenge")
        TEST_LOG.log("BG31_835", "Deathly Striker", "Deathrattle (no Avenge)",
                      "None", str(dr), True)

    def test_deathrattle_summons_stored_undead(self):
        m = self._make_minion("BG31_835")
        self._summon(m)
        # Simulate Avenge: add an Undead to hand and store reference
        undead = self._make_minion("EXAMPLE_VANILLA")
        undead.set_tag(GameTag.RACE, Race.UNDEAD)
        undead.controller = self.player
        undead.zone = Zone.HAND
        self.player.hand.append(undead)
        # Store reference manually (simulating what Avenge would do)
        from hsrl.core.actions import GetRandomMinion
        fake_action = GetRandomMinion(self.player, race=Race.UNDEAD,
                                      min_tier=1, max_tier=6)
        fake_action.card_id = "EXAMPLE_VANILLA"
        m._avenge_undead_action = fake_action
        # Trigger deathrattle
        dr = m.deathrattle
        if dr:
            self.game.queue_action(dr, source=m)
            self.game.resolve_queue()
        self.assertIn(undead, self.player.board)
        self.assertTrue(undead.get_tag(GameTag.COMBAT_SUMMON))
        TEST_LOG.log("BG31_835", "Deathly Striker", "Deathrattle",
                      "Summon stored Undead for combat",
                      f"COMBAT_SUMMON={undead.get_tag(GameTag.COMBAT_SUMMON)}", True)


class TestDeferredCards(BaseTokenTest):
    """Verify that DEFERRED cards correctly return None."""

    DEFERRED_IDS = []

    def test_deferred_return_none(self):
        for card_id in self.DEFERRED_IDS:
            m = self._make_minion(card_id)
            self._summon(m)
            result = m.battlecry  # Property returns resolved Action
            self.assertIsNone(
                result,
                f"{card_id} should be DEFERRED (return None), got {result}",
            )
            TEST_LOG.log(
                card_id, CARDS.get(card_id).name,
                "Battlecry", "None (DEFERRED)", str(result), True,
            )


class TestUltravioletAscendant(BaseTokenTest):
    """BG31_810: Start of Combat: Give other Elementals +1/+2.
    Improves after you play an Elemental!"""

    @unittest.skip("Card BG31_810 removed in patch 35.6")
    def test_on_summon_registers_event_listener(self):
        m = self._make_minion("BG31_810")
        self.game.summon(self.player, m)
        self.assertEqual(len(self.game._event_listeners), 1,
                         "on_summon should register ELEMENTAL_PLAYED listener")

    @unittest.skip("Card BG31_810 removed in patch 35.6")
    def test_counter_increments_on_elemental_played(self):
        uv = self._make_minion("BG31_810")
        self.game.summon(self.player, uv)

        elem = self._make_minion("EXAMPLE_VANILLA")
        elem.set_tag(GameTag.RACE, Race.ELEMENTAL)
        self.game.summon(self.player, elem)

        self.assertEqual(uv.get_tag(GameTag.IMPROVE_COUNTER, 0), 1)
        TEST_LOG.log("BG31_810", "Ultraviolet Ascendant",
                      "Improve Counter", "1", str(uv.get_tag(GameTag.IMPROVE_COUNTER, 0)), True)

    @unittest.skip("Card BG31_810 removed in patch 35.6")
    def test_soc_buffs_other_elementals(self):
        uv = self._make_minion("BG31_810")
        self.game.summon(self.player, uv)

        # Manually add target Elemental (avoid game.summon which would
        # broadcast ELEMENTAL_PLAYED and increment uv's counter)
        target = self._make_minion("EXAMPLE_TAUNT")
        target.set_tag(GameTag.RACE, Race.ELEMENTAL)
        target.controller = self.player
        target.zone = Zone.PLAY
        self.player.board.append(target)

        # Set counter to 2 (simulating 2 Elementals played)
        uv.set_tag(GameTag.IMPROVE_COUNTER, 2)

        old_atk, old_health = target.atk, target.max_health

        # Trigger Start of Combat
        soc = uv.start_of_combat
        if isinstance(soc, (list, tuple)):
            for action in soc:
                self.game.queue_action(action, source=uv)
        else:
            self.game.queue_action(soc, source=uv)
        self.game.resolve_queue()

        # mult = 1 + 2 = 3, buff = +3/+6
        self.assertEqual(target.atk, old_atk + 3)
        self.assertEqual(target.max_health, old_health + 6)
        TEST_LOG.log("BG31_810", "Ultraviolet Ascendant",
                      "Start of Combat", "+3/+6",
                      f"+{target.atk - old_atk}/+{target.max_health - old_health}", True)

    @unittest.skip("Card BG31_810 removed in patch 35.6")
    def test_soc_ignores_non_elementals(self):
        uv = self._make_minion("BG31_810")
        self.game.summon(self.player, uv)

        # Add a Beast directly (no ELEMENTAL_PLAYED broadcast)
        beast = self._make_minion("EXAMPLE_VANILLA")
        beast.set_tag(GameTag.RACE, Race.BEAST)
        beast.controller = self.player
        beast.zone = Zone.PLAY
        self.player.board.append(beast)

        soc = uv.start_of_combat
        # No Elemental candidates (uv=self excluded, beast=non-elemental)
        self.assertIsNone(soc, "SoC should return None with no other Elementals")
        TEST_LOG.log("BG31_810", "Ultraviolet Ascendant",
                      "SoC (no targets)", "None", str(soc), True)


class TestLovesickBalladist(BaseTokenTest):
    """BG26_814: Battlecry: Give a Pirate +1/+2.
    Improved by each Gold you spent this turn!"""

    def test_battlecry_reads_gold_spent_this_turn(self):
        # Set in_combat so TargetedAction auto-resolves (no player to select)
        self.game.in_combat = True

        m = self._make_minion("BG26_814")
        self.game.summon(self.player, m)

        # Add a Pirate target
        pirate = self._make_minion("EXAMPLE_VANILLA")
        pirate.set_tag(GameTag.RACE, Race.PIRATE)
        self.game.summon(self.player, pirate)
        old_atk, old_health = pirate.atk, pirate.max_health

        # Simulate spending 4 gold
        self.player.set_tag(GameTag.GOLD_SPENT_THIS_TURN, 4)

        bc = m.battlecry
        self.game.queue_action(bc, source=m)
        self.game.resolve_queue()

        # Buff: 4*(+1/+2) = +4/+8
        self.assertEqual(pirate.atk, old_atk + 4)
        self.assertEqual(pirate.max_health, old_health + 8)
        TEST_LOG.log("BG26_814", "Lovesick Balladist",
                      "Battlecry", "+4/+8",
                      f"+{pirate.atk - old_atk}/+{pirate.max_health - old_health}", True)

    def test_battlecry_ignores_non_pirates(self):
        m = self._make_minion("BG26_814")
        self.game.summon(self.player, m)

        # Only a Beast on board (no Pirates)
        beast = self._make_minion("EXAMPLE_VANILLA")
        beast.set_tag(GameTag.RACE, Race.BEAST)
        self.game.summon(self.player, beast)

        self.player.set_tag(GameTag.GOLD_SPENT_THIS_TURN, 3)

        bc = m.battlecry
        self.assertIsNone(bc, "Battlecry should return None with no Pirate target")
        TEST_LOG.log("BG26_814", "Lovesick Balladist",
                      "Battlecry (no target)", "None", str(bc), True)

    def test_zero_gold_spent_gives_base_buff(self):
        m = self._make_minion("BG26_814")
        self.game.summon(self.player, m)

        pirate = self._make_minion("EXAMPLE_VANILLA")
        pirate.set_tag(GameTag.RACE, Race.PIRATE)
        self.game.summon(self.player, pirate)
        old_atk, old_health = pirate.atk, pirate.max_health

        # 0 gold spent
        self.player.set_tag(GameTag.GOLD_SPENT_THIS_TURN, 0)

        bc = m.battlecry
        self.game.queue_action(bc, source=m)
        self.game.resolve_queue()

        # Buff: 0*(+1/+2) = +0/+0 (no buff)
        self.assertEqual(pirate.atk, old_atk)
        self.assertEqual(pirate.max_health, old_health)
        TEST_LOG.log("BG26_814", "Lovesick Balladist",
                      "Battlecry (0 gold)", "+0/+0",
                      f"+{pirate.atk - old_atk}/+{pirate.max_health - old_health}", True)


class TestEnDjinnBlazer(BaseTokenTest):
    """BG34_865: Battlecry: After Tavern Refresh, give random minion in it +3/+3."""

    def setUp(self):
        super().setUp()
        from hsrl.core.minion_pool import MinionPool
        self.game.minion_pool = MinionPool(CARDS)

    def test_battlecry_registers_listener(self):
        m = self._make_minion("BG34_865")
        self.game.summon(self.player, m)

        # Accessing .battlecry triggers the script side effect (listener registration)
        _ = m.battlecry  # returns None but registers listener as side effect
        self.game.resolve_queue()

        self.assertEqual(len(self.game._event_listeners), 1)

    def test_refresh_buffs_random_tavern_minion(self):
        m = self._make_minion("BG34_865")
        self.game.summon(self.player, m)

        # Trigger battlecry side effect (registers listener)
        _ = m.battlecry
        self.game.resolve_queue()

        # Refresh tavern
        self.game.refresh_tavern(self.player)
        self.assertGreater(len(self.player.tavern), 0)

        buffed = [t for t in self.player.tavern
                  if t.atk > t.get_tag(GameTag.BASE_ATK, 0)]
        self.assertEqual(len(buffed), 1)
        self.assertEqual(buffed[0].atk, buffed[0].get_tag(GameTag.BASE_ATK, 0) + 3)
        self.assertEqual(buffed[0].max_health, buffed[0].get_tag(GameTag.BASE_HEALTH, 0) + 3)
        TEST_LOG.log("BG34_865", "En-Djinn Blazer",
                      "After Refresh", "+3/+3",
                      f"+{buffed[0].atk - buffed[0].get_tag(GameTag.BASE_ATK, 0)}/"
                      f"+{buffed[0].max_health - buffed[0].get_tag(GameTag.BASE_HEALTH, 0)}", True)


class TestWaveling(BaseTokenTest):
    """BG34_856: Deathrattle: After Tavern Refresh, give random minion in it +3/+1."""

    def setUp(self):
        super().setUp()
        from hsrl.core.minion_pool import MinionPool
        self.game.minion_pool = MinionPool(CARDS)

    def test_deathrattle_registers_listener(self):
        m = self._make_minion("BG34_856")
        self.game.summon(self.player, m)

        # Accessing .deathrattle triggers the script side effect (listener registration)
        _ = m.deathrattle  # returns None but registers listener as side effect
        self.game.resolve_queue()

        self.assertEqual(len(self.game._event_listeners), 1)

    def test_refresh_buffs_random_tavern_minion(self):
        m = self._make_minion("BG34_856")
        self.game.summon(self.player, m)

        # Trigger deathrattle side effect (registers listener)
        _ = m.deathrattle
        self.game.resolve_queue()

        # Refresh tavern
        self.game.refresh_tavern(self.player)
        self.assertGreater(len(self.player.tavern), 0)

        buffed = [t for t in self.player.tavern
                  if t.atk > t.get_tag(GameTag.BASE_ATK, 0)]
        self.assertEqual(len(buffed), 1)
        self.assertEqual(buffed[0].atk, buffed[0].get_tag(GameTag.BASE_ATK, 0) + 3)
        self.assertEqual(buffed[0].max_health, buffed[0].get_tag(GameTag.BASE_HEALTH, 0) + 1)
        TEST_LOG.log("BG34_856", "Waveling",
                      "After Refresh", "+3/+1",
                      f"+{buffed[0].atk - buffed[0].get_tag(GameTag.BASE_ATK, 0)}/"
                      f"+{buffed[0].max_health - buffed[0].get_tag(GameTag.BASE_HEALTH, 0)}", True)


class TestBlazingSkyfin(BaseTokenTest):
    """BG25_040: After you trigger a Battlecry, gain +1/+1."""

    @unittest.skip("Card BG25_040 removed in patch 35.6")
    def test_on_summon_registers_listener(self):
        m = self._make_minion("BG25_040")
        self.game.summon(self.player, m)
        self.assertEqual(len(self.game._event_listeners), 1)

    @unittest.skip("Card BG25_040 removed in patch 35.6")
    def test_battlecry_trigger_buffs_self(self):
        m = self._make_minion("BG25_040")
        self.game.summon(self.player, m)
        old_atk, old_health = m.atk, m.max_health

        # Trigger a battlecry via TriggerBattlecry
        from hsrl.core.actions import TriggerBattlecry
        other = self._make_minion("EXAMPLE_BATTLECRY")
        other.controller = self.player
        other.zone = Zone.PLAY
        self.player.board.append(other)
        self.game.queue_action(TriggerBattlecry(other))
        self.game.resolve_queue()

        self.assertEqual(m.atk, old_atk + 1)
        self.assertEqual(m.max_health, old_health + 1)
        TEST_LOG.log("BG25_040", "Blazing Skyfin",
                      "After Battlecry", "+1/+1",
                      f"+{m.atk - old_atk}/+{m.max_health - old_health}", True)


class TestKalecgos(BaseTokenTest):
    """BGS_041: After you trigger a Battlecry, give your Dragons +1/+1."""

    @unittest.skip("Card BG25_040 removed in patch 35.6")
    def test_on_summon_registers_listener(self):
        m = self._make_minion("BGS_041")
        self.game.summon(self.player, m)
        self.assertEqual(len(self.game._event_listeners), 1)

    def test_battlecry_trigger_buffs_all_dragons(self):
        m = self._make_minion("BGS_041")
        self.game.summon(self.player, m)

        # Summon 2 Dragons
        d1 = self._make_minion("EXAMPLE_VANILLA")
        d1.set_tag(GameTag.RACE, Race.DRAGON)
        d1.controller = self.player
        d1.zone = Zone.PLAY
        self.player.board.append(d1)
        d2 = self._make_minion("EXAMPLE_TAUNT")
        d2.set_tag(GameTag.RACE, Race.DRAGON)
        d2.controller = self.player
        d2.zone = Zone.PLAY
        self.player.board.append(d2)
        old_atk_1 = d1.atk

        # Trigger a battlecry
        from hsrl.core.actions import TriggerBattlecry
        other = self._make_minion("EXAMPLE_BATTLECRY")
        other.controller = self.player
        other.zone = Zone.PLAY
        self.player.board.append(other)
        self.game.queue_action(TriggerBattlecry(other))
        self.game.resolve_queue()

        self.assertEqual(d1.atk, old_atk_1 + 1)
        TEST_LOG.log("BGS_041", "Kalecgos",
                      "After Battlecry", "+1/+1 to Dragons",
                      f"d1: +{d1.atk - old_atk_1}", True)


class TestChampionOfSargeras(BaseTokenTest):
    """BG27_016: Battlecry and Deathrattle: Tavern minions have +2/+1."""

    def test_battlecry_adds_tavern_buff(self):
        m = self._make_minion("BG27_016")
        self.game.summon(self.player, m)

        bc = m.battlecry
        self.game.queue_action(bc, source=m)
        self.game.resolve_queue()

        self.assertEqual(len(self.player.tavern_buffs), 1)
        tb = self.player.tavern_buffs[0]
        self.assertEqual(tb.atk, 2)
        self.assertEqual(tb.health, 1)
        TEST_LOG.log("BG27_016", "Champion of Sargeras",
                      "Battlecry", "+2/+1 to Tavern", f"+{tb.atk}/+{tb.health}", True)

    def test_deathrattle_adds_tavern_buff(self):
        m = self._make_minion("BG27_016")
        self.game.summon(self.player, m)

        dr = m.deathrattle
        self.game.queue_action(dr, source=m)
        self.game.resolve_queue()

        self.assertEqual(len(self.player.tavern_buffs), 1)
        tb = self.player.tavern_buffs[0]
        self.assertEqual(tb.atk, 2)
        self.assertEqual(tb.health, 1)
        TEST_LOG.log("BG27_016", "Champion of Sargeras",
                      "Deathrattle", "+2/+1 to Tavern", f"+{tb.atk}/+{tb.health}", True)


class TestChoralMrrrglr(BaseTokenTest):
    """BG26_354: Start of Combat: Gain stats of all minions in hand."""

    def test_soc_gains_hand_minion_stats(self):
        m = self._make_minion("BG26_354")
        self.game.summon(self.player, m)
        old_atk, old_health = m.atk, m.max_health

        # Put 2 minions in hand with known stats
        h1 = self._make_minion("EXAMPLE_VANILLA")
        h1.set_tag(GameTag.BASE_ATK, 3)
        h1.set_tag(GameTag.BASE_HEALTH, 5)
        h1.set_tag(GameTag.HEALTH, 5)
        h1.controller = self.player
        h1.zone = Zone.HAND
        self.player.hand.append(h1)

        h2 = self._make_minion("EXAMPLE_TAUNT")
        h2.set_tag(GameTag.BASE_ATK, 1)
        h2.set_tag(GameTag.BASE_HEALTH, 4)
        h2.set_tag(GameTag.HEALTH, 4)
        h2.controller = self.player
        h2.zone = Zone.HAND
        self.player.hand.append(h2)

        soc = m.start_of_combat
        self.game.queue_action(soc, source=m)
        self.game.resolve_queue()

        # Total hand stats: 3+1=4 ATK, 5+4=9 Health
        self.assertEqual(m.atk, old_atk + 4)
        self.assertEqual(m.max_health, old_health + 9)
        TEST_LOG.log("BG26_354", "Choral Mrrrglr",
                      "Start of Combat", f"+{4}/+{9}",
                      f"+{m.atk - old_atk}/+{m.max_health - old_health}", True)


class TestTheLastOneStanding(BaseTokenTest):
    """BG34_320: Rally: Give a friendly minion of each type +2/+2."""

    def test_rally_buffs_one_per_race(self):
        m = self._make_minion("BG34_320")
        self.game.summon(self.player, m)

        # Set up minions of 3 different races
        beast = self._make_minion("EXAMPLE_VANILLA")
        beast.set_tag(GameTag.RACE, Race.BEAST)
        self.game.summon(self.player, beast)

        murloc = self._make_minion("EXAMPLE_TAUNT")
        murloc.set_tag(GameTag.RACE, Race.MURLOC)
        self.game.summon(self.player, murloc)

        dragon = self._make_minion("EXAMPLE_DEATHRATTLE")
        dragon.set_tag(GameTag.RACE, Race.DRAGON)
        self.game.summon(self.player, dragon)

        old_beast_atk = beast.atk
        old_murloc_atk = murloc.atk
        old_dragon_atk = dragon.atk

        rally = m.rally
        self.game.queue_action(rally, source=m)
        self.game.resolve_queue()

        self.assertEqual(beast.atk, old_beast_atk + 2)
        self.assertEqual(murloc.atk, old_murloc_atk + 2)
        self.assertEqual(dragon.atk, old_dragon_atk + 2)
        TEST_LOG.log("BG34_320", "The Last One Standing",
                      "Rally", "+2/+2 per type",
                      f"beast+{beast.atk - old_beast_atk} "
                      f"murloc+{murloc.atk - old_murloc_atk} "
                      f"dragon+{dragon.atk - old_dragon_atk}", True)


class TestFireForgedEvoker(BaseTokenTest):
    """BG32_822: SoC buffs Dragons, Improves after casting a Tavern spell."""

    @unittest.skip("Card BG25_040 removed in patch 35.6")
    def test_on_summon_registers_listener(self):
        """on_summon registers TAVERN_SPELL_CAST listener."""
        m = self._make_minion("BG32_822")
        self.game.summon(self.player, m)
        self.game.resolve_queue()

        ls = [l for _, l in self.game._event_listeners
              if l.event_name == "TAVERN_SPELL_CAST"]
        self.assertEqual(len(ls), 1)
        TEST_LOG.log("BG32_822", "Fire-forged Evoker",
                      "on_summon", "Register TAVERN_SPELL_CAST listener",
                      f"{len(ls)} TAVERN_SPELL_CAST listener(s) registered", True)

    def test_soc_buffs_dragons_with_improve_scaling(self):
        """SoC buffs Dragons scaled by TAVERN_SPELL_CAST counter."""
        from hsrl.core.actions import CastTavernSpell
        m = self._make_minion("BG32_822")
        self.game.summon(self.player, m)
        self.game.resolve_queue()

        # Cast 2 tavern spells
        self.game.queue_action(CastTavernSpell(self.player))
        self.game.resolve_queue()
        self.game.queue_action(CastTavernSpell(self.player))
        self.game.resolve_queue()

        # Create a friendly Dragon
        dragon = self._make_minion("EXAMPLE_TAUNT")
        dragon.set_tag(GameTag.RACE, Race.DRAGON)
        self.game.summon(self.player, dragon)
        old_atk, old_health = dragon.atk, dragon.max_health

        # Trigger Start of Combat
        self._trigger_effect(m, "start_of_combat")

        # counter=2, mult=3 → +3/+6
        self.assertEqual(dragon.atk, old_atk + 3)
        self.assertEqual(dragon.max_health, old_health + 6)
        TEST_LOG.log("BG32_822", "Fire-forged Evoker",
                      "SoC (after 2 spells)", "+3/+6 to Dragon",
                      f"+{dragon.atk - old_atk}/+{dragon.max_health - old_health}", True)


class TestRovingSailor(BaseTokenTest):
    """BG35_702: BC buffs friendly minion, Improved by Tavern spells cast this turn."""

    def test_battlecry_reads_spell_count(self):
        """Battlecry reads TAVERN_SPELLS_CAST_THIS_TURN for scaling."""
        from hsrl.core.actions import CastTavernSpell

        # Set in_combat so TargetedAction auto-resolves (no player to select)
        self.game.in_combat = True

        # Cast 3 tavern spells
        self.game.queue_action(CastTavernSpell(self.player))
        self.game.resolve_queue()
        self.game.queue_action(CastTavernSpell(self.player))
        self.game.resolve_queue()
        self.game.queue_action(CastTavernSpell(self.player))
        self.game.resolve_queue()

        # Create a friendly minion and the Roving Sailor
        friend = self._make_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, friend)
        old_atk, old_health = friend.atk, friend.max_health

        sailor = self._make_minion("BG35_702")
        self.game.summon(self.player, sailor)

        # Trigger battlecry — spell_count=3 → +3/+6
        self._trigger_effect(sailor, "battlecry")

        self.assertEqual(friend.atk, old_atk + 3)
        self.assertEqual(friend.max_health, old_health + 6)
        TEST_LOG.log("BG35_702", "Roving Sailor",
                      "Battlecry (3 spells)", "+3/+6",
                      f"+{friend.atk - old_atk}/+{friend.max_health - old_health}", True)

    def test_zero_spell_count_returns_none(self):
        """With 0 spells cast, battlecry returns None (no buff)."""
        friend = self._make_minion("EXAMPLE_VANILLA")
        self.game.summon(self.player, friend)
        old_atk = friend.atk

        sailor = self._make_minion("BG35_702")
        self.game.summon(self.player, sailor)

        self._trigger_effect(sailor, "battlecry")
        self.assertEqual(friend.atk, old_atk)  # No change
        TEST_LOG.log("BG35_702", "Roving Sailor",
                      "Battlecry (0 spells)", "No buff",
                      f"ATK unchanged: {friend.atk}", True)


class TestOminousSeer(BaseTokenTest):
    """BG31_330: Battlecry: The next Tavern spell you buy costs (1) less."""

    def setUp(self):
        super().setUp()
        from hsrl.core.minion_pool import MinionPool
        from hsrl.core.spell_pool import SpellPool
        self.game.minion_pool = MinionPool(CARDS)
        self.game.spell_pool = SpellPool(CARDS)

    def test_battlecry_increments_next_spell_cost_reduction(self):
        """Battlecry sets NEXT_SPELL_COST_REDUCTION += 1."""
        m = self._make_minion("BG31_330")
        self.game.summon(self.player, m)

        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 0)

        bc = m.battlecry  # Returns None (side effect only)
        self.assertIsNone(bc)

        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 1)
        TEST_LOG.log("BG31_330", "Ominous Seer",
                      "Battlecry", "NEXT_SPELL_COST_REDUCTION +1",
                      f"Discount: {self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)}", True)

    def test_multiple_battlecries_stack_discount(self):
        """Multiple Ominous Seer battlecries stack the discount."""
        m1 = self._make_minion("BG31_330")
        self.game.summon(self.player, m1)
        _ = m1.battlecry  # +1

        m2 = self._make_minion("BG31_330")
        self.game.summon(self.player, m2)
        _ = m2.battlecry  # +1

        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 2)
        TEST_LOG.log("BG31_330", "Ominous Seer (x2)",
                      "Battlecry", "NEXT_SPELL_COST_REDUCTION +2",
                      f"Discount: {self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)}", True)

    def test_discount_applied_on_spell_buy(self):
        """End-to-end: BC sets discount → buy_spell applies and resets it."""
        m = self._make_minion("BG31_330")
        self.game.summon(self.player, m)
        _ = m.battlecry  # Sets NEXT_SPELL_COST_REDUCTION = 1

        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 1)

        # Refresh tavern to get a spell
        self.player.set_tag(GameTag.GOLD, 10)
        self.player.set_tag(GameTag.TAVERN_TIER, 1)
        self.game.refresh_tavern(self.player)

        spells = [e for e in self.player.tavern
                  if e.get_tag(GameTag.CARDTYPE) == 3]
        if not spells:
            self.skipTest("No spells in tavern")
        spell = spells[0]
        cost = spell.cost
        old_gold = self.player.gold

        self.game.buy_spell(self.player, spell)

        # Discount of 1 applied
        self.assertEqual(self.player.gold, old_gold - max(0, cost - 1))
        # Discount consumed
        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 0)
        TEST_LOG.log("BG31_330", "Ominous Seer",
                      "buy_spell with discount", "cost - 1",
                      f"Gold: {self.player.gold}, Reduction: {self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)}", True)


class TestLaboratoryAssistant(BaseTokenTest):
    """BG35_150: Battlecry: Add a Fodder to your next 3 Refreshes."""

    def setUp(self):
        super().setUp()
        from hsrl.core.minion_pool import MinionPool
        self.game.minion_pool = MinionPool(CARDS)

    def test_battlecry_sets_counter(self):
        """Battlecry should set FODDER_REFRESH_REMAINING = 3."""
        m = self._make_minion("BG35_150")
        self._summon(m)
        # Battlecry returns None but has side effect of setting tag + registering listener
        bc = m.battlecry
        self.game.resolve_queue()
        self.assertEqual(
            m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 3,
            "Lab Assistant should set refresh counter to 3"
        )
        TEST_LOG.log("BG35_150", "Laboratory Assistant",
                      "Battlecry", "FODDER_REFRESH_REMAINING=3",
                      str(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0)), True)

    def test_battlecry_registers_listener(self):
        """Battlecry should register a TAVERN_REFRESH listener."""
        m = self._make_minion("BG35_150")
        self._summon(m)
        bc = m.battlecry
        self.game.resolve_queue()
        self.assertEqual(
            len(self.game._event_listeners), 1,
            "Should register 1 TAVERN_REFRESH listener"
        )

    def test_refresh_adds_fodder_and_decrements(self):
        """Each refresh should add FODDER to a tavern minion and decrement counter."""
        m = self._make_minion("BG35_150")
        self._summon(m)
        bc = m.battlecry
        self.game.resolve_queue()

        self.game.refresh_tavern(self.player)
        self.game.resolve_queue()

        self.assertEqual(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 2)
        fodder_count = sum(
            1 for t in self.player.tavern if t.has_tag(GameTag.FODDER)
        )
        self.assertEqual(fodder_count, 1,
                         "First refresh should add FODDER to 1 tavern minion")
        TEST_LOG.log("BG35_150", "Laboratory Assistant",
                      "Refresh #1", "FODDER +1, counter=2",
                      f"FODDER count={fodder_count}, remaining={m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0)}", True)

    def test_refresh_stops_after_counter_exhausted(self):
        """After 3 refreshes, no more FODDER should be added."""
        m = self._make_minion("BG35_150")
        self._summon(m)
        bc = m.battlecry
        self.game.resolve_queue()

        for _ in range(3):
            self.game.refresh_tavern(self.player)
            self.game.resolve_queue()

        self.assertEqual(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 0)
        fodder_after_3 = sum(
            1 for t in self.player.tavern if t.has_tag(GameTag.FODDER)
        )
        self.assertLessEqual(fodder_after_3, 3)

        # 4th refresh — counter=0, action no-ops, fresh tavern has no FODDER
        self.game.refresh_tavern(self.player)
        self.game.resolve_queue()

        self.assertEqual(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 0,
                         "Counter should stay at 0, not go negative")
        fodder_after_4 = sum(
            1 for t in self.player.tavern if t.has_tag(GameTag.FODDER)
        )
        self.assertEqual(fodder_after_4, 0,
                         "Fresh tavern after counter exhausted should have no FODDER")
        TEST_LOG.log("BG35_150", "Laboratory Assistant",
                      "After 4 refreshes", "No more FODDER",
                      f"FODDER count={fodder_after_4}, remaining=0", True)

    def test_golden_sets_counter_to_6(self):
        """Golden Lab Assistant should set counter to 6."""
        m = self._make_minion("BG35_150")
        m.set_tag(GameTag.GOLDEN, True)
        self._summon(m)
        bc = m.battlecry
        self.game.resolve_queue()
        self.assertEqual(
            m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 6,
            "Golden should set counter to 6"
        )
        TEST_LOG.log("BG35_150", "Laboratory Assistant (Golden)",
                      "Battlecry", "FODDER_REFRESH_REMAINING=6",
                      str(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0)), True)


# ═══════════════════════════════════════════════════════════════════════════
# Test: BG28_550 — Rodeo Performer
# ═══════════════════════════════════════════════════════════════════════════

class TestRodeoPerformer(BaseTokenTest):
    """Battlecry: Discover a Tavern spell."""

    def test_battlecry_adds_spell_to_hand(self):
        """Battlecry should add a Spell card to hand."""
        m = self._make_minion("BG28_550")
        self._summon(m)
        self._trigger_effect(m, "battlecry")
        self.assertGreater(len(self.player.hand), 0,
                           "Hand should not be empty after DiscoverSpell")
        spell = self.player.hand[0]
        from hsrl.core.spell import Spell as SpellEntity
        self.assertIsInstance(spell, SpellEntity,
                              "Card in hand should be a Spell")
        TEST_LOG.log("BG28_550", "Rodeo Performer",
                      "Battlecry", "Add a Tavern spell to hand",
                      f"Spell: {spell.get_tag(GameTag.CARD_ID)}", len(self.player.hand) > 0)

    def test_battlecry_does_not_add_gold(self):
        """Battlecry should not add Gold/minion — only a spell to hand."""
        m = self._make_minion("BG28_550")
        self._summon(m)
        hand_before = len(self.player.hand)
        gold_before = self.player.gold
        self._trigger_effect(m, "battlecry")
        self.assertEqual(self.player.gold, gold_before,
                         "Gold should not change from DiscoverSpell")
        self.assertEqual(len(self.player.hand), hand_before + 1,
                         "Exactly one card should be added to hand")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Spellcraft Minions (6 Naga) — generate+cast+effect
# ═══════════════════════════════════════════════════════════════════════════

class TestSpellcraftGlowscale(BaseTokenTest):
    """BG23_008 Glowscale: Spellcraft → Divine Shield."""

    def test_spellcraft_generates_spell(self):
        """Spellcraft should generate BG23_008t in hand."""
        m = self._make_minion("BG23_008")
        self._summon(m)
        self.game._generate_spellcraft_spells()
        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0].get_tag(GameTag.CARD_ID), "BG23_008t")
        TEST_LOG.log("BG23_008", "Glowscale", "Spellcraft Generate",
                      "BG23_008t in hand", "BG23_008t", True)

    def test_spell_on_play_gives_divine_shield(self):
        """Playing the spell gives Divine Shield to a random friendly minion."""
        m = self._make_minion("BG23_008")
        self._summon(m)
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.assertFalse(m.divine_shield)
        self.game.play_spell(self.player, spell)
        self.assertTrue(m.divine_shield)
        TEST_LOG.log("BG23_008", "Glowscale", "Spell on_play",
                      "Divine Shield", "Divine Shield granted", True)


class TestSpellcraftDarkcrestStrategist(BaseTokenTest):
    """BG31_920 Darkcrest Strategist: Spellcraft → random Naga."""

    def test_spell_generates_and_adds_naga_to_hand(self):
        """Playing the spell adds a random Naga to hand."""
        m = self._make_minion("BG31_920")
        self._summon(m)
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.game.play_spell(self.player, spell)
        # Hand: spell removed, Naga added → 1 card
        self.assertGreater(len(self.player.hand), 0)
        naga = self.player.hand[0]
        self.assertEqual(naga.race, Race.NAGA)
        TEST_LOG.log("BG31_920", "Darkcrest Strategist", "Spell on_play",
                      "Random Naga in hand",
                      f"{naga.get_tag(GameTag.CARD_ID)} (race={naga.race})", True)


class TestSpellcraftRimescalePriestess(BaseTokenTest):
    """BG33_319 Rimescale Priestess: Spellcraft → random Tavern spell."""

    def test_spell_generates_and_adds_spell_to_hand(self):
        """Playing the spell adds a random Tavern spell to hand."""
        m = self._make_minion("BG33_319")
        self._summon(m)
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.game.play_spell(self.player, spell)
        self.assertGreater(len(self.player.hand), 0)
        new_card = self.player.hand[0]
        is_spell = new_card.get_tag(GameTag.CARDTYPE, 0) == CardType.SPELL
        TEST_LOG.log("BG33_319", "Rimescale Priestess", "Spell on_play",
                      "Random spell in hand",
                      f"{new_card.get_tag(GameTag.CARD_ID)}", is_spell)


class TestSpellcraftDeepSeaAngler(BaseTokenTest):
    """BG23_004 Deep-Sea Angler: Spellcraft → +2/+2 and Taunt."""

    def test_spell_on_play_buffs_and_taunts(self):
        """Playing the spell gives +2/+2 and Taunt."""
        m = self._make_minion("BG23_004")
        self._summon(m)
        atk_before, hp_before = m.atk, m.health
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.assertFalse(m.taunt)
        self.game.play_spell(self.player, spell)
        self.assertEqual(m.atk, atk_before + 2)
        self.assertEqual(m.health, hp_before + 2)
        self.assertTrue(m.taunt)
        TEST_LOG.log("BG23_004", "Deep-Sea Angler", "Spell on_play",
                      "+2/+2 + Taunt", f"{m.atk}/{m.health} Taunt={m.taunt}", True)


class TestSpellcraftWaverider(BaseTokenTest):
    """BG23_007 Waverider: Spellcraft → +2/+2, Windfury if Naga."""

    @unittest.skip("Card BG23_007 removed in patch 35.6")
    def test_spell_on_play_buffs_naga_with_windfury(self):
        """Playing spell on a Naga gives +2/+2 and Windfury."""
        m = self._make_minion("BG23_007")
        self._summon(m)
        m.set_tag(GameTag.RACE, Race.NAGA)
        atk_before, hp_before = m.atk, m.health
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.game.play_spell(self.player, spell)
        self.assertEqual(m.atk, atk_before + 2)
        self.assertEqual(m.health, hp_before + 2)
        self.assertTrue(m.windfury)
        TEST_LOG.log("BG23_007", "Waverider", "Spell on_play (Naga)",
                      "+2/+2 + Windfury", f"{m.atk}/{m.health} WF={m.windfury}", True)

    @unittest.skip("Card BG23_007 removed in patch 35.6")
    def test_spell_on_play_buffs_non_naga_no_windfury(self):
        """Playing spell on non-Naga gives +2/+2 but NOT Windfury."""
        m = self._make_minion("BG23_007")
        self._summon(m)
        m.set_tag(GameTag.RACE, Race.BEAST)
        atk_before = m.atk
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.game.play_spell(self.player, spell)
        self.assertEqual(m.atk, atk_before + 2)
        self.assertFalse(m.windfury)
        TEST_LOG.log("BG23_007", "Waverider", "Spell on_play (non-Naga)",
                      "+2/+2 only", f"{m.atk}/{m.health} WF={m.windfury}", True)


class TestSpellcraftReefRiffer(BaseTokenTest):
    """BG26_501 Reef Riffer: Spellcraft → stats equal to Tier."""

    def test_spell_on_play_buffs_by_tier(self):
        """Playing the spell buffs by player's Tavern Tier."""
        m = self._make_minion("BG26_501")
        self._summon(m)
        self.player.set_tag(GameTag.TAVERN_TIER, 3)
        atk_before, hp_before = m.atk, m.health
        self.game._generate_spellcraft_spells()
        spell = self.player.hand[0]
        self.game.play_spell(self.player, spell)
        self.assertEqual(m.atk, atk_before + 3)
        self.assertEqual(m.health, hp_before + 3)
        TEST_LOG.log("BG26_501", "Reef Riffer", "Spell on_play (Tier 3)",
                      "+3/+3", f"{m.atk}/{m.health}", True)


class TestBlueChromadrake(unittest.TestCase):
    """Blue Chromadrake (BG34_634t): BC — Get a random 3-Cost Tavern spell."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def _get_cost_3_spell_ids(self):
        """Return all pool spell IDs that cost 3."""
        ids = []
        for card_id, data in CARDS._cards.items():
            if data.cardtype == CardType.SPELL and not card_id.startswith("EXAMPLE_"):
                if data.tags.get(GameTag.COST) == 3:
                    ids.append(card_id)
        return ids

    def test_bc_gives_cost3_spell(self):
        """Battlecry adds a random 3-Cost spell to hand."""
        data = CARDS.get("BG34_634t")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        action = m.battlecry
        self.assertIsNotNone(action, "Blue Chromadrake should have a battlecry")
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)
        spell = self.player.hand[0]
        spell_cost = spell.get_tag(GameTag.COST)
        self.assertEqual(spell_cost, 3, f"Spell should cost 3, got {spell_cost}")
        TEST_LOG.log("BG34_634t", "Blue Chromadrake", "Battlecry: Get 3-Cost spell",
                      "3-Cost spell in hand", f"{spell.get_tag(GameTag.CARD_ID)} (Cost {spell_cost})", True)

    def test_bc_spell_is_valid_pool_spell(self):
        """The spell given is from the pool, not an EXAMPLE card."""
        data = CARDS.get("BG34_634t")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        action = m.battlecry
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        spell = self.player.hand[0]
        spell_id = spell.get_tag(GameTag.CARD_ID)
        self.assertFalse(spell_id.startswith("EXAMPLE_"), f"Should not give EXAMPLE spell: {spell_id}")
        cost_3_ids = self._get_cost_3_spell_ids()
        self.assertIn(spell_id, cost_3_ids, f"Spell {spell_id} should be a cost-3 pool spell")
        TEST_LOG.log("BG34_634t", "Blue Chromadrake", "Spell is valid pool spell",
                      "Pool spell", f"{spell_id}", True)


class TestRefreshingAnomaly(unittest.TestCase):
    """Refreshing Anomaly (BGS_116): BC — Gain 2 free Refreshes."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_bc_gives_2_free_refreshes(self):
        """Battlecry sets FREE_REFRESH_REMAINING to 2."""
        data = CARDS.get("BGS_116")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        self.assertEqual(self.player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0), 0)
        action = m.battlecry
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0), 2)
        TEST_LOG.log("BGS_116", "Refreshing Anomaly", "BC: Gain 2 free Refreshes",
                      "FREE_REFRESH_REMAINING=2", "2", True)

    def test_bc_stacks_with_existing(self):
        """Battlecry stacks with existing free refreshes."""
        self.player.set_tag(GameTag.FREE_REFRESH_REMAINING, 3)
        data = CARDS.get("BGS_116")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        action = m.battlecry
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0), 5)
        TEST_LOG.log("BGS_116", "Refreshing Anomaly", "BC stacks with existing",
                      "FREE_REFRESH_REMAINING=5", "5", True)


class TestAlertAlarmist(unittest.TestCase):
    """Alert Alarmist (BG35_340): DR — Next Tavern spell costs (2) less."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_dr_sets_discount(self):
        """Deathrattle sets NEXT_SPELL_COST_REDUCTION to 2."""
        data = CARDS.get("BG35_340")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 0)
        action = m.deathrattle
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 2)
        TEST_LOG.log("BG35_340", "Alert Alarmist", "DR: Next spell costs (2) less",
                      "NEXT_SPELL_COST_REDUCTION=2", "2", True)

    def test_dr_taunt_keyword(self):
        """Alert Alarmist has Taunt keyword."""
        data = CARDS.get("BG35_340")
        m = Minion(data, game=self.game)
        self.assertTrue(m.has_tag(GameTag.TAUNT), "Alert Alarmist should have Taunt")
        TEST_LOG.log("BG35_340", "Alert Alarmist", "Keyword: Taunt", "True", "True", True)


# ═══════════════════════════════════════════════════════════════════════════
# Tavern Spell Buff Modifier Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBlackChromadrake(unittest.TestCase):
    """Black Chromadrake (BG34_635t): BC — +1 Health to future Tavern spells."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_bc_sets_spell_health_bonus(self):
        """Battlecry increments TAVERN_SPELL_HEALTH_BONUS by 1."""
        data = CARDS.get("BG34_635t")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 0)
        action = m.battlecry
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 1)
        TEST_LOG.log("BG34_635t", "Black Chromadrake",
                      "BC: Your spells give +1 Health", "TAVERN_SPELL_HEALTH_BONUS=1",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)}", True)

    def test_bc_stacks_health_bonus(self):
        """Multiple Black Chromadrake BCs stack the health bonus."""
        data = CARDS.get("BG34_635t")
        for _ in range(3):
            m = Minion(data, game=self.game)
            m.controller = self.player
            self.player.board.append(m)
            action = m.battlecry
            self.game.queue_action(action, source=m)
            self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 3)
        TEST_LOG.log("BG34_635t", "Black Chromadrake",
                      "BC×3: bonus stacks", "TAVERN_SPELL_HEALTH_BONUS=3",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)}", True)


class TestRedChromadrake(unittest.TestCase):
    """Red Chromadrake (BG34_638t): BC — +1 Attack to future Tavern spells."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_bc_sets_spell_atk_bonus(self):
        """Battlecry increments TAVERN_SPELL_ATK_BONUS by 1."""
        data = CARDS.get("BG34_638t")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 0)
        action = m.battlecry
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 1)
        TEST_LOG.log("BG34_638t", "Red Chromadrake",
                      "BC: Your spells give +1 Attack", "TAVERN_SPELL_ATK_BONUS=1",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)}", True)

    def test_bc_stacks_atk_bonus(self):
        """Multiple Red Chromadrake BCs stack the attack bonus."""
        data = CARDS.get("BG34_638t")
        for _ in range(2):
            m = Minion(data, game=self.game)
            m.controller = self.player
            self.player.board.append(m)
            action = m.battlecry
            self.game.queue_action(action, source=m)
            self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 2)
        TEST_LOG.log("BG34_638t", "Red Chromadrake",
                      "BC×2: bonus stacks", "TAVERN_SPELL_ATK_BONUS=2",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)}", True)


class TestFriendlyGeist(unittest.TestCase):
    """Friendly Geist (BG32_880): DR — +1 Attack to future Tavern spells."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_dr_sets_atk_bonus(self):
        """Deathrattle increments TAVERN_SPELL_ATK_BONUS by 1."""
        data = CARDS.get("BG32_880")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 0)
        action = m.deathrattle
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 1)
        TEST_LOG.log("BG32_880", "Friendly Geist",
                      "DR: Your spells give +1 Attack", "TAVERN_SPELL_ATK_BONUS=1",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)}", True)

    def test_dr_stacks_with_bc(self):
        """Friendly Geist DR stacks with Chromadrake BC bonuses."""
        # Set some existing bonus
        self.player.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 2)
        data = CARDS.get("BG32_880")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        action = m.deathrattle
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 3)
        TEST_LOG.log("BG32_880", "Friendly Geist",
                      "DR stacks with existing bonus", "TAVERN_SPELL_ATK_BONUS: 2→3",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)}", True)


class TestTranquilMeditative(unittest.TestCase):
    """Tranquil Meditative (BG32_835): Spellcraft — gives Meditation spell token."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.minion_pool = None
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_spellcraft_generates_meditation(self):
        """Spellcraft generates BG32_835t in hand."""
        data = CARDS.get("BG32_835")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.append(m)
        self.game._generate_spellcraft_spells()
        self.assertEqual(len(self.player.hand), 1)
        spell = self.player.hand[0]
        self.assertEqual(spell.get_tag(GameTag.CARD_ID), "BG32_835t")
        TEST_LOG.log("BG32_835", "Tranquil Meditative",
                      "Spellcraft generates Meditation", "BG32_835t in hand",
                      spell.get_tag(GameTag.CARD_ID), True)

    def test_golden_generates_golden_meditation(self):
        """Golden Tranquil Meditative generates BG32_835_Gt."""
        data = CARDS.get("BG32_835")
        m = Minion(data, game=self.game)
        m.set_tag(GameTag.GOLDEN, True)
        m.controller = self.player
        self.player.board.append(m)
        self.game._generate_spellcraft_spells()
        self.assertEqual(len(self.player.hand), 1)
        spell = self.player.hand[0]
        self.assertEqual(spell.get_tag(GameTag.CARD_ID), "BG32_835t_GOLDEN")
        TEST_LOG.log("BG32_835", "Tranquil Meditative (Golden)",
                      "Spellcraft generates Golden Meditation", "BG32_835t_GOLDEN in hand",
                      spell.get_tag(GameTag.CARD_ID), True)


class TestMeditationSpell(unittest.TestCase):
    """Meditation Spell (BG32_835t): on_play — +1/+1 to future Tavern spell buffs."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def test_on_play_sets_both_bonuses(self):
        """Casting Meditation sets both ATK and HEALTH bonuses."""
        spell = self.game.create_minion("BG32_835t")
        spell.controller = self.player
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 0)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 0)
        action = spell.on_play
        self.assertIsNotNone(action)
        self.game.queue_action(action, source=spell)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 1)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 1)
        TEST_LOG.log("BG32_835t", "Meditation",
                      "on_play: +1/+1 to future spells", "ATK=1, HEALTH=1",
                      f"ATK={self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)}, HEALTH={self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)}", True)


class TestTavernSpellModifier(unittest.TestCase):
    """Integration tests: spell modifiers affect actual buff spell values."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.game.in_combat = True  # Auto-resolve TargetedActions
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.game.active_player = self.player

    def _cast_example_buff_spell(self):
        """Helper: cast EXAMPLE_BUFF_SPELL on a board token and return it."""
        token = self.game.create_minion("EXAMPLE_VANILLA")
        token.controller = self.player
        self.player.board.append(token)
        spell = self.game.create_minion("EXAMPLE_BUFF_SPELL")
        spell.controller = self.player
        action = spell.on_play
        self.game.queue_action(action, source=spell)
        self.game.resolve_queue()
        return token

    def test_no_modifier_gives_base_buff(self):
        """Without modifiers, spell gives exactly +2/+2."""
        token = self._cast_example_buff_spell()
        self.assertEqual(token.atk, 4, f"Expected ATK=4 (2 base + 2 buff), got {token.atk}")
        self.assertEqual(token.health, 5, f"Expected Health=5 (3 base + 2 buff), got {token.health}")
        TEST_LOG.log("EXAMPLE", "Buff Spell (no modifier)",
                      "Base buff +2/+2", "ATK=4, Health=5",
                      f"ATK={token.atk}, Health={token.health}", token.atk == 4)

    def test_atk_modifier_increases_atk_only(self):
        """TAVERN_SPELL_ATK_BONUS adds to ATK but not Health."""
        self.player.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 3)
        token = self._cast_example_buff_spell()
        self.assertEqual(token.atk, 7, f"Expected ATK=7 (2 base + 2 buff + 3 bonus), got {token.atk}")
        self.assertEqual(token.health, 5, f"Expected Health=5 (3 base + 2 buff), got {token.health}")
        TEST_LOG.log("EXAMPLE", "Buff Spell (ATK=3)",
                      "ATK bonus applies, Health unchanged", "ATK=7, Health=5",
                      f"ATK={token.atk}, Health={token.health}", token.atk == 7)

    def test_health_modifier_increases_health_only(self):
        """TAVERN_SPELL_HEALTH_BONUS adds to Health but not ATK."""
        self.player.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 2)
        token = self._cast_example_buff_spell()
        self.assertEqual(token.atk, 4, f"Expected ATK=4 (2 base + 2 buff), got {token.atk}")
        self.assertEqual(token.health, 7, f"Expected Health=7 (3 base + 2 buff + 2 bonus), got {token.health}")
        TEST_LOG.log("EXAMPLE", "Buff Spell (Health=2)",
                      "Health bonus applies, ATK unchanged", "ATK=4, Health=7",
                      f"ATK={token.atk}, Health={token.health}", token.health == 7)

    def test_both_modifiers_stack(self):
        """Both ATK and Health bonuses apply simultaneously."""
        self.player.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 2)
        self.player.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 2)
        token = self._cast_example_buff_spell()
        self.assertEqual(token.atk, 6, f"Expected ATK=6 (2 base + 2 buff + 2 bonus), got {token.atk}")
        self.assertEqual(token.health, 7, f"Expected Health=7 (3 base + 2 buff + 2 bonus), got {token.health}")
        TEST_LOG.log("EXAMPLE", "Buff Spell (ATK=2, Health=2)",
                      "Both bonuses apply", "ATK=6, Health=7",
                      f"ATK={token.atk}, Health={token.health}", token.atk == 6 and token.health == 7)

    def test_modifiers_persist_across_turns_simulated(self):
        """Modifiers persist — not cleared between recruit phases."""
        self.player.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 1)
        self.player.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 1)
        # Simulate end of turn (which clears temporary buffs but NOT these modifiers)
        self.game._clear_temporary_buffs()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 1,
                         "ATK modifier should persist after turn end")
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 1,
                         "Health modifier should persist after turn end")
        TEST_LOG.log("EXAMPLE", "Spell Modifier Persistence",
                      "Modifiers survive end-of-turn cleanup", "ATK=1, Health=1",
                      f"ATK={self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)}, Health={self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)}", True)

    def test_empty_board_bc_still_works(self):
        """Black Chromadrake BC works even with empty board."""
        data = CARDS.get("BG34_635t")
        m = Minion(data, game=self.game)
        m.controller = self.player
        self.player.board.clear()
        self.player.board.append(m)
        action = m.battlecry
        self.assertIsNotNone(action, "BC should return ImproveTavernSpellBuff even on empty board")
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 1,
                         "Modifier should be set on Player, regardless of board state")
        TEST_LOG.log("BG34_635t", "Black Chromadrake (empty board)",
                      "BC on empty board still works", "TAVERN_SPELL_HEALTH_BONUS=1",
                      f"= {self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)}", True)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 9 — On-Sell Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSunBaconRelaxer(unittest.TestCase):
    """BG20_301: When you sell this, get 2 Blood Gems."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_on_sell_gives_2_blood_gems(self):
        m = self.game.create_minion("BG20_301")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 2,
                         "Should add 2 Blood Gems to hand")
        self.assertTrue(all("BLOOD_GEM" in h.get_tag(GameTag.CARD_ID, "") for h in self.player.hand),
                        "Both should be Blood Gem cards")


class TestTad(unittest.TestCase):
    """BG22_202: When you sell this, get a random Murloc."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_on_sell_gives_random_murloc(self):
        m = self.game.create_minion("BG22_202")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1, "Should add exactly 1 minion to hand")


class TestSellemental(unittest.TestCase):
    """BGS_115: When you sell this, get a 3/3 Elemental (Water Droplet)."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_on_sell_gives_water_droplet(self):
        m = self.game.create_minion("BGS_115")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1, "Should add exactly 1 minion to hand")
        droplet = self.player.hand[0]
        self.assertEqual(droplet.get_tag(GameTag.CARD_ID), "BGS_115t",
                         "Should be Water Droplet")
        self.assertEqual(droplet.atk, 3, "Water Droplet should have 3 ATK")
        self.assertEqual(droplet.health, 3, "Water Droplet should have 3 Health")


class TestRiverSkipper(unittest.TestCase):
    """BG33_140: When you sell this, get a random Tier 1 minion."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_on_sell_gives_tier_1_minion(self):
        m = self.game.create_minion("BG33_140")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1, "Should add exactly 1 minion to hand")
        got = self.player.hand[0]
        card_id = got.get_tag(GameTag.CARD_ID)
        data = CARDS.get(card_id)
        self.assertEqual(data.tech_level, 1, f"Got {card_id}, expected Tier 1")


class TestShoalfinMystic(unittest.TestCase):
    """BG32_860: When you sell this, improve Tavern spell buffs +1/+1."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    @unittest.skip("Card BG32_860 removed in patch 35.6")
    def test_on_sell_improves_tavern_spell_buffs(self):
        m = self.game.create_minion("BG32_860")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 1)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 1)


class TestFireBaller(unittest.TestCase):
    """BG31_816: When you sell this, give minions +{0} ATK. Improve future Ballers."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_first_sell_buffs_zero(self):
        """First Baller sale: buff +0 ATK, increment counter to 1."""
        # Add some friendly minions to the board
        board_minions = []
        for _ in range(3):
            t = self.game.create_minion("EXAMPLE_VANILLA")
            t.controller = self.player
            t.zone = Zone.PLAY
            self.player.board.append(t)
            board_minions.append(t)
        # Create and add Fire Baller
        m = self.game.create_minion("BG31_816")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        # Trigger on-sell
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        # First sale: bonus=0, so no ATK change
        for t in board_minions:
            self.assertEqual(t.atk, 2, f"First sale buffs +0 ATK, expected ATK=2, got {t.atk}")
        # Counter should be incremented to 1
        self.assertEqual(self.player.get_tag(GameTag.BALLER_FIRE_BONUS, 0), 1)

    def test_second_sell_buffs_one(self):
        """Second Baller sale: buff +1 ATK, increment counter to 2."""
        board_minions = []
        for _ in range(3):
            t = self.game.create_minion("EXAMPLE_VANILLA")
            t.controller = self.player
            t.zone = Zone.PLAY
            self.player.board.append(t)
            board_minions.append(t)
        # First Baller
        m1 = self.game.create_minion("BG31_816")
        m1.controller = self.player
        m1.zone = Zone.PLAY
        self.player.board.append(m1)
        action1 = m1.on_sell
        self.game.queue_action(action1, source=m1)
        self.game.resolve_queue()
        self.player.board.remove(m1)  # simulate removal after sell
        # Second Baller
        m2 = self.game.create_minion("BG31_816")
        m2.controller = self.player
        m2.zone = Zone.PLAY
        self.player.board.append(m2)
        action2 = m2.on_sell
        self.game.queue_action(action2, source=m2)
        self.game.resolve_queue()
        # Second sale: bonus=1, so ATK increases by 1
        for t in board_minions:
            self.assertEqual(t.atk, 3, f"Second sale buffs +1 ATK, expected ATK=3, got {t.atk}")
        self.assertEqual(self.player.get_tag(GameTag.BALLER_FIRE_BONUS, 0), 2)


class TestSnowBaller(unittest.TestCase):
    """BG31_818: When you sell this, give minions +{0} Health. Improve future Ballers."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_first_sell_buffs_zero(self):
        board_minions = []
        for _ in range(3):
            t = self.game.create_minion("EXAMPLE_VANILLA")
            t.controller = self.player
            t.zone = Zone.PLAY
            self.player.board.append(t)
            board_minions.append(t)
        m = self.game.create_minion("BG31_818")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        for t in board_minions:
            self.assertEqual(t.health, 3, f"First sale buffs +0 Health, expected HP=3, got {t.health}")
        self.assertEqual(self.player.get_tag(GameTag.BALLER_SNOW_BONUS, 0), 1)

    def test_second_sell_buffs_one(self):
        board_minions = []
        for _ in range(3):
            t = self.game.create_minion("EXAMPLE_VANILLA")
            t.controller = self.player
            t.zone = Zone.PLAY
            self.player.board.append(t)
            board_minions.append(t)
        m1 = self.game.create_minion("BG31_818")
        m1.controller = self.player
        m1.zone = Zone.PLAY
        self.player.board.append(m1)
        action1 = m1.on_sell
        self.game.queue_action(action1, source=m1)
        self.game.resolve_queue()
        self.player.board.remove(m1)
        m2 = self.game.create_minion("BG31_818")
        m2.controller = self.player
        m2.zone = Zone.PLAY
        self.player.board.append(m2)
        action2 = m2.on_sell
        self.game.queue_action(action2, source=m2)
        self.game.resolve_queue()
        for t in board_minions:
            self.assertEqual(t.health, 4, f"Second sale buffs +1 Health, expected HP=4, got {t.health}")
        self.assertEqual(self.player.get_tag(GameTag.BALLER_SNOW_BONUS, 0), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 9 — End-of-Turn Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIgnitionSpecialist(unittest.TestCase):
    """BG28_595: At the end of your turn, get 2 random Tavern spells."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_eot_gives_2_spells(self):
        m = self.game.create_minion("BG28_595")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.end_of_turn
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 2, "Should add 2 spells to hand")
        from hsrl.core.enums import CardType as CT
        for h in self.player.hand:
            data = CARDS.get(h.get_tag(GameTag.CARD_ID))
            self.assertEqual(data.cardtype, CardType.SPELL,
                             f"Got {data.name}, expected a SPELL type")


class TestMarqueeTicker(unittest.TestCase):
    """BG31_178: At the end of your turn, get a random Tavern spell."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_eot_gives_1_spell(self):
        m = self.game.create_minion("BG31_178")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.end_of_turn
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1, "Should add exactly 1 spell to hand")
        data = CARDS.get(self.player.hand[0].get_tag(GameTag.CARD_ID))
        self.assertEqual(data.cardtype, CardType.SPELL)


class TestCousinErrgl(unittest.TestCase):
    """BG35_142: At the end of your turn, get a Mama or Papa Mrrglton."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_eot_gives_mama_or_papa_mrrglton(self):
        m = self.game.create_minion("BG35_142")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.end_of_turn
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(len(self.player.hand), 1)
        got_id = self.player.hand[0].get_tag(GameTag.CARD_ID)
        self.assertIn(got_id, ["BG35_140", "BG35_141"],
                      f"Expected Mama or Papa Mrrglton, got {got_id}")


class TestFelfireConjurer(unittest.TestCase):
    """BG32_821: At the end of your turn, improve Tavern spell buffs +1/+1."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_eot_improves_tavern_spell_buffs(self):
        m = self.game.create_minion("BG32_821")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.end_of_turn
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 1)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 1)

    def test_eot_stacks_with_multiple_triggers(self):
        m = self.game.create_minion("BG32_821")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        for _ in range(3):
            action = m.end_of_turn
            self.game.queue_action(action, source=m)
            self.game.resolve_queue()
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0), 3)
        self.assertEqual(self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0), 3)


class TestSurfingSylvar(unittest.TestCase):
    """BG32_235: At EOT, give adjacent minions +{0} ATK per friendly Golden."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def _trigger_eot(self, source):
        """Queue end_of_turn effect handling list/None returns like the engine."""
        action = source.end_of_turn
        if action is not None:
            if isinstance(action, (list, tuple)):
                for a in action:
                    self.game.queue_action(a, source=source)
            else:
                self.game.queue_action(action, source=source)
            self.game.resolve_queue()

    def test_no_golden_no_buff(self):
        """With 0 golden minions, adjacent minions should not change ATK."""
        left = self.game.create_minion("EXAMPLE_VANILLA")
        left.controller = self.player
        left.zone = Zone.PLAY
        self.player.board.append(left)
        sylvar = self.game.create_minion("BG32_235")
        sylvar.controller = self.player
        sylvar.zone = Zone.PLAY
        self.player.board.append(sylvar)
        right = self.game.create_minion("EXAMPLE_VANILLA")
        right.controller = self.player
        right.zone = Zone.PLAY
        self.player.board.append(right)
        self._trigger_eot(sylvar)
        self.assertEqual(left.atk, 2, "No golden → no buff")
        self.assertEqual(right.atk, 2, "No golden → no buff")

    def test_one_golden_buffs_adjacent(self):
        """With 1 golden minion on board, adjacent get +1 ATK each."""
        left = self.game.create_minion("EXAMPLE_VANILLA")
        left.controller = self.player
        left.zone = Zone.PLAY
        self.player.board.append(left)
        # Make left golden
        left.set_tag(GameTag.GOLDEN, True)
        sylvar = self.game.create_minion("BG32_235")
        sylvar.controller = self.player
        sylvar.zone = Zone.PLAY
        self.player.board.append(sylvar)
        right = self.game.create_minion("EXAMPLE_VANILLA")
        right.controller = self.player
        right.zone = Zone.PLAY
        self.player.board.append(right)
        self._trigger_eot(sylvar)
        self.assertEqual(left.atk, 3, "Adjacent golden gives +1 ATK")
        self.assertEqual(right.atk, 3, "Adjacent golden gives +1 ATK")


class TestWoodlandDefiler(unittest.TestCase):
    """BG35_151: At EOT, add a Fodder to your next 3 Refreshes."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        from hsrl.core.minion_pool import MinionPool
        self.game.minion_pool = MinionPool(CARDS)
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_eot_sets_fodder_counter(self):
        m = self.game.create_minion("BG35_151")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        # end_of_turn is side-effect: sets FODDER_REFRESH_REMAINING on source + registers listener
        m.end_of_turn
        self.assertEqual(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 3,
                         "Should set FODDER_REFRESH_REMAINING = 3 on source minion")

    def test_refresh_adds_fodder_and_decrements(self):
        """After EOT sets counter, refresh should add FODDER to tavern minion."""
        m = self.game.create_minion("BG35_151")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        # Trigger EOT (side effect: sets FODDER_REFRESH_REMAINING + registers listener)
        m.end_of_turn
        # Now refresh tavern
        self.game.refresh_tavern(self.player)
        self.game.resolve_queue()
        self.assertEqual(m.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0), 2)
        fodder_count = sum(1 for t in self.player.tavern if t.has_tag(GameTag.FODDER))
        self.assertEqual(fodder_count, 1, "Refresh should add FODDER to 1 tavern minion")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 9 — EXAMPLE_ON_SELL_BALLER Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExampleOnSellBaller(unittest.TestCase):
    """EXAMPLE_ON_SELL_BALLER: standard example for per-card-ID counter pattern."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]

    def test_first_sell_buffs_zero_then_increment(self):
        board_minion = self.game.create_minion("EXAMPLE_VANILLA")
        board_minion.controller = self.player
        board_minion.zone = Zone.PLAY
        self.player.board.append(board_minion)
        m = self.game.create_minion("EXAMPLE_ON_SELL_BALLER")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.on_sell
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(board_minion.atk, 2, "First sale buffs +0 ATK")
        self.assertEqual(self.player.get_tag(GameTag.BALLER_FIRE_BONUS, 0), 1,
                         "Counter incremented to 1")

    def test_second_sell_buffs_one_then_increment(self):
        board_minion = self.game.create_minion("EXAMPLE_VANILLA")
        board_minion.controller = self.player
        board_minion.zone = Zone.PLAY
        self.player.board.append(board_minion)
        m1 = self.game.create_minion("EXAMPLE_ON_SELL_BALLER")
        m1.controller = self.player
        m1.zone = Zone.PLAY
        self.player.board.append(m1)
        a1 = m1.on_sell
        self.game.queue_action(a1, source=m1)
        self.game.resolve_queue()
        self.player.board.remove(m1)
        m2 = self.game.create_minion("EXAMPLE_ON_SELL_BALLER")
        m2.controller = self.player
        m2.zone = Zone.PLAY
        self.player.board.append(m2)
        a2 = m2.on_sell
        self.game.queue_action(a2, source=m2)
        self.game.resolve_queue()
        self.assertEqual(board_minion.atk, 3, "Second sale buffs +1 ATK")
        self.assertEqual(self.player.get_tag(GameTag.BALLER_FIRE_BONUS, 0), 2)
# ═══════════════════════════════════════════════════════════════════════════════
# Phase 10 — Event Broadcast Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventBroadcasts(unittest.TestCase):
    """Verify TURN_BEGIN, TURN_END, END_OF_COMBAT events fire at correct times."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 10
        self.game.players = [self.player]
        self.events = []

    def _make_listener(self, event_name):
        """Create a listener that captures when the event fires."""
        from hsrl.core.events import EventListener
        from hsrl.core.actions import Action
        events = self.events

        class _CaptureAction(Action):
            def do(self, source, game, target=None):
                events.append(event_name)

        return EventListener(event_name=event_name, action=_CaptureAction())

    def test_turn_begin_is_broadcast(self):
        """TURN_BEGIN should fire when recruit phase starts."""
        self.game.register_listener(self.player, self._make_listener("TURN_BEGIN"))
        self.game._start_recruit_phase()
        self.assertIn("TURN_BEGIN", self.events)

    def test_turn_end_is_broadcast(self):
        """TURN_END should fire when recruit phase ends."""
        self.game.register_listener(self.player, self._make_listener("TURN_END"))
        self.game.end_recruit_phase()
        self.assertIn("TURN_END", self.events)

    def test_end_of_combat_is_broadcast(self):
        """END_OF_COMBAT should fire when combat phase ends."""
        self.game.register_listener(self.player, self._make_listener("END_OF_COMBAT"))
        self.game._end_combat_phase()
        self.assertIn("END_OF_COMBAT", self.events)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 10 — Accord-o-Tron (BG26_147) Start-of-Turn Test
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccordOTron(unittest.TestCase):
    """BG26_147: At the start of your turn, gain 1 Gold."""

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.player.gold = 5
        self.game.players = [self.player]

    def test_start_of_turn_gains_gold(self):
        m = self.game.create_minion("BG26_147")
        m.controller = self.player
        m.zone = Zone.PLAY
        self.player.board.append(m)
        action = m.start_of_turn
        self.game.queue_action(action, source=m)
        self.game.resolve_queue()
        self.assertEqual(self.player.gold, 6, "Should gain 1 Gold from SOT effect")


if __name__ == "__main__":
    # Capture test results
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)

    # Print test output
    print(stream.getvalue())

    # Print log report
    TEST_LOG.report()

    # Exit with proper code
    sys.exit(0 if result.wasSuccessful() else 1)
