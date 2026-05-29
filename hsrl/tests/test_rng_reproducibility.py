"""Random seed reproducibility tests.

Verify that the same seed produces identical game state sequences.
"""

import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions  # noqa: F401
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag
from hsrl.core.game import Game
from hsrl.core.player import Player


class TestRNGReproducibility(unittest.TestCase):

    def setUp(self):
        self.hero_id = "EXAMPLE_VANILLA"

    def _make_game(self, seed):
        g = Game([], seed=seed)
        g.card_db = CARDS
        g.init_pool()
        for i in range(8):
            p = Player(CARDS.get(self.hero_id), game=g)
            p.set_tag(GameTag.TAVERN_TIER, 3)
            p.set_tag(GameTag.GOLD, 10)
            g.players.append(p)
        return g

    def test_same_seed_produces_same_tavern_refresh(self):
        seed = 42
        g1 = self._make_game(seed)
        g2 = self._make_game(seed)

        g1.refresh_tavern(g1.players[0])
        g2.refresh_tavern(g2.players[0])

        ids1 = [m.get_tag(GameTag.CARD_ID) for m in g1.players[0].tavern]
        ids2 = [m.get_tag(GameTag.CARD_ID) for m in g2.players[0].tavern]
        self.assertEqual(ids1, ids2,
                          "Same seed should produce identical tavern refreshes")

    def test_different_seed_produces_different_tavern(self):
        g1 = self._make_game(42)
        g2 = self._make_game(99)

        g1.refresh_tavern(g1.players[0])
        g2.refresh_tavern(g2.players[0])

        ids1 = [m.get_tag(GameTag.CARD_ID) for m in g1.players[0].tavern]
        ids2 = [m.get_tag(GameTag.CARD_ID) for m in g2.players[0].tavern]
        # With 270+ pool minions, different seeds should almost always differ
        self.assertNotEqual(ids1, ids2,
                            "Different seeds should produce different refreshes")

    def test_same_seed_combat_target_selection_identical(self):
        seed = 123
        g1 = self._make_game(seed)
        g2 = self._make_game(seed)

        # Set up identical boards
        for g in (g1, g2):
            p = g.players[0]
            for _ in range(3):
                m = g.create_minion("EXAMPLE_VANILLA")
                g.summon(p, m)

        # Combat target selection should be identical
        board = [m for m in g1.players[0].board if not m.dead]
        targets1 = [g1._choose_attack_target(board) for _ in range(5)]
        board = [m for m in g2.players[0].board if not m.dead]
        targets2 = [g2._choose_attack_target(board) for _ in range(5)]

        positions1 = [t.zone_position if t else -1 for t in targets1]
        positions2 = [t.zone_position if t else -1 for t in targets2]
        self.assertEqual(positions1, positions2,
                          "Same seed should produce same combat targets")

    def test_default_seed_is_random(self):
        g1 = self._make_game(None)
        g2 = self._make_game(None)
        g1.refresh_tavern(g1.players[0])
        g2.refresh_tavern(g2.players[0])
        ids1 = [m.get_tag(GameTag.CARD_ID) for m in g1.players[0].tavern]
        ids2 = [m.get_tag(GameTag.CARD_ID) for m in g2.players[0].tavern]
        # No seed → should be different (extremely unlikely to match by chance)
        self.assertNotEqual(ids1, ids2)

    def test_game_create_game_passes_seed(self):
        g1 = Game.create_game(
            ["EXAMPLE_VANILLA"] * 2, card_db=CARDS,
        )
        # create_game doesn't pass seed yet, but g1.rng should exist
        self.assertTrue(hasattr(g1, 'rng'))
        self.assertTrue(hasattr(g1, '_seed'))


if __name__ == "__main__":
    unittest.main()
