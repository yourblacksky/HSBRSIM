"""Regression tests for deterministic behavior across Python processes."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class TestHashSeedDeterminism(unittest.TestCase):
    def test_trinket_tribe_index_is_stable_across_hash_seeds(self):
        """Trinket classification must not depend on set iteration order."""
        script = """
import hashlib
import json

import hsrl.cards.anomalies
import hsrl.cards.minions
import hsrl.cards.rewards
import hsrl.cards.spells
import hsrl.cards.trinkets
from hsrl.core.card_db import CARDS
from hsrl.core.game import Game

Game._trinket_tribe_index = None
index = Game._get_trinket_tribe_index(CARDS)
canonical = {key or \"NEUTRAL\": value for key, value in index.items()}
payload = json.dumps(canonical, sort_keys=True, separators=(\",\", \":\"))
print(hashlib.sha256(payload.encode(\"utf-8\")).hexdigest())
"""
        repo_root = Path(__file__).resolve().parents[2]
        digests = []
        for seed in ("0", "1", "2", "42"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = str(repo_root)
            output = subprocess.check_output(
                [sys.executable, "-c", script],
                cwd=repo_root,
                env=env,
                text=True,
            )
            digests.append(output.strip())

        self.assertEqual(len(set(digests)), 1, digests)


if __name__ == "__main__":
    unittest.main()
