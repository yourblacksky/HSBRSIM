"""Shared training constants (compat).

``hsrl/train/wrappers.py`` was referenced by the old agent stack
(``hsrl/agents/nn_mcts_agent.py``) but never shipped. The flat keys below
match the dict returned by ``build_observation_v2``.
"""

from __future__ import annotations

# Keys produced by hsrl.rl_env.observation.observation_v2.build_observation_v2
FLAT_OBS_KEYS = [
    "entity_stats",
    "entity_mask",
    "entity_groups",
    "global_features",
    "hero_features",
    "opponent_features",
]
