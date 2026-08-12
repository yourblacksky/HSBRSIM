"""
HSRL Action System

Every state change in the game is represented as an Action.
Actions are queued and resolved by the Game engine.
This follows the philosophy that all mechanics must go through a standardized pipeline.

Pattern:
    Action -> queue -> broadcast events -> resolve -> trigger follow-ups
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union, TYPE_CHECKING
from hsrl.core.enums import CardType, GameTag, KEYWORD_TAGS, Race, Zone
from hsrl.core.events import GOLD_SPENT, BATTLECRY_TRIGGER, TAVERN_SPELL_CAST

if TYPE_CHECKING:
    from hsrl.core.entity import BaseEntity
    from hsrl.core.game import Game
    from hsrl.core.player import Player
else:
    BaseEntity = object
    Game = object
    Player = object


# ── Utility Functions ──

def get_adjacent_minions(board: list, minion: "BaseEntity") -> tuple:
    """Return (left, right) neighbors of a minion on a board.

    Excludes dead minions. Returns None for positions without valid neighbors.
    Extracted from Cleave logic in Attack.do() so other systems can reuse it.
    """
    if minion not in board:
        return None, None
    pos = board.index(minion)
    left = board[pos - 1] if pos > 0 and not board[pos - 1].dead else None
    right = board[pos + 1] if pos + 1 < len(board) and not board[pos + 1].dead else None
    return left, right


MAX_HAND_SIZE = 10


class Action:
    """Base class for all game actions."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self._then: List[Action] = []   # Chain actions

    def then(self, *actions: Action) -> Action:
        """Chain additional actions to run after this one succeeds."""
        self._then.extend(actions)
        return self

    def trigger(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        """Execute the action and any chained actions."""
        self.do(source, game, target)
        for action in self._then:
            action.trigger(source, game, target)

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        """Override in subclasses."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.args})"


# ── Core Game Actions ──

class Attack(Action):
    """
    A minion attacks a target.
    In Battlegrounds, targeting is random (except Taunt priority).
    """

    def __init__(self, attacker: BaseEntity, defender: BaseEntity):
        super().__init__()
        self.attacker = attacker
        self.defender = defender

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.attacker.dead or self.defender.dead:
            return
        if self.attacker.atk <= 0:
            return

        game.broadcast("BEFORE_ATTACK", self.attacker, self.defender)

        # ── MINION_ATTACKED for on-attack effects (Roaring Recruiter, Ring Bearer) ──
        game.broadcast("MINION_ATTACKED", self.attacker, self.defender)
        if self.attacker.controller is not None:
            game._dispatch_trinket_event(self.attacker.controller, "on_friendly_attack",
                                          attacker=self.attacker)
        # ── Rally: triggers when attack is declared, before damage resolves ──
        game._last_attack_target = self.defender
        if self.attacker.has_tag(GameTag.RALLY) and not self.attacker.dead:
            rally_action = self.attacker.rally
            times = 2 if (self.attacker.controller and
                          self.attacker.controller.get_tag(GameTag.RALLY_DOUBLED, False)) else 1
            for _ in range(times):
                if rally_action:
                    if isinstance(rally_action, (list, tuple)):
                        for action in rally_action:
                            game.queue_action(action, source=self.attacker)
                    else:
                        game.queue_action(rally_action, source=self.attacker)

        # ── Attacker deals damage ──
        game.queue_action(Hit(self.defender, self.attacker.atk, source=self.attacker))

        # ── Cleave hits adjacent ──
        if self.attacker.cleave and self.defender.zone == Zone.PLAY:
            board = game.get_board(self.defender.controller)
            pos = self.defender.zone_position
            for adj in (pos - 1, pos + 1):
                if 0 <= adj < len(board):
                    adj_minion = board[adj]
                    if adj_minion and not adj_minion.dead:
                        game.queue_action(Hit(adj_minion, self.attacker.atk, source=self.attacker))

        # ── Defender retaliates (if alive and defender is a minion with >0 atk) ──
        if not self.defender.dead and hasattr(self.defender, "atk"):
            if self.defender.atk > 0:
                game.queue_action(Hit(self.attacker, self.defender.atk, source=self.defender))

        # ── Mark attacker as exhausted (unless windfury) ──
        attacks_done = self.attacker.get_tag(GameTag.WINDFURY_ATTACKS, 0) + 1
        self.attacker.set_tag(GameTag.WINDFURY_ATTACKS, attacks_done)
        if attacks_done >= (2 if self.attacker.windfury else 1):
            self.attacker.set_tag(GameTag.EXHAUSTED, True)

        game.broadcast("AFTER_ATTACK", self.attacker, self.defender)

        # Volatile Venom: minions die after attacking
        if (self.attacker.controller and
                self.attacker.controller.get_tag(GameTag.DIE_AFTER_ATTACK, False)):
            if not self.attacker.dead:
                game.queue_action(Destroy(self.attacker))


class AttackImmediately(Action):
    """A minion attacks immediately during combat, outside normal turn order.
    Used by effects like 'Summon an X that attacks immediately'
    and 'Gain Divine Shield and attack immediately'.
    """

    def __init__(self, attacker: BaseEntity):
        super().__init__()
        self.attacker = attacker

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.attacker.dead or self.attacker.atk <= 0:
            return

        # Find the enemy player for this combat pair. During full lobby combat,
        # other players' boards still exist and must not become target candidates.
        enemy = None
        if hasattr(game, "get_current_combat_opponent"):
            enemy = game.get_current_combat_opponent(self.attacker.controller)
        if enemy is None:
            return

        # Choose target respecting Taunt
        living = [m for m in enemy.board if not m.dead]
        if not living:
            return
        taunts = [m for m in living if m.taunt]
        if taunts:
            target = game.rng.choice(taunts)
        else:
            target = game.rng.choice(living)

        # Perform the attack via the standard Attack action
        game.queue_action(Attack(self.attacker, target))


class Hit(Action):
    """Deal damage to a target. Handles Divine Shield, Poisonous, etc."""

    def __init__(self, target: BaseEntity, amount: int, source: Optional[BaseEntity] = None):
        super().__init__()
        self.target = target
        self.amount = amount
        self.source = source

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return

        game.broadcast("BEFORE_HIT", self.target, self.amount, self.source)

        # ── Divine Shield blocks all damage ──
        if self.target.divine_shield:
            self.target.set_tag(GameTag.DIVINE_SHIELD, False)
            self.target.set_tag(GameTag.DIVINE_SHIELD_INTACT, False)
            game.broadcast("DIVINE_SHIELD_LOST", self.target)
            if self.target.controller is not None:
                game._dispatch_trinket_event(self.target.controller,
                                              "on_lose_divine_shield", minion=self.target)
            # Poisonous does NOT trigger through Divine Shield (no damage dealt)
            return

        # ── Apply damage ──
        old_health = self.target.health
        self.target.health = max(0, self.target.health - self.amount)
        actual_damage = old_health - self.target.health

        if actual_damage > 0:
            game.broadcast("DAMAGE", self.target, actual_damage, self.source)
            # Emit MINION_DAMAGED for on-damage-taken effects (Winterfinner, Trigore, etc.)
            if self.target.get_tag(GameTag.CARDTYPE) == CardType.MINION:
                game.broadcast("MINION_DAMAGED", self.target, actual_damage, self.source)
            # Trinket: on_friendly_damage dispatch
            if self.target.controller is not None:
                game._dispatch_trinket_event(self.target.controller, "on_friendly_damage",
                                             minion=self.target, amount=actual_damage)

        # ── Track killer: if damage kills the target, record attacker ──
        if self.target.health <= 0 and self.source:
            self.target.set_tag(GameTag.KILLER, self.source.entity_id)

        # ── Poisonous: kill immediately if damage was dealt ──
        if self.source and self.source.poisonous and actual_damage > 0:
            self.target.set_tag(GameTag.DEAD, True)
            self.target.health = 0
            game.broadcast("POISON_KILL", self.target, self.source)

        # ── Venomous: kill if source survives ──
        if self.source and self.source.venomous and actual_damage > 0:
            if not self.source.dead:
                self.target.set_tag(GameTag.DEAD, True)
                self.target.health = 0
                game.broadcast("VENOM_KILL", self.target, self.source)
                self.source.set_tag(GameTag.VENOMOUS, False)
                game.broadcast("KEYWORD_LOST", self.source, GameTag.VENOMOUS)

        game.broadcast("AFTER_HIT", self.target, actual_damage, self.source)


class Heal(Action):
    """Restore health to a target."""

    def __init__(self, target: BaseEntity, amount: int):
        super().__init__()
        self.target = target
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        old_health = self.target.health
        self.target.health = min(self.target.max_health, self.target.health + self.amount)
        actual_heal = self.target.health - old_health
        if actual_heal > 0:
            game.broadcast("HEAL", self.target, actual_heal)


class Buff(Action):
    """Apply a stat buff (+atk/+health) to a target."""

    def __init__(self, target: BaseEntity, atk: int = 0, health: int = 0,
                 temporary: bool = False):
        super().__init__()
        self.target = target
        self.atk = atk
        self.health = health
        self.temporary = temporary

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        if self.target.dead:
            return
        atk = self.atk
        health = self.health
        # Elemental buff bonus: Sand Swirler / Glowing Cinder
        if (hasattr(source, 'race') and source.race == Race.ELEMENTAL
                and hasattr(source, 'controller') and source.controller):
            ctrl = source.controller
            atk += ctrl.tags.get(GameTag.ELEMENTAL_BUFF_BONUS_ATK, 0)
            health += ctrl.tags.get(GameTag.ELEMENTAL_BUFF_BONUS_HEALTH, 0)
        buff = BuffEnchantment(atk=atk, health=health,
                               temporary=self.temporary)
        self.target.add_buff(buff)
        game.broadcast("BUFF", self.target, atk, health)


class ApplyGlobalAura(Action):
    """Apply a persistent global aura to all matching minions controlled by a player.

    Unlike Buff (one-shot per-minion), this aura persists for the entire game
    and automatically applies to minions summoned later, including those in hand.
    """

    def __init__(self, player: "Player", atk: int = 0, health: int = 0,
                 race_filter=None):
        super().__init__()
        self.player = player
        self.atk = atk
        self.health = health
        self.race_filter = race_filter

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        aura = GlobalAura(atk=self.atk, health=self.health, race_filter=self.race_filter)
        self.player.auras.append(aura)
        game.broadcast("GLOBAL_AURA_APPLIED", self.player, aura)


class Summon(Action):
    """Summon a minion onto a player's board."""

    def __init__(self, player: Player, minion: BaseEntity, position: Optional[int] = None):
        super().__init__()
        self.player = player
        self.minion = minion
        self.position = position

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        game.summon(self.player, self.minion, position=self.position)


class CloneMinion(Action):
    """Create an exact copy of a minion (deep-copied stats, buffs, enchants).

    Used by Archlich Kel'Thuzad and similar "resummon an exact copy" effects.
    After creation, self.clone holds the new minion; caller chains Summon.
    """

    def __init__(self, original: BaseEntity):
        super().__init__()
        self.original = original
        self.clone = None

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.original.dead:
            return
        import copy as _copy
        clone = game.create_minion(self.original.data.id)
        if clone is None:
            return
        # Copy mutable state (deep copy so clone has independent state)
        clone.tags = _copy.deepcopy(self.original.tags)
        clone._buffs = _copy.deepcopy(self.original._buffs)
        if hasattr(self.original, '_script_overrides'):
            clone._script_overrides = _copy.deepcopy(self.original._script_overrides)
        # Clear event listeners — they reference the original and must be
        # re-registered when the clone is summoned.
        clone._events = []
        self.clone = clone


class Destroy(Action):
    """Play a minion from hand to the board during recruit phase."""

    def __init__(self, player: Player, minion: BaseEntity, position: Optional[int] = None):
        super().__init__()
        self.player = player
        self.minion = minion
        self.position = position

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        game.play_minion(self.player, self.minion, position=self.position)


class Destroy(Action):
    """Destroy (kill) a minion. Triggers deathrattle."""

    def __init__(self, target: BaseEntity):
        super().__init__()
        self.target = target

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        self.target.set_tag(GameTag.DEAD, True)
        self.target.health = 0
        game.broadcast("BEFORE_DESTROY", self.target)
        # Death processing is handled by game.process_deaths()


class RemoveMinion(Action):
    """Remove a minion from play (to graveyard or setaside)."""

    def __init__(self, target: BaseEntity, to_zone: Zone = Zone.GRAVEYARD):
        super().__init__()
        self.target = target
        self.to_zone = to_zone

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        old_zone = self.target.zone
        self.target.zone = self.to_zone
        self.target.set_tag(GameTag.ZONE_POSITION, 0)
        game.broadcast("ZONE_CHANGE", self.target, old_zone, self.to_zone)


class Reborn(Action):
    """Resummon a minion with 1 health (Reborn mechanic)."""

    def __init__(self, target: BaseEntity):
        super().__init__()
        self.target = target

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if not self.target.reborn or self.target.has_tag(GameTag.REBORN_USED):
            return

        # Create a fresh copy without Reborn
        new_minion = game.create_minion(self.target.data.id)
        new_minion.controller = self.target.controller
        new_minion.set_tag(GameTag.REBORN, False)
        new_minion.set_tag(GameTag.REBORN_USED, True)
        new_minion.set_tag(GameTag.HEALTH, 1)
        new_minion.set_tag(GameTag.MAX_HEALTH, 1)
        new_minion.set_tag(GameTag.BASE_HEALTH, 1)

        position = self.target.zone_position
        game.summon(self.target.controller, new_minion, position=position)
        game.broadcast("REBORN_TRIGGER", self.target, new_minion)


class GainKeyword(Action):
    """Grant a keyword to a minion."""

    def __init__(self, target: BaseEntity, keyword: GameTag):
        super().__init__()
        self.target = target
        self.keyword = keyword

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        self.target.set_tag(self.keyword, True)
        game.broadcast("KEYWORD_GAINED", self.target, self.keyword)


class LoseKeyword(Action):
    """Remove a keyword from a minion."""

    def __init__(self, target: BaseEntity, keyword: GameTag):
        super().__init__()
        self.target = target
        self.keyword = keyword

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        self.target.set_tag(self.keyword, False)
        game.broadcast("KEYWORD_LOST", self.target, self.keyword)


class Silence(Action):
    """Remove all keywords, buffs, script overrides, and event listeners from a minion."""

    def __init__(self, target: BaseEntity):
        super().__init__()
        self.target = target

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        if self.target.has_tag(GameTag.SILENCED):
            return  # already silenced, no-op
        # 1. Clear all keyword tags
        for kw in KEYWORD_TAGS:
            self.target.set_tag(kw, False)
        # 2. Clear buffs
        self.target.clear_buffs()
        # 3. Clear per-instance script overrides
        self.target._script_overrides.clear()
        # 4. Clear per-entity event listeners
        self.target.clear_events()
        # 5. Unregister from game-wide listener registry
        game.unregister_all_listeners_for_entity(self.target)
        # 6. Set silenced state flag
        self.target.set_tag(GameTag.SILENCED, True)
        # 7. Broadcast
        from hsrl.core.events import SILENCED
        game.broadcast(SILENCED, self.target)


class DealDamageToRandomEnemy(Action):
    """Deal damage to a random enemy minion (for effects like Kaboom Bot)."""

    def __init__(self, player: Player, amount: int, count: int = 1):
        super().__init__()
        self.player = player
        self.amount = amount
        self.count = count

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        enemies = game.get_living_enemies(self.player)
        for _ in range(self.count):
            if not enemies:
                break
            victim = game.rng.choice(enemies)
            game.queue_action(Hit(victim, self.amount, source=source))
            enemies = [e for e in enemies if not e.dead]


class AvengeIncrement(Action):
    """Increment the avenge counter for all friendly Avenge minions."""

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        board = game.get_board(self.player)
        for minion in board:
            if minion.dead:
                continue
            if minion.has_tag(GameTag.Avenge):
                counter = minion.get_tag(GameTag.AVENGE_COUNTER, 0) + 1
                target_count = minion.get_tag(GameTag.AVENGE_TARGET, 3)
                minion.set_tag(GameTag.AVENGE_COUNTER, counter)
                if counter >= target_count:
                    minion.set_tag(GameTag.AVENGE_COUNTER, 0)
                    if minion.data.scripts and hasattr(minion.data.scripts, "avenge"):
                        avenge_action = minion.data.scripts.avenge
                        if callable(avenge_action):
                            avenge_action = avenge_action(minion, game)
                        if avenge_action is not None:
                            if isinstance(avenge_action, (list, tuple)):
                                for action in avenge_action:
                                    game.queue_action(action, source=minion)
                            else:
                                game.queue_action(avenge_action, source=minion)
                    game.broadcast("AVENGE_TRIGGER", minion)
        # Trinket avenge: check player trinkets
        for trinket in self.player.trinkets:
            # Only process if trinket has avenge script and data defines avenge target
            if not trinket.data.scripts:
                continue
            if not hasattr(trinket.data.scripts, "avenge"):
                continue
            counter = trinket.get_tag(GameTag.AVENGE_COUNTER, 0) + 1
            target_count = trinket.get_tag(GameTag.AVENGE_TARGET, 3)
            trinket.set_tag(GameTag.AVENGE_COUNTER, counter)
            if counter >= target_count:
                trinket.set_tag(GameTag.AVENGE_COUNTER, 0)
                avenge_fn = trinket.data.scripts.avenge
                if callable(avenge_fn):
                    result = avenge_fn(trinket, game)
                else:
                    result = avenge_fn
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            game.queue_action(action, source=trinket)
                    else:
                        game.queue_action(result, source=trinket)
                game.broadcast("AVENGE_TRIGGER", trinket)


# ── Economy Actions ──

class SpendGold(Action):
    """Player spends gold."""

    def __init__(self, player: Player, amount: int):
        super().__init__()
        self.player = player
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        current = self.player.get_tag(GameTag.GOLD, 0)
        self.player.set_tag(GameTag.GOLD, max(0, current - self.amount))
        game.broadcast(GOLD_SPENT, self.player, self.amount)
        # Trigger trinket on_spend_gold effects
        for trinket in self.player.trinkets:
            on_sg = trinket.on_spend_gold
            if on_sg:
                if isinstance(on_sg, (list, tuple)):
                    for action in on_sg:
                        game.queue_action(action, source=trinket)
                else:
                    game.queue_action(on_sg, source=trinket)


class GainGold(Action):
    """Player gains gold."""

    def __init__(self, player: Player, amount: int):
        super().__init__()
        self.player = player
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        current = self.player.get_tag(GameTag.GOLD, 0)
        max_gold = self.player.get_tag(GameTag.MAX_GOLD, 99)
        self.player.set_tag(GameTag.GOLD, min(max_gold, current + self.amount))
        game.broadcast("GOLD_GAINED", self.player, self.amount)


class GainFreeRefresh(Action):
    """Grant free refreshes to a player. Each free refresh skips gold deduction."""

    def __init__(self, player: Player, amount: int):
        super().__init__()
        self.player = player
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        current = self.player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
        self.player.set_tag(GameTag.FREE_REFRESH_REMAINING, current + self.amount)


class SetNextSpellDiscount(Action):
    """Set a discount on the next tavern spell purchase."""

    def __init__(self, player: Player, amount: int):
        super().__init__()
        self.player = player
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        self.player.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, self.amount)


