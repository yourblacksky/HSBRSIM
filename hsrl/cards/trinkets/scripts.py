"""
Trinket Script Registry

Trinkets provide passive or triggered effects. Each script class can define:
  - start_of_combat(source, game) → Action
  - end_of_turn(source, game) → Action
  - on_buy(source, game) → Action
  - on_summon(source, game) → Action (one-time setup)
  - avenge(source, game) → Action
  - spellcraft(source, game) → str (returns card_id)
  - on_play(source, game) → Action (for spell trinkets)
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from hsrl.core.enums import CardType, GameTag, Race, Zone
from hsrl.core.actions import (
    Action, AttackImmediately, AttachMagnetic, Buff, BuffTavern,
    CastTavernSpell, DealDamageToHero, Destroy,
    DiscoverMinion, DiscoverSpell, GainDeathrattle, GainFreeRefresh,
    GainGold, GainKeyword, ImproveBloodGem, ImproveTavernSpellBuff,
    IncrementImproveCounter, PlayBloodGems, SetNextSpellDiscount,
    Summon, Transform, AddToHand, TriggerBattlecry,
)

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.entity import BaseEntity
    from hsrl.core.player import Player


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _random_friendly(source) -> Optional[BaseEntity]:
    living = [m for m in source.controller.board if not m.dead]
    return source.game.rng.choice(living) if living else None


def _living_board(player: Player) -> list:
    return [m for m in player.board if not m.dead]


def _buff_all(source, atk=0, health=0):
    actions = []
    for m in source.controller.board:
        if not m.dead:
            actions.append(Buff(m, atk=atk, health=health))
    return actions if actions else None


def _buff_tribe(source, tribe: Race, atk=0, health=0):
    actions = []
    for m in source.controller.board:
        if not m.dead and m.race == tribe:
            actions.append(Buff(m, atk=atk, health=health))
    return actions if actions else None


def _buff_random(source, count: int, atk=0, health=0):
    living = [m for m in source.controller.board if not m.dead]
    targets = source.game.rng.sample(living, min(count, len(living)))
    actions = []
    for m in targets:
        actions.append(Buff(m, atk=atk, health=health))
    return actions if actions else None


def _buff_leftmost(source, atk=0, health=0):
    board = [m for m in source.controller.board if not m.dead]
    if board:
        return Buff(board[0], atk=atk, health=health)
    return None


def _buff_rightmost(source, atk=0, health=0):
    board = [m for m in source.controller.board if not m.dead]
    if board:
        return Buff(board[-1], atk=atk, health=health)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Pattern Scripts
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleTrinketScript:
    """Start of Combat: Give your leftmost minion +1/+1."""

    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_leftmost(source, atk=1, health=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Buff All
# ═══════════════════════════════════════════════════════════════════════════════

class SoCBuffAllScript:
    """Start of Combat: Buff all friendly minions."""
    ATK = 2
    HEALTH = 2

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_all(source, atk=cls.ATK, health=cls.HEALTH)


class SoCBuffAll1x1Script(SoCBuffAllScript):
    ATK = 1; HEALTH = 1

class SoCBuffAll2x1Script(SoCBuffAllScript):
    ATK = 2; HEALTH = 1

class SoCBuffAll2x2Script(SoCBuffAllScript):
    ATK = 2; HEALTH = 2

class SoCBuffAll3x2Script(SoCBuffAllScript):
    ATK = 3; HEALTH = 2

class SoCBuffAll3x3Script(SoCBuffAllScript):
    ATK = 3; HEALTH = 3

class SoCBuffAll6x6Script(SoCBuffAllScript):
    ATK = 6; HEALTH = 6

class SoCBuffAll8x5Script(SoCBuffAllScript):
    ATK = 8; HEALTH = 5


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Buff Tribe
# ═══════════════════════════════════════════════════════════════════════════════

class SoCBuffTribeScript:
    """Start of Combat: Buff all friendly minions of a specific tribe."""
    TRIBE: Race = Race.INVALID
    ATK = 0
    HEALTH = 0

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_tribe(source, cls.TRIBE, atk=cls.ATK, health=cls.HEALTH)


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Buff Left/Right-most
# ═══════════════════════════════════════════════════════════════════════════════

class SoCBuffLeftmostScript:
    """Start of Combat: Buff leftmost minion."""
    ATK = 1
    HEALTH = 1

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_leftmost(source, atk=cls.ATK, health=cls.HEALTH)


class SoCBuffRightmostScript:
    ATK = 1; HEALTH = 1

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_rightmost(source, atk=cls.ATK, health=cls.HEALTH)


class SoCBuffLeftRightMostScript:
    """Start of Combat: Buff left- and right-most minions."""
    ATK = 0; HEALTH = 0

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        left = _buff_leftmost(source, atk=cls.ATK, health=cls.HEALTH)
        if left: actions.append(left)
        right = _buff_rightmost(source, atk=cls.ATK, health=cls.HEALTH)
        if right: actions.append(right)
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Buff Random
# ═══════════════════════════════════════════════════════════════════════════════

class SoCBuffRandomScript:
    """Start of Combat: Buff N random friendly minions."""
    COUNT = 1
    ATK = 0
    HEALTH = 0

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_random(source, cls.COUNT, atk=cls.ATK, health=cls.HEALTH)


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Summon
# ═══════════════════════════════════════════════════════════════════════════════

class SoCSummonScript:
    """Start of Combat: Summon a specific token when board has space."""
    TOKEN_ID: str = ""

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import Summon
        if len(source.controller.board) < 7:
            token = game.create_minion(cls.TOKEN_ID)
            if token is None:
                return None
            return Summon(source.controller, token)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Give Keyword
# ═══════════════════════════════════════════════════════════════════════════════

class SoCGiveKeywordScript:
    """Start of Combat: Give all minions a keyword."""
    KEYWORD = GameTag.DIVINE_SHIELD

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for m in source.controller.board:
            if not m.dead and not m.has_tag(cls.KEYWORD):
                actions.append(GainKeyword(m, cls.KEYWORD))
        return actions if actions else None


class SoCGiveTauntScript(SoCGiveKeywordScript):
    KEYWORD = GameTag.TAUNT

class SoCGiveRebornScript(SoCGiveKeywordScript):
    KEYWORD = GameTag.REBORN

class SoCGiveDivineShieldScript(SoCGiveKeywordScript):
    KEYWORD = GameTag.DIVINE_SHIELD


class SoCGiveKeywordTribeScript:
    """Start of Combat: Give a specific tribe a keyword."""
    TRIBE: Race = Race.INVALID
    KEYWORD = GameTag.TAUNT

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for m in source.controller.board:
            if not m.dead and m.race == cls.TRIBE and not m.has_tag(cls.KEYWORD):
                actions.append(GainKeyword(m, cls.KEYWORD))
        return actions if actions else None


class SoCGiveLeftRightMostKeywordScript:
    """Start of Combat: Give left- and right-most minions a keyword."""
    KEYWORD = GameTag.REBORN

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        board = _living_board(source.controller)
        if not board:
            return None
        actions = []
        for idx in (0, -1):
            if idx < len(board) and not board[idx].has_tag(cls.KEYWORD):
                actions.append(GainKeyword(board[idx], cls.KEYWORD))
        return actions if actions else None


class SoCGiveTribeKeywordRandomScript:
    """Start of Combat: Give N random friendly <TRIBE> <KEYWORD>."""
    COUNT = 1
    KEYWORD = GameTag.DIVINE_SHIELD
    TRIBE: Race = Race.INVALID

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        targets = [m for m in source.controller.board
                   if not m.dead and not m.has_tag(cls.KEYWORD)
                   and (cls.TRIBE == Race.INVALID or m.race == cls.TRIBE)]
        n = min(cls.COUNT, len(targets))
        if n == 0:
            return None
        actions = []
        for m in game.rng.sample(targets, n):
            actions.append(GainKeyword(m, cls.KEYWORD))
        return actions if actions else None


class SoCGiveTwoLeftmostBeastsDSScript(SoCGiveTribeKeywordRandomScript):
    """Stegodon Portrait: Give two left-most Beasts Divine Shield."""
    COUNT = 2
    KEYWORD = GameTag.DIVINE_SHIELD
    TRIBE = Race.BEAST

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        beasts = [m for m in source.controller.board
                  if not m.dead and m.race == Race.BEAST
                  and not m.has_tag(GameTag.DIVINE_SHIELD)]
        if not beasts:
            return None
        actions = []
        for m in beasts[:2]:
            actions.append(GainKeyword(m, GameTag.DIVINE_SHIELD))
        return actions if actions else None


class SoCGive4RandomPiratesDSScript(SoCGiveTribeKeywordRandomScript):
    """Protective Ring: Give 4 random friendly Pirates Divine Shield."""
    COUNT = 4
    KEYWORD = GameTag.DIVINE_SHIELD
    TRIBE = Race.PIRATE


# ═══════════════════════════════════════════════════════════════════════════════
# Passive Auras (on_summon sets player-level tags)
# ═══════════════════════════════════════════════════════════════════════════════

class DRDoubleScript:
    """Your Deathrattles trigger an extra time."""
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller.set_tag(GameTag.DEATHRATTLE_DOUBLED, True)


class BCDoubleScript:
    """Your Battlecries trigger an extra time."""
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller.set_tag(GameTag.BATTLECRY_DOUBLED, True)


class EoTDoubleScript:
    """Your End of Turn effects trigger an extra time."""
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller.set_tag(GameTag.END_OF_TURN_DOUBLED, True)


class HeroPowerDoubleScript:
    """Your Hero Power triggers twice."""
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller.set_tag(GameTag.HERO_POWER_DOUBLED, True)


class AuraStatsScript:
    """Your minions have +ATK/+HEALTH (permanent aura via on_summon)."""
    ATK = 2
    HEALTH = 1

    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        from hsrl.core.actions import GlobalAura
        aura = GlobalAura(atk=AuraStatsScript.ATK, health=AuraStatsScript.HEALTH)
        source.controller.auras.append(aura)
        # Store reference for cleanup
        # Store aura reference via GameTag for cleanup tracking


class AuraStatsTribeScript:
    """Your <tribe> have +ATK (permanent aura)."""
    TRIBE: Race = Race.INVALID
    ATK = 3
    HEALTH = 0

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        from hsrl.core.actions import ApplyGlobalAura
        ApplyGlobalAura(source.controller, atk=cls.ATK, health=cls.HEALTH,
                         race_filter=cls.TRIBE).do(source, game)


class ArtisanalUrnUndead3Script(AuraStatsTribeScript):
    """Lesser: Your Undead have +3 Attack."""
    TRIBE = Race.UNDEAD
    ATK = 3
    HEALTH = 0


class ArtisanalUrnUndead10Script(AuraStatsTribeScript):
    """Greater: Your Undead have +10 Attack."""
    TRIBE = Race.UNDEAD
    ATK = 10
    HEALTH = 0


# ═══════════════════════════════════════════════════════════════════════════════
# End of Turn: Buff
# ═══════════════════════════════════════════════════════════════════════════════

class EoTBuffAllScript:
    """End of Turn: Buff all friendly minions."""
    ATK = 1
    HEALTH = 1

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_all(source, atk=cls.ATK, health=cls.HEALTH)


class EoTBuffGoldenScript:
    """End of Turn: Buff Golden minions."""
    ATK = 3
    HEALTH = 3

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for m in source.controller.board:
            if not m.dead and m.is_golden:
                actions.append(Buff(m, atk=cls.ATK, health=cls.HEALTH))
        return actions if actions else None


class EoTBuffGolden10x10Script(EoTBuffGoldenScript):
    ATK = 10; HEALTH = 10


class EoTBuffTribeScript:
    """End of Turn: Buff specific tribe."""
    TRIBE: Race = Race.INVALID
    ATK = 2
    HEALTH = 0

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_tribe(source, cls.TRIBE, atk=cls.ATK, health=cls.HEALTH)


class EoTBuffDivineShieldScript:
    """End of Turn: Buff minions with Divine Shield."""
    ATK = 3
    HEALTH = 0

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for m in source.controller.board:
            if not m.dead and m.has_tag(GameTag.DIVINE_SHIELD):
                actions.append(Buff(m, atk=cls.ATK, health=cls.HEALTH))
        return actions if actions else None


class EoTBuffDivineShield7x0Script(EoTBuffDivineShieldScript):
    ATK = 7; HEALTH = 0


# ═══════════════════════════════════════════════════════════════════════════════
# End of Turn: Economy / Get Cards
# ═══════════════════════════════════════════════════════════════════════════════

class EoTGainGoldScript:
    """End of Turn: Gain Gold."""
    GOLD = 1

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return GainGold(source.controller, cls.GOLD)


class EoTFreeRefreshScript:
    """End of Turn: Gain a free refresh."""
    COUNT = 1

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import GainFreeRefresh
        return GainFreeRefresh(source.controller, cls.COUNT)


class EoTImproveGoldCapScript:
    """End of Turn: Increase max gold cap."""
    AMOUNT = 1

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        cap = source.controller.get_tag(GameTag.MAX_GOLD, 10)
        source.controller.set_tag(GameTag.MAX_GOLD, cap + cls.AMOUNT)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Gold generation (Start of Combat / Start of Turn)
# ═══════════════════════════════════════════════════════════════════════════════

class GainGoldPerTurnScript:
    """Gain Gold each turn (via SoC)."""
    GOLD = 1

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return GainGold(source.controller, cls.GOLD)


class GainGold2Script(GainGoldPerTurnScript):
    GOLD = 2

class GainGold3Script(GainGoldPerTurnScript):
    GOLD = 3

class GainGold4Script(GainGoldPerTurnScript):
    GOLD = 4


# ═══════════════════════════════════════════════════════════════════════════════
# Avenge
# ═══════════════════════════════════════════════════════════════════════════════

class AvengeBuffAllScript:
    """Avenge (N): Give your minions +ATK/+HEALTH."""
    ATK = 1
    HEALTH = 1

    @classmethod
    def avenge(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_all(source, atk=cls.ATK, health=cls.HEALTH)


class AvengeBuffAllPermanentScript:
    """Avenge (N): Give your minions +ATK/+HEALTH permanently."""
    ATK = 3
    HEALTH = 3

    @classmethod
    def avenge(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import Buff
        actions = []
        for m in source.controller.board:
            if not m.dead:
                actions.append(Buff(m, atk=cls.ATK, health=cls.HEALTH))
        return actions if actions else None


class AvengeBuffAll4x4Script(AvengeBuffAllScript):
    ATK = 4; HEALTH = 4


class AvengeSummonScript:
    """Avenge (N): Summon a token."""
    TOKEN_ID: str = ""

    @classmethod
    def avenge(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import Summon
        if len(source.controller.board) < 7:
            token = game.create_minion(cls.TOKEN_ID)
            if token is None:
                return None
            return Summon(source.controller, token)
        return None


class AvengeGetRandomMagneticScript:
    """Avenge (N): Get a random Magnetic minion."""
    @classmethod
    def avenge(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import AddToHand
        from hsrl.core.card_db import CARDS
        magnetic_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4  # MINION
            and data.tags.get(GameTag.MAGNETIC)
            and not cid.startswith("EXAMPLE")
        ]
        if not magnetic_ids:
            return None
        token = game.create_minion(game.rng.choice(magnetic_ids))
        if token is None:
            return None
        return AddToHand(source.controller, token)


class AvengeDealDamageToHeroScript:
    """Avenge (N): Deal 1 damage to your hero."""
    @classmethod
    def avenge(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import DealDamageToHero
        return DealDamageToHero(source.controller, 1)


class AvengeGiveKeywordScript:
    """Avenge (N): Give a random friendly minion of a tribe a keyword."""
    KEYWORD = GameTag.REBORN
    TRIBE: Race = Race.INVALID

    @classmethod
    def avenge(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        targets = [m for m in source.controller.board
                   if not m.dead and not m.has_tag(cls.KEYWORD)]
        if cls.TRIBE != Race.INVALID:
            targets = [m for m in targets if m.race == cls.TRIBE]
        if not targets:
            return None
        return GainKeyword(game.rng.choice(targets), cls.KEYWORD)


class AvengeGiveRebornUndeadScript(AvengeGiveKeywordScript):
    KEYWORD = GameTag.REBORN
    TRIBE = Race.UNDEAD


# ═══════════════════════════════════════════════════════════════════════════════
# On Buy
# ═══════════════════════════════════════════════════════════════════════════════

class OnBuyBuffScript:
    """After you buy a minion, give a friendly minion +ATK/+HEALTH."""
    ATK = 0
    HEALTH = 0
    TARGET_TRIBE: Race = Race.INVALID

    @classmethod
    def on_buy(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        targets = _living_board(source.controller)
        if cls.TARGET_TRIBE != Race.INVALID:
            targets = [m for m in targets if m.race == cls.TARGET_TRIBE]
        if not targets:
            return None
        target = game.rng.choice(targets)
        return Buff(target, atk=cls.ATK, health=cls.HEALTH)


# ═══════════════════════════════════════════════════════════════════════════════
# After Refresh (on tavern refresh)
# ═══════════════════════════════════════════════════════════════════════════════

class AfterRefreshBuffTavernScript:
    """After Refresh: Buff tavern minions."""
    ATK = 1
    HEALTH = 1

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import BuffTavern
        return BuffTavern(source.controller, atk=cls.ATK, health=cls.HEALTH)


# ═══════════════════════════════════════════════════════════════════════════════
# Spellcraft Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class SpellCostReductionScript:
    """Tavern spells that give stats cost (2) less — refresh discount each turn."""

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        # Refresh the spell cost discount each turn
        source.controller.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION,
                                   max(source.controller.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0), 2))
        return None


class SpellcraftConsumeTavernMinionScript:
    """Spellcraft: Choose a friendly minion to consume a random tavern minion."""
    @staticmethod
    def spellcraft(source: BaseEntity, game: Game) -> str:
        return "BG30_MagicItem_429t"  # Placeholder spell token


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Turn: Discover / Get
# ═══════════════════════════════════════════════════════════════════════════════

class SoTDiscoverMinionScript:
    """At the start of each turn, Discover a minion."""

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return DiscoverMinion(source.controller)


class SoTDiscoverTavernSpellScript:
    """At the start of each turn, Discover a Tavern spell."""

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return DiscoverSpell(source.controller)


class SoTGetRandomBattlecryScript:
    """At the start of each turn, get a random Battlecry minion."""

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.card_db import CARDS
        bc_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4
            and data.tags.get(GameTag.BATTLECRY)
            and not cid.startswith("EXAMPLE")
        ]
        if not bc_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(bc_ids))


class SoTGetRandomMagneticScript:
    """At the start of each turn, get a random Magnetic minion."""

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.card_db import CARDS
        magnetic_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4
            and data.tags.get(GameTag.MAGNETIC)
            and not cid.startswith("EXAMPLE")
        ]
        if not magnetic_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(magnetic_ids))


class SoTCastSpellScript:
    """At the start of each turn, cast a Tavern spell (for Improves tracking)."""
    COUNT = 1

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for _ in range(cls.COUNT):
            actions.append(CastTavernSpell(source.controller))
        return actions if actions else None


class PocketCycloneScript(SoTCastSpellScript):
    """Cast Easterly Winds once. At the start of each turn, repeat it."""
    COUNT = 1

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return CastTavernSpell(source.controller)


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Turn: Repeat Get (Get X, then get another each turn)
# ═══════════════════════════════════════════════════════════════════════════════

class SoTRepeatGetScript:
    """Get X. At the start of each turn, get another (by card_id)."""
    TOKEN_ID: str = ""

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        game.queue_action(AddToHand(source.controller, cls.TOKEN_ID), source=source)

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return AddToHand(source.controller, cls.TOKEN_ID)


class SoTRepeatGetBloodGemScript:
    """Get a keyword Blood Gem. At the start of each turn, get another."""
    GEM_IDS = ("BLOOD_GEM_TAUNT", "BLOOD_GEM_DS", "BLOOD_GEM_REBORN")

    @classmethod
    def _gem(cls, source):
        return AddToHand(source.controller, source.game.rng.choice(cls.GEM_IDS))

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        game.queue_action(cls._gem(source), source=source)

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return cls._gem(source)


class SoTRepeatGetRandomTribeScript:
    """Get a random <TRIBE> minion. At the start of each turn, get another."""
    TRIBE: Race = Race.INVALID
    COUNT = 1

    @classmethod
    def _get(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4
            and data.tags.get(GameTag.RACE) == cls.TRIBE
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        actions = []
        for _ in range(cls.COUNT):
            actions.append(AddToHand(source.controller, game.rng.choice(pool)))
        return actions if actions else None

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        result = cls._get(source, game)
        if result:
            for a in (result if isinstance(result, list) else [result]):
                game.queue_action(a, source=source)

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return cls._get(source, game)


class SoTRepeatGetRandomTierScript:
    """Get N random Tier Y minions. At the start of each turn, get N more."""
    TIER = 1
    COUNT = 1

    @classmethod
    def _get(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4
            and data.tags.get(GameTag.TECH_LEVEL) == cls.TIER
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        actions = []
        for _ in range(cls.COUNT):
            actions.append(AddToHand(source.controller, game.rng.choice(pool)))
        return actions if actions else None

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        result = cls._get(source, game)
        if result:
            for a in (result if isinstance(result, list) else [result]):
                game.queue_action(a, source=source)

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return cls._get(source, game)


# SoTRepeatGet subclasses: specific named minions

class ButcherSickleScript(SoTRepeatGetScript):
    TOKEN_ID = "BG28_604"  # Butchering

class WisdomballSupplyScript(SoTRepeatGetScript):
    TOKEN_ID = "BG30_802"  # Knockoff Wisdomball

class SellementalPortraitScript(SoTRepeatGetScript):
    TOKEN_ID = "BGS_115"  # Sellemental

class BalladistPortraitScript(SoTRepeatGetScript):
    TOKEN_ID = "BG26_814"  # Lovesick Balladist


# SoTRepeatGet subclasses: random tribe

class SoTRepeatGetRandomMechScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.MECH

class SoTRepeatGetRandomPirateScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.PIRATE

class SoTRepeatGetRandomDemonScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.DEMON

class SoTRepeatGetRandomDragonScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.DRAGON

class SoTRepeatGetRandomUndeadScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.UNDEAD

class SoTRepeatGetRandomNagaScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.NAGA

class SoTRepeatGetRandomMurlocScript(SoTRepeatGetRandomTribeScript):
    TRIBE = Race.MURLOC

class SoTGetRandomMagneticMechScript(SoTRepeatGetRandomTribeScript):
    """Get N random Magnetic Mecha-Demons. At SoT get N more."""
    COUNT = 2


# SoTRepeatGet subclasses: random tier

class SoTRepeatGetTier7Script(SoTRepeatGetRandomTierScript):
    TIER = 7


# SoTRepeatGet subclasses: bounty

class SoTRepeatGetBountyScript:
    """Get N random Bounties. At the start of each turn, get N more."""
    COUNT = 1

    @classmethod
    def _get(cls, source, game):
        from hsrl.core.actions import GetRandomBounty
        actions = []
        for _ in range(cls.COUNT):
            actions.append(GetRandomBounty(source.controller))
        return actions if actions else None

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        result = cls._get(source, game)
        if result:
            for a in result:
                game.queue_action(a, source=source)

    @classmethod
    def start_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return cls._get(source, game)


class SoTRepeatGetBounty2Script(SoTRepeatGetBountyScript):
    COUNT = 2


# ═══════════════════════════════════════════════════════════════════════════════
# Start of Combat: Unique
# ═══════════════════════════════════════════════════════════════════════════════

class SoCDoubleScript:
    """Your Start of Combat effects trigger an extra time."""

    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller.set_tag(GameTag.START_OF_COMBAT_DOUBLED, True)


class SoCDoubleLowestStatsScript:
    """Start of Combat: Double the stats of your N lowest Attack minions."""
    COUNT = 2

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        board = _living_board(source.controller)
        if not board:
            return None
        board.sort(key=lambda m: m.atk)
        targets = board[:min(cls.COUNT, len(board))]
        actions = []
        for m in targets:
            actions.append(Buff(m, atk=m.atk, health=m.health))
        return actions if actions else None


class SoCLeftmostGainsHighestHealthScript:
    """Start of Combat: Left-most minion gains stats of highest-Health minion."""

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        board = _living_board(source.controller)
        if not board:
            return None
        highest = max(board, key=lambda m: m.health)
        leftmost = board[0]
        return Buff(leftmost, atk=highest.atk, health=highest.health)


# ═══════════════════════════════════════════════════════════════════════════════
# End of Turn: Variants
# ═══════════════════════════════════════════════════════════════════════════════

class EoTBuffLeftmostScript:
    """End of Turn: Give your left-most minion +ATK/+HEALTH."""
    ATK = 1; HEALTH = 1

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_leftmost(source, atk=cls.ATK, health=cls.HEALTH)


class EoTBuffLeftmost3x2Script(EoTBuffLeftmostScript):
    """Cliffdiver Sticker: +3/+2 leftmost, improves by battlecries triggered this game.

    Formal spec:
      1. on_summon: register BATTLECRY_TRIGGER listener → IncrementImproveCounter
      2. end_of_turn: buff leftmost by (ATK + counter, HEALTH + counter)

    Test: trigger N battlecries → EoT buffs leftmost for (3+N)/(2+N).
    """
    ATK = 3; HEALTH = 2

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import BATTLECRY_TRIGGER, EventListener
        game.register_listener(source, EventListener(
            event_name=BATTLECRY_TRIGGER,
            action=IncrementImproveCounter(source),
        ))

    @classmethod
    def end_of_turn(cls, source, game):
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        return _buff_leftmost(source, atk=cls.ATK + counter, health=cls.HEALTH + counter)


class EoTBuffLeftmost2x2Script(EoTBuffLeftmostScript):
    """Charming Panpipes: +3/+3 leftmost, improves per spell cast this game.

    Formal spec:
      1. on_summon: register TAVERN_SPELL_CAST listener → IncrementImproveCounter
      2. end_of_turn: buff leftmost by (ATK + counter, HEALTH + counter)

    Test: cast N spells → EoT buffs leftmost for (3+N)/(3+N).
    """
    ATK = 3; HEALTH = 3

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener
        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=IncrementImproveCounter(source),
        ))

    @classmethod
    def end_of_turn(cls, source, game):
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        return _buff_leftmost(source, atk=cls.ATK + counter, health=cls.HEALTH + counter)


class EoTBuffLeftmost4x3Script(EoTBuffLeftmostScript):
    """Auric Offering: +4/+3 leftmost, repeats once per friendly golden minion.

    Formal spec:
      1. end_of_turn: buff leftmost by +4/+3
      2. For each additional golden minion on board, buff again

    Test: N golden minions → leftmost gets (N) × (+4/+3).
    """
    ATK = 4; HEALTH = 3

    @classmethod
    def end_of_turn(cls, source, game):
        board = source.controller.get_board_minions()
        living = [m for m in board if not m.dead]
        if not living:
            return None
        golden_count = sum(1 for m in living if m.has_tag(GameTag.GOLDEN))
        leftmost = living[0]
        actions = []
        for _ in range(golden_count):
            actions.append(Buff(leftmost, atk=cls.ATK, health=cls.HEALTH))
        return actions if actions else None


class EoTBuffRandomMurlocScript:
    """End of Turn: Give a random friendly Murloc +ATK/+HEALTH."""
    ATK = 1; HEALTH = 1

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        murlocs = [m for m in source.controller.board
                    if not m.dead and m.race == Race.MURLOC]
        if not murlocs:
            return None
        return Buff(game.rng.choice(murlocs), atk=cls.ATK, health=cls.HEALTH)


class MugOfTheSireScript:
    """Whenever you would summon a minion that doesn't fit in your warband,
    give your minions +5 Attack."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_OVERFLOW, EventListener

        class _OverflowBuffAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                board = [m for m in self.player.board if not m.dead]
                for m in board:
                    game_ref.queue_action(Buff(m, atk=5, health=0))

        game.register_listener(source, EventListener(
            event_name=MINION_OVERFLOW,
            action=_OverflowBuffAction(source.controller),
        ))


