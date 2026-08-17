"""
HSRL RL Environment — Action Space Definition

Defines the Discrete(50) action space and maps between integer actions
and game method calls. Action semantics depend on the current ActionMode:

Action encoding (50 discrete actions):
  NORMAL mode:
    0-6:   Buy tavern slot N
    7-13:  Sell board minion N
    14-23: Play hand card N
    24:    Refresh tavern
    25:    Upgrade tavern tier
    26:    Freeze/unfreeze tavern
    27:    Use hero power
    28:    End turn
    29:    GET_BUDDY
    30:    REARRANGE board
  SELECT modes (TARGET, DISCOVER, TRINKET, START_CHOICE):
    0-N:   Select candidate N (only valid actions shown in mask)
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

import numpy as np
from gymnasium.spaces import Discrete

from hsrl.core.enums import CardType, GameTag

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player

NUM_ACTIONS = 50

class ActionMode(IntEnum):
    """Current action interpretation mode for the RL agent."""
    NORMAL = 0             # recruit-phase actions (buy/sell/play/refresh/etc.)
    START_CHOICE = 1       # start-of-game hero power choice
    TARGET_SELECT = 2      # board minion target selection (TargetedAction)
    TRINKET_SELECT = 3     # trinket selection (0-3 map to trinket options)
    DISCOVER_SELECT = 4    # discover choice (0-2 map to PendingChoice options)
    POSITION_SELECT = 5    # board position selection for rearrangement

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
SECOND_HERO_POWER = 31  # use secondary hero power (anomaly-granted)

# The first reserved action id
RESERVED_START = 32


def detect_action_mode(game, player, awaiting_start_choice=False,
                       awaiting_target=False, awaiting_trinket=False) -> int:
    """Detect the current ActionMode from game/env state.

    Priority: START_CHOICE > DISCOVER > TARGET > TRINKET > NORMAL
    """
    if awaiting_start_choice:
        return ActionMode.START_CHOICE
    if game is None:
        return ActionMode.START_CHOICE  # pre-game
    if game.has_pending_choice(player):
        return ActionMode.DISCOVER_SELECT
    if awaiting_target or game.has_pending_target(player):
        return ActionMode.TARGET_SELECT
    if awaiting_trinket or bool(getattr(player, '_pending_trinket_offers', None)):
        return ActionMode.TRINKET_SELECT
    return ActionMode.NORMAL


def make_action_space() -> Discrete:
    """Build the Discrete(50) action space."""
    return Discrete(NUM_ACTIONS)


def build_action_mask(game: "Game", player: "Player",
                      can_rearrange: bool = True,
                      awaiting_trinket_selection: bool = False,
                      awaiting_start_choice: bool = False,
                      start_choice_count: int = 0,
                      mode: int = ActionMode.NORMAL) -> np.ndarray:
    """Return boolean mask of shape (NUM_ACTIONS,) — True where action is legal.

    Must be called during recruit phase with the active player.

    can_rearrange: only allow REARRANGE if board changed since last rearrange.
    awaiting_trinket_selection: when True, repurpose actions 0-3 as trinket
        selection indices (only affordable offers are valid).
    """
    mask = np.zeros(NUM_ACTIONS, dtype=np.bool_)

    # ── Discover selection mode ──
    if mode == ActionMode.DISCOVER_SELECT:
        choice = game.get_pending_choice(player)
        if choice is not None:
            for i in range(min(len(choice.options), RESERVED_START)):
                mask[i] = True
        return mask

    # ── Deferred target selection mode ──
    if mode == ActionMode.TARGET_SELECT:
        for i in range(min(len(game.get_pending_target_candidates(player)), RESERVED_START)):
            mask[i] = True
        return mask

    # ── Pending choice auto-resolve (catch-all before normal mask building) ──
    pending_choice = game.get_pending_choice(player) if game is not None else None
    if pending_choice is not None:
        # Only END_TURN is valid until choice is resolved
        mask[END_TURN] = True
        return mask

    # ── Start choice mode ──
    if awaiting_start_choice:
        for i in range(min(start_choice_count, 4)):
            mask[i] = True
        return mask

    # ── Trinket selection mode ──
    if awaiting_trinket_selection:
        offers = getattr(player, '_pending_trinket_offers', []) or []
        for i in range(min(4, len(offers))):
            cid = offers[i]
            cost = _trinket_cost(game, cid)
            if player.gold >= cost:
                mask[i] = True
        mask[END_TURN] = True  # Allow declining trinket offer
        return mask

    # Buy tavern slots 0-6. The engine rejects purchases at the hand cap, so
    # the authoritative mask must not advertise those actions as executable.
    hand_has_space = len(player.hand) < 10
    for i in range(7):
        if hand_has_space and i < len(player.tavern):
            entity = player.tavern[i]
            cost = entity.get_tag(GameTag.COST, 3)
            ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct in (CardType.MINION, CardType.SPELL) and player.gold >= cost:
                mask[BUY_OFFSET + i] = True

    # Sell board slots 7-13
    living = [m for m in player.board if not m.dead]
    for i in range(7):
        if i < len(living):
            mask[SELL_OFFSET + i] = True

    # Play hand cards 14-23 (10 slots)
    board_count = len(player.get_board_minions())
    for i in range(10):
        if i < len(player.hand):
            card = player.hand[i]
            ct = card.get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct == CardType.SPELL:
                mask[PLAY_OFFSET + i] = True  # spells always playable
            elif ct == CardType.MINION and board_count < 7:
                mask[PLAY_OFFSET + i] = True  # minions need board space

    # Refresh (costs 1 gold or has free refresh)
    free_refreshes = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
    if player.gold >= 1 or free_refreshes > 0:
        mask[REFRESH] = True

    # Upgrade tavern
    upgrade_cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
    if player.gold >= upgrade_cost and player.tavern_tier < 7:
        mask[UPGRADE] = True

    # Freeze/unfreeze (always valid if there are tavern minions)
    if len(player.tavern) > 0:
        mask[FREEZE] = True

    # Hero power
    if (not player.get_tag(GameTag.HERO_POWER_USED, False)
            or player.get_tag(GameTag.HERO_POWER_EXTRA_USES, 0) > 0):
        hp_cost = player.hero_power_cost
        if player.gold >= hp_cost:
            mask[HERO_POWER] = True

    # Secondary hero power (anomaly-granted)
    if player.has_secondary_hero_power:
        if not player.get_tag(GameTag.SECONDARY_HERO_POWER_USED, False):
            shp_cost = player.secondary_hero_power_cost
            if player.gold >= shp_cost:
                mask[SECOND_HERO_POWER] = True

    # End turn (always valid)
    mask[END_TURN] = True

    # Rearrange — valid when board changed and ≥2 minions (once per change)
    if board_count >= 2 and can_rearrange:
        mask[REARRANGE] = True

    # Get Buddy (valid if meter is full, not yet obtained, and can afford)
    if (not player._buddy_obtained
            and player._buddy_card_id is not None
            and player._buddy_meter >= player._buddy_meter_max
            and player.gold >= player._buddy_cost):
        mask[GET_BUDDY] = True

    return mask


def decode_action(action_id: int, game: "Game", player: "Player",
                   awaiting_trinket_selection: bool = False) -> str | None:
    """Execute a discrete action for the player. Returns 'end_turn' if the
    action ends the recruit phase, or None otherwise.

    Invalid actions are silently ignored (no-op).

    awaiting_trinket_selection: when True, actions 0-3 select a trinket
        from player._pending_trinket_offers.
    """
    if awaiting_trinket_selection:
        if action_id == END_TURN:
            # Decline trinket offer — clear pending offers
            player._pending_trinket_offers = []
            return "end_turn"
        if 0 <= action_id <= 3:
            game.buy_trinket(player, action_id)
            return None
        return None

    if action_id == END_TURN:
        return "end_turn"

    if action_id == REFRESH:
        _do_refresh(game, player)
        return None

    if action_id == UPGRADE:
        _do_upgrade(game, player)
        return None

    if action_id == FREEZE:
        _do_freeze(player)
        return None

    if action_id == HERO_POWER:
        _do_hero_power(game, player)
        return None

    if action_id == SECOND_HERO_POWER:
        _do_secondary_hero_power(game, player)
        return None

    if action_id == GET_BUDDY:
        game.get_buddy(player)
        return None

    if action_id == REARRANGE:
        _do_rearrange(player)
        return None

    if BUY_OFFSET <= action_id <= BUY_OFFSET + 6:
        _do_buy(game, player, action_id - BUY_OFFSET)
        return None

    if SELL_OFFSET <= action_id <= SELL_OFFSET + 6:
        _do_sell(game, player, action_id - SELL_OFFSET)
        return None

    if PLAY_OFFSET <= action_id <= PLAY_OFFSET + 9:
        _do_play(game, player, action_id - PLAY_OFFSET)
        return None

    # Reserved — no-op
    return None


def _do_buy(game: "Game", player: "Player", slot: int) -> None:
    """Buy the entity at the given tavern slot."""
    if slot >= len(player.tavern):
        return
    entity = player.tavern[slot]
    ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
    if ct == CardType.MINION:
        game.buy_minion(player, entity)
    elif ct == CardType.SPELL:
        game.buy_spell(player, entity)


def _do_sell(game: "Game", player: "Player", slot: int) -> None:
    """Sell the minion at the given board slot."""
    living = [m for m in player.board if not m.dead]
    if slot >= len(living):
        return
    game.sell_minion(player, living[slot])


def _do_play(game: "Game", player: "Player", slot: int) -> None:
    """Play a card from hand (minion → board, spell → cast)."""
    if slot >= len(player.hand):
        return
    card = player.hand[slot]
    ct = card.get_tag(GameTag.CARDTYPE, CardType.INVALID)
    if ct == CardType.MINION:
        game.play_minion(player, card)
    elif ct == CardType.SPELL:
        game.play_spell(player, card)


def _do_refresh(game: "Game", player: "Player") -> None:
    """Refresh the tavern. Costs 1 gold or consumes a free refresh."""
    free_remaining = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
    if player.gold < 1 and free_remaining <= 0:
        return
    game.refresh_tavern(player)
    if free_remaining <= 0:
        from hsrl.core.actions import SpendGold
        game.queue_action(SpendGold(player, 1))
    else:
        player.set_tag(GameTag.FREE_REFRESH_REMAINING, free_remaining - 1)
    game.resolve_queue()


def _do_upgrade(game: "Game", player: "Player") -> None:
    """Upgrade the tavern tier."""
    from hsrl.core.actions import UpgradeTavern
    upgrade_cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
    if player.gold < upgrade_cost or player.tavern_tier >= 7:
        return
    game.queue_action(UpgradeTavern(player))
    game.resolve_queue()


def _do_freeze(player: "Player") -> None:
    """Toggle freeze on all tavern minions."""
    if not player.tavern:
        return
    # If any minion is frozen, unfreeze all; otherwise freeze all
    any_frozen = any(m.has_tag(GameTag.FROZEN) for m in player.tavern)
    for m in player.tavern:
        m.set_tag(GameTag.FROZEN, not any_frozen)


def _do_hero_power(game: "Game", player: "Player") -> None:
    """Use the hero power."""
    game.use_hero_power(player)


def _do_secondary_hero_power(game: "Game", player: "Player") -> None:
    """Use the secondary hero power."""
    from hsrl.core.actions import UseSecondaryHeroPower
    game.queue_action(UseSecondaryHeroPower(player))
    game.resolve_queue()


def _do_rearrange(player: "Player") -> None:
    """Rearrange board minions using a combat-aware heuristic.

    Strategy:
      1. Taunt minions first (leftmost), highest health within taunts
      2. Cleave minions next (to hit opponent's adjacency)
      3. Remaining non-taunts by attack descending
      4. Reborn / deathrattle minions after high-attack ones

    This is free and unlimited — the model learns to use it before combat.
    """
    living = [m for m in player.board if not m.dead]
    if len(living) < 2:
        return

    def _sort_key(m):
        taunt = 0 if m.has_tag(GameTag.TAUNT) else 2
        cleave = 1 if (taunt > 0 and m.has_tag(GameTag.CLEAVE)) else 0
        atk = -m.atk   # descending
        health = -m.health  # descending
        return (taunt, cleave, atk, health)

    living.sort(key=_sort_key)

    # Rebuild the board: put living in new order, preserve board size
    new_board = []
    for i, m in enumerate(living):
        m.set_tag(GameTag.ZONE_POSITION, i + 1)
        new_board.append(m)
    # Keep dead minions at end (maintain list length for index stability)
    for m in player.board:
        if m.dead:
            new_board.append(m)
    player.board = new_board


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
        SECOND_HERO_POWER: "second_hero_power",
        END_TURN: "end_turn",
        GET_BUDDY: "get_buddy",
        REARRANGE: "rearrange",
    }
    return names.get(action_id, f"reserved_{action_id}")


def _trinket_cost(game: "Game", card_id: str) -> int:
    """Return the gold cost of a trinket from card_db, or 99 if unknown."""
    data = game.card_db.get(card_id) if game.card_db else None
    return data.tags.get(GameTag.COST, 3) if data and data.tags else 99