class UseHeroPower(Action):
    """Player uses their hero power.

    Checks: not already used this turn, enough gold.
    Deducts cost, marks used, executes the hero_power script method.
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        if self.player.get_tag(GameTag.HERO_POWER_USED):
            extra = self.player.get_tag(GameTag.HERO_POWER_EXTRA_USES, 0)
            if extra <= 0:
                return
            self.player.set_tag(GameTag.HERO_POWER_EXTRA_USES, extra - 1)
        cost = self.player.hero_power_cost
        if self.player.gold < cost:
            return
        if cost > 0:
            SpendGold(self.player, cost).do(source, game)
        self.player.set_tag(GameTag.HERO_POWER_USED, True)

        # Execute hero power script if present
        if self.player.data.scripts:
            hp_fn = getattr(self.player.data.scripts, "hero_power", None)
            if hp_fn and callable(hp_fn):
                result = hp_fn(self.player, game)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            game.queue_action(action, source=self.player)
                    else:
                        game.queue_action(result, source=self.player)

        from hsrl.core.events import HERO_POWER_USED
        game.broadcast(HERO_POWER_USED, self.player)


class UseSecondaryHeroPower(Action):
    """Player uses their secondary hero power (from anomalies).

    Checks: secondary HP exists, not already used this turn, enough gold.
    The secondary hero power is resolved via its script class from CardDB.
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        hp_card_id = self.player.get_tag(GameTag.SECONDARY_HERO_POWER_ID, 0)
        if not hp_card_id or hp_card_id == 0:
            return
        if self.player.get_tag(GameTag.SECONDARY_HERO_POWER_USED, False):
            return
        cost = self.player.get_tag(GameTag.SECONDARY_HERO_POWER_COST, 0)
        if self.player.gold < cost:
            return
        if cost > 0:
            SpendGold(self.player, cost).do(source, game)
        self.player.set_tag(GameTag.SECONDARY_HERO_POWER_USED, True)

        # Execute secondary hero power script
        hp_data = game.card_db.get(str(hp_card_id))
        if hp_data and hp_data.scripts:
            hp_fn = getattr(hp_data.scripts, "hero_power", None)
            if hp_fn and callable(hp_fn):
                result = hp_fn(self.player, game)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            game.queue_action(action, source=self.player)
                    else:
                        game.queue_action(result, source=self.player)

        from hsrl.core.events import HERO_POWER_USED
        game.broadcast(HERO_POWER_USED, self.player)