class ToxicStingerScript:
    """End of Turn: Give a random friendly Murloc +8/+8 and Venomous."""

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        murlocs = [m for m in source.controller.board
                    if not m.dead and m.race == Race.MURLOC]
        if not murlocs:
            return None
        target = game.rng.choice(murlocs)
        return [Buff(target, atk=8, health=8),
                GainKeyword(target, GameTag.VENOMOUS)]


class EoTGetWindfallScript:
    """End of Turn: Get a Windfall Tornado."""
    TOKEN_ID = "BG31_817"

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return AddToHand(source.controller, cls.TOKEN_ID)


class EoTTriggerBattlecriesScript:
    """End of Turn: Trigger your left- and right-most minions' Battlecries."""

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        targets = [board[0]]
        if len(board) > 1:
            targets.append(board[-1])
        actions = [TriggerBattlecry(m) for m in targets if m.has_tag(GameTag.BATTLECRY)]
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# On Buy: Buff Two Random
# ═══════════════════════════════════════════════════════════════════════════════

class OnBuyBuffTwoRandomScript:
    """After you buy a minion, give two random friendly minions +ATK/+HEALTH."""
    ATK = 0; HEALTH = 0

    @classmethod
    def on_buy(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_random(source, 2, atk=cls.ATK, health=cls.HEALTH)


class OnBuyBuffTwoRandom1x1Script(OnBuyBuffTwoRandomScript):
    ATK = 1; HEALTH = 1


# ═══════════════════════════════════════════════════════════════════════════════
# On Play: Buff Tribe (whenever you play a card)
# ═══════════════════════════════════════════════════════════════════════════════

class OnPlayBuffTribeScript:
    """Whenever you play a card, give your <TRIBE> +ATK/+HEALTH."""
    TRIBE: Race = Race.INVALID
    ATK = 1; HEALTH = 1

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game, **kwargs) -> Optional[Action]:
        return _buff_tribe(source, cls.TRIBE, atk=cls.ATK, health=cls.HEALTH)


class OnPlayBuffDragonScript(OnPlayBuffTribeScript):
    TRIBE = Race.DRAGON
    ATK = 4
    HEALTH = 4


# ═══════════════════════════════════════════════════════════════════════════════
# On Spend Gold: Buff
# ═══════════════════════════════════════════════════════════════════════════════

class OnSpendGoldBuffScript:
    """Whenever you spend Gold, give a random friendly minion +ATK/+HEALTH."""
    ATK = 0; HEALTH = 0

    @classmethod
    def on_spend_gold(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        living = _living_board(source.controller)
        if not living:
            return None
        return Buff(game.rng.choice(living), atk=cls.ATK, health=cls.HEALTH)


class OnSpendGoldBuffMurlocScript(OnSpendGoldBuffScript):
    ATK = 1; HEALTH = 1


# ═══════════════════════════════════════════════════════════════════════════════
# Get Random Minions by Tier
# ═══════════════════════════════════════════════════════════════════════════════

class GetRandomMinionsTier1x6Script:
    """Horn of Summoning: Get 6 random minions of Tier 1."""
    TIER = 1; COUNT = 6


class GetRandomMinionsTierScript:
    """Get N random minions of Tier Y."""
    TIER = 1; COUNT = 1

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4
            and data.tags.get(GameTag.TECH_LEVEL) == cls.TIER
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        actions = []
        for _ in range(cls.COUNT):
            actions.append(AddToHand(source.controller, game.rng.choice(pool)))
        return actions if actions else None


class GetRandomMinionsTier1x6Script(GetRandomMinionsTierScript):
    """Horn of Summoning: Get 6 random minions of Tier 1."""
    TIER = 1; COUNT = 6


# ═══════════════════════════════════════════════════════════════════════════════
# Tavern Buff Aura (Minions in the Tavern have +X/+Y)
# ═══════════════════════════════════════════════════════════════════════════════

class TavernBuffAuraScript:
    """Minions in the Tavern have +ATK/+HEALTH."""
    ATK = 1; HEALTH = 0

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        game.queue_action(
            BuffTavern(source.controller, atk=cls.ATK, health=cls.HEALTH),
            source=source,
        )


class TavernBuffAura2x1Script(TavernBuffAuraScript):
    ATK = 2; HEALTH = 1

class TavernBuffAura3x3Script(TavernBuffAuraScript):
    ATK = 3; HEALTH = 3


# ═══════════════════════════════════════════════════════════════════════════════
# On Play: Tribe-filtered (whenever you play a card of a specific tribe)
# ═══════════════════════════════════════════════════════════════════════════════

class OnPlayTribeFilteredScript:
    """Whenever you play a card of TRIBE, do something."""
    TRIBE: Race = Race.INVALID

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game, played_card=None) -> Optional[Action]:
        if played_card is None:
            return None
        tribe = played_card.get_tag(GameTag.RACE, Race.INVALID)
        if tribe != cls.TRIBE:
            return None
        return cls._on_tribe_play(source, game, played_card)

    @classmethod
    def _on_tribe_play(cls, source, game, played_card):
        return None


class OnPlayElementalTavernBuffScript(OnPlayTribeFilteredScript):
    """After you play an Elemental, give Elementals in the Tavern +ATK/+HEALTH this game."""
    TRIBE = Race.ELEMENTAL
    ATK = 2; HEALTH = 2

    @classmethod
    def _on_tribe_play(cls, source, game, played_card):
        return BuffTavern(source.controller, atk=cls.ATK, health=cls.HEALTH,
                          race_filter=Race.ELEMENTAL)


class OnPlayElementalTavernBuff4x4Script(OnPlayElementalTavernBuffScript):
    ATK = 5; HEALTH = 5


class OnPlayElementalFreeRefreshScript(OnPlayTribeFilteredScript):
    """After you play an Elemental, gain a free Refresh."""
    TRIBE = Race.ELEMENTAL

    @classmethod
    def _on_tribe_play(cls, source, game, played_card):
        from hsrl.core.actions import GainFreeRefresh
        return GainFreeRefresh(source.controller, 1)


class OnPlayElementalGetTavernSpellScript(OnPlayTribeFilteredScript):
    """After you play an Elemental, get a random Tavern spell. (Twice per turn.)"""
    TRIBE = Race.ELEMENTAL

    @classmethod
    def _on_tribe_play(cls, source, game, played_card):
        # Get a random tavern spell
        from hsrl.core.card_db import CARDS
        spell_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 3  # SPELL
            and data.tags.get(GameTag.TECH_LEVEL)  # Has tier
            and not cid.startswith("EXAMPLE")
        ]
        if not spell_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(spell_ids))


# ═══════════════════════════════════════════════════════════════════════════════
# On Cast: Per-cast Tavern spell triggers
# ═══════════════════════════════════════════════════════════════════════════════

class OnCastBuffTribeScript:
    """After you cast a Tavern spell, give your <TRIBE> +ATK/+HEALTH."""
    TRIBE: Race = Race.INVALID
    ATK = 2; HEALTH = 2

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _tribe = cls.TRIBE
        _atk = cls.ATK
        _health = cls.HEALTH

        class _BuffTribeOnCast(Action):
            def do(self, source_ent, game_ref, target=None):
                actions = []
                for m in source.controller.board:
                    if not m.dead and m.race == _tribe:
                        actions.append(Buff(m, atk=_atk, health=_health))
                for a in actions:
                    game_ref.queue_action(a)

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffTribeOnCast(),
            condition=lambda spell, player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


class OnCastBuffPirateScript(OnCastBuffTribeScript):
    TRIBE = Race.PIRATE; ATK = 2; HEALTH = 2


class OnCastBuffTribelessScript:
    """After you cast a Tavern spell, give your minions with no type +4/+4."""

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener

        class _BuffTribelessOnCast(Action):
            def do(self, source_ent, game_ref, target=None):
                actions = []
                for m in source.controller.board:
                    if not m.dead and m.race == Race.NONE:
                        actions.append(Buff(m, atk=4, health=4))
                for a in actions:
                    game_ref.queue_action(a)

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffTribelessOnCast(),
            condition=lambda spell, player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Combat Events: First Death, On Attack, On Lose Divine Shield, On Summon
# ═══════════════════════════════════════════════════════════════════════════════

class FirstDeathTransferStatsScript:
    """First time a friendly minion dies each combat, give its stats to random."""
    TARGET_COUNT = 1
    _flag_attr = '_first_death_used'

    @classmethod
    def on_friendly_death_combat(cls, source: BaseEntity, game: Game,
                                  dead_minion=None) -> Optional[Action]:
        if getattr(source, cls._flag_attr, False):
            return None
        setattr(source, cls._flag_attr, True)
        if dead_minion is None:
            return None
        living = [m for m in source.controller.board if not m.dead]
        if not living:
            return None
        targets = game.rng.sample(living, min(cls.TARGET_COUNT, len(living)))
        actions = []
        for t in targets:
            actions.append(Buff(t, atk=dead_minion.atk, health=dead_minion.health))
        return actions if actions else None

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        setattr(source, cls._flag_attr, False)
        return None


class FirstDeathTransferStats2xScript(FirstDeathTransferStatsScript):
    TARGET_COUNT = 2


class OnFriendlyDeathCombatGetTavernSpellScript:
    """Whenever a friendly minion with no type dies, get a random Tavern spell.
    (The Eye of Dalaran)"""
    _flag_attr = '_on_death_used'

    @classmethod
    def on_friendly_death_combat(cls, source: BaseEntity, game: Game,
                                  dead_minion=None) -> Optional[Action]:
        if dead_minion is None:
            return None
        if dead_minion.race != Race.NONE:
            return None
        from hsrl.core.card_db import CARDS
        spell_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 3 and data.tags.get(GameTag.TECH_LEVEL)
            and not cid.startswith("EXAMPLE")
        ]
        if not spell_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(spell_ids))


# ═══════════════════════════════════════════════════════════════════════════════
# Every N Turns ("At the start/end of every N turns, ...")
# ═══════════════════════════════════════════════════════════════════════════════

class _EveryNTurnsBase:
    """Increment turn counter on each turn, trigger when counter % PERIOD == 0."""
    PERIOD = 2

    @classmethod
    def on_turn_begin(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        if counter % cls.PERIOD == 0:
            return cls.on_trigger(source, game)
        return None

    @classmethod
    def on_trigger(cls, source, game):
        return None


class EveryTwoTurnsRepeatGetScript(_EveryNTurnsBase):
    """Every 2 turns, get a specific token."""
    PERIOD = 2
    TOKEN_ID = ""

    @classmethod
    def on_trigger(cls, source, game):
        return AddToHand(source.controller, cls.TOKEN_ID)

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        """Give the first token immediately."""
        if cls.TOKEN_ID:
            game.queue_action(AddToHand(source.controller, cls.TOKEN_ID), source=source)


class EveryThreeTurnsRepeatGetScript(_EveryNTurnsBase):
    """Every 3 turns, get a specific token."""
    PERIOD = 3
    TOKEN_ID = ""

    @classmethod
    def on_trigger(cls, source, game):
        return AddToHand(source.controller, cls.TOKEN_ID)

    @classmethod
    def on_summon(cls, source: BaseEntity, game: Game) -> None:
        if cls.TOKEN_ID:
            game.queue_action(AddToHand(source.controller, cls.TOKEN_ID), source=source)


# ═══════════════════════════════════════════════════════════════════════════════
# Counter-based Triggers ("After you X N times")
# ═══════════════════════════════════════════════════════════════════════════════

class _CounterBase:
    """Base mixin: increment per-trinket counter, trigger when target reached."""
    TARGET = 1

    @classmethod
    def _increment(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        if counter >= cls.TARGET:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            return cls.on_trigger(source, game)
        return None

    @classmethod
    def on_trigger(cls, source, game):
        return None


class CounterSpellCastScript(_CounterBase):
    """After you cast N Tavern spells, trigger."""

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener

        class _IncrementOnCast(Action):
            def do(self, source_ent, game_ref, target=None):
                result = cls._increment(source, game_ref)
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        for a in result:
                            game_ref.queue_action(a, source=source)
                    else:
                        game_ref.queue_action(result, source=source)

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_IncrementOnCast(),
            condition=lambda spell, player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


class CounterBuyScript(_CounterBase):
    """After you buy N minions, trigger."""

    @classmethod
    def on_minion_bought(cls, source, game):
        return cls._increment(source, game)


class CounterSellScript(_CounterBase):
    """After you sell N minions, trigger."""

    @classmethod
    def on_minion_sold(cls, source, game):
        return cls._increment(source, game)


class CounterRefreshScript(_CounterBase):
    """After you Refresh N times, trigger."""

    @classmethod
    def on_tavern_refresh(cls, source, game):
        return cls._increment(source, game)


# ── Counter subclasses: specific effects ──

class CounterBuyBCScript(CounterBuyScript):
    """After you buy 2 Battlecry minions, get a random Battlecry minion."""
    TARGET = 2

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        bc_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.BATTLECRY)
            and not cid.startswith("EXAMPLE")
        ]
        if not bc_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(bc_ids))


class CounterSellMurlocScript(CounterSellScript):
    """After you sell 5 minions, get a random Murloc."""
    TARGET = 5

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.MURLOC
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        return AddToHand(source.controller, game.rng.choice(pool))


class CounterSellElementalScript(CounterSellScript):
    """After you sell 5 minions, get a random Elemental."""
    TARGET = 5
    TRIBE_RACE = Race.ELEMENTAL

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.RACE) == cls.TRIBE_RACE
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        return AddToHand(source.controller, game.rng.choice(pool))


class CounterSellTokenScript(CounterSellScript):
    """After you sell 4 minions, get a Mounting Avalanche."""
    TARGET = 4
    TOKEN_ID = "BG33_899"

    @classmethod
    def on_trigger(cls, source, game):
        return AddToHand(source.controller, cls.TOKEN_ID)


class CounterSpellCastNagaScript(CounterSpellCastScript):
    """After you cast 6 spells, get a random Naga."""
    TARGET = 6

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.NAGA
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        return AddToHand(source.controller, game.rng.choice(pool))


class CounterSpellCastBloodGemAllScript(CounterSpellCastScript):
    """After you cast N spells, play a Blood Gem on all your minions."""
    TARGET = 5
    GEM_COUNT = 1

    @classmethod
    def on_trigger(cls, source, game):
        living = _living_board(source.controller)
        if not living:
            return None
        actions = []
        for m in living:
            actions.append(PlayBloodGems(m, cls.GEM_COUNT))
        return actions if actions else None


class CounterSpellCastBloodGemAll5x1Script(CounterSpellCastBloodGemAllScript):
    TARGET = 5; GEM_COUNT = 1

class CounterSpellCastBloodGemAll5x2Script(CounterSpellCastBloodGemAllScript):
    TARGET = 5; GEM_COUNT = 2


class CounterRefreshHealthCostScript(CounterRefreshScript):
    """After you Refresh 3 times, the highest-Tier minion costs Health.

    Formal spec:
      1. Counter increments on each tavern refresh
      2. When counter reaches 3: set HEALTH_COST_DEMON tag on controller
      3. Engine checks HEALTH_COST_DEMON in buy_minion()
    """
    TARGET = 3

    @classmethod
    def on_trigger(cls, source, game):
        source.controller.set_tag(GameTag.HEALTH_COST_DEMON, True)
        return None


class CounterDeathScript(_CounterBase):
    """After N friendly minions die, trigger."""

    @classmethod
    def on_friendly_death_combat(cls, source, game, dead_minion=None):
        return cls._increment(source, game)


class CounterDeathGetUndeadScript(CounterDeathScript):
    """After 9 friendly minions die, get a random Undead."""
    TARGET = 9

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.UNDEAD
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        return AddToHand(source.controller, game.rng.choice(pool))


class CounterDeathGetBeastScript(CounterDeathScript):
    """After 7 friendly minions die, get a random Beast."""
    TARGET = 7

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.BEAST
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        return AddToHand(source.controller, game.rng.choice(pool))


class CounterDeathGetMechScript(CounterDeathScript):
    """After 7 friendly minions die, get a random Mech."""
    TARGET = 7

    @classmethod
    def on_trigger(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.MECH
            and not cid.startswith("EXAMPLE")
        ]
        if not pool:
            return None
        return AddToHand(source.controller, game.rng.choice(pool))


class CounterSpendGoldScript(_CounterBase):
    """After you spend N Gold, trigger."""

    @classmethod
    def on_spend_gold(cls, source, game):
        return cls._increment(source, game)


class CounterSpendGoldBuffPirateScript(CounterSpendGoldScript):
    """After you spend 10 Gold, give your Pirates +1/+1 and improve this."""
    TARGET = 10

    @classmethod
    def on_trigger(cls, source, game):
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
        source.set_tag(GameTag.IMPROVE_COUNTER, counter)
        bonus = 1 + counter
        return _buff_tribe(source, Race.PIRATE, atk=bonus, health=bonus)


class CounterSpendGoldCastSpellScript(CounterSpendGoldScript):
    """After you spend 7 Gold, cast Shiny Ring."""
    TARGET = 7

    @classmethod
    def on_trigger(cls, source, game):
        return CastTavernSpell(source.controller)


# ═══════════════════════════════════════════════════════════════════════════════
# Combat Events: On Attack, On Lose Divine Shield, On Summon In Combat
# ═══════════════════════════════════════════════════════════════════════════════

class _LimitedPerCombatBase:
    """Base for combat effects with a per-combat usage limit. Reset on SoC."""
    MAX_USES = 3
    _counter_attr = '_combat_uses'

    @classmethod
    def _use(cls, source):
        used = getattr(source, cls._counter_attr, 0) + 1
        setattr(source, cls._counter_attr, used)
        return used <= cls.MAX_USES

    @classmethod
    def start_of_combat(cls, source, game):
        setattr(source, cls._counter_attr, 0)
        return None


class OnAttackBuffScript:
    """Whenever a friendly minion attacks, give it +ATK."""
    ATK = 4

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _atk = cls.ATK

        class _BuffAttacker(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                if target.controller != source.controller:
                    return
                game_ref.queue_action(Buff(target, atk=_atk, health=0))

        listener = EventListener(
            event_name="AFTER_ATTACK",
            action=_BuffAttacker(),
            condition=lambda attacker, defender: (
                attacker is not None
                and not attacker.dead
                and attacker.controller == source.controller
            ),
        )
        game.register_listener(source, listener)
        return None


class OnAttackBuffBeastScript:
    """Whenever a friendly Beast attacks, give it +2 ATK and permanently improve this."""
    ATK = 2
    IMPROVE_BY = 1

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _atk_base = cls.ATK
        _improve = cls.IMPROVE_BY

        class _BuffAttackingBeast(Action):
            def do(self, source_ent, game_ref, target=None):
                # target = args[0] from AFTER_ATTACK = attacker
                if target is None or target.dead:
                    return
                if target.race != Race.BEAST:
                    return
                if target.controller != source.controller:
                    return
                source.set_tag(GameTag.IMPROVE_COUNTER,
                               source.get_tag(GameTag.IMPROVE_COUNTER, 0) + _improve)
                bonus = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
                game_ref.queue_action(Buff(target, atk=_atk_base + bonus, health=0))

        listener = EventListener(
            event_name="AFTER_ATTACK",
            action=_BuffAttackingBeast(),
            condition=lambda attacker, defender: (
                attacker is not None
                and not attacker.dead
                and attacker.race == Race.BEAST
                and attacker.controller == source.controller
            ),
        )
        game.register_listener(source, listener)
        return None


class OnLoseDSRegainDSScript(_LimitedPerCombatBase):
    """After a friendly Mech loses Divine Shield, give it DS (N times per combat)."""
    MAX_USES = 3

    @classmethod
    def on_lose_divine_shield(cls, source: BaseEntity, game: Game,
                               minion=None) -> Optional[Action]:
        if minion is None or minion.dead or minion.race != Race.MECH:
            return None
        if not cls._use(source):
            return None
        return GainKeyword(minion, GameTag.DIVINE_SHIELD)


class OnLoseDSGetSpellScript(_LimitedPerCombatBase):
    """After a friendly minion loses Divine Shield, get a random Tavern spell (N times)."""
    MAX_USES = 4

    @classmethod
    def on_lose_divine_shield(cls, source: BaseEntity, game: Game,
                               minion=None) -> Optional[Action]:
        if minion is None:
            return None
        if not cls._use(source):
            return None
        from hsrl.core.card_db import CARDS
        spell_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 3 and data.tags.get(GameTag.TECH_LEVEL)
            and not cid.startswith("EXAMPLE")
        ]
        if not spell_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(spell_ids))


class OnLoseVenomousBuffScript:
    """Whenever a friendly minion loses Venomous, give it +ATK/+HEALTH permanently."""
    ATK = 4
    HEALTH = 4

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener

        _atk = cls.ATK
        _health = cls.HEALTH

        class _BuffOnVenomousLost(Action):
            def do(self, source_ent, game_ref, target=None):
                # target = args[0] from KEYWORD_LOST broadcast = the minion
                if target is None or target.dead:
                    return
                if target.controller != source.controller:
                    return
                game_ref.queue_action(Buff(target, atk=_atk, health=_health))

        listener = EventListener(
            event_name="KEYWORD_LOST",
            action=_BuffOnVenomousLost(),
            condition=lambda minion, keyword: (
                keyword == GameTag.VENOMOUS
                and minion is not None
                and not minion.dead
                and minion.controller == source.controller
            ),
        )
        game.register_listener(source, listener)
        return None


class OnSummonInCombatGiveDSScript(_LimitedPerCombatBase):
    """Whenever you summon a minion in combat, give it DS (N times per combat)."""
    MAX_USES = 5
    TRIBE: Race = Race.INVALID

    @classmethod
    def on_summon_in_combat(cls, source: BaseEntity, game: Game,
                              summoned=None) -> Optional[Action]:
        if summoned is None or summoned.dead:
            return None
        if cls.TRIBE != Race.INVALID and summoned.race != cls.TRIBE:
            return None
        if not cls._use(source):
            return None
        return GainKeyword(summoned, GameTag.DIVINE_SHIELD)


class OnSummonBeastDoubleAtkScript:
    """After you summon a Beast in combat, double its Attack."""

    @classmethod
    def on_summon_in_combat(cls, source: BaseEntity, game: Game,
                              summoned=None) -> Optional[Action]:
        if summoned is None or summoned.dead or summoned.race != Race.BEAST:
            return None
        if summoned.atk <= 0:
            return None
        return Buff(summoned, atk=summoned.atk, health=0)


class OnSummonMurlocGiveDSScript(OnSummonInCombatGiveDSScript):
    TRIBE = Race.MURLOC
    MAX_USES = 99  # unlimited per combat


class OnSummonMechGiveMechDSScript:
    """After you summon a Mech in combat, give a friendly Mech DS."""

    @classmethod
    def on_summon_in_combat(cls, source: BaseEntity, game: Game,
                              summoned=None) -> Optional[Action]:
        if summoned is None or summoned.race != Race.MECH:
            return None
        mechs = [m for m in source.controller.board
                 if not m.dead and m.race == Race.MECH
                 and not m.has_tag(GameTag.DIVINE_SHIELD)]
        if not mechs:
            return None
        return GainKeyword(game.rng.choice(mechs), GameTag.DIVINE_SHIELD)


# ═══════════════════════════════════════════════════════════════════════════════
# Blood Gem: Bonus Modification + SoC Play BG
# ═══════════════════════════════════════════════════════════════════════════════

class ModifyBloodGemBonusScript:
    """Your Blood Gems give an extra +ATK/+HEALTH."""
    EXTRA_ATK = 0
    EXTRA_HEALTH = 0

    @classmethod
    def modify_blood_gem(cls, source: BaseEntity, game: Game):
        """Return (extra_atk, extra_health) per gem. Called by PlayBloodGems.do()."""
        return (cls.EXTRA_ATK, cls.EXTRA_HEALTH)


class GreatBoarStickerLesserScript(ModifyBloodGemBonusScript):
    """Get 3 Blood Gems. Your Blood Gems give an extra +2/+1."""
    EXTRA_ATK = 2
    EXTRA_HEALTH = 1
    COUNT = 3

    @classmethod
    def on_summon(cls, source, game):
        return [AddToHand(source.controller, "BLOOD_GEM") for _ in range(cls.COUNT)]


class GreatBoarStickerGreaterScript(ModifyBloodGemBonusScript):
    """Get 5 Blood Gems. Your Blood Gems give an extra +3/+3."""
    EXTRA_ATK = 3
    EXTRA_HEALTH = 3
    COUNT = 5

    @classmethod
    def on_summon(cls, source, game):
        return [AddToHand(source.controller, "BLOOD_GEM") for _ in range(cls.COUNT)]


