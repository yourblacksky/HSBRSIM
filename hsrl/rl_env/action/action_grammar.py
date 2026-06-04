"""
ActionGrammar — enumerates legal structured AtomicActions from game state.

Bridges the Game engine API to the structured action system.
Supports: atomic enumeration, legacy mask, model output decoding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hsrl.core.enums import CardType, GameTag
from hsrl.rl_env.action.atomic_action import (
    AtomicAction, ActionType, ZoneType,
    buy, sell, play, roll, level, freeze, end_turn,
    hero_power, discover_choose, noop,
)

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player

# Number of action types = len of the StrEnum
ACTION_TYPE_COUNT = len(ActionType)

# Legacy mask size
LEGACY_NUM_ACTIONS = 50


class ActionGrammar:
    """Enumerates legal structured actions for a given game state."""

    def enumerate_legal_atomic_actions(
        self, game: "Game", player: "Player",
    ) -> list[AtomicAction]:
        """Return all legal AtomicActions for the current state."""
        actions = []

        # BUY: tavern slots with affordable minions/spells
        for i, entity in enumerate(player.tavern[:7]):
            cost = entity.get_tag(GameTag.COST, 3)
            ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct in (CardType.MINION, CardType.SPELL) and player.gold >= cost:
                actions.append(buy(i))

        # SELL: living board minions
        living = [m for m in player.board if not m.dead]
        for i, _ in enumerate(living[:7]):
            actions.append(sell(i))

        # PLAY: hand cards (minions need board space, spells always playable)
        board_count = len(living)
        for i, card in enumerate(player.hand[:10]):
            ct = card.get_tag(GameTag.CARDTYPE, CardType.INVALID)
            if ct == CardType.SPELL:
                actions.append(play(i))
            elif ct == CardType.MINION and board_count < 7:
                actions.append(play(i))

        # ROLL: costs 1 gold or has free refresh
        free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        if player.gold >= 1 or free > 0:
            actions.append(roll())

        # LEVEL: can afford and not max tier
        upgrade_cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
        max_tier = 7 if player.get_tag(GameTag.TIER_7_UNLOCKED, False) else 6
        if player.gold >= upgrade_cost and player.tavern_tier < max_tier:
            actions.append(level())

        # FREEZE: toggle freeze on tavern (valid if any tavern minions)
        if len(player.tavern) > 0:
            actions.append(freeze())

        # HERO_POWER: not used this turn and can afford
        hp_used = player.get_tag(GameTag.HERO_POWER_USED, False)
        extra = player.get_tag(GameTag.HERO_POWER_EXTRA_USES, 0)
        if (not hp_used or extra > 0) and player.gold >= player.hero_power_cost:
            actions.append(hero_power())

        # END_TURN: always valid
        actions.append(end_turn())

        return actions

    def build_legacy_mask(
        self, game: "Game", player: "Player",
    ) -> np.ndarray:
        """Build a legacy 50-way boolean action mask (for old env compat)."""
        from hsrl.env.action import build_action_mask
        return build_action_mask(game, player)

    def build_structured_mask(
        self, game: "Game", player: "Player",
    ) -> dict[str, np.ndarray]:
        """Build structured masks for hierarchical model output.

        Returns:
            action_type_mask: (ACTION_TYPE_COUNT,) bool
            source_zone_mask: (len(ZoneType),) bool — valid source zones
            source_ptr_mask: (24,) bool — combined shop/board/hand valid pointers
        """
        legal = self.enumerate_legal_atomic_actions(game, player)

        type_mask = np.zeros(ACTION_TYPE_COUNT, dtype=bool)
        zone_mask = np.zeros(len(ZoneType), dtype=bool)
        ptr_mask = np.zeros(24, dtype=bool)  # shop(7) + board(7) + hand(10)

        for a in legal:
            type_idx = list(ActionType).index(a.action_type)
            type_mask[type_idx] = True

            if a.source_zone == ZoneType.SHOP and 0 <= a.source_index < 7:
                ptr_mask[a.source_index] = True
            elif a.source_zone == ZoneType.BOARD and 0 <= a.source_index < 7:
                ptr_mask[7 + a.source_index] = True
            elif a.source_zone == ZoneType.HAND and 0 <= a.source_index < 10:
                ptr_mask[14 + a.source_index] = True

        return {
            "action_type_mask": type_mask,
            "source_zone_mask": zone_mask,
            "source_ptr_mask": ptr_mask,
        }

    def action_to_legacy_id(self, action: AtomicAction) -> int | None:
        """Convert structured action to legacy 0-49 action id."""
        from hsrl.rl_env.action.atomic_action import action_to_legacy_id
        return action_to_legacy_id(action)

    def legacy_id_to_action(self, action_id: int) -> AtomicAction:
        """Convert legacy 0-49 action id to structured action."""
        from hsrl.rl_env.action.atomic_action import legacy_id_to_action
        return legacy_id_to_action(action_id)

    def execute_atomic(
        self, game: "Game", player: "Player", action: AtomicAction,
    ) -> bool:
        """Execute a structured atomic action via direct state mutation.
        Returns True if the action was applied successfully.
        Used for fast plan simulation (no engine events).
        """
        from hsrl.agents.agent_utils import simulate_action

        legacy_id = self.action_to_legacy_id(action)
        if legacy_id is None:
            return False
        return simulate_action(player, legacy_id)
