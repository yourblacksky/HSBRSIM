"""
Tavern Spell Script Registry

Each tavern spell has an on_play effect that triggers when cast from hand.
Script classes receive (spell, game) and return an Action.

Categories:
  - GainGold: Gain N gold
  - BuffRandomFriendly: Buff a random friendly minion
  - GetRandomMinion: Get a random minion (optionally tier-filtered)
  - DiscoverMinion: Discover a minion
  - DiscoverSpell: Discover a tavern spell
  - BuffTavern: Buff minions in Bob's tavern
  - DealDamageToRandomEnemy: Deal damage to random enemy minions
  - GainKeyword: Give a specific keyword to a random friendly (permanent)
  - BuffHand: Buff a minion in hand
  - GainArmor: Gain hero armor
  - BloodGem: Play blood gems on random friendly
  - MakeGolden: Make a random friendly minion golden
  - TransformFriendly: Transform a random friendly minion
  - StealTavern: Get a random minion from Bob's tavern
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from hsrl.core.enums import GameTag, Race
from hsrl.core.actions import (
    Action, Buff, Destroy, GainGold, GetRandomMinion, DiscoverMinion, DiscoverSpell,
    BuffTavern, DealDamageToRandomEnemy, GainKeyword, BuffRandomTavernMinion,
    PlayBloodGems, GetBloodGem, AddToHand, TargetedAction, Summon, Transform,
    ChooseOne,
)
from hsrl.core.enums import CardType as CardTypeEnum  # for local use

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.entity import BaseEntity
    from hsrl.core.player import Player


# ── Helpers ─────────────────────────────────────────────────────────────────

def _targeted_friendly_buff(player: Player, atk: int = 0, health: int = 0,
                            label: str = "") -> TargetedAction:
    """Create a TargetedAction that buffs a friendly board minion.

    During RECRUIT phase, the player/RL-agent chooses the target.
    During COMBAT phase, a random target is auto-selected.
    """
    def filter_fn():
        return [m for m in player.board if not m.dead]

    def action_factory(target):
        return Buff(target, atk=atk, health=health)

    return TargetedAction(filter_fn, action_factory, label=label)


def _targeted_friendly_keyword(player: Player, keyword_tag: GameTag,
                                label: str = "") -> TargetedAction:
    """Create a TargetedAction that grants a keyword to a friendly board minion."""
    def filter_fn():
        return [m for m in player.board if not m.dead]

    def action_factory(target):
        return GainKeyword(target, keyword_tag)

    return TargetedAction(filter_fn, action_factory, label=label)


def _random_friendly(player: Player, game: Game) -> Optional[BaseEntity]:
    """Return a random living friendly minion on the board, or None.
    (Deprecated: prefer _targeted_friendly_buff for new code.)"""
    living = [m for m in player.board if not m.dead]
    return game.rng.choice(living) if living else None


def _random_hand_minion(player: Player) -> Optional[BaseEntity]:
    """Return a random minion in hand, or None."""
    from hsrl.core.minion import Minion
    minions = [e for e in player.hand if isinstance(e, Minion)]
    return player.game.rng.choice(minions) if minions else None


def _random_tavern_minion(player: Player) -> Optional[BaseEntity]:
    """Return a random minion in Bob's tavern, or None."""
    return player.game.rng.choice(player.tavern) if player.tavern else None


# ── Script Classes ──────────────────────────────────────────────────────────

class GainGoldScript:
    """Gain N gold."""

    amount = 1

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        return GainGold(source.controller, cls.amount)


class GainGold2(GainGoldScript):
    amount = 2

class GainGold3(GainGoldScript):
    amount = 3

class GainGold4(GainGoldScript):
    amount = 4

class GainGold5(GainGoldScript):
    amount = 5


class BuffRandomFriendlyScript:
    """Buff a friendly minion (player-chosen during recruit, random during combat)."""

    atk = 0
    health = 0

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        return _targeted_friendly_buff(
            source.controller, atk=cls.atk, health=cls.health,
            label=f"Buff +{cls.atk}/+{cls.health}",
        )


class FortifyScript(BuffRandomFriendlyScript):
    """Give a minion +1/+1."""
    atk = 1
    health = 1


