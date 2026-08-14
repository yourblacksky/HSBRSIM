"""
HSRL Game Engine

Manages the full Battlegrounds game state and turn flow.

Phases:
  Recruit Phase -> Combat Phase -> Recruit Phase -> ...

Combat rules:
  - Player with more minions attacks first; tie -> random
  - Minions attack left-to-right, alternating sides
  - All targets random (with Taunt priority)
  - Damage cap applies until top 4
"""

from __future__ import annotations

import copy
import random
from collections import Counter, namedtuple
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# ── Combat Memory ──────────────────────────────────────────────────────────
# Per-opponent record of last combat encounter. Persists across turns so
# the POMDP value network can use HDT-observable "last known board" info.

CombatRecord = namedtuple("CombatRecord", [
    "board",         # List[Minion] — snapshot of opponent's board
    "turn",          # int — game turn when combat occurred
    "damage_dealt",  # int — damage dealt TO this opponent
    "damage_taken",  # int — damage taken FROM this opponent
    "result",        # float — 1.0=win, 0.0=loss, 0.5=draw
])

from hsrl.core.enums import CardType, GameTag, PlayState, Race, State, Step, Zone
from hsrl.core.entity import CardData
from hsrl.core.exceptions import CombatResolutionTimeout
from hsrl.core.events import *
from hsrl.core.minion import Minion
from hsrl.core.player import Player

from hsrl.core.actions import MAX_HAND_SIZE, GainGold, Action

if TYPE_CHECKING:
    from hsrl.core.actions import Action


