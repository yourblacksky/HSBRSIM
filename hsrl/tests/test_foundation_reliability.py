"""Foundation reliability regressions for multiplayer scope and search purity."""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hsrl.cards.minions  # noqa: F401 - populate the card registry
from hsrl.agents.mcts_agent import BeamSearchAgent
from hsrl.core.actions import Action, PlayBloodGems, Summon
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag, Race, Step
from hsrl.core.exceptions import CombatResolutionTimeout
from hsrl.core.events import (
    EventListener,
    EventScope,
    MINION_BOUGHT,
    MINION_SOLD,
    START_OF_COMBAT,
    TAVERN_UPGRADED,
    TURN_BEGIN,
)
from hsrl.core.game import Game
from hsrl.core.player import Player


class _Increment(Action):
    def __init__(self, sink, key):
        super().__init__()
        self.sink = sink
        self.key = key

    def do(self, source, game, target=None):
        self.sink[self.key] = self.sink.get(self.key, 0) + 1


class _Rebroadcast(Action):
    def __init__(self, event_name):
        super().__init__()
        self.event_name = event_name

    def do(self, source, game, target=None):
        game.broadcast(self.event_name, source)


class FoundationGameCase(unittest.TestCase):
    def setUp(self):
        self.game = Game([], seed=7)
        self.game.card_db = CARDS
        self.players = [
            Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
            for _ in range(4)
        ]
        self.game.players = self.players

    def minion(self, player, atk=2, health=3):
        minion = self.game.create_minion("EXAMPLE_VANILLA")
        minion.set_tag(GameTag.BASE_ATK, atk)
        minion.set_tag(GameTag.BASE_HEALTH, health)
        minion.set_tag(GameTag.HEALTH, health)
        self.game.summon(player, minion)
        return minion

    def test_missing_patch_token_summon_is_safe_noop(self):
        before = list(self.players[0].board)
        self.game.queue_action(Summon(self.players[0], None))
        self.game.resolve_queue()
        self.assertEqual(self.players[0].board, before)


class TestCombatResolutionBudget(FoundationGameCase):
    def test_recursive_combat_event_raises_typed_timeout(self):
        self.game.combat_event_budget = 3
        self.game.in_combat = True
        self.game._start_combat_budget(self.players[0], self.players[1])
        self.game.register_listener(
            self.players[0],
            EventListener("LOOP", _Rebroadcast("LOOP")),
        )

        with self.assertRaises(CombatResolutionTimeout) as raised:
            self.game.broadcast("LOOP", self.players[0])

        error = raised.exception
        self.assertEqual(error.budget, "events")
        self.assertEqual(error.limit, 3)
        self.assertEqual(error.observed, 4)
        self.assertEqual(error.player_ids, (
            self.players[0].entity_id,
            self.players[1].entity_id,
        ))

    def test_combat_action_budget_counts_across_queue_resolutions(self):
        self.game.combat_action_budget = 2
        self.game.in_combat = True
        self.game._start_combat_budget(self.players[0], self.players[1])
        counts = {}
        for _ in range(3):
            self.game.queue_action(_Increment(counts, "actions"), self.players[0])

        with self.assertRaises(CombatResolutionTimeout) as raised:
            self.game.resolve_queue()

        self.assertEqual(raised.exception.budget, "actions")
        self.assertEqual(counts, {"actions": 2})


class TestBloodGemTriggerProvenance(FoundationGameCase):
    def test_hot_air_surveyor_repeats_only_hand_played_gems(self):
        player = self.players[0]
        surveyor = self.game.create_minion("BG30_121")
        target = self.minion(player)
        self.game.summon(player, surveyor)
        before = (target.atk, target.health)

        self.game.queue_action(
            PlayBloodGems(target, from_hand=True), source=player,
        )
        self.game.resolve_queue()
        self.assertEqual((target.atk, target.health), (before[0] + 2, before[1] + 2))

        self.game.queue_action(PlayBloodGems(target), source=player)
        self.game.resolve_queue()
        self.assertEqual((target.atk, target.health), (before[0] + 3, before[1] + 3))

    def test_two_geomagus_bonus_gems_do_not_recurse(self):
        player = self.players[0]
        first = self.game.create_minion("BG28_583")
        second = self.game.create_minion("BG28_583")
        self.game.summon(player, first)
        self.game.summon(player, second)
        before = (second.atk, second.health)

        self.game.queue_action(
            PlayBloodGems(first, from_hand=True), source=player,
        )
        self.game.resolve_queue()

        self.assertEqual((second.atk, second.health), (before[0] + 1, before[1] + 1))
        self.assertFalse(self.game._action_queue)


