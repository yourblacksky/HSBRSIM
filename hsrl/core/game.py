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
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from hsrl.core.enums import CardType, GameTag, PlayState, Race, State, Step, Zone
from hsrl.core.entity import CardData
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

    def __init__(self, players: List[Player], card_db=None):
        self.players = players
        self.card_db = card_db
        self.turn: int = 0
        self.step: Step = Step.INVALID
        self.state: State = State.INVALID
        self._action_queue: List[Tuple[Action, BaseEntity, Optional[BaseEntity]]] = []
        self._event_listeners: List[Tuple[BaseEntity, EventListener]] = []
        self._next_entity_id = 1
        self._last_attack_target: Optional["Minion"] = None
        self._last_defender: Optional[Player] = None  # Last defender in combat (for tiebreaker)
        self._deferred_actions: List[Tuple[Player, Action]] = []
        self._turn_schedule: dict = {}   # turn → list of callbacks
        self._combat_death_log: List[Minion] = []
        self.in_combat: bool = False
        self.active_player: Optional[Player] = None  # Current active player during recruit
        self.minion_pool = None  # Lazy init via init_pool()
        self.spell_pool = None   # Lazy init via init_pool()
        self.active_anomaly = None  # Optional Anomaly entity (game-wide modifier)

        for p in self.players:
            p.game = self

    def init_pool(self) -> None:
        """Initialize the shared minion and spell pools. Call after card_db is set."""
        from hsrl.core.minion_pool import MinionPool
        from hsrl.core.spell_pool import SpellPool
        self.minion_pool = MinionPool(self.card_db)
        self.spell_pool = SpellPool(self.card_db)

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
            drawn = self.minion_pool.draw(6, count=count)
        elif anomaly_allowed_tiers:
            # Anomaly tier filter: only draw minions of allowed tiers
            allowed = set(anomaly_allowed_tiers)
            max_tier = min(max(allowed), player.tavern_tier)
            drawn = self.minion_pool.draw(max_tier, count=count * 3)
            # Filter to only allowed tiers
            drawn = [m for m in drawn if m.data.tech_level in allowed][:count]
        elif hasattr(player, '_tavern_min_tier') and player._tavern_min_tier > 1:
            # Player-level tier filter (e.g. Bob-blehead trinket: no tier 1-2)
            min_t = player._tavern_min_tier
            drawn = self.minion_pool.draw(tavern_tier, count=count, min_tier=min_t)
        elif (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)
                and getattr(self.active_anomaly, '_only_current_tier', False)):
            drawn = self.minion_pool.draw(player.tavern_tier, count=count,
                                          min_tier=player.tavern_tier)
        else:
            drawn = self.minion_pool.draw(tavern_tier, count=count)
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
        cost = minion.get_tag(GameTag.COST, 3)
        # Anomaly: minions cost equals their tier (No Tier 1, cost = tier)
        anomaly = self.active_anomaly
        if anomaly is not None and not isinstance(anomaly, bool):
            if getattr(anomaly, '_cost_equals_tier', False):
                cost = minion.data.tech_level
            if getattr(anomaly, '_minions_cost_2', False):
                cost = 2
        # Electrode Attractor: magnetic mechs cost (2)
        if minion.has_tag(GameTag.MAGNETIC) and player.get_tag(GameTag.MAGNETIC_COST_OVERRIDE, 0) > 0:
            cost = player.get_tag(GameTag.MAGNETIC_COST_OVERRIDE)
        # Pilgrimp Sticker: one demon per turn buyable with health
        health_cost_demon = (player.get_tag(GameTag.HEALTH_COST_DEMON, 0) > 0
                             and minion.has_tag(GameTag.RACE) and minion.race == Race.DEMON)
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
        if len(player.hand) >= MAX_HAND_SIZE:
            # Hand is full — minion is removed from tavern but not added to hand
            minion.zone = Zone.REMOVED
            self.resolve_queue()
            return
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
        if len(player.hand) >= MAX_HAND_SIZE:
            spell.zone = Zone.REMOVED
            self.resolve_queue()
            return
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
        # Return 1 Gold
        self.queue_action(GainGold(player, 1))
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
        data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'bg_cards.json')
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
                race_val = c.get('card_race', 0) or 0
                try:
                    race = Race(race_val)
                except (ValueError, NameError):
                    race = Race.INVALID
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

    def broadcast(self, event_name: str, *args) -> None:
        """Broadcast an event to all registered listeners.
        The first positional arg (if any BaseEntity) is passed as target to the action trigger.
        """
        to_remove = []
        for entity, listener in self._event_listeners:
            if listener.check(event_name, args):
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
        """Return all living enemy minions across all opponents.
        For 1v1 combat simulation this returns the specific opponent's board."""
        # In full 8-player, this would need matchup info. For now, return all non-player boards.
        enemies = []
        for p in self.players:
            if p is player:
                continue
            if p.is_alive:
                enemies.extend(p.get_board_minions())
        return enemies

    def get_opponent(self, player: Player) -> Optional[Player]:
        """Get the current combat opponent.
        In full game this would use matchup system; here we pick a random alive opponent."""
        candidates = [p for p in self.players if p is not player and p.is_alive]
        if not candidates:
            return None
        return random.choice(candidates)

    # ── Summoning ──

    def summon(self, player: Player, minion: Minion, position: Optional[int] = None) -> None:
        """Put a minion onto a player's board."""
        if len(player.board) >= 7:
            # Board is full; minion is not summoned (standard BG rule)
            return
        minion.controller = player
        minion.zone = Zone.PLAY
        if position is None or position > len(player.board):
            position = len(player.board)
        player.board.insert(position, minion)
        self._update_zone_positions(player.board)
        # Trigger on_summon script (for registering event listeners)
        on_summon_action = minion.on_summon
        if on_summon_action:
            self.queue_action(on_summon_action, source=minion)
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
            player.hand.remove(minion)
            from hsrl.core.actions import AttachMagnetic
            self.queue_action(AttachMagnetic(minion, magnetic_target))
            self.resolve_queue()
            return

        if len(player.board) >= 7:
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
        """
        card_id = entity.get_tag(GameTag.CARD_ID)
        if not card_id:
            return
        if entity.is_golden:
            return

        copies = []
        for m in player.hand + player.board:
            if m.uuid == entity.uuid:
                continue
            if m.is_golden:
                continue
            if m.get_tag(GameTag.CARD_ID) == card_id:
                copies.append(m)

        # Designer Eyepatch: pirates only need 2 copies (entity + 1 other)
        need_copies = 1 if (player.get_tag(GameTag.PIRATES_NEED_2_COPIES) and
                            entity.race == Race.PIRATE) else 2
        if len(copies) >= need_copies:
            self._combine_triple(player, [entity] + copies[:need_copies])

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

    def _grant_triple_reward(self, player: Player, golden) -> None:
        """Grant a Triple Reward Discover when a golden minion is played.

        Discovers a minion from the reward tier (tier+1 of the original,
        capped at 6). Clears TRIPLE_REWARD_TIER after use.
        """
        from hsrl.core.actions import DiscoverMinion

        reward_tier = golden.get_tag(GameTag.TRIPLE_REWARD_TIER,
                                     golden.tech_level + 1)
        golden.set_tag(GameTag.TRIPLE_REWARD_TIER, 0)

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
        for p in self.players:
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

            # Trigger deathrattle
            dr = m.deathrattle
            if dr:
                self.broadcast(DEATHRATTLE_TRIGGER, m)
                if isinstance(dr, (list, tuple)):
                    for action in dr:
                        self.queue_action(action, source=m)
                else:
                    self.queue_action(dr, source=m)

            # Trigger Reborn
            if m.reborn and not m.has_tag(GameTag.REBORN_USED):
                from hsrl.core.actions import Reborn
                self.queue_action(Reborn(m), source=m)

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
        """Process queued actions. _wave tracks death processing depth."""
        while self._action_queue:
            if _total_actions >= self._MAX_ACTIONS_PER_RESOLVE:
                return
            action, source, target = self._action_queue.pop(0)
            action.trigger(source, self, target)
            _total_actions += 1
            self._check_deaths(_wave, _total_actions)

    def resolve_queue(self) -> None:
        """Public entry point — process all queued actions."""
        self._resolve_queue(0)

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

        An anomaly modifies global game rules. Pick one at random from card_db
        and trigger its on_apply script.
        """
        if self.active_anomaly is not None:
            return

        from hsrl.core.anomaly import Anomaly

        available_ids = [
            cid for cid, data in self.card_db._cards.items()
            if data.cardtype == CardType.ANOMALY
        ]
        if not available_ids:
            return

        import random
        anomaly_id = random.choice(available_ids)
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

    def _offer_trinkets(self, player: Player) -> None:
        """Offer trinkets to a player on Turn 6 (Lesser) and Turn 9 (Greater).

        Trinkets are passive items that occupy one of two slots:
          - TRINKET_1 (Lesser, Turn 6)
          - TRINKET_2 (Greater, Turn 9)

        Offering rules:
          - Detect dominant tribe(s) on board to bias trinket selection
          - Offer 1-3 trinkets; player auto-picks one in RL mode
          - At least one trinket has cost <= 2
        """
        from hsrl.core.trinket import Trinket

        trinket_slot = GameTag.TRINKET_1 if self.turn == 6 else GameTag.TRINKET_2
        # Skip if slot already filled or trinkets already offered
        if player.has_tag(trinket_slot):
            return
        if player.has_tag(GameTag.TRINKET_OFFERED):
            return
        player.set_tag(GameTag.TRINKET_OFFERED, True)

        # Collect available trinkets from card_db
        available_ids = [
            cid for cid, data in self.card_db._cards.items()
            if data.cardtype == CardType.TRINKET
        ]
        if not available_ids:
            return

        # Pick 2-3 random trinkets (simplified RL selection)
        import random
        count = min(3, len(available_ids))
        offered = random.sample(available_ids, count)

        # Auto-select the first trinket (simplified)
        chosen_id = offered[0]
        trinket_data = self.card_db.get(chosen_id)
        trinket = Trinket(trinket_data, game=self)
        trinket.controller = player
        cost = trinket.cost
        if player.gold >= cost:
            from hsrl.core.actions import SpendGold
            self.queue_action(SpendGold(player, cost))
        player.trinkets.append(trinket)
        player.set_tag(trinket_slot, True)

        # Register trinket event listeners if it has a script
        if trinket_data.scripts:
            if hasattr(trinket_data.scripts, 'start_of_combat'):
                pass  # Handled via _trigger_start_of_combat
            # Register on_buy/avenge/etc. listeners as needed
            fn = getattr(trinket_data.scripts, 'on_summon', None)
            if fn and callable(fn):
                fn(trinket, self)

        self.broadcast("TRINKET_OFFERED", player, chosen_id)
        self.resolve_queue()

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
        quest_id = random.choice(available_ids)
        reward_id = random.choice(reward_ids)

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
        self.broadcast(RECRUIT_BEGIN, self.turn)
        self.broadcast("TURN_BEGIN", self.turn)
        for p in self.players:
            if not p.is_alive:
                continue
            # Dispatch trinket on_turn_begin (for every-N-turns counters)
            self._dispatch_trinket_event(p, "on_turn_begin")
            # Reset hero power usage
            p.set_tag(GameTag.HERO_POWER_USED, False)
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
            # Gold carryover: unspent gold carries to next turn (BG27_Anomaly_002)
            if (self.active_anomaly is not None
                    and hasattr(self.active_anomaly, '_gold_carryover')):
                unspent = p.get_tag(GameTag.GOLD, 0)
                gold_gained += unspent
                if unspent >= 5:
                    gold_gained += 1  # bonus for keeping 5+
            p.set_tag(GameTag.GOLD, gold_gained)
            # Reduce tavern upgrade cost by 1 (if not already 0)
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

    def end_recruit_phase(self) -> None:
        # ── Trigger End of Turn effects BEFORE combat ──
        self._trigger_end_of_turn()
        self.resolve_queue()
        # ── Clear "this turn only" temporary buffs from minions ──
        self._clear_temporary_buffs()
        # ── Clear "until next turn" temporary deathrattles ──
        self._clear_temporary_deathrattles()
        # ── Clear unused Spellcraft spells from hand ──
        self._cleanup_spellcraft_spells()
        self.broadcast("TURN_END", self.turn)
        self.broadcast(RECRUIT_END, self.turn)
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

    def _start_combat_phase(self) -> None:
        self.step = Step.COMBAT
        self.broadcast(COMBAT_BEGIN, self.turn)

        # Pair up players for combat (simplified: random pairs)
        alive_players = [p for p in self.players if p.is_alive]
        random.shuffle(alive_players)

        # Simple pairing: if odd number, one player faces a ghost (not implemented)
        for i in range(0, len(alive_players), 2):
            p1 = alive_players[i]
            p2 = alive_players[i + 1] if i + 1 < len(alive_players) else None
            if p2:
                self._run_combat(p1, p2)

        self._end_combat_phase()

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
            if random.choice([True, False]):
                attacker_side, defender_side = board_a, board_b
                attacker_player, defender_player = player_a, player_b
            else:
                attacker_side, defender_side = board_b, board_a
                attacker_player, defender_player = player_b, player_a

        # Combat loop
        round_limit = 1000  # Prevent infinite loops
        for _ in range(round_limit):
            # Get next attacker from attacker_side
            attacker = self._get_next_attacker(attacker_side)
            if attacker is None:
                break

            # Choose target from defender_side
            target = self._choose_attack_target(defender_side)
            if target is None:
                break

            from hsrl.core.actions import Attack
            self.queue_action(Attack(attacker, target))
            self.resolve_queue()

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

    def _get_next_attacker(self, board: List[Minion]) -> Optional[Minion]:
        """Get the leftmost living minion that can attack."""
        for m in board:
            if not m.dead and m.can_attack:
                return m
        return None

    def _choose_attack_target(self, board: List[Minion]) -> Optional[Minion]:
        """Choose a random target, respecting Taunt."""
        living = [m for m in board if not m.dead]
        if not living:
            return None
        taunts = [m for m in living if m.taunt]
        if taunts:
            return random.choice(taunts)
        return random.choice(living)

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
        self.broadcast(START_OF_COMBAT, player)

        # Priority 0: Anomaly Start of Combat effects (global, once per combat)
        if (self.active_anomaly is not None
                and not isinstance(self.active_anomaly, bool)
                and self.active_anomaly.data
                and self.active_anomaly.data.scripts):
            soc = getattr(self.active_anomaly.data.scripts, 'start_of_combat', None)
            if soc and callable(soc):
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
        """Deal damage to the losing player based on surviving minions.
        If both boards are empty (draw), the defender takes 1 damage (tiebreaker).
        """
        living1 = [m for m in board1 if not m.dead]
        living2 = [m for m in board2 if not m.dead]

        if living1 and not living2:
            winner, loser = p1, p2
            survivors = living1
        elif living2 and not living1:
            winner, loser = p2, p1
            survivors = living2
        else:
            # Draw — both boards empty or both have survivors
            # Tiebreaker: defender takes 1 damage (last attacker wins)
            if self._last_defender is not None:
                self._deal_player_damage(self._last_defender, 1)
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
                    and damage >= player.health):
                player.health = 1  # survive at 1 HP
                next_turn = self.turn + 1
                p_ref = player
                self.schedule_turn_action(next_turn,
                    lambda g, t: g.queue_action(GainGold(p_ref, 11)))
                return
            player.health -= damage
        if player.health <= 0:
            player.set_tag(GameTag.PLAYSTATE, PlayState.LOST)
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
                p._buddy_card_id = random.choice(buddy_pool)

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
        """
        for p in self.players:
            if not p.is_alive:
                continue
            self.active_player = p
            self._auto_player_turn(p)
            self.resolve_queue()

    def _auto_player_turn(self, player: Player) -> None:
        """Auto-play one player's recruit phase using a simple heuristic."""
        max_attempts = 20
        attempts = 0
        while player.gold > 0 and attempts < max_attempts:
            attempts += 1
            # Priority 1: Buy best affordable minion
            affordable = [m for m in player.tavern
                          if not m.dead and m.get_tag(GameTag.COST, 3) <= player.gold]
            if affordable and len(player.hand) < MAX_HAND_SIZE:
                best = max(affordable, key=lambda m: m.atk + m.health)
                self.buy_minion(player, best)
                # Play minion from hand immediately after buying
                minion_hand = [m for m in player.hand
                               if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
                if minion_hand and len(player.board) < 7:
                    self.play_minion(player, minion_hand[0])
                continue

            # Priority 2: Upgrade tavern
            upgrade_cost = player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
            if player.gold >= upgrade_cost and player.tavern_tier < 6:
                from hsrl.core.actions import UpgradeTavern
                self.queue_action(UpgradeTavern(player))
                self.resolve_queue()
                continue

            # Priority 3: Refresh
            if player.gold >= 1:
                self.refresh_tavern(player)
                from hsrl.core.actions import SpendGold
                self.queue_action(SpendGold(player, 1))
                self.resolve_queue()
                continue

            break  # Nothing more to do

        # Play any remaining minions from hand
        minion_hand = [m for m in player.hand
                       if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
        for m in minion_hand:
            if len(player.board) < 7:
                self.play_minion(player, m)

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
    def create_game(hero_ids: List[str], card_db=None, apply_anomaly: bool = True) -> "Game":
        """Factory: create a Game with players from hero card IDs.

        Args:
            hero_ids: List of hero card IDs (e.g. ['BG20_HERO_100', ...])
            card_db: CardDB instance (uses global CARDS if None)
            apply_anomaly: Whether to apply a random anomaly

        Returns:
            Initialized Game ready to start.
        """
        from hsrl.core.card_db import CARDS
        db = card_db or CARDS
        game = Game([])
        game.card_db = db
        game.init_pool()

        players = []
        for hid in hero_ids:
            p = game.create_player(hid)
            players.append(p)
        game.players = players
        for p in players:
            p.game = game

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
