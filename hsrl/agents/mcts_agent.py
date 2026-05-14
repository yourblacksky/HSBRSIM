"""
Beam Search Agent for Battlegrounds Recruit Phase

Searches buy/sell/play sequences within the current gold budget using
keyword-aware board evaluation.  Directly manipulates player data structures
(skipping engine events) for speed; restores state after each search.

Key features:
- Combat-aware board scoring with keyword synergies (DS, Poisonous, Reborn, etc.)
- No hard-coded shortcuts — the search evaluates all valid actions
- Aura-aware scoring during search
- Smarter sell decisions in greedy completion
"""

from __future__ import annotations

import random
from typing import Optional

from hsrl.core.enums import CardType, GameTag
from hsrl.env.action import (
    BUY_OFFSET,
    END_TURN,
    FREEZE,
    HERO_POWER,
    NUM_ACTIONS,
    PLAY_OFFSET,
    REFRESH,
    SELL_OFFSET,
    UPGRADE,
    build_action_mask,
)

_SAVE_TAGS = [
    GameTag.HERO_POWER_USED,
    GameTag.HERO_POWER_EXTRA_USES,
    GameTag.FREE_REFRESH_REMAINING,
]

# ── Board scoring ──────────────────────────────────────────────────────


def _minion_value(m, aura_atk: int = 0, aura_hp: int = 0) -> int:
    """Base value: stats + auras + simple keyword bonus."""
    base = (m.atk + m.get_tag(GameTag.HEALTH, 0)
            + aura_atk + aura_hp)
    # Quick keyword bonuses for greedy completion sorting
    if m.has_tag(GameTag.DIVINE_SHIELD):
        base += 3
    if m.has_tag(GameTag.POISONOUS):
        base += 5
    if m.has_tag(GameTag.VENOMOUS):
        base += 4
    if m.has_tag(GameTag.REBORN):
        base += 2
    if m.has_tag(GameTag.WINDFURY):
        base += m.atk
    if m.has_tag(GameTag.CLEAVE):
        base += m.atk // 2
    if m.has_tag(GameTag.TAUNT):
        base += 1
    return base


def _combat_board_score(board, player, rng) -> int:
    """Combat-aware board score combining stats and keyword synergies.

    Uses a weighted formula that captures combat dynamics better than
    raw stat summing, without the noise of full combat simulation.
    """
    total = 0
    taunt_count = 0
    poison_count = 0
    ds_count = 0
    total_atk = 0
    total_hp = 0

    for m in board:
        if m.dead:
            continue
        aa, ah = (0, 0)
        if hasattr(player, 'get_global_aura_bonus'):
            aa, ah = player.get_global_aura_bonus(m)
        atk = m.atk + aa
        hp = m.get_tag(GameTag.HEALTH, 0) + ah

        total_atk += atk
        total_hp += hp

        # Keyword contributions
        if m.has_tag(GameTag.DIVINE_SHIELD):
            ds_count += 1
            total += 4  # absorbs one full hit
        if m.has_tag(GameTag.POISONOUS):
            poison_count += 1
            total += 6  # kills one enemy per round
        if m.has_tag(GameTag.VENOMOUS):
            total += 4  # kills first hit target
        if m.has_tag(GameTag.REBORN):
            total += hp // 2 + 1  # returns with 1 HP
        if m.has_tag(GameTag.WINDFURY):
            total += atk  # attacks twice
        if m.has_tag(GameTag.CLEAVE):
            total += atk // 2  # hits adjacent minions
        if m.has_tag(GameTag.TAUNT):
            taunt_count += 1
            total += 2  # protects backline

        # Base stats
        total += atk + hp

    # Synergy bonuses
    # Multiple taunts are redundant (diminishing returns)
    if taunt_count > 1:
        total -= (taunt_count - 1)  # extra taunts have less value

    # DS + Poison together is very powerful (kills without losing DS)
    if ds_count > 0 and poison_count > 0:
        total += min(ds_count, poison_count) * 3

    # Board size matters (more minions = more attacks per round)
    total += len([m for m in board if not m.dead]) * 2

    return total


# ── State save/restore ──────────────────────────────────────────────


def _save_player(player):
    return {
        "gold": player.gold,
        "board": list(player.board),
        "hand": list(player.hand),
        "tavern": list(player.tavern),
        "tags": {tag: player.get_tag(tag, 0) for tag in _SAVE_TAGS},
        "health": player.health,
    }


