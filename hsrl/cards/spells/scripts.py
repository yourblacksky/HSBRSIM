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
    Action, Buff, GainGold, GetRandomMinion, DiscoverMinion, DiscoverSpell,
    BuffTavern, DealDamageToRandomEnemy, GainKeyword, BuffRandomTavernMinion,
    PlayBloodGems, GetBloodGem, AddToHand,
)

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.entity import BaseEntity
    from hsrl.core.player import Player


# ── Helper ──────────────────────────────────────────────────────────────────

def _random_friendly(player: Player, game: Game) -> Optional[BaseEntity]:
    """Return a random living friendly minion on the board, or None."""
    living = [m for m in player.board if not m.dead]
    return random.choice(living) if living else None


def _random_hand_minion(player: Player) -> Optional[BaseEntity]:
    """Return a random minion in hand, or None."""
    from hsrl.core.minion import Minion
    minions = [e for e in player.hand if isinstance(e, Minion)]
    return random.choice(minions) if minions else None


def _random_tavern_minion(player: Player) -> Optional[BaseEntity]:
    """Return a random minion in Bob's tavern, or None."""
    return random.choice(player.tavern) if player.tavern else None


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
    """Buff a random friendly minion."""

    atk = 0
    health = 0

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            return Buff(target, atk=cls.atk, health=cls.health)
        return None


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


class GetRandomMinionScript:
    """Get a random minion matching tier/race filters."""

    min_tier = None
    max_tier = None
    race = None

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
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
    """Get a random Tier 1 or 2 minion."""
    max_tier = 2


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
    """Get a random minion."""
    pass  # No tier filter


class SearchThroughTimeScript(GetRandomMinionScript):
    """Get a random minion."""
    pass


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


class PerfectVisionScript(DiscoverMinionScript):
    """Discover a minion."""
    pass


class CloningConchScript(DiscoverMinionScript):
    """Discover a copy of a friendly minion."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            race_val = target.get_tag(GameTag.RACE, Race.NONE)
            if race_val and race_val != Race.NONE and race_val != Race.INVALID:
                return DiscoverMinion(source.controller, race=race_val)
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
    """Give a specific keyword to a random friendly minion (permanent)."""

    keyword = None

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target and cls.keyword:
            return GainKeyword(target, cls.keyword)
        return None


class BoonOfBeetlesScript(GainKeywordScript):
    """Give a random friendly minion Taunt."""
    keyword = GameTag.TAUNT


class TrickyTrousersScript(GainKeywordScript):
    """Give a random friendly minion a random keyword."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            keywords = [GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.WINDFURY, GameTag.REBORN]
            return GainKeyword(target, random.choice(keywords))
        return None


class DefendersRitesScript(GainKeywordScript):
    """Give a random friendly minion Taunt and Divine Shield."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            return [
                GainKeyword(target, GameTag.TAUNT),
                GainKeyword(target, GameTag.DIVINE_SHIELD),
            ]
        return None


class NaturalBlessingScript(GainKeywordScript):
    """Give a random friendly minion random keyword from {Taunt, DS, Reborn}."""
    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            keywords = [GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.REBORN]
            return GainKeyword(target, random.choice(keywords))
        return None


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
    """Play blood gems on friendly minions."""

    count = 1

    @classmethod
    def on_play(cls, source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            return PlayBloodGems(target, count=cls.count)
        return GetBloodGem(source.controller, count=cls.count)


class GemConfiscationScript(BloodGemScript):
    """Play 2 Blood Gems on a random friendly minion."""
    count = 2


class MakeGoldenScript:
    """Make a random friendly minion Golden."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target and not target.golden:
            target.set_tag(GameTag.GOLDEN, True)
            target.atk = target.atk * 2
            target.health = target.health * 2
        return None


