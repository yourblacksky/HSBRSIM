"""Regression tests for the single-patch runtime closure contract."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import hsrl.cards.heroes  # noqa: F401 - populate hero registry
from hsrl.core.card_db import CARDS
from hsrl.core.enums import GameTag
from hsrl.core.game import Game
from hsrl.runtime_version import (
    RuntimeVersionError,
    current_runtime_manifest,
    validate_runtime_manifest,
)


class TestRuntimeVersionClosure(unittest.TestCase):
    def test_checked_in_runtime_is_closed(self):
        runtime = validate_runtime_manifest(use_cache=False)
        self.assertEqual(runtime["patch"], "35.6.0.243002")
        self.assertEqual(runtime["carddefs"]["build"], 243002)

    def test_tavish_mapping_matches_35_6_carddefs(self):
        validate_runtime_manifest(use_cache=False)
        tavish = CARDS.get("BG22_HERO_000")
        self.assertIsNotNone(tavish)
        self.assertEqual(
            tavish.tags[GameTag.HERO_POWER],
            "BG22_HERO_000p_Alt",
        )
        self.assertIsNone(tavish.scripts)

    def test_wrong_carddefs_build_fails_closed(self):
        manifest = current_runtime_manifest()
        with tempfile.TemporaryDirectory() as directory:
            carddefs = Path(directory) / "CardDefs.xml"
            carddefs.write_text(
                '<?xml version="1.0"?><CardDefs build="248348"></CardDefs>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeVersionError, "CardDefs"):
                validate_runtime_manifest(
                    expected=manifest,
                    carddefs_path=carddefs,
                    use_cache=False,
                )

    def test_match_start_propagates_version_failure(self):
        with mock.patch(
            "hsrl.runtime_version.validate_runtime_manifest",
            side_effect=RuntimeVersionError("forced mismatch"),
        ):
            with self.assertRaisesRegex(RuntimeVersionError, "forced mismatch"):
                Game.create_game(["EXAMPLE_HERO"], CARDS, seed=1)

    def test_tavish_formal_match_is_refused_until_lock_and_load_exists(self):
        with self.assertRaisesRegex(
            RuntimeVersionError, "unsupported version-correct power",
        ):
            Game.create_game(["BG22_HERO_000"], CARDS, seed=1)

    def test_manifest_id_is_stable_and_content_addressed(self):
        first = current_runtime_manifest()
        second = current_runtime_manifest()
        self.assertEqual(first["manifest_id"], second["manifest_id"])
        self.assertRegex(first["manifest_id"], r"^hsbrsim-35\.6\.0\.243002-[0-9a-f]{16}$")
        payload = dict(first)
        payload.pop("manifest_id")
        self.assertTrue(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
