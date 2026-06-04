"""
Shared utilities for HSRL agents (SearchAgent, AZAgent, etc.).

Extracts duplicated code around:
  - Player state save/restore
  - Simplified action simulation (for lookahead search)
  - Plausible tavern generation (for beam search REFRESH simulation)
  - Auto-play hand minions
  - Trinket cost resolution
  - Value network version resolution and loading
"""

from __future__ import annotations

import random
from typing import Optional

from hsrl.core.enums import CardType, GameTag
from hsrl.env.action import (
    BUY_OFFSET, SELL_OFFSET, PLAY_OFFSET,
    REFRESH, UPGRADE, FREEZE, HERO_POWER, END_TURN,
    NUM_ACTIONS,
)

# ── Tags to save/restore during simulation ──────────────────────────────
_SAVE_TAGS = [
    GameTag.HERO_POWER_USED,
    GameTag.HERO_POWER_EXTRA_USES,
    GameTag.FREE_REFRESH_REMAINING,
    GameTag.TAVERN_UPGRADE_COST,
    GameTag.TAVERN_MINION_COST_OVERRIDE,
    GameTag.FIRST_MINION_FREE,
    GameTag.NEXT_SPELL_COST_REDUCTION,
    GameTag.BLOOD_GEM_BONUS_ATK,
    GameTag.BLOOD_GEM_BONUS_HEALTH,
]


def save_player_state(player) -> dict:
    """Save mutable player state for simulation rollback."""
    return {
        "gold": player.gold,
        "board": list(player.board),
        "hand": list(player.hand),
        "tavern": list(player.tavern),
        "tags": {tag: player.get_tag(tag, 0) for tag in _SAVE_TAGS},
        "health": player.health,
        "tavern_tier": player.tavern_tier,
        "armor": player.armor,
    }


def restore_player_state(player, saved: dict):
    """Restore player state from a savepoint."""
    player.gold = saved["gold"]
    player.board = list(saved["board"])
    player.hand = list(saved["hand"])
    player.tavern = list(saved["tavern"])
    player.health = saved["health"]
    player.tavern_tier = saved["tavern_tier"]
    player.armor = saved["armor"]
    for tag, val in saved["tags"].items():
        player.set_tag(tag, val)


# ── Simplified action simulation (no engine events) ──────────────────────

def simulate_action(player, action: int) -> bool:
    """Apply a single action via direct state manipulation.

    Used for fast forward simulation in one-step lookahead / beam search.
    Returns True if the action was applied successfully.
    """
    if BUY_OFFSET <= action <= BUY_OFFSET + 6:
        slot = action - BUY_OFFSET
        if slot >= len(player.tavern):
            return False
        entity = player.tavern.pop(slot)
        cost = entity.get_tag(GameTag.COST, 3)
        if player.gold < cost:
            player.tavern.insert(slot, entity)
            return False
        player.gold -= cost
        player.hand.append(entity)
        return True

    if SELL_OFFSET <= action <= SELL_OFFSET + 6:
        slot = action - SELL_OFFSET
        living = [m for m in player.board if not m.dead]
        if slot >= len(living):
            return False
        entity = living[slot]
        if entity in player.board:
            player.board.remove(entity)
        player.gold += 1
        return True

    if PLAY_OFFSET <= action <= PLAY_OFFSET + 9:
        slot = action - PLAY_OFFSET
        if slot >= len(player.hand):
            return False
        board_living = player.get_board_minions()
        if len(board_living) >= 7:
            return False
        entity = player.hand.pop(slot)
        ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
        if ct != CardType.MINION:
            player.hand.insert(slot, entity)
            return False
        player.board.append(entity)
        return True

    if action == REFRESH:
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        if player.gold < 1 and free <= 0:
            return False
        if free > 0:
            player.set_tag(GameTag.FREE_REFRESH_REMAINING, free - 1)
        else:
            player.gold -= 1
        return True

    if action == UPGRADE:
        _BASE_COST = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10}
        cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
        if player.gold < cost or player.tavern_tier >= 7:
            return False
        player.gold -= cost
        player.tavern_tier += 1
        next_base = _BASE_COST.get(player.tavern_tier + 1, 10)
        player.set_tag(GameTag.TAVERN_UPGRADE_COST, next_base)
        return True

    if action == FREEZE:
        return True

    if action == HERO_POWER:
        hp_cost = player.hero_power_cost
        if player.gold < hp_cost:
            return False
        player.gold -= hp_cost
        player.set_tag(GameTag.HERO_POWER_USED, True)
        return True

    if action == END_TURN:
        return True

    return False


