"""Regression tests for the complete self-play environment."""

import unittest

from hsrl.core.enums import Race
from hsrl.rl_env.envs.full_game_env import _enum_name


class TestFullGameEnvironment(unittest.TestCase):
    def test_tribe_manifest_accepts_enum_and_raw_values(self):
        self.assertEqual(_enum_name(Race.BEAST), "BEAST")
        self.assertEqual(_enum_name(int(Race.DEMON)), "DEMON")


if __name__ == "__main__":
    unittest.main()