class FleetingVigorScript(BuffRandomFriendlyScript):
    """Give a minion +2/+2."""
    atk = 2
    health = 2


class TheApplesScript(BuffRandomFriendlyScript):
    """Give a minion +1/+2."""
    atk = 1
    health = 2


class AzeriteEmpowermentScript(BuffRandomFriendlyScript):
    """Give a minion +4/+4."""
    atk = 4
    health = 4


class SacredGiftScript(BuffRandomFriendlyScript):
    """Give a minion +5/+5."""
    atk = 5
    health = 5


class CorruptedCupcakesScript(BuffRandomFriendlyScript):
    """Give a minion +3/+2."""
    atk = 3
    health = 2


class ShiftingTideScript(BuffRandomFriendlyScript):
    """Give a minion +1/+1 twice. If it's a Naga, repeat again (4x total)."""
    atk = 1
    health = 1

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            is_naga = target.race == Race.NAGA
            loops = 4 if is_naga else 2
            return [Buff(target, atk=1, health=1) for _ in range(loops)]

        return TargetedAction(filter_fn, action_factory,
                              label="Shifting Tide — +1/+1 (x2, x4 for Naga)")


class HealthyBountyScript:
    """Give four friendly minions +4 Health."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        living = [m for m in source.controller.board if not m.dead]
        targets = game.rng.sample(living, min(4, len(living)))
        return [Buff(t, health=4) for t in targets] if targets else None


class HostileBountyScript:
    """Give four friendly minions +4 Attack."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        living = [m for m in source.controller.board if not m.dead]
        targets = game.rng.sample(living, min(4, len(living)))
        return [Buff(t, atk=4) for t in targets] if targets else None


class SelfishBountyScript:
    """Give your left-most minion +6/+6."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        return Buff(board[0], atk=6, health=6) if board else None


class SanctifyScript:
    """Give your minions with Divine Shield +6 Attack."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        ds_minions = [m for m in source.controller.board
                      if not m.dead and m.get_tag(GameTag.DIVINE_SHIELD)]
        if ds_minions:
            return [Buff(t, atk=6) for t in ds_minions]
        return None


class MenagerieTablewareScript:
    """Give your minions +3/+3. Repeat for each different friendly minion type."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        unique_types = set()
        for m in board:
            r = m.race
            if r and r not in (Race.INVALID, Race.NONE, Race.ALL):
                unique_types.add(r)
        repeat_count = max(1, len(unique_types))
        actions = []
        for _ in range(repeat_count):
            for m in board:
                actions.append(Buff(m, atk=3, health=3))
        return actions


class WaveOfGoldScript:
    """Give your minions +3/+2. Give Golden ones another +3/+2."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        actions = [Buff(m, atk=3, health=2) for m in board]
        for m in board:
            if m.is_golden:
                actions.append(Buff(m, atk=3, health=2))
        return actions


class DeepwaterClanScript:
    """Give a minion +2/+2. Give your Murlocs +2/+2."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            actions = [Buff(target, atk=2, health=2)]
            murlocs = [m for m in source.controller.board
                       if not m.dead and m != target and m.race == Race.MURLOC]
            for m in murlocs:
                actions.append(Buff(m, atk=2, health=2))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Deepwater Clan — +2/+2 (target + Murlocs)")


class QueensCommandScript:
    """Give your minions +2/+2. Give all your Naga another +2/+2."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        actions = [Buff(m, atk=2, health=2) for m in board]
        for m in board:
            if m.race == Race.NAGA:
                actions.append(Buff(m, atk=2, health=2))
        return actions


class BackToBackScript:
    """Give a minion +4/+4. Future Back to Backs give an extra +4/+4 per cast."""

    _counter_tag = GameTag.IMPROVE_COUNTER

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        extra = source.controller.get_tag(GameTag.IMPROVE_COUNTER, 0) * 4

        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            return Buff(target, atk=4 + extra, health=4 + extra)

        # Increment counter for future casts
        current = source.controller.get_tag(GameTag.IMPROVE_COUNTER, 0)
        source.controller.set_tag(GameTag.IMPROVE_COUNTER, current + 1)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Back to Back — +{4+extra}/+{4+extra}")