class UpgradeTavern(Action):
    """Player upgrades their tavern tier."""

    # Base gold cost to reach each tier (key = tier you are GOING TO)
    _BASE_COST = {2: 5, 3: 7, 4: 8, 5: 9, 6: 10, 7: 11}

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        current = self.player.get_tag(GameTag.TAVERN_TIER, 1)
        max_tier = 7 if self.player.get_tag(GameTag.TIER_7_UNLOCKED, False) else 6
        if current >= max_tier:
            return

        cost = max(self.player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5), 1)
        # Anomaly: upgrade costs 2 less (Uncompensated Upset)
        if (game.active_anomaly is not None
                and not isinstance(game.active_anomaly, bool)
                and getattr(game.active_anomaly, '_upgrade_cost_less_2', False)):
            cost = max(0, cost - 2)
        if self.player.gold < cost:
            return

        SpendGold(self.player, cost).do(source, game)
        self.player.set_tag(GameTag.TAVERN_TIER, current + 1)
        # Set the base cost for the next upgrade tier
        next_base = self._BASE_COST.get(current + 2, 10)
        self.player.set_tag(GameTag.TAVERN_UPGRADE_COST, next_base)
        game.track_tavern_upgrade(self.player, current + 1)
        game.broadcast("TAVERN_UPGRADED", self.player, current + 1)
        # Trigger anomaly on_upgrade if active
        if (game.active_anomaly is not None
                and not isinstance(game.active_anomaly, bool)
                and game.active_anomaly.data
                and game.active_anomaly.data.scripts):
            on_upgrade = getattr(game.active_anomaly.data.scripts, 'on_upgrade', None)
            if on_upgrade and callable(on_upgrade):
                result = on_upgrade(game.active_anomaly, game)
                if result:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            game.queue_action(action, source=game.active_anomaly)
                    else:
                        game.queue_action(result, source=game.active_anomaly)


# ── Blood Gem Actions ──

class PlayBloodGems(Action):
    """Play Blood Gems on a target minion.
    Base Blood Gem gives +1/+1. Bonus stats are added per gem.
    """

    def __init__(self, target: BaseEntity, count: int = 1):
        super().__init__()
        self.target = target
        self.count = count

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        controller = self.target.controller
        if controller is None:
            return
        bonus_atk = controller.get_tag(GameTag.BLOOD_GEM_BONUS_ATK, 0)
        bonus_health = controller.get_tag(GameTag.BLOOD_GEM_BONUS_HEALTH, 0)
        # Query trinkets for per-trinket blood gem bonuses
        for trinket in controller.trinkets:
            if trinket.data.scripts:
                modify = getattr(trinket.data.scripts, 'modify_blood_gem', None)
                if modify and callable(modify):
                    result = modify(trinket, game)
                    if result:
                        bonus_atk += result[0]
                        bonus_health += result[1]
        total_atk = (1 + bonus_atk) * self.count
        total_health = (1 + bonus_health) * self.count
        game.queue_action(Buff(self.target, atk=total_atk, health=total_health), source=source)
        # Broadcast BLOOD_GEM_PLAYED for on-gem effects (Geomagus Roogug, Hired Ritualist)
        game.broadcast("BLOOD_GEM_PLAYED", self.target, controller, self.count)


class ImproveBloodGem(Action):
    """Permanently improve Blood Gem buff values for a player.
    'Your Blood Gems give an extra +X/+Y this game.'
    """

    def __init__(self, player: "Player", atk_bonus: int = 0, health_bonus: int = 0):
        super().__init__()
        self.player = player
        self.atk_bonus = atk_bonus
        self.health_bonus = health_bonus

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        if self.atk_bonus:
            cur = self.player.get_tag(GameTag.BLOOD_GEM_BONUS_ATK, 0)
            self.player.set_tag(GameTag.BLOOD_GEM_BONUS_ATK, cur + self.atk_bonus)
        if self.health_bonus:
            cur = self.player.get_tag(GameTag.BLOOD_GEM_BONUS_HEALTH, 0)
            self.player.set_tag(GameTag.BLOOD_GEM_BONUS_HEALTH, cur + self.health_bonus)
        game.broadcast("BLOOD_GEM_IMPROVED", self.player, self.atk_bonus, self.health_bonus)


class ImproveTavernSpellBuff(Action):
    """Permanently improve stat bonuses applied by future Tavern spell casts.
    'Your Tavern spells give an extra +X/+Y this game.'
    """

    def __init__(self, player: "Player", atk_bonus: int = 0, health_bonus: int = 0):
        super().__init__()
        self.player = player
        self.atk_bonus = atk_bonus
        self.health_bonus = health_bonus

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        if self.atk_bonus:
            cur = self.player.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)
            self.player.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, cur + self.atk_bonus)
        if self.health_bonus:
            cur = self.player.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)
            self.player.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, cur + self.health_bonus)
        game.broadcast("TAVERN_SPELL_BUFF_IMPROVED", self.player, self.atk_bonus, self.health_bonus)


class GetBloodGem(Action):
    """Add Blood Gem spell cards to a player's hand.
    'Get a Blood Gem' — the spell goes to hand for later use.
    """

    def __init__(self, player: "Player", count: int = 1, variant: str = "base"):
        super().__init__()
        self.player = player
        self.count = count
        self.variant = variant  # "base" | "divine_shield" | "taunt"

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        card_ids = {
            "base": "BLOOD_GEM",
            "divine_shield": "BLOOD_GEM_DS",
            "taunt": "BLOOD_GEM_TAUNT",
        }
        card_id = card_ids[self.variant]
        for _ in range(self.count):
            if len(self.player.hand) >= MAX_HAND_SIZE:
                return  # Hand full — further gems are lost (standard BG rule)
            spell = game.create_minion(card_id)
            spell.controller = self.player
            spell.zone = Zone.HAND
            self.player.hand.append(spell)
            game.broadcast("BLOOD_GEM_RECEIVED", self.player, spell)


# ── Pool validation helper ───────────────────────────────────────────

def _is_valid_pool_card(card_id: str) -> bool:
    """Check if a card_id represents a valid pool minion (excludes tokens,
    buddy cards, golden-only cards, and examples)."""
    import re
    if card_id.startswith("EXAMPLE_"):
        return False
    if re.search(r't\d*$', card_id) and len(card_id) > 3:
        return False  # Token cards (e.g. BG19_010t, BG27_004t2)
    if "Buddy" in card_id or "buddy" in card_id.lower():
        return False  # Hero buddy cards
    if card_id.endswith("_G"):
        return False  # Golden-only cards
    # Also check the actual CardData: exclude tokens with tech_level <= 0
    # (pool minions always have tech_level >= 1)
    from hsrl.core.card_db import CARDS
    data = CARDS.get(card_id)
    if data is not None and data.tech_level <= 0:
        return False  # Token minion (e.g. BG31_817 Windfall Tornado)
    return True


# ── Discover Actions ──

class PendingChoice:
    """A discovery choice awaiting player (or RL agent) selection.

    The game engine pauses when a pending choice exists. Only a choice
    resolution action is valid until the choice is made.
    """

    def __init__(self, choice_type: str, options: list, source: "BaseEntity",
                 player: "Player", callback):
        self.choice_type = choice_type   # "minion", "spell", "reward", "trinket"
        self.options = options           # list of (card_id, name) tuples
        self.source = source            # entity that triggered the discover
        self.player = player            # player making the choice
        self.callback = callback        # fn(chosen_index) -> Action or list[Action]

    def resolve(self, index: int, game: "Game"):
        if index < 0 or index >= len(self.options):
            return
        result = self.callback(index)
        if result is not None:
            if isinstance(result, (list, tuple)):
                for a in result:
                    game.queue_action(a, source=self.source)
            else:
                game.queue_action(result, source=self.source)


