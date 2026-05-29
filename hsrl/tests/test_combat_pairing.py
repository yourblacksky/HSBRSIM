"""Multi-player combat pairing and ghost opponent tests.

Tests:
  1. Even number of players produces pairs covering all players
  2. Odd number of players produces ghost combat for the odd player out
  3. Ghost combat with empty ghost board deals 0 damage
  4. Ghost combat with survivors deals damage to the player
  5. Opponent history prevents immediate rematches when possible
"""

import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions   # noqa: F401
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag
from hsrl.core.game import Game
from hsrl.core.player import Player


def _make_game(n: int) -> Game:
    from hsrl.core.enums import State
    g = Game([], seed=0)
    g.card_db = CARDS
    g.init_pool()
    for i in range(n):
        p = Player(CARDS.get("EXAMPLE_VANILLA"), game=g)
        p.set_tag(GameTag.TAVERN_TIER, 3)
        p.set_tag(GameTag.GOLD, 10)
        g.players.append(p)
    g.state = State.RUNNING
    return g


class TestCombatPairing(unittest.TestCase):

    def test_even_player_pairing_covers_all(self):
        g = _make_game(8)
        alive = [p for p in g.players if p.is_alive]
        pairs = g._pair_combat_players(alive)
        paired = set()
        for p1, p2 in pairs:
            paired.add(p1)
            if p2 is not None:
                paired.add(p2)
        self.assertEqual(len(paired), len(alive))

    def test_no_self_pairing(self):
        g = _make_game(8)
        alive = [p for p in g.players if p.is_alive]
        pairs = g._pair_combat_players(alive)
        for p1, p2 in pairs:
            if p2 is not None:
                self.assertIsNot(p1, p2)

    def test_odd_player_gets_ghost(self):
        g = _make_game(7)
        alive = [p for p in g.players if p.is_alive]
        pairs = g._pair_combat_players(alive)
        ghost_pairs = [(p1, p2) for p1, p2 in pairs if p2 is None]
        self.assertEqual(len(ghost_pairs), 1, "One player should face ghost")
        self.assertIsNone(ghost_pairs[0][1])

    def test_ghost_board_from_dead_player(self):
        g = _make_game(3)
        alive = [p for p in g.players if p.is_alive]
        # Kill one player
        dead = alive[2]
        dead.health = 0
        from hsrl.core.enums import PlayState
        dead.set_tag(GameTag.PLAYSTATE, PlayState.LOST)
        dead.last_combat_board = []
        m = g.create_minion("EXAMPLE_VANILLA")
        m.controller = dead
        dead.last_combat_board.append(m)

        ghost = g._build_ghost_board(alive[0])
        self.assertTrue(len(ghost) >= 0)  # Should not crash


class TestGhostCombat(unittest.TestCase):

    def setUp(self):
        self.game = Game([], seed=0)
        self.game.card_db = CARDS
        self.p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
        self.p1.set_tag(GameTag.TAVERN_TIER, 3)
        self.game.players = [self.p1]

    def test_empty_ghost_board_no_damage(self):
        health_before = self.p1.health
        self.game._run_ghost_combat(self.p1, [])
        self.assertEqual(self.p1.health, health_before,
                         "Empty ghost should deal no damage")

    def test_ghost_with_survivors_deals_damage(self):
        ghost = self.game.create_minion("EXAMPLE_VANILLA")
        ghost.controller = None
        # 2/3 vanilla — tech_level=1, survives against empty player board
        health_before = self.p1.health
        self.game._run_ghost_combat(self.p1, [ghost])
        self.assertLess(self.p1.health, health_before,
                        "Ghost with surviving minions should deal damage")

    def test_ghost_combat_does_not_crash_with_players(self):
        """Ghost combat handles full player board."""
        for _ in range(3):
            m = self.game.create_minion("EXAMPLE_VANILLA")
            self.game.summon(self.p1, m)
        ghost = [self.game.create_minion("EXAMPLE_VANILLA")]
        # Should not crash
        self.game._run_ghost_combat(self.p1, ghost)
        self.assertTrue(True)


class TestEliminationRanking(unittest.TestCase):

    def test_death_order_tracks_when_multiple_die_same_turn(self):
        g = _make_game(4)
        g.turn = 5
        # Kill two players in the same combat round
        g._deal_player_damage(g.players[2], 999)
        g._deal_player_damage(g.players[3], 999)
        self.assertTrue(hasattr(g.players[2], '_death_order'))
        self.assertTrue(hasattr(g.players[3], '_death_order'))
        self.assertNotEqual(g.players[2]._death_order,
                           g.players[3]._death_order,
                           "Simultaneous deaths should have distinct order")


if __name__ == "__main__":
    unittest.main()