class EyesEarthMotherScript:
    """Choose a friendly minion from Tier 4 or below. Make it Golden."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board
                    if not m.dead and not m.is_golden
                    and m.get_tag(GameTag.TECH_LEVEL, 0) <= 4]

        def action_factory(target):
            target.set_tag(GameTag.GOLDEN, True)
            target.atk = target.atk * 2
            target.health = target.health * 2
            return None

        return TargetedAction(filter_fn, action_factory,
                              label="Eyes of Earth Mother — Make T≤4 Golden")


class MountingAvalancheScript:
    """Sell a friendly minion. Give its stats to your left-most Elemental."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            stolen_atk = target.atk
            stolen_health = target.health
            elementals = [m for m in source.controller.board
                          if not m.dead and m != target and m.race == Race.ELEMENTAL]
            actions = [Destroy(target)]
            if elementals:
                elem = elementals[0]  # left-most Elemental
                actions.append(Buff(elem, atk=stolen_atk, health=stolen_health))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Mounting Avalanche — Sell → Elemental")


class ChannelDevourerScript:
    """Sell a friendly minion. Give its stats to a random friendly minion."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            stolen_atk = target.atk
            stolen_health = target.health
            others = [m for m in source.controller.board
                      if not m.dead and m != target]
            actions = [Destroy(target)]
            if others:
                receiver = game.rng.choice(others)
                actions.append(Buff(receiver, atk=stolen_atk, health=stolen_health))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Channel the Devourer — Sell → random")


class FriendlyBountyScript:
    """Get a random minion of your most common type."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        race_counts: dict = {}
        for m in board:
            r = m.race
            if r and r not in (Race.INVALID, Race.NONE, Race.ALL):
                race_counts[r] = race_counts.get(r, 0) + 1
        if not race_counts:
            return GetRandomMinion(source.controller)
        most_common = max(race_counts, key=race_counts.get)
        return GetRandomMinion(source.controller, race=most_common)


class EonarsFavorScript:
    """Choose a minion. Give minions of its type in the Tavern +3/+3 this game."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            chosen_race = target.race
            if not chosen_race or chosen_race in (Race.INVALID, Race.NONE, Race.ALL):
                return None
            return BuffTavern(source.controller, atk=3, health=3,
                              race_filter=chosen_race)

        return TargetedAction(filter_fn, action_factory,
                              label="Eonar's Favor — Buff Tavern by type")


class GetRandomMinionScript:
    """Get a random minion matching tier/race filters."""

    min_tier = None
    max_tier = None
    race = None

    use_discover = False  # Set True for DiscoverMinion instead of random

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        if cls.use_discover:
            from hsrl.core.actions import DiscoverMinion
            return DiscoverMinion(
                source.controller,
                min_tier=cls.min_tier,
                max_tier=cls.max_tier,
                race=cls.race,
            )
        return GetRandomMinion(
            source.controller,
            min_tier=cls.min_tier,
            max_tier=cls.max_tier,
            race=cls.race,
        )


class RecruitATraineeScript(GetRandomMinionScript):
    """Get a random Tier 1 minion."""
    max_tier = 1


class HastyExcavationScript(GetRandomMinionScript):
    """Get a random Tier 2 minion."""
    max_tier = 2


class ANewSproutScript(GetRandomMinionScript):
    """Discover a Tier 1 minion (zhCN: 发现一个等级1的随从)."""
    max_tier = 1
    use_discover = True


class PortalInAFountainScript(GetRandomMinionScript):
    """Get a random Tier 3 minion."""
    max_tier = 3


class PortalInACrystalScript(GetRandomMinionScript):
    """Get a random Tier 4 minion."""
    max_tier = 4


class UpperHandScript(GetRandomMinionScript):
    """Get a random minion from a tier higher than your tavern."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        tier = source.controller.tavern_tier
        return GetRandomMinion(source.controller, min_tier=tier + 1)


class HiredHeadhunterScript(GetRandomMinionScript):
    """Discover a Battlecry minion (zhCN: 发现一张战吼随从牌)."""
    pass  # No tier filter
    use_discover = True


class SearchThroughTimeScript(GetRandomMinionScript):
    """Discover a minion of your current tier, locked in hand 1 turn."""
    use_discover = True

    @classmethod
    def on_play(cls, source, game):
        tier = source.controller.tavern_tier
        from hsrl.core.actions import DiscoverMinion
        return DiscoverMinion(
            source.controller,
            min_tier=tier,
            max_tier=tier,
        )