class DiscoverMinion(Action):
    """Discover a minion and add it to the player's hand.

    Creates a PendingChoice state so the player or RL agent can choose.
    Heuristic/auto-play resolves with a random choice for backward compatibility.
    """

    def __init__(
        self,
        player: Player,
        race: Optional[Any] = None,
        max_tier: Optional[int] = None,
        min_tier: Optional[int] = None,
        card_type: Optional[Any] = None,
        card_id_filter: Optional[str] = None,
    ):
        super().__init__()
        self.player = player
        self.race = race
        self.max_tier = max_tier
        self.min_tier = min_tier
        self.card_type = card_type if card_type is not None else CardType.MINION
        self.card_id_filter = card_id_filter

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != self.card_type:
                continue
            if self.race is not None and data.race != self.race:
                continue
            if self.max_tier is not None and data.tech_level > self.max_tier:
                continue
            if self.min_tier is not None and data.tech_level < self.min_tier:
                continue
            if self.card_id_filter is not None and card_id != self.card_id_filter:
                continue
            if not _is_valid_pool_card(card_id):
                continue
            candidates.append(card_id)
        if not candidates:
            return
        if len(self.player.hand) >= MAX_HAND_SIZE:
            return

        # Limit to discover pool size (3 in real BG, but we show all valid)
        pool = game.rng.sample(candidates, min(3, len(candidates)))
        options = [(cid, game.card_db.get(cid).name) for cid in pool]

        def _on_choice(index):
            chosen_id = pool[index]
            minion = game.create_minion(chosen_id)
            if minion is None:
                return None
            minion.controller = self.player
            minion.zone = Zone.HAND
            self.player.hand.append(minion)
            game._last_discovered_id = chosen_id
            game.broadcast("DISCOVER", self.player, chosen_id)
            game._check_for_triple(self.player, minion)
            return None

        game._pending_choice = PendingChoice(
            "minion", options, source, self.player, _on_choice,
        )


class DiscoverSpell(Action):
    """Discover a Tavern Spell and add it to the player's hand.
    Mirrors DiscoverMinion but for CardType.SPELL cards.
    """

    def __init__(
        self,
        player: Player,
        max_tier: Optional[int] = None,
        spell_school: Optional[Any] = None,
    ):
        super().__init__()
        self.player = player
        self.max_tier = max_tier
        self.spell_school = spell_school

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        from hsrl.core.enums import CardType
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != CardType.SPELL:
                continue
            if card_id.startswith("EXAMPLE_"):
                continue
            if self.max_tier is not None and data.tech_level > self.max_tier:
                continue
            candidates.append(card_id)
        if not candidates:
            return
        if len(self.player.hand) >= MAX_HAND_SIZE:
            return

        pool = game.rng.sample(candidates, min(3, len(candidates)))
        options = [(cid, game.card_db.get(cid).name) for cid in pool]

        def _on_choice(index):
            chosen_id = pool[index]
            spell = game.create_spell(chosen_id)
            if spell is None:
                return None
            spell.controller = self.player
            spell.zone = Zone.HAND
            self.player.hand.append(spell)
            game.broadcast("DISCOVER_SPELL", self.player, chosen_id)
            return None

        game._pending_choice = PendingChoice(
            "spell", options, source, self.player, _on_choice,
        )


class FreezeTavernMinion(Action):
    """Freeze a specific minion in Bob's Tavern.
    Frozen minions persist across refreshes and gain +2/+1 each turn.
    """

    def __init__(self, minion: "BaseEntity"):
        super().__init__()
        self.minion = minion

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        self.minion.set_tag(GameTag.FROZEN, True)
        game.broadcast("TAVERN_MINION_FROZEN", self.minion)


class UpgradeTavernMinionTier(Action):
    """Replace a tavern minion with a random minion of a higher tier.
    Used by Galakrond's Greed: freeze a minion, then replace with higher tier.
    """

    def __init__(self, minion: "BaseEntity", player: "Player",
                 freeze_new: bool = False):
        super().__init__()
        self.minion = minion
        self.player = player
        self.freeze_new = freeze_new

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        current_tier = self.minion.get_tag(GameTag.TECH_LEVEL, 1)
        # Draw a random minion from a higher tier
        candidates = []
        for tier in range(current_tier + 1, 8):
            if game.minion_pool and tier in game.minion_pool._pools:
                candidates.extend(game.minion_pool._pools[tier])
        if not candidates:
            return
        chosen_id = game.rng.choice(candidates)
        # Remove old minion from tavern
        if self.minion in self.player.tavern:
            self.player.tavern.remove(self.minion)
        # Return old minion to pool
        old_card_id = self.minion.get_tag(GameTag.CARD_ID)
        if old_card_id and game.minion_pool:
            game.minion_pool.return_card(old_card_id)
        # Remove chosen from pool
        if game.minion_pool:
            game.minion_pool.remove_card(chosen_id)
        # Create new minion
        new_minion = game.create_minion(chosen_id)
        new_minion.controller = self.player
        new_minion.zone = Zone.TAVERN
        if self.freeze_new:
            new_minion.set_tag(GameTag.FROZEN, True)
        self.player.tavern.append(new_minion)
        game.broadcast("TAVERN_MINION_REPLACED", self.player, chosen_id)


class CopyFirstKilledEnemy(Action):
    """After combat, copy the first enemy killed to the player's hand.
    Used by 'I'll Take That!' (Arch-Villain Rafaam).
    """

    def __init__(self, player: "Player"):
        super().__init__()
        self.player = player

    def do(self, source: "BaseEntity", game: "Game", target: Optional["BaseEntity"] = None) -> None:
        # Find first enemy minion in the combat death log
        for dead_m in game._combat_death_log:
            if dead_m.controller is not None and dead_m.controller != self.player:
                # This is an enemy minion that died
                card_id = dead_m.get_tag(GameTag.CARD_ID)
                if card_id and not dead_m.is_golden:
                    new_minion = game.create_minion(card_id)
                    new_minion.controller = self.player
                    new_minion.zone = Zone.HAND
                    self.player.hand.append(new_minion)
                    game.broadcast("COPY_FIRST_KILLED_ENEMY", self.player, card_id)
                    return


class RotateRatKingType(Action):
    """Rotate the Rat King's hero power to a different random tribe.
    Picks a race different from the current RAT_KING_TYPE on the player.
    Supports all 10 standard Battlegrounds tribes.
    """

    RAT_KING_RACES = [
        Race.BEAST, Race.MECH, Race.MURLOC, Race.DEMON, Race.DRAGON,
        Race.PIRATE, Race.ELEMENTAL, Race.QUILBOAR, Race.NAGA, Race.UNDEAD,
    ]

    def __init__(self, player: "Player"):
        super().__init__()
        self.player = player

    def do(self, source: "BaseEntity", game: "Game",
           target: Optional["BaseEntity"] = None) -> None:
        current = self.player.get_tag(GameTag.RAT_KING_TYPE, Race.NONE)
        candidates = [r for r in self.RAT_KING_RACES if r != current]
        if not candidates:
            return
        new_type = game.rng.choice(candidates)
        self.player.set_tag(GameTag.RAT_KING_TYPE, new_type)
        game.broadcast("RAT_KING_TYPE_ROTATED", self.player, new_type)


class GetRandomMinion(Action):
    """Get a random minion matching criteria and add it to the player's hand.
    Semantically distinct from Discover — the player has no choice.
    'Get a random [Race]' / 'Get a random Tier X minion' effects.
    """

    def __init__(
        self,
        player: Player,
        race: Optional[Any] = None,
        min_tier: Optional[int] = None,
        max_tier: Optional[int] = None,
        card_type: Optional[Any] = None,
    ):
        super().__init__()
        self.player = player
        self.race = race
        self.min_tier = min_tier
        self.max_tier = max_tier
        self.card_type = card_type if card_type is not None else CardType.MINION

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        candidates = []
        import re
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != self.card_type:
                continue
            if self.race is not None and data.race != self.race:
                continue
            if self.min_tier is not None and data.tech_level < self.min_tier:
                continue
            if self.max_tier is not None and data.tech_level > self.max_tier:
                continue
            if not _is_valid_pool_card(card_id):
                continue
            candidates.append(card_id)
        if candidates:
            if len(self.player.hand) >= MAX_HAND_SIZE:
                return
            chosen_id = game.rng.choice(candidates)
            minion = game.create_minion(chosen_id)
            minion.controller = self.player
            minion.zone = Zone.HAND
            self.player.hand.append(minion)
            game.broadcast("GET_RANDOM_MINION", self.player, chosen_id)
            game._check_for_triple(self.player, minion)


class GetRandomBounty(Action):
    """Add a random Bounty spell to the target player's hand.

    Bounties are special spells in Battlegrounds Season 13.
    Used by minions like Lost City Looter, Bigwig Bandit, Shipwrecked Rascal.
    """

    BOUNTY_SPELLS = [
        "BG33_811",  # Healthy Bounty: +4 Health
        "BG33_812",  # Hostile Bounty: +2/+2 and Taunt
        "BG33_813",  # Selfish Bounty: +5/+5 to this
        "BG33_814",  # Friendly Bounty: +3/+3 to a friendly minion
        "BG33_815",  # Wealthy Bounty: +2/+2, Gain 1 Gold
    ]

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        cid = game.rng.choice(self.BOUNTY_SPELLS)
        spell = game.create_minion(cid)
        if spell is None:
            return
        spell.controller = self.player
        spell.zone = Zone.HAND
        self.player.hand.append(spell)


