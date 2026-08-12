"""
HSRL Game Logger — Human-readable event and state logger.

Provides a formatted, hierarchical log of every action, event, and state
change during a Battlegrounds game. Designed for debugging, analysis, and
RL training transparency.

Usage:
    from hsrl.utils.logger import GameLogger

    game = Game(players)
    logger = GameLogger(game)
    logger.attach()  # Hooks into game.queue_action and game.broadcast

    game.start_game()
    # ... game plays out ...

    logger.snapshot()  # Dump full state
    logger.detach()    # Remove hooks

Output format:
    ═══ Turn 1 — RECRUIT Phase ═══
    [1] Battlecry: Razorfen Geomancer
    ├── GetBloodGem(player=P1, count=2)
    │   └── Hand: +2 BLOOD_GEM (total: 4)
    └── Board state:
        P1 (10 HP, 3 Gold, Tier 1)
        ├── [0] Razorfen Geomancer  2/3  (Tavern Tier 1)
        └── Hand: BLOOD_GEM, BLOOD_GEM, TAVERN_COIN
"""

from __future__ import annotations

import sys
import textwrap
from typing import Any, Dict, List, Optional, TextIO, Tuple

from hsrl.core.actions import (
    Action,
    Attack,
    AttackImmediately,
    Buff,
    Destroy,
    GainGold,
    GainKeyword,
    GetBloodGem,
    Heal,
    Hit,
    ImproveBloodGem,
    LoseKeyword,
    PlayBloodGems,
    Reborn,
    Summon,
    TriggerBattlecry,
)
from hsrl.core.enums import CardType, GameTag, Race, Step, Zone
from hsrl.core.events import (
    AFTER_ATTACK,
    AFTER_HIT,
    AVENGE_TRIGGER,
    BEFORE_ATTACK,
    BEFORE_DESTROY,
    BEFORE_HIT,
    BUFF,
    COMBAT_BEGIN,
    COMBAT_END,
    DAMAGE,
    DEATH,
    DEATHRATTLE_TRIGGER,
    DIVINE_SHIELD_LOST,
    ENTITY_CREATED,
    HEAL,
    PLAYER_DAMAGE_TAKEN,
    PLAYER_DEFEATED,
    POISON_KILL,
    REBORN_TRIGGER,
    RECRUIT_BEGIN,
    RECRUIT_END,
    SUMMON,
    VENOM_KILL,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Action name mapping for readable log lines
# ═══════════════════════════════════════════════════════════════════════════════

ACTION_NAMES: Dict[type, str] = {
    Attack: "Attack",
    AttackImmediately: "AttackImmediately",
    Hit: "Hit",
    Heal: "Heal",
    Buff: "Buff",
    Summon: "Summon",
    Destroy: "Destroy",
    Reborn: "Reborn",
    GainKeyword: "GainKeyword",
    LoseKeyword: "LoseKeyword",
    PlayBloodGems: "PlayBloodGems",
    GetBloodGem: "GetBloodGem",
    ImproveBloodGem: "ImproveBloodGem",
    GainGold: "GainGold",
    TriggerBattlecry: "TriggerBattlecry",
}

EVENT_LABELS: Dict[str, str] = {
    ENTITY_CREATED: "Entity Created",
    BEFORE_ATTACK: "Before Attack",
    AFTER_ATTACK: "After Attack",
    BEFORE_HIT: "Before Hit",
    AFTER_HIT: "After Hit",
    DAMAGE: "Damage",
    HEAL: "Heal",
    DIVINE_SHIELD_LOST: "Divine Shield Lost",
    POISON_KILL: "Poison Kill",
    VENOM_KILL: "Venom Kill",
    BEFORE_DESTROY: "Before Destroy",
    DEATH: "Death",
    DEATHRATTLE_TRIGGER: "Deathrattle Trigger",
    REBORN_TRIGGER: "Reborn Trigger",
    SUMMON: "Summon",
    BUFF: "Buff",
    AVENGE_TRIGGER: "Avenge Trigger",
    PLAYER_DAMAGE_TAKEN: "Player Damage Taken",
    PLAYER_DEFEATED: "Player Defeated",
    RECRUIT_BEGIN: "Recruit Phase Begin",
    RECRUIT_END: "Recruit Phase End",
    COMBAT_BEGIN: "Combat Phase Begin",
    COMBAT_END: "Combat Phase End",
}

RACE_NAMES: Dict[Race, str] = {
    Race.BEAST: "Beast",
    Race.DEMON: "Demon",
    Race.DRAGON: "Dragon",
    Race.ELEMENTAL: "Elemental",
    Race.MECH: "Mech",
    Race.MURLOC: "Murloc",
    Race.NAGA: "Naga",
    Race.PIRATE: "Pirate",
    Race.QUILBOAR: "Quilboar",
    Race.UNDEAD: "Undead",
    Race.ALL: "All",
    Race.NONE: "Neutral",
}

ZONE_NAMES: Dict[Zone, str] = {
    Zone.PLAY: "Board",
    Zone.HAND: "Hand",
    Zone.GRAVEYARD: "Graveyard",
    Zone.TAVERN: "Tavern",
    Zone.SETASIDE: "Set Aside",
}

# ═══════════════════════════════════════════════════════════════════════════════
# Helper: entity formatting
# ═══════════════════════════════════════════════════════════════════════════════


def _fmt_minion(m) -> str:
    """Format a minion as a one-line summary."""
    card_id = m.get_tag(GameTag.CARD_ID, "?")
    name = m.get_tag(GameTag.NAME, card_id)
    atk = m.atk
    hp = m.health
    max_hp = m.max_health
    race_val = m.race
    race_str = RACE_NAMES.get(race_val, "")
    tier = m.tech_level

    hp_str = f"{hp}/{max_hp}"
    keywords = []
    if m.taunt:
        keywords.append("Taunt")
    if m.divine_shield:
        keywords.append("DS")
    if m.poisonous:
        keywords.append("Poison")
    if m.venomous:
        keywords.append("Venom")
    if m.reborn:
        keywords.append("Reborn")
    if m.windfury:
        keywords.append("WF")
    if m.cleave:
        keywords.append("Cleave")
    if m.is_golden:
        keywords.append("★")
    kw_str = " ".join(keywords)

    parts = [f"{name}"]
    parts.append(f"{atk}/{hp_str}")
    if kw_str:
        parts.append(kw_str)
    if race_str:
        parts.append(f"({race_str})")
    parts.append(f"T{tier}")
    return " ".join(parts)


def _fmt_player(p) -> str:
    """Format a player as a one-line summary."""
    name = p.get_tag(GameTag.NAME, "?")
    health = p.health
    armor = p.armor
    gold = p.gold
    tier = p.tavern_tier
    parts = [f"{name}"]
    parts.append(f"HP={health}")
    if armor > 0:
        parts.append(f"Armor={armor}")
    parts.append(f"Gold={gold}")
    parts.append(f"Tier={tier}")
    return " ".join(parts)


def _action_desc(action: Action) -> str:
    """Get a human-readable description of an Action."""
    cls = type(action)
    name = ACTION_NAMES.get(cls, cls.__name__)

    # Per-class details
    if isinstance(action, Hit):
        return f"{name}(amount={action.amount})"
    elif isinstance(action, Buff):
        return f"{name}(atk=+{action.atk}, health=+{action.health})"
    elif isinstance(action, GainKeyword):
        kw_name = GameTag(action.keyword).name if action.keyword else "?"
        return f"{name}(keyword={kw_name})"
    elif isinstance(action, LoseKeyword):
        kw_name = GameTag(action.keyword).name if action.keyword else "?"
        return f"{name}(keyword={kw_name})"
    elif isinstance(action, PlayBloodGems):
        return f"{name}(count={action.count})"
    elif isinstance(action, GetBloodGem):
        return f"{name}(count={action.count}, variant={action.variant})"
    elif isinstance(action, ImproveBloodGem):
        return f"{name}(atk_bonus=+{action.atk_bonus}, health_bonus=+{action.health_bonus})"
    elif isinstance(action, GainGold):
        return f"{name}(amount={action.amount})"
    elif isinstance(action, Attack):
        return f"{name}()"
    elif isinstance(action, AttackImmediately):
        return f"{name}(attacker={_fmt_minion(action.attacker)})"
    elif isinstance(action, Destroy):
        return f"{name}()"
    elif isinstance(action, Summon):
        return f"{name}()"
    elif isinstance(action, Reborn):
        return f"{name}(original={_fmt_minion(action.original)})"
    elif isinstance(action, TriggerBattlecry):
        return f"{name}(target={_fmt_minion(action.target)})"
    return name


# ═══════════════════════════════════════════════════════════════════════════════
# GameLogger
# ═══════════════════════════════════════════════════════════════════════════════


class GameLogger:
    """
    Human-readable logger for HSRL game events and state changes.

    Parameters:
        game: The Game instance to log
        verbosity: 0=quiet, 1=actions only, 2=actions+events
        output: File-like object (default: sys.stdout)
        line_width: Maximum line width for formatting (default: 100)
    """

    def __init__(
        self,
        game: "Game",
        verbosity: int = 1,
        output: Optional[TextIO] = None,
        line_width: int = 100,
    ):
        self.game = game
        self.verbosity = verbosity
        self.output = output or sys.stdout
        self.line_width = line_width
        self._action_counter: int = 0
        self._indent: int = 0
        self._current_turn: int = 0
        self._current_phase: str = "INIT"
        self._attached: bool = False

        # Original methods (for detach)
        self._original_queue_action = None
        self._original_broadcast = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def attach(self) -> None:
        """Hook into the Game's action queue and event broadcast."""
        if self._attached:
            return
        self._original_queue_action = self.game.queue_action
        self._original_broadcast = self.game.broadcast
        self.game.queue_action = self._wrapped_queue_action
        self.game.broadcast = self._wrapped_broadcast
        self._attached = True

    def detach(self) -> None:
        """Remove hooks from the Game."""
        if not self._attached:
            return
        self.game.queue_action = self._original_queue_action
        self.game.broadcast = self._original_broadcast
        self._attached = False

    # ── Wrapped methods ────────────────────────────────────────────────

    def _wrapped_queue_action(self, action, source=None, target=None):
        """Intercept queue_action to log the action and its effects."""
        self._action_counter += 1
        n = self._action_counter

        # Pre-action state snapshots (for verbose mode)
        if self.verbosity >= 2:
            self._log_pre_state(action, source, target)

        # Log the action
        if self.verbosity >= 1:
            self._log_action_line(n, action, source, target)

        # Execute original
        self._original_queue_action(action, source, target)

    def _wrapped_broadcast(self, event_name, *args, **kwargs):
        """Intercept broadcast to log events."""
        if self.verbosity >= 2:
            self._log_event_line(event_name, *args)
        self._original_broadcast(event_name, *args, **kwargs)

    # ── Phase markers ──────────────────────────────────────────────────

    def phase_begin(self, phase_name: str) -> None:
        """Log the start of a phase."""
        self._current_phase = phase_name
        turn = self.game.turn
        if turn != self._current_turn:
            self._current_turn = turn
            self._write(f"\n{'═' * 60}")
            self._write(f"  Turn {turn} — {phase_name}")
            self._write(f"{'═' * 60}\n")
        else:
            self._write(f"\n─── {phase_name} ───\n")

    def phase_end(self, phase_name: str) -> None:
        """Log the end of a phase."""
        self._write(f"─── {phase_name} End ───\n")

    # ── State snapshot ─────────────────────────────────────────────────

    def snapshot(self, title: str = "Game State Snapshot") -> None:
        """Dump the full game state in a readable format."""
        self._write(f"\n{'━' * 60}")
        self._write(f"  {title}")
        self._write(f"{'━' * 60}")

        for i, player in enumerate(self.game.players):
            self._write_player_snapshot(player, i)

        self._write(f"{'━' * 60}\n")

    def snapshot_player(self, player: "Player", index: int = 0) -> None:
        """Dump a single player's state."""
        self._write_player_snapshot(player, index)

    # ── Internal formatting ────────────────────────────────────────────

    def _write(self, line: str) -> None:
        """Write a line to the output."""
        indent = "  " * self._indent
        self.output.write(f"{indent}{line}\n")
        self.output.flush()

    def _log_action_line(self, n: int, action, source, target) -> None:
        """Format and write an action log line."""
        desc = _action_desc(action)
        src_str = ""
        tgt_str = ""

        if source is not None:
            src_str = self._entity_label(source)

        if target is not None:
            tgt_str = self._entity_label(target)

        line = f"[{n}] {desc}"
        if src_str:
            line += f"  src={src_str}"
        if tgt_str:
            line += f"  → {tgt_str}"
        self._write(line)

    def _log_event_line(self, event_name: str, *args) -> None:
        """Format and write an event log line."""
        label = EVENT_LABELS.get(event_name, event_name)
        detail = self._format_event_args(event_name, *args)
        self._write(f"  ⚡ {label}{detail}")

    def _log_pre_state(self, action, source, target) -> None:
        """Log entity state before an action (verbose mode)."""
        if source is not None and hasattr(source, "atk"):
            self._write(f"  pre:  {_fmt_minion(source)}")
        if target is not None and hasattr(target, "atk"):
            self._write(f"  pre:  {_fmt_minion(target)}")

    def _format_event_args(self, event_name: str, *args) -> str:
        """Format event arguments into a readable string."""
        parts = []
        for arg in args:
            if hasattr(arg, "atk") and hasattr(arg, "health"):
                parts.append(_fmt_minion(arg))
            elif hasattr(arg, "health") and hasattr(arg, "gold"):
                parts.append(_fmt_player(arg))
            elif isinstance(arg, (int, float)):
                parts.append(str(arg))
            else:
                parts.append(str(arg)[:60])
        if parts:
            return "  " + " | ".join(parts)
        return ""

    def _entity_label(self, entity) -> str:
        """Get a short label for an entity."""
        if entity is None:
            return "None"
        if hasattr(entity, "atk") and hasattr(entity, "health"):
            return _fmt_minion(entity)
        if hasattr(entity, "health") and hasattr(entity, "gold"):
            return _fmt_player(entity)
        return str(type(entity).__name__)

    def _write_player_snapshot(self, player, index: int) -> None:
        """Write a formatted player state snapshot."""
        name = player.get_tag(GameTag.NAME, f"Player {index}")
        card_id = player.get_tag(GameTag.CARD_ID, "?")
        hero_power = player.get_tag(GameTag.HERO_POWER, "none")
        hero_power_used = player.get_tag(GameTag.HERO_POWER_USED, False)

        # Player header
        hp_used = " (used)" if hero_power_used else ""
        self._write(f"\n  ┌─ Player {index}: {name} ({card_id})")
        max_gold = player.get_tag(GameTag.MAX_GOLD, 10)
        self._write(f"  │  HP={player.health}  Armor={player.armor}  "
                     f"Gold={player.gold}/{max_gold}  "
                     f"Tavern Tier={player.tavern_tier}")
        self._write(f"  │  Hero Power: {hero_power}{hp_used}  "
                     f"Upgrade Cost: {player.get_tag(GameTag.TAVERN_UPGRADE_COST, 0)}")

        # Global auras
        if player.auras:
            self._write(f"  │  Auras:")
            for aura in player.auras:
                race_filter = RACE_NAMES.get(aura.race_filter, "All") if aura.race_filter else "All"
                self._write(f"  │    +{aura.atk}/+{aura.health} "
                             f"(race={race_filter})")

        # Blood Gem bonuses
        bg_atk = player.get_tag(GameTag.BLOOD_GEM_BONUS_ATK, 0)
        bg_hp = player.get_tag(GameTag.BLOOD_GEM_BONUS_HEALTH, 0)
        if bg_atk > 0 or bg_hp > 0:
            self._write(f"  │  Blood Gem Bonus: +{bg_atk}/+{bg_hp}")

        # Scaling counters
        mrrglton = player.get_tag(GameTag.MRRGLTON_COUNT, 0)
        if mrrglton > 0:
            self._write(f"  │  Mrrglton Count: {mrrglton}")

        plague = player.get_tag(GameTag.PLAGUERUNNER_SCALE, 0)
        if plague > 3:
            self._write(f"  │  Plaguerunner Scale: {plague}")

        # Board
        self._write(f"  │")
        self._write(f"  │  Board ({len(player.board)}/7):")
        for i, m in enumerate(player.board):
            self._write(f"  │    [{i}] {_fmt_minion(m)}")

        # Hand
        hand = player.get_hand_minions()
        if hand:
            self._write(f"  │")
            self._write(f"  │  Hand ({len(hand)}):")
            for i, m in enumerate(hand):
                self._write(f"  │    [{i}] {_fmt_minion(m)}")

        # Graveyard
        graveyard = player.graveyard
        if graveyard:
            graveyard_names = [
                m.get_tag(GameTag.NAME, m.get_tag(GameTag.CARD_ID, "?"))
                for m in graveyard
            ]
            self._write(f"  │  Graveyard: {', '.join(graveyard_names)}")

        self._write(f"  └─")

    # ── Convenience: decorate game ──────────────────────────────────────

    @staticmethod
    def wrap(game: "Game", verbosity: int = 1, output: Optional[TextIO] = None) -> "GameLogger":
        """Create a logger and attach it to the game. Returns the logger."""
        logger = GameLogger(game, verbosity=verbosity, output=output)
        logger.attach()
        return logger


# ═══════════════════════════════════════════════════════════════════════════════
# Quick-access helpers
# ═══════════════════════════════════════════════════════════════════════════════


def log_game_phases(game: "Game", logger: Optional[GameLogger] = None) -> GameLogger:
    """
    Create and attach a logger that marks phase transitions.
    Convenience function for test suites.
    """
    if logger is None:
        logger = GameLogger(game, verbosity=1)
    logger.attach()
    return logger
