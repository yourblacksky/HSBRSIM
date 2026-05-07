"""
Action space constants shared between the advisor and the RL environment.

These define the Discrete(50) action encoding used by the HDT plugin
to build action masks and interpret suggested actions.
"""

NUM_ACTIONS = 50

# Action type constants
BUY_OFFSET = 0       # 0-6   (7 tavern slots)
SELL_OFFSET = 7      # 7-13  (7 board slots)
PLAY_OFFSET = 14     # 14-23 (10 hand slots)
REFRESH = 24
UPGRADE = 25
FREEZE = 26
HERO_POWER = 27
END_TURN = 28
GET_BUDDY = 29
REARRANGE = 30       # rearrange board minion positions

# The first reserved action id
RESERVED_START = 31


def get_action_name(action_id: int) -> str:
    """Return a human-readable name for an action id."""
    if BUY_OFFSET <= action_id <= BUY_OFFSET + 6:
        return f"buy_tavern_{action_id - BUY_OFFSET}"
    if SELL_OFFSET <= action_id <= SELL_OFFSET + 6:
        return f"sell_board_{action_id - SELL_OFFSET}"
    if PLAY_OFFSET <= action_id <= PLAY_OFFSET + 9:
        return f"play_hand_{action_id - PLAY_OFFSET}"
    names = {
        REFRESH: "refresh",
        UPGRADE: "upgrade",
        FREEZE: "freeze",
        HERO_POWER: "hero_power",
        END_TURN: "end_turn",
        GET_BUDDY: "get_buddy",
        REARRANGE: "rearrange",
    }
    return names.get(action_id, f"reserved_{action_id}")