class HogwashBasinScript:
    """Start of Combat: Play 3 Blood Gems on all your minions."""
    COUNT = 3

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        living = _living_board(source.controller)
        if not living:
            return None
        actions = []
        for m in living:
            actions.append(PlayBloodGems(m, cls.COUNT))
        return actions if actions else None


class HoggyBankScript:
    """Start of Combat: Give your Quilboar 'Deathrattle: Get 2 Blood Gems'."""
    TOKEN_ID = "BG20_GEM"  # Blood Gem card
    COUNT = 2

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import GainDeathrattle
        token = cls.TOKEN_ID
        count = cls.COUNT

        def _get_gems(src, g):
            actions = []
            for _ in range(count):
                actions.append(AddToHand(src.controller, token))
            return actions if actions else None

        actions = []
        for m in source.controller.board:
            if not m.dead and m.race == Race.QUILBOAR:
                actions.append(GainDeathrattle(m, _get_gems))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# Magnetic: On Magnetize + EoT Magnetize
# ═══════════════════════════════════════════════════════════════════════════════

class OnMagnetizeBuffScript:
    """Whenever you Magnetize a minion, give it +ATK/+HEALTH and improve this."""
    ATK = 2
    HEALTH = 1
    IMPROVE_ATK = 1
    IMPROVE_HEALTH = 1

    @classmethod
    def on_magnetized(cls, source: BaseEntity, game: Game,
                       host=None, magnetic_minion=None) -> Optional[Action]:
        if host is None or host.dead:
            return None
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        bonus_atk = cls.ATK + counter * cls.IMPROVE_ATK
        bonus_health = cls.HEALTH + counter * cls.IMPROVE_HEALTH
        source.set_tag(GameTag.IMPROVE_COUNTER, counter + 1)
        return Buff(host, atk=bonus_atk, health=bonus_health)


class OnMagnetizeBuff4x4Script(OnMagnetizeBuffScript):
    """Whenever a friendly minion is Magnetized, give it +4/+4."""
    ATK = 4
    HEALTH = 4
    IMPROVE_ATK = 0
    IMPROVE_HEALTH = 0


class OnMagnetizeBuff3x3ImproveScript(OnMagnetizeBuffScript):
    """Whenever you Magnetize, give it +3/+3 and improve this."""
    ATK = 3
    HEALTH = 3
    IMPROVE_ATK = 3
    IMPROVE_HEALTH = 3


class DiscoverMagneticMechScript:
    """Discover 2 Magnetic Mechs."""
    COUNT = 2

    @classmethod
    def start_of_combat(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for _ in range(cls.COUNT):
            from hsrl.core.card_db import CARDS
            magnetic_ids = [
                cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4
                and data.tags.get(GameTag.MAGNETIC)
                and data.tags.get(GameTag.RACE) == Race.MECH
                and not cid.startswith("EXAMPLE")
            ]
            if magnetic_ids:
                actions.append(DiscoverMinion(source.controller,
                                 card_id_filter=set(magnetic_ids)))
        return actions if actions else None


class EoTMagnetizeLeftRightScript:
    """End of Turn: Magnetize a token to your left- and right-most Mechs."""
    TOKEN_ID = ""

    @classmethod
    def end_of_turn(cls, source: BaseEntity, game: Game) -> Optional[Action]:
        board = _living_board(source.controller)
        if not board or not cls.TOKEN_ID:
            return None
        from hsrl.core.actions import AttachMagnetic
        actions = []
        for idx in (0, -1):
            if abs(idx) <= len(board):
                m = board[idx]
                if m.race == Race.MECH:
                    token = game.create_minion(cls.TOKEN_ID)
                    if token:
                        token.controller = source.controller
                        actions.append(AttachMagnetic(token, m))
        return actions if actions else None


class OnPlayMagneticGetSpellScript:
    """After you play a Magnetic minion, get a random Tavern spell."""

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game, played_card=None) -> Optional[Action]:
        if played_card is None:
            return None
        if not played_card.has_tag(GameTag.MAGNETIC):
            return None
        from hsrl.core.card_db import CARDS
        spell_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 3 and data.tags.get(GameTag.TECH_LEVEL)
            and not cid.startswith("EXAMPLE")
        ]
        if not spell_ids:
            return None
        return AddToHand(source.controller, game.rng.choice(spell_ids))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12a: OnDRTrigger → Buff Rightmost
# ═══════════════════════════════════════════════════════════════════════════════

class OnDRTriggerBuffRightmostScript:
    """After you trigger a Deathrattle, give your right-most minion +X/+Y."""
    ATK = 2
    HEALTH = 2

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _atk = cls.ATK
        _health = cls.HEALTH

        class _BuffRightmost(Action):
            def do(self, source_ent, game_ref, target=None):
                board = _living_board(source.controller)
                if not board:
                    return
                game_ref.queue_action(Buff(board[-1], atk=_atk, health=_health))

        listener = EventListener(
            event_name="DEATHRATTLE_TRIGGER",
            action=_BuffRightmost(),
            condition=lambda m: (
                m is not None
                and m.controller == source.controller
            ),
        )
        game.register_listener(source, listener)
        return None


class OnDRTriggerBuffRightmost6x4Script(OnDRTriggerBuffRightmostScript):
    """After you trigger a Deathrattle, give your right-most minion +6/+4."""
    ATK = 6
    HEALTH = 4


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12b: OnPlay → Buff Leftmost Hand
# ═══════════════════════════════════════════════════════════════════════════════

class OnPlayBuffLeftmostHandScript:
    """After you play a minion, give the left-most minion in your hand +X/+Y."""
    ATK = 3
    HEALTH = 2

    @classmethod
    def on_play(cls, source, game, played_card=None):
        # Only trigger when a minion is played (not spell)
        if played_card is None or not hasattr(played_card, 'atk'):
            return None
        hand = source.controller.hand
        if not hand:
            return None
        return Buff(hand[0], atk=cls.ATK, health=cls.HEALTH)


class OnPlayBuffLeftmostHand6x6Script(OnPlayBuffLeftmostHandScript):
    """After you play a minion, give the left-most minion in your hand +6/+6."""
    ATK = 6
    HEALTH = 6


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12c: SimpleGet — pure get card, no secondary effects
# ═══════════════════════════════════════════════════════════════════════════════

class GetElementalOfSurpriseScript:
    """Get an Elemental of Surprise."""
    CARD_ID = "BG26_175"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetSilverGooseScript:
    """Get a Silver Goose."""
    CARD_ID = "BG29_801"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetTwoEndtimesEggsScript:
    """Get 2 Eggs of the Endtimes."""
    CARD_ID = "BG34_639"
    COUNT = 2

    @classmethod
    def on_summon(cls, source, game):
        return [AddToHand(source.controller, cls.CARD_ID) for _ in range(cls.COUNT)]