class AddToHand(Action):
    """Add a specific minion (by card id) to the player's hand."""

    def __init__(self, player: Player, card_id: str):
        super().__init__()
        self.player = player
        self.card_id = card_id

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if len(self.player.hand) >= MAX_HAND_SIZE:
            return
        data = game.card_db.get(self.card_id)
        if data and data.cardtype == CardType.SPELL:
            entity = game.create_spell(self.card_id)
        else:
            entity = game.create_minion(self.card_id)
        if entity is None:
            return
        entity.controller = self.player
        entity.zone = Zone.HAND
        self.player.hand.append(entity)
        game.broadcast("ADD_TO_HAND", self.player, entity)
        # Trigger on_enter_hand for in-hand-effect minions (Bream Counter, etc.)
        if hasattr(entity, 'data') and entity.data.scripts:
            enter_hand_fn = getattr(entity.data.scripts, 'on_enter_hand', None)
            if enter_hand_fn:
                result = enter_hand_fn(entity, game)
                if isinstance(result, Action):
                    game.queue_action(result, source=entity)
        from hsrl.core.minion import Minion
        if isinstance(entity, Minion):
            game._check_for_triple(self.player, entity)


class DealDamageToHero(Action):
    """Deal damage to a player's hero."""

    def __init__(self, player: Player, amount: int):
        super().__init__()
        self.player = player
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        damage = self.amount
        armor = self.player.armor
        if armor > 0:
            absorbed = min(damage, armor)
            self.player.armor = armor - absorbed
            damage -= absorbed
        if damage > 0:
            self.player.health -= damage
        from hsrl.core.events import PLAYER_DAMAGE_TAKEN
        game.broadcast(PLAYER_DAMAGE_TAKEN, self.player, self.amount, None)


class TransferStats(Action):
    """Destroy a source minion and add its ATK + MAX_HEALTH as a buff to a target minion."""

    def __init__(self, source_ent: BaseEntity, target_ent: BaseEntity):
        super().__init__()
        self.source_ent = source_ent
        self.target_ent = target_ent

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.source_ent.dead or self.target_ent.dead:
            return
        atk = self.source_ent.atk
        hp = self.source_ent.max_health
        Destroy(self.source_ent).do(self.source_ent, game)
        Buff(self.target_ent, atk=atk, health=hp).do(self.target_ent, game)


# ── Stat Swap Action ──

class SwapStats(Action):
    """Swap the Attack of two minions (Vol'jin hero power)."""

    def __init__(self, minion_a: BaseEntity, minion_b: BaseEntity):
        super().__init__()
        self.minion_a = minion_a
        self.minion_b = minion_b

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        if self.minion_a.dead or self.minion_b.dead:
            return
        a_atk = self.minion_a.atk
        b_atk = self.minion_b.atk
        self.minion_a.set_tag(GameTag.BASE_ATK, b_atk)
        self.minion_b.set_tag(GameTag.BASE_ATK, a_atk)
        self.minion_a.set_tag(GameTag.HEALTH, self.minion_a.max_health)
        self.minion_b.set_tag(GameTag.HEALTH, self.minion_b.max_health)


# ── Trigger / Scheduling Actions ──

class TriggerBattlecry(Action):
    """Trigger the Battlecry of a target minion as if it were just played."""

    def __init__(self, target: BaseEntity):
        super().__init__()
        self.target = target

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        bc = self.target.battlecry
        if bc:
            from hsrl.core.enums import GameTag
            player = self.target.controller
            times = 2 if (player and player.get_tag(GameTag.BATTLECRY_DOUBLED)) else 1
            for _ in range(times):
                if isinstance(bc, (list, tuple)):
                    for action in bc:
                        game.queue_action(action, source=self.target)
                else:
                    game.queue_action(bc, source=self.target)
        game.broadcast(BATTLECRY_TRIGGER, self.target, self.target.controller)


class ScheduleNextTurn(Action):
    """Schedule an action to execute at the start of the next Recruit phase.
    Used by effects like 'Gain 1 Gold next turn'.
    """

    def __init__(self, player: Player, action: Action):
        super().__init__()
        self.player = player
        self.action = action

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        game._deferred_actions.append((self.player, self.action))


# ── Transform / Morph Actions ──

class Transform(Action):
    """Transform a minion into a different minion, preserving buffs and position.

    Used by Chromadrake (Season 13) and similar evolution/transform effects.
    The old minion is replaced in-place on the board.
    """

    def __init__(self, target: BaseEntity, new_card_id: str):
        super().__init__()
        self.target = target
        self.new_card_id = new_card_id

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        controller = self.target.controller
        if controller is None:
            return
        board = controller.board
        if self.target not in board:
            return

        # Create the new minion
        new_minion = game.create_minion(self.new_card_id)
        new_minion.controller = controller
        new_minion.zone = self.target.zone

        # Transfer buffs from old minion to new minion
        for b in self.target._buffs:
            new_minion.add_buff(b)

        # Transfer Golden status
        if self.target.is_golden:
            new_minion.set_tag(GameTag.GOLDEN, True)

        # Replace in board at same position
        idx = board.index(self.target)
        board[idx] = new_minion
        new_minion.set_tag(GameTag.ZONE_POSITION, idx)

        # Move old minion to graveyard
        self.target.zone = Zone.GRAVEYARD
        controller.graveyard.append(self.target)

        game.broadcast("TRANSFORM", self.target, new_minion)


class FodderConsume(Action):
    """A demon consumes a minion from hand or board to gain its stats.

    Used by Fodder keyword (Season 13). The consumed minion is destroyed/removed,
    and the demon gains its attack and health.
    """

    def __init__(self, demon: BaseEntity, consumed: BaseEntity):
        super().__init__()
        self.demon = demon
        self.consumed = consumed

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.demon.dead or self.consumed.dead:
            return

        atk_gain = self.consumed.atk
        health_gain = self.consumed.max_health

        # Remove the consumed minion
        consumer_controller = self.consumed.controller
        if consumer_controller:
            if self.consumed in consumer_controller.hand:
                consumer_controller.hand.remove(self.consumed)
            elif self.consumed in consumer_controller.board:
                game.remove_from_board(self.consumed)
        self.consumed.zone = Zone.GRAVEYARD

        # Demon gains the stats
        game.queue_action(Buff(self.demon, atk=atk_gain, health=health_gain))
        from hsrl.core.events import FODDER_CONSUME
        game.broadcast(FODDER_CONSUME, self.demon, self.consumed, atk_gain, health_gain)


