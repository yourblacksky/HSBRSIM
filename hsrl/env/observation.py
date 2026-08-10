"""Legacy observation API (compat shim over Observation V2).

``hsrl/env/observation.py`` never shipped with the repo, but
``hsrl/agents/nn_mcts_agent.py`` imports ``build_observation`` from it.
The v2 implementation lives in ``hsrl.rl_env.observation.observation_v2``
and returns a dict with the same look-up semantics (``obs.get(key)``).
"""

from __future__ import annotations

from hsrl.rl_env.observation.observation_v2 import build_observation_v2


def build_observation(game, player, include_opponents: bool = False) -> dict:
    """Legacy API: build_observation(game, player) -> Observation V2 dict."""
    return build_observation_v2(game, player, include_opponents=include_opponents)