class EggOfEndtimesPortraitLesserScript:
    """Get an Egg of the Endtimes. At the start of every 2 turns, repeat this."""
    CARD_ID = "BG34_639"
    N = 2

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def on_turn_begin(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.N:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            return AddToHand(source.controller, cls.CARD_ID)
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12d: Get + stats/keyword modification
# ═══════════════════════════════════════════════════════════════════════════════

class GetTimewarpedRadioStarRebornScript:
    """Get a Timewarped Radio Star. Give it Reborn."""
    CARD_ID = "BG34_Giant_330"

    @classmethod
    def on_summon(cls, source, game):
        # Create the minion in hand
        from hsrl.core.card_db import CARDS
        card_data = CARDS.get(cls.CARD_ID)
        if card_data is None:
            return None
        token = game.create_minion(cls.CARD_ID)
        if token is None:
            return None
        token.zone = Zone.HAND
        source.controller.hand.append(token)
        return GainKeyword(token, GameTag.REBORN)


class GetGoldenMishmashAndAmalgamScript:
    """Get a Golden Mishmash and a 10/10 Amalgam with Venomous."""
    MISHMASH_GOLDEN = "TB_BaconShop_HERO_33_Buddy_G"
    AMALGAM = "TB_BaconShop_HP_033t"

    @classmethod
    def on_summon(cls, source, game):
        actions = []
        # Golden Mishmash (already 8/8 golden)
        mishmash = game.create_minion(cls.MISHMASH_GOLDEN)
        if mishmash:
            mishmash.zone = Zone.HAND
            source.controller.hand.append(mishmash)
        # Amalgam: base 2/2, set to 10/10 + Venomous
        amalgam = game.create_minion(cls.AMALGAM)
        if amalgam:
            amalgam.zone = Zone.HAND
            source.controller.hand.append(amalgam)
            actions.append(Buff(amalgam, atk=8, health=8))
            actions.append(GainKeyword(amalgam, GameTag.VENOMOUS))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12e: Every N Turns engine + trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class EveryNTurnsBaseScript:
    """Base class: every N turns, reset counter and call effect().
    Subclasses set N and override effect()."""
    N = 2  # Fire every N turns
    START_COUNTER = 0  # Starting counter value

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, cls.START_COUNTER)
        return None

    @classmethod
    def effect(cls, source, game):
        """Override in subclass. Return Action or list of Actions."""
        raise NotImplementedError

    @classmethod
    def on_turn_begin(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.N:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            result = cls.effect(source, game)
            return result
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


class GoldenizerSupplyScript(EveryNTurnsBaseScript):
    """At the end of every 3 turns, get a Goldenizer."""
    N = 3
    START_COUNTER = 3  # First trigger after 3 turns

    @classmethod
    def effect(cls, source, game):
        return AddToHand(source.controller, "BG26_813t")

    @classmethod
    def end_of_turn(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.N:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            return AddToHand(source.controller, "BG26_813t")
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


class DuplicatingLensScript:
    """Get a copy of the first minion you summon each combat.

    Formal spec:
      1. on_summon: reset per-combat flag
      2. on_summon_in_combat: first minion summoned → add copy to hand
      3. start_of_combat: reset flag for new combat
    """

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_summon_in_combat(cls, source, game, summoned=None):
        if source.get_tag(GameTag.TRINKET_COUNTER, 0) >= 1:
            return None
        if summoned is None or summoned.dead:
            return None
        if summoned.controller != source.controller:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, 1)
        return AddToHand(source.controller, summoned.data.id)


class LensCaseGetScript(EveryNTurnsBaseScript):
    """At the start of every 2 turns, get a Duplicating Lens."""
    N = 2
    START_COUNTER = 2  # First trigger after 2 turns

    @classmethod
    def effect(cls, source, game):
        return AddToHand(source.controller, "BG35_MagicItem_817t")


class ConchPortraitScript(EveryNTurnsBaseScript):
    """At the start of every 2 turns, get another Cloning Conch."""
    N = 2
    START_COUNTER = 2

    @classmethod
    def on_summon(cls, source, game):
        # First get a Cloning Conch immediately
        actions = [AddToHand(source.controller, "BG28_601")]
        source.set_tag(GameTag.TRINKET_COUNTER, cls.START_COUNTER)
        return actions

    @classmethod
    def effect(cls, source, game):
        return AddToHand(source.controller, "BG28_601")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12f: Delayed Gain Gold / Other
# ═══════════════════════════════════════════════════════════════════════════════

class DelayedGainGold10Script:
    """In two turns, gain 10 Gold. (Once per game.)"""
    DELAY = 2
    GOLD = 10

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, cls.DELAY)
        return None

    @classmethod
    def on_turn_begin(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter <= 0:
            return None  # Already triggered
        counter -= 1
        if counter == 0:
            source.set_tag(GameTag.TRINKET_COUNTER, -1)  # Prevent re-trigger
            return GainGold(source.controller, cls.GOLD)
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


class DelayedGreaterTrinketGain3Script:
    """Gain 2 Gold. Greater Trinket early purchase timing is TODO."""
    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(GainGold(source.controller, 2), source=source)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12g: OnCastSpell → Buff all
# ═══════════════════════════════════════════════════════════════════════════════

class OnCastSpellBuffAllPermanentScript:
    """Whenever you cast a spell, give your minions +X/+Y permanently."""
    ATK = 1
    HEALTH = 1

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _atk = cls.ATK
        _health = cls.HEALTH

        class _BuffAllOnCast(Action):
            def do(self, source_ent, game_ref, target=None):
                board = _living_board(source.controller)
                if not board:
                    return
                for m in board:
                    game_ref.queue_action(Buff(m, atk=_atk, health=_health))

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffAllOnCast(),
            condition=lambda spell, player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


class OnCastSpellBuffAllPermanentCombatScript(OnCastSpellBuffAllPermanentScript):
    """Whenever you cast a spell, give minions +3/+2 in combat, +1/+1 out.

    DEFERRED: always gives +1/+1. Full implementation needs combat-phase
    context awareness for the +3/+2 in-combat variant.
    """
    ATK = 1
    HEALTH = 1


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 12h: Various other scripts
# ═══════════════════════════════════════════════════════════════════════════════

class SoCMakeHighestTierDragonGoldenScript:
    """Start of Combat: Make your highest-Tier Dragon Golden."""
    @classmethod
    def start_of_combat(cls, source, game):
        dragons = [m for m in source.controller.board if not m.dead and m.race == Race.DRAGON]
        if not dragons:
            return None
        highest = max(dragons, key=lambda m: m.tech_level)
        # Make it golden: set golden flag and double stats
        if not highest.is_golden:
            highest.set_tag(GameTag.GOLDEN, True)
            highest.set_tag(GameTag.ATK, highest.atk * 2)
            highest.set_tag(GameTag.HEALTH, highest.health * 2)
        return None


class CounterAttackPlayBGOnQuilboarScript:
    """After 2 friendly minions attack each combat, play Blood Gem on all Quilboar."""
    COUNT = 2

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_attack(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.COUNT:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            quilboar = [m for m in source.controller.board if not m.dead and m.race == Race.QUILBOAR]
            if quilboar:
                return [PlayBloodGems(q, 1) for q in quilboar]
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


class CounterPirateAttackGainGoldScript:
    """After 2 friendly Pirates attack, gain 1 Gold next turn."""
    COUNT = 2

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_attack(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.COUNT:
            source.set_tag(GameTag.TRINKET_COUNTER, -1)  # fired, gain gold next turn
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        if source.get_tag(GameTag.TRINKET_COUNTER, 0) == -1:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            return GainGold(source.controller, 1)
        return None


class SoTSpinYoggWheelScript:
    """Spin the Wheel of Yogg-Saron. At the start of each turn, spin it again."""
    YOGG_SPELL_IDS = [
        "BG30_MagicItem_994t",  # placeholder - actual Yogg wheel spells
    ]

    @classmethod
    def on_summon(cls, source, game):
        # Spin once on equip
        return CastTavernSpell(source.controller, game.rng.choice(cls.YOGG_SPELL_IDS))

    @classmethod
    def start_of_turn(cls, source, game):
        return CastTavernSpell(source.controller, game.rng.choice(cls.YOGG_SPELL_IDS))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 9: Blood Gem — Avenge/Improved/DR Trigger/EoT
# ═══════════════════════════════════════════════════════════════════════════════

class AvengeImproveBGScript:
    """Avenge(N): Your Blood Gems give an extra +ATK/+HEALTH this game."""
    ATK_BONUS = 0
    HEALTH_BONUS = 1

    @classmethod
    def avenge(cls, source, game):
        return ImproveBloodGem(source.controller,
                                atk_bonus=cls.ATK_BONUS,
                                health_bonus=cls.HEALTH_BONUS)


class AvengeImproveBG1HealthScript(AvengeImproveBGScript):
    """Avenge(4): Blood Gems give +1 Health."""
    ATK_BONUS = 0
    HEALTH_BONUS = 1


class AvengeImproveBG1x1Script(AvengeImproveBGScript):
    """Avenge(4): Blood Gems give +1/+1."""
    ATK_BONUS = 1
    HEALTH_BONUS = 1


class EoTPlayBGOnEachTribeScript:
    """End of Turn: Play 7 Blood Gems on a friendly minion of each type."""
    COUNT = 7

    @classmethod
    def end_of_turn(cls, source, game):
        # Group living minions by race
        tribes = {}
        for m in source.controller.board:
            if not m.dead and m.race != Race.INVALID:
                tribes.setdefault(m.race, []).append(m)
        if not tribes:
            return None
        actions = []
        for tribe, minions in tribes.items():
            target = game.rng.choice(minions)
            actions.append(PlayBloodGems(target, cls.COUNT))
        return actions if actions else None


class OnDRTriggerPlayBGRandomScript:
    """After you trigger a Deathrattle, play a Blood Gem on 3 random minions."""
    COUNT = 3

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _count = cls.COUNT

        class _PlayBGOnDR(Action):
            def do(self, source_ent, game_ref, target=None):
                living = _living_board(source.controller)
                if not living:
                    return
                targets = game.rng.sample(living, min(_count, len(living)))
                for t in targets:
                    game_ref.queue_action(PlayBloodGems(t, 1))

        listener = EventListener(
            event_name="DEATHRATTLE_TRIGGER",
            action=_PlayBGOnDR(),
            condition=lambda m: (
                m is not None
                and m.controller == source.controller
            ),
        )
        game.register_listener(source, listener)
        return None


class OnDRTriggerImproveBGTempScript:
    """After you trigger a Deathrattle, your Blood Gems give +2/+1 until next combat."""
    ATK_PER = 2
    HEALTH_PER = 1

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_deathrattle_triggered(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None

    @classmethod
    def modify_blood_gem(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return (counter * cls.ATK_PER, counter * cls.HEALTH_PER)
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# Phase 10: Magnetic + Spellcraft + EoT/SoT repeat Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class AccordOTronPortraitScript:
    """At end of turn, Magnetize an Accord-o-Tron to left- and right-most Mechs."""
    ACCORD_CARD_ID = "BG26_147"

    @classmethod
    def end_of_turn(cls, source, game):
        board = _living_board(source.controller)
        mechs = [m for m in board if m.race == Race.MECH]
        if not mechs:
            return None
        # Find leftmost and rightmost mechs
        leftmost = mechs[0]
        rightmost = mechs[-1]
        actions = []
        # Create Accord-o-Tron for leftmost mech
        acc1 = game.create_minion(cls.ACCORD_CARD_ID)
        if acc1 is not None:
            acc1.controller = source.controller
            actions.append(AttachMagnetic(acc1, leftmost))
        # Create Accord-o-Tron for rightmost mech (if different)
        if rightmost is not leftmost:
            acc2 = game.create_minion(cls.ACCORD_CARD_ID)
            if acc2 is not None:
                acc2.controller = source.controller
                actions.append(AttachMagnetic(acc2, rightmost))
        return actions if actions else None


class TrinketSpellcraft3030Script:
    """Spellcraft: Give a minion +30/+30 until next turn."""
    SC_SPELL_ID = "BG30_MagicItem_714t"

    @classmethod
    def spellcraft(cls, source, game):
        return cls.SC_SPELL_ID


class TrinketSpellcraftMurlocKeywordScript:
    """Spellcraft: Give a Murloc a random Bonus Keyword."""
    SC_SPELL_ID = "BG32_MagicItem_892t"

    @classmethod
    def spellcraft(cls, source, game):
        return cls.SC_SPELL_ID


class TrinketSpellcraftBeastBuffRebornScript:
    """Spellcraft: Give a Beast +2/+2 and Reborn."""
    SC_SPELL_ID = "BG35_MagicItem_872t"

    @classmethod
    def spellcraft(cls, source, game):
        return cls.SC_SPELL_ID


class TrinketSpellcraftDestroyUndeadScript:
    """Spellcraft: Destroy a friendly Undead to get a random Undead."""
    SC_SPELL_ID = "BG35_MagicItem_306t"

    @classmethod
    def spellcraft(cls, source, game):
        return cls.SC_SPELL_ID


class TrinketSpellcraftDestroyUndead2Script:
    """Spellcraft: Destroy a friendly Undead to get 2 random Undead."""
    SC_SPELL_ID = "BG35_MagicItem_733t"

    @classmethod
    def spellcraft(cls, source, game):
        return cls.SC_SPELL_ID


class EoTGetRandomMinionPerTribeScript:
    """At end of turn, get a random minion of each different type you control."""

    @classmethod
    def end_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        # Gather unique tribes from board
        tribes = set()
        for m in source.controller.board:
            if not m.dead and m.race != Race.INVALID:
                tribes.add(m.race)
        if not tribes:
            return None
        actions = []
        for tribe in tribes:
            pool = [cid for cid, data in CARDS._cards.items()
                    if data.cardtype == 4
                    and data.tags.get(GameTag.RACE) == tribe
                    and not cid.startswith('EXAMPLE')]
            if pool:
                actions.append(AddToHand(source.controller, game.rng.choice(pool)))
        return actions if actions else None


class EoTStealHighestTavernRepeatScript:
    """Steal highest-Tier card from Tavern. At EoT, repeat this."""

    @classmethod
    def on_summon(cls, source, game):
        return EoTStealHighestTavernRepeatScript._steal_highest(source, game)

    @classmethod
    def end_of_turn(cls, source, game):
        return EoTStealHighestTavernRepeatScript._steal_highest(source, game)

    @staticmethod
    def _steal_highest(source, game):
        tavern = [m for m in source.controller.tavern if not m.dead]
        if not tavern:
            return None
        highest = max(tavern, key=lambda m: m.get_tag(GameTag.TECH_LEVEL, 1))
        # "Steal" = remove from tavern, add to hand
        source.controller.tavern.remove(highest)
        highest.zone = Zone.HAND
        highest.controller = source.controller
        source.controller.hand.append(highest)
        return None  # No queue action needed, side effects handled above


class SoTGetCopyLastOpponentHighestScript:
    """At SoT, get a plain copy of the highest-Tier minion in last opponent's warband."""

    @classmethod
    def start_of_turn(cls, source, game):
        if not hasattr(source.controller, 'last_opponent_board') or \
           not source.controller.last_opponent_board:
            return None
        if not source.controller.last_opponent_board:
            return None
        highest = max(source.controller.last_opponent_board,
                      key=lambda m: m.get_tag(GameTag.TECH_LEVEL, 1))
        if highest is None:
            return None
        return AddToHand(source.controller, highest.get_tag(GameTag.CARD_ID))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 10b: SoT Repeat Get (get X cards each SoT)
# ═══════════════════════════════════════════════════════════════════════════════

class SoTGetRandomSpellcraftScript:
    """Get 3 random Spellcraft spells. At SoT, get 3 more."""
    COUNT = 3

    @classmethod
    def on_summon(cls, source, game):
        return cls._get_spellcraft_spells(source, game)

    @classmethod
    def start_of_turn(cls, source, game):
        return cls._get_spellcraft_spells(source, game)

    @classmethod
    def _get_spellcraft_spells(cls, source, game):
        from hsrl.core.card_db import CARDS
        sc_pool = [cid for cid, data in CARDS._cards.items()
                   if data.cardtype == CardType.SPELL
                   and data.tags.get(GameTag.SPELLCRAFT)
                   and not cid.startswith('EXAMPLE')]
        if not sc_pool:
            return None
        count = min(cls.COUNT, len(sc_pool))
        chosen = game.rng.sample(sc_pool, count)
        return [AddToHand(source.controller, cid) for cid in chosen]


class SoTRepeatGetGrittyHeadhunterScript:
    """Get a Gritty Headhunter. At SoT, repeat this."""
    CARD_ID = "BG26_155"  # Gritty Headhunter

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def start_of_turn(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class SoTRepeatGetPrivateerScript:
    """Get a Proud Privateer + 2 random Bounties. At SoT, get another 2 Bounties."""
    PRIVATEER_ID = "BG26_166"  # Proud Privateer

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        actions = [AddToHand(source.controller, cls.PRIVATEER_ID)]
        # Get 2 random Bounty spells
        bounty_pool = [cid for cid, data in CARDS._cards.items()
                       if data.cardtype == CardType.SPELL
                       and 'Bounty' in (getattr(data, 'name', '') or '')
                       and not cid.startswith('EXAMPLE')]
        if bounty_pool:
            chosen = game.rng.sample(bounty_pool, min(2, len(bounty_pool)))
            for cid in chosen:
                actions.append(AddToHand(source.controller, cid))
        return actions

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        bounty_pool = [cid for cid, data in CARDS._cards.items()
                       if data.cardtype == CardType.SPELL
                       and 'Bounty' in (getattr(data, 'name', '') or '')
                       and not cid.startswith('EXAMPLE')]
        if not bounty_pool:
            return None
        chosen = game.rng.sample(bounty_pool, min(2, len(bounty_pool)))
        return [AddToHand(source.controller, cid) for cid in chosen]


class SoTGoldenRandomMinionScript:
    """Make a random friendly minion (Tier 4 or below) Golden. At SoT, repeat."""
    MAX_TIER = 4

    @classmethod
    def start_of_turn(cls, source, game):
        eligible = [m for m in source.controller.board
                    if not m.dead
                    and not m.is_golden
                    and m.get_tag(GameTag.TECH_LEVEL, 1) <= cls.MAX_TIER]
        if not eligible:
            return None
        target = game.rng.choice(eligible)
        target.set_tag(GameTag.GOLDEN, True)
        target.atk = target.atk * 2
        target.health = target.health * 2
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 11: Refresh + Avenge + SoC Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class AvengeImproveTavernSpellScript:
    """Avenge(N): Your Tavern spells give an extra +X/+Y this game."""
    ATK_BONUS = 1
    HEALTH_BONUS = 0

    @classmethod
    def avenge(cls, source, game):
        return ImproveTavernSpellBuff(source.controller,
                                       atk_bonus=cls.ATK_BONUS,
                                       health_bonus=cls.HEALTH_BONUS)


class AvengeImproveTavernSpell1x1Script(AvengeImproveTavernSpellScript):
    """Avenge(4): Your Tavern spells give an extra +1/+1 this game."""
    ATK_BONUS = 1
    HEALTH_BONUS = 1


class OnRefreshBuffTavernMinionsScript:
    """After Tavern Refresh, give its minions +X/+Y this turn."""
    ATK = 2
    HEALTH = 2

    @classmethod
    def on_tavern_refresh(cls, source, game):
        tavern = [m for m in source.controller.tavern if not m.dead]
        if not tavern:
            return None
        return [Buff(m, atk=cls.ATK, health=cls.HEALTH, temporary=True) for m in tavern]


class OnRefreshBuffMurlocsTavernScript:
    """After Refresh, give Murlocs in Tavern +5/+5 and a random Bonus Keyword."""
    BONUS_KEYWORDS = [
        GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.WINDFURY,
        GameTag.REBORN, GameTag.POISONOUS,
    ]

    @classmethod
    def on_tavern_refresh(cls, source, game):
        tavern = source.controller.tavern
        murlocs = [m for m in tavern if not m.dead and m.race == Race.MURLOC]
        if not murlocs:
            return None
        actions = []
        for m in murlocs:
            actions.append(Buff(m, atk=5, health=5))
            actions.append(GainKeyword(m, game.rng.choice(cls.BONUS_KEYWORDS)))
        return actions


class OnRefreshTransferHighestToLowestScript:
    """After Refresh, give stats of highest-ATK tavern minion to lowest."""

    @classmethod
    def on_tavern_refresh(cls, source, game):
        tavern = [m for m in source.controller.tavern if not m.dead]
        if len(tavern) < 2:
            return None
        highest = max(tavern, key=lambda m: m.atk)
        lowest = min(tavern, key=lambda m: m.atk)
        if highest is lowest:
            return None
        if highest.atk > 0:
            actions = [Buff(lowest, atk=highest.atk, health=0)]
        else:
            return None
        if highest.health > 0:
            actions.append(Buff(lowest, atk=0, health=highest.health))
        return actions


class SoCBuffOnePerTribeImproveScript:
    """SoC: Give a friendly minion of each type +X/+Y. Improve permanently."""
    ATK = 3
    HEALTH = 2

    @classmethod
    def start_of_combat(cls, source, game):
        # Group by tribe
        tribes = {}
        for m in source.controller.board:
            if not m.dead and m.race != Race.INVALID:
                tribes.setdefault(m.race, []).append(m)
        if not tribes:
            return None
        # Current improved values
        atk = cls.ATK + source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        health = cls.HEALTH + source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        actions = []
        for tribe, minions in tribes.items():
            target = game.rng.choice(minions)
            actions.append(Buff(target, atk=atk, health=health))
        # Improve for next turn
        actions.append(IncrementImproveCounter(source, 1))
        return actions


class SoCBuffNagaImprovePerSpellsScript:
    """SoC: Give Naga +X Health. Improved by every N spells cast this game."""
    BASE_HEALTH = 1
    SPELLS_PER_IMPROVE = 4

    @classmethod
    def start_of_combat(cls, source, game):
        spells_cast = source.controller.get_tag(GameTag.TAVERN_SPELLS_CAST_THIS_GAME, 0)
        improves = spells_cast // cls.SPELLS_PER_IMPROVE
        health_bonus = cls.BASE_HEALTH + improves
        nagas = [m for m in source.controller.board if not m.dead and m.race == Race.NAGA]
        if not nagas:
            return None
        return [Buff(m, atk=0, health=health_bonus) for m in nagas]


class AvengeTransferATKScript:
    """Avenge(3): Give ATK of right-most minion to another friendly Dragon."""

    @classmethod
    def avenge(cls, source, game):
        board = _living_board(source.controller)
        if len(board) < 2:
            return None
        rightmost = board[-1]
        if rightmost.atk <= 0:
            return None
        dragons = [m for m in board if m.race == Race.DRAGON and m is not rightmost]
        if not dragons:
            return None
        target = game.rng.choice(dragons)
        return Buff(target, atk=rightmost.atk, health=0)


class SoCTriggerAllFriendlyDRScript:
    """SoC: Trigger all friendly Deathrattles."""

    @classmethod
    def start_of_combat(cls, source, game):
        actions = []
        for m in source.controller.board:
            if not m.dead and m.deathrattle:
                dr_fn = m.deathrattle
                if dr_fn is not None and callable(dr_fn):
                    result = dr_fn(m, game)
                    if result is not None:
                        if isinstance(result, (list, tuple)):
                            actions.extend(result)
                        else:
                            actions.append(result)
        return actions if actions else None


class OnBuyBuffMurlocTeachSpellScript:
    """After you buy a Tavern spell, get a 1/1 Murloc and teach it that spell."""
    COUNTER_MAX = 2  # 2 times per turn

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_spell_cast(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter >= cls.COUNTER_MAX:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, counter + 1)
        from hsrl.core.card_db import CARDS
        # Create a 1/1 Murloc Scout token
        token_id = "BG20_HERO_201p"
        actions = [AddToHand(source.controller, token_id)]
        # Get the spell card_id that was cast
        spell_cid = kwargs.get('spell_card_id')
        if spell_cid:
            actions.append(AddToHand(source.controller, spell_cid))
        return actions


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 11b: Simple SoC / Get Card trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class SoCBuffBeastsCombatImproveOnSummonScript:
    """SoC: Your Beasts have +1/+1 this combat. After you summon a Beast, improve."""
    @classmethod
    def start_of_combat(cls, source, game):
        improves = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        atk = 1 + improves
        health = 1 + improves
        beasts = [m for m in source.controller.board if not m.dead and m.race == Race.BEAST]
        return [Buff(m, atk=atk, health=health) for m in beasts] if beasts else None

    @classmethod
    def on_summon_in_combat(cls, source, game, **kwargs):
        summoned = kwargs.get('summoned') or kwargs.get('minion')
        if summoned is not None and getattr(summoned, 'race', None) == Race.BEAST:
            return IncrementImproveCounter(source, 1)
        return None


class SoCGiveMurlocsHandATKScript:
    """SoC: Give your Murlocs the ATK of the highest-ATK minion in your hand."""

    @classmethod
    def start_of_combat(cls, source, game):
        hand = source.controller.hand
        if not hand:
            return None
        highest = max(hand, key=lambda m: m.atk)
        if highest.atk <= 0:
            return None
        murlocs = [m for m in source.controller.board if not m.dead and m.race == Race.MURLOC]
        if not murlocs:
            return None
        return [Buff(m, atk=highest.atk, health=0) for m in murlocs]


class SoCSummonGoldenFishNZothScript:
    """SoC: Summon a Golden Fish of N'Zoth that copies Deathrattles."""
    FISH_CARD_ID = "TB_BaconUps_307"

    @classmethod
    def start_of_combat(cls, source, game):
        if len(source.controller.board) >= 7:
            return None
        fish = game.create_minion(cls.FISH_CARD_ID)
        if fish is None:
            return None
        # Fish of N'Zoth copies Deathrattles - simplified as Summon
        return Summon(source.controller, fish)


class DiscoverTier3DarkmoonPrizeScript:
    """Discover a Tier 3 Darkmoon Prize."""
    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        # Darkmoon Prizes - find spell cards from DMF set
        prize_pool = [cid for cid, data in CARDS._cards.items()
                      if data.cardtype == CardType.SPELL
                      and 'dmf' in cid.lower()
                      and not cid.startswith('EXAMPLE')]
        if not prize_pool:
            return None
        return DiscoverSpell(source.controller, prize_pool)


class DiscoverTier6MinionSetStatsScript:
    """Discover a Tier 6 minion. Set its stats to X/X."""
    STATS = (12, 12)

    @classmethod
    def on_summon(cls, source, game):
        return DiscoverMinion(source.controller, min_tier=6, max_tier=6)


class DiscoverTwoTier6SetStatsScript(DiscoverTier6MinionSetStatsScript):
    """Discover two Tier 6 minions. Set their stats to 20/20."""
    STATS = (20, 20)

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        # Discover two Tier 6 minions
        return [DiscoverMinion(source.controller, min_tier=6, max_tier=6) for _ in range(2)]


class OnBuyGetMagneticSatelliteScript:
    """First time you buy a minion each turn, get a Magnetic Satellite with its stats."""
    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_minion_bought(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, 1)
        # Magnetic Satellite card - BG31_171t
        return AddToHand(source.controller, "BG31_171t")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 13: SoC + Easy-Win Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class SoCTripleTribelessStatsScript:
    """Start of Combat: Triple the stats of your minions with no type."""
    @classmethod
    def start_of_combat(cls, source, game):
        tribeless = [m for m in source.controller.board
                     if not m.dead and m.race == Race.INVALID]
        if not tribeless:
            return None
        # Triple = add 2x current stats
        return [Buff(m, atk=m.atk * 2, health=m.health * 2) for m in tribeless]


class SoCSummonCopyLeftmostScript:
    """Start of Combat: Summon a copy of your left-most minion."""
    @classmethod
    def start_of_combat(cls, source, game):
        board = _living_board(source.controller)
        if not board or len(board) >= 7:
            return None
        # Summon a copy of the leftmost
        original = board[0]
        copy_minion = game.create_minion(original.get_tag(GameTag.CARD_ID))
        if copy_minion is None:
            return None
        # Copy buffs by setting tags directly
        copy_minion.set_tag(GameTag.ATK, original.atk)
        copy_minion.set_tag(GameTag.HEALTH, original.health)
        # Copy keywords
        for kw in [GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.WINDFURY,
                    GameTag.REBORN, GameTag.POISONOUS, GameTag.VENOMOUS]:
            if original.has_tag(kw):
                copy_minion.set_tag(kw, True)
        return Summon(source.controller, copy_minion)


class SoCSummonAndGetPirateAttackScript:
    """Start of Combat: Summon and get a random Pirate. It attacks immediately."""
    @classmethod
    def start_of_combat(cls, source, game):
        if len(source.controller.board) >= 7:
            return None
        from hsrl.core.card_db import CARDS
        pirate_pool = [cid for cid, data in CARDS._cards.items()
                       if data.cardtype == CardType.MINION
                       and data.tags.get(GameTag.RACE) == Race.PIRATE
                       and not cid.startswith('EXAMPLE')]
        if not pirate_pool:
            return None
        chosen_id = game.rng.choice(pirate_pool)
        pirate = game.create_minion(chosen_id)
        if pirate is None:
            return None
        actions = [Summon(source.controller, pirate)]
        actions.append(AttackImmediately(pirate))
        return actions


class SoCGiveElementalFrostlingDRScript:
    """SoC: Give 2 friendly Elementals 'Deathrattle: Summon a Flourishing Frostling'."""
    FROSTLING_ID = "BG34_501"  # Flourishing Frostling

    @classmethod
    def start_of_combat(cls, source, game):
        elementals = [m for m in source.controller.board
                      if not m.dead and m.race == Race.ELEMENTAL]
        if not elementals:
            return None
        targets = game.rng.sample(elementals, min(2, len(elementals)))
        actions = []
        for t in targets:
            token_id = cls.FROSTLING_ID

            def make_dr(minion, tid=token_id):
                def dr(source_minion, g):
                    token = g.create_minion(tid)
                    if token:
                        return Summon(source_minion.controller, token)
                    return None
                return dr

            actions.append(GainDeathrattle(t, make_dr(t)))
        return actions


class SoCGivePirateSkyPirateDRScript:
    """SoC: Give 3 friendly Pirates 'Deathrattle: Summon an attacking Sky Pirate'."""
    SKY_PIRATE_ID = "BGS_061t"
    TARGET_COUNT = 3

    @classmethod
    def start_of_combat(cls, source, game):
        pirates = [m for m in source.controller.board
                   if not m.dead and m.race == Race.PIRATE]
        if not pirates:
            return None
        targets = game.rng.sample(pirates, min(cls.TARGET_COUNT, len(pirates)))
        actions = []
        for t in targets:
            token_id = cls.SKY_PIRATE_ID

            def make_dr(minion, tid=token_id):
                def dr(source_minion, g):
                    token = g.create_minion(tid)
                    if token:
                        token.set_tag(GameTag.ATK, token.atk + source_minion.atk)
                        return [
                            Summon(source_minion.controller, token),
                            AttackImmediately(token),
                        ]
                    return None
                return dr

            actions.append(GainDeathrattle(t, make_dr(t)))
        return actions


class SoCMakeHighestTierDragonGoldenScript:
    """Start of Combat: Make your highest-Tier Dragon Golden."""
    @classmethod
    def start_of_combat(cls, source, game):
        dragons = [m for m in source.controller.board
                   if not m.dead and m.race == Race.DRAGON]
        if not dragons:
            return None
        highest = max(dragons, key=lambda m: m.tech_level)
        if not highest.is_golden:
            highest.set_tag(GameTag.GOLDEN, True)
            highest.set_tag(GameTag.ATK, highest.atk * 2)
            highest.set_tag(GameTag.HEALTH, highest.health * 2)
        return None


class OnCastSpellBuffUndeadWhereverScript:
    """After you cast a Tavern spell, your Undead have +X Attack this game (wherever they are)."""
    ATK_BONUS = 1

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_spell_cast(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        # Apply +ATK to all undead on board and in hand
        undead = []
        for m in source.controller.board:
            if not m.dead and m.race == Race.UNDEAD:
                undead.append(m)
        for m in source.controller.hand:
            if not m.dead and m.race == Race.UNDEAD:
                undead.append(m)
        if undead:
            return [Buff(m, atk=cls.ATK_BONUS, health=0) for m in undead]
        return None


class OnCastSpellBuffUndeadWherever2Script(OnCastSpellBuffUndeadWhereverScript):
    """After you cast a Tavern spell, your Undead have +2 Attack this game."""
    ATK_BONUS = 2


class SoCGiveMurlocsHandATKScript:
    """SoC: Give your Murlocs the ATK of the highest-ATK minion in your hand."""
    @classmethod
    def start_of_combat(cls, source, game):
        hand = source.controller.hand
        if not hand:
            return None
        highest = max(hand, key=lambda m: m.atk)
        if highest.atk <= 0:
            return None
        murlocs = [m for m in source.controller.board
                   if not m.dead and m.race == Race.MURLOC]
        if not murlocs:
            return None
        return [Buff(m, atk=highest.atk, health=0) for m in murlocs]


class OnBuyGetRandomPirateScript:
    """After you buy a Pirate, get a random Pirate."""
    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_minion_bought(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return None
        # Check if bought minion was a Pirate
        bought = kwargs.get('minion') or kwargs.get('bought')
        if bought is not None and getattr(bought, 'race', None) == Race.PIRATE:
            source.set_tag(GameTag.TRINKET_COUNTER, 1)
            from hsrl.core.card_db import CARDS
            pirate_pool = [cid for cid, data in CARDS._cards.items()
                           if data.cardtype == CardType.MINION
                           and data.tags.get(GameTag.RACE) == Race.PIRATE
                           and not cid.startswith('EXAMPLE')]
            if pirate_pool:
                return AddToHand(source.controller, game.rng.choice(pirate_pool))
        return None


class SoCSummonMechCopyFirstDeadScript:
    """When you have space, summon an exact copy of your first Mech that died each combat."""
    @classmethod
    def start_of_combat(cls, source, game):
        # Reset tracking
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_death_combat(cls, source, game, **kwargs):
        if source.get_tag(GameTag.TRINKET_COUNTER, 0) > 0:
            return None
        dead = kwargs.get('dead_minion')
        if dead is not None and dead.race == Race.MECH:
            source.set_tag(GameTag.TRINKET_COUNTER, 1)
            # Store the card ID for later summoning
            source.set_tag(GameTag.TRINKET_COUNTER_TARGET, dead.get_tag(GameTag.CARD_ID))
            # Summon copy at end of combat or when space available
            if len(source.controller.board) < 7:
                copy_minion = game.create_minion(dead.get_tag(GameTag.CARD_ID))
                if copy_minion:
                    return Summon(source.controller, copy_minion)
        return None


class SoTSpinYoggWheelScript:
    """Spin the Wheel of Yogg-Saron. At the start of each turn, spin it again.

    Yogg wheel effects (subset of the full 20-effect table):
      1. +4/+4 to all friendly minions
      2. Deal 5 damage to a random enemy hero
      3. Gain 4 Gold
      4. Get a random minion of your tavern tier
      5. Give a random friendly minion +8/+8
      6. Refresh the tavern (free)
    """

    @classmethod
    def on_summon(cls, source, game):
        return cls._spin(source, game)

    @classmethod
    def start_of_turn(cls, source, game):
        return cls._spin(source, game)

    @classmethod
    def _spin(cls, source, game):
        board = _living_board(source.controller)
        effect = game.rng.choice([
            "_buff_all", "_damage_hero", "_gain_gold",
            "_random_minion", "_buff_one", "_free_refresh",
        ])
        if effect == "_buff_all":
            return [Buff(m, atk=4, health=4) for m in board] if board else None
        elif effect == "_damage_hero":
            enemies = [p for p in game.players
                       if p is not source.controller and p.is_alive]
            if enemies:
                from hsrl.core.actions import DealDamageToHero
                return DealDamageToHero(game.rng.choice(enemies), 5)
            return None
        elif effect == "_gain_gold":
            return GainGold(source.controller, 4)
        elif effect == "_random_minion":
            tier = source.controller.tavern_tier
            from hsrl.core.card_db import CARDS
            pool = [cid for cid, data in CARDS._cards.items()
                    if data.cardtype == 4 and data.tech_level == tier
                    and not cid.startswith("EXAMPLE")]
            if pool:
                return AddToHand(source.controller, game.rng.choice(pool))
            return None
        elif effect == "_buff_one":
            if board:
                return Buff(game.rng.choice(board), atk=8, health=8)
            return None
        elif effect == "_free_refresh":
            source.controller.set_tag(GameTag.FREE_REFRESH_REMAINING,
                                      source.controller.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) + 1)
            return None
        return None


class CounterSpendGoldDoubleATKScript:
    """When you spend 20 Gold, double your minions' Attack. (Twice per game.)"""
    TRIGGER = 20
    MAX_USES = 2

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)  # gold spent tracker
        source.set_tag(GameTag.TRINKET_COUNTER_TARGET, 0)  # use count
        return None

    @classmethod
    def on_spend_gold(cls, source, game, **kwargs):
        spent = kwargs.get('amount', 0)
        uses = source.get_tag(GameTag.TRINKET_COUNTER_TARGET, 0)
        if uses >= cls.MAX_USES:
            return None
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + spent
        if counter >= cls.TRIGGER:
            source.set_tag(GameTag.TRINKET_COUNTER, counter - cls.TRIGGER)
            source.set_tag(GameTag.TRINKET_COUNTER_TARGET, uses + 1)
            board = _living_board(source.controller)
            if board:
                # Double ATK
                return [Buff(m, atk=m.atk, health=0) for m in board]
        else:
            source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


class AvengeDiscoverBCAndTriggerBCScript:
    """Avenge (2): Trigger a friendly Battlecry."""
    @classmethod
    def avenge(cls, source, game):
        board = _living_board(source.controller)
        bc_minions = [m for m in board if m.battlecry]
        if not bc_minions:
            return None
        target = game.rng.choice(bc_minions)
        bc_fn = target.battlecry
        if bc_fn is not None and callable(bc_fn):
            return bc_fn(target, game)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 13b: Simple Get (no secondary) — additional cards
# ═══════════════════════════════════════════════════════════════════════════════

class GetTemperatureShiftScript:
    """Get a Temperature Shift."""
    CARD_ID = "BG31_819"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetSnarlingConductorScript:
    """Get a Snarling Conductor."""
    CARD_ID = "BG28_585"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 14: Final Easy-Win Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class SoCGiveNagaSpellcraftDRScript:
    """SoC: Give your Naga 'Deathrattle: Get a random Spellcraft spell'."""
    @classmethod
    def start_of_combat(cls, source, game):
        from hsrl.core.card_db import CARDS
        naga = [m for m in source.controller.board
                if not m.dead and m.race == Race.NAGA]
        if not naga:
            return None
        # Build pool of Spellcraft spell cards
        sc_spell_pool = [
            "BG23_004t", "BG23_007t", "BG23_008t",
            "BG26_501t", "BG31_920t", "BG33_319t",
            "BG30_MagicItem_714t", "BG32_MagicItem_892t",
            "BG35_MagicItem_872t", "BG35_MagicItem_306t",
            "BG35_MagicItem_733t",
        ]
        actions = []
        for t in naga:
            def make_dr(minion, pool=list(sc_spell_pool)):
                def dr(source_minion, g):
                    spell_id = g.rng.choice(pool)
                    return AddToHand(source_minion.controller, spell_id)
                return dr
            actions.append(GainDeathrattle(t, make_dr(t)))
        return actions


class OnPlayNagaGetSpellcraftScript:
    """After you play a Naga, get a random Spellcraft spell."""
    @classmethod
    def on_play(cls, source, game, played_card=None):
        if played_card is None or not hasattr(played_card, 'race'):
            return None
        if played_card.race != Race.NAGA:
            return None
        sc_spell_pool = [
            "BG23_004t", "BG23_007t", "BG23_008t",
            "BG26_501t", "BG31_920t", "BG33_319t",
        ]
        return AddToHand(source.controller, game.rng.choice(sc_spell_pool))


class OnPlayDemonDealDamageToHeroScript:
    """After you play a Demon, deal 1 damage to your hero."""
    @classmethod
    def on_summon(cls, source, game):
        # Grant 5 armor on equip
        controller = source.controller
        current_armor = controller.get_tag(GameTag.ARMOR, 0)
        controller.set_tag(GameTag.ARMOR, current_armor + 5)
        return None

    @classmethod
    def on_play(cls, source, game, played_card=None):
        if played_card is None or not hasattr(played_card, 'race'):
            return None
        if played_card.race != Race.DEMON:
            return None
        return DealDamageToHero(source.controller, 1)


class OnPlayElementalDiscountNextSpellScript:
    """After you play an Elemental, your next Tavern spell costs (1) less."""
    @classmethod
    def on_play(cls, source, game, played_card=None):
        if played_card is None or not hasattr(played_card, 'race'):
            return None
        if played_card.race != Race.ELEMENTAL:
            return None
        return SetNextSpellDiscount(source.controller, 1)


class SoCGiveNagaDRScript:
    """SoC: Give your Naga a Deathrattle that gets a random Spellcraft spell."""
    # Alias — already have SoCGiveNagaSpellcraftDRScript above
    pass


class FirstSpellEachTurnExtraTimeScript:
    """Your first spell each turn casts an extra time."""
    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_spell_cast(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, 1)
        # Re-cast the same spell
        spell = kwargs.get('spell')
        if spell:
            return CastTavernSpell(source.controller, spell.get_tag(GameTag.CARD_ID))
        return None


class OnBuyGetDoubloonGrifterScript:
    """Get a Doubloon Grifter. The first Pirate you buy each turn is free."""
    CARD_ID = "BG31_826"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class OnBuyFirstPirateFreeScript:
    """The first Pirate you buy each turn is free."""
    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_minion_bought(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return None
        bought = kwargs.get('minion') or kwargs.get('bought')
        if bought is not None and getattr(bought, 'race', None) == Race.PIRATE:
            source.set_tag(GameTag.TRINKET_COUNTER, 1)
            # DEFERRED: refunds gold after purchase (full fix needs 0-cost during buy)
            return GainGold(source.controller, bought.get_tag(GameTag.COST, 3))
        return None


class SoCGetNagaSpellcraftDRCopyScript:
    """SoC: Give your Naga 'Deathrattle: Get a random Spellcraft spell'."""
    # Same as SoCGiveNagaSpellcraftDRScript
    pass


class SummonCounterGetRandomBeastScript:
    """After you summon 6 Beasts, get a random Beast."""
    TARGET = 6

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_summon_in_combat(cls, source, game, **kwargs):
        summoned = kwargs.get('summoned') or kwargs.get('minion')
        if summoned is None or getattr(summoned, 'race', None) != Race.BEAST:
            return None
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.TARGET:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            from hsrl.core.card_db import CARDS
            beast_pool = [cid for cid, data in CARDS._cards.items()
                          if data.cardtype == CardType.MINION
                          and data.tags.get(GameTag.RACE) == Race.BEAST
                          and not cid.startswith('EXAMPLE')]
            if beast_pool:
                return AddToHand(source.controller, game.rng.choice(beast_pool))
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 15: Easy-Win Trinkets (Existing Engines)
# ═══════════════════════════════════════════════════════════════════════════════

# ════════════════ Phase 15a: on_friendly_damage → buff random ══════════════════

class OnFriendlyDamageBuffRandomScript:
    """Whenever a friendly minion takes damage, give a random friendly +X ATK."""
    ATK_BONUS = 3

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _atk = cls.ATK_BONUS

        class _BuffRandomOnFriendlyDamage(Action):
            def do(self, source_ent, game_ref, target=None):
                board = _living_board(source.controller)
                if not board:
                    return
                chosen = game.rng.choice(board)
                game_ref.queue_action(Buff(chosen, atk=_atk, health=0))

        listener = EventListener(
            event_name="DAMAGE",
            action=_BuffRandomOnFriendlyDamage(),
            condition=lambda minion, amount, src: (
                minion is not None
                and not minion.dead
                and minion.controller == source.controller
            ),
        )
        game.register_listener(source, listener)
        return None


class OnFriendlyDamageBuffRandom4Script(OnFriendlyDamageBuffRandomScript):
    """Whenever a friendly minion takes damage, give a random friendly +5 ATK."""
    ATK_BONUS = 5


# ════════════════ Phase 15b: SimpleGet (pure get-card) ═════════════════════════

class GetFishOfNZothScript:
    """Get a Fish of N'Zoth."""
    CARD_ID = "TB_BaconUps_307"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetFacelessManipulatorScript:
    """Get a Faceless Manipulator."""
    CARD_ID = "BG_EX1_564"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetTimewarpedPoetScript:
    """Get a Timewarped Poet."""
    CARD_ID = "BG34_Giant_314"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetTideOracleMorglScript:
    """Get a Tide Oracle Morgl."""
    CARD_ID = "BG27_513"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetArcaneBehemothScript:
    """Get an Arcane Behemoth."""
    CARD_ID = "BG31_360"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetTimewarpedSkipperScript:
    """Get a Timewarped Skipper."""
    CARD_ID = "BG34_Giant_072"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetTimewarpedLeapfroggerScript:
    """Get a Timewarped Leapfrogger."""
    CARD_ID = "BG34_Giant_031"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetAllChromadrakesScript:
    """Get all 5 Chromadrakes."""
    CHROMADRAKE_IDS = [
        "BG34_Giant_201",  # Red Chromadrake
        "BG34_Giant_202",  # Blue Chromadrake
        "BG34_Giant_203",  # Green Chromadrake
        "BG34_Giant_204",  # Bronze Chromadrake
        "BG34_Giant_205",  # Black Chromadrake
    ]

    @classmethod
    def on_summon(cls, source, game):
        return [AddToHand(source.controller, cid) for cid in cls.CHROMADRAKE_IDS]


class ChromaticTearLesserScript:
    """Get 2 random Chromadrakes. At the start of each turn, repeat this."""
    COUNT = 2

    @classmethod
    def _get_chromadrakes(cls, source):
        return [
            AddToHand(source.controller, source.game.rng.choice(CHROMADRAKE_IDS))
            for _ in range(cls.COUNT)
        ]

    @classmethod
    def on_summon(cls, source, game):
        return cls._get_chromadrakes(source)

    @classmethod
    def start_of_turn(cls, source, game):
        return cls._get_chromadrakes(source)


# ════════════════ Phase 15c: Get + secondary effect ════════════════════════════

class GetSoulRewinderAndWrathWeaverScript:
    """Get a Soul Rewinder and a Wrath Weaver."""
    SOUL_REWINDER = "BG26_174"
    WRATH_WEAVER = "BGS_004"

    @classmethod
    def on_summon(cls, source, game):
        return [
            AddToHand(source.controller, cls.SOUL_REWINDER),
            AddToHand(source.controller, cls.WRATH_WEAVER),
        ]


class GetGoldgrubberAndAureateScript:
    """Get a Goldgrubber and an Aureate Laureate."""
    GOLDGRUBBER = "BGS_066"
    AUREATE = "BG32_236"

    @classmethod
    def on_summon(cls, source, game):
        return [
            AddToHand(source.controller, cls.GOLDGRUBBER),
            AddToHand(source.controller, cls.AUREATE),
        ]


class GetBrannAndRandomBCScript:
    """Get a Brann Bronzebeard and a random Battlecry minion."""
    BRANN = "BG_LOE_077"

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        bc_pool = [cid for cid, data in CARDS._cards.items()
                   if data.cardtype == CardType.MINION
                   and data.tags.get(GameTag.BATTLECRY) == True
                   and not cid.startswith('EXAMPLE')]
        actions = [AddToHand(source.controller, cls.BRANN)]
        if bc_pool:
            actions.append(AddToHand(source.controller, game.rng.choice(bc_pool)))
        return actions


class GetWhelpSmugglerSetStatsScript:
    """Get a Whelp Smuggler. Set its stats to 12/12."""
    CARD_ID = "BG21_013"

    @classmethod
    def on_summon(cls, source, game):
        token = game.create_minion(cls.CARD_ID)
        if token is None:
            return None
        token.zone = Zone.HAND
        source.controller.hand.append(token)
        # Base Whelp Smuggler is 2/5, set to 12/12
        token.set_tag(GameTag.ATK, 12)
        token.set_tag(GameTag.HEALTH, 12)
        return None


class GetLivingAzeriteElementalBonusScript:
    """Get a Living Azerite. Your Living Azerites also give stats to friendly Elementals."""
    CARD_ID = "BG28_707"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetLightfangAllTypesScript:
    """Get a Lightfang Enforcer. Your Lightfang Enforcers have all minion types."""
    CARD_ID = "BGS_009"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 15d: on_friendly_attack → buff/keyword ═════════════════

class OnFriendlyDragonAttackGiveDSScript:
    """Whenever a friendly Dragon attacks, give it Divine Shield. (3 times per combat.)"""
    MAX_TRIGGERS = 3

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_attack(cls, source, game, **kwargs):
        attacker = kwargs.get('attacker')
        if attacker is None or getattr(attacker, 'race', None) != Race.DRAGON:
            return None
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter >= cls.MAX_TRIGGERS:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, counter + 1)
        return GainKeyword(attacker, GameTag.DIVINE_SHIELD)


# ════════════════ Phase 15e: on_summon_in_combat → buff ════════════════════════

class OnSummonBeastBuff44Script:
    """Whenever you summon a Beast, give it +4/+4."""
    ATK = 4
    HEALTH = 4

    @classmethod
    def on_summon_in_combat(cls, source, game, **kwargs):
        summoned = kwargs.get('summoned') or kwargs.get('minion')
        if summoned is None or getattr(summoned, 'race', None) != Race.BEAST:
            return None
        return Buff(summoned, atk=cls.ATK, health=cls.HEALTH)


# ════════════════ Phase 15f: Cast Ice Block + Gain Gold ════════════════════════

class CastIceBlockGainGoldScript:
    """Cast Ice Block. Gain 5 Gold."""
    ICE_BLOCK = "TB_Bacon_Secrets_12"
    GOLD = 5

    @classmethod
    def on_summon(cls, source, game):
        return [
            CastTavernSpell(source.controller),
            GainGold(source.controller, cls.GOLD),
        ]


# ════════════════ Phase 15g: Discover Deathrattle + first DR extra time ═══════

class DiscoverDRFirstDRExtraTimeScript:
    """Discover a Deathrattle minion. Your first Deathrattle each combat triggers an extra time."""
    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        dr_pool = [cid for cid, data in CARDS._cards.items()
                   if data.cardtype == CardType.MINION
                   and data.tags.get(GameTag.DEATHRATTLE) == True
                   and not cid.startswith('EXAMPLE')]
        if dr_pool:
            return DiscoverMinion(source.controller, card_id_filter=dr_pool)
        return None

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_deathrattle_triggered(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, 1)
        # Re-trigger the deathrattle (extra time)
        dr_minion = kwargs.get('minion')
        if dr_minion is not None and hasattr(dr_minion, 'deathrattle') and callable(dr_minion.deathrattle):
            return dr_minion.deathrattle(dr_minion, game)
        return None


# ════════════════ Phase 15h: Get Prized Promo-Drake + first SoC extra time ═════

class GetPromoDrakeFirstSoCExtraTimeScript:
    """Get a Prized Promo-Drake. Your first Start of Combat effect each combat triggers an extra time."""
    CARD_ID = "BG21_014"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_start_of_combat_triggered(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter > 0:
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, 1)
        # Re-trigger the first SoC effect
        soc_minion = kwargs.get('minion')
        if soc_minion is not None and hasattr(soc_minion, 'start_of_combat') and callable(soc_minion.start_of_combat):
            return soc_minion.start_of_combat(soc_minion, game)
        return None


# ════════════════ Phase 15i: After Refresh → double highest-Health minion ═════

class OnRefreshDoubleHighestHealthScript:
    """After the Tavern is Refreshed, double the stats of its highest-Health minion."""
    @classmethod
    def on_tavern_refresh(cls, source, game, **kwargs):
        tavern = source.controller.tavern
        if not tavern:
            return None
        highest = max(tavern, key=lambda m: m.health)
        if highest.health <= 0:
            return None
        return Buff(highest, atk=highest.atk, health=highest.health)


# ════════════════ Phase 15j: Every 2 turns → gain gold + discover T6 ══════════

class Every2TurnsGainGoldDiscoverT6Script:
    """At the start of every 2 turns, gain 2 Gold and Discover a Tier 6 minion."""
    N = 2
    START_COUNTER = 2
    GOLD = 2

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, cls.START_COUNTER)
        return None

    @classmethod
    def on_turn_begin(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.N:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            return [
                GainGold(source.controller, cls.GOLD),
                DiscoverMinion(source.controller, min_tier=6),
            ]
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


# ════════════════ Phase 15k: Reduce Tavern upgrade cost + repeat ══════════════

class ReduceUpgradeCostRepeatScript:
    """Reduce the Cost of upgrading the Tavern by (3). At the start of each turn, repeat this."""
    COST_REDUCTION = 3

    @classmethod
    def on_summon(cls, source, game):
        cur = source.controller.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
        source.controller.set_tag(GameTag.TAVERN_UPGRADE_COST, max(0, cur - cls.COST_REDUCTION))
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        cur = source.controller.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
        source.controller.set_tag(GameTag.TAVERN_UPGRADE_COST, max(0, cur - cls.COST_REDUCTION))
        return None


# ════════════════ Phase 15l: Every 2 turns → craft custom Undead ══════════════

class Every2TurnsCraftUndeadScript:
    """Craft a custom Undead. At the start of every 2 turns, repeat this."""
    N = 2
    START_COUNTER = 2

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, cls.START_COUNTER)
        return None

    @classmethod
    def effect(cls, source, game):
        # Discover an Undead minion — "craft" = discover + buff
        from hsrl.core.card_db import CARDS
        undead_pool = [cid for cid, data in CARDS._cards.items()
                       if data.cardtype == CardType.MINION
                       and data.tags.get(GameTag.RACE) == Race.UNDEAD
                       and not cid.startswith('EXAMPLE')]
        if undead_pool:
            return DiscoverMinion(source.controller, card_id_filter=undead_pool)
        return None

    @classmethod
    def on_turn_begin(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.N:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            return cls.effect(source, game)
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


# ════════════════ Phase 15m: Get + Dr. Boom's Monster repeat ══════════════════

class GetDrBoomsMonsterRepeatScript:
    """Get a Dr. Boom's Monster. At the start of each turn, get another."""
    CARD_ID = "BG31_176"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def start_of_turn(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 15n: Get random + repeat each turn ════════════════════

class GetRandomMinionRepeatScript:
    """Get a random minion. At the start of each turn, get another."""
    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == CardType.MINION
                and not cid.startswith('EXAMPLE')]
        if pool:
            return AddToHand(source.controller, game.rng.choice(pool))
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == CardType.MINION
                and not cid.startswith('EXAMPLE')]
        if pool:
            return AddToHand(source.controller, game.rng.choice(pool))
        return None


class Get2RandomMinionsRepeatScript:
    """Get 2 random minions. At the start of each turn, get 2 more."""
    COUNT = 2

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == CardType.MINION
                and not cid.startswith('EXAMPLE')]
        if pool:
            chosen = game.rng.sample(pool, min(cls.COUNT, len(pool)))
            return [AddToHand(source.controller, cid) for cid in chosen]
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == CardType.MINION
                and not cid.startswith('EXAMPLE')]
        if pool:
            chosen = game.rng.sample(pool, min(cls.COUNT, len(pool)))
            return [AddToHand(source.controller, cid) for cid in chosen]
        return None


# ════════════════ Phase 15o: After hero takes damage, tavern spell bonus ══════

class OnHeroDamageTavernSpellBonusScript:
    """After your hero takes damage, your Tavern spells give an extra +1/+1 this turn."""
    ATK_BONUS = 1
    HEALTH_BONUS = 1

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)
        source.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)
        return None

    @classmethod
    def on_hero_damage(cls, source, game, **kwargs):
        current_atk = source.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)
        current_health = source.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)
        source.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, current_atk + cls.ATK_BONUS)
        source.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, current_health + cls.HEALTH_BONUS)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)
        source.set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 16: Engine-Backed Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