class ConsumeTavernMinion(Action):
    """Select a minion from the player's tavern, consume it, and gain its stats.

    Supports two selection modes:
    - "random": pick a random minion from the tavern
    - "highest_health": pick the minion with the highest current health
    """

    def __init__(self, player: Player, source: BaseEntity,
                 mode: str = "random"):
        super().__init__()
        self.player = player
        self.source = source
        self.mode = mode

    def do(self, source: BaseEntity, game: Game, target=None) -> None:

        if self.source.dead:
            return

        candidates = [m for m in self.player.tavern
                      if not m.dead and m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not candidates:
            return

        # Implicator Portrait: override to highest-health targeting
        actual_mode = "highest_health" if (
            self.mode == "highest_health"
            or self.player.get_tag(GameTag.IMPLICATOR_CONSUME_HIGHEST, False)
        ) else self.mode

        if actual_mode == "highest_health":
            chosen = max(candidates, key=lambda m: m.health)
        else:
            chosen = game.rng.choice(candidates)

        atk_gain = chosen.atk
        health_gain = chosen.max_health
        card_id = chosen.get_tag(GameTag.CARD_ID)

        # Remove from tavern
        if chosen in self.player.tavern:
            self.player.tavern.remove(chosen)

        # Return card to minion pool
        if game.minion_pool and card_id:
            game.minion_pool.return_card(card_id)

        # Mark the consumed minion as dead
        chosen.set_tag(GameTag.DEAD, True)
        chosen.zone = Zone.GRAVEYARD

        # Source gains the stats
        Buff(self.source, atk=atk_gain, health=health_gain).do(self.source, game)

        from hsrl.core.events import FODDER_CONSUME
        game.broadcast(FODDER_CONSUME, self.source, chosen, atk_gain, health_gain)
        # Trinket: on_tavern_minion_consumed
        game._dispatch_trinket_event(self.player, "on_tavern_minion_consumed",
                                     consumed=chosen)


class CopyTavernMinion(Action):
    """Copy a random minion from the controller's tavern to their hand.

    Used by Sea Witch Zar'jira's Spellcraft: Siren's Song.
    The copy preserves the original's current BASE_ATK and BASE_HEALTH.
    """

    def __init__(self, controller: Player):
        super().__init__()
        self.controller = controller

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        candidates = [
            m for m in self.controller.tavern
            if not m.dead and m.get_tag(GameTag.CARDTYPE) == CardType.MINION
        ]
        if not candidates:
            return
        original = game.rng.choice(candidates)
        copy_card_id = original.get_tag(GameTag.CARD_ID)
        if copy_card_id:
            copy_minion = game.create_minion(copy_card_id)
            if copy_minion:
                copy_minion.set_tag(GameTag.BASE_ATK, original.get_tag(GameTag.BASE_ATK, 0))
                copy_minion.set_tag(GameTag.BASE_HEALTH, original.get_tag(GameTag.BASE_HEALTH, 0))
                copy_minion.controller = self.controller
                copy_minion.zone = Zone.HAND
                self.controller.hand.append(copy_minion)


class AttachMagnetic(Action):
    """Attach a Magnetic minion to a friendly Mech, transferring stats and keywords.

    The magnetic minion is consumed (removed from board/hand) and its
    BASE_ATK, BASE_HEALTH, buffs, and keyword tags are transferred to the host.
    The host does NOT gain the MAGNETIC keyword itself.
    """

    MAGNETIC_TRANSFER_KEYWORDS = [
        GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.POISONOUS,
        GameTag.VENOMOUS, GameTag.REBORN, GameTag.WINDFURY, GameTag.CLEAVE,
    ]

    def __init__(self, magnetic_minion, host_mech):
        super().__init__()
        self.magnetic_minion = magnetic_minion
        self.host = host_mech

    def do(self, source, game, target=None):
        mag = self.magnetic_minion
        host = self.host
        if mag.dead or host.dead:
            return

        # Transfer base stats
        host.set_tag(GameTag.BASE_ATK,
                     host.get_tag(GameTag.BASE_ATK, 0) + mag.get_tag(GameTag.BASE_ATK, 0))
        host.set_tag(GameTag.BASE_HEALTH,
                     host.get_tag(GameTag.BASE_HEALTH, 0) + mag.get_tag(GameTag.BASE_HEALTH, 0))
        host.set_tag(GameTag.HEALTH, host.health + mag.get_tag(GameTag.BASE_HEALTH, 0))

        # Transfer buffs
        for buff in list(mag._buffs):
            host.add_buff(buff)
        mag._buffs.clear()

        # Transfer keywords
        for kw in self.MAGNETIC_TRANSFER_KEYWORDS:
            if mag.has_tag(kw):
                host.set_tag(kw, True)

        # Remove magnetic minion from wherever it is
        controller = mag.controller
        if controller:
            if mag in controller.hand:
                controller.hand.remove(mag)
            elif mag in controller.board:
                game.remove_from_board(mag)

        # Return card to pool
        card_id = mag.get_tag(GameTag.CARD_ID)
        if game.minion_pool and card_id:
            game.minion_pool.return_card(card_id)

        mag.set_tag(GameTag.DEAD, True)
        mag.zone = Zone.GRAVEYARD

        # Broadcast MAGNETIZED for on-magnetize effects (Junk Jouster, etc.)
        game.broadcast("MAGNETIZED", host, controller)
        if controller is not None:
            game._dispatch_trinket_event(controller, "on_magnetized",
                                          host=host, magnetic_minion=mag)


class GiveKeyword(Action):
    """Give a keyword to a minion for this combat only (temporary).
    Contrast with GainKeyword, which is permanent.
    """

    def __init__(self, target: BaseEntity, keyword: GameTag):
        super().__init__()
        self.target = target
        self.keyword = keyword

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        self.target.set_tag(self.keyword, True)


class GainDeathrattle(Action):
    """Grant a Deathrattle function to a minion dynamically at runtime.

    Sets target._script_overrides["deathrattle"] = deathrattle_fn.
    The function must have signature fn(source, game) -> Action.

    Used by hero powers that give minions deathrattles (Murloc King,
    Fragrant Phylactery, Earth Invocation).
    """

    def __init__(self, target: BaseEntity, deathrattle_fn):
        super().__init__()
        self.target = target
        self.deathrattle_fn = deathrattle_fn

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        self.target._script_overrides["deathrattle"] = self.deathrattle_fn


class GainSpecificDeathrattle(Action):
    """Grant a deathrattle that summons a specific token minion.

    Convenience wrapper around GainDeathrattle for the common pattern:
    "Give a minion 'Deathrattle: Summon a [token]'".

    Used by Surf n' Surf's Spellcraft (Crab Mount spell).
    """

    def __init__(self, target: BaseEntity, token_card_id: str):
        super().__init__()
        self.target = target
        self.token_card_id = token_card_id

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.target.dead:
            return
        token_cid = self.token_card_id

        def _summon_token(src, g):
            token = g.create_minion(token_cid)
            if token is None:
                return None
            return Summon(src.controller, token)

        self.target._script_overrides["deathrattle"] = _summon_token


class ClearTemporaryDeathrattles(Action):
    """Remove temporary deathrattles from all minions on a player's board.

    Called at end of recruit phase to clean up "until next turn" deathrattles
    granted by Spellcraft effects (e.g., Surf n' Surf's Crab Mount).
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        for m in self.player.get_board_minions():
            if m.dead:
                continue
            if m.get_tag(GameTag.TEMPORARY_DEATHRATTLE):
                m._script_overrides.pop("deathrattle", None)
                m.set_tag(GameTag.TEMPORARY_DEATHRATTLE, False)


class SummonFromHandForCombat(Action):
    """Summon a minion from hand to board for this combat only.

    The minion fights in the current combat, then returns to hand afterward.
    Used by Diremuck Forager, Expert Aviator, Deathly Striker.
    """

    def __init__(self, controller, minion):
        super().__init__()
        self.controller = controller
        self.minion = minion

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        if self.minion.dead:
            return
        if len(self.controller.board) >= 7:
            return  # Board full
        # Remove from hand
        if self.minion in self.controller.hand:
            self.controller.hand.remove(self.minion)
        # Place on board (rightmost)
        self.minion.controller = self.controller
        self.minion.zone = Zone.PLAY
        self.controller.board.append(self.minion)
        game._update_zone_positions(self.controller.board)
        # Mark as combat-only summon
        self.minion.set_tag(GameTag.COMBAT_SUMMON, True)
        # Reset combat state so it can attack this combat
        self.minion.reset_combat_state()
        game.broadcast("COMBAT_SUMMON", self.minion, self.controller)


class ReturnCombatSummons(Action):
    """At end of combat, return surviving combat-summoned minions to hand.

    Dead combat summons stay dead (they go to graveyard via normal death handling).
    """

    def do(self, source: BaseEntity, game: Game, target: Optional[BaseEntity] = None) -> None:
        for p in game.players:
            if not p.is_alive:
                continue
            to_return = [m for m in p.board
                         if m.get_tag(GameTag.COMBAT_SUMMON) and not m.dead]
            for m in to_return:
                p.board.remove(m)
                m.set_tag(GameTag.COMBAT_SUMMON, False)
                m.zone = Zone.HAND
                p.hand.append(m)


# ── Targeted Action (Deferred Target Selection) ───────────────────────────

class TargetedAction(Action):
    """An action that needs a target selected before it can execute.

    During RECRUIT phase, the engine pauses the action queue and stores this
    as pending in game._pending_targeted_queue. The player (or RL agent) must call
    game.resolve_pending_target(index) to select a target.

    During COMBAT phase, a random valid target is auto-selected.

    filter_fn: () -> list of valid target entities (evaluated lazily)
    action_factory: (target) -> Optional[Action] — action to queue, or None
    label: human-readable description for debugging
    """

    def __init__(self, filter_fn, action_factory, label: str = "",
                 target_domain: str = "board"):
        super().__init__()
        self.filter_fn = filter_fn
        self.action_factory = action_factory
        self.label = label
        self.target_domain = target_domain  # "board" or "tavern"
        self._target = None

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        if self._target is None:
            candidates = self.filter_fn()
            if not candidates:
                return
            if game.in_combat:
                self._target = game.rng.choice(candidates)
            else:
                # RECRUIT phase — pause for player selection
                game._pending_targeted_queue.append(self)
                return
        # Broadcast SPELL_CAST_ON_MINION for trinket listeners
        from hsrl.core.enums import CardType
        from hsrl.core.events import SPELL_CAST_ON_MINION
        source_ct = source.get_tag(GameTag.CARDTYPE, CardType.INVALID) if source else CardType.INVALID
        target_ct = self._target.get_tag(GameTag.CARDTYPE, CardType.INVALID) if self._target else CardType.INVALID
        if source_ct == CardType.SPELL and target_ct == CardType.MINION:
            # Convention: args[0] = target (minion), args[1] = source (spell)
            game.broadcast(SPELL_CAST_ON_MINION, self._target, source)

        result = self.action_factory(self._target)
        if result is not None:
            if isinstance(result, (list, tuple)):
                for a in result:
                    game.queue_action(a, source=source)
            else:
                game.queue_action(result, source=source)

    @property
    def candidates(self) -> list:
        """Current valid targets (for building action mask / UI)."""
        return self.filter_fn()


# ── Spell Casting on Minions ────────────────────────────────────────────

class CastSpellOnTarget(Action):
    """Cast a tavern spell directly on a target minion, bypassing
    hand/tavern mechanics. Used by Start of Combat anomaly effects."""

    def __init__(self, player, spell_id: str, target_minion):
        super().__init__()
        self.player = player
        self.spell_id = spell_id
        self.target_minion = target_minion

    def do(self, source, game, target=None):
        spell = game.create_spell(self.spell_id)
        if spell is None:
            return
        spell.controller = self.player
        on_play = spell.on_play
        if on_play and hasattr(on_play, '_target'):
            on_play._target = self.target_minion
            game.queue_action(on_play, source=spell)
        # SPELL_CAST_ON_MINION is broadcast by TargetedAction.do() when the
        # spell effect actually executes; do NOT broadcast here to avoid
        # double-triggering trinket listeners.


class CastSpellOnAll(Action):
    """Cast a tavern spell on all qualifying minions (optionally race-filtered).
    Used by Start of Combat anomaly effects."""

    def __init__(self, player, spell_id: str, race_filter=None):
        super().__init__()
        self.player = player
        self.spell_id = spell_id
        self.race_filter = race_filter

    def do(self, source, game, target=None):
        board = [m for m in self.player.board if not m.dead]
        targets = board
        if self.race_filter is not None:
            targets = [m for m in targets if m.race == self.race_filter]
        for m in targets:
            game.queue_action(CastSpellOnTarget(self.player, self.spell_id, m))


# ── Choose One ──────────────────────────────────────────────────────────

class ChooseOne(Action):
    """Present a set of predefined choices and execute the selected one.

    Like Discover, but choices are predefined actions rather than
    random card pools. Used by Sprightly Scarab, Fearless Foodie,
    Intrepid Botanist, etc.

    choices: list of (label: str, action_or_actions: Action | list[Action])
    index: which choice was selected (by AI policy; defaults to random)
    """

    def __init__(self, choices: list, index: Optional[int] = None):
        super().__init__()
        self.choices = choices  # [(label, action_or_list), ...]
        self.index = index      # None → random choice

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        if not self.choices:
            return
        idx = self.index if self.index is not None else game.rng.randrange(len(self.choices))
        _, action_or_list = self.choices[idx]
        if isinstance(action_or_list, (list, tuple)):
            for a in action_or_list:
                game.queue_action(a)
        else:
            game.queue_action(action_or_list)


# ── Helper classes ──

class BuffEnchantment:
    """Simple stat buff container."""

    def __init__(self, atk: int = 0, health: int = 0, temporary: bool = False):
        self.tags = {GameTag.ATK: atk, GameTag.HEALTH: health}
        self.temporary = temporary

    def get_tag(self, tag: GameTag, default: Any = 0) -> Any:
        return self.tags.get(tag, default)


class GlobalAura:
    """Persistent global aura that continuously applies stat bonuses to matching minions.

    'This game' auras live on the Player and are queried every time
    a minion's atk or max_health is computed. Once applied, they never expire.
    """

    def __init__(self, atk: int = 0, health: int = 0, race_filter=None):
        self.atk = atk
        self.health = health
        self.race_filter = race_filter  # None = all races, Race enum = filtered

    def __repr__(self) -> str:
        return f"<GlobalAura atk=+{self.atk} health=+{self.health} race={self.race_filter}>"


class TavernBuff:
    """Persistent buff applied to minions when they appear in Bob's Tavern.

    Unlike GlobalAura (which continuously affects board minions), TavernBuff
    is applied once when minions are drawn into the tavern via refresh_tavern().
    The buff persists across all future refreshes for the rest of the game.
    """

    def __init__(self, atk: int = 0, health: int = 0, race_filter=None,
                 max_tier: int = None):
        self.atk = atk
        self.health = health
        self.race_filter = race_filter  # None = all races
        self.max_tier = max_tier        # None = all tiers

    def matches(self, minion) -> bool:
        """Check if this buff applies to the given minion."""
        if self.race_filter is not None:
            minion_race = minion.get_tag(GameTag.RACE)
            if minion_race != self.race_filter and minion_race != Race.ALL:
                return False
        if self.max_tier is not None:
            if minion.get_tag(GameTag.TECH_LEVEL, 1) > self.max_tier:
                return False
        return True

    def __repr__(self) -> str:
        parts = []
        if self.atk:
            parts.append(f"atk=+{self.atk}")
        if self.health:
            parts.append(f"health=+{self.health}")
        if self.race_filter is not None:
            parts.append(f"race={self.race_filter.name}")
        if self.max_tier is not None:
            parts.append(f"max_tier={self.max_tier}")
        return f"<TavernBuff {' '.join(parts)}>"


class BuffTavern(Action):
    """Add a persistent buff to future tavern offerings for a player.

    "Give minions in the Tavern +X/+Y this game."
    """

    def __init__(self, player, atk: int = 0, health: int = 0,
                 race_filter=None, max_tier: int = None):
        super().__init__()
        self.player = player
        self.atk = atk
        self.health = health
        self.race_filter = race_filter
        self.max_tier = max_tier

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        tb = TavernBuff(
            atk=self.atk, health=self.health,
            race_filter=self.race_filter, max_tier=self.max_tier,
        )
        self.player.tavern_buffs.append(tb)
        game.broadcast("TAVERN_BUFF_ADDED", self.player, tb)

    def __repr__(self) -> str:
        return (f"<BuffTavern player={self.player.name} "
                f"atk=+{self.atk} health=+{self.health}>")


class IncrementImproveCounter(Action):
    """Increment the IMPROVE_COUNTER on a card.

    Used by "Improves after X" cards to track how many times
    the improvement condition has been met.
    """

    def __init__(self, target: BaseEntity, amount: int = 1):
        super().__init__()
        self.target = target
        self.amount = amount

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        if self.target.dead:
            return
        current = self.target.get_tag(GameTag.IMPROVE_COUNTER, 0)
        self.target.set_tag(GameTag.IMPROVE_COUNTER, current + self.amount)


class BuffRandomTavernMinion(Action):
    """Buff a random minion in the player's current tavern offerings.

    Used by "After the Tavern is Refreshed" cards like
    En-Djinn Blazer and Waveling.
    """

    def __init__(self, player: Player, atk: int = 0, health: int = 0):
        super().__init__()
        self.player = player
        self.atk = atk
        self.health = health

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        tavern = self.player.tavern
        candidates = [m for m in tavern if not m.dead]
        if not candidates:
            return
        t = game.rng.choice(candidates)
        Buff(t, atk=self.atk, health=self.health).do(source, game)


class AddFodderToRandomTavernMinion(Action):
    """Add FODDER keyword to a random minion in the player's tavern.

    Used by Laboratory Assistant's persistent refresh-triggered effect.
    Reads FODDER_REFRESH_REMAINING from source, decrements on each trigger.
    When counter reaches 0, becomes a no-op.
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        remaining = source.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0)
        if remaining <= 0:
            return

        source.set_tag(GameTag.FODDER_REFRESH_REMAINING, remaining - 1)

        tavern_minions = [
            m for m in self.player.tavern
            if not m.dead and m.get_tag(GameTag.CARDTYPE, 0) == 1
        ]
        if not tavern_minions:
            return

        chosen = game.rng.choice(tavern_minions)
        GainKeyword(chosen, GameTag.FODDER).do(source, game)


