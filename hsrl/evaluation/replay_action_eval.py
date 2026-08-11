"""Action-level replay evaluation with explicit metric coverage.

The evaluator consumes normalized P4 JSONL records. It does not pretend that
turn-level board snapshots contain expert actions or counterfactual outcomes:
each metric is reported as unavailable until its required fields are present.

Run:
    python -m hsrl.evaluation.replay_action_eval replay.jsonl --format markdown
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


SCHEMA_VERSION = 1


def canonical_action(action: Any) -> tuple | None:
    """Return an exact action identity including target/position/order."""
    if isinstance(action, int):
        return ("legacy", action)
    if not isinstance(action, dict):
        return None
    if isinstance(action.get("action"), dict):
        action = action["action"]
    name = str(action.get("action", action.get("name", ""))).strip().lower()
    if not name:
        legacy_id = action.get("legacy_id")
        return ("legacy", legacy_id) if isinstance(legacy_id, int) else None
    order = action.get("order")
    if isinstance(order, list):
        order = tuple(order)
    return (
        name,
        action.get("slot"),
        action.get("position"),
        action.get("target_slot"),
        order,
    )


def action_name(action: Any) -> str:
    key = canonical_action(action)
    if not key:
        return ""
    return str(key[0])


@dataclass
class ScalarMetric:
    total: float = 0.0
    count: int = 0
    eligible: int = 0

    def add(self, value: float) -> None:
        self.total += float(value)
        self.count += 1

    def result(self, *, percent: bool = False) -> dict:
        value = None if self.count == 0 else self.total / self.count
        if percent and value is not None:
            value *= 100.0
        coverage = None if self.eligible == 0 else self.count / self.eligible
        return {
            "value": value,
            "n": self.count,
            "eligible": self.eligible,
            "coverage": coverage,
        }


@dataclass
class ReplayActionEvaluator:
    policy_filter: str | None = None
    decisions: int = 0
    games: int = 0
    malformed_records: int = 0
    exact_match: ScalarMetric = field(default_factory=ScalarMetric)
    expert_top3: ScalarMetric = field(default_factory=ScalarMetric)
    board_regret: ScalarMetric = field(default_factory=ScalarMetric)
    signed_board_gap: ScalarMetric = field(default_factory=ScalarMetric)
    gold_waste: ScalarMetric = field(default_factory=ScalarMetric)
    premature_commit: ScalarMetric = field(default_factory=ScalarMetric)
    meaningless_refresh: ScalarMetric = field(default_factory=ScalarMetric)
    missed_enabler: ScalarMetric = field(default_factory=ScalarMetric)
    upgrade_damage: ScalarMetric = field(default_factory=ScalarMetric)
    positioning_regret: ScalarMetric = field(default_factory=ScalarMetric)
    placement: ScalarMetric = field(default_factory=ScalarMetric)
    top4: ScalarMetric = field(default_factory=ScalarMetric)
    _actors_by_game: dict = field(default_factory=dict, repr=False)

    def consume(self, record: dict) -> None:
        if record.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            self.malformed_records += 1
            return
        record_type = record.get("type")
        if record_type == "game_start":
            self._actors_by_game[record.get("game_id", "")] = {
                item.get("seat"): item.get("policy")
                for item in record.get("actors", []) if isinstance(item, dict)
            }
        elif record_type == "decision":
            self._consume_decision(record)
        elif record_type == "game_end":
            self._consume_game_end(record)
        elif record_type == "game_error":
            return
        else:
            self.malformed_records += 1

    def consume_all(self, records: Iterable[dict]) -> "ReplayActionEvaluator":
        for record in records:
            self.consume(record)
        return self

    def _consume_decision(self, record: dict) -> None:
        if self.policy_filter and record.get("behavior_policy") != self.policy_filter:
            return
        self.decisions += 1
        expert = canonical_action(record.get("expert_action"))
        ranking = record.get("model_topk") or []
        model_keys = [canonical_action(item) for item in ranking]
        model_keys = [key for key in model_keys if key is not None]

        self.exact_match.eligible += 1
        self.expert_top3.eligible += 1
        if expert is not None and model_keys:
            self.exact_match.add(expert == model_keys[0])
            self.expert_top3.add(expert in model_keys[:3])

        labels = record.get("labels") or {}
        expert_score = labels.get("expert_board_score_after")
        model_score = labels.get("model_board_score_after")
        self.board_regret.eligible += 1
        self.signed_board_gap.eligible += 1
        if _number(expert_score) and _number(model_score):
            gap = float(expert_score) - float(model_score)
            self.signed_board_gap.add(gap)
            self.board_regret.add(max(0.0, gap))

        self.gold_waste.eligible += 1
        if _number(labels.get("avoidable_gold_waste")):
            self.gold_waste.add(labels["avoidable_gold_waste"])

        if "premature_commit" in labels:
            self.premature_commit.eligible += 1
            if isinstance(labels["premature_commit"], bool):
                self.premature_commit.add(labels["premature_commit"])

        model_action = ranking[0] if ranking else None
        if action_name(model_action) == "refresh":
            self.meaningless_refresh.eligible += 1
            if isinstance(labels.get("meaningless_refresh"), bool):
                self.meaningless_refresh.add(labels["meaningless_refresh"])

        if labels.get("enabler_opportunity") is True:
            self.missed_enabler.eligible += 1
            if isinstance(labels.get("missed_enabler"), bool):
                self.missed_enabler.add(labels["missed_enabler"])

        if action_name(model_action) == "upgrade":
            self.upgrade_damage.eligible += 1
            if _number(labels.get("upgrade_expected_damage")):
                self.upgrade_damage.add(labels["upgrade_expected_damage"])

        expert_win = labels.get("expert_position_win_prob")
        model_win = labels.get("model_position_win_prob")
        if expert_win is not None or model_win is not None:
            self.positioning_regret.eligible += 1
            if _number(expert_win) and _number(model_win):
                self.positioning_regret.add(max(0.0, float(expert_win) - float(model_win)))

    def _consume_game_end(self, record: dict) -> None:
        ranks = []
        if isinstance(record.get("placements"), list):
            actors = self._actors_by_game.get(record.get("game_id", ""), {})
            for item in record["placements"]:
                if not isinstance(item, dict):
                    continue
                if self.policy_filter and actors.get(item.get("seat")) != self.policy_filter:
                    continue
                ranks.append(item.get("placement"))
        else:
            ranks.append(record.get("placement"))
        if ranks:
            self.games += 1
        for rank in ranks:
            self.placement.eligible += 1
            self.top4.eligible += 1
            if isinstance(rank, int) and 1 <= rank <= 8:
                self.placement.add(rank)
                self.top4.add(rank <= 4)

    def summary(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "decisions": self.decisions,
            "games": self.games,
            "malformed_records": self.malformed_records,
            "metrics": {
                "next_action_accuracy_pct": self.exact_match.result(percent=True),
                "expert_action_in_model_top3_pct": self.expert_top3.result(percent=True),
                "board_score_regret": self.board_regret.result(),
                "expert_minus_model_board_score": self.signed_board_gap.result(),
                "avoidable_gold_waste": self.gold_waste.result(),
                "premature_commit_rate_pct": self.premature_commit.result(percent=True),
                "meaningless_refresh_rate_pct": self.meaningless_refresh.result(percent=True),
                "missed_enabler_rate_pct": self.missed_enabler.result(percent=True),
                "expected_damage_after_upgrade": self.upgrade_damage.result(),
                "positioning_win_probability_regret": self.positioning_regret.result(),
                "average_placement": self.placement.result(),
                "top4_rate_pct": self.top4.result(percent=True),
            },
        }


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def iter_jsonl(paths: Iterable[str]) -> Iterator[dict]:
    for raw_path in paths:
        path = Path(raw_path)
        files = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
        for file_path in files:
            with file_path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"{file_path}:{line_number}: {exc}") from exc


def render_markdown(summary: dict) -> str:
    lines = [
        f"decisions={summary['decisions']} games={summary['games']} malformed={summary['malformed_records']}",
        "",
        "| metric | value | n/eligible | coverage |",
        "|---|---:|---:|---:|",
    ]
    for name, metric in summary["metrics"].items():
        value = "N/A" if metric["value"] is None else f"{metric['value']:.4f}"
        coverage = "N/A" if metric["coverage"] is None else f"{metric['coverage'] * 100:.1f}%"
        lines.append(f"| {name} | {value} | {metric['n']}/{metric['eligible']} | {coverage} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate normalized P4 action replay JSONL")
    parser.add_argument("paths", nargs="+", help="JSONL file(s) or directories")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--policy", default=None, help="optional behavior policy filter, e.g. llm or beam")
    args = parser.parse_args()
    summary = ReplayActionEvaluator(policy_filter=args.policy).consume_all(iter_jsonl(args.paths)).summary()
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(summary))


if __name__ == "__main__":
    main()