# ════════════════ Phase 16a: OnSpellCast → Buff Leftmost Hand ═════════════════

class OnCastSpellBuffLeftmostHand4x4Script:
    """After you cast a Tavern spell, give left-most hand and board minions +3/+3."""
    ATK = 3
    HEALTH = 3

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import EventListener
        _atk = cls.ATK
        _health = cls.HEALTH

        class _BuffLeftmost(Action):
            def do(self, source_ent, game_ref, target=None):
                hand = source.controller.hand
                if hand:
                    game_ref.queue_action(Buff(hand[0], atk=_atk, health=_health))
                board = _living_board(source.controller)
                if board:
                    game_ref.queue_action(Buff(board[0], atk=_atk, health=_health))

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffLeftmost(),
            condition=lambda spell, player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ════════════════ Phase 16b: OnConsume → Counter → Get Spell ══════════════════

class After2ConsumedGetTavernSpellScript:
    """After 2 minions in the Tavern are consumed, get a random Tavern spell."""
    TRIGGER = 2

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_tavern_minion_consumed(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.TRIGGER:
            source.set_tag(GameTag.TRINKET_COUNTER, 0)
            if game.spell_pool:
                spell_id = game.spell_pool.get_random()
                if spell_id:
                    return AddToHand(source.controller, spell_id)
            return None
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


# ════════════════ Phase 16c: Pure Get Multiple ════════════════════════════════

class GetBeatboxerAndMagneticScript:
    """Get a Polarizing Beatboxer and 1 random Magnetic Mech."""
    BEATBOXER = "BG26_149"

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        magnetic_pool = [cid for cid, data in CARDS._cards.items()
                         if data.cardtype == CardType.MINION
                         and data.tags.get(GameTag.MAGNETIC) == True
                         and not cid.startswith('EXAMPLE')]
        actions = [AddToHand(source.controller, cls.BEATBOXER)]
        if magnetic_pool:
            actions.append(AddToHand(source.controller, game.rng.choice(magnetic_pool)))
        return actions


class GetTwoMinionsPerTier123Script:
    """Get two minions each from Tiers 1, 2, and 3."""
    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        actions = []
        for tier in [1, 2, 3]:
            pool = [cid for cid, data in CARDS._cards.items()
                    if data.cardtype == CardType.MINION
                    and data.tags.get(GameTag.TECH_LEVEL) == tier
                    and not cid.startswith('EXAMPLE')]
            if len(pool) >= 2:
                chosen = game.rng.sample(pool, 2)
            elif pool:
                chosen = pool[:]
            else:
                continue
            for cid in chosen:
                actions.append(AddToHand(source.controller, cid))
        return actions if actions else None


# ════════════════ Phase 16d: Remove All + Gain Gold ═══════════════════════════

class RemoveAllMinionsGainGoldScript:
    """Remove all your minions. Gain 3 Gold for each removed."""
    GOLD_PER = 3

    @classmethod
    def on_summon(cls, source, game):
        board = list(source.controller.board)
        count = len(board)
        for m in board:
            m.set_tag(GameTag.DEAD, True)
            m.zone = Zone.GRAVEYARD
            if m in source.controller.board:
                source.controller.board.remove(m)
        if count > 0:
            return GainGold(source.controller, count * cls.GOLD_PER)
        return None


# ════════════════ Phase 16e: Get + Set Stats ═══════════════════════════════════

class GetBattlecruiser12x12Script:
    """Get a 12/12 Battlecruiser."""
    CARD_ID = "BG31_HERO_801pt"

    @classmethod
    def on_summon(cls, source, game):
        token = game.create_minion(cls.CARD_ID)
        if token is None:
            return None
        token.zone = Zone.HAND
        source.controller.hand.append(token)
        token.set_tag(GameTag.ATK, 12)
        token.set_tag(GameTag.HEALTH, 12)
        return None


class GetImpulsiveTrickster6x6Script:
    """Get a 6/6 Impulsive Trickster."""
    CARD_ID = "BG21_006"

    @classmethod
    def on_summon(cls, source, game):
        token = game.create_minion(cls.CARD_ID)
        if token is None:
            return None
        token.zone = Zone.HAND
        source.controller.hand.append(token)
        token.set_tag(GameTag.ATK, 6)
        token.set_tag(GameTag.HEALTH, 6)
        return None


# ════════════════ Phase 16f: Spell Discount (First N Free) ════════════════════

class First3SpellsFreeEachTurnScript:
    """The first 3 Tavern spells you buy each turn are free."""
    FREE_COUNT = 3

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def modify_spell_cost(cls, source, game, **kwargs):
        """Called before buying a spell to check/apply discount."""
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if counter < cls.FREE_COUNT:
            return 999  # Effectively free (reduced to 0 by engine)
        return 0


# ════════════════ Phase 16g: Get + OnDiscover → Spell ═════════════════════════

class GetPrimalfinLookoutDiscoverSpellScript:
    """Get a Primalfin Lookout. After you Discover a minion, get a random Tavern spell."""
    CARD_ID = "BGS_020"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def on_discover_triggered(cls, source, game, **kwargs):
        if game.spell_pool:
            spell_id = game.spell_pool.get_random()
            if spell_id:
                return AddToHand(source.controller, spell_id)
        return None


# ════════════════ Phase 16h: Get + OnDestroyOutside → Coin Pouch ══════════════

class GetMawCasterDestroyCoinScript:
    """Get a Maw Caster. Whenever you destroy a minion outside combat, get a 3-Gold Coin Pouch."""
    CARD_ID = "BG32_340"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def on_minion_destroyed_outside_combat(cls, source, game, **kwargs):
        # 3-Gold Coin Pouch (placeholder — actual card ID may differ)
        return GainGold(source.controller, 3)


# ════════════════ Phase 16i: Every 4 Buys → Health Cost ═══════════════════════

class Every4BuysHealthCostScript:
    """Every fourth card you buy costs Health instead of Gold."""
    TRIGGER = 4

    @classmethod
    def on_summon(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_minion_bought(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None

    @classmethod
    def modify_purchase_cost(cls, source, game, **kwargs):
        """Called before purchase to check if this buy should cost health."""
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
        if counter >= cls.TRIGGER:
            return "health"  # Signal to game engine to use health instead of gold
        return "gold"


# ════════════════ Phase 16j: After Play Demon → Another Consumes ══════════════

class OnPlayDemonConsumeTavernScript:
    """After you play a Demon, another friendly Demon consumes a minion in the Tavern."""
    @classmethod
    def on_play(cls, source, game, played_card=None):
        if played_card is None or getattr(played_card, 'race', None) != Race.DEMON:
            return None
        # Find another friendly demon (not the played one) that can consume
        from hsrl.core.actions import ConsumeTavernMinion
        demons = [m for m in source.controller.board
                  if not m.dead and m.race == Race.DEMON and m is not played_card]
        if not demons:
            return None
        consumer = game.rng.choice(demons)
        return ConsumeTavernMinion(source.controller, consumer, mode="random")


# ════════════════ Phase 16k: OnSummonBeastBuff Script (combat) ════════════════

class OnSummonBeastGiveRebornScript:
    """Whenever you summon a Beast in combat, give it Reborn."""
    @classmethod
    def on_summon_in_combat(cls, source, game, **kwargs):
        summoned = kwargs.get('summoned') or kwargs.get('minion')
        if summoned is None or getattr(summoned, 'race', None) != Race.BEAST:
            return None
        return GainKeyword(summoned, GameTag.REBORN)


# ════════════════ Phase 16l: EoT Play Blood Gems On Each Type ════════════════

class EoTPlayBGOnMinionOfEachTypeScript:
    """At the end of your turn, play 5 Blood Gems on a friendly minion of each type."""
    COUNT = 5

    @classmethod
    def end_of_turn(cls, source, game):
        board = _living_board(source.controller)
        if not board:
            return None
        # Find one minion of each race
        seen_races = set()
        targets = []
        for m in board:
            if m.race not in seen_races and m.race != Race.INVALID:
                seen_races.add(m.race)
                targets.append(m)
        if not targets:
            return None
        actions = []
        for t in targets:
            actions.append(PlayBloodGems(t, cls.COUNT))
        return actions



class GetFelementalExtraStatsScript:
    """Get a Felemental."""
    CARD_ID = "BG25_041"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


class GetBristlebachScript:
    """Get a Bristlebach."""
    CARD_ID = "BG26_157"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

# ═══════════════════════════════════════════════════════════════════════════════
# Phase 17: Aura + Transform + Spell Engine Trinkets
# ═══════════════════════════════════════════════════════════════════════════════

# ════════════════ Phase 17a: Low-Tier Aura (SoC buff T1-3) ═══════════════════

class SoCBuffLowTier75Script:
    """SoC: Your minions from Tier 3 or lower have +7/+5."""
    ATK = 7
    HEALTH = 5

    @classmethod
    def start_of_combat(cls, source, game):
        targets = [m for m in source.controller.board
                   if not m.dead and m.tech_level <= 3]
        if not targets:
            return None
        return [Buff(m, atk=cls.ATK, health=cls.HEALTH) for m in targets]


# ════════════════ Phase 17b: Transform All → T4 ════════════════════════════════

class TransformAllToRandomTier4Script:
    """Transform all your minions into random Tier 4 minions."""
    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        from hsrl.core.actions import Transform
        t4_pool = [cid for cid, data in CARDS._cards.items()
                   if data.cardtype == CardType.MINION
                   and data.tags.get(GameTag.TECH_LEVEL) == 4
                   and not cid.startswith('EXAMPLE')]
        if not t4_pool:
            return None
        board = list(source.controller.board)
        actions = []
        for m in board:
            if not m.dead:
                new_id = game.rng.choice(t4_pool)
                actions.append(Transform(m, new_id))
        return actions if actions else None


# ════════════════ Phase 17c: Spell Discount — first spell costs (1) less ══════

class FirstSpellEachTurnCosts1LessScript:
    """The first Tavern spell you buy each turn costs (1) less.

    Sets NEXT_SPELL_COST_REDUCTION=1 on the player. buy_spell() applies the
    discount and clears it. Re-enabled each turn via start_of_turn.
    """

    @classmethod
    def on_summon(cls, source, game):
        source.controller.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 1)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        source.controller.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 1)
        return None


# ════════════════ Phase 17d: EoT — Lock Tier 7 Discover ═══════════════════════

class DiscoverTier7LockScript:
    """Discover a Tier 7 minion. Lock it in your hand for 2 turns."""
    @classmethod
    def on_summon(cls, source, game):
        return DiscoverMinion(source.controller, min_tier=7)


class DiscoverGoldenTier7LockScript:
    """Discover a Golden Tier 7 minion. Lock it in your hand for 2 turns."""
    @classmethod
    def on_summon(cls, source, game):
        # Discover golden T7: discover a T7, then make it golden
        from hsrl.core.card_db import CARDS
        t7_pool = [cid for cid, data in CARDS._cards.items()
                   if data.cardtype == CardType.MINION
                   and data.tags.get(GameTag.TECH_LEVEL) == 7
                   and not cid.startswith('EXAMPLE')]
        if t7_pool:
            return DiscoverMinion(source.controller, card_id_filter=t7_pool)
        return None


# ════════════════ Phase 17e: Get + EoT Trigger Battlecry ══════════════════════

class GetHackerfinEoTTriggerBCScript:
    """Get a Hackerfin. At the end of each turn, trigger your Hackerfins' Battlecries."""
    CARD_ID = "BG31_148"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

    @classmethod
    def end_of_turn(cls, source, game):
        hackerfins = [m for m in source.controller.board
                      if not m.dead and m.get_tag(GameTag.CARD_ID) == cls.CARD_ID]
        if not hackerfins:
            return None
        actions = []
        for h in hackerfins:
            if h.battlecry:
                bc_fn = h.battlecry
                if bc_fn is not None and callable(bc_fn):
                    result = bc_fn(h, game)
                    if result is not None:
                        actions.append(result)
        return actions if actions else None


# ════════════════ Phase 17f: Combat — Quilboar death → Golem ══════════════════

class QuilboarDeathSummonGolemScript:
    """Whenever a friendly Quilboar dies, summon a Golem with stats equal to Blood Gems."""
    MAX_TRIGGERS = None
    GOLEM_ID = "BG28_801t"  # Placeholder — actual Blood Gem Golem token

    @classmethod
    def start_of_combat(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 0)
        return None

    @classmethod
    def on_friendly_death_combat(cls, source, game, **kwargs):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0)
        if cls.MAX_TRIGGERS is not None and counter >= cls.MAX_TRIGGERS:
            return None
        dead = kwargs.get('dead_minion')
        if dead is not None and dead.race == Race.QUILBOAR:
            source.set_tag(GameTag.TRINKET_COUNTER, counter + 1)
            blood_gems = dead.get_tag(GameTag.BLOOD_GEM_COUNT, 0)
            if len(source.controller.board) < 7:
                golem = game.create_minion(cls.GOLEM_ID)
                if golem:
                    golem.set_tag(GameTag.ATK, blood_gems)
                    golem.set_tag(GameTag.HEALTH, blood_gems)
                    from hsrl.core.actions import Summon
                    return Summon(source.controller, golem)
        return None


# ════════════════ Phase 17g: Get Zesty Shaker + extra spell copy ═════════════

class GetZestyShakerExtraCopyScript:
    """Get a Zesty Shaker. Your Zesty Shakers give an extra copy of the spell."""
    CARD_ID = "BG26_505"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17h: Get Kaboom Bot + DR bonus ════════════════════════

class GetKaboomBotDRBonusScript:
    """Get a Kaboom Bot. Your Kaboom Bots' Deathrattles deal 10 extra damage."""
    CARD_ID = "TB_BaconUps_028"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17i: Get Sky Pirate Flagbearer + aura ═════════════════

class GetSkyPirateFlagbearerAuraScript:
    """Get a Sky Pirate Flagbearer. Your Sky Pirates have +6 Attack."""
    CARD_ID = "BG30_119"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17j: Get Hot-Air Surveyor + BG bonus ══════════════════

class GetHotAirSurveyorBGBonusScript:
    """Get a Hot-Air Surveyor. Blood Gems played from your hand give an extra +4/+4."""
    CARD_ID = "BG30_121"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17k: Get Drakkari Enchanter + types ═══════════════════

class GetDrakkariMechElementalScript:
    """Get a Drakkari Enchanter. Your Drakkari Enchanters are both Mechs and Elementals."""
    CARD_ID = "BG26_ICC_901"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17l: Get Monstrous Macaw + BC trigger ═════════════════

class GetMonstrousMacawTriggerBCScript:
    """Get a Monstrous Macaw. Your Monstrous Macaws also trigger your left-most Battlecry."""
    CARD_ID = "TB_BaconUps_135"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17m: Get Selfless Hero + BC trigger ═══════════════════

class GetSelflessHeroTriggerBCScript:
    """Get a Selfless Hero. Your Selfless Heroes also trigger on Battlecry."""
    CARD_ID = "TB_BaconUps_014"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17n: Get Charging Czarina + Health ═══════════════════

class GetChargingCzarinaHealthScript:
    """Get a Charging Czarina. Your Charging Czarinas also give Health."""
    CARD_ID = "BG28_741"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 17o: Get Groundbreaker + left buff ════════════════════

class GetGroundbreakerLeftBuffScript:
    """Get a Groundbreaker. Your Groundbreakers also give stats to the minion to their left."""
    CARD_ID = "BG31_035"

    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)



class GetFlamingEnforcerScript:
    """Get a Flaming Enforcer."""
    CARD_ID = "BG34_500"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

class GetTimewarpedGlowscaleScript:
    """Get a Timewarped Glowscale."""
    CARD_ID = "BG34_Giant_035"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

class GetSlimyFelbloodScript:
    """Get a Slimy Felblood."""
    CARD_ID = "BG29_873"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

class GetArchlichKelThuzadScript:
    """Get an Archlich Kel'Thuzad."""
    CARD_ID = "BG28_308"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

