"""Regression tests for P4 action-level replay metrics."""

import unittest

from hsrl.evaluation.replay_action_eval import ReplayActionEvaluator, canonical_action


class TestReplayActionEvaluator(unittest.TestCase):
    def test_canonical_action_includes_position_and_order(self):
        self.assertNotEqual(
            canonical_action({"action": "play", "slot": 0, "position": 0}),
            canonical_action({"action": "play", "slot": 0, "position": 1}),
        )
        self.assertEqual(
            canonical_action({"action": "reorder", "order": [2, 0, 1]}),
            ("reorder", None, None, None, (2, 0, 1)),
        )

    def test_all_requested_metrics_and_denominators(self):
        records = [
            {
                "type": "decision", "schema_version": 1,
                "expert_action": {"action": "buy", "slot": 1},
                "model_topk": [
                    {"action": "refresh", "probability": 0.5},
                    {"action": "buy", "slot": 1, "probability": 0.3},
                    {"action": "end_turn", "probability": 0.2},
                ],
                "labels": {
                    "expert_board_score_after": 20.0,
                    "model_board_score_after": 17.0,
                    "avoidable_gold_waste": 1,
                    "premature_commit": True,
                    "meaningless_refresh": True,
                    "enabler_opportunity": True,
                    "missed_enabler": True,
                },
            },
            {
                "type": "decision", "schema_version": 1,
                "expert_action": {"action": "upgrade"},
                "model_topk": [{"action": "upgrade"}],
                "labels": {
                    "expert_board_score_after": 12.0,
                    "model_board_score_after": 14.0,
                    "avoidable_gold_waste": 0,
                    "premature_commit": False,
                    "upgrade_expected_damage": 6.5,
                    "expert_position_win_prob": 0.70,
                    "model_position_win_prob": 0.55,
                },
            },
            {"type": "game_end", "schema_version": 1, "placement": 3},
        ]
        summary = ReplayActionEvaluator().consume_all(records).summary()
        metrics = summary["metrics"]
        self.assertEqual(metrics["next_action_accuracy_pct"]["value"], 50.0)
        self.assertEqual(metrics["expert_action_in_model_top3_pct"]["value"], 100.0)
        self.assertEqual(metrics["board_score_regret"]["value"], 1.5)
        self.assertEqual(metrics["expert_minus_model_board_score"]["value"], 0.5)
        self.assertEqual(metrics["avoidable_gold_waste"]["value"], 0.5)
        self.assertEqual(metrics["premature_commit_rate_pct"]["value"], 50.0)
        self.assertEqual(metrics["meaningless_refresh_rate_pct"]["value"], 100.0)
        self.assertEqual(metrics["missed_enabler_rate_pct"]["value"], 100.0)
        self.assertEqual(metrics["expected_damage_after_upgrade"]["value"], 6.5)
        self.assertAlmostEqual(metrics["positioning_win_probability_regret"]["value"], 0.15)
        self.assertEqual(metrics["average_placement"]["value"], 3.0)
        self.assertEqual(metrics["top4_rate_pct"]["value"], 100.0)

    def test_missing_counterfactuals_are_na_not_zero(self):
        record = {
            "type": "decision", "schema_version": 1,
            "expert_action": {"action": "end_turn"},
            "model_topk": [{"action": "end_turn"}],
            "labels": {},
        }
        metrics = ReplayActionEvaluator().consume_all([record]).summary()["metrics"]
        self.assertIsNone(metrics["board_score_regret"]["value"])
        self.assertEqual(metrics["board_score_regret"]["coverage"], 0.0)
        self.assertIsNone(metrics["expected_damage_after_upgrade"]["coverage"])

    def test_bridge_game_end_can_be_filtered_by_behavior_policy(self):
        records = [
            {"type": "game_start", "game_id": "g", "actors": [
                {"seat": 0, "policy": "llm"}, {"seat": 1, "policy": "beam"},
            ]},
            {"type": "game_end", "game_id": "g", "placements": [
                {"seat": 0, "placement": 2}, {"seat": 1, "placement": 7},
            ]},
        ]
        metrics = ReplayActionEvaluator(policy_filter="llm").consume_all(records).summary()["metrics"]
        self.assertEqual(metrics["average_placement"]["value"], 2.0)
        self.assertEqual(metrics["top4_rate_pct"]["value"], 100.0)


if __name__ == "__main__":
    unittest.main()