class DiscoverMinionScript:
    """Discover a minion."""

    max_tier = None
    race = None

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        return DiscoverMinion(
            source.controller,
            max_tier=cls.max_tier,
            race=cls.race,
        )


class ChefsChoiceScript(DiscoverMinionScript):
    """Discover a minion of your tavern tier."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        tier = source.controller.tavern_tier
        return DiscoverMinion(source.controller, max_tier=tier)


class HallowedRitualScript(DiscoverMinionScript):
    """Discover a Tier 7 minion."""
    max_tier = 7


class TombTurningScript(DiscoverMinionScript):
    """Discover an Undead."""
    race = Race.UNDEAD


class PerfectVisionScript(DiscoverMinionScript):
    """Discover a minion."""
    pass


class CloningConchScript(DiscoverMinionScript):
    """Discover a copy of a friendly minion (player-chosen target during recruit)."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]
        def action_factory(target):
            race_val = target.get_tag(GameTag.RACE, Race.NONE)
            if race_val and race_val != Race.NONE and race_val != Race.INVALID:
                return DiscoverMinion(source.controller, race=race_val)
            return None
        return TargetedAction(filter_fn, action_factory,
                              label="Discover copy of minion's race")
        return DiscoverMinion(source.controller)


class ContractedCorpseScript(DiscoverMinionScript):
    """Discover an Undead minion."""
    race = Race.UNDEAD


class DiscoverSpellScript:
    """Discover a tavern spell."""

    max_tier = None

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        return DiscoverSpell(source.controller, max_tier=cls.max_tier)


class LeafThroughPagesScript(DiscoverSpellScript):
    """Discover a Tier 1 or 2 spell."""
    max_tier = 2


class PlanarTelescopeScript(DiscoverSpellScript):
    """Discover a Tier 3 or 4 spell."""
    max_tier = 4


class MisplacedTeaSetScript(DiscoverSpellScript):
    """Discover a spell."""
    pass


class KnockoffWisdomballScript(DiscoverSpellScript):
    """Discover 2 spells."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        return [DiscoverSpell(source.controller), DiscoverSpell(source.controller)]


class ArcaneAbsorptionScript(DiscoverSpellScript):
    """Discover a spell."""
    pass


class LostStaffOfHamuulScript(DiscoverSpellScript):
    """Discover a spell."""
    pass


class BuffTavernScript:
    """Buff minions in Bob's tavern."""

    atk = 0
    health = 0

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        return BuffTavern(source.controller, atk=cls.atk, health=cls.health)


class ShinyRingScript(BuffTavernScript):
    """Give tavern minions +1/+1."""
    atk = 1
    health = 1


class MightOfStormwindScript(BuffTavernScript):
    """Give tavern minions +2/+1."""
    atk = 2
    health = 1


class ConflagrationScript(BuffTavernScript):
    """Give tavern minions +2/+0."""
    atk = 2
    health = 0


class EasterlyWindsScript(BuffTavernScript):
    """Give tavern minions +1/+2."""
    atk = 1
    health = 2


class SaloonsFinestScript(BuffTavernScript):
    """Give tavern minions +2/+2."""
    atk = 2
    health = 2


class TimeManagementScript(BuffTavernScript):
    """Give tavern minions +1/+1."""
    atk = 1
    health = 1


class DealDamageToRandomEnemyScript:
    """Deal N damage to random enemy minion."""

    amount = 1
    count = 1

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        # DealDamageToRandomEnemy damages random enemy minions of the given player
        return DealDamageToRandomEnemy(source.controller, cls.amount, cls.count)


class PointyArrowScript(DealDamageToRandomEnemyScript):
    """Deal 3 damage to a random enemy minion."""
    amount = 3


class GainKeywordScript:
    """Give a specific keyword to a friendly minion (player-chosen during recruit)."""

    keyword = None

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        if cls.keyword is None:
            return None
        return _targeted_friendly_keyword(source.controller, cls.keyword,
                                          label=f"Grant {cls.keyword}")


class BoonOfBeetlesScript(GainKeywordScript):
    """Give a friendly minion Taunt."""
    keyword = GameTag.TAUNT