class GetBristlemaneScrapsmithScript:
    """Get a Bristlemane Scrapsmith."""
    CARD_ID = "BG24_707"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)

class GetRedeemerPortraitScript:
    """Redeemer Portrait."""
    CARD_ID = "BG32_MagicItem_944t"
    @classmethod
    def on_summon(cls, source, game):
        return AddToHand(source.controller, cls.CARD_ID)


# ════════════════ Phase 18: Start-of-Turn Repeat Get (non-pool spells) ══════════

class SoTRepeatGetAzeriteScript(SoTRepeatGetScript):
    """Get an Azerite Empowerment. At the start of each turn, get another."""
    TOKEN_ID = "BG28_169"


class SoTRepeatGetNaturalBlessingScript(SoTRepeatGetScript):
    """Get a Natural Blessing. At the start of each turn, get another."""
    TOKEN_ID = "BG28_845"


# ════════════════ Phase 18b: On-Summon simple effects ═══════════════════════════

class GainGold3OnSummonScript:
    """Gain 3 Gold. Buy your Greater Trinket next turn instead of turn 9.

    Note: greater trinket timing acceleration is DEFERRED (needs trinket timing system).
    """

    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(GainGold(source.controller, 3), source=source)


class SoTRepeatGetPortalInABottleScript(SoTRepeatGetScript):
    """Duo: Get a Portal in a Bottle. At the start of each turn, get another."""
    TOKEN_ID = "BGDUO_113"


class SoTRepeatGetOrcConductorScript(SoTRepeatGetScript):
    """Duo: Get an Orc-estra Conductor. At the start of each turn, get another."""
    TOKEN_ID = "BGDUO_119"


class SoTRepeatGetWoodlandDefilerScript(SoTRepeatGetScript):
    """Get a Woodland Defiler. At the start of each turn, get another."""
    TOKEN_ID = "BG35_151"


class GetMagneticMechsScript:
    """Get N Magnetic Mechs of any Tier (N=2 for Lesser, N=3 for Greater)."""
    N = 2

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.card_db import CARDS
        magnetic_ids = [
            cid for cid, data in CARDS._cards.items()
            if data.cardtype == 4
            and data.tags.get(GameTag.MAGNETIC)
            and not cid.startswith("EXAMPLE")
        ]
        for _ in range(cls.N):
            if magnetic_ids:
                game.queue_action(AddToHand(source.controller, game.rng.choice(magnetic_ids)), source=source)


class GetMagneticMechs3Script(GetMagneticMechsScript):
    """Get 3 Magnetic Mechs of any Tier."""
    N = 3


class SoTMarvelousMushroomScript:
    """Your Tavern spells give an extra +1/+1. At the start of each turn, improve this.

    Formal spec:
      1. on_summon: ImproveTavernSpellBuff(+1/+1)
      2. start_of_turn: ImproveTavernSpellBuff(+1/+1)

    Test: equip → tavern spells get +1/+1. After N turns → +1+N/+1+N.
    """

    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1), source=source)

    @classmethod
    def start_of_turn(cls, source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1)


class SoTGetAzeriteEmpowermentScript:
    """Get an Azerite Empowerment. At the start of each turn, get another."""
    TOKEN_ID = "BG28_169"

    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(AddToHand(source.controller, cls.TOKEN_ID), source=source)

    @classmethod
    def start_of_turn(cls, source, game):
        return AddToHand(source.controller, cls.TOKEN_ID)

# ════════════════ Phase 18c: Tavern Spell Buff Improvement ═════════════════════

class SoTTavernSpellBuffCounterScript:
    """Your Tavern spells give extra ATK/HEALTH. Improves after N spells cast.

    Formal spec:
      1. on_summon: apply initial ImproveTavernSpellBuff + register TAVERN_SPELL_CAST listener
      2. Listener: decrement counter; when 0 → ImproveTavernSpellBuff + reset counter
    """
    ATK_BONUS = 1
    HEALTH_BONUS = 1
    TARGET = 5  # spells needed to improve

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener
        game.queue_action(
            ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1),
            source=source)
        source.set_tag(GameTag.TRINKET_COUNTER, 5)

        def _on_cast(trinket, g):
            c = trinket.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
            if c <= 0:
                trinket.set_tag(GameTag.TRINKET_COUNTER, 5)
                return ImproveTavernSpellBuff(trinket.controller, atk_bonus=1, health_bonus=1)
            trinket.set_tag(GameTag.TRINKET_COUNTER, c)
            return None

        class _ListenerAction(Action):
            def __init__(self, t):
                super().__init__()
                self.t = t
            def do(self, s, g, target=None):
                result = _on_cast(self.t, g)
                if result:
                    g.queue_action(result)

        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_ListenerAction(source),
        ))


class SoTTavernSpellBuffCounterFromHandScript:
    """Like SoTTavernSpellBuffCounterScript but only counts spells played from hand.

    Greater trinket variant (801t): 「从手牌施放」限定。
    """
    ATK_BONUS = 1
    HEALTH_BONUS = 1
    TARGET = 4

    @staticmethod
    def on_summon(source, game):
        game.queue_action(
            ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1),
            source=source)
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 4)

        def _on_cast(trinket, g):
            # Only count spells cast from hand (SPELL_PLAYED_FROM_HAND tag)
            from hsrl.core.enums import GameTag as GT
            c = trinket.get_tag(GT.TRINKET_COUNTER, 1) - 1
            if c <= 0:
                trinket.set_tag(GT.TRINKET_COUNTER, 4)
                return ImproveTavernSpellBuff(trinket.controller, atk_bonus=1, health_bonus=1)
            trinket.set_tag(GT.TRINKET_COUNTER, c)
            return None

        class _ListenerAction(Action):
            def __init__(self, t):
                super().__init__()
                self.t = t

            def do(self, s, g, target=None):
                result = _on_cast(self.t, g)
                if result:
                    g.queue_action(result)

        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_ListenerAction(source),
        ))


# ════════════════ Phase 18d: Extra Hero Power + Gold ═══════════════════════════

class ExtraHeroPowerGainGoldScript:
    """Each turn you can use your Hero Power an extra time.
    After you use your Hero Power, gain 1 Gold.

    Formal spec:
      1. on_summon: set HERO_POWER_EXTRA_USES = 1 on controller
      2. register HERO_POWER_USED listener → GainGold(1)
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.HERO_POWER_EXTRA_USES,
                                   source.controller.get_tag(GameTag.HERO_POWER_EXTRA_USES, 0) + 1)

        from hsrl.core.events import HERO_POWER_USED, EventListener

        class _GainGoldAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                game_ref.queue_action(GainGold(self.player, 1))

        game.register_listener(source, EventListener(
            event_name=HERO_POWER_USED,
            action=_GainGoldAction(source.controller),
        ))


# ════════════════ Phase 18e: Spellcraft Permanent ══════════════════════════════

class GetSpellcraftPermanentScript:
    """Get a minion. Its Spellcraft persists (doesn't expire after use).

    Sets PERMANENT_SPELLCRAFT tag on the minion when added to hand.
    """
    CARD_ID = ""
    PERMANENT_TAG = True

    @classmethod
    def on_summon(cls, source, game):
        token = game.create_minion(cls.CARD_ID)
        if token is None:
            return None
        token.controller = source.controller
        token.zone = Zone.HAND
        token.set_tag(GameTag.PERMANENT_SPELLCRAFT, True)
        source.controller.hand.append(token)
        return None


class GetSoulJugglerSpellcraftScript(GetSpellcraftPermanentScript):
    """Get a Soul Juggler. Its Spellcraft is permanent."""
    CARD_ID = "BGS_002"


class GetSlumberSorcererSpellcraftScript(GetSpellcraftPermanentScript):
    """Get a Slumber Sorcerer. Its Spellcraft is permanent."""
    CARD_ID = "BG32_833"


# ════════════════ Phase 18f: Elemental buff enhancement ════════════════════════

class ElementalStatBonusScript:
    """Your elementals that give stats to minions give an extra ATK/HEALTH."""
    ATK_BONUS = 2
    HEALTH_BONUS = 1

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.ELEMENTAL_STAT_BONUS_ATK,
                                   source.controller.get_tag(GameTag.ELEMENTAL_STAT_BONUS_ATK, 0) + 2)
        source.controller.set_tag(GameTag.ELEMENTAL_STAT_BONUS_HEALTH,
                                   source.controller.get_tag(GameTag.ELEMENTAL_STAT_BONUS_HEALTH, 0) + 1)


class ElementalStatBonusGreaterScript(ElementalStatBonusScript):
    """Your elementals that give stats give an extra +4/+2."""
    ATK_BONUS = 4
    HEALTH_BONUS = 2


# ════════════════ Phase 18g: On Spell Cast on Minion ═══════════════════════════

class OnSpellCastOnMinionBuffScript:
    """Whenever you cast a spell on a minion, give it +ATK/+HEALTH."""
    ATK = 2
    HEALTH = 1

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import SPELL_CAST_ON_MINION, EventListener
        # Capture the class-level ATK/HEALTH for the listener
        _atk = OnSpellCastOnMinionBuffScript.ATK
        _health = OnSpellCastOnMinionBuffScript.HEALTH
        # If source has its own script class, use those values instead
        if hasattr(source, 'data') and source.data and source.data.scripts:
            _atk = getattr(source.data.scripts, 'ATK', _atk)
            _health = getattr(source.data.scripts, 'HEALTH', _health)

        class _BuffAction(Action):
            def __init__(self, trinket):
                super().__init__()
                self.trinket = trinket

            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                game_ref.queue_action(Buff(target, atk=_atk, health=_health))

        game.register_listener(source, EventListener(
            event_name=SPELL_CAST_ON_MINION,
            action=_BuffAction(source),
        ))


class LorewalkerScrollLesserScript:
    """Whenever you cast a spell on a minion, give it +4/+4."""
    ATK = 4
    HEALTH = 4

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import SPELL_CAST_ON_MINION, EventListener
        _atk = 4
        _health = 4

        class _BuffAction(Action):
            def __init__(self, trinket):
                super().__init__()
                self.trinket = trinket

            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                game_ref.queue_action(Buff(target, atk=_atk, health=_health))

        game.register_listener(source, EventListener(
            event_name=SPELL_CAST_ON_MINION,
            action=_BuffAction(source),
        ))


class LorewalkerScrollGreaterScript:
    """Whenever you cast a spell on a minion, give it +8/+8."""
    ATK = 8
    HEALTH = 8

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import SPELL_CAST_ON_MINION, EventListener
        _atk = 8
        _health = 8

        class _BuffAction(Action):
            def __init__(self, trinket):
                super().__init__()
                self.trinket = trinket

            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                game_ref.queue_action(Buff(target, atk=_atk, health=_health))

        game.register_listener(source, EventListener(
            event_name=SPELL_CAST_ON_MINION,
            action=_BuffAction(source),
        ))


# ════════════════ Phase 18f2: Egg Portrait — Delayed Hatch ═════════════════════

class EggOfTheEndtimesPortraitScript:
    """Get a golden Egg of the Endtimes. It hatches next turn.

    Formal spec:
      1. on_summon: create golden BG34_639_G, add to hand with HATCH_DELAY=1
      2. start_of_turn: decrement HATCH_DELAY; when 0 → transform into a random Dragon

    Note: the exact dragon pool for hatching is deferred; uses random Tier-5+ dragon.
    """
    EGG_GOLDEN = "BG34_639_G"

    @classmethod
    def on_summon(cls, source, game):
        token = game.create_minion(cls.EGG_GOLDEN)
        if token is None:
            return None
        token.controller = source.controller
        token.zone = Zone.HAND
        token.set_tag(GameTag.GOLDEN, True)
        token.set_tag(GameTag.TRINKET_COUNTER, 1)  # hatch delay counter
        source.controller.hand.append(token)
        return None


# ════════════════ Phase 18f3: Coral Spear — On Spellcraft → Stormwind ══════════

class CoralSpearScript:
    """
    Natural language: Whenever you cast a Spellcraft spell, cast Might of Stormwind.

    Formal spec:
      1. on_summon: register SPELLCRAFT_CAST EventListener
      2. On each SPELLCRAFT_CAST from source.controller: play BGS_Treasures_007
         (+2/+2 to all friendly minions)
    Test: register listener via on_summon, cast spellcraft, verify buff applied.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import SPELLCRAFT_CAST, EventListener
        from hsrl.core.actions import CastTavernSpell

        class _CastStormwind(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                spell = g.create_spell("BGS_Treasures_007")
                if spell is None:
                    return
                spell.controller = self.player
                g.queue_action(CastTavernSpell(self.player, "BGS_Treasures_007"))

        game.register_listener(source, EventListener(
            event_name=SPELLCRAFT_CAST,
            action=_CastStormwind(source.controller),
            condition=lambda spell, p: p == source.controller,
        ))
        return None


# ════════════════ Phase 18f4: Trusty Crowbar — On Add Pirate → Buff ════════════

class TrustyCrowbarScript:
    """Whenever you get a Pirate, give your leftmost minion +ATK/+HEALTH.

    Formal spec:
      1. on_summon: register ADD_TO_HAND listener
      2. Listener: if added card is Pirate → buff leftmost
    """
    ATK = 2
    HEALTH = 1

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import ADD_TO_HAND, EventListener

        class _CrowbarAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if target is None:
                    return
                # Check if the added card is a pirate
                if target.race != Race.PIRATE:
                    return
                board = self.player.get_board_minions()
                living = [m for m in board if not m.dead]
                if not living:
                    return
                g.queue_action(Buff(living[0], atk=2, health=1))

        game.register_listener(source, EventListener(
            event_name=ADD_TO_HAND,
            action=_CrowbarAction(source.controller),
        ))


# ════════════════ Phase 18g1: Gold-plated Compass — Next Purchase Golden ═══════

class GoldPlatedCompassScript:
    """Make your next purchase golden. Gain 5 free refreshes.

    Formal spec:
      1. on_summon: set NEXT_PURCHASE_GOLDEN += 1, GainFreeRefresh(5)
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.NEXT_PURCHASE_GOLDEN,
                                   source.controller.get_tag(GameTag.NEXT_PURCHASE_GOLDEN, 0) + 1)
        game.queue_action(GainFreeRefresh(source.controller, 5), source=source)


# ════════════════ Phase 18g2: Combat Tracking — First Killed/Summoned ══════════

class BoomControllerScript:
    """When you have space, summon an exact copy of the first Mech you killed
    in each combat.

    Formal spec:
      1. on_summon: register END_OF_COMBAT listener
      2. END_OF_COMBAT: check combat death log for first mech death → summon copy
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener

        class _BoomAction(Action):
            def __init__(self, trinket):
                super().__init__()
                self.trinket = trinket
            def do(self, s, g, target=None):
                if len(self.trinket.controller.board) >= 7:
                    return
                # Find first dead mech for this player
                first_mech = None
                for m in g._combat_death_log:
                    if m.controller == self.trinket.controller and m.race == Race.MECH:
                        first_mech = m
                        break
                if first_mech is None:
                    return
                from hsrl.core.actions import Summon
                token = g.create_minion(first_mech.get_tag(GameTag.CARD_ID))
                if token:
                    # Copy current stats (max stats in combat)
                    token.set_tag(GameTag.ATK, first_mech.atk)
                    token.set_tag(GameTag.HEALTH, first_mech.health)
                    g.queue_action(Summon(self.trinket.controller, token))

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_BoomAction(source),
        ))


class TwinSkyLanternsScript:
    """When you have space, summon an exact copy of the first minion you summoned
    in each combat.

    Lesser: 1 copy. Greater: 2 copies.
    """
    COPIES = 1

    @classmethod
    def on_summon(cls, source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener

        class _LanternAction(Action):
            def __init__(self, trinket, copies):
                super().__init__()
                self.trinket = trinket
                self.copies = copies
            def do(self, s, g, target=None):
                for _ in range(self.copies):
                    if len(self.trinket.controller.board) >= 7:
                        return
                    first_summoned = None
                    for m in g._combat_summon_log:
                        if m.controller == self.trinket.controller:
                            first_summoned = m
                            break
                    if first_summoned is None:
                        return
                    from hsrl.core.actions import Summon
                    token = g.create_minion(first_summoned.get_tag(GameTag.CARD_ID))
                    if token:
                        token.set_tag(GameTag.ATK, first_summoned.atk)
                        token.set_tag(GameTag.HEALTH, first_summoned.health)
                        g.queue_action(Summon(self.trinket.controller, token))

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_LanternAction(source, cls.COPIES),
        ))


class TwinSkyLanternsGreaterScript(TwinSkyLanternsScript):
    """Greater: summon 2 copies of the first summoned minion."""
    COPIES = 2


class STharaStickerScript:
    """In each combat, after your last minion dies, summon your first dead Demon
    with its max stats.

    Formal spec:
      1. on_summon: register on_friendly_death_combat listener
      2. Listener: if no living friendly minions remain → find first dead demon → summon
    """

    @staticmethod
    def on_summon(source, game):
        # The on_friendly_death_combat is dispatched from _check_deaths
        # We register a listener via a different mechanism
        # Actually, we'll hook into the trinket event system
        pass

    @classmethod
    def on_friendly_death_combat(cls, source, game, dead_minion=None):
        if dead_minion is None:
            return None
        board = source.controller.get_board_minions()
        living = [m for m in board if not m.dead]
        if living:
            return None
        # Last friendly just died — find first dead demon
        first_demon = None
        for m in game._combat_death_log:
            if m.controller == source.controller and m.race == Race.DEMON:
                first_demon = m
                break
        if first_demon is None:
            return None
        from hsrl.core.actions import Summon
        token = game.create_minion(first_demon.get_tag(GameTag.CARD_ID))
        if token is None:
            return None
        token.set_tag(GameTag.ATK, first_demon.atk)
        token.set_tag(GameTag.HEALTH, first_demon.health)
        return Summon(source.controller, token)


# ════════════════ Phase 18h: Chromatic Tear — Get Chromadrakes ═════════════════

CHROMADRAKE_IDS = [
    "BG34_634t",  # Blue Chromadrake 4/4
    "BG34_635t",  # Black Chromadrake 4/6
    "BG34_636t",  # Green Chromadrake 3/5
    "BG34_637t",  # Bronze Chromadrake 5/3
    "BG34_638t",  # Red Chromadrake 6/4
]

class ChromaticTearScript:
    """Get 2 random Chromatic Dragons. After you play N Battlecry minions, repeat.

    Formal spec:
      1. on_summon: add 2 random Chromadrakes to hand; register BATTLECRY_TRIGGER listener
      2. Listener: decrement counter; when 0 → add 2 more + reset counter
    """
    COUNT = 2
    TARGET_BC = 3  # battlecry minions needed to trigger again

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import BATTLECRY_TRIGGER, EventListener
        # Add 2 random Chromadrakes on equip
        for _ in range(2):
            game.queue_action(AddToHand(source.controller, game.rng.choice(CHROMADRAKE_IDS)), source=source)
        source.set_tag(GameTag.TRINKET_COUNTER, 3)

        class _ChromAction(Action):
            def __init__(self, t):
                super().__init__()
                self.t = t
            def do(self, s, g, target=None):
                c = self.t.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    self.t.set_tag(GameTag.TRINKET_COUNTER, 3)
                    for _ in range(2):
                        g.queue_action(AddToHand(self.t.controller, g.rng.choice(CHROMADRAKE_IDS)))
                else:
                    self.t.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=BATTLECRY_TRIGGER,
            action=_ChromAction(source),
        ))


# ════════════════ Phase 18i: Bubble Crown — One-shot tavern spell buff ════════

class BubbleCrownScript:
    """After you cast N spells, your Tavern spells give an extra +2/+4.

    Formal spec:
      1. on_summon: register TAVERN_SPELL_CAST listener (once=True after trigger)
      2. Listener: decrement counter; when 0 → ImproveTavernSpellBuff(+2/+4), remove listener
    """
    TARGET = 6

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 6)

        class _BubbleAction(Action):
            def __init__(self, t):
                super().__init__()
                self.t = t
            def do(self, s, g, target=None):
                c = self.t.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    g.queue_action(ImproveTavernSpellBuff(self.t.controller, atk_bonus=2, health_bonus=4))
                    self.t.set_tag(GameTag.TRINKET_COUNTER, -1)  # done
                else:
                    self.t.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_BubbleAction(source),
        ))


# ════════════════ Phase 18j: Marine Signet — Minion-play counter ═══════════════

class MarineSignetScript:
    """After you play 4 minions, get a random Tavern spell. Improves after.

    Formal spec:
      1. on_summon: register MINION_PLAYED listener; start at spell tier 1
      2. Listener: decrement counter; when 0 → DiscoverSpell at current tier, upgrade tier
    """
    TARGET = 4

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 4)
        source.set_tag(GameTag.TRINKET_TIER, 1)

        class _SignetAction(Action):
            def __init__(self, t):
                super().__init__()
                self.t = t
            def do(self, s, g, target=None):
                c = self.t.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    tier = self.t.get_tag(GameTag.TRINKET_TIER, 1)
                    self.t.set_tag(GameTag.TRINKET_COUNTER, 4)
                    self.t.set_tag(GameTag.TRINKET_TIER, min(tier + 1, 6))
                    g.queue_action(DiscoverSpell(self.t.controller, max_tier=tier))
                else:
                    self.t.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_SignetAction(source),
        ))


# ════════════════ Phase 18k: Transcribing Typewriter — Extra purchase copy ═════

class TranscribingTypewriterScript:
    """Get an extra copy of the next N minions you buy.

    Formal spec:
      1. on_summon: set BUY_EXTRA_COPIES = 3 on controller
      2. register MINION_BOUGHT listener → if copies remain, add extra copy to hand
    """
    COPIES = 3

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        current = int(source.controller.get_tag(GameTag.BUY_EXTRA_COPIES, 0))
        source.controller.set_tag(GameTag.BUY_EXTRA_COPIES, current + 3)

        class _CopyAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if target is None:
                    return
                remaining = int(self.player.get_tag(GameTag.BUY_EXTRA_COPIES, 0))
                if remaining <= 0:
                    return
                self.player.set_tag(GameTag.BUY_EXTRA_COPIES, remaining - 1)
                g.queue_action(AddToHand(self.player, target.get_tag(GameTag.CARD_ID)))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_CopyAction(source.controller),
        ))


# ════════════════ Phase 19: Electromagnetic Device — Discover Magnetic + Buff ══

class ElectromagneticDeviceScript:
    """Discover a Magnetic Mech. Whenever a friendly minion is Magnetized,
    give it +3/+3.

    Formal spec:
      1. on_summon: DiscoverMinion(magnetic filter); register MAGNETIZED listener
      2. MAGNETIZED listener: Buff the magnetized minion +3/+3
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MAGNETIZED, EventListener

        # Discover a Magnetic mech
        game.queue_action(DiscoverMinion(source.controller, card_type=CardType.MINION), source=source)

        class _MagnetizeBuffAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if target is None or target.dead:
                    return
                g.queue_action(Buff(target, atk=3, health=3))

        game.register_listener(source, EventListener(
            event_name=MAGNETIZED,
            action=_MagnetizeBuffAction(source.controller),
        ))


# ════════════════ Phase 19b: Gem Donation — First Sell Blood Gems ══════════════

class GemDonationScript:
    """Each turn, your first sold minion plays its Blood Gems on the 3 highest-tier
    minions in the Tavern.

    Formal spec:
      1. on_summon: register MINION_SOLD listener with per-turn tracking
      2. First sell: find 3 highest-tier tavern minions → PlayBloodGems on each
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_SOLD, EventListener
        source.controller.set_tag(GameTag.TRINKET_COUNTER, 0)  # turn-based: 0 = not yet sold this turn

        class _GemDonationAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                # Only trigger on first sell each turn
                if self.player.get_tag(GameTag.TRINKET_COUNTER, 0) >= 1:
                    return
                self.player.set_tag(GameTag.TRINKET_COUNTER, 1)
                # Find 3 highest-tier tavern minions
                tavern = self.player.tavern
                if not tavern:
                    return
                sorted_by_tier = sorted(tavern, key=lambda m: m.get_tag(GameTag.TECH_LEVEL, 1), reverse=True)
                top3 = sorted_by_tier[:3]
                for tm in top3:
                    g.queue_action(PlayBloodGems(tm, 1))

        game.register_listener(source, EventListener(
            event_name=MINION_SOLD,
            action=_GemDonationAction(source.controller),
        ))


# ════════════════ Phase 19c: Designer Eyepatch — 2 Copies for Golden ═══════════

class DesignerEyepatchScript:
    """You only need 2 copies to make a Pirate golden.

    Formal spec:
      1. on_summon: set PIRATES_NEED_2_COPIES = True on controller
      2. _check_for_triple checks this tag for pirates (engine change in game.py)
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.PIRATES_NEED_2_COPIES, True)


# ════════════════ Phase 19d: Orb of the Unknown — Random Lesser Trinket ════════

class OrbOfTheUnknownScript:
    """
    Natural language: Get a random Lesser Trinket.

    Formal spec:
      1. on_summon: DiscoverTrinket(player, lesser_only=True)
      2. Adds a random Lesser Trinket without replacing this one

    Test: after equip, player has an additional Lesser Trinket.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import DiscoverTrinket
        game.queue_action(DiscoverTrinket(source.controller, lesser_only=True), source=source)
        return None


# ════════════════ Phase 19e: Spitescale Sushi Roll — Extra Spellcraft ══════════

class SpitescaleSushiRollScript:
    """Get a Spitescale Special. Your first 2 Spellcraft spells each turn
    cast an extra time.

    Formal spec:
      1. on_summon: add Spitescale Special (BG28_606) to hand
      2. Set SPELLCRAFT_EXTRA_CASTS = 2 on controller (reset each turn)
    """
    TOKEN_ID = "BG28_606"

    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(AddToHand(source.controller, cls.TOKEN_ID), source=source)
        source.controller.set_tag(GameTag.SPELLCRAFT_EXTRA_CASTS,
                                   source.controller.get_tag(GameTag.SPELLCRAFT_EXTRA_CASTS, 0) + 2)


# ════════════════ Phase 19f: Electrode Attractor — Magnetic Cost + Refresh ═════