class TestOwnerEventScope(FoundationGameCase):
    def test_recruit_event_only_reaches_owners_listeners(self):
        counts = {}
        for index, player in enumerate(self.players[:2]):
            self.game.register_listener(
                player,
                EventListener(MINION_BOUGHT, _Increment(counts, index)),
            )
        bought = self.minion(self.players[0])

        self.game.broadcast(MINION_BOUGHT, bought, self.players[0])

        self.assertEqual(counts, {0: 1})

    def test_buy_sell_and_upgrade_are_owner_local(self):
        counts = {}
        events = (MINION_BOUGHT, MINION_SOLD, TAVERN_UPGRADED)
        for index, player in enumerate(self.players[:2]):
            for event_name in events:
                self.game.register_listener(
                    player,
                    EventListener(event_name, _Increment(counts, (index, event_name))),
                )
        minion = self.minion(self.players[0])

        self.game.broadcast(MINION_BOUGHT, minion, self.players[0])
        self.game.broadcast(MINION_SOLD, minion, self.players[0])
        self.game.broadcast(TAVERN_UPGRADED, self.players[0], 2)

        self.assertEqual(
            counts,
            {(0, event_name): 1 for event_name in events},
        )

    def test_global_scope_must_be_explicit(self):
        counts = {}
        ownerless = self.game.create_minion("EXAMPLE_VANILLA")
        self.game.register_listener(
            ownerless,
            EventListener(TURN_BEGIN, _Increment(counts, "implicit")),
        )
        self.game.register_listener(
            ownerless,
            EventListener(
                TURN_BEGIN,
                _Increment(counts, "explicit"),
                scope=EventScope.GLOBAL,
            ),
        )

        self.game.broadcast(TURN_BEGIN, self.players[0])

        self.assertEqual(counts, {"explicit": 1})

    def test_turn_begin_passes_each_listener_its_owner(self):
        counts = {}
        for index, player in enumerate(self.players[:2]):
            self.game.register_listener(
                player,
                EventListener(
                    TURN_BEGIN,
                    _Increment(counts, index),
                    condition=lambda event_player, owner=player: event_player is owner,
                ),
            )

        self.game._start_recruit_phase()

        self.assertEqual(counts, {0: 1, 1: 1})

    def test_start_of_combat_listener_fires_once_for_its_owner(self):
        counts = {}
        for index, player in enumerate(self.players):
            self.game.register_listener(
                player,
                EventListener(START_OF_COMBAT, _Increment(counts, index)),
            )
            self.minion(player)
        self.game.in_combat = True
        self.game.step = Step.COMBAT
        self.game._current_combat_opponents = {
            self.players[0]: self.players[1],
            self.players[1]: self.players[0],
        }

        self.game._trigger_start_of_combat(self.players[0].board, self.players[0])
        self.game._trigger_start_of_combat(self.players[1].board, self.players[1])
        self.game.resolve_queue()

        self.assertEqual(counts, {0: 1, 1: 1})


class TestCombatPairIsolation(FoundationGameCase):
    def test_enemy_lookup_never_includes_third_party_board(self):
        current_enemy = self.minion(self.players[1])
        third_party = self.minion(self.players[2])
        self.game._current_combat_opponents = {
            self.players[0]: self.players[1],
            self.players[1]: self.players[0],
        }

        enemies = self.game.get_living_enemies(self.players[0])

        self.assertEqual(enemies, [current_enemy])
        self.assertNotIn(third_party, enemies)

    def test_death_scan_does_not_process_third_party_board(self):
        self.minion(self.players[0])
        self.minion(self.players[1])
        third_party = self.minion(self.players[2], health=1)
        third_party.health = 0
        self.game.in_combat = True
        self.game.step = Step.COMBAT
        self.game._current_combat_opponents = {
            self.players[0]: self.players[1],
            self.players[1]: self.players[0],
        }

        self.game._check_deaths()

        self.assertIn(third_party, self.players[2].board)
        self.assertNotIn(third_party, self.players[2].graveyard)