class TransformFriendlyScript:
    """Transform a random friendly minion."""

    @staticmethod
    def on_play(source: BaseEntity, game: Game) -> Action:
        target = _random_friendly(source.controller, game)
        if target:
            from hsrl.core.actions import Transform
            return Transform(target)
        return None


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
    "BG30_804": BuffRandomFriendlyScript,   # Robust Evolution: Buff
    "BG31_243": PortalInAFountainScript,    # Portal in a Fountain: Get T3
    "BG31_881": TimeManagementScript,       # Time Management: Tavern +1/+1
    "BG33_811": BuffRandomFriendlyScript,   # Healthy Bounty: Buff
    "BG33_812": BuffRandomFriendlyScript,   # Hostile Bounty: Buff
    "BG33_813": BuffRandomFriendlyScript,   # Selfish Bounty: Buff
    "BG33_814": BuffRandomFriendlyScript,   # Friendly Bounty: Buff
    "BG33_815": BuffRandomFriendlyScript,   # Wealthy Bounty: Buff
    "BG33_899": BuffRandomFriendlyScript,   # Mounting Avalanche: Buff

    # ── Tier 4 ──
    "BG28_601": CloningConchScript,         # Cloning Conch: Discover copy
    "BG28_603": BoonOfBeetlesScript,        # Boon of Beetles: Taunt
    "BG28_606": BuffRandomFriendlyScript,   # Spitescale Special: Naga buff
    "BG28_698": GemConfiscationScript,      # Gem Confiscation: 2 Blood Gems
    "BG28_825": DefendersRitesScript,       # Defender's Rites: Taunt+DS
    "BG28_845": NaturalBlessingScript,      # Natural Blessing: Random keyword
    "BG28_888": MisplacedTeaSetScript,      # Misplaced Tea Set: Discover spell
    "BG31_819": BuffRandomFriendlyScript,   # Temperature Shift: Buff
    "BG32_815": BuffRandomFriendlyScript,   # Shifting Tide: Naga spell
    "BG34_444": EasterlyWindsScript,        # Easterly Winds: Tavern +1/+2
    "BG34_888": BuffRandomFriendlyScript,   # Tomb Turning: Buff
    "BG35_149": BuffRandomFriendlyScript,   # Deepwater Clan: Naga buff
    "BG35_910": ConflagrationScript,        # Conflagration: Tavern +2/+0
    "BG35_911": ArcaneAbsorptionScript,     # Arcane Absorption: Discover spell
    "BG35_912": BuffRandomFriendlyScript,   # Eonar's Favor: Buff
    "BG35_952": BuffRandomFriendlyScript,   # Back to Back: Buff

    # ── Tier 5 ──
    "BG28_500": ArmorStashScript,           # Armor Stash: +5 Armor
    "BG28_573": UpperHandScript,            # Upper Hand: Get higher tier
    "BG28_604": TransformFriendlyScript,    # Butchering: Transform
    "BG28_607": CorruptedCupcakesScript,    # Corrupted Cupcakes: +3/+2
    "BG28_830": MakeGoldenScript,           # Golden Touch: Make golden
    "BG28_849": SaloonsFinestScript,        # Saloon's Finest: Tavern +2/+2
    "BG28_882": ContractedCorpseScript,     # Contracted Corpse: Discover Undead
    "BG31_242": GainGold5,                  # Bargain Bundle: +5 Gold
    "BG31_244": PortalInACrystalScript,     # Portal in a Crystal: Get T4
    "BG33_817": BuffRandomFriendlyScript,   # Sanctify: Buff
    "BG34_889": BuffRandomFriendlyScript,   # Brood of Nozdormu: Buff
    "BG34_990": BuffRandomFriendlyScript,   # Wave of Gold: Buff
    "BG35_922": BuffRandomFriendlyScript,   # Queen's Command: Naga buff
    "BG28_GIL_836": HiredHeadhunterScript,  # Hired Headhunter: Get random
    "EBG_Spell_032": BuffRandomFriendlyScript,   # Channel the Devourer
    "EBG_Spell_037": TransformFriendlyScript,    # Unmasked Identity: Transform

    # ── Tier 6 ──
    "BG28_169": AzeriteEmpowermentScript,   # Azerite Empowerment: +4/+4
    "BG28_838": PerfectVisionScript,        # Perfect Vision: Discover
    "BG30_802": KnockoffWisdomballScript,   # Knockoff Wisdomball: Discover 2 spells
    "EBG_Spell_017": BuffRandomFriendlyScript,   # Eyes of the Earth Mother
    "EBG_Spell_038": LostStaffOfHamuulScript,    # Lost Staff of Hamuul: Discover spell

    # ── Tier 7 ──
    "BG28_507": SacredGiftScript,           # Sacred Gift: +5/+5
    "BG31_889": BuffRandomFriendlyScript,   # Sharing is Caring: Buff
    "BG31_896": BuffRandomFriendlyScript,   # Hallowed Ritual: Buff
    "BG34_272": BuffRandomFriendlyScript,   # Menagerie Tableware: Buff
}