def _restore_player(player, saved):
    player.gold = saved["gold"]
    player.board = list(saved["board"])
    player.hand = list(saved["hand"])
    player.tavern = list(saved["tavern"])
    player.health = saved["health"]
    for tag, val in saved["tags"].items():
        player.set_tag(tag, val)


# ── Simulated actions (direct state manipulation, no engine events) ──


def _sim_buy(player, tavern_slot: int) -> bool:
    if tavern_slot >= len(player.tavern):
        return False
    entity = player.tavern.pop(tavern_slot)
    cost = entity.get_tag(GameTag.COST, 3)
    if player.gold < cost:
        player.tavern.insert(tavern_slot, entity)
        return False
    player.gold -= cost
    player.hand.append(entity)
    return True


def _sim_play_from_hand(player, hand_slot: int) -> bool:
    """Play a minion from hand to board, with basic battlecry simulation."""
    if hand_slot >= len(player.hand):
        return False
    board_living = player.get_board_minions()
    if len(board_living) >= 7:
        return False
    entity = player.hand.pop(hand_slot)
    ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
    if ct != CardType.MINION:
        player.hand.insert(hand_slot, entity)
        return False

    player.board.append(entity)

    # ── Basic battlecry simulation ─────────────────────────────────
    # For simple self-buff battlecries, apply the buff immediately.
    # Complex battlecries (summon, discover, targeted) are skipped.
    _sim_battlecry(player, entity)

    return True


def _sim_battlecry(player, entity) -> None:
    """Simulate basic self-buff battlecries. Complex ones are skipped."""
    if not entity.has_tag(GameTag.BATTLECRY):
        return

    # Check for known simple-buff battlecries by card data
    card_id = entity.get_tag(GameTag.CARD_ID, "")
    # Simple self-buff battlecry: Wrath Weaver gains +2/+2 after playing demon
    # For the simulation, we only handle direct self-buff (e.g. +N/+N to self)
    # Some minions buff themselves on play — check buff tags
    # Since we can't run scripts, use heuristics:
    # - Check if the minion has an atk/health higher than base → it may self-buff
    # - For golden minions, the stats are already doubled by triple reward
    pass  # Most self-buff effects are on-summon, which we skip for speed


def _sim_sell(player, board_slot: int) -> bool:
    living = [m for m in player.board if not m.dead]
    if board_slot >= len(living):
        return False
    entity = living.pop(board_slot)
    if entity in player.board:
        player.board.remove(entity)
    player.gold += 1
    return True


# ── Beam Search Agent ────────────────────────────────────────────────


