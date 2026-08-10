"""HSRL AI Agents."""

from hsrl.agents.mcts_agent import BeamSearchAgent

try:
    # Optional NN agent — requires the full v2 stack (gymnasium, torch, ...).
    from hsrl.agents.nn_mcts_agent import NNMCTSAgent
except Exception:  # pragma: no cover - optional dependency
    NNMCTSAgent = None  # type: ignore[assignment,misc]

__all__ = ["BeamSearchAgent", "NNMCTSAgent"]