class TrickyTrousersScript(GainKeywordScript):
    """Give a friendly minion a random keyword."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]
        def action_factory(target):
            keywords = [GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.WINDFURY, GameTag.REBORN]
            return GainKeyword(target, game.rng.choice(keywords))
        return TargetedAction(filter_fn, action_factory, label="Grant random keyword")


class DefendersRitesScript(GainKeywordScript):
    """Give a friendly minion Taunt and Divine Shield."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]
        def action_factory(target):
            return [GainKeyword(target, GameTag.TAUNT),
                    GainKeyword(target, GameTag.DIVINE_SHIELD)]
        return TargetedAction(filter_fn, action_factory,
                              label="Grant Taunt + Divine Shield")


class NaturalBlessingScript(GainKeywordScript):
    """Give a friendly minion random keyword from {Taunt, DS, Reborn}."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]
        def action_factory(target):
            keywords = [GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.REBORN]
            return GainKeyword(target, game.rng.choice(keywords))
        return TargetedAction(filter_fn, action_factory,
                              label="Grant random blessing")


class BuffHandScript:
    """Buff a random minion in hand."""

    atk = 0
    health = 0

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        target = _random_hand_minion(source.controller)
        if target:
            return Buff(target, atk=cls.atk, health=cls.health)
        # Fallback: buff a random tavern minion if hand is empty
        return BuffRandomTavernMinion(source.controller, atk=cls.atk, health=cls.health)


class TavernDishBananaScript(BuffHandScript):
    """Give a minion in hand +1/+1."""
    atk = 1
    health = 1


class BloodGemScript:
    """Play blood gems on a friendly minion (player-chosen during recruit)."""

    count = 1

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]
        def action_factory(target):
            return PlayBloodGems(target, count=cls.count)
        return TargetedAction(filter_fn, action_factory,
                              label=f"Play {cls.count} Blood Gem(s)")


class GemConfiscationScript(BloodGemScript):
    """Play 2 Blood Gems on a friendly minion."""
    count = 2


class MakeGoldenScript:
    """Make a friendly minion Golden (player-chosen during recruit)."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board
                    if not m.dead and not m.is_golden]
        def action_factory(target):
            target.set_tag(GameTag.GOLDEN, True)
            target.atk = target.atk * 2
            target.health = target.health * 2
            return None
        return TargetedAction(filter_fn, action_factory,
                              label="Make minion Golden")


class TransformFriendlyScript:
    """Transform a friendly minion (player-chosen during recruit)."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        from hsrl.core.actions import Transform

        def filter_fn():
            return [m for m in source.controller.board if not m.dead]
        def action_factory(target):
            tier = target.tech_level
            pool = game.minion_pool._pools.get(tier, [])
            if not pool:
                return None
            new_id = game.rng.choice(list(set(pool)))
            return Transform(target, new_id)
        return TargetedAction(filter_fn, action_factory,
                              label="Transform minion")


class GainArmorScript:
    """Gain hero armor."""

    amount = 0

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        player = source.controller
        player.set_tag(GameTag.ARMOR, player.armor + cls.amount)
        return None


class ArmorStashScript(GainArmorScript):
    """Gain 5 Armor."""
    amount = 5


class StealTavernScript:
    """Get a random minion from Bob's tavern."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        minion = _random_tavern_minion(source.controller)
        if minion:
            source.controller.tavern.remove(minion)
            return AddToHand(source.controller, minion.data.id)
        return None


# ── Spell Script Registry ───────────────────────────────────────────────────
# Maps card_id → script_class with on_play(source, game) → Action

class DeepBluesScript:
    """
    Natural language: Give a minion +2/+2 until next turn. Improve your future
    Deep Blues.

    Formal spec:
      1. Get IMPROVE_COUNTER from player; base bonus = 2 (from XML data)
      2. Increment counter for future uses
      3. Apply targeted buff: + (2 + counter) ATK, + (2 + counter) HEALTH, temporary=True
      4. Temporary buffs are cleared at end of combat / end of recruit phase

    Test: first use gives +2/+2 temp; second gives +3/+3 temp.
    """
    BASE_ATK = 2
    BASE_HEALTH = 2

    @staticmethod
    def on_play(source, game):
        player = source.controller
        counter = player.get_tag(GameTag.IMPROVE_COUNTER, 0)
        player.set_tag(GameTag.IMPROVE_COUNTER, counter + 1)
        bonus_atk = DeepBluesScript.BASE_ATK + counter
        bonus_health = DeepBluesScript.BASE_HEALTH + counter

        def filter_fn():
            return [m for m in player.board if not m.dead]

        def action_factory(target):
            return Buff(target, atk=bonus_atk, health=bonus_health, temporary=True)

        return TargetedAction(filter_fn, action_factory,
                            label=f"Deep Blues (+{bonus_atk}/+{bonus_health})")