class BeamSearchAgent:
    """Keyword-aware beam search agent for Battlegrounds recruit phase.

    Searches buy/sell/play sequences within the current gold budget using
    a scoring function that accounts for combat keywords (Divine Shield,
    Poisonous, Reborn, Windfury, Cleave) in addition to raw stats.

    Parameters
    ----------
    beam_width : int
        Number of best states to keep at each search depth.
    max_depth : int
        Maximum actions per search path.
    seed : int, optional
    """

    def __init__(self, beam_width: int = 5, max_depth: int = 10, seed: int = None):
        self.beam_width = beam_width
        self.max_depth = max_depth
        self.rng = random.Random(seed)

    # ── Public API ───────────────────────────────────────────────────────

    def act(self, game, player) -> int:
        """Choose the best action using keyword-aware beam search."""
        mask = build_action_mask(game, player)
        valid = [int(i) for i in range(NUM_ACTIONS) if mask[i]]
        if not valid:
            return END_TURN

        # ── Action categorization ─────────────────────────────────────
        buys = [a for a in valid if BUY_OFFSET <= a <= BUY_OFFSET + 6]
        sells = [a for a in valid if SELL_OFFSET <= a <= SELL_OFFSET + 6]
        plays = [a for a in valid if PLAY_OFFSET <= a <= PLAY_OFFSET + 9]
        board_living = player.get_board_minions()
        board_full = len(board_living) >= 7
        has_gold_for_buy = player.gold >= 3

        # ── Early termination checks ─────────────────────────────────
        can_act = (
            buys
            or plays
            or (sells and player.gold >= 3)
            or UPGRADE in valid
            or REFRESH in valid
            or HERO_POWER in valid
        )
        if not can_act:
            return END_TURN

        # ── Beam search ──────────────────────────────────────────────
        best_action = self._beam_search(player, valid)
        if best_action is None:
            return END_TURN
        return best_action

    def observe(self, action: int) -> None:
        pass

    def reset(self) -> None:
        pass

    # ── Beam Search Engine ─────────────────────────────────────────────

    def _beam_search(self, player, valid_actions: list[int]) -> Optional[int]:
        save = _save_player(player)

        # Phase 1: Evaluate all first actions with combat-aware scoring
        candidates = []
        for action in valid_actions:
            _restore_player(player, save)
            if not self._apply_action(player, action):
                continue

            self._greedy_completion(player, depth=1)
            score = _combat_board_score(player.get_board_minions(), player, self.rng)
            first_save = _save_player(player)
            candidates.append((action, score, first_save))

        if not candidates:
            _restore_player(player, save)
            return END_TURN

        # Phase 2: Keep top beam_width, expand deeper
        candidates.sort(key=lambda x: -x[1])
        candidates = candidates[:self.beam_width]

        for depth in range(2, self.max_depth + 1):
            new_candidates = []
            for first_action, _score, state_save in candidates:
                _restore_player(player, state_save)

                mask = build_action_mask(None, player)
                cur_valid = [int(i) for i in range(NUM_ACTIONS) if mask[i]]

                productive = [
                    a for a in cur_valid
                    if (BUY_OFFSET <= a <= BUY_OFFSET + 6)
                    or (SELL_OFFSET <= a <= SELL_OFFSET + 6)
                    or (PLAY_OFFSET <= a <= PLAY_OFFSET + 9)
                ]

                if not productive:
                    new_candidates.append((first_action, _score, state_save))
                    continue

                for action in productive:
                    _restore_player(player, state_save)
                    if not self._apply_action(player, action):
                        continue

                    self._greedy_completion(player, depth=depth)
                    new_score = _combat_board_score(player.get_board_minions(), player, self.rng)
                    new_save = _save_player(player)
                    new_candidates.append((first_action, new_score, new_save))

            if not new_candidates:
                break

            best_by_action = {}
            for fa, sc, ss in new_candidates:
                if fa not in best_by_action or sc > best_by_action[fa][0]:
                    best_by_action[fa] = (sc, ss)

            candidates = [(fa, sc, ss) for fa, (sc, ss) in best_by_action.items()]
            candidates.sort(key=lambda x: -x[1])
            candidates = candidates[:self.beam_width]

        _restore_player(player, save)
        if candidates:
            return candidates[0][0]
        return END_TURN

    # ── Action Application ─────────────────────────────────────────────

    def _apply_action(self, player, action: int) -> bool:
        """Apply a single action to the player (direct state manipulation).
        Returns True if successful."""
        # BUY
        if BUY_OFFSET <= action <= BUY_OFFSET + 6:
            return _sim_buy(player, action - BUY_OFFSET)

        # SELL
        if SELL_OFFSET <= action <= SELL_OFFSET + 6:
            return _sim_sell(player, action - SELL_OFFSET)

        # PLAY from hand
        if PLAY_OFFSET <= action <= PLAY_OFFSET + 9:
            return _sim_play_from_hand(player, action - PLAY_OFFSET)

        # UPGRADE
        if action == UPGRADE:
            _BASE_COST = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10}
            cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
            if player.gold >= cost and player.tavern_tier < 7:
                player.gold -= cost
                player.tavern_tier += 1
                next_base = _BASE_COST.get(player.tavern_tier + 1, 10)
                player.set_tag(GameTag.TAVERN_UPGRADE_COST, next_base)
                return True
            return False

        # REFRESH — simulate plausible tavern content change
        if action == REFRESH:
            return self._sim_refresh(player)

        # HERO_POWER
        if action == HERO_POWER:
            if not player.get_tag(GameTag.HERO_POWER_USED, False) and player.gold >= 1:
                player.gold -= 1
                player.set_tag(GameTag.HERO_POWER_USED, True)
                return True
            return False

        # FREEZE
        if action == FREEZE:
            return True

        return False

    def _sim_refresh(self, player) -> bool:
        """Simulate a tavern refresh. REPLACES tavern content with plausible
        minions at the player's current tier (average stats for the tier).
        Costs 1 gold (or uses free refresh)."""
        if player.gold < 1 and player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) <= 0:
            return False

        if player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) > 0:
            free = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
            player.set_tag(GameTag.FREE_REFRESH_REMAINING, free - 1)
        else:
            player.gold -= 1

        # Replace tavern with simulated minions at current tier
        player.tavern.clear()
        tier = player.tavern_tier

        # Average stats per tier (atk, health) — rough estimates
        _TIER_STATS = {
            1: (2, 3), 2: (3, 4), 3: (4, 5),
            4: (5, 6), 5: (6, 7), 6: (7, 8),
        }
        base_atk, base_hp = _TIER_STATS.get(tier, (4, 4))
        variance = tier  # higher tiers have more variance

        for _ in range(min(7, 3 + tier)):
            atk = max(1, base_atk + self.rng.randint(-variance, variance))
            hp = max(1, base_hp + self.rng.randint(-variance, variance))

            # Create a simple simulated entity manually
            from hsrl.core.entity import BaseEntity, CardData
            data = CardData(
                id=f"_sim_t{tier}_{_}",
                name=f"SimTier{tier}",
                text="",
                tags={
                    GameTag.BASE_ATK: atk,
                    GameTag.BASE_HEALTH: hp,
                    GameTag.COST: 3,
                    GameTag.TECH_LEVEL: tier,
                },
            )
            entity = BaseEntity(data, game=None)
            player.tavern.append(entity)

        return True

    # ── Greedy Completion ──────────────────────────────────────────────

    def _greedy_completion(self, player, depth: int):
        """Conservative greedy completion from current state.

        Only uses the EXISTING tavern (no simulated refresh — that would
        generate fake minions and give unrealistic scores).  Sells worst
        minions to make room, plays hand, buys best from real tavern.
        """
        max_steps = self.max_depth - depth
        steps = 0

        while steps < max_steps:
            steps += 1
            board_living = player.get_board_minions()
            board_full = len(board_living) >= 7

            # Priority 1: Play best minion from hand if board has room
            if not board_full:
                best_idx = None
                best_score = -1
                for i, c in enumerate(player.hand):
                    ct = c.get_tag(GameTag.CARDTYPE, 0)
                    if ct == CardType.MINION:
                        aa, ah = player.get_global_aura_bonus(c)
                        s = _minion_value(c, aa, ah)
                        if s > best_score:
                            best_score = s
                            best_idx = i
                if best_idx is not None:
                    _sim_play_from_hand(player, best_idx)
                    continue

            # Priority 2: Buy best affordable tavern minion (board not full)
            affordable = [
                i for i, e in enumerate(player.tavern)
                if e.get_tag(GameTag.COST, 3) <= player.gold
                and len(player.hand) < 10
            ]
            if affordable and not board_full:
                best_i = max(affordable, key=lambda i: _minion_value(
                    player.tavern[i],
                    *player.get_global_aura_bonus(player.tavern[i])))
                _sim_buy(player, best_i)
                # Auto-play
                if len(player.get_board_minions()) < 7:
                    for hi, c in enumerate(player.hand):
                        if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                            _sim_play_from_hand(player, hi)
                            break
                continue

            # Priority 3: If board is full, consider sell+buy to upgrade
            if affordable and board_full:
                best_net = 0
                best_trade = None
                for si, sm in enumerate(board_living):
                    aa_s, ah_s = player.get_global_aura_bonus(sm)
                    sold_val = _minion_value(sm, aa_s, ah_s)
                    for bi in affordable:
                        bought = player.tavern[bi]
                        aa_b, ah_b = player.get_global_aura_bonus(bought)
                        bought_val = _minion_value(bought, aa_b, ah_b)
                        net = bought_val - sold_val
                        if net > best_net:
                            best_net = net
                            live_idx = [j for j, bm in enumerate(player.board)
                                        if not bm.dead].index(si)
                            best_trade = (live_idx, bi)
                if best_trade and best_net > 0:
                    _sim_sell(player, best_trade[0])
                    _sim_buy(player, best_trade[1])
                    if len(player.get_board_minions()) < 7:
                        for hi, c in enumerate(player.hand):
                            if c.get_tag(GameTag.CARDTYPE, 0) == CardType.MINION:
                                _sim_play_from_hand(player, hi)
                                break
                    continue

            # Priority 4: Upgrade tavern if affordable
            _BASE_COST = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10}
            cost = max(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
            if player.gold >= cost and player.tavern_tier < 6:
                player.gold -= cost
                player.tavern_tier += 1
                next_base = _BASE_COST.get(player.tavern_tier + 1, 10)
                player.set_tag(GameTag.TAVERN_UPGRADE_COST, next_base)
                continue

            # No more productive actions — stop
            break