class CastTavernSpell(Action):
    """Broadcast TAVERN_SPELL_CAST and increment per-turn counter.

    Used by "Improves after you cast a Tavern spell" cards.
    This is the engine action triggered when a player casts a tavern spell.

    If spell_card_id is passed, also marks LAST_SPELL_CARD_ID and
    increments TAVERN_SPELLS_CAST_THIS_GAME.
    """

    def __init__(self, player: Player, spell_card_id: str = None):
        super().__init__()
        self.player = player
        self.spell_card_id = spell_card_id

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        current = self.player.get_tag(GameTag.TAVERN_SPELLS_CAST_THIS_TURN, 0)
        self.player.set_tag(GameTag.TAVERN_SPELLS_CAST_THIS_TURN, current + 1)
        if self.spell_card_id:
            self.player.set_tag(GameTag.LAST_SPELL_CARD_ID, self.spell_card_id)
            total = self.player.get_tag(GameTag.TAVERN_SPELLS_CAST_THIS_GAME, 0)
            self.player.set_tag(GameTag.TAVERN_SPELLS_CAST_THIS_GAME, total + 1)
        game.broadcast(TAVERN_SPELL_CAST, source, self.player)
        # Dispatch trinket counter-based on_spell_cast triggers
        for trinket in self.player.trinkets:
            if not trinket.data.scripts:
                continue
            fn = getattr(trinket.data.scripts, "on_spell_cast", None)
            if fn and callable(fn):
                result = fn(trinket, game)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for action in result:
                            game.queue_action(action, source=trinket)
                    elif isinstance(result, Action):
                        game.queue_action(result, source=trinket)


class CastYoggWheel(Action):
    """Spin the Wheel of Yogg-Saron: pick a random effect and apply it.

    Yogg effects include: deal damage to random enemy, buff friendly minions,
    gain gold, summon a minion, etc.
    """

    YOGG_EFFECTS = [
        "deal_3_to_random_enemy",
        "deal_6_to_random_enemy",
        "buff_board_2_2",
        "buff_board_4_4",
        "gain_gold_2",
        "gain_gold_5",
        "summon_random_minion",
        "deal_1_to_all_enemies",
        "buff_leftmost_5_5",
        "free_refresh",
        "discover_minion",
        "nothing",
    ]

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        effect = game.rng.choice(self.YOGG_EFFECTS)

        if effect == "deal_3_to_random_enemy":
            DealDamageToRandomEnemy(self.player, amount=3, count=1).do(source, game)
        elif effect == "deal_6_to_random_enemy":
            DealDamageToRandomEnemy(self.player, amount=6, count=1).do(source, game)
        elif effect == "buff_board_2_2":
            for m in self.player.board:
                if not m.dead:
                    Buff(m, atk=2, health=2).do(source, game)
        elif effect == "buff_board_4_4":
            for m in self.player.board:
                if not m.dead:
                    Buff(m, atk=4, health=4).do(source, game)
        elif effect == "gain_gold_2":
            GainGold(self.player, 2).do(source, game)
        elif effect == "gain_gold_5":
            GainGold(self.player, 5).do(source, game)
        elif effect == "summon_random_minion":
            from hsrl.core.card_db import CARDS
            pool = [cid for cid, data in CARDS._cards.items()
                    if data.cardtype == 4 and not cid.startswith("EXAMPLE")]
            if pool:
                token = game.create_minion(game.rng.choice(pool))
                if token:
                    game.summon(self.player, token)
        elif effect == "deal_1_to_all_enemies":
            DealDamageToRandomEnemy(self.player, amount=1, count=3).do(source, game)
        elif effect == "buff_leftmost_5_5":
            living = [m for m in self.player.board if not m.dead]
            if living:
                Buff(living[0], atk=5, health=5).do(source, game)
        elif effect == "free_refresh":
            GainFreeRefresh(self.player, 1).do(source, game)
        elif effect == "discover_minion":
            DiscoverMinion(self.player, max_tier=6).do(source, game)
        # "nothing" — no effect


# ── Darkmoon Prize pool ────────────────────────────────────────────────

# Darkmoon Prize effects: (display_name, action_factory(player) → Action)
_PRIZE_POOL = [
    ("Give your minions +2/+2", lambda p: _buff_all_friendly(p, 2, 2)),
    ("Gain 4 Gold", lambda p: GainGold(p, 4)),
    ("Give a random friendly +5/+5 and Taunt",
     lambda p: (_buff_random_friendly(p, 5, 5, GameTag.TAUNT))),
    ("Your next Refresh costs (0)", lambda p: GainFreeRefresh(p, 1)),
    ("Your next Tavern upgrade costs (3) less",
     lambda p: _set_tag(p, GameTag.TAVERN_UPGRADE_COST,
                        max(0, p.get_tag(GameTag.TAVERN_UPGRADE_COST, 5) - 3))),
    ("Get a plain copy of a minion from last opponent",
     lambda p: _copy_from_last_opponent(p)),
    ("Discover a minion of your most common type",
     lambda p: _discover_majority_tribe(p)),
]