class EscapeEruptionScript:
    """
    Natural language: Choose One - Give your minions +4 Attack; or +4 Health.

    Formal spec:
      1. Present ChooseOne with two options:
         a. "+4 Attack" → Buff each friendly minion +4 ATK
         b. "+4 Health" → Buff each friendly minion +4 Health
      2. Apply the chosen buff to all friendly minions on the board.

    Test: verify choosing Attack gives all +4 ATK; choosing Health gives all +4 Health.
    """
    @staticmethod
    def on_play(source, game):
        player = source.controller
        board = [m for m in player.board if not m.dead]
        if not board:
            return None

        atk_buffs = [Buff(m, atk=4, health=0) for m in board]
        hp_buffs = [Buff(m, atk=0, health=4) for m in board]

        return ChooseOne([
            ("+4 Attack to all", atk_buffs),
            ("+4 Health to all", hp_buffs),
        ])


class _NotYetImplementedScript:
    """Placeholder for spells that require new engine mechanics.

    Returns None (no effect) rather than prompting for a target and doing nothing.
    See card text for intended behavior.
    """

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        return None


class RobustEvolutionScript:
    """Transform a friendly minion into one of a higher Tier. It keeps its stats.

    Formal spec:
      1. TargetedAction: player selects a friendly board minion
      2. Find all pool minion IDs with tier > target's tier
      3. Randomly pick one, Transform(target, new_id)
    Test: transform a T1 minion into random T2+ minion, stats preserved.
    """

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            from hsrl.core.card_db import CARDS
            target_tier = target.tech_level
            candidates = []
            for cid, data in CARDS._cards.items():
                if (data.cardtype == CardTypeEnum.MINION
                        and not cid.startswith("EXAMPLE_")
                        and not cid.startswith("BGDUO")
                        and data.tech_level > target_tier):
                    candidates.append(cid)
            if not candidates:
                return None
            new_id = game.rng.choice(candidates)
            return Transform(target, new_id)

        return TargetedAction(filter_fn, action_factory,
                              label="Robust Evolution — transform to higher tier")


# ── Tier 3-7 spell scripts ─────────────────────────────────────────────────

class TemperatureShiftScript:
    """Get a Fire Baller (BG31_816) and a Snow Baller (BG31_818)."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        actions = []
        for token_id in ("BG31_816", "BG31_818"):
            if len(source.controller.hand) < 10:
                actions.append(AddToHand(source.controller, token_id))
        return actions if actions else None


class SpitescaleSpecialScript:
    """Get 3 random Spellcraft spells of different types."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        from hsrl.core.card_db import CARDS
        spellcraft_spells = [
            cid for cid, data in CARDS._cards.items()
            if (data.cardtype == CardTypeEnum.SPELL
                and not cid.startswith("EXAMPLE_")
                and data.tags.get(GameTag.SPELLCRAFT))
        ]
        if not spellcraft_spells:
            return None
        chosen = game.rng.sample(spellcraft_spells,
                                 min(3, len(spellcraft_spells)))
        actions = []
        for cid in chosen:
            if len(source.controller.hand) < 10:
                actions.append(AddToHand(source.controller, cid))
        return actions if actions else None


class BroodOfNozdormuScript:
    """Start of Combat: Double your left-most minion's stats."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        leftmost = board[0]
        return Buff(leftmost, atk=leftmost.atk, health=leftmost.max_health)


class SharingIsCaringScript:
    """Start of Combat: Summon a copy of your left-most minion."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        if len(board) >= 7:
            return None
        leftmost = board[0]
        copy_minion = game.create_minion(leftmost.data.id)
        if copy_minion is None:
            return None
        # Copy stats and keywords
        copy_minion.set_tag(GameTag.BASE_ATK, leftmost.atk)
        copy_minion.set_tag(GameTag.BASE_HEALTH, leftmost.max_health)
        copy_minion.set_tag(GameTag.HEALTH, leftmost.health)
        if leftmost.is_golden:
            copy_minion.set_tag(GameTag.GOLDEN, True)
        return Summon(source.controller, copy_minion)