class ElectrodeAttractorScript:
    """Magnetic Mechs cost (2). Whenever you Refresh, always offer an additional
    Magnetic Mech.

    Formal spec:
      1. on_summon: set MAGNETIC_COST_OVERRIDE = 2 on controller
      2. register TAVERN_REFRESH listener → add random magnetic mech to tavern
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.MAGNETIC_COST_OVERRIDE, 2)
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _RefreshMagneticAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                from hsrl.core.card_db import CARDS
                magnetic_ids = [
                    cid for cid, data in CARDS._cards.items()
                    if data.cardtype == 4
                    and data.tags.get(GameTag.MAGNETIC)
                    and not cid.startswith("EXAMPLE")
                ]
                if magnetic_ids:
                    token = g.create_minion(game.rng.choice(magnetic_ids))
                    if token:
                        token.controller = self.player
                        token.zone = Zone.PLAY
                        self.player.tavern.append(token)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshMagneticAction(source.controller),
            condition=lambda player: player == source.controller,
        ))


# ════════════════ Phase 19h: Conductor Portrait — Get Howler Driver ════════════

class ConductorPortraitScript:
    """Get a Howler Driver. After you play a Blood Gem, play one on a random friendly.

    Formal spec:
      1. on_summon: add Howler Driver (BG30_402) to hand
      2. Register BLOOD_GEM_PLAYED listener → bonus Blood Gem on random friendly
    """
    HOWLER_ID = "BG30_402"

    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(AddToHand(source.controller, cls.HOWLER_ID), source=source)

        from hsrl.core.events import BLOOD_GEM_PLAYED, EventListener

        class _BonusBloodGem(Action):
            def do(self, source_ent, game_ref, target=None):
                board = _living_board(source.controller)
                if not board:
                    return
                target = game.rng.choice(board)
                game_ref.queue_action(PlayBloodGems(
                    target, 1, trigger_played_event=False,
                ))

        game.register_listener(source, EventListener(
            event_name=BLOOD_GEM_PLAYED,
            action=_BonusBloodGem(),
            condition=lambda minion, player, count=1: (
                player == source.controller
                and bool(getattr(game, "_blood_gem_from_hand", False))
            ),
        ))


# ════════════════ Phase 19g0: Innkeeper's Stein — Extra Higher Tier ════════════

class InnkeepersSteinScript:
    """Whenever you Refresh, also offer an additional minion of a higher Tier.

    Formal spec:
      1. on_summon: register TAVERN_REFRESH listener
      2. Listener: add 1 random minion of current tier + 1 to the tavern
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _SteinAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if len(self.player.tavern) >= 7:
                    return
                higher_tier = min(self.player.tavern_tier + 1, 6)
                card_id = g.minion_pool.draw(tavern_tier=higher_tier, count=1) if g.minion_pool else None
                if card_id:
                    token = g.create_minion(card_id[0])
                    if token:
                        token.controller = self.player
                        token.zone = Zone.TAVERN
                        self.player.tavern.append(token)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_SteinAction(source.controller),
            condition=lambda player: player == source.controller,
        ))


# ════════════════ Phase 19g1: Guiding Candle — Tier-6 Only Refresh ═════════════

class GuidingCandleScript:
    """Your first 2 Refreshes each turn only contain Tier 6 minions.

    Formal spec:
      1. on_summon: set GUIDING_CANDLE_REFRESHES = 2 on controller
      2. refresh_tavern checks this → if >0, draws only tier 6
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.GUIDING_CANDLE_REFRESHES,
                                   source.controller.get_tag(GameTag.GUIDING_CANDLE_REFRESHES, 0) + 2)


class WarbandWhistleScript:
    """Gain a free Refresh that includes original copies of your warband minions.

    Formal spec:
      1. on_summon: add 3 random minions from your board to the tavern, GainFreeRefresh(1)
      2. The free refresh then fills the remaining slots normally
    """
    @staticmethod
    def on_summon(source, game):
        # Add copies of board minions to tavern
        board = source.controller.get_board_minions()
        if board:
            slots = min(3, 7 - len(source.controller.tavern))
            for m in game.rng.sample(board, min(slots, len(board))):
                if len(source.controller.tavern) >= 7:
                    break
                token = game.create_minion(m.get_tag(GameTag.CARD_ID))
                if token:
                    token.controller = source.controller
                    token.zone = Zone.TAVERN
                    source.controller.tavern.append(token)
        game.queue_action(GainFreeRefresh(source.controller, 1), source=source)


# ════════════════ Phase 20: Implicator Portrait — Get False Implicators ════════

class ImplicatorPortraitScript:
    """Get 2 False Implicators. Your demons always eat the highest-health
    tavern minion.

    Formal spec:
      1. on_summon: add 2x False Implicator (BG29_140) to hand
      2. Set IMPLICATOR_CONSUME_HIGHEST flag → ConsumeTavernMinion uses max-health
    """
    IMP_ID = "BG29_140"

    @classmethod
    def on_summon(cls, source, game):
        for _ in range(2):
            game.queue_action(AddToHand(source.controller, cls.IMP_ID), source=source)
        source.controller.set_tag(GameTag.IMPLICATOR_CONSUME_HIGHEST, True)


# ════════════════ Phase 20b: Pilgrimp Sticker — Health-Cost Demon ══════════════

class PilgrimpStickerScript:
    """One Demon per turn can be bought with Health instead of Gold.

    Formal spec:
      1. on_summon: set HEALTH_COST_DEMON = 1 on controller
      2. buy_minion checks this tag; if demon → pay with health
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.HEALTH_COST_DEMON, 1)


class BazaarStickerScript:
    """One Tavern Spell per turn can be bought with Health instead of Gold.

    Formal spec:
      1. on_summon: set HEALTH_COST_SPELL = 1 on controller
      2. buy_spell checks this tag; if set → pay with health
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.HEALTH_COST_SPELL, 1)


# ════════════════ Phase 20c: Tarecgosa Sticker — Dragon Combat Persistence ═════

class TarecgosaStickerScript:
    """Your left- and right-most Dragons permanently keep extra keywords
    and stats gained during combat.

    Formal spec:
      1. on_summon: set COMBAT_PERSIST_DRAGONS = True on controller
      2. _persist_combat_stats copies buffs from combat clone to original
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.COMBAT_PERSIST_DRAGONS, True)


# ════════════════ Phase 20d: Tide Raiser Portrait — Get Tidemistress ═══════════

class TideRaiserPortraitScript:
    """Get a Tidemistress Athissa. In combat, after you cast a spell, get a copy.

    Formal spec:
      1. on_summon: add Tidemistress Athissa (BG23_013) to hand
      2. Register TAVERN_SPELL_CAST listener → in combat → add copy to hand
    """
    CARD_ID = "BG23_013"

    @classmethod
    def on_summon(cls, source, game):
        game.queue_action(AddToHand(source.controller, cls.CARD_ID), source=source)

        from hsrl.core.events import EventListener

        class _GetCopyOnCombatSpell(Action):
            def do(self, source_ent, game_ref, target=None):
                if not game_ref.in_combat:
                    return
                if len(source.controller.hand) < 10:
                    game_ref.queue_action(AddToHand(source.controller, cls.CARD_ID))

        game.register_listener(source, EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_GetCopyOnCombatSpell(),
            condition=lambda spell, player: player == source.controller,
        ))


# ════════════════ Phase 20e: Mystery Cube — Discover Trinket Each Turn ══════════

class MysteryCubeScript:
    """
    Natural language: At the start of each turn, Discover a new Lesser Trinket
    to replace this one.

    Formal spec:
      1. start_of_turn: DiscoverTrinket(player, replace_source=True, lesser_only=True)
      2. New trinket replaces this one, triggering its on_summon

    Test: at turn start, trinket is replaced by a new Lesser Trinket.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.actions import DiscoverTrinket
        return DiscoverTrinket(source.controller, replace_source=True, lesser_only=True)


class SouvenirStandScript:
    """
    Natural language: When you buy a Greater Trinket, this transforms into its copy.

    Formal spec:
      1. on_summon: register TRINKET_OFFERED listener
      2. When a greater trinket is acquired: DiscoverTrinket with replace_source
         and greater_only (copies the greater trinket effect)

    Test: buying a greater trinket replaces this with a greater trinket.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _CopyGreater(Action):
            def __init__(self, trinket):
                super().__init__()
                self.trinket = trinket
            def do(self, s, g, target=None):
                from hsrl.core.actions import DiscoverTrinket
                g.queue_action(DiscoverTrinket(
                    self.trinket.controller, replace_source=True, greater_only=True))

        game.register_listener(source, EventListener(
            event_name="TRINKET_OFFERED",
            action=_CopyGreater(source),
            condition=lambda p, cid: p == source.controller,
        ))
        return None


class TripVouchersScript:
    """
    Natural language: After 2 turns, Discover a Greater Trinket to replace this.

    Formal spec:
      1. on_summon: set TRINKET_COUNTER = 2 on source
      2. start_of_turn: decrement counter; when 0 → DiscoverTrinket(replace, greater)
    Test: after 2 turns, trinket is replaced by a Greater Trinket.
    """

    @staticmethod
    def on_summon(source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 2)
        return None

    @classmethod
    def start_of_turn(cls, source, game):
        counter = source.get_tag(GameTag.TRINKET_COUNTER, 0) - 1
        if counter <= 0:
            from hsrl.core.actions import DiscoverTrinket
            return DiscoverTrinket(source.controller, replace_source=True, greater_only=True)
        source.set_tag(GameTag.TRINKET_COUNTER, counter)
        return None


# ════════════════ Phase 19g: Artanis Sticker — Copy Specific Card ══════════════

class ArtanisStickerScript:
    """Get a copy of a specific card (hero-dependent, {0} in card text).

    Uses ARTANIS_COPY_TARGET tag set during trinket offer. Falls back to
    copying the player's leftmost minion.
    """
    @classmethod
    def on_summon(cls, source, game):
        target_id = source.get_tag(GameTag.ARTANIS_COPY_TARGET)
        if target_id:
            game.queue_action(AddToHand(source.controller, target_id), source=source)
        else:
            # Fallback: copy leftmost minion
            board = source.controller.get_board_minions()
            living = [m for m in board if not m.dead]
            if living:
                game.queue_action(AddToHand(source.controller, living[0].data.id), source=source)


# ═══════════════════════════════════════════════════════════════════════════════
# Generic / DEFERRED
# ═══════════════════════════════════════════════════════════════════════════════

class UITimerScript:
    """UI-only timer indicator — no gameplay effect. Shows trinket shop countdown."""
    pass


class OutOfScopeDuosScript:
    """OUT_OF_SCOPE: Duos trinket — this project is Solo-only. No Duos content is implemented."""
    pass


class SoTGenericScript:
    """Generic Start of Turn effect — DEFERRED, each trinket has unique logic."""
    pass

class EternalPortraitScript:
    """Get an Eternal Knight. SoC: Give your Eternal Knights Taunt and Reborn."""
    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_all(source, atk=1, health=1)


class AutomatonPortraitScript:
    """Start of Combat: When you have space, summon an Ancestral Automaton."""
    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        from hsrl.core.actions import Summon
        if len(source.controller.board) < 7:
            token = game.create_minion("BG_TTN_401")
            if token:
                return Summon(source.controller, token)
        return None


class RivendarePortraitScript:
    """Get a Titus Rivendare. Your Deathrattles trigger an extra time."""
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller.set_tag(GameTag.DEATHRATTLE_DOUBLED, True)


class ReflectivePendantScript:
    """Start of Combat: Give your minions +1 Attack."""
    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        return _buff_all(source, atk=1, health=0)


class TokenOfTheOldGodsScript:
    """Spellcraft: Choose a minion to transform into one from a higher Tier."""
    # DEFERRED: Needs Spellcraft + Discover one-Tier-higher minion + Transform

    @staticmethod
    def spellcraft(source, game):
        return None  # DEFERRED


class BobBleheadScript:
    """
    Natural language: Gain 2 Gold. The Tavern no longer offers cards from
    Tier 1 or Tier 2.

    Formal spec:
      1. on_summon: set _tavern_min_tier = 3 on controller (no tier 1-2)
      2. start_of_combat: GainGold(2)
      3. Engine checks _tavern_min_tier during refresh_tavern

    Test: after equip, tavern minions are all tier 3+.
    """
    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        return GainGold(source.controller, 2)

    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.controller._tavern_min_tier = 3


class BronzeTimepieceScript:
    """Start of Combat: Give each minion Health equal to half its Attack."""
    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        actions = []
        for m in source.controller.board:
            if not m.dead:
                bonus = m.atk // 2
                if bonus > 0:
                    actions.append(Buff(m, atk=0, health=bonus))
        return actions if actions else None


class EmeraldDreamcatcherScript:
    """Start of Combat: Set your Dragons' Attack to the highest in your warband."""
    @staticmethod
    def start_of_combat(source: BaseEntity, game: Game) -> Optional[Action]:
        board = _living_board(source.controller)
        if not board:
            return None
        max_atk = max(m.atk for m in board)
        dragons = [m for m in board if m.race == Race.DRAGON]
        actions = []
        for d in dragons:
            diff = max_atk - d.atk
            if diff > 0:
                actions.append(Buff(d, atk=diff, health=0))
        return actions if actions else None


class FelbatPortraitScript:
    """
    Natural language: Get a Famished Felbat. The Tavern always has 7 cards.

    Formal spec:
      1. on_summon: AddToHand(source.controller, "BG28_900") — Famished Felbat
      2. Set a flag on the player for always-7-tavern (DEFERRED: tavern size mod)

    Test: player has Famished Felbat in hand after trinket purchase.
    """
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        game.queue_action(AddToHand(source.controller, "BG28_900"))