def _buff_all_friendly(player, atk, health):
    actions = []
    for m in player.board:
        if not m.dead:
            actions.append(Buff(m, atk=atk, health=health))
    return actions if actions else None


def _buff_random_friendly(player, atk, health, keyword=None):
    board = [m for m in player.board if not m.dead]
    if not board:
        return None
    target = player.game.rng.choice(board)
    actions = [Buff(target, atk=atk, health=health)]
    if keyword:
        actions.append(GainKeyword(target, keyword))
    return actions


def _set_tag(player, tag, value):
    player.set_tag(tag, value)
    return None


def _copy_from_last_opponent(player):
    game = player.game
    opponents = [p for p in game.players if p != player and p.is_alive]
    if not opponents:
        return None
    opp = game.rng.choice(opponents)
    board = [m for m in opp.board if not m.dead]
    if not board:
        return None
    target = game.rng.choice(board)
    return AddToHand(player, target.get_tag(GameTag.CARD_ID))


def _discover_majority_tribe(player):
    from collections import Counter
    tribes = Counter()
    for m in player.board:
        if not m.dead and m.race not in (Race.NONE, Race.ALL, Race.INVALID):
            tribes[m.race] += 1
    if not tribes:
        return DiscoverMinion(player)
    majority = tribes.most_common(1)[0][0]
    return DiscoverMinion(player, race=majority)


class DiscoverPrize(Action):
    """Discover a Darkmoon Prize from a pool of 8 effects."""

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        pool = list(_PRIZE_POOL)
        choices = game.rng.sample(pool, min(3, len(pool)))
        options = [(f"prize_{i}", name) for i, (name, _) in enumerate(choices)]

        def callback(index):
            _, factory = choices[index]
            return factory(self.player)

        game._pending_choice = PendingChoice(
            choice_type="discover_prize",
            options=options,
            source=source,
            player=self.player,
            callback=callback,
        )


class DiscoverHeroPower(Action):
    """Discover a new Hero Power to replace your current one.

    Picks `count` random hero powers from the registered pool (excluding
    the player's current one). Replaces HERO_POWER tag and script.
    Default count is 3 (Sir Finley, Master Nguyen). Genn uses count=2.
    """

    def __init__(self, player: Player, count: int = 3):
        super().__init__()
        self.player = player
        self.count = count

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        from hsrl.core.card_db import CARDS
        current_hp_id = self.player.get_tag(GameTag.HERO_POWER)

        # Collect all active hero powers except the current one
        hp_pool = []
        for cid, data in CARDS._cards.items():
            if data.cardtype == CardType.HERO_POWER and not cid.startswith("EXAMPLE"):
                if cid != current_hp_id:
                    hp_pool.append((cid, data.name, data.scripts))

        if len(hp_pool) < self.count:
            return

        choices = game.rng.sample(hp_pool, self.count)
        options = [(cid, name) for cid, name, _ in choices]

        def callback(index):
            new_hp_id, new_name, new_script = choices[index]
            # Replace hero power on the player's hero data
            self.player.set_tag(GameTag.HERO_POWER, new_hp_id)
            if new_script is not None:
                self.player.data.scripts = new_script
            return None

        game._pending_choice = PendingChoice(
            choice_type="discover_hero_power",
            options=options,
            source=source,
            player=self.player,
            callback=callback,
        )


class DiscoverBuddy(Action):
    """Discover a Buddy minion.

    Picks 3 random non-golden Buddy minions and adds the chosen
    one to the player's hand.
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        import json
        from pathlib import Path

        # Load buddy card IDs from bg_cards.json
        data_dir = Path(__file__).parent.parent.parent / "data"
        with open(data_dir / "bg_cards.json") as f:
            all_cards = json.load(f)

        # Filter for non-golden buddy minions
        buddy_pool = []
        for c in all_cards:
            cid = c["id"]
            if "Buddy" not in cid:
                continue
            if cid.endswith("_G") or cid.endswith("_e"):
                continue
            buddy_pool.append((cid, c.get("name", cid)))

        if len(buddy_pool) < 3:
            return

        choices = game.rng.sample(buddy_pool, 3)
        options = [(cid, name) for cid, name in choices]

        def callback(index):
            chosen_id, _ = choices[index]
            # Auto-register the buddy card if needed, then add to hand
            if game.card_db:
                game._auto_register_card(chosen_id)
            return AddToHand(self.player, chosen_id)

        game._pending_choice = PendingChoice(
            choice_type="discover_buddy",
            options=options,
            source=source,
            player=self.player,
            callback=callback,
        )


class DiscoverReward(Action):
    """Discover a new quest reward from the reward pool and apply it.

    Creates a PendingChoice so the player/RL agent can choose.
    Heuristic mode auto-resolves with the first option.
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:
        from hsrl.cards.rewards.scripts import REWARD_SCRIPT_REGISTRY

        pool = list(REWARD_SCRIPT_REGISTRY.keys())
        if not pool:
            return

        # Pick 2 options, create PendingChoice
        choices = game.rng.sample(pool, min(2, len(pool)))
        options = [(cid, game.card_db.get(cid).name if game.card_db.get(cid) else cid)
                    for cid in choices]

        def _on_choice(index):
            chosen_id = choices[index]
            reward_data = game.card_db.get(chosen_id)
            if reward_data is None:
                return None
            from hsrl.core.quest import QuestReward
            reward = QuestReward(reward_data, game=game)
            reward.controller = self.player
            self.player.rewards.append(reward)
            if reward.data.scripts:
                fn = getattr(reward.data.scripts, 'on_unlock', None)
                if fn and callable(fn):
                    result = fn(reward, game)
                    if result:
                        if isinstance(result, (list, tuple)):
                            return list(result)
                        return result
            return None

        game._pending_choice = PendingChoice(
            "reward", options, source, self.player, _on_choice,
        )


class DiscoverTrinket(Action):
    """Discover a trinket and optionally replace the source trinket.

    Picks 2 random trinkets from the registry pool, selects one, and equips it.
    If replace_source is True, removes the source trinket first.
    If greater_only is True, only offers Greater trinkets (slot=2).
    If lesser_only is True, only offers Lesser trinkets (slot=1).
    """

    def __init__(self, player: "Player", replace_source: bool = False,
                 greater_only: bool = False, lesser_only: bool = False):
        super().__init__()
        self.player = player
        self.replace_source = replace_source
        self.greater_only = greater_only
        self.lesser_only = lesser_only

    def do(self, source: "BaseEntity", game: "Game", target=None) -> None:
        from hsrl.core.trinket import Trinket

        # Pool of available trinket card IDs
        pool = [
            cid for cid, data in game.card_db._cards.items()
            if data.cardtype == CardType.TRINKET
        ]
        if not pool:
            return

        # Filter by slot type if requested
        if self.greater_only:
            pool = [cid for cid in pool if 't' in cid and not cid.startswith('EXAMPLE')]
        elif self.lesser_only:
            pool = [cid for cid in pool if cid[-1] != 't' and not cid.startswith('EXAMPLE')]

        if not pool:
            return

        # Pick 2, auto-select first
        choices = game.rng.sample(pool, min(2, len(pool)))
        chosen_id = choices[0]

        trinket_data = game.card_db.get(chosen_id)
        if trinket_data is None:
            return

        trinket = Trinket(trinket_data, game=game)
        trinket.controller = self.player

        # Replace source if requested
        if self.replace_source and source is not None:
            if source in self.player.trinkets:
                self.player.trinkets.remove(source)

        self.player.trinkets.append(trinket)

        # Trigger on_summon and queue returned actions
        if trinket_data.scripts:
            fn = getattr(trinket_data.scripts, 'on_summon', None)
            if fn and callable(fn):
                result = fn(trinket, game)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for a in result:
                            game.queue_action(a, source=trinket)
                    elif isinstance(result, Action):
                        game.queue_action(result, source=trinket)


class GuessMinion(Action):
    """Guess which minion comes from the next opponent's last combat.

    In RL context without UI:
    1. Pick the next opponent (random alive enemy)
    2. Pick a random minion from their last combat board as the correct answer
    3. Auto-guess: 50% chance of being correct
    4. If correct, GainGold(1) (a Coin)

    This approximates the player choosing between 2 minions.
    """

    def __init__(self, player: Player):
        super().__init__()
        self.player = player

    def do(self, source: BaseEntity, game: Game, target=None) -> None:

        # Find next opponent
        enemies = [p for p in game.players if p != self.player and p.is_alive]
        if not enemies:
            return
        opponent = game.rng.choice(enemies)

        # Get opponent's last combat board (or current board as fallback)
        opp_board = getattr(opponent, 'last_opponent_board', None)
        if not opp_board:
            opp_board = [m for m in opponent.board if not m.dead]
        if not opp_board:
            return

        # Pick a real minion from opponent's board
        real_minion = game.rng.choice(opp_board)

        # Pick a random minion from the card pool as the decoy
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and not cid.startswith("EXAMPLE")]
        if not pool:
            return

        # Auto-guess: 50% chance of correct
        if game.rng.random() < 0.5:
            # Correct guess → gain 1 Gold (a Coin)
            GainGold(self.player, 1).do(source, game)
            game.broadcast("GUESS_CORRECT", self.player,
                          real_minion.get_tag(GameTag.CARD_ID))
        else:
            game.broadcast("GUESS_WRONG", self.player,
                          real_minion.get_tag(GameTag.CARD_ID))