class ButcheringScript:
    """Destroy a friendly Undead. Give your Undead Attack equal to its Attack.

    Uses TargetedAction: player selects which Undead to destroy during recruit.
    """

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        def filter_fn():
            return [m for m in source.controller.board
                    if not m.dead and m.race == Race.UNDEAD]

        def action_factory(target):
            atk_val = target.atk
            actions = [Destroy(target)]
            for m in source.controller.board:
                if not m.dead and m != target and m.race == Race.UNDEAD:
                    actions.append(Buff(m, atk=atk_val))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Destroy Undead → give ATK to other Undead")


SPELL_SCRIPT_REGISTRY: dict = {
    # ── Tier 1 ──
    "BG28_503": FortifyScript,              # Fortify: +1/+1
    "BG28_504": RecruitATraineeScript,      # Recruit a Trainee: Get T1
    "BG28_512": StealTavernScript,          # Enchanted Lasso: Steal tavern minion
    "BG28_810": GainGoldScript,             # Tavern Coin: +1 Gold
    "BG28_897": TavernDishBananaScript,     # Tavern Dish Banana: +1/+1 hand
    "BG28_966": TheApplesScript,            # Them Apples: +1/+2
    "BG33_101": ANewSproutScript,           # A New Sprout: Get T1/T2
    "EBG_Spell_014": PointyArrowScript,     # Pointy Arrow: 3 dmg random enemy

    # ── Tier 2 ──
    "BG28_518": ChefsChoiceScript,          # Chef's Choice: Discover
    "BG28_571": HastyExcavationScript,      # Hasty Excavation: Get T2
    "BG28_805": GainGold4,                  # Strike Oil: +4 Gold
    "BG28_827": LeafThroughPagesScript,     # Leaf Through Pages: Discover T1/T2 spell
    "BG34_330": SearchThroughTimeScript,    # Search Through Time: Get random
    "BG35_951": MightOfStormwindScript,     # Might of Stormwind: Tavern +2/+1

    # ── Tier 3 ──
    "BG28_168": ShinyRingScript,            # Shiny Ring: Tavern +1/+1
    "BG28_519": FleetingVigorScript,        # Fleeting Vigor: +2/+2
    "BG28_520": TrickyTrousersScript,       # Tricky Trousers: Random keyword
    "BG28_521": PlanarTelescopeScript,      # Planar Telescope: Discover T3/T4 spell
    "BG28_800": GainGold2,                  # Careful Investment: +2 Gold
    "BG28_884": GainGold3,                  # Overconfidence: +3 Gold
    "BG28_886": GainGold2,                  # Staff of Enrichment: +2 Gold
    "BG30_804": RobustEvolutionScript,      # Transform → higher tier, keep stats
    "BG31_243": PortalInAFountainScript,    # Portal in a Fountain: Get T3
    "BG31_881": TimeManagementScript,       # Time Management: Tavern +1/+1
    "BG33_811": HealthyBountyScript,        # Healthy Bounty: +4 Health to 4 friendlies
    "BG33_812": HostileBountyScript,        # Hostile Bounty: +4 Attack to 4 friendlies
    "BG33_813": SelfishBountyScript,        # Selfish Bounty: left-most +6/+6
    "BG33_814": FriendlyBountyScript,       # Friendly Bounty: most common type
    "BG33_815": GainGold2,                  # Wealthy Bounty: Gain 2 Gold
    "BG33_899": MountingAvalancheScript,    # Mounting Avalanche: Sell→leftmost Elemental

    # ── Tier 4 ──
    "BG28_601": CloningConchScript,         # Cloning Conch: Discover copy
    "BG28_603": BoonOfBeetlesScript,        # Boon of Beetles: Taunt
    "BG28_606": SpitescaleSpecialScript,    # Get 3 random Spellcraft spells
    "BG28_698": GemConfiscationScript,      # Gem Confiscation: 2 Blood Gems
    "BG28_825": DefendersRitesScript,       # Defender's Rites: Taunt+DS
    "BG28_845": NaturalBlessingScript,      # Natural Blessing: Random keyword
    "BG28_888": MisplacedTeaSetScript,      # Misplaced Tea Set: Discover spell
    "BG31_819": TemperatureShiftScript,     # Get Fire Baller + Snow Baller
    "BG32_815": ShiftingTideScript,         # Shifting Tide: +1/+1 x2, x4 for Naga
    "BG34_444": EasterlyWindsScript,        # Easterly Winds: Tavern +1/+2
    "BG34_888": TombTurningScript,          # Tomb Turning: Discover Undead
    "BG35_149": DeepwaterClanScript,        # Deepwater Clan: +2/+2 target + Murlocs
    "BG35_910": ConflagrationScript,        # Conflagration: Tavern +2/+0
    "BG35_911": ArcaneAbsorptionScript,     # Arcane Absorption: Discover spell
    "BG35_912": EonarsFavorScript,          # Eonar's Favor: Choose→buff tavern by type
    "BG35_952": BackToBackScript,           # Back to Back: +4/+4 scaling

    # ── Tier 5 ──
    "BG28_500": ArmorStashScript,           # Armor Stash: +5 Armor
    "BG28_573": UpperHandScript,            # Upper Hand: Get higher tier
    "BG28_604": ButcheringScript,           # Destroy Undead → give Undead ATK
    "BG28_607": CorruptedCupcakesScript,    # Corrupted Cupcakes: +3/+2
    "BG28_830": MakeGoldenScript,           # Golden Touch: Make golden
    "BG28_849": SaloonsFinestScript,        # Saloon's Finest: Tavern +2/+2
    "BG28_882": ContractedCorpseScript,     # Contracted Corpse: Discover Undead
    "BG31_242": GainGold5,                  # Bargain Bundle: +5 Gold
    "BG31_244": PortalInACrystalScript,     # Portal in a Crystal: Get T4
    "BG33_817": SanctifyScript,             # Sanctify: +6 atk to DS minions
    "BG34_889": BroodOfNozdormuScript,      # SoC: Double left-most minion's stats
    "BG34_990": WaveOfGoldScript,           # Wave of Gold: +3/+2, golden x2
    "BG35_922": QueensCommandScript,        # Queen's Command: +2/+2, Naga x2
    "BG28_GIL_836": HiredHeadhunterScript,  # Hired Headhunter: Get random
    "EBG_Spell_032": ChannelDevourerScript, # Channel Devourer: Sell→random friendly
    "EBG_Spell_037": TransformFriendlyScript,    # Unmasked Identity: Transform

    # ── Tier 6 ──
    "BG28_169": AzeriteEmpowermentScript,   # Azerite Empowerment: +4/+4
    "BG28_838": PerfectVisionScript,        # Perfect Vision: Discover
    "BG30_802": KnockoffWisdomballScript,   # Knockoff Wisdomball: Discover 2 spells
    "EBG_Spell_017": EyesEarthMotherScript, # Eyes of Earth Mother: Golden T≤4
    "EBG_Spell_038": LostStaffOfHamuulScript,    # Lost Staff of Hamuul: Discover spell

    # ── Tier 7 ──
    "BG28_507": SacredGiftScript,           # Sacred Gift: +5/+5
    "BG31_889": SharingIsCaringScript,      # SoC: Summon copy of left-most minion
    "BG31_896": HallowedRitualScript,       # Hallowed Ritual: Discover T7
    "BG34_272": MenagerieTablewareScript,   # Menagerie Tableware: +3/+3 per type

    # ── Token spells ──
    "BG30_117t": EscapeEruptionScript,      # Escape Eruption: Choose One +4 ATK or +4 Health
    "BG35_Anomaly_001t": _NotYetImplementedScript,  # Fly the Flag: choose minion → add copies to pool
    "BG26_502t": DeepBluesScript,           # Deep Blues: +2/+2 temp, self-improving

    # ── Patch 35.6.0 — New ──
    "BG34_689": _NotYetImplementedScript,   # Blood Gem Barrage: after refresh → tavern blood gems
}
