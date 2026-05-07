"""
HSRL Adviser — HDT Plugin Backend

Provides real-time game state capture and trajectory collection for
Battlegrounds players via HDT. Optional model inference for action
suggestions (requires sb3-contrib and a trained checkpoint).
"""

from hsrl.advisor.overlay_protocol import (
    ActionSuggestion,
    GameStateMessage,
    SuggestionsMessage,
)
from hsrl.advisor.state_mapper import StateMapper
from hsrl.advisor.collector import DataCollector
from hsrl.advisor.server import AdviserServer

__all__ = [
    "ActionSuggestion",
    "AdviserServer",
    "DataCollector",
    "GameStateMessage",
    "StateMapper",
    "SuggestionsMessage",
]