class Game:
    """
    Main game controller for a Battlegrounds match.
    """

    DEFAULT_COMBAT_EVENT_BUDGET = 20_000
    DEFAULT_COMBAT_ACTION_BUDGET = 20_000
    DEFAULT_COMBAT_ATTACK_BUDGET = 1_000

    def __init__(self, players: List[Player], card_db=None, seed: int = None,
                 combat_event_budget: int = DEFAULT_COMBAT_EVENT_BUDGET,
                 combat_action_budget: int = DEFAULT_COMBAT_ACTION_BUDGET,
                 combat_attack_budget: int = DEFAULT_COMBAT_ATTACK_BUDGET):
        self.players = players
        self.card_db = card_db
        self.turn: int = 0
        # Per-game random state — set seed for deterministic replay.
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self._seed = seed
        self.step: Step = Step.INVALID
        self.state: State = State.INVALID
        # Combat event log for audit/demo
        self._combat_event_log: List[dict] = []
        self._action_queue: List[Tuple[Action, BaseEntity, Optional[BaseEntity]]] = []
        self._event_listeners: List[Tuple[BaseEntity, EventListener]] = []
        self._next_entity_id = 1
        self._last_attack_target: Optional["Minion"] = None
        self._last_defender: Optional[Player] = None  # Last defender in combat (for tiebreaker)
        self._deferred_actions: List[Tuple[Player, Action]] = []
        self._turn_schedule: dict = {}   # turn → list of callbacks
        self._combat_death_log: List[Minion] = []
        self._combat_summon_log: List[Minion] = []
        self.in_combat: bool = False
        self.combat_event_budget = int(combat_event_budget)
        self.combat_action_budget = int(combat_action_budget)
        self.combat_attack_budget = int(combat_attack_budget)
        self._combat_budget_counts: Optional[Dict[str, int]] = None
        self._combat_budget_items: Dict[str, Counter] = {}
        self._combat_budget_players: Tuple[Optional[int], Optional[int]] = (None, None)
        self.active_player: Optional[Player] = None  # Current active player during recruit
        self.minion_pool = None  # Lazy init via init_pool()
        self.spell_pool = None   # Lazy init via init_pool()
        self.active_anomaly = None  # Optional Anomaly entity (game-wide modifier)
        self.active_tribes: Optional[set] = None  # Set of playable tribes (None = all, unset)
        self._combat_pairs: List[Tuple[Player, Player]] = []  # (player, opponent) per combat
        self._scheduled_combat_pairs: List[Tuple[Player, Optional[Player]]] = []
        self._current_combat_opponents: Dict[Player, Player] = {}
        self._start_of_combat_global_broadcasted: bool = False
        # Recruit decisions are isolated by player.  The compatibility
        # properties below still expose the active player's value to older
        # callers which used the former game-global fields directly.
        self._pending_targeted_queues: Dict[Player, list] = {}
        self._pending_choices: Dict[Player, object] = {}
        self._auto_resolve_choices: bool = True  # Auto-resolve pending choices in heuristic/test mode
        self._combat_draw_streaks: Dict[Tuple[int, int], int] = {}

        # Combat memory: per-player per-opponent last-seen board snapshots.
        # combat_memory[player_id][opponent_id] = CombatRecord
        self.combat_memory: Dict[int, Dict[int, CombatRecord]] = {}

        # Per-player triple tracking: triples_by_tier[player_id] = {tier: count}
        self._triples_by_tier: Dict[int, Dict[int, int]] = {}

        # Per-player tavern upgrade timing: upgrade_turns[player_id] = {tier: turn}
        self._tavern_upgrade_turns: Dict[int, Dict[int, int]] = {}

        for p in self.players:
            p.game = self

    @property
    def _pending_targeted_queue(self) -> list:
        """Compatibility view of the active player's pending target queue."""
        if self.active_player is not None:
            return self._pending_targeted_queues.setdefault(self.active_player, [])
        non_empty = [q for q in self._pending_targeted_queues.values() if q]
        return non_empty[0] if len(non_empty) == 1 else []

    @_pending_targeted_queue.setter
    def _pending_targeted_queue(self, value: list) -> None:
        if self.active_player is None:
            if value:
                raise ValueError("active_player is required for a pending target")
            self._pending_targeted_queues.clear()
            return
        self._pending_targeted_queues[self.active_player] = value

    @property
    def _pending_choice(self):
        """Compatibility view of the active player's pending choice."""
        if self.active_player is not None:
            return self._pending_choices.get(self.active_player)
        values = list(self._pending_choices.values())
        return values[0] if len(values) == 1 else None

    @_pending_choice.setter
    def _pending_choice(self, value) -> None:
        player = getattr(value, "player", None) or self.active_player
        if player is None:
            if value is None:
                self._pending_choices.clear()
                return
            raise ValueError("player is required for a pending choice")
        if value is None:
            self._pending_choices.pop(player, None)
        else:
            self._pending_choices[player] = value

    # ── Deep state snapshot / restore for MCTS search ──────────────────────

    def snapshot_player_state(self, player: Player) -> dict:
        """Deep snapshot of a player's mutable state for safe search restore.

        Snaps the player's board, hand, tavern and all their entities' tags,
        buffs, and script overrides. This allows MCTS to mutate entity state
        during forward simulation and then perfectly restore.

        Returns a dict that can be passed to restore_player_state().
        """
        def _snap_entity(e) -> dict:
            return e.snapshot()  # BaseEntity.snapshot()

        def _snap_list(lst: list) -> list:
            return [(_snap_entity(e), e) for e in lst]

        return {
            "gold": player.gold,
            "health": player.health,
            "armor": player.armor,
            "tavern_tier": player.tavern_tier,
            "board": _snap_list(player.board),
            "hand": _snap_list(player.hand),
            "tavern": _snap_list(player.tavern),
            "tags": {tag: player.get_tag(tag, 0) for tag in (
                GameTag.HERO_POWER_USED,
                GameTag.HERO_POWER_EXTRA_USES,
                GameTag.FREE_REFRESH_REMAINING,
                GameTag.FROZEN,
                GameTag.TAVERN_UPGRADE_COST,
            )},
        }

    def restore_player_state(self, player: Player, saved: dict) -> None:
        """Restore player state from a snapshot taken by snapshot_player_state()."""
        player.gold = saved["gold"]
        player.health = saved["health"]
        player.armor = saved["armor"]
        player.tavern_tier = saved["tavern_tier"]

        def _restore_list(lst: list, snaps: list) -> None:
            lst.clear()
            for snap, entity in snaps:
                entity.restore_snapshot(snap)
                lst.append(entity)

        _restore_list(player.board, saved["board"])
        _restore_list(player.hand, saved["hand"])
        _restore_list(player.tavern, saved["tavern"])

        for tag, val in saved["tags"].items():
            player.set_tag(tag, val)

    def init_pool(self) -> None:
        """Initialize the shared minion and spell pools. Call after card_db is set."""
        from hsrl.core.minion_pool import MinionPool
        from hsrl.core.spell_pool import SpellPool
        self.minion_pool = MinionPool(self.card_db, rng=self.rng)
        self.spell_pool = SpellPool(self.card_db, rng=self.rng)

    def refresh_tavern(self, player: Player, preserve_frozen: bool = False) -> None:
        """Refresh Bob's tavern offerings for a player.

        Args:
            preserve_frozen: If True, minions with FROZEN tag persist and gain
                +2/+1. Only True during automatic turn-start refresh.
                Manual refreshes (hero powers, spells) set this to False.
        """
        if self.minion_pool is None:
            return
        # Consume free refresh if available
        free_remaining = player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        if free_remaining > 0:
            player.set_tag(GameTag.FREE_REFRESH_REMAINING, free_remaining - 1)
        tavern_tier = player.tavern_tier
        # Anomaly: always 7 cards in tavern
        anomaly_always7 = (
            self.active_anomaly is not None
            and not isinstance(self.active_anomaly, bool)
            and getattr(self.active_anomaly, '_tavern_always_7', False)
        )
        # Anomaly: tier filter (only specific tiers)
        anomaly_allowed_tiers = None
        if (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)):
            anomaly_allowed_tiers = getattr(self.active_anomaly, '_allowed_tiers', None)
        # Preserve frozen minions only during auto-refresh
        frozen_minions = []
        if preserve_frozen:
            for m in player.tavern:
                if m.get_tag(GameTag.FROZEN, False):
                    from hsrl.core.actions import BuffEnchantment
                    m.add_buff(BuffEnchantment(atk=2, health=1))
                    m.set_tag(GameTag.HEALTH, m.max_health)
                    frozen_minions.append(m)
        # Offer counts include frozen minions (subtract from new draws)
        offer_counts = {1: 3, 2: 4, 3: 4, 4: 5, 5: 5, 6: 6}
        base_count = offer_counts.get(tavern_tier, 6)
        count = max(0, 7 if anomaly_always7 else base_count - len(frozen_minions))
        if anomaly_always7:
            count = max(0, 7 - len(frozen_minions))

        # Guiding Candle: first N refreshes only contain Tier 6 minions
        guiding = player.get_tag(GameTag.GUIDING_CANDLE_REFRESHES, 0)
        if guiding > 0:
            player.set_tag(GameTag.GUIDING_CANDLE_REFRESHES, guiding - 1)
            drawn = self.minion_pool.draw(6, count=count, race_filter=self.active_tribes)
        elif anomaly_allowed_tiers:
            # Anomaly tier filter: draw minions only from allowed tiers.
            # Pool is pre-pruned at game start (tiers + tribes), so we can
            # draw exactly `count` minions without needing oversampling.
            allowed = set(anomaly_allowed_tiers)
            max_tier = min(max(allowed), player.tavern_tier)
            drawn = self.minion_pool.draw(max_tier, count=count, race_filter=self.active_tribes)
        elif hasattr(player, '_tavern_min_tier') and player._tavern_min_tier > 1:
            # Player-level tier filter (e.g. Bob-blehead trinket: no tier 1-2)
            min_t = player._tavern_min_tier
            drawn = self.minion_pool.draw(tavern_tier, count=count, min_tier=min_t, race_filter=self.active_tribes)
        elif (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)
                and getattr(self.active_anomaly, '_only_current_tier', False)):
            drawn = self.minion_pool.draw(player.tavern_tier, count=count,
                                          min_tier=player.tavern_tier,
                                          race_filter=self.active_tribes)
        else:
            drawn = self.minion_pool.draw(tavern_tier, count=count, race_filter=self.active_tribes)
        player.tavern.clear()
        # Add frozen minions first (they persist across auto-refresh only)
        for m in frozen_minions:
            m.zone = Zone.TAVERN
            player.tavern.append(m)
        # Draw new minions
        for card_id in drawn:
            minion = self.create_minion(card_id)
            minion.controller = player
            minion.zone = Zone.TAVERN
            # Apply persistent tavern buffs (e.g. Felemental, Dune Dweller)
            for tb in player.tavern_buffs:
                if tb.matches(minion):
                    from hsrl.core.actions import BuffEnchantment
                    minion.add_buff(BuffEnchantment(atk=tb.atk, health=tb.health))
                    minion.set_tag(GameTag.HEALTH, minion.max_health)
            player.tavern.append(minion)
        # Add 1 tavern spell (fixed: every refresh provides 1 spell)
        if self.spell_pool is not None:
            spells_drawn = self.spell_pool.draw(tavern_tier, count=1)
            for card_id in spells_drawn:
                spell = self.create_spell(card_id)
                spell.controller = player
                spell.zone = Zone.TAVERN
                player.tavern.append(spell)
        # Broadcast TAVERN_REFRESH for "After the Tavern is Refreshed" cards
        self.broadcast(TAVERN_REFRESH, player)
        # Dispatch counter-based trinket triggers
        self._dispatch_trinket_event(player, "on_tavern_refresh")

    def buy_minion(self, player: Player, minion: "Minion") -> None:
        """Buy a minion from the tavern and add it to hand."""
        from hsrl.core.actions import SpendGold
        if minion not in player.tavern:
            return
        # Hand must have room before spending gold (standard BG rule)
        if len(player.hand) >= MAX_HAND_SIZE:
            return
        cost = minion.get_tag(GameTag.COST, 3)
        # Anomaly: minions cost equals their tier (No Tier 1, cost = tier)
        anomaly = self.active_anomaly
        if anomaly is not None and not isinstance(anomaly, bool):
            if getattr(anomaly, '_cost_equals_tier', False):
                cost = minion.data.tech_level
            if getattr(anomaly, '_minions_cost_2', False):
                cost = 2
            if getattr(anomaly, '_minions_cost_1', False):
                cost = 1
        # Electrode Attractor: magnetic mechs cost (2)
        if minion.has_tag(GameTag.MAGNETIC) and player.get_tag(GameTag.MAGNETIC_COST_OVERRIDE, 0) > 0:
            cost = player.get_tag(GameTag.MAGNETIC_COST_OVERRIDE)
        # Health cost: Pilgrimp Sticker (player aura) or Leeching Felhound (self)
        health_cost_demon = (
            minion.has_tag(GameTag.HEALTH_COST_DEMON)
            or (player.get_tag(GameTag.HEALTH_COST_DEMON, 0) > 0
                and minion.has_tag(GameTag.RACE) and minion.race == Race.DEMON)
        )
        if health_cost_demon and player.health > cost:
            from hsrl.core.actions import DealDamageToHero
            self.queue_action(DealDamageToHero(player, cost))
            player.set_tag(GameTag.HEALTH_COST_DEMON, 0)
        else:
            if player.gold < cost:
                return
            self.queue_action(SpendGold(player, cost))
        # Track gold spent this turn (for "Improves by gold spent" cards)
        current = player.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0)
        player.set_tag(GameTag.GOLD_SPENT_THIS_TURN, current + cost)
        player.tavern.remove(minion)
        minion.zone = Zone.HAND
        player.hand.append(minion)
        # Minion is already removed from pool during refresh_tavern
        # Check for triple after adding to hand
        self._check_for_triple(player, minion)
        self.resolve_queue()
        self.broadcast("MINION_BOUGHT", minion, player)
        # Trigger trinket on_buy scripts
        for trinket in player.trinkets:
            on_buy = trinket.on_buy
            if on_buy:
                if isinstance(on_buy, (list, tuple)):
                    for action in on_buy:
                        self.queue_action(action, source=trinket)
                else:
                    self.queue_action(on_buy, source=trinket)
        # Dispatch counter-based trinket triggers
        self._dispatch_trinket_event(player, "on_minion_bought")
        self._increment_quest_progress(player)
        # Anomaly: auto-refresh tavern after each purchase
        anomaly = self.active_anomaly
        if anomaly is not None and not isinstance(anomaly, bool):
            if getattr(anomaly, '_auto_refresh_after_buy', False):
                self.refresh_tavern(player)

    def buy_spell(self, player: Player, spell) -> None:
        """Buy a spell from the tavern and add it to hand."""
        from hsrl.core.actions import SpendGold
        if spell not in player.tavern:
            return
        # Hand must have room before spending gold
        if len(player.hand) >= MAX_HAND_SIZE:
            return
        cost = spell.get_tag(GameTag.COST, 0)
        # Apply NEXT_SPELL_COST_REDUCTION discount
        discount = player.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)
        actual_cost = max(0, cost - discount)
        # Bazaar Sticker: one spell per turn buyable with health
        health_cost_spell = player.get_tag(GameTag.HEALTH_COST_SPELL, 0) > 0
        if health_cost_spell and player.health > actual_cost:
            from hsrl.core.actions import DealDamageToHero
            self.queue_action(DealDamageToHero(player, actual_cost))
            player.set_tag(GameTag.HEALTH_COST_SPELL, 0)
        else:
            if player.gold < actual_cost:
                return
            self.queue_action(SpendGold(player, actual_cost))
        # Track gold spent this turn
        current = player.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0)
        player.set_tag(GameTag.GOLD_SPENT_THIS_TURN, current + actual_cost)
        # Consume discount
        if discount > 0:
            player.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)
        player.tavern.remove(spell)
        spell.zone = Zone.HAND
        player.hand.append(spell)
        self.resolve_queue()

    def play_spell(self, player: Player, spell) -> None:
        """Cast a tavern spell from hand: broadcast TAVERN_SPELL_CAST, return to pool.

        If the spell has an on_play effect (e.g. Spellcraft spells), it is triggered
        before the TAVERN_SPELL_CAST broadcast.
        """
        from hsrl.core.actions import CastTavernSpell
        if spell not in player.hand:
            return
        # Trigger on_play effect for Spellcraft and other cast-triggered spells
        on_play_action = spell.on_play
        if on_play_action:
            if isinstance(on_play_action, (list, tuple)):
                for a in on_play_action:
                    self.queue_action(a, source=spell)
            else:
                self.queue_action(on_play_action, source=spell)
        # Broadcast for Spellcraft-specific events
        if spell.has_tag(GameTag.SPELLCRAFT_SPELL):
            self.broadcast("SPELLCRAFT_CAST", spell, player)
        # Trigger trinket on_play effects (whenever you play a card)
        self._dispatch_trinket_event(player, "on_play", played_card=spell)
        # Track last spell card id for "replay last spell" effects
        player.set_tag(GameTag.LAST_SPELL_CARD_ID, spell.get_tag(GameTag.CARD_ID))
        self.queue_action(CastTavernSpell(player), source=spell)
        player.hand.remove(spell)
        spell.zone = Zone.REMOVED
        # Return to shared spell pool
        card_id = spell.get_tag(GameTag.CARD_ID)
        if self.spell_pool and self.spell_pool.is_pool_spell(card_id):
            self.spell_pool.return_card(card_id)
        self._increment_quest_progress(player)
        self.resolve_queue()

    def use_hero_power(self, player: Player) -> None:
        """Use the player's hero power. Handles cost deduction, usage flag, and script execution."""
        from hsrl.core.actions import UseHeroPower
        self.queue_action(UseHeroPower(player), source=player)
        self.resolve_queue()

    def sell_minion(self, player: Player, minion: Minion) -> None:
        """Sell a minion: return gold, trigger on-sell effects, return to pool."""
        from hsrl.core.actions import GainGold
        # Trigger on-sell effect if minion has one
        sell_action = minion.on_sell
        if sell_action:
            if isinstance(sell_action, (list, tuple)):
                for action in sell_action:
                    self.queue_action(action, source=minion)
            else:
                self.queue_action(sell_action, source=minion)
        # Return 1 Gold (or 0 if anomaly overrides)
        sell_price = 0 if (self.active_anomaly is not None
                           and not isinstance(self.active_anomaly, bool)
                           and getattr(self.active_anomaly, '_sell_price_0', False)) else 1
        if sell_price > 0:
            self.queue_action(GainGold(player, sell_price))
        # Broadcast MINION_SOLD event
        self.broadcast("MINION_SOLD", minion, player)
        # Dispatch counter-based trinket triggers
        self._dispatch_trinket_event(player, "on_minion_sold")
        self._increment_quest_progress(player)
        # Return to shared pool
        if minion.controller and hasattr(minion, 'is_golden'):
            if self.minion_pool:
                card_id = minion.get_tag(GameTag.CARD_ID)
                if self.minion_pool.is_pool_minion(card_id):
                    copies = 3 if minion.is_golden else 1
                    self.minion_pool.return_card(card_id, copies)
        # Remove from board
        self.remove_from_board(minion)
        player.graveyard.append(minion)
        self.resolve_queue()

    # ── Entity lifecycle ──

    def create_minion(self, card_id: str) -> Minion:
        """Create a new minion from the card database.
        Auto-registers missing cards from bg_cards.json if needed.
        Returns None if card_id cannot be found anywhere.
        """
        if self.card_db is None:
            raise RuntimeError("No card database set")
        try:
            minion = self.card_db.create_minion(card_id, game=self)
        except KeyError:
            # Auto-register missing token from bg_cards.json
            self._auto_register_card(card_id)
            try:
                minion = self.card_db.create_minion(card_id, game=self)
            except KeyError:
                return None  # Card not found anywhere
        minion.entity_id = self._next_entity_id
        self._next_entity_id += 1
        self.broadcast(ENTITY_CREATED, minion)
        # Auto-golden if ALL_MINIONS_GOLDEN anomaly is active
        if (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)
                and self.active_anomaly.has_tag(GameTag.ALL_MINIONS_GOLDEN)):
            minion.set_tag(GameTag.GOLDEN, True)
            minion.atk = minion.atk * 2
            minion.health = minion.health * 2
        return minion

    def _auto_register_card(self, card_id: str) -> None:
        """Auto-register a missing card from bg_cards.json data."""
        import json, os
        data_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'bg_cards.json')
        try:
            with open(data_path) as f:
                cards = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        for c in cards:
            if c.get('id') == card_id:
                from hsrl.core.card_db import register_card
                name = c.get('name', card_id)
                ct = c.get('card_type', 4)
                from hsrl.core.enums import CardType
                cardtype = CardType(ct) if ct in [1,4,5,42] else CardType.MINION
                from hsrl.core.enums import DBF_RACE_TO_ENUM
                race_val = c.get('card_race')
                race = DBF_RACE_TO_ENUM.get(race_val, Race.NONE)
                register_card(
                    card_id=card_id, name=name, text='',
                    cardtype=cardtype, race=race, tech_level=c.get('tech_level', 1) or 1,
                    tags={
                        GameTag.BASE_ATK: c.get('atk') or 1,
                        GameTag.BASE_HEALTH: c.get('health') or 1,
                    },
                )
                return

    def create_spell(self, card_id: str):
        """Create a new spell from the card database.
        Auto-registers missing cards from bg_cards.json if needed.
        """
        if self.card_db is None:
            raise RuntimeError("No card database set")
        try:
            spell = self.card_db.create_spell(card_id, game=self)
        except KeyError:
            self._auto_register_card(card_id)
            try:
                spell = self.card_db.create_spell(card_id, game=self)
            except KeyError:
                # Fallback: create as minion (spell token)
                try:
                    return self.create_minion(card_id)
                except (KeyError, RuntimeError):
                    return None
        spell.entity_id = self._next_entity_id
        self._next_entity_id += 1
        self.broadcast(ENTITY_CREATED, spell)
        return spell

    def create_player(self, card_id: str) -> Player:
        """Create a player (hero) from the card database."""
        if self.card_db is None:
            raise RuntimeError("No card database set")
        data = self.card_db.get(card_id)
        if data is None:
            raise KeyError(f"Unknown hero card id: {card_id}")
        player = Player(data, game=self)
        player.entity_id = self._next_entity_id
        self._next_entity_id += 1
        self.broadcast(ENTITY_CREATED, player)
        return player

    # ── Action queue ──

    def queue_action(self, action: Action, source: Optional[BaseEntity] = None, target: Optional[BaseEntity] = None) -> None:
        """Queue an action for resolution."""
        if source is None:
            source = self.players[0] if self.players else None
        self._action_queue.append((action, source, target))

    def _start_combat_budget(self, player_a: Player,
                             player_b: Optional[Player]) -> None:
        self._combat_budget_counts = {"events": 0, "actions": 0, "attacks": 0}
        self._combat_budget_items = {
            "events": Counter(), "actions": Counter(), "attacks": Counter(),
        }
        self._combat_budget_players = (
            getattr(player_a, "entity_id", None),
            getattr(player_b, "entity_id", None),
        )

    def _consume_combat_budget(self, budget: str, amount: int = 1,
                               item: str = "") -> None:
        if not self.in_combat or self._combat_budget_counts is None:
            return
        limits = {
            "events": self.combat_event_budget,
            "actions": self.combat_action_budget,
            "attacks": self.combat_attack_budget,
        }
        self._combat_budget_counts[budget] += amount
        if item:
            self._combat_budget_items[budget][str(item)] += amount
        observed = self._combat_budget_counts[budget]
        limit = limits[budget]
        if limit >= 0 and observed > limit:
            raise CombatResolutionTimeout(
                budget=budget,
                limit=limit,
                observed=observed,
                turn=self.turn,
                player_ids=self._combat_budget_players,
                details={"top_items": self._combat_budget_items[budget].most_common(8)},
            )

    def schedule_turn_action(self, turn: int, callback) -> None:
        """Schedule a callback to fire at the start of turn N.
        callback receives (game, turn) and can queue actions.
        """
        if turn not in self._turn_schedule:
            self._turn_schedule[turn] = []
        self._turn_schedule[turn].append(callback)

    def process_deferred_actions(self) -> None:
        """Execute all deferred actions and turn-scheduled callbacks."""
        # Turn-scheduled callbacks
        callbacks = self._turn_schedule.pop(self.turn, [])
        for cb in callbacks:
            cb(self, self.turn)
        # Deferred actions
        for player, action in self._deferred_actions:
            self.queue_action(action, source=player)
        self._deferred_actions.clear()
        self.resolve_queue()

    # ── Event broadcasting ──

    @staticmethod
    def _entity_owner(entity) -> Optional[Player]:
        if isinstance(entity, Player):
            return entity
        controller = getattr(entity, "controller", None)
        return controller if isinstance(controller, Player) else None

    def _event_owner(self, args) -> Optional[Player]:
        for arg in args:
            owner = self._entity_owner(arg)
            if owner is not None:
                return owner
        return None

    def _listener_in_scope(self, entity, listener, event_name, event_owner,
                           include_global: bool) -> bool:
        listener_owner = self._entity_owner(entity)
        if listener_owner is None:
            # Ownerless sources do not silently become global. The active
            # anomaly slot is an explicit game-wide declaration; every other
            # source must opt in with EventScope.GLOBAL.
            return include_global and (
                listener.scope == EventScope.GLOBAL
                or entity is self.active_anomaly
            )
        if listener.scope == EventScope.GLOBAL:
            return include_global
        if listener.scope == EventScope.OWNER:
            return event_owner is listener_owner
        if listener.scope == EventScope.COMBAT_PAIR:
            return (event_owner is listener_owner
                    or self._current_combat_opponents.get(event_owner) is listener_owner)

        # AUTO is deliberately conservative: Start of Combat and recruit
        # events are owner-local; other events during a resolved combat are
        # visible only to the two participants. Events with no identifiable
        # owner retain their historical game-wide lifecycle semantics.
        if event_name == START_OF_COMBAT:
            return event_owner is listener_owner
        if self.in_combat and self._current_combat_opponents:
            return (event_owner is listener_owner
                    or self._current_combat_opponents.get(event_owner) is listener_owner)
        if event_owner is not None:
            return event_owner is listener_owner
        return True

    def broadcast(self, event_name: str, *args, event_player=None,
                  include_global: bool = True) -> None:
        """Broadcast an event to all registered listeners.

        Owner-local events are inferred from their entity/player arguments.
        During combat, listeners are additionally constrained to the active
        pair. ``event_player`` makes lifecycle ownership explicit without
        changing the arguments delivered to legacy listener conditions.

        The first positional arg (if any BaseEntity) is passed as target to the action trigger.
        """
        self._consume_combat_budget("events", item=event_name)
        event_owner = event_player or self._event_owner(args)
        to_remove = []
        for entity, listener in self._event_listeners:
            if (self._listener_in_scope(entity, listener, event_name, event_owner,
                                        include_global)
                    and listener.check(event_name, args)):
                # Pass the first arg as target — convention is first arg is the relevant entity
                target = args[0] if args else None
                listener.action.trigger(entity, self, target)
                if listener.once:
                    to_remove.append((entity, listener))
        for item in to_remove:
            if item in self._event_listeners:
                self._event_listeners.remove(item)

    def register_listener(self, entity: BaseEntity, listener: "EventListener") -> None:
        self._event_listeners.append((entity, listener))

    def unregister_listener(self, entity: BaseEntity, listener: "EventListener") -> None:
        if (entity, listener) in self._event_listeners:
            self._event_listeners.remove((entity, listener))

    def unregister_all_listeners_for_entity(self, entity: BaseEntity) -> None:
        """Remove all event listeners registered by an entity."""
        self._event_listeners = [
            (e, l) for (e, l) in self._event_listeners if e is not entity
        ]

    # ── Board helpers ──

    def get_board(self, player: Player) -> List[Minion]:
        return player.board

    def get_living_enemies(self, player: Player) -> List[Minion]:
        """Return living minions belonging to the active combat opponent."""
        opponent = self.get_current_combat_opponent(player)
        if opponent is None:
            return []
        return [m for m in opponent.get_board_minions() if not m.dead]

    def get_opponent(self, player: Player) -> Optional[Player]:
        """Get the bound current combat opponent, if one exists."""
        return self.get_current_combat_opponent(player)

    def get_current_combat_opponent(self, player: Player) -> Optional[Player]:
        """Return the opponent for the combat pair currently being resolved."""
        return self._current_combat_opponents.get(player)

    def rearrange_board(self, player: Player, order: list[int]) -> bool:
        """Apply an exact permutation of the living recruit-phase board."""
        living = player.get_board_minions()
        if len(living) < 2 or sorted(order) != list(range(len(living))):
            return False
        player.board = [living[index] for index in order]
        self._update_zone_positions(player.board)
        return True

    # ── Summoning ──

    def summon(self, player: Player, minion: Minion, position: Optional[int] = None) -> None:
        """Put a minion onto a player's board."""
        if len(player.board) >= 7:
            # Board is full; minion is not summoned (standard BG rule)
            self.broadcast(MINION_OVERFLOW, minion, player)
            return
        minion.controller = player
        minion.zone = Zone.PLAY
        if position is None or position > len(player.board):
            position = len(player.board)
        player.board.insert(position, minion)
        self._update_zone_positions(player.board)
        # Broadcast ELEMENTAL_PLAYED for "Improves after playing an Elemental" cards
        if minion.race == Race.ELEMENTAL:
            self.broadcast(ELEMENTAL_PLAYED, minion, player)
        self.broadcast(SUMMON, minion, player)
        # Trinket: summon in combat
        if self.step == Step.COMBAT:
            self._combat_summon_log.append(minion)
            self._dispatch_trinket_event(player, "on_summon_in_combat",
                                          summoned=minion)
        # Broadcast MINION_PLAYED for "after you play a card" effects
        # (One-Amalgam Tour Group, Primitive Painter, etc.)
        self.broadcast(MINION_PLAYED, minion, player)
        # Trigger on_summon script AFTER broadcasts so "After you play X"
        # listeners don't catch the minion's own play event.
        on_summon_action = minion.on_summon
        if on_summon_action:
            self.queue_action(on_summon_action, source=minion)
    def play_minion(self, player: Player, minion: Minion,
                    position: Optional[int] = None,
                    magnetic_target: Optional[Minion] = None) -> None:
        """Play a minion from hand to the board during recruit phase.

        Triggers battlecry, checks for triple reward (if golden),
        then checks for triple combination.

        If magnetic_target is provided and minion has MAGNETIC, attach
        the magnetic minion to the target Mech instead of summoning it.
        """
        if minion not in player.hand:
            return

        # Magnetic attachment path
        if magnetic_target is not None and minion.magnetic:
            # Validate target: same controller, alive on board, valid race
            target_race = magnetic_target.race
            if magnetic_target.controller != player:
                return
            if magnetic_target.dead or magnetic_target.zone != Zone.PLAY:
                return
            card_id = minion.get_tag(GameTag.CARD_ID)
            if card_id == "BG31_859":
                # Technical Element: can magnetize to Mechs and Elementals
                if target_race not in (Race.MECH, Race.ELEMENTAL):
                    return
            elif target_race != Race.MECH:
                return
            player.hand.remove(minion)
            from hsrl.core.actions import AttachMagnetic
            self.queue_action(AttachMagnetic(minion, magnetic_target))
            self.resolve_queue()
            return

        if len(player.board) >= 7:
            self.broadcast(MINION_OVERFLOW, minion, player)
            return

        # Remove from hand
        player.hand.remove(minion)

        # Increment cards played this turn counter
        current = player.get_tag(GameTag.CARDS_PLAYED_THIS_TURN, 0)
        player.set_tag(GameTag.CARDS_PLAYED_THIS_TURN, current + 1)

        # Summon to board
        self.summon(player, minion, position=position)

        # Auto-golden check (Gold-plated Compass trinket)
        next_golden = player.get_tag(GameTag.NEXT_PURCHASE_GOLDEN, 0)
        if next_golden > 0 and not minion.is_golden:
            player.set_tag(GameTag.NEXT_PURCHASE_GOLDEN, next_golden - 1)
            minion.set_tag(GameTag.GOLDEN, True)

        # Trigger battlecry
        bc = minion.battlecry
        if bc:
            times = 2 if player.get_tag(GameTag.BATTLECRY_DOUBLED) else 1
            for _ in range(times):
                if isinstance(bc, (list, tuple)):
                    for action in bc:
                        self.queue_action(action, source=minion)
                else:
                    self.queue_action(bc, source=minion)
            self.broadcast(BATTLECRY_TRIGGER, minion, player)
        self.resolve_queue()

        # Trigger trinket on_play effects (whenever you play a card)
        self._dispatch_trinket_event(player, "on_play", played_card=minion)

        # Check for triple reward (if golden)
        if minion.is_golden:
            self._grant_triple_reward(player, minion)

        # Check for triple formation
        self._check_for_triple(player, minion)

    def _check_for_triple(self, player: Player, entity) -> None:
        """After a minion enters hand or board, check if a triple is formed.

        Counts non-golden copies of the same card_id across hand and board.
        When 3 are found, triggers _combine_triple.

        Special case: Elemental of Surprise (BG26_175) can triple with any
        Elemental as a substitute for one copy.
        """
        card_id = entity.get_tag(GameTag.CARD_ID)
        if not card_id:
            return
        if entity.is_golden:
            return
        # Only pool minions can triple; Blood Gems, spells, and tokens cannot.
        if entity.get_tag(GameTag.CARDTYPE) != CardType.MINION:
            return

        copies = []
        for m in player.hand + player.board:
            if m.uuid == entity.uuid:
                continue
            if m.is_golden:
                continue
            if m.get_tag(GameTag.CARD_ID) == card_id:
                copies.append(m)

        need_copies = 1 if (player.get_tag(GameTag.PIRATES_NEED_2_COPIES) and
                            entity.race == Race.PIRATE) else 2

        if len(copies) >= need_copies:
            self._combine_triple(player, [entity] + copies[:need_copies])
            return

        # Elemental of Surprise: can triple with any Elemental as substitute
        if card_id == "BG26_175" and len(copies) == 1:
            # Have 2x Elemental of Surprise, need 1 more Elemental
            for m in player.hand + player.board:
                if m.uuid == entity.uuid or m in copies:
                    continue
                if m.is_golden:
                    continue
                if m.race == Race.ELEMENTAL and m.get_tag(GameTag.CARDTYPE) == CardType.MINION:
                    copies.append(m)
                    break
            if len(copies) >= 2:
                self._combine_triple(player, [entity] + copies[:2])

        elif card_id != "BG26_175" and entity.race == Race.ELEMENTAL and len(copies) == 1:
            # Have 2x of this Elemental, check for Elemental of Surprise as 3rd
            for m in player.hand + player.board:
                if m.uuid == entity.uuid or m in copies:
                    continue
                if m.is_golden:
                    continue
                if m.get_tag(GameTag.CARD_ID) == "BG26_175":
                    copies.append(m)
                    break
            if len(copies) >= 2:
                self._combine_triple(player, [entity] + copies[:2])

    def _combine_triple(self, player: Player,
                        copies: List["Minion"]) -> None:
        """Combine 3 identical non-golden minions into one golden version.

        1. Remove all 3 copies from their zones → Zone.SETASIDE
        2. Create golden version with doubled base stats
        3. Merge all buffs from the 3 source copies
        4. Set TRIPLE_REWARD_TIER = min(tier+1, 6)
        5. Add golden to hand
        """
        if len(copies) != 3:
            return

        card_id = copies[0].get_tag(GameTag.CARD_ID)
        tier = copies[0].tech_level

        # 1. Remove all 3 copies from their zones
        for m in copies:
            if m in player.hand:
                player.hand.remove(m)
            elif m in player.board:
                self.remove_from_board(m)
                if m in player.graveyard:
                    player.graveyard.remove(m)
            m.zone = Zone.SETASIDE
            m.set_tag(GameTag.ZONE_POSITION, 0)

        # 2. Create golden version from card database
        golden = self.create_minion(card_id)
        golden.controller = player

        golden.set_tag(GameTag.GOLDEN, True)
        base_atk = golden.get_tag(GameTag.BASE_ATK, 0)
        base_health = golden.get_tag(GameTag.BASE_HEALTH, 0)
        golden.set_tag(GameTag.BASE_ATK, base_atk * 2)
        golden.set_tag(GameTag.BASE_HEALTH, base_health * 2)
        golden.set_tag(GameTag.HEALTH, golden.max_health)

        # 3. Merge all buffs from the 3 source copies
        for m in copies:
            for buff in m._buffs:
                golden.add_buff(buff)

        # 4. Set triple reward tier
        reward_tier = min(tier + 1, 6)
        golden.set_tag(GameTag.TRIPLE_REWARD_TIER, reward_tier)

        # 5. Add golden to hand
        golden.zone = Zone.HAND
        player.hand.append(golden)

        self.broadcast(TRIPLE_COMBINED, player, golden, copies)
        # Track triple for POMDP features
        self.track_triple(player, tier)

    def _grant_triple_reward(self, player: Player, golden) -> None:
        """Grant a Triple Reward Discover when a golden minion is played.

        Normally discovers a minion from the reward tier (tier+1 of original).
        If TRIPLE_REWARD_IS_PRIZE is set (Corrupted Tome), discovers a Prize instead.
        """
        reward_tier = golden.get_tag(GameTag.TRIPLE_REWARD_TIER,
                                     golden.tech_level + 1)
        golden.set_tag(GameTag.TRIPLE_REWARD_TIER, 0)

        if player.get_tag(GameTag.TRIPLE_REWARD_IS_PRIZE, False):
            from hsrl.core.actions import DiscoverPrize
            reward = DiscoverPrize(player)
        else:
            from hsrl.core.actions import DiscoverMinion
            reward = DiscoverMinion(player, max_tier=reward_tier)

        self.queue_action(reward)
        self.resolve_queue()

        self.broadcast(TRIPLE_REWARD_DISCOVERED, player, golden, reward_tier)

    def remove_from_board(self, minion: Minion) -> None:
        """Remove a minion from its controller's board."""
        player = minion.controller
        if player and minion in player.board:
            player.board.remove(minion)
            self._update_zone_positions(player.board)
        minion.zone = Zone.GRAVEYARD
        self.unregister_all_listeners_for_entity(minion)

    def _update_zone_positions(self, board: List[Minion]) -> None:
        for i, m in enumerate(board):
            m.set_tag(GameTag.ZONE_POSITION, i)

    # ── Death processing ──

    _MAX_DEATH_WAVES = 20  # prevent infinite recursion
    _MAX_ACTIONS_PER_RESOLVE = 5000  # prevent infinite action loops

    def _check_deaths(self, _wave: int = 0, _total_actions: int = 0) -> None:
        """Check for deaths after each action. Process deathrattles."""
        if _wave > self._MAX_DEATH_WAVES:
            return
        if _total_actions >= self._MAX_ACTIONS_PER_RESOLVE:
            return
        dead_minions: List[Minion] = []
        players_to_scan = self.players
        if self.in_combat and self._current_combat_opponents:
            players_to_scan = list(self._current_combat_opponents)
        for p in players_to_scan:
            for m in p.board:
                if m.dead and m.zone == Zone.PLAY:
                    dead_minions.append(m)

        if not dead_minions:
            return

        # Process deaths
        for m in dead_minions:
            self.broadcast(BEFORE_DESTROY, m)
            self.broadcast(DEATH, m)

            # Log death for combat tracking (Kangor's Apprentice etc.)
            self._combat_death_log.append(m)

            # Trigger Reborn (spec §6: Reborn BEFORE Deathrattle)
            if m.reborn and not m.has_tag(GameTag.REBORN_USED):
                from hsrl.core.actions import Reborn
                self.queue_action(Reborn(m), source=m)

            # Trigger deathrattle (spec §6: after Reborn)
            dr = m.deathrattle
            if dr:
                self.broadcast(DEATHRATTLE_TRIGGER, m)
                # Increment per-player deathrattle counter (Falling Sky Golem, etc.)
                if m.controller:
                    total = m.controller.get_tag(GameTag.DEATHRATTLE_TRIGGERED, 0)
                    m.controller.set_tag(GameTag.DEATHRATTLE_TRIGGERED, total + 1)
                if isinstance(dr, (list, tuple)):
                    for action in dr:
                        self.queue_action(action, source=m)
                else:
                    self.queue_action(dr, source=m)

            # Increment Avenge counters for friendly minions
            from hsrl.core.actions import AvengeIncrement
            if m.controller:
                self.queue_action(AvengeIncrement(m.controller), source=m)
                # Dispatch trinket on_friendly_death_combat
                self._dispatch_trinket_event(m.controller, "on_friendly_death_combat",
                                              dead_minion=m)

            self.remove_from_board(m)
            if m.controller:
                m.controller.graveyard.append(m)

        self._resolve_queue(_wave + 1, _total_actions)

    def _resolve_queue(self, _wave: int = 0, _total_actions: int = 0) -> None:
        """Process queued actions. _wave tracks death processing depth.

        Stops mid-queue if a TargetedAction pauses awaiting target selection.
        """
        while self._action_queue:
            if _total_actions >= self._MAX_ACTIONS_PER_RESOLVE:
                return
            action, source, target = self._action_queue.pop(0)
            self._consume_combat_budget("actions", item=type(action).__name__)
            action.trigger(source, self, target)
            _total_actions += 1
            # TargetedAction may pause the queue (recruit-phase target selection)
            if self.has_pending_target(self.active_player):
                return
            self._check_deaths(_wave, _total_actions)

    def resolve_queue(self) -> None:
        """Public entry point — process all queued actions.
        Auto-resolves pending discover choices unless disabled by RL env.

        Pending targeted actions are deliberate decision points. Never clear
        them here: doing so silently discards the battlecry/spell effect before
        an RL policy can choose its target.
        """
        self._resolve_queue(0)
        choice = self.get_pending_choice(self.active_player)
        if self._auto_resolve_choices and choice is not None:
            self.resolve_pending_choice(self.rng.randrange(len(choice.options)), self.active_player)

    def set_pending_choice(self, player: Player, choice) -> None:
        self._pending_choices[player] = choice

    def get_pending_choice(self, player: Optional[Player] = None):
        player = player or self.active_player
        if player is not None:
            return self._pending_choices.get(player)
        values = list(self._pending_choices.values())
        return values[0] if len(values) == 1 else None

    def has_pending_choice(self, player: Optional[Player] = None) -> bool:
        return self.get_pending_choice(player) is not None

    def enqueue_pending_target(self, player: Player, action) -> None:
        self._pending_targeted_queues.setdefault(player, []).append(action)

    def _pending_targets(self, player: Optional[Player] = None) -> list:
        player = player or self.active_player
        if player is not None:
            return self._pending_targeted_queues.setdefault(player, [])
        non_empty = [q for q in self._pending_targeted_queues.values() if q]
        return non_empty[0] if len(non_empty) == 1 else []

    def has_pending_target(self, player: Optional[Player] = None) -> bool:
        """Check if a TargetedAction is awaiting target selection."""
        return bool(self._pending_targets(player))

    def get_pending_target_domain(self, player: Optional[Player] = None) -> str:
        """Return the target domain ('board' or 'tavern') for the pending action."""
        queue = self._pending_targets(player)
        if not queue:
            return "board"
        return getattr(queue[0], 'target_domain', 'board')

    def get_pending_target_candidates(self, player: Optional[Player] = None) -> list:
        """Return the list of valid target entities for the pending targeted action."""
        queue = self._pending_targets(player)
        if not queue:
            return []
        return queue[0].candidates

    def resolve_pending_target(self, target_index: int, player: Optional[Player] = None) -> bool:
        """Select a target for the front-of-queue TargetedAction.
        Returns True if more targets remain (sequential multi-target support).

        target_index: index into the candidates list (0-based).
        """
        queue = self._pending_targets(player)
        if not queue:
            return False
        action = queue.pop(0)
        candidates = action.candidates
        if 0 <= target_index < len(candidates):
            action.target = candidates[target_index]
        elif candidates:
            import random
            action.target = self.rng.choice(candidates)
        else:
            return bool(queue)
        # Re-queue the TargetedAction — it will now execute with target set
        self.queue_action(action)
        self.resolve_queue()
        return bool(queue)

    def auto_resolve_pending_target(self, player: Optional[Player] = None) -> None:
        """Auto-resolve the pending TargetedAction with a random valid target.

        Used by heuristic auto-play which has no target preference.
        If there are no valid targets, the pending action is discarded.
        Works for sequential multi-target: drains the entire queue.
        """
        queue = self._pending_targets(player)
        if not queue:
            return
        action = queue.pop(0)
        candidates = action.candidates
        if candidates:
            action.target = self.rng.choice(candidates)
            self.queue_action(action)
            self.resolve_queue()
        while queue:
            a = queue.pop(0)
            c = a.candidates
            if c:
                a.target = self.rng.choice(c)
                self.queue_action(a)
                self.resolve_queue()

    def start_game(self) -> None:
        self.state = State.RUNNING
        self.turn = 1
        # Trigger hero on_summon scripts (for passive hero powers that register listeners)
        for p in self.players:
            if p.data.scripts:
                fn = getattr(p.data.scripts, "on_summon", None)
                if fn and callable(fn):
                    fn(p, self)
        # Apply anomaly before starting recruit phase
        self._apply_anomaly()
        # Select active tribes (5 of 10, unless anomaly overrides)
        self._select_active_tribes()
        # Assign buddies if buddy anomaly is active
        anomaly = self.active_anomaly
        buddies_enabled = (
            anomaly is not None and not isinstance(anomaly, bool) and
            (anomaly.has_tag(GameTag.BUDDIES_ENABLED) or
             any(hasattr(anomaly, a) and getattr(anomaly, a)
                 for a in ['_buddy_discover_on_buy', '_buddy_third_button',
                           '_buddies_all_types', '_quest_for_buddy',
                           '_buddy_cost_per_buy', '_buddy_cost_reduction']))
        )
        if buddies_enabled:
            self._assign_buddies()
        self._start_recruit_phase()

    def _apply_anomaly(self) -> None:
        """Apply a random anomaly at game start (if any are registered).

        Anomaly modifies global game rules. Pick one at random from card_db
        and trigger its on_apply script.
        Only anomalies with non-DEFERRED scripts are eligible.
        """
        if self.active_anomaly is not None:
            return

        from hsrl.core.anomaly import Anomaly

        available_ids = []
        for cid, data in self.card_db._cards.items():
            if data.cardtype != CardType.ANOMALY:
                continue
            if cid.startswith("EXAMPLE"):
                continue
            if "BGDUO" in cid:
                continue
            # Skip DEFERRED anomalies (no functional script)
            if data.scripts is None:
                continue
            doc = (data.scripts.__doc__ or "").lower()
            if "deferred" in doc:
                continue
            available_ids.append(cid)

        if not available_ids:
            return

        anomaly_id = self.rng.choice(available_ids)
        anomaly_data = self.card_db.get(anomaly_id)
        anomaly = Anomaly(anomaly_data, game=self)
        self.active_anomaly = anomaly

        # Trigger on_apply script
        if anomaly.data.scripts:
            apply_fn = getattr(anomaly.data.scripts, "on_apply", None)
            if apply_fn and callable(apply_fn):
                result = apply_fn(anomaly, self)
                if result:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            self.queue_action(action, source=anomaly)
                    else:
                        self.queue_action(result, source=anomaly)
                    self.resolve_queue()

        self.broadcast("ANOMALY_APPLIED", anomaly_id)


    def _select_active_tribes(self) -> None:
        """Randomly select 5 of 10 playable tribes."""
        from hsrl.core.enums import Race
        anomaly = self.active_anomaly
        if anomaly is not None and not isinstance(anomaly, bool):
            t = getattr(anomaly, "_single_tribe", None)
            if t is not None:
                self.active_tribes = {t}
                return
            tf = getattr(anomaly, "_tribe_filters", None)
            if tf is not None:
                self.active_tribes = set(tf)
                return
        playable = [Race.BEAST, Race.DEMON, Race.DRAGON, Race.ELEMENTAL,
                     Race.MECH, Race.MURLOC, Race.NAGA, Race.PIRATE,
                     Race.QUILBOAR, Race.UNDEAD]
        self.active_tribes = set(self.rng.sample(playable, 5))

        # Prune minion pool to only active tribes + neutrals
        if self.minion_pool is not None:
            allowed = self.active_tribes | {Race.ALL, Race.NONE, Race.INVALID}
            for tier, cards in list(self.minion_pool._pools.items()):
                self.minion_pool._pools[tier] = [
                    cid for cid in cards
                    if self.minion_pool._matches_race(cid, allowed)
                ]

    # ── Trinket offering ─────────────────────────────────────────────────────

    # Cached tribe → trinket-id list. Built lazily from card_db when needed.
    _trinket_tribe_index: Optional[Dict[str, List[str]]] = None

    # Cached trinket type pools (lesser/greater). Loaded from pool_trinket_texts.json.
    _trinket_lesser_ids: Optional[set] = None
    _trinket_greater_ids: Optional[set] = None

    @classmethod
    def _load_trinket_type_pools(cls) -> None:
        """Load trinket type classification from pool_trinket_texts.json.

        Populates _trinket_lesser_ids and _trinket_greater_ids class caches.
        Called lazily on first _offer_trinkets() invocation.
        """
        if cls._trinket_lesser_ids is not None:
            return
        import json
        import os
        pool_path = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                                 "pool_trinket_texts.json")
        lesser, greater = set(), set()
        try:
            with open(pool_path) as f:
                data = json.load(f)
            for cid, entry in data.items():
                ttype = entry.get("trinket_type", "")
                if ttype == "lesser":
                    lesser.add(cid)
                elif ttype == "greater":
                    greater.add(cid)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        cls._trinket_lesser_ids = lesser
        cls._trinket_greater_ids = greater

    @classmethod
    def _get_trinket_tribe_index(cls, card_db) -> Dict[str, List[str]]:
        """Build (or return cached) index: tribe_name → [trinket_id, ...].

        Tribe detection uses card name, card text, and script source references.
        Returns a dict with tribe keys plus a ``None`` key for neutral trinkets.
        """
        if cls._trinket_tribe_index is not None:
            return cls._trinket_tribe_index

        import re
        import inspect

        _RACE_KEYWORDS = {
            "BEAST":      r"\b(?:beast|wolf|raptor|bear|savannah|monkey|beetle|rat|hyena|spider|serpent|saurolisk|dragonhawk|carrion)\b",
            "MECH":       r"\b(?:mech|automaton|bot|tron|drill|cog|scrap|magnet|ironforge|annoy|micro|replicating|electrode)\b",
            "MURLOC":     r"\b(?:murloc|fin|mrrgl|primalfin|coldlight|murkeye)\b",
            "DEMON":      r"\b(?:demon|wrath|fel|void|soul|imp|dread|infernal|abyssal|doom|jaraxxus)\b",
            "DRAGON":     r"\b(?:dragon|whelp|draconic|ember|twilight|onyxia|kalecgos|ysera|nozdormu|azure|malygos|aspect)\b",
            "PIRATE":     r"\b(?:pirate|booty|cannon|ship|southsea|skycap|swashbuckler|buccaneer|hozen|plunder|admiral|bilgewater)\b",
            "ELEMENTAL":  r"\b(?:elemental|fire|water|frost|earth|magma|storm|elementium|igneous)\b",
            "QUILBOAR":   r"\b(?:quilboar|blood.gem|bristleback|gem|bristlemane|razorfen|boar|quill)\b",
            "NAGA":       r"\b(?:naga|spellcraft|spell|coilfang|azshara|tidal|lurker|scales)\b",
            "UNDEAD":     r"\b(?:undead|deathrattle|skeleton|ghoul|lich|banshee|cadaver|grave|mummy|necromancer)\b",
        }
        _RACE_NAMES = set(Race.__members__) - {"NONE", "INVALID", "ALL"}

        tribe_map: Dict[str, List[str]] = {t: [] for t in _RACE_KEYWORDS}
        neutral: List[str] = []

        for cid, data in card_db._cards.items():
            if data.cardtype != CardType.TRINKET or cid.startswith("EXAMPLE"):
                continue

            name = (data.name or "").lower()
            text = (data.text or "").lower()
            combined = name + " " + text

            # Try card text first
            matched = None
            for tribe, pattern in _RACE_KEYWORDS.items():
                if re.search(pattern, combined):
                    matched = tribe
                    break

            # Fall back to script source scanning
            if matched is None and data.scripts is not None:
                try:
                    src = inspect.getsource(data.scripts)
                    src_upper = src.upper()
                    for race_name in _RACE_NAMES:
                        if race_name in src_upper:
                            matched = race_name
                            break
                except (TypeError, OSError):
                    pass

            if matched:
                tribe_map[matched].append(cid)
            else:
                neutral.append(cid)

        tribe_map[None] = neutral  # type: ignore[index]
        cls._trinket_tribe_index = tribe_map
        return tribe_map

    @staticmethod
    def _detect_dominant_tribe(player: Player) -> Optional[str]:
        """Return the most common race name on the player's board.
        Ties are broken by total stats (atk+hp). Returns None for empty board.
        """
        from collections import Counter
        board = player.get_board_minions()
        if not board:
            return None
        race_counts: Dict[str, List[Minion]] = {}
        for m in board:
            r = m.race
            rname = r.name if hasattr(r, "name") else str(r)
            if rname in ("NONE", "INVALID", "ALL"):
                continue
            race_counts.setdefault(rname, []).append(m)
        if not race_counts:
            return None
        # Pick the race with the most minions; tie-break by total stats
        def _key(item):
            rname, minions = item
            return (len(minions), sum(m.atk + m.health for m in minions))
        return max(race_counts.items(), key=_key)[0]

    def _get_trinket_cost(self, card_id: str) -> int:
        """Return the gold cost of a trinket, or 99 if unknown."""
        data = self.card_db.get(card_id)
        return data.tags.get(GameTag.COST, 3) if data else 99

    def _score_trinket_for_player(self, card_id: str, player: Player) -> float:
        """Score a trinket for a player. Higher = better fit."""
        cost = self._get_trinket_cost(card_id)
        if cost >= 99:
            return -100.0
        dominant = self._detect_dominant_tribe(player)
        index = self._get_trinket_tribe_index(self.card_db)

        score = 0.0

        # Tribe match
        if dominant and card_id in index.get(dominant, []):  # type: ignore[operator]
            score += 15.0
        elif any(card_id in index.get(t, []) for t in index if t is not None):  # type: ignore[operator]
            # Matches some tribe but not the dominant one
            score -= 5.0
        # else: neutral → no penalty, no bonus

        # Cost efficiency (cheaper = more gold for minions)
        if cost == 0:
            score += 10.0
        elif cost <= 2:
            score += 5.0
        elif cost >= 5:
            score -= 5.0

        # Prefer trinkets the player can actually afford
        if player.gold < cost:
            score -= 20.0

        return score

    def _offer_trinkets(self, player: Player) -> None:
        """Offer 4 trinkets on Turn 6 (Lesser) and Turn 9 (Greater).

        Selection is biased toward the player's dominant board tribe. At least
        one offered trinket costs ≤ 2 gold. Offers are stored on
        player._pending_trinket_offers for the player (or agent) to choose from.
        """
        trinket_slot = GameTag.TRINKET_1 if self.turn == 6 else GameTag.TRINKET_2
        if player.has_tag(trinket_slot) or player._pending_trinket_offers:
            return

        # ── Load trinket type pools (lazy) ──
        self._load_trinket_type_pools()
        allowed_ids = (
            self._trinket_lesser_ids if self.turn == 6
            else self._trinket_greater_ids
        )

        # ── Build candidate pools filtered by trinket type ──
        index = self._get_trinket_tribe_index(self.card_db)
        neutral_pool: List[str] = [
            cid for cid in index.get(None, [])
            if allowed_ids is None or cid in allowed_ids
        ]
        dominant = self._detect_dominant_tribe(player)
        tribe_pool: List[str] = [
            cid for cid in index.get(dominant, [])
            if allowed_ids is None or cid in allowed_ids
        ] if dominant else []

        # ── Assemble 4 offers: bias toward dominant tribe ──
        offered: List[str] = []
        if tribe_pool:
            n_tribe = min(3, len(tribe_pool))
            offered.extend(self.rng.sample(tribe_pool, n_tribe))

        # Fill remaining slots from neutral pool
        needed = 4 - len(offered)
        if needed > 0 and neutral_pool:
            offered.extend(self.rng.sample(neutral_pool, min(needed, len(neutral_pool))))

        # If still short, pad from any filtered candidate
        if len(offered) < 4:
            all_filtered = tribe_pool + neutral_pool
            remaining = [c for c in all_filtered if c not in offered]
            needed = 4 - len(offered)
            if remaining:
                offered.extend(self.rng.sample(remaining, min(needed, len(remaining))))

        if len(offered) < 4:
            # Fallback: use all available trinkets (ignore type filter)
            all_ids = [cid for cid in index.get(None, []) + sum(
                [v for k, v in index.items() if k is not None], []
            ) if cid not in offered]
            needed = 4 - len(offered)
            if all_ids:
                offered.extend(self.rng.sample(all_ids, min(needed, len(all_ids))))

        if not offered:
            return

        # ── Ensure at least one cheap option (cost ≤ 2) ──
        has_cheap = any(self._get_trinket_cost(cid) <= 2 for cid in offered)
        if not has_cheap:
            all_candidates = tribe_pool + neutral_pool
            cheap_candidates = [
                cid for cid in all_candidates
                if cid not in offered and self._get_trinket_cost(cid) <= 2
            ]
            if cheap_candidates:
                offered.sort(key=lambda cid: self._get_trinket_cost(cid))
                offered[-1] = self.rng.choice(cheap_candidates)

        player._pending_trinket_offers = offered
        self.broadcast("TRINKETS_OFFERED", player, offered)

    def buy_trinket(self, player: Player, offer_index: int) -> bool:
        """Purchase a trinket from the player's pending offers.

        Args:
            player: The player making the purchase.
            offer_index: 0-based index into player._pending_trinket_offers.

        Returns:
            True if the purchase succeeded, False otherwise.
        """
        from hsrl.core.trinket import Trinket
        from hsrl.core.actions import SpendGold

        if not player._pending_trinket_offers:
            return False
        if offer_index < 0 or offer_index >= len(player._pending_trinket_offers):
            return False

        trinket_slot = GameTag.TRINKET_1 if self.turn == 6 else GameTag.TRINKET_2
        if player.has_tag(trinket_slot):
            return False

        chosen_id = player._pending_trinket_offers[offer_index]
        trinket_data = self.card_db.get(chosen_id)
        if trinket_data is None:
            return False

        cost = trinket_data.tags.get(GameTag.COST, 3) if trinket_data.tags else 3
        if player.gold < cost:
            return False

        trinket = Trinket(trinket_data, game=self)
        trinket.controller = player
        self.queue_action(SpendGold(player, cost))
        player.trinkets.append(trinket)
        player.set_tag(trinket_slot, True)
        player._pending_trinket_offers = []

        # Trigger on_summon and queue returned actions
        if trinket_data.scripts:
            fn = getattr(trinket_data.scripts, "on_summon", None)
            if fn and callable(fn):
                result = fn(trinket, self)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for a in result:
                            self.queue_action(a, source=trinket)
                    elif isinstance(result, Action):
                        self.queue_action(result, source=trinket)

        self.broadcast("TRINKET_PURCHASED", player, chosen_id)
        self.resolve_queue()
        return True

    # ── Quest System ──────────────────────────────────────────────────────────

    def _offer_quests(self, player: Player) -> None:
        """Offer quests to a player on Turn 4.

        Player chooses from 3 quest+reward pairs.
        Each quest has a type and target; the reward is unlocked on completion.
        """
        if player.active_quest is not None:
            return

        # Collect available quests from card_db
        available_ids = [
            cid for cid, data in self.card_db._cards.items()
            if data.cardtype == CardType.QUEST
        ]
        reward_ids = [
            cid for cid, data in self.card_db._cards.items()
            if data.cardtype == CardType.REWARD
            and cid not in ("EXAMPLE_TRIPLE_REWARD",)  # Exclude triple rewards
        ]

        if not available_ids or not reward_ids:
            return

        import random
        quest_id = self.rng.choice(available_ids)
        reward_id = self.rng.choice(reward_ids)

        quest = self.card_db.create_quest(quest_id, game=self)
        quest.controller = player
        player.active_quest = quest

        reward = self.card_db.create_quest_reward(reward_id, game=self)
        reward.controller = player
        player.rewards.append(reward)
        quest.set_tag(GameTag.REWARD_UNLOCKED, reward)

        # Trigger quest on_summon for registration
        if quest.data.scripts:
            fn = getattr(quest.data.scripts, "on_summon", None)
            if fn and callable(fn):
                fn(quest, self)

        self.broadcast("QUEST_OFFERED", player, quest_id, reward_id)

    def _increment_quest_progress(self, player: Player, amount: int = 1) -> None:
        """Increment quest progress. Triggers reward unlock on completion."""
        quest = player.active_quest
        if quest is None or quest.is_complete:
            return

        completed = quest.increment_progress(amount)
        if completed:
            self.broadcast("QUEST_COMPLETED", player, quest)
            # Activate the reward's on_unlock script
            reward = quest.reward_data
            if reward is not None:
                player.set_tag(GameTag.REWARD_UNLOCKED, True)
                if reward.data.scripts:
                    unlock = getattr(reward.data.scripts, "on_unlock", None)
                    if unlock and callable(unlock):
                        result = unlock(reward, self)
                        if result:
                            if isinstance(result, (list, tuple)):
                                for action in result:
                                    self.queue_action(action, source=reward)
                            else:
                                self.queue_action(result, source=reward)
                    # Register on_summon for reward if it has one
                    on_summon = getattr(reward.data.scripts, "on_summon", None)
                    if on_summon and callable(on_summon):
                        on_summon(reward, self)
                self.resolve_queue()

    def _start_recruit_phase(self) -> None:
        self.step = Step.RECRUIT
        # Process turn-scheduled callbacks and deferred actions
        self.process_deferred_actions()
        alive_players = [p for p in self.players if p.is_alive]
        for index, p in enumerate(alive_players):
            self.broadcast(RECRUIT_BEGIN, p, event_player=p,
                           include_global=index == 0)
            self.broadcast(TURN_BEGIN, p, event_player=p,
                           include_global=index == 0)
        for p in alive_players:
            if not p.is_alive:
                continue
            # Dispatch trinket on_turn_begin (for every-N-turns counters)
            self._dispatch_trinket_event(p, "on_turn_begin")
            # Reset hero power usage
            p.set_tag(GameTag.HERO_POWER_USED, False)
            p.set_tag(GameTag.SECONDARY_HERO_POWER_USED, False)
            # Anomaly: all heroes are Nguyen — discover a hero power each turn
            anomaly = self.active_anomaly
            if (anomaly is not None and not isinstance(anomaly, bool)
                    and getattr(anomaly, '_all_heroes_nguyen', False)):
                from hsrl.core.actions import DiscoverSpell
                self.queue_action(DiscoverSpell(p))
            # Reset turn-level tracking counters
            p.set_tag(GameTag.GOLD_SPENT_THIS_TURN, 0)
            p.set_tag(GameTag.TAVERN_SPELLS_CAST_THIS_TURN, 0)
            p.set_tag(GameTag.CARDS_PLAYED_THIS_TURN, 0)
            p.clear_tag(GameTag.TRINKET_OFFERED)  # Reset trinket offered flag each turn
            # Offer trinkets on Turn 6 and Turn 9
            if self.turn in (6, 9):
                self._offer_trinkets(p)
            # Offer quests on Turn 4
            if self.turn == 4:
                self._offer_quests(p)
            # Increment turns-in-hand for all minions in hand
            for m in p.hand:
                current = m.get_tag(GameTag.TURNS_IN_HAND, 0)
                m.set_tag(GameTag.TURNS_IN_HAND, current + 1)
            # Gain gold (3 on turn 1, +1 each turn, max 10)
            gold_gained = min(3 + self.turn - 1, 10)
            # Set max gold cap for this turn (base: min(3+turn-1, 10),
            # may be increased by hero powers, trinkets, spells).
            p.set_tag(GameTag.MAX_GOLD, gold_gained)
            # Anomaly override: set specific starting gold (Curse of Aggramar)
            if (self.turn == 1
                    and self.active_anomaly is not None
                    and not isinstance(self.active_anomaly, bool)):
                override = getattr(self.active_anomaly, '_start_gold', None)
                if override is not None:
                    gold_gained = override
            # Gold carryover: unspent gold carries to next turn (BG27_Anomaly_002)
            if (self.active_anomaly is not None
                    and hasattr(self.active_anomaly, '_gold_carryover')):
                unspent = p.get_tag(GameTag.GOLD, 0)
                gold_gained += unspent
                if unspent >= 5:
                    gold_gained += 1  # bonus for keeping 5+
            p.set_tag(GameTag.GOLD, gold_gained)
            # Reduce tavern upgrade cost by 1 each turn after the first
            # (skip turn 1 — the initial cost of 5 is already correct)
            if self.turn > 1:
                current_cost = p.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)
                if current_cost > 0:
                    p.set_tag(GameTag.TAVERN_UPGRADE_COST, current_cost - 1)

        # ── Trigger Start of Turn effects ──
        self._trigger_start_of_turn()
        self.resolve_queue()

        # ── Generate Spellcraft spells ──
        self._generate_spellcraft_spells()
        self.resolve_queue()

        # ── Auto-refresh tavern (preserves frozen minions) ──
        for p in self.players:
            if p.is_alive and self.minion_pool is not None:
                self.refresh_tavern(p, preserve_frozen=True)
        self.resolve_queue()

        # Battlegrounds exposes the next opponent throughout recruit. Pair now
        # and reuse this schedule at combat instead of choosing after everyone
        # has already made their decisions.
        alive = [p for p in self.players if p.is_alive]
        self._scheduled_combat_pairs = self._pair_combat_players(alive)
        self._current_combat_opponents = {}
        for p1, p2 in self._scheduled_combat_pairs:
            if p2 is not None:
                self._current_combat_opponents[p1] = p2
                self._current_combat_opponents[p2] = p1

    def end_recruit_phase(self) -> None:
        # A heuristic/route turn may end immediately after opening a targeted
        # action or discover. Resolve every recruit decision before combat;
        # otherwise resolve_queue() pauses forever and combat Hit actions never
        # execute even though attacks continue.
        for player in self.players:
            while self.has_pending_target(player):
                self.auto_resolve_pending_target(player)
            choice = self.get_pending_choice(player)
            while choice is not None:
                self.resolve_pending_choice(self.rng.randrange(len(choice.options)), player)
                choice = self.get_pending_choice(player)
        # ── Trigger End of Turn effects BEFORE combat ──
        self._trigger_end_of_turn()
        self.resolve_queue()
        # ── Clear "this turn only" temporary buffs from minions ──
        self._clear_temporary_buffs()
        # ── Clear "until next turn" temporary deathrattles ──
        self._clear_temporary_deathrattles()
        # ── Clear unused Spellcraft spells from hand ──
        self._cleanup_spellcraft_spells()
        alive_players = [p for p in self.players if p.is_alive]
        for index, p in enumerate(alive_players):
            self.broadcast(TURN_END, p, event_player=p,
                           include_global=index == 0)
            self.broadcast(RECRUIT_END, p, event_player=p,
                           include_global=index == 0)
        self._start_combat_phase()

    def _clear_temporary_buffs(self) -> None:
        """Remove temporary (this-turn-only or this-combat-only) buffs from all minions."""
        for p in self.players:
            if not p.is_alive:
                continue
            for m in p.board:
                if not m.dead:
                    m._buffs = [b for b in m._buffs
                                if not getattr(b, 'temporary', False)]

    def _clear_temporary_deathrattles(self) -> None:
        """Remove temporary deathrattles (from Spellcraft effects like Crab Mount)."""
        for p in self.players:
            if not p.is_alive:
                continue
            for m in p.board:
                if not m.dead and m.get_tag(GameTag.TEMPORARY_DEATHRATTLE):
                    m._script_overrides.pop("deathrattle", None)
                    m.set_tag(GameTag.TEMPORARY_DEATHRATTLE, False)

    def _pair_combat_players(self, alive: list) -> list:
        """Pair alive players for combat, avoiding recent rematches when possible.

        Returns list of (player, opponent) tuples. If odd, one player faces
        a ghost (None opponent + ghost board).
        """
        import random
        # Track opponent history (last 2 opponents per player)
        if not hasattr(self, '_opponent_history'):
            self._opponent_history: dict = {p: [] for p in self.players}

        paired = set()
        pairs = []

        # Greedy pairing: for each unpaired player, find best available opponent
        unpaired = list(alive)
        self.rng.shuffle(unpaired)

        while len(unpaired) >= 2:
            p1 = unpaired[0]
            best = None
            for p2 in unpaired[1:]:
                if p2 in self._opponent_history.get(p1, []):
                    continue  # recent rematch — try to avoid
                best = p2
                break
            if best is None:
                best = unpaired[1]  # fallback: forced rematch

            pairs.append((p1, best))
            self._opponent_history.setdefault(p1, []).append(best)
            self._opponent_history.setdefault(best, []).append(p1)
            # Keep only last 2 opponents in history
            if len(self._opponent_history[p1]) > 2:
                self._opponent_history[p1] = self._opponent_history[p1][-2:]
            if len(self._opponent_history[best]) > 2:
                self._opponent_history[best] = self._opponent_history[best][-2:]
            unpaired.remove(p1)
            unpaired.remove(best)

        if unpaired:
            # Odd player — faces ghost
            ghost_player = unpaired[0]
            pairs.append((ghost_player, None))

        return pairs

    def _build_ghost_board(self, player: Player) -> list:
        """Build a ghost opponent board for the unpaired player.

        Uses the last board of a dead player, or a copy of a random alive
        player's board (excluding the current player).
        """
        import random
        # Prefer dead players' boards
        dead = [p for p in self.players if not p.is_alive]
        for dp in dead:
            ghost_board = getattr(dp, 'last_combat_board', None)
            if ghost_board:
                return [self._snapshot_minion_for_combat(m) for m in ghost_board
                        if not m.dead]

        # Fallback: copy a random alive player's board
        candidates = [p for p in self.players if p.is_alive and p is not player]
        if candidates:
            donor = self.rng.choice(candidates)
            return [self._snapshot_minion_for_combat(m)
                    for m in donor.board if not m.dead]

        # Last resort: empty
        return []

    def _start_combat_phase(self) -> None:
        self.step = Step.COMBAT
        self.broadcast(COMBAT_BEGIN, self.turn)

        alive_players = [p for p in self.players if p.is_alive]
        self._combat_pairs = []

        # Snapshot each player's board BEFORE combat clones
        for p in self.players:
            if p.is_alive:
                p.last_combat_board = [m for m in p.board if not m.dead]

        scheduled_players = {
            player for pair in self._scheduled_combat_pairs for player in pair
            if player is not None
        }
        if scheduled_players == set(alive_players):
            pairs = self._scheduled_combat_pairs
        else:
            pairs = self._pair_combat_players(alive_players)

        for p1, p2 in pairs:
            if p2 is not None:
                self._combat_pairs.append((p1, p2))
                self._combat_pairs.append((p2, p1))
                self._run_combat(p1, p2)
            else:
                # Ghost combat
                ghost_board = self._build_ghost_board(p1)
                self._combat_pairs.append((p1, None))
                self._run_ghost_combat(p1, ghost_board)

        self._end_combat_phase()

    def _run_ghost_combat(self, player: Player, ghost_board: list) -> None:
        """Run combat between a player and a ghost opponent.

        The ghost board fights normally but the ghost "player" takes no damage.
        Player deals damage to the ghost and takes damage from surviving
        ghost minions.
        """
        if not ghost_board:
            # Empty ghost — player wins, no damage dealt or taken
            return

        self.in_combat = True
        self._start_combat_budget(player, None)

        # Save original board
        original_board = list(player.board)

        # Replace with combat clones
        player.board = [self._snapshot_minion_for_combat(m) for m in original_board]

        board_player = player.get_board_minions()
        for m in board_player + ghost_board:
            m.reset_combat_state()

        self._combat_death_log = []
        self._combat_summon_log = []

        # Start of Combat for player only
        self._trigger_start_of_combat(board_player, player)

        # Determine first attacker
        if len(board_player) > len(ghost_board):
            attacker_side, defender_side = board_player, ghost_board
        elif len(ghost_board) > len(board_player):
            attacker_side, defender_side = ghost_board, board_player
        else:
            if self.rng.choice([True, False]):
                attacker_side, defender_side = board_player, ghost_board
            else:
                attacker_side, defender_side = ghost_board, board_player

        # Combat loop
        consecutive_passes = 0
        for _ in range(self.combat_attack_budget + 1):
            attacker = self._get_next_attacker(attacker_side)
            if attacker is None:
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                attacker_side, defender_side = defender_side, attacker_side
                continue
            consecutive_passes = 0
            target = self._choose_attack_target(defender_side)
            if target is None:
                break

            from hsrl.core.actions import Attack
            self._consume_combat_budget("attacks")
            self.queue_action(Attack(attacker, target))
            self.resolve_queue()

            attacker_side, defender_side = defender_side, attacker_side

            living_player = [m for m in board_player if not m.dead]
            living_ghost = [m for m in ghost_board if not m.dead]
            if not living_player or not living_ghost:
                break

        living_player = [m for m in board_player if not m.dead]

        # Damage: ghost survivors deal damage to player
        damage = 0
        for m in ghost_board:
            if not m.dead:
                damage += m.tech_level
        # Apply damage cap
        cap = self._get_damage_cap()
        if cap is not None:
            damage = min(damage, cap)

        if damage > 0:
            self._deal_player_damage(player, damage)

        # Restore original board
        player.board = original_board

        self.in_combat = False

    def _snapshot_minion_for_combat(self, minion: Minion) -> Minion:
        """Create a combat clone of a minion with deep-copied mutable state.

        Combat operates on clones so that original boards are not affected
        by combat-only buffs, damage, or deaths.
        """
        clone = copy.copy(minion)
        clone.tags = copy.deepcopy(minion.tags)
        clone._buffs = copy.deepcopy(minion._buffs)
        clone._script_overrides = copy.deepcopy(minion._script_overrides)
        # Clear event listeners — they reference the original entity and must
        # not fire during combat on the clone. Combat mechanics (deathrattle,
        # reborn, avenge) are dispatched directly through _check_deaths(), not
        # the event listener system.
        clone._events = []
        return clone

    def _run_combat(self, player_a: Player, player_b: Player) -> None:
        """Run a single combat between two players."""
        self.in_combat = True
        previous_combat_opponents = self._current_combat_opponents
        self._current_combat_opponents = {
            player_a: player_b,
            player_b: player_a,
        }
        self._start_combat_budget(player_a, player_b)
        self._start_of_combat_global_broadcasted = False

        # Reset anomaly SoC guard so effects fire once per combat
        if self.active_anomaly is not None and not isinstance(self.active_anomaly, bool):
            self.active_anomaly._soc_triggered = False

        # Save original boards and graveyards — combat runs on snapshots
        original_board_a = list(player_a.board)
        original_board_b = list(player_b.board)
        original_graveyard_a = list(player_a.graveyard)
        original_graveyard_b = list(player_b.graveyard)

        # Replace boards with combat clones
        player_a.board = [self._snapshot_minion_for_combat(m) for m in original_board_a]
        player_b.board = [self._snapshot_minion_for_combat(m) for m in original_board_b]
        # Clear graveyards — combat deaths are tracked in _combat_death_log
        player_a.graveyard = []
        player_b.graveyard = []

        board_a = player_a.get_board_minions()
        board_b = player_b.get_board_minions()

        for m in board_a + board_b:
            m.reset_combat_state()

        # Reset combat death log + summon log
        self._combat_death_log = []
        self._combat_summon_log = []

        # Start of Combat effects
        self._trigger_start_of_combat(board_a, player_a)
        self._trigger_start_of_combat(board_b, player_b)
        self.resolve_queue()

        # Determine first attacker
        if len(board_a) > len(board_b):
            attacker_side, defender_side = board_a, board_b
            attacker_player, defender_player = player_a, player_b
        elif len(board_b) > len(board_a):
            attacker_side, defender_side = board_b, board_a
            attacker_player, defender_player = player_b, player_a
        else:
            # Random
            if self.rng.choice([True, False]):
                attacker_side, defender_side = board_a, board_b
                attacker_player, defender_player = player_a, player_b
            else:
                attacker_side, defender_side = board_b, board_a
                attacker_player, defender_player = player_b, player_a

        # Log combat start
        self._combat_event_log.append({
            'event': 'combat_start',
            'turn': self.turn,
            'p1': player_a.get_tag(GameTag.NAME) or str(player_a.entity_id), 'p2': player_b.get_tag(GameTag.NAME) or str(player_b.entity_id),
            'p1_board': [f"{m.atk}/{m.health}" for m in board_a if not m.dead],
            'p2_board': [f"{m.atk}/{m.health}" for m in board_b if not m.dead],
            'first_attacker': attacker_player.get_tag(GameTag.NAME) or str(attacker_player.entity_id),
        })

        # Combat loop
        consecutive_passes = 0
        for _ in range(self.combat_attack_budget + 1):
            # Get next attacker from attacker_side
            attacker = self._get_next_attacker(attacker_side)
            if attacker is None:
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                attacker_side, defender_side = defender_side, attacker_side
                attacker_player, defender_player = defender_player, attacker_player
                continue
            consecutive_passes = 0

            # Choose target from defender_side
            target = self._choose_attack_target(defender_side)
            if target is None:
                break

            from hsrl.core.actions import Attack
            self._consume_combat_budget("attacks")
            att_atk, att_hp = attacker.atk, attacker.health
            def_atk, def_hp = target.atk, target.health
            self.queue_action(Attack(attacker, target))
            self.resolve_queue()
            # Log attack outcome
            atk_alive = not attacker.dead
            def_alive = not target.dead
            self._combat_event_log.append({
                'event': 'attack',
                'attacker': attacker.get_tag(GameTag.NAME) or '?',
                'atk_before': f"{att_atk}/{att_hp}",
                'atk_after': f"{attacker.atk}/{attacker.health}",
                'atk_dead': not atk_alive,
                'defender': target.get_tag(GameTag.NAME) or '?',
                'def_before': f"{def_atk}/{def_hp}",
                'def_after': f"{target.atk}/{target.health}",
                'def_dead': not def_alive,
            })

            # Swap sides
            self._last_defender = defender_player
            attacker_side, defender_side = defender_side, attacker_side
            attacker_player, defender_player = defender_player, attacker_player

            # Check if combat should end
            living_a = [m for m in board_a if not m.dead]
            living_b = [m for m in board_b if not m.dead]
            if not living_a or not living_b:
                break

        # Calculate damage
        self._resolve_combat_damage(player_a, player_b, board_a, board_b)

        # Log combat end
        living_a = [m for m in board_a if not m.dead]
        living_b = [m for m in board_b if not m.dead]
        winner = player_a if living_a else (player_b if living_b else None)
        self._combat_event_log.append({
            'event': 'combat_end',
            'survivors_p1': len(living_a), 'survivors_p2': len(living_b),
            'p1_alive': player_a.is_alive, 'p2_alive': player_b.is_alive,
            'winner': winner.get_tag(GameTag.NAME) or str(winner.entity_id) if winner else 'draw',
        })

        # Tarecgosa Sticker: persist combat-gained stats for left/right dragons
        self._persist_combat_stats(player_a, board_a, original_board_a)
        self._persist_combat_stats(player_b, board_b, original_board_b)

        # Restore original boards and graveyards
        player_a.board = original_board_a
        player_b.board = original_board_b
        player_a.graveyard = original_graveyard_a
        player_b.graveyard = original_graveyard_b

        # Track opponent's last combat board (for discover-from-opponent effects)
        player_a.last_opponent_board = [m for m in board_b if not m.dead]
        player_b.last_opponent_board = [m for m in board_a if not m.dead]

        # ── Save combat memory for POMDP value network ──
        self._save_combat_record(player_a, player_b, board_a, board_b)

        self._current_combat_opponents = previous_combat_opponents
        self.in_combat = False

    def _persist_combat_stats(self, player, combat_board, original_board):
        """Tarecgosa Sticker: persist combat-gained stats for left/right dragons."""
        if not player.get_tag(GameTag.COMBAT_PERSIST_DRAGONS):
            return
        living_combat = [m for m in combat_board if not m.dead]
        if not living_combat:
            return
        leftmost = living_combat[0]
        rightmost = living_combat[-1]

        for clone in (leftmost, rightmost):
            if clone.race != Race.DRAGON:
                continue
            # Find the original by matching position in the combat board to original
            try:
                idx = combat_board.index(clone)
                if idx < len(original_board):
                    original = original_board[idx]
                    # Copy combat-gained buffs (ATK/HEALTH gained during combat)
                    combat_atk = clone.atk
                    combat_hp = clone.max_health
                    orig_atk = original.atk
                    orig_hp = original.max_health
                    atk_gain = combat_atk - orig_atk
                    hp_gain = combat_hp - orig_hp
                    if atk_gain > 0 or hp_gain > 0:
                        from hsrl.core.actions import BuffEnchantment
                        original.add_buff(BuffEnchantment(atk=max(0, atk_gain), health=max(0, hp_gain)))
                        original.set_tag(GameTag.HEALTH, original.max_health)
                    # Copy keywords gained during combat
                    for kw in [GameTag.DIVINE_SHIELD, GameTag.TAUNT, GameTag.WINDFURY,
                               GameTag.REBORN, GameTag.POISONOUS, GameTag.VENOMOUS]:
                        if clone.has_tag(kw) and not original.has_tag(kw):
                            original.set_tag(kw, True)
            except (ValueError, IndexError):
                continue

    # ── Combat Memory Tracking ──────────────────────────────────────────

    def _save_combat_record(self, player_a: Player, player_b: Player,
                            board_a: List[Minion], board_b: List[Minion]) -> None:
        """Record per-player per-opponent combat outcome for POMDP features."""
        living_a = [m for m in board_a if not m.dead]
        living_b = [m for m in board_b if not m.dead]

        stats_a = sum(m.atk + m.health for m in living_a)
        stats_b = sum(m.atk + m.health for m in living_b)

        if not living_a and not living_b:
            result_a = result_b = 0.5
        elif living_a and not living_b:
            result_a, result_b = 1.0, 0.0
        elif living_b and not living_a:
            result_a, result_b = 0.0, 1.0
        elif stats_a > stats_b:
            result_a, result_b = 1.0, 0.0
        elif stats_b > stats_a:
            result_a, result_b = 0.0, 1.0
        else:
            result_a = result_b = 0.5

        # Damage formula (matches _resolve_combat_damage):
        # winner.tavern_tier + sum(survivor tiers), capped
        def _combat_damage(winner, survivors):
            if not survivors:
                return 0
            dmg = winner.tavern_tier
            for m in survivors:
                dmg += m.tech_level
            cap = self._get_damage_cap()
            if cap is not None:
                dmg = min(dmg, cap)
            return dmg

        dmg_a = _combat_damage(player_a, living_a) if living_a and not living_b else (
            _combat_damage(player_a, living_a) if (living_a and living_b and stats_a > stats_b) else 0)
        dmg_b = _combat_damage(player_b, living_b) if living_b and not living_a else (
            _combat_damage(player_b, living_b) if (living_b and living_a and stats_b > stats_a) else 0)

        # Player A's record against B
        if player_a.entity_id not in self.combat_memory:
            self.combat_memory[player_a.entity_id] = {}
        self.combat_memory[player_a.entity_id][player_b.entity_id] = CombatRecord(
            board=[m for m in living_b],
            turn=self.turn,
            damage_dealt=dmg_a,
            damage_taken=dmg_b,
            result=result_a,
        )

        # Player B's record against A
        if player_b.entity_id not in self.combat_memory:
            self.combat_memory[player_b.entity_id] = {}
        self.combat_memory[player_b.entity_id][player_a.entity_id] = CombatRecord(
            board=[m for m in living_a],
            turn=self.turn,
            damage_dealt=dmg_b,
            damage_taken=dmg_a,
            result=result_b,
        )

    def track_triple(self, player: Player, tier: int) -> None:
        """Record a triple discovery at the given tavern tier."""
        pid = player.entity_id
        if pid not in self._triples_by_tier:
            self._triples_by_tier[pid] = {}
        self._triples_by_tier[pid][tier] = self._triples_by_tier[pid].get(tier, 0) + 1

    def get_triples_by_tier(self, player: Player) -> Dict[int, int]:
        """Get triples discovered per tier for a player."""
        return self._triples_by_tier.get(player.entity_id, {})

    def track_tavern_upgrade(self, player: Player, new_tier: int) -> None:
        """Record when a player upgrades to each tavern tier."""
        pid = player.entity_id
        if pid not in self._tavern_upgrade_turns:
            self._tavern_upgrade_turns[pid] = {}
        if new_tier not in self._tavern_upgrade_turns[pid]:
            self._tavern_upgrade_turns[pid][new_tier] = self.turn

    def get_tavern_upgrade_turns(self, player: Player) -> Dict[int, int]:
        """Get {tier: turn} for a player's tavern upgrades."""
        return self._tavern_upgrade_turns.get(player.entity_id, {})

    def _get_next_attacker(self, board: List[Minion]) -> Optional[Minion]:
        """Get the next attacker, restarting the board cycle when exhausted.

        Battlegrounds minions attack again after every living minion on their
        side has taken its turn. Treating WINDFURY_ATTACKS as a once-per-combat
        counter made stable boards draw forever and prevented matches ending.
        """
        for m in board:
            if not m.dead and m.can_attack:
                return m
        living_attackers = [m for m in board if not m.dead and m.atk > 0]
        if living_attackers:
            for m in living_attackers:
                m.set_tag(GameTag.WINDFURY_ATTACKS, 0)
                m.set_tag(GameTag.EXHAUSTED, False)
            return living_attackers[0]
        return None

    def _choose_attack_target(self, board: List[Minion]) -> Optional[Minion]:
        """Choose a random target, respecting Taunt."""
        living = [m for m in board if not m.dead]
        if not living:
            return None
        taunts = [m for m in living if m.taunt]
        if taunts:
            return self.rng.choice(taunts)
        return self.rng.choice(living)

    def _dispatch_trinket_event(self, player: Player, method_name: str, **kwargs) -> None:
        """Call method_name on all player trinkets that have it.
        Extra kwargs are passed to the method (e.g. played_card=...)."""
        for trinket in player.trinkets:
            if not trinket.data.scripts:
                continue
            fn = getattr(trinket.data.scripts, method_name, None)
            if fn and callable(fn):
                if kwargs:
                    result = fn(trinket, self, **kwargs)
                else:
                    result = fn(trinket, self)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            self.queue_action(action, source=trinket)
                    elif isinstance(result, Action):
                        self.queue_action(result, source=trinket)

    def _trigger_start_of_turn(self) -> None:
        """Trigger all Start of Turn effects for each alive player's board."""
        # Priority 0: Anomaly Start of Turn effects (global)
        if (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)
                and self.active_anomaly.data
                and self.active_anomaly.data.scripts):
            sot = getattr(self.active_anomaly.data.scripts, 'start_of_turn', None)
            if sot and callable(sot):
                result = sot(self.active_anomaly, self)
                if result:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            self.queue_action(action, source=self.active_anomaly)
                    else:
                        self.queue_action(result, source=self.active_anomaly)
        for p in self.players:
            if not p.is_alive:
                continue
            # Priority 1: Trinket Start of Turn effects
            for trinket in p.trinkets:
                sot = trinket.start_of_turn
                if sot:
                    if isinstance(sot, (list, tuple)):
                        for action in sot:
                            self.queue_action(action, source=trinket)
                    else:
                        self.queue_action(sot, source=trinket)
            # Priority 2: Minion Start of Turn effects
            for m in p.board:
                if m.dead:
                    continue
                sot = m.start_of_turn
                if sot:
                    if isinstance(sot, (list, tuple)):
                        for action in sot:
                            self.queue_action(action, source=m)
                    else:
                        self.queue_action(sot, source=m)

    def _trigger_end_of_turn(self) -> None:
        """Trigger all End of Turn effects for each alive player's board."""
        for p in self.players:
            if not p.is_alive:
                continue
            # Priority 1: Trinket End of Turn effects
            for trinket in p.trinkets:
                eot = trinket.end_of_turn
                if eot:
                    if isinstance(eot, (list, tuple)):
                        for action in eot:
                            self.queue_action(action, source=trinket)
                    else:
                        self.queue_action(eot, source=trinket)
            # Priority 2: Minion End of Turn effects
            for m in p.board:
                if m.dead:
                    continue
                eot = m.end_of_turn
                if eot:
                    times = 2 if p.get_tag(GameTag.END_OF_TURN_DOUBLED) else 1
                    for _ in range(times):
                        if isinstance(eot, (list, tuple)):
                            for action in eot:
                                self.queue_action(action, source=m)
                        else:
                            self.queue_action(eot, source=m)

    def _generate_spellcraft_spells(self) -> None:
        """Generate a temporary Spellcraft spell for each Spellcraft minion/trinket.

        Each Spellcraft minion/trinket produces one spell at the start of each Recruit phase.
        The spell goes to the player's hand and is discarded if not played by end of turn.
        """
        for p in self.players:
            if not p.is_alive:
                continue
            # Minion Spellcraft
            for m in p.board:
                if m.dead:
                    continue
                if not m.has_tag(GameTag.SPELLCRAFT):
                    continue
                # Get the spell card_id from the minion's script
                if not m.data.scripts:
                    continue
                spellcraft_fn = getattr(m.data.scripts, "spellcraft", None)
                if spellcraft_fn is None or not callable(spellcraft_fn):
                    continue
                spell_id = spellcraft_fn(m, self)
                if spell_id is None:
                    continue
                # If golden, get the golden variant
                if m.is_golden:
                    golden_id = spell_id + "_GOLDEN"
                    if golden_id in self.card_db:
                        spell_id = golden_id
                # Create spell card and add to hand
                spell = self.create_minion(spell_id)
                if spell is None:
                    continue
                spell.controller = p
                spell.zone = Zone.HAND
                spell.set_tag(GameTag.SPELLCRAFT_SPELL, True)
                p.hand.append(spell)
            # Trinket Spellcraft
            for trinket in p.trinkets:
                if not trinket.data.scripts:
                    continue
                spellcraft_fn = getattr(trinket.data.scripts, "spellcraft", None)
                if spellcraft_fn is None or not callable(spellcraft_fn):
                    continue
                spell_id = spellcraft_fn(trinket, self)
                if spell_id is None:
                    continue
                spell = self.create_minion(spell_id)
                if spell is None:
                    continue
                spell.controller = p
                spell.zone = Zone.HAND
                spell.set_tag(GameTag.SPELLCRAFT_SPELL, True)
                p.hand.append(spell)

    def _cleanup_spellcraft_spells(self) -> None:
        """Remove unplayed Spellcraft spells from all players' hands."""
        for p in self.players:
            to_remove = [m for m in p.hand if m.has_tag(GameTag.SPELLCRAFT_SPELL)]
            for m in to_remove:
                p.hand.remove(m)
                m.zone = Zone.REMOVED

    def _trigger_start_of_combat(self, board: List[Minion], player: Player) -> None:
        # Broadcast to global listeners (hero powers, etc.)
        self.broadcast(
            START_OF_COMBAT,
            player,
            event_player=player,
            include_global=not self._start_of_combat_global_broadcasted,
        )
        self._start_of_combat_global_broadcasted = True

        # Priority 0: Anomaly Start of Combat effects (global, once per combat)
        if (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)
                and self.active_anomaly.data
                and self.active_anomaly.data.scripts
                and not getattr(self.active_anomaly, '_soc_triggered', False)):
            soc = getattr(self.active_anomaly.data.scripts, 'start_of_combat', None)
            if soc and callable(soc):
                self.active_anomaly._soc_triggered = True
                result = soc(self.active_anomaly, self)
                if result:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            self.queue_action(action, source=self.active_anomaly)
                    else:
                        self.queue_action(result, source=self.active_anomaly)

        # Priority 1: Trinket Start of Combat effects
        for trinket in player.trinkets:
            soc = trinket.start_of_combat
            if soc:
                if isinstance(soc, (list, tuple)):
                    for action in soc:
                        self.queue_action(action, source=trinket)
                else:
                    self.queue_action(soc, source=trinket)

        # Priority 2: Minion Start of Combat effects
        for m in board:
            soc = m.start_of_combat
            if soc:
                if isinstance(soc, (list, tuple)):
                    for action in soc:
                        self.queue_action(action, source=m)
                else:
                    self.queue_action(soc, source=m)

        # Priority 3: Repeat if SoC doubled (Valdrakken Wind Chimes)
        if player.get_tag(GameTag.START_OF_COMBAT_DOUBLED):
            for trinket in player.trinkets:
                soc = trinket.start_of_combat
                if soc:
                    if isinstance(soc, (list, tuple)):
                        for action in soc:
                            self.queue_action(action, source=trinket)
                    else:
                        self.queue_action(soc, source=trinket)
            for m in board:
                soc = m.start_of_combat
                if soc:
                    if isinstance(soc, (list, tuple)):
                        for action in soc:
                            self.queue_action(action, source=m)
                    else:
                        self.queue_action(soc, source=m)

    def _resolve_combat_damage(self, p1: Player, p2: Player, board1: List[Minion], board2: List[Minion]) -> None:
        """Deal damage to the loser, with a bounded repeated-draw tiebreak."""
        living1 = [m for m in board1 if not m.dead]
        living2 = [m for m in board2 if not m.dead]
        draw_key = tuple(sorted((p1.entity_id, p2.entity_id)))
        if living1 and not living2:
            winner, loser = p1, p2
            survivors = living1
            self._combat_draw_streaks.pop(draw_key, None)
        elif living2 and not living1:
            winner, loser = p2, p1
            survivors = living2
            self._combat_draw_streaks.pop(draw_key, None)
        else:
            # Identical endgame boards can produce a true draw forever because
            # recruit boards are restored after combat. Preserve two normal
            # draws, then apply a deterministic one-damage tiebreak so an
            # offline match always has a terminal placement.
            streak = self._combat_draw_streaks.get(draw_key, 0) + 1
            self._combat_draw_streaks[draw_key] = streak
            if streak >= 3:
                score1 = sum(m.atk + m.health for m in living1)
                score2 = sum(m.atk + m.health for m in living2)
                if score1 != score2:
                    loser = p1 if score1 < score2 else p2
                else:
                    loser = p1 if (self.turn + p1.entity_id + p2.entity_id) % 2 else p2
                self._deal_player_damage(loser, 1)
                self.broadcast(PLAYER_DAMAGE_TAKEN, loser, 1, None)
            return

        if loser is None:
            return

        # Damage = winner's tavern tier + sum of survivors' tavern tiers
        # Tokens count as tier 1
        damage = winner.tavern_tier
        for m in survivors:
            tier = m.tech_level
            damage += tier

        # Apply damage cap
        cap = self._get_damage_cap()
        if cap is not None:
            damage = min(damage, cap)

        # Deal damage to loser
        self._deal_player_damage(loser, damage)
        self.broadcast(PLAYER_DAMAGE_TAKEN, loser, damage, winner)

    def _get_damage_cap(self) -> Optional[int]:
        """Return the current damage cap, or None if removed."""
        # Anomaly override: Curse of Aggramar
        if (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)):
            override = getattr(self.active_anomaly, '_damage_cap_override', None)
            if override is not None:
                return override
        alive_count = sum(1 for p in self.players if p.is_alive)
        if alive_count <= 4:
            return None
        if self.turn <= 3:
            return 5
        elif self.turn <= 7:
            return 10
        else:
            return 15

    def _deal_player_damage(self, player: Player, damage: int) -> None:
        """Apply damage to a player's health, considering armor."""
        armor = player.armor
        if armor > 0:
            remaining = max(0, damage - armor)
            player.armor = armor - (damage - remaining)
            damage = remaining
        if damage > 0:
            # Eleventh Hour: prevent fatal combat damage, gain 11 gold next turn
            if (self.active_anomaly is not None
                    and hasattr(self.active_anomaly, '_eleventh_hour')
                    and player.entity_id not in getattr(
                        self.active_anomaly, '_eleventh_hour_used', set()
                    )
                    and damage >= player.health):
                used = getattr(self.active_anomaly, '_eleventh_hour_used', set())
                used.add(player.entity_id)
                self.active_anomaly._eleventh_hour_used = used
                player.health = 1  # survive at 1 HP
                next_turn = self.turn + 1
                p_ref = player
                self.schedule_turn_action(next_turn,
                    lambda g, t: g.queue_action(GainGold(p_ref, 11)))
                return
            player.health -= damage
        if player.health <= 0:
            player.set_tag(GameTag.PLAYSTATE, PlayState.LOST)
            player._death_turn = self.turn
            if not hasattr(self, '_death_counter'):
                self._death_counter = 0
            self._death_counter += 1
            player._death_order = self._death_counter
            self.broadcast(PLAYER_DEFEATED, player)

    def _end_combat_phase(self) -> None:
        self.broadcast("END_OF_COMBAT", self.turn)
        self.broadcast(COMBAT_END, self.turn)
        # Fill buddy meters after combat
        self._fill_buddy_meters()
        # Let Tarecgosa/Persistent Poet snapshot combat-gained stats
        self.broadcast(PRE_COMBAT_CLEANUP, self.turn)
        # Return combat-summoned minions to hand before cleanup
        from hsrl.core.actions import ReturnCombatSummons
        ReturnCombatSummons().do(None, self)
        # Remove temporary buffs from surviving minions
        self._clear_temporary_buffs()
        # Clean up boards (remove dead, return living to recruit board)
        for p in self.players:
            p.board = [m for m in p.board if not m.dead]
            p.graveyard.clear()
        self._check_game_over()
        if self.state == State.RUNNING:
            self.turn += 1
            self._start_recruit_phase()

    # ── Buddy System ─────────────────────────────────────────────────────────

    def _assign_buddies(self) -> None:
        """Assign a random buddy card to each player from the registered pool."""
        buddy_pool = [
            cid for cid, data in self.card_db._cards.items()
            if '_Buddy' in cid and data.cardtype == CardType.MINION
            and '_Buddy_G' not in cid and not cid.endswith('Buddy_e')
        ]
        if not buddy_pool:
            return
        import random
        for p in self.players:
            if p._buddy_card_id is None:
                p._buddy_card_id = self.rng.choice(buddy_pool)

    def _fill_buddy_meters(self) -> None:
        """Fill buddy meters after combat. Each player's surviving minions
        and killed enemy minions contribute to the meter."""
        for p in self.players:
            if not p.is_alive or p._buddy_obtained:
                continue
            if p._buddy_card_id is None:
                continue

            # Count surviving friendly minions
            survivors = len([m for m in p.board if not m.dead])
            # Count enemies this player killed (from combat death log)
            killed = len([m for m in self._combat_death_log
                         if m.controller is not None and m.controller != p])

            # Anomaly: quest-for-buddy — gain from quests not combat meter
            anomaly = self.active_anomaly
            if anomaly is not None and not isinstance(anomaly, bool):
                if getattr(anomaly, '_quest_for_buddy', False):
                    p._buddy_meter = min(p._buddy_meter + 25, p._buddy_meter_max)
                    continue

            # Standard meter fill: 1 point per surviving minion + enemy killed
            fill_amount = survivors + killed
            p._buddy_meter = min(p._buddy_meter + fill_amount, p._buddy_meter_max)

    def get_buddy(self, player: "Player") -> Optional["Minion"]:
        """Player purchases their buddy. Returns the buddy minion or None."""
        anomaly = self.active_anomaly
        if anomaly is not None and isinstance(anomaly, bool):
            anomaly = None

        if player._buddy_card_id is None:
            return None

        # Third button: golden buddy upgrade after normal buddy obtained
        if player._buddy_obtained:
            if (anomaly is None
                    or not getattr(anomaly, '_buddy_third_button', False)
                    or player._buddy_golden_available):
                return None
            # Allow golden buddy purchase
            cost = max(1, player._buddy_cost // 2)
            if player.gold < cost:
                return None
            from hsrl.core.actions import SpendGold
            self.queue_action(SpendGold(player, cost))
            golden_id = player._buddy_card_id.replace('_Buddy', '_Buddy_G')
            if golden_id == player._buddy_card_id:
                golden_id = player._buddy_card_id + '_G'
            buddy = self.create_minion(golden_id)
            if buddy is None:
                return None
            buddy.controller = player
            buddy.set_tag(GameTag.GOLDEN, True)
            buddy.atk = buddy.atk * 2
            buddy.health = buddy.health * 2
            player.hand.append(buddy)
            buddy.zone = Zone.HAND
            player._buddy_golden_available = True
            self.resolve_queue()
            return buddy

        if player._buddy_meter < player._buddy_meter_max:
            return None

        # Check gold
        cost = player._buddy_cost
        # Anomaly: cost per buy reduction
        if anomaly is not None:
            if getattr(anomaly, '_buddy_cost_per_buy', False):
                cost = max(1, cost - 1)

        if player.gold < cost:
            return None

        from hsrl.core.actions import SpendGold
        self.queue_action(SpendGold(player, cost))

        buddy = self.create_minion(player._buddy_card_id)
        if buddy is None:
            return None
        buddy.controller = player

        # Anomaly: buddies have all types
        if anomaly is not None:
            if getattr(anomaly, '_buddies_all_types', False):
                buddy.set_tag(GameTag.RACE, Race.ALL)

        player.hand.append(buddy)
        buddy.zone = Zone.HAND
        player._buddy_obtained = True

        # Anomaly: discover on buddy buy
        if anomaly is not None:
            if getattr(anomaly, '_buddy_discover_on_buy', False):
                from hsrl.core.actions import DiscoverMinion
                self.queue_action(DiscoverMinion(player))

        self.resolve_queue()
        return buddy

    def _check_game_over(self) -> None:
        alive = [p for p in self.players if p.is_alive]
        if len(alive) <= 1:
            self.state = State.COMPLETE
            for p in alive:
                p.set_tag(GameTag.PLAYSTATE, PlayState.WON)

    # ── Representation ──

    def __repr__(self) -> str:
        return f"<Game turn={self.turn} step={self.step.name} players={len(self.players)}>"

    # ── Game Runner ──

    def run_turn(self) -> None:
        """Execute one complete game turn: recruit → combat → check deaths."""
        if self.state != State.RUNNING:
            return
        # _start_recruit_phase is called by _end_combat_phase or start_game
        if self.turn == 0:
            self._start_recruit_phase()
        self._auto_recruit_actions()
        self.end_recruit_phase()
        # _end_combat_phase → _check_game_over → _start_recruit_phase (next turn)

    def _auto_recruit_actions(self) -> None:
        """Auto-play recruit phase actions for all alive players.

        For each alive player, attempts to:
        1. Spend gold on the best available minion in tavern
        2. Use hero power if affordable
        3. Upgrade tavern if affordable and beneficial

        Auto-resolves any pending TargetedAction with random selection,
        since heuristic players don't have target preferences.
        """
        import random

        for p in self.players:
            if not p.is_alive:
                continue
            self.active_player = p
            self._auto_player_turn(p)
            self.resolve_queue()
            # Auto-resolve any pending targeted actions randomly
            while self.has_pending_target(p):
                self.auto_resolve_pending_target(p)
            # Auto-resolve pending discover/choice randomly for heuristic players
            choice = self.get_pending_choice(p)
            while choice is not None:
                self.resolve_pending_choice(self.rng.randrange(len(choice.options)), p)
                choice = self.get_pending_choice(p)

    def resolve_pending_choice(self, index: int, player: Optional[Player] = None) -> None:
        """Resolve the current PendingChoice with the given option index.
        Called by the RL agent (or heuristic bot) to make a discover selection.
        """
        player = player or self.active_player
        choice = self.get_pending_choice(player)
        if choice is None:
            return
        player = player or choice.player
        choice.resolve(index, self)
        self._pending_choices.pop(player, None)
        self.resolve_queue()

    @staticmethod
    def _board_score(board: list, player: Optional[Player] = None) -> int:
        """Total stats score: sum of (atk + health), plus trinket/aura bonuses."""
        base = sum(m.atk + m.health for m in board)
        if player is None:
            return base
        # Add aura bonuses from hero powers and trinkets
        bonus = 0
        for m in board:
            a, h = player.get_global_aura_bonus(m)
            bonus += a + h
        return base + bonus

    def _auto_player_turn(self, player: Player) -> None:
        """Greedy Q-score heuristic: for every affordable minion, evaluate the
        board after buying + playing it. Pick the action that gives the highest
        total board stats. When board is full, consider selling the weakest
        minion to make room if it yields a net stat gain and gold >= 3."""
        from hsrl.core.actions import SpendGold, UpgradeTavern

        # ── Trinket selection: score and buy best affordable trinket ──
        if player._pending_trinket_offers:
            offers = player._pending_trinket_offers
            best_idx = max(
                range(len(offers)),
                key=lambda i: self._score_trinket_for_player(offers[i], player)
            )
            self.buy_trinket(player, best_idx)

        max_attempts = 30
        attempts = 0

        def _minion_score(m):
            a, h = player.get_global_aura_bonus(m)
            return m.atk + m.health + a + h

        # Target tier by turn: standard Battlegrounds leveling curve.
        # Reach tier 2 by turn 3, tier 3 by turn 5, tier 4 by turn 7, etc.
        # Small random offset per player for diversity (some greed, some aggro).
        _BASE_TARGET = {1:1, 2:1, 3:2, 4:2, 5:3, 6:3, 7:4, 8:4, 9:5, 10:5, 11:6}
        target_tier = _BASE_TARGET.get(self.turn, 6)

        while player.gold > 0 and attempts < max_attempts:
            attempts += 1

            board = player.get_board_minions()
            current_score = self._board_score(board, player)
            upgrade_cost = player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)

            # ── Upgrade priority: if behind curve and can afford it ──
            if (player.gold >= upgrade_cost and player.tavern_tier < 6
                    and player.tavern_tier < target_tier):
                self.queue_action(UpgradeTavern(player))
                self.resolve_queue()
                continue

            # ── If board full, sell weakest if it frees gold for a buy ──
            if len(board) >= 7 and player.gold >= 1:
                weakest = min(board, key=_minion_score)
                projected_gold = player.gold + 1
                if projected_gold >= 3:
                    self.sell_minion(player, weakest)
                    board = player.get_board_minions()
                    current_score = self._board_score(board, player)
                    if player.gold <= 0:
                        break
                    continue  # Re-evaluate after selling

            # ── Evaluate every affordable tavern minion ──
            affordable = [m for m in player.tavern
                          if not m.dead and m.get_tag(GameTag.CARDTYPE, CardType.INVALID) == CardType.MINION
                          and m.get_tag(GameTag.COST, 3) <= player.gold
                          and len(player.hand) < MAX_HAND_SIZE]

            best_score = current_score
            best_action = None  # (action_type, buy_target, replace_target)

            if affordable:
                for candidate in affordable:
                    ca, ch = player.get_global_aura_bonus(candidate)
                    cand_score = candidate.atk + candidate.health + ca + ch

                    if len(board) < 7:
                        score = current_score + cand_score
                        if score > best_score:
                            best_score = score
                            best_action = ("buy_play", candidate, None)
                    else:
                        weakest = min(board, key=_minion_score)
                        wa, wh = player.get_global_aura_bonus(weakest)
                        weakest_score = weakest.atk + weakest.health + wa + wh
                        net_change = cand_score - weakest_score
                        if net_change > 0:
                            score = current_score + net_change
                            if score > best_score:
                                best_score = score
                                best_action = ("sell_buy_play", candidate, weakest)

            # ── Evaluate affordable tavern spells ──
            affordable_spells = [m for m in player.tavern
                                 if not m.dead and m.get_tag(GameTag.CARDTYPE, CardType.INVALID) == CardType.SPELL
                                 and m.get_tag(GameTag.COST, 0) <= player.gold
                                 and len(player.hand) < MAX_HAND_SIZE]

            for spell in affordable_spells:
                spell_cost = spell.get_tag(GameTag.COST, 0)
                spell_score = self._estimate_spell_value(spell, player, board, current_score)
                if spell_score > best_score:
                    best_score = spell_score
                    best_action = ("buy_play_spell", spell, None)

            if best_action:
                action_type, buy_target, replace_target = best_action
                if action_type == "sell_buy_play":
                    self.sell_minion(player, replace_target)
                    if player.gold < buy_target.get_tag(GameTag.COST, 3):
                        continue
                if action_type == "buy_play_spell":
                    self.buy_spell(player, buy_target)
                    spell_hand = [m for m in player.hand
                                  if m.get_tag(GameTag.CARDTYPE) == CardType.SPELL]
                    if spell_hand:
                        self.play_spell(player, spell_hand[-1])
                    continue
                self.buy_minion(player, buy_target)
                minion_hand = [m for m in player.hand
                               if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
                if minion_hand and len(player.get_board_minions()) < 7:
                    self.play_minion(player, minion_hand[-1])
                continue

            # ── Fallback: upgrade tavern (when at or ahead of curve) ──
            if player.gold >= upgrade_cost and player.tavern_tier < 6:
                self.queue_action(UpgradeTavern(player))
                self.resolve_queue()
                continue

            # ── Fallback: refresh ──
            if player.gold >= 1:
                self.refresh_tavern(player)
                self.queue_action(SpendGold(player, 1))
                self.resolve_queue()
                continue

            break

        # ── Play any remaining minions from hand ──
        minion_hand = [m for m in player.hand
                       if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
        for m in minion_hand:
            if len(player.get_board_minions()) < 7:
                self.play_minion(player, m)

        # ── Play any remaining spells from hand ──
        spell_hand = [m for m in player.hand
                      if m.get_tag(GameTag.CARDTYPE) == CardType.SPELL]
        for m in spell_hand:
            self.play_spell(player, m)

    @staticmethod
    def _estimate_spell_value(spell, player, board, current_score) -> float:
        """Estimate the board score after buying and playing a tavern spell.

        For simple stat buffs, estimates the net board stat increase.
        For utility spells (gold, refresh, discover), returns a small
        positive bonus to encourage purchase.
        """
        from hsrl.core.enums import CardType
        spell_cost = spell.get_tag(GameTag.COST, 0)
        spell_name = spell.get_tag(GameTag.NAME, '')

        # ── Known buff spells: estimate +ATK/+HP to board ──
        buff_spells = {
            'Fortify': (1, 1), 'Fleeting Vigor': (2, 2),
            'Them Apples': (1, 2), 'Azerite Empowerment': (4, 4),
            'Sacred Gift': (5, 5), 'Corrupted Cupcakes': (3, 2),
            "Saloons Finest": (0, 0),  # Tavern buff, skip
        }
        if spell_name in buff_spells:
            atk_bonus, hp_bonus = buff_spells[spell_name]
            board_size = len(board)
            if board_size > 0:
                return current_score + (atk_bonus + hp_bonus) * min(board_size, 4)
            return current_score

        # ── Tavern buff spells (buff minions in tavern) ──
        tavern_buff_spells = {"Shiny Ring", "Might of Stormwind", "Conflagration",
                              "Easterly Winds", "Saloons Finest", "Time Management"}
        if spell_name in tavern_buff_spells:
            return current_score + 2  # Small bonus for future value

        # ── Gold spells: value = gold gained - cost ──
        gold_spells = {'Gain Gold', 'Overconfidence', 'Staff of Enrichment',
                       'Careful Investment', 'Borrowed Rope', 'Brilliant Deal'}
        if spell_name in gold_spells or 'Gold' in spell_name:
            gold_gain = {'Gain Gold': 2, 'Overconfidence': 3,
                         'Staff of Enrichment': 2}.get(spell_name, 2)
            return current_score + (gold_gain - spell_cost) * 2

        # ── Discover/Get spells: modest value from card generation ──
        discover_spells = {'Recruit a Trainee', 'Hasty Excavation', 'A New Sprout',
                           'Portal in a Fountain', 'Portal in a Crystal',
                           'Chefs Choice', 'Leaf Through Pages', 'Planar Telescope',
                           'Cloning Conch', 'Spitescale Special'}
        if spell_name in discover_spells or 'Discover' in spell_name or 'Get' in spell_name:
            return current_score + 3

        # ── Default: modest positive value for unknown spells, encourages trying ──
        return current_score + 1

    def run_full_game(self, max_turns: int = 50) -> Optional[Player]:
        """Run a complete Battlegrounds game simulation.
        Returns the winning player, or None if max_turns exceeded.
        If all players die simultaneously, the one with highest HP wins.
        """
        if self.state != State.RUNNING:
            self.start_game()

        while self.state == State.RUNNING:
            self.run_turn()
            alive = [p for p in self.players if p.is_alive]
            if len(alive) == 1:
                self.state = State.COMPLETE
                return alive[0]
            if len(alive) == 0:
                # All died simultaneously — highest HP before death wins
                self.state = State.COMPLETE
                return max(self.players, key=lambda p: (
                    p.health, p.tavern_tier, len([m for m in p.board if not m.dead])))
            if self.turn >= max_turns:
                self.state = State.COMPLETE
                return max(alive, key=lambda p: p.health)
        alive = [p for p in self.players if p.is_alive]
        return alive[0] if len(alive) == 1 else None

    @staticmethod
    def create_game(hero_ids: List[str], card_db=None, apply_anomaly: bool = True,
                    hero_power_overrides: Dict[int, str] = None,
                    seed: int = None) -> "Game":
        """Factory: create a Game with players from hero card IDs.

        Args:
            hero_ids: List of hero card IDs (e.g. ['BG20_HERO_100', ...])
            card_db: CardDB instance (uses global CARDS if None)
            apply_anomaly: Whether to apply a random anomaly
            hero_power_overrides: Optional dict mapping player index to
                hero power card_id override (for start-of-game choice)
            seed: Random seed for deterministic replay

        Returns:
            Initialized Game ready to start.
        """
        # A formal match may only start from the checked-in, content-addressed
        # patch closure. The default validation is cached after the first
        # successful check in a process.
        from hsrl.runtime_version import RuntimeVersionError, validate_runtime_manifest
        runtime = validate_runtime_manifest()

        from hsrl.core.card_db import CARDS
        db = card_db or CARDS
        unsupported_powers = set(
            runtime.get("unsupported_runtime_entities", {}).get("hero_powers", [])
        )
        for hero_id in hero_ids:
            hero_data = db.get(hero_id)
            power_id = hero_data.tags.get(GameTag.HERO_POWER) if hero_data else None
            if power_id in unsupported_powers:
                raise RuntimeVersionError(
                    f"hero {hero_id} uses unsupported version-correct power {power_id}; "
                    "formal match start refused"
                )
        game = Game([], seed=seed)
        game.card_db = db
        game.init_pool()

        players = []
        for hid in hero_ids:
            p = game.create_player(hid)
            players.append(p)
        game.players = players
        for p in players:
            p.game = game

        # Apply hero power overrides before start_game (start-of-game choice)
        if hero_power_overrides:
            for idx, power_id in hero_power_overrides.items():
                if 0 <= idx < len(players):
                    players[idx].set_tag(GameTag.HERO_POWER, power_id)

        if not apply_anomaly:
            game.active_anomaly = True  # Block anomaly application

        game.start_game()
        return game

    @staticmethod
    def run_game(hero_ids: List[str], card_db=None, max_turns: int = 50) -> "Game":
        """Convenience: create and run a full game. Returns the completed Game object."""
        game = Game.create_game(hero_ids, card_db)
        game.run_full_game(max_turns)
        return game


# ── TYPE_CHECKING helpers ──
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hsrl.core.entity import BaseEntity
    from hsrl.core.events import EventListener