class TestKnownHeroIsolation(FoundationGameCase):
    def setUp(self):
        super().setUp()
        while len(self.players) < 8:
            player = Player(CARDS.get("EXAMPLE_VANILLA"), game=self.game)
            self.players.append(player)
        for player in self.players:
            minion = self.minion(player, atk=2, health=100)
            minion.set_tag(GameTag.RACE, Race.BEAST)

    def _third_party_stats(self):
        return [
            [(m.atk, m.health, copy.deepcopy(m.tags)) for m in p.board]
            for p in self.players[2:]
        ]

    def test_tavish_cannot_touch_a_combat_he_is_not_in(self):
        from hsrl.cards.heroes.scripts import DeadeyeScript

        tavish = self.players[2]
        tavish.set_tag(GameTag.HERO_POWER, "BG22_HERO_000p_t1")
        DeadeyeScript.on_summon(tavish, self.game)
        before = self._third_party_stats()

        self.game._run_combat(self.players[0], self.players[1])

        self.assertEqual(self._third_party_stats(), before)

    def test_illidan_cannot_touch_a_combat_he_is_not_in(self):
        from hsrl.cards.heroes.scripts import WingmenScript

        illidan = self.players[3]
        WingmenScript.on_summon(illidan, self.game)
        before = self._third_party_stats()

        self.game._run_combat(self.players[0], self.players[1])

        self.assertEqual(self._third_party_stats(), before)

    def test_wagtoggle_triggers_once_only_for_her_own_start(self):
        from hsrl.cards.heroes.scripts import WaxWarbandScript

        wagtoggle = self.players[0]
        WaxWarbandScript.on_summon(wagtoggle, self.game)
        own = wagtoggle.board[0]
        third_party = self.players[2].board[0]
        own_before = (own.atk, own.max_health)
        third_before = (third_party.atk, third_party.max_health)
        self.game.in_combat = True
        self.game.step = Step.COMBAT
        self.game._current_combat_opponents = {
            self.players[0]: self.players[1],
            self.players[1]: self.players[0],
        }

        self.game._trigger_start_of_combat(wagtoggle.board, wagtoggle)
        self.game._trigger_start_of_combat(self.players[1].board, self.players[1])
        self.game.resolve_queue()

        self.assertEqual((own.atk, own.max_health),
                         (own_before[0] + 2, own_before[1] + 2))
        self.assertEqual((third_party.atk, third_party.max_health), third_before)


class TestListenerLifecycle(FoundationGameCase):
    def test_sold_minion_listener_is_unregistered(self):
        counts = {}
        minion = self.minion(self.players[0])
        self.game.register_listener(
            minion,
            EventListener(TURN_BEGIN, _Increment(counts, "sold")),
        )

        self.game.sell_minion(self.players[0], minion)
        self.game.broadcast(TURN_BEGIN, self.players[0])

        self.assertEqual(counts, {})

    def test_dead_minion_listener_is_unregistered(self):
        counts = {}
        minion = self.minion(self.players[0], health=1)
        self.game.register_listener(
            minion,
            EventListener(TURN_BEGIN, _Increment(counts, "dead")),
        )
        minion.health = 0

        self.game._check_deaths()
        self.game.broadcast(TURN_BEGIN, self.players[0])

        self.assertEqual(counts, {})


class TestBeamSearchPurity(FoundationGameCase):
    def test_act_does_not_mutate_player_or_entity_state(self):
        player = self.players[0]
        player.gold = 10
        player.tavern_tier = 1
        player.set_tag(GameTag.TAVERN_UPGRADE_COST, 5)
        self.minion(player)
        tavern_minion = self.game.create_minion("EXAMPLE_VANILLA")
        tavern_minion.controller = player
        player.tavern.append(tavern_minion)

        before = {
            "tags": copy.deepcopy(player.tags),
            "board": [(m, m.snapshot()) for m in player.board],
            "hand": [(m, m.snapshot()) for m in player.hand],
            "tavern": [(m, m.snapshot()) for m in player.tavern],
        }

        BeamSearchAgent(beam_width=3, max_depth=4, seed=11).act(self.game, player)

        self.assertEqual(player.tags, before["tags"])
        for zone in ("board", "hand", "tavern"):
            entities = getattr(player, zone)
            self.assertEqual(entities, [entity for entity, _ in before[zone]])
            for entity, snapshot in before[zone]:
                self.assertEqual(entity.snapshot(), snapshot)


if __name__ == "__main__":
    unittest.main()