class CorruptedTomeScript:
    """Get a Triple Prize. Triple Rewards become Triple Prizes instead.

    Formal spec:
      1. on_summon: set TRIPLE_REWARD_PRIZE flag on player
      2. Engine (_combine_triple) checks flag → DiscoverPrize instead of DiscoverMinion
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.TRIPLE_REWARD_IS_PRIZE, True)
        return None


class DazzlingDaggerScript:
    """Your minions have +1 Attack. Improves by every 4 spells cast this game."""
    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        from hsrl.core.actions import GlobalAura
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        aura = GlobalAura(atk=1 + counter, health=0)
        source.controller.auras.append(aura)
        source._aura = aura


# ═══════════════════════════════════════════════════════════════════════════════
# Patch 35.6.0 — New trinkets
# ═══════════════════════════════════════════════════════════════════════════════

class ChillmereMosaicScript:
    """Status: DEFERRED — Spellcraft: Refresh Tavern with Battlecry minions at cost (1).
    Dependency: filtered tavern refresh + trinket spellcraft subsystem."""
    @staticmethod
    def spellcraft(source, game):
        return None


class DoubleStitchNeedleScript:
    """Status: DEFERRED — Spellcraft: Double a minion's stats, lock in hand 1 turn.
    Dependency: stat-doubling action + hand-lock mechanism."""
    @staticmethod
    def spellcraft(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# TRINKET_SCRIPT_REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

TRINKET_SCRIPT_REGISTRY: dict = {
    # ── Standard Example ──
    "EXAMPLE_TRINKET": ExampleTrinketScript,

    # ── SoC: Buff All ──
    "BG30_MagicItem_438t": MugOfTheSireScript,          # Mug of the Sire: overflow minion → +5 Atk to all
    "BG30_MagicItem_970": SoCBuffAll2x2Script,         # Valorous Medallion (Lesser)
    "BG30_MagicItem_970t": SoCBuffAll6x6Script,        # Valorous Medallion (Greater)
    "BG30_MagicItem_706": ReflectivePendantScript,     # Reflective Pendant: +1 Atk all

    # ── SoC: Summon ──
    "BG30_MagicItem_303": AutomatonPortraitScript,     # Automaton Portrait
    "BG32_MagicItem_960": SoCSummonScript,             # Crocheted Sungill

    # ── SoC: Keywords ──
    "BG32_MagicItem_360": SoCGiveLeftRightMostKeywordScript,  # Baleful Incense: Reborn to L/R Undead

    # ── Passive Auras ──
    "BG30_MagicItem_310": RivendarePortraitScript,     # Rivendare Portrait: DR double
    "BG32_MagicItem_416": BCDoubleScript,              # War Drum: BC doubling
    "BG30_MagicItem_804": HeroPowerDoubleScript,       # Ancient Wishbone: HP double

    # ── Economy ──
    "BG32_MagicItem_823": GainGold2Script,             # Wax Imprinter: Gain 2 Gold
    "BG30_MagicItem_998": BobBleheadScript,            # Bob-blehead: Gain 2 Gold + tier filter
    "BG30_MagicItem_996": GainGold4Script,             # Bob's Tip Jar: Gain 4 Gold
    "BG30_MagicItem_847": EoTImproveGoldCapScript,     # Goblin Wallet: +1 max gold EoT

    # ── Unique Scripts ──
    "BG30_MagicItem_301": EternalPortraitScript,       # Eternal Portrait
    "BG30_MagicItem_416": TokenOfTheOldGodsScript,     # Token of the Old Gods (DEFERRED)
    "BG30_MagicItem_995": BronzeTimepieceScript,       # Bronze Timepiece
    "BG30_MagicItem_542": EmeraldDreamcatcherScript,   # Emerald Dreamcatcher
    "BG30_MagicItem_991": FelbatPortraitScript,        # Felbat Portrait
    "BG30_MagicItem_429": SpellcraftConsumeTavernMinionScript,  # Demonblood Gourd
    "BG35_MagicItem_812": CorruptedTomeScript,         # Corrupted Tome (DEFERRED)

    # ── EoT ──
    "BG30_MagicItem_984": EoTBuffDivineShieldScript,   # Charging Staff (Lesser): +3 Atk to DS
    "BG32_MagicItem_231": EoTBuffGoldenScript,         # Gilded Anchor (Lesser): +3/+3 to Golden
    "BG32_MagicItem_276": EoTBuffTribeScript,          # Enigmatic Headstone: Undead +2 Atk

    # ── Avenge ──
    "BG32_MagicItem_864": AvengeBuffAllScript,         # Bird Feeder (Lesser): Avenge(2) +1/+1 all
    "BG32_MagicItem_860": AvengeSummonScript,          # Beetle Band (Lesser): Avenge(5) summon
    "BG32_MagicItem_860t": AvengeSummonScript,         # Beetle Band (Greater): Avenge(6) summon
    "BG30_MagicItem_545": AvengeGetRandomMagneticScript,  # Fridge Magnet: Avenge(3) get Magnetic
    "BG30_MagicItem_864": AvengeBuffAllPermanentScript,   # Gilnean Thorned Rose: Avenge(3) +3/+3 perm

    # ── Auras ──
    "BG30_MagicItem_880": AuraStatsScript,             # Feral Talisman (Lesser): +2/+1 aura
    "BG30_MagicItem_880t": AuraStatsScript,            # Feral Talisman (Greater): +8/+5 aura
    "BG30_MagicItem_989": ArtisanalUrnUndead3Script,    # Artisanal Urn (Lesser): Undead +3 Atk
    "BG30_MagicItem_989t": ArtisanalUrnUndead10Script,  # Artisanal Urn (Greater): Undead +10 Atk
    "BG32_MagicItem_934": DazzlingDaggerScript,        # Dazzling Dagger: +1 Atk (Improves)

    # ── Cost Reduction ──
    "BG35_MagicItem_921": SpellCostReductionScript,    # Cowrie Necklace: Spell cost (2) less

    # ── SoT: Discover / Get ──
    "BG30_MagicItem_420": SoTDiscoverTavernSpellScript,   # Book of Medivh (Lesser)
    "BG30_MagicItem_420t": SoTDiscoverTavernSpellScript,  # Book of Medivh (Greater)
    "BG30_MagicItem_430": SoTGetRandomBattlecryScript,    # Rockin' Music Box
    "BG32_MagicItem_361": SoTDiscoverMinionScript,        # Portable Factory (Lesser)
    "BG32_MagicItem_361t": SoTDiscoverMinionScript,       # Portable Factory (Greater)
    "BG35_MagicItem_301": SoTGetRandomMagneticScript,     # Scraper Sticker

    # ── SoT: Cast Spell ──
    "BG32_MagicItem_286": SoTCastSpellScript,             # Lavish Cape
    "BG35_MagicItem_850": PocketCycloneScript,            # Pocket Cyclone (Lesser): cast Easterly Winds once
    "BG35_MagicItem_850t": SoTCastSpellScript,            # Pocket Cyclone (Greater): cast Easterly Winds x2

    # ── SoT: Repeat Get (specific named minion) ──
    "BG30_MagicItem_406": ButcherSickleScript,            # Butcher's Sickle: get Butchering
    "BG30_MagicItem_987": BalladistPortraitScript,        # Balladist Portrait: get Lovesick Balladist
    "BG31_MagicItem_903": WisdomballSupplyScript,         # Wisdomball Supply: get Knockoff Wisdomball
    "BG32_MagicItem_831": SellementalPortraitScript,      # Sellemental Portrait: get Sellemental
    "BG30_MagicItem_916": SoTRepeatGetScript,             # Essence of Dreams: get Dreamer's Embrace 
    # ── SoT: Repeat Get (random tribe) ──
    "BG30_MagicItem_543": SoTRepeatGetRandomDemonScript,  # Devourer Sticker: random Demon
    "BG30_MagicItem_942": SoTGetRandomMagneticMechScript, # Mecha-Jaraxxus Sticker: 2 Magnetic Mecha-Demons
    "BG35_MagicItem_309": SoTRepeatGetRandomMurlocScript, # Errgl Sticker: random Murloc

    # ── SoT: Repeat Get (random tier) ──
    "BG30_MagicItem_993": SoTRepeatGetTier7Script,        # Pagle's Fishing Rod: random Tier 7

    # ── SoT: Repeat Get (Blood Gem) ──
    "BG35_MagicItem_434": SoTRepeatGetBloodGemScript,     # Jewelry Box: Blood Gem

    # ── SoT: Repeat Get (Bounty) ──
    "BG35_MagicItem_890": SoTRepeatGetBounty2Script,      # Sunken Anchor: 2 random Bounties

    # ── SoT: Generic / DEFERRED ──
    "BG30_MagicItem_426": GetRandomMinionRepeatScript,               # Colorful Compass (Lesser): DEFERRED - random type not controlled
    "BG30_MagicItem_426t": Get2RandomMinionsRepeatScript,              # Colorful Compass (Greater): DEFERRED
    "BG30_MagicItem_703": MysteryCubeScript,               # Mystery Cube: discover lesser trinket each turn (approx)
    "BG30_MagicItem_705": ReduceUpgradeCostRepeatScript,               # Bartend-o-Tron's Oilcan: DEFERRED - Tavern upgrade cost
    "BG30_MagicItem_930": SoTGetCopyLastOpponentHighestScript,               # Burgling Claw: DEFERRED - copy from last opponent
    "BG30_MagicItem_994": SoTSpinYoggWheelScript,               # Yogg-Tastic Pastry: DEFERRED - spin Wheel of Yogg
    "BG32_MagicItem_700": SoTMarvelousMushroomScript,      # Marvelous Mushroom: tavern spell buff +1/+1 per turn
    "BG32_MagicItem_931": SoTGetRandomSpellcraftScript,               # Azsharan Statuette: DEFERRED - random Spellcraft spells
    "BG32_MagicItem_950": SoTRepeatGetGrittyHeadhunterScript,               # Gritty Portrait: DEFERRED - needs Marauder's Contract
    "BG32_MagicItem_951": SoTGoldenRandomMinionScript,               # Gold Pendant: DEFERRED - make random minion golden
    "BG35_MagicItem_712": SoTRepeatGetPrivateerScript,               # Privateer Portrait: DEFERRED - mixed get Proud Privateer + Bounties

    # ── SoC: Unique ──
    "BG30_MagicItem_441": SoCLeftmostGainsHighestHealthScript,  # Tinyfin Onesie: leftmost gains highest health
    "BG30_MagicItem_962": SoCDoubleLowestStatsScript,           # Training Certificate: double lowest atk
    "BG32_MagicItem_365": SoCDoubleScript,                      # Valdrakken Wind Chimes: SoC double
    "BG30_MagicItem_902": SoCGiveLeftRightMostKeywordScript,    # Holy Mallet: L/R Divine Shield

    # ── EoT: Variants ──
    "BG35_MagicItem_753": EoTBuffLeftmostScript,          # Murky Sticker: buff leftmost
    "BG32_MagicItem_111": ToxicStingerScript,              # Toxic Stinger: +8/+8 and Venomous to random Murloc
    "BG32_MagicItem_832": EoTGetWindfallScript,           # Windfall Portrait (Lesser): get Windfall Tornado
    "BG32_MagicItem_832t": EoTGetWindfallScript,          # Windfall Portrait (Greater)
    "BG35_MagicItem_752": EoTTriggerBattlecriesScript,    # Young Murk-Eye Sticker: trigger L/R BCs

    # ── On Buy: Buff Two Random ──
    "BG30_MagicItem_414": OnBuyBuffTwoRandom1x1Script,    # Kodo Leather Pouch (Lesser)
    "BG30_MagicItem_414t": OnBuyBuffTwoRandom1x1Script,   # Kodo Leather Pouch (Greater)

    # ── On Play: Buff Tribe ──
    "BG30_MagicItem_900": OnPlayBuffDragonScript,         # Dragonwing Glider (Lesser): play card → buff Dragon
    "BG30_MagicItem_900t": OnPlayBuffDragonScript,        # Dragonwing Glider (Greater)

    # ── On Spend Gold: Buff ──
    "BG30_MagicItem_924": OnSpendGoldBuffMurlocScript,    # Booty Bay Brew (Lesser): spend gold → buff
    "BG30_MagicItem_924t": OnSpendGoldBuffMurlocScript,   # Booty Bay Brew (Greater)

    # ── Get Random Minions by Tier ──
    "BG32_MagicItem_350": GetRandomMinionsTierScript,     # Splinter of Aurum
    "BG32_MagicItem_858": GetRandomMinionsTierScript,     # Explorer's Binoculars
    "BG32_MagicItem_304": GetRandomMinionsTier1x6Script,  # Horn of Summoning: get 6 Tier 1 minions

    # ── Tavern Buff Aura ──
    "BG30_MagicItem_541": TavernBuffAuraScript,           # Nether Pendant: +1 atk tavern
    "BG30_MagicItem_841": TavernBuffAuraScript,           # Glowing Gauntlet: +3/+3 tavern
    "BG30_MagicItem_879": TavernBuffAura2x1Script,        # Dalaran Cheese Wheel (Lesser): +2/+1
    "BG30_MagicItem_879t": TavernBuffAura2x1Script,       # Dalaran Cheese Wheel (Greater): +2/+1
    "BG30_MagicItem_992": TavernBuffAura2x1Script,        # Darnassus Pie (Lesser): +2/+1
    "BG30_MagicItem_992t": TavernBuffAura2x1Script,       # Darnassus Pie (Greater): +2/+1

    # ── Counter: Buy ──
    "BG30_MagicItem_982": CounterBuyBCScript,               # Shaman Prayer Beads: buy 2 BC → get random BC

    # ── Counter: Sell ──
    "BG30_MagicItem_710": CounterSellMurlocScript,          # Fungalmancer Sticker: sell 5 → random Murloc
    "BG30_MagicItem_951": CounterSellElementalScript,       # Lava Lamp: sell 5 → random Elemental
    "BG35_MagicItem_863": CounterSellTokenScript,           # Avalanche Sticker: sell 4 → Mounting Avalanche

    # ── Counter: Spell Cast ──
    "BG32_MagicItem_930": CounterSpellCastNagaScript,       # Archaic Scroll: cast 6 spells → random Naga
    "BG32_MagicItem_808": CounterSpellCastBloodGemAll5x1Script,   # Bloodbound Earrings (Lesser): cast 5 → BG on all
    "BG32_MagicItem_808t": CounterSpellCastBloodGemAll5x2Script,  # Bloodbound Earrings (Greater): cast 5 → 2 BG on all

    # ── Counter: Refresh ──
    "BG35_MagicItem_152": CounterRefreshHealthCostScript,   # Demonic Tapestry: refresh 3 → health cost (DEFERRED)

    # ── Counter: Death ──
    "BG30_MagicItem_713": CounterDeathGetUndeadScript,       # Bleeding Heart: 9 friendly die → random Undead
    "BG30_MagicItem_931": CounterDeathGetBeastScript,        # Lucky Tabby: 7 friendly die → random Beast
    "BG35_MagicItem_302": CounterDeathGetMechScript,         # Stormcoil Sticker: 7 friendly die → random Mech

    # ── Counter: Spend Gold ──
    "BG32_MagicItem_232": CounterSpendGoldBuffPirateScript,  # Shark Cannon: spend 10 Gold → buff Pirates + improve
    "BG30_MagicItem_999": CounterSpendGoldCastSpellScript,   # Fancy Spellbook: spend 7 Gold → cast Shiny Ring

    # ── Avenge: Variants ──
    "BG32_MagicItem_864t": AvengeBuffAll4x4Script,          # Bird Feeder (Greater): Avenge(2) +4/+4 all

    # ── EoT: Buff Leftmost Variants (improve/repeat parts DEFERRED) ──
    "BG32_MagicItem_890": EoTBuffLeftmost3x2Script,         # Cliffdiver Sticker: EoT +3/+2 leftmost (improve DEFERRED)
    "BG32_MagicItem_922": EoTBuffLeftmost2x2Script,         # Charming Panpipes: EoT +3/+3 leftmost
    "BG32_MagicItem_954": EoTBuffLeftmost4x3Script,         # Auric Offering: EoT +4/+3 leftmost (repeat DEFERRED)

    # ── Phase 7: New registrations ──

    # ── EoT: Variants ──
    "BG30_MagicItem_984t": EoTBuffDivineShield7x0Script,    # Charging Staff (Greater): +7 Atk to DS
    "BG32_MagicItem_231t": EoTBuffGolden10x10Script,        # Gilded Anchor (Greater): +10/+10 to Golden
    "BG32_MagicItem_367": EoTDoubleScript,                  # Ghastly Sticker: EoT extra time

    # ── Avenge: Give Keyword ──
    "BG30_MagicItem_437": AvengeGiveRebornUndeadScript,     # Staff of the Scourge: Avenge(5) give random Undead Reborn

    # ── SoC: Give Keyword (Tribe-targeted) ──
    "BG35_MagicItem_702": SoCGiveTwoLeftmostBeastsDSScript,  # Stegodon Portrait: SoC give 2 leftmost Beasts DS
    "BG35_MagicItem_711": SoCGive4RandomPiratesDSScript,     # Protective Ring: SoC give 4 random Pirates DS

    # ── Phase 8: On Play Tribe ──
    "BG30_MagicItem_544": OnPlayElementalTavernBuffScript,    # Nomi Sticker (Lesser): play Elemental → Elementals in Tavern +2/+2
    "BG30_MagicItem_544t": OnPlayElementalTavernBuff4x4Script, # Nomi Sticker (Greater): play Elemental → +5/+5
    "BG32_MagicItem_888": OnPlayElementalFreeRefreshScript,   # Recycling Sticker: play Elemental → free Refresh
    "BG35_MagicItem_851": OnPlayElementalGetTavernSpellScript, # Water Wheel: play Elemental → get random Tavern spell

    # ── Phase 8: Per-Cast Tavern Spell ──
    "BG32_MagicItem_281": OnCastBuffTribelessScript,          # Wizard's Pipe: cast spell → tribeless +4/+4
    "BG35_MagicItem_710": OnCastBuffPirateScript,              # Miniature Ship: cast spell → Pirates +2/+2

    # ── Combat Death: First Death Transfer Stats ──
    "BG30_MagicItem_433": FirstDeathTransferStatsScript,       # Alliance Keychain (Lesser): first death → transfer to 1
    "BG30_MagicItem_433t": FirstDeathTransferStats2xScript,    # Alliance Keychain (Greater): first death → transfer to 2
    "BG30_MagicItem_981": OnFriendlyDeathCombatGetTavernSpellScript,  # Eye of Dalaran: tribeless dies → Tavern spell

    # ── Phase 9: Every N Turns ──
    "BG30_MagicItem_425": Every2TurnsGainGoldDiscoverT6Script,   # Azeroth Model Globe: every 2 turns gain 2 Gold + Discover T6
    "BG30_MagicItem_435": GoldenizerSupplyScript,                # Goldenizer Supply: every 3 turns get Goldenizer
    "BG30_MagicItem_707": DiscoverTier3DarkmoonPrizeScript,      # Tickatus Sticker: every 3 turns Discover Darkmoon Prize (DEFERRED: Darkmoon pool)
    "BG32_MagicItem_300": Every2TurnsCraftUndeadScript,          # Putricide Sticker: every 2 turns craft Undead
    "BG35_MagicItem_305": ConchPortraitScript,                   # Conch Portrait: every 2 turns get Cloning Conch
    "BG35_MagicItem_817": LensCaseGetScript,                     # Lens Case: every 2 turns get Duplicating Lens
    "BG35_MagicItem_817t": DuplicatingLensScript,                # Duplicating Lens: copy of first summon each combat

    # ── Phase 11: Combat Events ──

    # ── Combat On Attack ──
    "BG32_MagicItem_200": OnAttackBuffBeastScript,             # All-Purpose Kibble: Beast attacks → +2 Atk (improves)
    "BG30_MagicItem_925": OnAttackBuffScript,                  # Ceremonial Sword: friendly attacks → +4 Atk

    # ── Combat On Lose Divine Shield ──
    "BG30_MagicItem_910": OnLoseDSRegainDSScript,              # Mechagon Adapter: Mech loses DS → regain DS (3x)
    "BG32_MagicItem_171": OnLoseDSGetSpellScript,              # Divine Signet: lose DS → get Tavern spell (4x)

    # ── Combat On Lose Venomous ──
    "BG30_MagicItem_432": OnLoseVenomousBuffScript,            # Belcher Portrait (Lesser): lose Venomous → +4/+4 (DEFERRED)
    "BG30_MagicItem_432t": OnLoseVenomousBuffScript,           # Belcher Portrait (Greater): lose Venomous → +14/+14 (DEFERRED)

    # ── Combat On Summon ──
    "BG30_MagicItem_886": OnSummonInCombatGiveDSScript,        # Reinforced Shield: summon in combat → DS (5x)
    "BG30_MagicItem_540": OnSummonBeastDoubleAtkScript,        # Slamma Sticker: summon Beast in combat → double Atk
    "BG32_MagicItem_301": OnSummonMurlocGiveDSScript,          # Bassgill Portrait: summon Murloc in combat → DS
    "BG30_MagicItem_978": OnSummonMechGiveMechDSScript,        # Blingtron's Sunglasses: summon Mech → give friendly Mech DS

    # ── Phase 12: Blood Gem ──
    "BG30_MagicItem_988": GreatBoarStickerLesserScript,        # Great Boar Sticker (Lesser): get 3 BG, BG give +2/+1
    "BG30_MagicItem_988t": GreatBoarStickerGreaterScript,      # Great Boar Sticker (Greater): get 5 BG, BG give +3/+3
    "BG32_MagicItem_904": HogwashBasinScript,                  # Hogwash Basin: SoC play 3 BG on all
    "BG30_MagicItem_411": HoggyBankScript,                     # Hoggy Bank: SoC give Quilboar DR: get 2 BG

    # ── Phase 12: Magnetic ──
    "BG35_MagicItem_300": OnMagnetizeBuffScript,               # Copper Coil (Lesser): Magnetize → +2/+1 (improves)
    "BG35_MagicItem_300t": OnMagnetizeBuff3x3ImproveScript,    # Copper Coil (Greater): Magnetize → +3/+3 (improves)
    "BG30_MagicItem_709t": DiscoverMagneticMechScript,         # Electromagnetic Device: Discover 2 Magnetic Mechs + on_magnetize buff 4/4
    "BG32_MagicItem_170": OnPlayMagneticGetSpellScript,        # Spell-powered Wrench: play Magnetic → get Tavern spell

    # ── Phase 13-15: Remaining trinkets (DEFERRED — need engine subsystems) ──

    "BG30_MagicItem_402": ConductorPortraitScript,  # Conductor Portrait: get Howler Driver (discard trigger defer)
    "BG30_MagicItem_403": SoCTripleTribelessStatsScript,    "BG30_MagicItem_407": SoCSummonAndGetPirateAttackScript,    "BG30_MagicItem_410": AvengeImproveBG1HealthScript,
    "BG30_MagicItem_410t2": AvengeImproveBG1x1Script,
    "BG30_MagicItem_418": GetBrannAndRandomBCScript,    "BG30_MagicItem_419": EoTGetRandomMinionPerTribeScript,
    "BG30_MagicItem_422": LorewalkerScrollLesserScript,  # Lorewalker Scroll (Lesser): cast spell on minion → +4/+4
    "BG30_MagicItem_422t": LorewalkerScrollGreaterScript, # Lorewalker Scroll (Greater): cast spell on minion → +8/+8
    "BG30_MagicItem_423": InnkeepersSteinScript,  # Innkeeper's Stein: refresh always offers extra higher-tier minion
    "BG30_MagicItem_427": OnFriendlyDamageBuffRandomScript,    "BG30_MagicItem_427t": OnFriendlyDamageBuffRandom4Script,    "BG30_MagicItem_431": GetLivingAzeriteElementalBonusScript,    "BG30_MagicItem_434": FirstSpellEachTurnExtraTimeScript,    "BG30_MagicItem_439": DesignerEyepatchScript,  # Designer Eyepatch: pirates only need 2 copies for golden
    "BG30_MagicItem_440": BoomControllerScript,  # Boom Controller: summon copy of first dead mech in combat
    "BG30_MagicItem_442": QuilboarDeathSummonGolemScript,    "BG30_MagicItem_546": CounterAttackPlayBGOnQuilboarScript,    "BG30_MagicItem_547": OnCastSpellBuffUndeadWhereverScript,    "BG30_MagicItem_547t": OnCastSpellBuffUndeadWherever2Script,    "BG30_MagicItem_548": GetTimewarpedGlowscaleScript,    "BG30_MagicItem_555": GetElementalOfSurpriseScript,    "BG30_MagicItem_700": DiscoverDRFirstDRExtraTimeScript,    "BG30_MagicItem_701": Every4BuysHealthCostScript,    "BG30_MagicItem_702": GetPrimalfinLookoutDiscoverSpellScript,    "BG30_MagicItem_709": ElectromagneticDeviceScript,  # Electromagnetic Device: discover magnetic + magnetize buff +3/+3
    "BG30_MagicItem_711": MarineSignetScript,  # Marine Signet: after 4 minions → get spell + improve tier
    "BG30_MagicItem_714": TrinketSpellcraft3030Script,
    "BG30_MagicItem_777": GetSilverGooseScript,    "BG30_MagicItem_803": GetKaboomBotDRBonusScript,    "BG30_MagicItem_821": GetFishOfNZothScript,    "BG30_MagicItem_821t2": SoCSummonGoldenFishNZothScript,    "BG30_MagicItem_822": TwinSkyLanternsScript,  # Twin Sky Lanterns (Lesser): summon copy of first summoned in combat
    "BG30_MagicItem_822t2": TwinSkyLanternsGreaterScript,  # Twin Sky Lanterns (Greater): summon 2 copies of first summoned
    "BG30_MagicItem_825": GetWhelpSmugglerSetStatsScript,    "BG30_MagicItem_828": GetZestyShakerExtraCopyScript,    "BG30_MagicItem_843t": SoCBuffLowTier75Script,    "BG30_MagicItem_868": GetSoulRewinderAndWrathWeaverScript,    "BG30_MagicItem_869": GetSlimyFelbloodScript,    "BG30_MagicItem_876": GetFacelessManipulatorScript,    "BG30_MagicItem_888": SouvenirStandScript,  # Souvenir Stand: transform into copy of greater trinket (approx)
    "BG30_MagicItem_891": TripVouchersScript,  # Trip Vouchers: after 2 turns discover greater trinket (approx)
    "BG30_MagicItem_914": OnPlayBuffLeftmostHandScript,    "BG30_MagicItem_914t": OnPlayBuffLeftmostHand6x6Script,    "BG30_MagicItem_917": SoCGiveNagaSpellcraftDRScript,    "BG30_MagicItem_918": GetPromoDrakeFirstSoCExtraTimeScript,    "BG30_MagicItem_919": OnPlayNagaGetSpellcraftScript,    "BG30_MagicItem_920": SpitescaleSushiRollScript,  # Spitescale Sushi Roll: get Spitescale Special + extra spellcraft casts
    "BG30_MagicItem_921": GetSkyPirateFlagbearerAuraScript,    "BG30_MagicItem_923": CounterPirateAttackGainGoldScript,    "BG30_MagicItem_943": GetHotAirSurveyorBGBonusScript,    "BG30_MagicItem_944": GetRedeemerPortraitScript,    "BG30_MagicItem_952": SoCGiveElementalFrostlingDRScript,    "BG30_MagicItem_971": GetLightfangAllTypesScript,    "BG30_MagicItem_972": SoCSummonCopyLeftmostScript,    "BG30_MagicItem_979": OnPlayElementalDiscountNextSpellScript,    "BG30_MagicItem_986": First3SpellsFreeEachTurnScript,    "BG30_Trinket_1st": UITimerScript,  # UI timer: Lesser Trinket shop countdown (no gameplay effect)
    "BG30_Trinket_2nd": UITimerScript,  # UI timer: Greater Trinket shop countdown (no gameplay effect)

    "BG32_MagicItem_172": GetDrBoomsMonsterRepeatScript,    "BG32_MagicItem_179": GetDrakkariMechElementalScript,    "BG32_MagicItem_204": GetArchlichKelThuzadScript,    "BG32_MagicItem_205": GetMawCasterDestroyCoinScript,    "BG32_MagicItem_230": CounterSpendGoldDoubleATKScript,    "BG32_MagicItem_270": AvengeImproveTavernSpellScript,    "BG32_MagicItem_270t": AvengeImproveTavernSpell1x1Script,    "BG32_MagicItem_271": DelayedGreaterTrinketGain3Script,  # Ornate Clock: gain 2 Gold (greater trinket timing defer)
    "BG32_MagicItem_274": GetBristlebachScript,    "BG32_MagicItem_278": OnBuyGetMagneticSatelliteScript,    "BG32_MagicItem_279": EoTPlayBGOnMinionOfEachTypeScript,    "BG32_MagicItem_280": SoCBuffOnePerTribeImproveScript,    "BG32_MagicItem_282": GetMagneticMechsScript,   # Magneto-Mechinator (Lesser): get 2 Magnetic Mechs
    "BG32_MagicItem_283": GetChargingCzarinaHealthScript,    "BG32_MagicItem_284": EoTPlayBGOnEachTribeScript,
    "BG32_MagicItem_306": SoCTriggerAllFriendlyDRScript,    "BG32_MagicItem_362": DiscoverTier6MinionSetStatsScript,    "BG32_MagicItem_362t": DiscoverTwoTier6SetStatsScript,    "BG32_MagicItem_363": OnFriendlyDragonAttackGiveDSScript,    "BG32_MagicItem_364": GetTimewarpedPoetScript,    "BG32_MagicItem_366": GuidingCandleScript,  # Guiding Candle: first 2 refreshes only tier 6
    "BG32_MagicItem_400": TransformAllToRandomTier4Script,    "BG32_MagicItem_415": AvengeDiscoverBCAndTriggerBCScript,    "BG32_MagicItem_417": TarecgosaStickerScript,  # Tarecgosa Sticker: left/right dragons keep combat stats
    "BG32_MagicItem_419": SoCMakeHighestTierDragonGoldenScript,    "BG32_MagicItem_428": DelayedGainGold10Script,    "BG32_MagicItem_801": SoTTavernSpellBuffCounterScript,  # Flask of Homunculation (Lesser): +1/+1 spell buff, improve after 5 spells
    "BG32_MagicItem_801t": SoTTavernSpellBuffCounterFromHandScript,  # Flask of Homunculation (Greater): +1/+1 from-hand spells, improve after 4
    "BG32_MagicItem_802": ElementalStatBonusScript,  # Azerite-Encrusted (Lesser): elementals give extra +2/+1
    "BG32_MagicItem_802t": ElementalStatBonusGreaterScript,  # Azerite-Encrusted (Greater): elementals give extra +4/+2
    "BG32_MagicItem_803": GetMonstrousMacawTriggerBCScript,    "BG32_MagicItem_804": GetSelflessHeroTriggerBCScript,    "BG32_MagicItem_806": GetBattlecruiser12x12Script,    "BG32_MagicItem_807": GetGoldenMishmashAndAmalgamScript,    "BG32_MagicItem_809": GemDonationScript,  # Gem Donation: first sell plays blood gems on 3 highest tavern minions
    "BG32_MagicItem_817": EoTStealHighestTavernRepeatScript,
    "BG32_MagicItem_820": GetImpulsiveTrickster6x6Script,    "BG32_MagicItem_821": PilgrimpStickerScript,  # Pilgrimp Sticker: one demon per turn buyable with health
    "BG32_MagicItem_822": BazaarStickerScript,  # Bazaar Sticker: one spell per turn buyable with health
    "BG32_MagicItem_824": ImplicatorPortraitScript,  # Implicator Portrait: get 2 False Implicators
    "BG32_MagicItem_830": GetFelementalExtraStatsScript,    "BG32_MagicItem_844": RemoveAllMinionsGainGoldScript,    "BG32_MagicItem_862": OnDRTriggerBuffRightmostScript,    "BG32_MagicItem_862t": OnDRTriggerBuffRightmost6x4Script,    "BG32_MagicItem_887": OnPlayDemonDealDamageToHeroScript,    "BG32_MagicItem_891": OnRefreshBuffMurlocsTavernScript,    "BG32_MagicItem_892": TrinketSpellcraftMurlocKeywordScript,
    "BG32_MagicItem_893": OnCastSpellBuffLeftmostHand4x4Script,    "BG32_MagicItem_894": SoTRepeatGetNaturalBlessingScript,  # Blessing Portrait: get Natural Blessing + one each turn
    "BG32_MagicItem_901": GoldPlatedCompassScript,  # Gold-plated Compass: next purchase golden + 5 free refreshes
    "BG32_MagicItem_902": After2ConsumedGetTavernSpellScript,    "BG32_MagicItem_906": ArtanisStickerScript,  # Artanis Sticker: get a copy of hero-dependent card
    "BG32_MagicItem_907": STharaStickerScript,  # S'Thara Sticker: after last friendly dies, summon first dead demon
    "BG32_MagicItem_920": GetSoulJugglerSpellcraftScript,  # Juggler Portrait: get Soul Juggler with permanent spellcraft
    "BG32_MagicItem_925": GetHackerfinEoTTriggerBCScript,    "BG32_MagicItem_926": GetTideOracleMorglScript,    "BG32_MagicItem_932": SoCBuffNagaImprovePerSpellsScript,    "BG32_MagicItem_933": GetSlumberSorcererSpellcraftScript,  # Sorcerer Portrait: get Slumber Sorcerer with permanent spellcraft
    "BG32_MagicItem_935": FirstSpellEachTurnCosts1LessScript,    "BG32_MagicItem_944": SoTRepeatGetAzeriteScript,  # Azerite Portrait: get Azerite Empowerment + one each turn
    "BG32_MagicItem_953": GetGoldgrubberAndAureateScript,    "BG32_MagicItem_957": OnBuyGetDoubloonGrifterScript,    "BG32_MagicItem_998": GetArcaneBehemothScript,
    "BG35_MagicItem_150": OnRefreshBuffTavernMinionsScript,    "BG35_MagicItem_151": SoTRepeatGetWoodlandDefilerScript,  # Desecrator Portrait (Lesser): get Woodland Defiler + one each turn
    "BG35_MagicItem_151t": SoTRepeatGetWoodlandDefilerScript,  # Desecrator Portrait (Greater): get Woodland Defiler + one each turn
    "BG35_MagicItem_154": OnPlayDemonConsumeTavernScript,    "BG35_MagicItem_155": OnHeroDamageTavernSpellBonusScript,    "BG35_MagicItem_156": GetFlamingEnforcerScript,    "BG35_MagicItem_303": GetTimewarpedSkipperScript,    "BG35_MagicItem_306": TrinketSpellcraftDestroyUndeadScript,
    "BG35_MagicItem_310": GetTimewarpedRadioStarRebornScript,    "BG35_MagicItem_430": GetBristlemaneScrapsmithScript,    "BG35_MagicItem_431t": OnDRTriggerImproveBGTempScript,
    "BG35_MagicItem_432": OnDRTriggerPlayBGRandomScript,
    "BG35_MagicItem_700": SummonCounterGetRandomBeastScript,    "BG35_MagicItem_701": SoCBuffBeastsCombatImproveOnSummonScript,    "BG35_MagicItem_713": TrustyCrowbarScript,  # Trusty Crowbar: on get pirate → buff leftmost +2/+1
    "BG35_MagicItem_714": SoCGivePirateSkyPirateDRScript,    "BG35_MagicItem_733": TrinketSpellcraftDestroyUndead2Script,
    "BG35_MagicItem_741": GetBeatboxerAndMagneticScript,    "BG35_MagicItem_742": AccordOTronPortraitScript,
    "BG35_MagicItem_743": ElectrodeAttractorScript,  # Electrode Attractor: magnetic mechs cost (2) + refresh bonus magnetic
    "BG35_MagicItem_750": OnBuyBuffMurlocTeachSpellScript,    "BG35_MagicItem_754": SoCGiveMurlocsHandATKScript,    "BG35_MagicItem_801": ExtraHeroPowerGainGoldScript,  # Teron's Training: extra hero power each turn + gain 1 gold after use
    "BG35_MagicItem_815": GetTwoMinionsPerTier123Script,    "BG35_MagicItem_816": OrbOfTheUnknownScript,  # Orb of the Unknown: random lesser trinket (approx: free refresh + 2 gold)
    "BG35_MagicItem_820": CastIceBlockGainGoldScript,    "BG35_MagicItem_821": DiscoverTier7LockScript,    "BG35_MagicItem_821t": DiscoverGoldenTier7LockScript,    "BG35_MagicItem_840": ChromaticTearLesserScript,    "BG35_MagicItem_840t": ChromaticTearScript,  # Chromatic Tear: get 2 Chromadrakes + repeat
    "BG35_MagicItem_842": EggOfEndtimesPortraitLesserScript,    "BG35_MagicItem_848t": EggOfTheEndtimesPortraitScript,  # Egg Portrait: get golden Egg, hatches next turn
    "BG35_MagicItem_849": AvengeTransferATKScript,    "BG35_MagicItem_852": OnRefreshTransferHighestToLowestScript,    "BG35_MagicItem_861": GetTemperatureShiftScript,    "BG35_MagicItem_862": OnRefreshDoubleHighestHealthScript,    "BG35_MagicItem_870": GetTimewarpedLeapfroggerScript,    "BG35_MagicItem_871": OnSummonBeastBuff44Script,    "BG35_MagicItem_872": TrinketSpellcraftBeastBuffRebornScript,
    "BG35_MagicItem_920": BubbleCrownScript,  # Bubble Crown: after 6 spells → improve tavern spell buff +2/+4
    "BG35_MagicItem_922": TideRaiserPortraitScript,  # Tide Raiser Portrait: get Tidemistress (combat spell copy TODO)
    "BG35_MagicItem_923": OnCastSpellBuffAllPermanentScript,    "BG35_MagicItem_924": GetGroundbreakerLeftBuffScript,    "BG35_MagicItem_925": CoralSpearScript,  # Coral Spear: on spellcast → cast Might of Stormwind
    "BG35_MagicItem_930": WarbandWhistleScript,  # Warband Whistle: free refresh with board copies
    "BG35_MagicItem_931": TranscribingTypewriterScript,  # Transcribing Typewriter (Lesser): extra copy of next 3 buys
    "BG35_MagicItem_931t": TranscribingTypewriterScript,  # Transcribing Typewriter (Greater): extra copy of next 3 buys

    # ── Patch 35.6.0 — New trinkets ──
    "BG35_MagicItem_755": ChillmereMosaicScript,       # Chillmere Mosaic: Spellcraft refresh with Battlecry
    "BG35_MagicItem_838": DoubleStitchNeedleScript,     # Double Stitch Needle: Spellcraft double stats + lock

    "BGDUO_MagicItem_001": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_002": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_003": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_004": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_005": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_006": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_007": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_008": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_009": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_010": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
    "BGDUO_MagicItem_010t": OutOfScopeDuosScript,  # OUT_OF_SCOPE (Duos)
}