# ── Plausible tavern generation (for beam search REFRESH) ────────────────

_TIER_STATS = {
    1: (2, 3), 2: (3, 4), 3: (4, 5),
    4: (5, 6), 5: (6, 7), 6: (7, 8),
}


def populate_tavern(player, rng: random.Random):
    """Generate plausible minions in the tavern based on player tier.

    Used in beam search to enable evaluation of REFRESH→BUY sequences.
    Minion stats are randomized around tier-appropriate baselines.
    """
    from hsrl.core.entity import BaseEntity, CardData

    player.tavern.clear()
    tier = player.tavern_tier
    base_atk, base_hp = _TIER_STATS.get(tier, (4, 4))
    variance = tier

    for _ in range(7):
        atk = max(1, base_atk + rng.randint(-variance, variance))
        hp = max(1, base_hp + rng.randint(-variance, variance + 1))
        data = CardData(id=f"fake_T{tier}", name=f"Tier{tier}", text="",
                        cardtype=CardType.MINION, tech_level=tier)
        entity = BaseEntity(data)
        entity.controller = player
        entity.set_tag(GameTag.COST, 3)
        entity.set_tag(GameTag.TECH_LEVEL, tier)
        entity.set_tag(GameTag.ATK, atk)
        entity.set_tag(GameTag.HEALTH, hp)
        entity.set_tag(GameTag.BASE_ATK, atk)
        entity.set_tag(GameTag.BASE_HEALTH, hp)
        entity.set_tag(GameTag.CARDTYPE, CardType.MINION)
        entity.set_tag(GameTag.RACE, 0)
        player.tavern.append(entity)


# ── Auto-play and helpers ─────────────────────────────────────────────────

def find_auto_play(player, mask) -> Optional[int]:
    """Find the first playable minion in hand. Returns action id or None."""
    hand_plays = [a for a in range(PLAY_OFFSET, PLAY_OFFSET + 10) if mask[a]]
    for a in hand_plays:
        slot = a - PLAY_OFFSET
        if slot < len(player.hand):
            ct = player.hand[slot].get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct == CardType.MINION:
                return a
    return None


def get_productive_actions(mask) -> list[int]:
    """Return all legal actions except END_TURN and HERO_POWER."""
    actions = []
    for a in range(NUM_ACTIONS):
        if mask[a] and a not in (END_TURN, HERO_POWER):
            actions.append(a)
    return actions


def get_trinket_cost(game, card_id: str) -> int:
    """Resolve trinket cost from card database."""
    data = game.card_db.get(card_id) if game.card_db else None
    return data.tags.get(GameTag.COST, 3) if data and data.tags else 99


# ── Value network loading helper ─────────────────────────────────────────

def load_value_network_for_agent(checkpoint_path: str, device: str = "cpu"):
    """Load value network from checkpoint, auto-detecting version.

    Returns (model, encode_fn, version_string).
    """
    import torch

    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    ckpt_version = ckpt.get("version", "v2")

    if ckpt_version in ("dense",):
        from hsrl.train.value_dense import DenseValueNetwork, encode_pomdp_state
        model = DenseValueNetwork()
    elif ckpt_version in ("v4",):
        from hsrl.train.game_value_sp import GameValueNetwork, encode_pomdp_state
        model = GameValueNetwork()
    else:
        from hsrl.train.game_value import GameValueNetwork, encode_pomdp_state
        model = GameValueNetwork()

    model.load_state_dict(ckpt.get("model_state_dict", ckpt), strict=False)
    model = model.to(device)
    model.eval()
    return model, encode_pomdp_state, ckpt_version
