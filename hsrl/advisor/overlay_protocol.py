"""
HSRL Adviser — Message Protocol

Defines the JSON message schemas used between the C# HDT plugin and the
Python inference server over WebSocket.

Direction legend:
  C# → Python: game_start, game_state, game_end
  Python → C#: suggestions, error
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Entity slot types ────────────────────────────────────────────────────────


@dataclass
class TavernSlot:
    card_id: str = ""
    atk: int = 0
    health: int = 0
    tier: int = 1
    cost: int = 3
    race: str = "INVALID"
    is_minion: bool = True
    is_spell: bool = False
    taunt: bool = False
    divine_shield: bool = False
    poisonous: bool = False
    reborn: bool = False
    frozen: bool = False


@dataclass
class HandSlot:
    card_id: str = ""
    atk: int = 0
    health: int = 0
    tier: int = 1
    cost: int = 0
    race: str = "INVALID"
    is_minion: bool = True
    is_spell: bool = False
    golden: bool = False
    battlecry: bool = False
    turns_in_hand: int = 0
    spellcraft: bool = False


@dataclass
class BoardSlot:
    atk: int = 0
    health: int = 0
    max_health: int = 0
    tier: int = 1
    taunt: bool = False
    divine_shield: bool = False
    divine_shield_intact: bool = False
    poisonous: bool = False
    venomous: bool = False
    reborn: bool = False
    windfury: bool = False
    cleave: bool = False
    golden: bool = False
    race: str = "INVALID"
    exhausted: bool = False


@dataclass
class TrinketSlot:
    card_id: str = ""
    cost: int = 0
    tier: int = 1
    has_start_of_combat: bool = False
    has_end_of_turn: bool = False
    has_start_of_turn: bool = False


@dataclass
class PlayerState:
    health: int = 40
    armor: int = 0
    gold: int = 3
    tavern_tier: int = 1
    upgrade_cost: int = 5
    hero_card_id: str = ""
    hero_power_used: bool = False
    hero_power_cost: int = 2
    hero_power_extra_uses: bool = False
    free_refresh_remaining: int = 0
    next_spell_cost_reduction: int = 0
    blood_gem_atk_bonus: int = 0
    blood_gem_health_bonus: int = 0
    pending_triple_reward_tier: int = 0


@dataclass
class OpponentSummary:
    health: int = 40
    armor: int = 0
    tavern_tier: int = 1
    board_size: int = 0
    alive: bool = True


# ── Top-level messages ───────────────────────────────────────────────────────


@dataclass
class GameStateMessage:
    """C# → Python: current Battlegrounds game state."""
    type: str = "game_state"
    game_id: str = ""
    turn: int = 1
    phase: str = "recruit"  # recruit | combat
    player: PlayerState = field(default_factory=PlayerState)
    tavern: list[Optional[TavernSlot]] = field(default_factory=lambda: [None] * 7)
    hand: list[Optional[HandSlot]] = field(default_factory=lambda: [None] * 10)
    board: list[Optional[BoardSlot]] = field(default_factory=lambda: [None] * 7)
    trinkets: list[Optional[TrinketSlot]] = field(default_factory=lambda: [None] * 2)
    opponents: list[OpponentSummary] = field(default_factory=list)
    alive_count: int = 8
    damage_cap: Optional[int] = None
    anomaly_card_id: str = ""


@dataclass
class ActionSuggestion:
    """One suggested action with its probability."""
    action: int = 25  # Default: END_TURN
    name: str = "end_turn"
    probability: float = 1.0


@dataclass
class SuggestionsMessage:
    """Python → C#: top-K action suggestions."""
    type: str = "suggestions"
    game_id: str = ""
    turn: int = 1
    actions: list[ActionSuggestion] = field(default_factory=list)
    value_estimate: float = 0.0
    predicted_rank: int = 4
    rearrangement: list[int] | None = None  # Suggested board slot order


@dataclass
class GameStartMessage:
    """C# → Python: new game started."""
    type: str = "game_start"
    game_id: str = ""
    hero_card_id: str = ""
    mmr: int = 0
    timestamp: str = ""


@dataclass
class GameEndMessage:
    """C# → Python: game ended."""
    type: str = "game_end"
    game_id: str = ""
    placement: int = 8
    mmr_change: int = 0


@dataclass
class ErrorMessage:
    """Python → C#: error response."""
    type: str = "error"
    message: str = ""
    game_id: str = ""


@dataclass
class RearrangeSuggestion:
    """Python → C#: suggested board arrangement."""
    type: str = "rearrange"
    game_id: str = ""
    turn: int = 1
    order: list[int] = field(default_factory=list)
    value_before: float = 0.0
    value_after: float = 0.0


# ── Helpers: deserialize from JSON dict ──────────────────────────────────────


def parse_game_state(data: dict) -> GameStateMessage:
    """Parse a game_state JSON dict into a GameStateMessage."""
    player = PlayerState(**data.get("player", {}))

    tavern = []
    for slot in data.get("tavern", []):
        tavern.append(TavernSlot(**slot) if slot else None)

    hand = []
    for slot in data.get("hand", []):
        hand.append(HandSlot(**slot) if slot else None)

    board = []
    for slot in data.get("board", []):
        board.append(BoardSlot(**slot) if slot else None)

    trinkets = []
    for slot in data.get("trinkets", []):
        trinkets.append(TrinketSlot(**slot) if slot else None)

    opponents = [OpponentSummary(**o) for o in data.get("opponents", [])]

    return GameStateMessage(
        type=data.get("type", "game_state"),
        game_id=data.get("game_id", ""),
        turn=data.get("turn", 1),
        phase=data.get("phase", "recruit"),
        player=player,
        tavern=tavern,
        hand=hand,
        board=board,
        trinkets=trinkets,
        opponents=opponents,
        alive_count=data.get("alive_count", 8),
        damage_cap=data.get("damage_cap"),
        anomaly_card_id=data.get("anomaly_card_id", ""),
    )


def parse_game_start(data: dict) -> GameStartMessage:
    """Parse a game_start JSON dict."""
    return GameStartMessage(
        type=data.get("type", "game_start"),
        game_id=data.get("game_id", ""),
        hero_card_id=data.get("hero_card_id", ""),
        mmr=data.get("mmr", 0),
        timestamp=data.get("timestamp", ""),
    )


def parse_game_end(data: dict) -> GameEndMessage:
    """Parse a game_end JSON dict."""
    return GameEndMessage(
        type=data.get("type", "game_end"),
        game_id=data.get("game_id", ""),
        placement=data.get("placement", 8),
        mmr_change=data.get("mmr_change", 0),
    )
