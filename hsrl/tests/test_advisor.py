"""
Tests for HSRL Adviser — HDT plugin backend.

Covers:
  1. overlay_protocol — message parsing and serialization
  2. state_mapper — HDT JSON → flat observation vector
  3. inference — model loading and prediction
  4. collector — data recording and persistence
  5. server — action mask builder and message handling
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from hsrl.advisor.overlay_protocol import (
    ActionSuggestion,
    BoardSlot,
    ErrorMessage,
    GameEndMessage,
    GameStartMessage,
    GameStateMessage,
    HandSlot,
    OpponentSummary,
    PlayerState,
    SuggestionsMessage,
    TavernSlot,
    TrinketSlot,
    parse_game_end,
    parse_game_start,
    parse_game_state,
)
from hsrl.advisor.state_mapper import FLAT_OBS_DIM, StateMapper
from hsrl.advisor.collector import DataCollector
from hsrl.advisor.server import build_action_mask_from_state
from hsrl.env.action import NUM_ACTIONS, END_TURN, REFRESH, UPGRADE, FREEZE, HERO_POWER


# ══════════════════════════════════════════════════════════════════════════════
# overlay_protocol tests
# ══════════════════════════════════════════════════════════════════════════════


class TestOverlayProtocol:
    """Test message dataclasses and JSON parsing."""

    def test_game_state_message_defaults(self):
        msg = GameStateMessage()
        assert msg.type == "game_state"
        assert msg.turn == 1
        assert msg.phase == "recruit"
        assert len(msg.tavern) == 7
        assert len(msg.hand) == 10
        assert len(msg.board) == 7
        assert len(msg.trinkets) == 2
        assert all(s is None for s in msg.tavern)

    def test_parse_game_state_full(self):
        data = {
            "type": "game_state",
            "game_id": "abc123",
            "turn": 5,
            "phase": "recruit",
            "player": {
                "health": 35, "armor": 5, "gold": 7, "tavern_tier": 3,
                "upgrade_cost": 6, "hero_card_id": "TEST_HERO",
                "hero_power_used": False, "hero_power_cost": 2,
                "hero_power_extra_uses": False, "free_refresh_remaining": 1,
                "next_spell_cost_reduction": 0, "blood_gem_atk_bonus": 2,
                "blood_gem_health_bonus": 1, "pending_triple_reward_tier": 0,
            },
            "tavern": [
                {"card_id": "BGS_001", "atk": 2, "health": 3, "tier": 1, "cost": 3,
                 "race": "BEAST", "is_minion": True, "is_spell": False,
                 "taunt": False, "divine_shield": False, "poisonous": False,
                 "reborn": False, "frozen": False},
                None, None, None, None, None, None,
            ],
            "hand": [None] * 10,
            "board": [None] * 7,
            "trinkets": [None, None],
            "opponents": [
                {"health": 40, "armor": 10, "tavern_tier": 3, "board_size": 5, "alive": True}
            ] * 7,
            "alive_count": 8,
            "damage_cap": 15,
            "anomaly_card_id": "",
        }
        msg = parse_game_state(data)
        assert msg.game_id == "abc123"
        assert msg.turn == 5
        assert msg.player.health == 35
        assert msg.player.gold == 7
        assert msg.player.tavern_tier == 3
        assert msg.tavern[0] is not None
        assert msg.tavern[0].card_id == "BGS_001"
        assert msg.tavern[0].race == "BEAST"
        assert msg.tavern[1] is None
        assert msg.alive_count == 8
        assert msg.damage_cap == 15

    def test_parse_game_state_null_slots(self):
        """Slots can be null in JSON."""
        data = {
            "type": "game_state",
            "game_id": "test",
            "turn": 1,
            "phase": "recruit",
            "player": {},
            "tavern": [None] * 7,
            "hand": [None] * 10,
            "board": [None] * 7,
            "trinkets": [None, None],
            "opponents": [],
            "alive_count": 8,
        }
        msg = parse_game_state(data)
        assert all(s is None for s in msg.tavern)

    def test_parse_game_state_missing_fields(self):
        """Missing optional fields should use defaults."""
        data = {
            "type": "game_state",
            "game_id": "minimal",
            "turn": 1,
            "phase": "recruit",
            "player": {},
            "tavern": [],
            "hand": [],
            "board": [],
            "trinkets": [],
            "opponents": [],
            "alive_count": 8,
        }
        msg = parse_game_state(data)
        assert msg.damage_cap is None
        assert msg.anomaly_card_id == ""

    def test_parse_game_start(self):
        data = {
            "type": "game_start",
            "game_id": "g1",
            "hero_card_id": "TB_BaconShop_HERO_59",
            "mmr": 7500,
            "timestamp": "2026-05-05T12:00:00",
        }
        msg = parse_game_start(data)
        assert msg.game_id == "g1"
        assert msg.mmr == 7500

    def test_parse_game_end(self):
        data = {
            "type": "game_end",
            "game_id": "g1",
            "placement": 3,
            "mmr_change": 15,
        }
        msg = parse_game_end(data)
        assert msg.placement == 3
        assert msg.mmr_change == 15

    def test_suggestions_message_serialization(self):
        msg = SuggestionsMessage(
            game_id="test",
            turn=5,
            actions=[
                ActionSuggestion(action=25, name="upgrade", probability=0.5),
                ActionSuggestion(action=0, name="buy_tavern_0", probability=0.3),
            ],
            value_estimate=0.123,
            predicted_rank=3,
        )
        import dataclasses
        d = dataclasses.asdict(msg)
        assert d["type"] == "suggestions"
        assert len(d["actions"]) == 2
        assert d["actions"][0]["probability"] == 0.5

    def test_error_message_serialization(self):
        msg = ErrorMessage(message="test error", game_id="g1")
        assert msg.__dict__["type"] == "error"


# ══════════════════════════════════════════════════════════════════════════════
# state_mapper tests
# ══════════════════════════════════════════════════════════════════════════════


class TestStateMapper:
    """Test HDT JSON → HrSRL observation mapping."""

    @staticmethod
    def _make_state(**overrides) -> GameStateMessage:
        """Build a minimal valid GameStateMessage."""
        defaults = dict(
            game_id="test", turn=3, phase="recruit",
            player=PlayerState(health=38, armor=5, gold=7, tavern_tier=2),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None],
            opponents=[OpponentSummary(health=40, alive=True)] * 7,
            alive_count=8,
        )
        defaults.update(overrides)
        return GameStateMessage(**defaults)

    def test_output_shape(self):
        mapper = StateMapper()
        msg = self._make_state()
        obs = mapper.map(msg)
        assert obs.shape == (FLAT_OBS_DIM,)
        assert obs.dtype == np.float32

    def test_global_features(self):
        mapper = StateMapper()
        msg = self._make_state(turn=10, alive_count=4)
        obs = mapper.map(msg)
        # Global starts at offset 0
        assert obs[0] == pytest.approx(10.0 / 20.0)  # turn normalized
        assert obs[2] == pytest.approx(4.0 / 8.0)     # alive count normalized

    def test_combat_phase_step_flag(self):
        mapper = StateMapper()
        msg = self._make_state(phase="combat")
        obs = mapper.map(msg)
        assert obs[1] == 0.0  # not recruit

    def test_player_feature_hp_gold(self):
        mapper = StateMapper()
        msg = self._make_state(player=PlayerState(health=20, gold=5))
        obs = mapper.map(msg)
        player_start = 20  # after GLOBAL_DIM
        assert obs[player_start + 0] == pytest.approx(20.0 / 40.0)
        assert obs[player_start + 2] == pytest.approx(5.0 / 10.0)

    def test_tavern_encoding(self):
        mapper = StateMapper()
        msg = self._make_state(
            tavern=[
                TavernSlot(card_id="BGS_001", atk=2, health=3, tier=1, cost=3,
                           race="BEAST", is_minion=True),
            ] + [None] * 6,
        )
        obs = mapper.map(msg)
        # Tavern starts at offset 20 + 15 = 35
        tavern_start = 35
        assert obs[tavern_start + 0] > 0.0  # atk encoded
        assert obs[tavern_start + 5] == 1.0  # is_minion

    def test_board_encoding(self):
        mapper = StateMapper()
        msg = self._make_state(
            board=[
                BoardSlot(atk=10, health=8, max_health=8, tier=2, taunt=True, race="DEMON"),
            ] + [None] * 6,
        )
        obs = mapper.map(msg)
        # Board starts at offset 20 + 15 + 7*12 + 10*12 = 239
        board_start = 20 + 15 + 7 * 12 + 10 * 12
        assert obs[board_start + 0] == pytest.approx(10.0 / 100.0)
        assert obs[board_start + 5] == 1.0  # taunt

    def test_all_zeros_for_empty_state(self):
        mapper = StateMapper()
        msg = self._make_state(alive_count=0, opponents=[])
        obs = mapper.map(msg)
        # With no alive count, rank should be 0
        alive_count_idx = 2
        assert obs[alive_count_idx] == 0.0

    def test_map_dict_shorthand(self):
        mapper = StateMapper()
        data = {
            "type": "game_state", "game_id": "t", "turn": 1, "phase": "recruit",
            "player": {}, "tavern": [], "hand": [], "board": [],
            "trinkets": [], "opponents": [], "alive_count": 8,
        }
        obs = mapper.map_dict(data)
        assert obs.shape == (FLAT_OBS_DIM,)

    def test_deterministic_output(self):
        mapper = StateMapper()
        msg = self._make_state(
            tavern=[TavernSlot(card_id="BGS_001", atk=2, health=3, tier=1, cost=3,
                               race="BEAST", is_minion=True)] + [None]*6,
        )
        obs1 = mapper.map(msg)
        obs2 = mapper.map(msg)
        np.testing.assert_array_equal(obs1, obs2)

    def test_race_mapping(self):
        mapper = StateMapper()
        for race in ["BEAST", "MURLOC", "DEMON", "MECH", "DRAGON", "PIRATE",
                      "ELEMENTAL", "QUILBOAR", "NAGA", "UNDEAD"]:
            msg = self._make_state(
                tavern=[TavernSlot(card_id="X", atk=0, health=0, tier=1, cost=1,
                                   race=race, is_minion=True)] + [None]*6,
            )
            obs = mapper.map(msg)
            tavern_start = 35
            race_val = obs[tavern_start + 4]
            assert race_val > 0.0, f"Race {race} should have non-zero encoding"


# ══════════════════════════════════════════════════════════════════════════════
# server action mask tests
# ══════════════════════════════════════════════════════════════════════════════


class TestActionMask:
    """Test build_action_mask_from_state with various game states."""

    def test_end_turn_always_valid(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=0, health=40),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert mask[END_TURN] == True

    def test_empty_tavern_no_buy(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=10, tavern_tier=1),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert not any(mask[0:7])  # No buy actions available

    def test_no_gold_no_buy_or_upgrade(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=0, tavern_tier=1, upgrade_cost=5),
            tavern=[
                TavernSlot(card_id="X", atk=2, health=3, tier=1, cost=3,
                           is_minion=True),
            ] + [None]*6,
            hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert not mask[0]       # Can't afford
        assert not mask[UPGRADE] # Can't afford
        assert not mask[REFRESH] # Can't afford
        assert mask[END_TURN]    # Always valid

    def test_board_full_no_play(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=10),
            tavern=[None]*7,
            hand=[
                HandSlot(card_id="X", atk=2, health=3, is_minion=True),
            ] + [None]*9,
            board=[
                BoardSlot(health=5) for _ in range(7)
            ],  # Full board
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert not mask[14]  # PLAY_OFFSET + 0 — board full

    def test_hero_power_used_no_extra(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=10, hero_power_used=True,
                              hero_power_cost=2, hero_power_extra_uses=False),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert not mask[HERO_POWER]

    def test_hero_power_extra_uses(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=10, hero_power_used=True,
                              hero_power_cost=2, hero_power_extra_uses=True),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert mask[HERO_POWER]

    def test_tier_7_no_upgrade(self):
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(gold=10, tavern_tier=7, upgrade_cost=10),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=8,
        )
        mask = build_action_mask_from_state(msg)
        assert not mask[UPGRADE]


# ══════════════════════════════════════════════════════════════════════════════
# collector tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDataCollector:
    """Test game data collection and persistence."""

    def test_collect_disabled(self):
        collector = DataCollector(enabled=False)
        collector.start_game("g1", {"hero": "TEST"})
        collector.record_step({}, 25)
        result = collector.end_game(3, 15)
        assert result is None

    def test_collect_enabled_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DataCollector(data_dir=tmpdir, enabled=True)
            collector.start_game("test_game_001", {"hero_card_id": "TEST_HERO", "mmr": 7000})
            collector.record_step({"turn": 1}, action_taken=25, turn=1)
            collector.record_step({"turn": 2}, action_taken=3, turn=2)
            filepath = collector.end_game(placement=4, mmr_change=-5)

            assert filepath is not None
            assert os.path.exists(filepath)

            # Read and verify content
            with open(filepath, "r") as f:
                lines = f.readlines()

            assert len(lines) == 4  # game_start, 2 steps, game_end

            start_line = json.loads(lines[0])
            assert start_line["type"] == "game_start"
            assert start_line["hero"] == "TEST_HERO"
            assert start_line["mmr"] == 7000

            step1 = json.loads(lines[1])
            assert step1["type"] == "step"
            assert step1["turn"] == 1
            assert step1["action_taken"] == 25

            end_line = json.loads(lines[3])
            assert end_line["type"] == "game_end"
            assert end_line["placement"] == 4
            assert end_line["mmr_change"] == -5

    def test_cancel_game_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DataCollector(data_dir=tmpdir, enabled=True)
            collector.start_game("test_cancel", {})
            collector.record_step({}, 25)
            collector.cancel_game()
            # Should not create any file
            jsonl_files = list(Path(tmpdir).rglob("*.jsonl"))
            assert len(jsonl_files) == 0

    def test_multiple_games(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DataCollector(data_dir=tmpdir, enabled=True)

            for i in range(3):
                collector.start_game(f"game_{i}", {"hero_card_id": f"HERO_{i}"})
                collector.record_step({}, 25 + i)
                collector.end_game(placement=i + 1, mmr_change=10)

            # Count files
            jsonl_files = list(Path(tmpdir).rglob("*.jsonl"))
            assert len(jsonl_files) == 3

    def test_total_games_collected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DataCollector(data_dir=tmpdir, enabled=True)
            collector.start_game("g1", {})
            collector.end_game(1)
            collector.start_game("g2", {})
            collector.end_game(2)

            assert collector.total_games_collected() == 2


# ══════════════════════════════════════════════════════════════════════════════
# inference smoke tests (requires model file — skipped if not available)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(
    not os.path.exists("checkpoints/selfplay_iter0099_20260505_171008.zip"),
    reason="Model checkpoint not available",
)
class TestInference:
    """Test model inference with a real checkpoint."""

    def test_load_and_predict(self):
        from hsrl.advisor.inference import ModelInference

        inference = ModelInference(
            "checkpoints/selfplay_iter0099_20260505_171008.zip"
        )

        obs = np.zeros(FLAT_OBS_DIM, dtype=np.float32)
        mask = np.zeros(NUM_ACTIONS, dtype=bool)
        mask[END_TURN] = True
        mask[REFRESH] = True

        best, suggestions, value = inference.predict(obs, mask)

        assert 0 <= best < NUM_ACTIONS
        assert len(suggestions) <= 5
        assert isinstance(value, float)
        for a, n, p in suggestions:
            assert 0 <= a < NUM_ACTIONS
            assert isinstance(n, str)
            assert 0.0 <= p <= 1.0

    def test_deterministic_inference(self):
        from hsrl.advisor.inference import ModelInference

        inference = ModelInference(
            "checkpoints/selfplay_iter0099_20260505_171008.zip"
        )

        obs = np.random.randn(FLAT_OBS_DIM).astype(np.float32) * 0.1
        mask = np.ones(NUM_ACTIONS, dtype=bool)

        best1, sug1, val1 = inference.predict(obs.copy(), mask.copy())
        best2, sug2, val2 = inference.predict(obs.copy(), mask.copy())

        assert best1 == best2
        assert val1 == pytest.approx(val2)
        for (a1, _, p1), (a2, _, p2) in zip(sug1, sug2):
            assert a1 == a2
            assert p1 == pytest.approx(p2)

    def test_predict_batch(self):
        from hsrl.advisor.inference import ModelInference

        inference = ModelInference(
            "checkpoints/selfplay_iter0099_20260505_171008.zip"
        )

        batch_obs = np.random.randn(4, FLAT_OBS_DIM).astype(np.float32) * 0.1
        batch_masks = np.ones((4, NUM_ACTIONS), dtype=bool)

        actions, values = inference.predict_batch(batch_obs, batch_masks)

        assert actions.shape == (4,)
        assert values.shape == (4,)
        assert all(0 <= a < NUM_ACTIONS for a in actions)


# ══════════════════════════════════════════════════════════════════════════════
# Edge case tests
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_health_player(self):
        mapper = StateMapper()
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(health=0, gold=0),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=1,
        )
        obs = mapper.map(msg)
        # Player HP at offset 20
        assert obs[20] == 0.0

    def test_max_health_armor_gold(self):
        mapper = StateMapper()
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(health=100, armor=50, gold=20),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=1,
        )
        obs = mapper.map(msg)
        # Should be capped at 1.0
        assert obs[20] <= 1.0
        assert obs[21] <= 1.0
        assert obs[22] <= 1.0

    def test_tavern_slot_with_spell(self):
        mapper = StateMapper()
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(),
            tavern=[
                TavernSlot(card_id="SPELL_001", tier=2, cost=2, is_minion=False, is_spell=True),
            ] + [None]*6,
            hand=[None]*10, board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=1,
        )
        obs = mapper.map(msg)
        tavern_start = 35
        # is_spell flag set
        assert obs[tavern_start + 6] == 1.0
        # atk/health should be 0 for spells
        assert obs[tavern_start + 0] == 0.0

    def test_hand_slot_with_golden_and_battlecry(self):
        mapper = StateMapper()
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(),
            tavern=[None]*7,
            hand=[
                HandSlot(card_id="X", atk=5, health=5, tier=3, cost=3,
                        is_minion=True, golden=True, battlecry=True, turns_in_hand=2),
            ] + [None]*9,
            board=[None]*7,
            trinkets=[None, None], opponents=[], alive_count=1,
        )
        obs = mapper.map(msg)
        hand_start = 20 + 15 + 7*12
        assert obs[hand_start + 7] == 1.0  # golden
        assert obs[hand_start + 8] == 1.0  # battlecry
        assert obs[hand_start + 9] == pytest.approx(2.0 / 5.0)  # turns_in_hand

    def test_trinket_with_scripts(self):
        mapper = StateMapper()
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[
                TrinketSlot(card_id="T1", cost=3, tier=2,
                           has_start_of_combat=True, has_start_of_turn=True),
                None,
            ],
            opponents=[], alive_count=1,
        )
        obs = mapper.map(msg)
        trinket_start = 20 + 15 + 7*12 + 10*12 + 7*15
        assert obs[trinket_start + 0] == 1.0  # present
        assert obs[trinket_start + 1] == pytest.approx(3.0 / 10.0)  # cost
        assert obs[trinket_start + 3] == 1.0  # start_of_combat
        assert obs[trinket_start + 5] == 1.0  # start_of_turn

    def test_none_trinket_second_slot(self):
        mapper = StateMapper()
        msg = GameStateMessage(
            game_id="t", turn=1, phase="recruit",
            player=PlayerState(),
            tavern=[None]*7, hand=[None]*10, board=[None]*7,
            trinkets=[None, None],
            opponents=[], alive_count=1,
        )
        obs = mapper.map(msg)
        trinket_start = 20 + 15 + 7*12 + 10*12 + 7*15
        # Second trinket slot should be all zeros
        second_start = trinket_start + 8
        assert np.all(obs[second_start:second_start + 8] == 0.0)
