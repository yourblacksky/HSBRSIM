"""
HSRL Hero Power Scripts

Hero powers follow the same script pattern as minion effects:
  @staticmethod
  def hero_power(source: Player, game: Game) -> Optional[Action]:

The source parameter is the Player entity (hero).
"""

import random

from hsrl.core.actions import (
    Action,
    AddToHand,
    Buff,
    BuffTavern,
    DealDamageToHero,
    DealDamageToRandomEnemy,
    DiscoverMinion,
    GainDeathrattle,
    GainGold,
    GainKeyword,
    GetRandomMinion,
    GiveKeyword,
    Hit,
    PlayBloodGems,
)
from hsrl.core.enums import GameTag, Race, Zone


# ═══════════════════════════════════════════════════════════════════════════
# Example Hero Power Scripts
# ═══════════════════════════════════════════════════════════════════════════

class ExampleHeroPowerBuff:
    """Hero Power (0): Give a random friendly minion +1/+1."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=1, health=1)


class ExampleHeroPowerGold:
    """Hero Power (2): Gain 2 Gold."""

    @staticmethod
    def hero_power(source, game):
        return GainGold(source, 2)


class ExampleHeroPowerMulti:
    """Hero Power (1): Give friendly Beasts +2 Attack."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        targets = [m for m in board if m.race in (Race.BEAST, Race.ALL)]
        if not targets:
            return None
        actions = [Buff(m, atk=2, health=0) for m in targets]
        return actions


class ExamplePermanentAura:
    """Passive Hero Power: Your Beasts have +1/+1.

    Formal spec:
      - Cost: 0 (passive — on_summon applies the aura at game start)
      - ApplyGlobalAura with atk=1, health=1, race_filter=Race.BEAST
      - Aura persists for entire game, affects current + future Beasts
      - hero_power returns None (no manual activation)

    Test: summon a Beast, verify +1/+1 from aura.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import ApplyGlobalAura
        ApplyGlobalAura(source, atk=1, health=1, race_filter=Race.BEAST).do(source, game)
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — BG20_HERO_103p: Bloodbound (Death Speaker Blackthorn)
# ═══════════════════════════════════════════════════════════════════════════

class BloodboundScript:
    """
    Natural language: Hero Power (1): Give a random friendly minion +1/+1.

    Status: ACTIVE

    Formal spec:
      - Cost: 1 gold
      - Pick random non-dead friendly minion, Buff +1/+1
      - Return None if board is empty

    Test: board with 2 minions, use hero power, verify one gets +1/+1.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=1, health=1)


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — BG20_HERO_100p: Glory of Combat (Rokara)
# ═══════════════════════════════════════════════════════════════════════════

class GloryOfCombatScript:
    """
    Natural language: Passive Hero Power. After a friendly minion kills
    an enemy, give it +1 Attack permanently.

    Status: ACTIVE

    Formal spec:
      - Passive: no cost, no manual activation
      - on game start, register DEATH listener
      - On DEATH event, check KILLER tag on dead minion in combat death log
      - If killer is friendly, Buff +1 ATK

    Test: friendly minion kills enemy during combat, verify +1 ATK.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.enums import GameTag

        class _GloryOfCombatListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                # Check combat death log for recently killed enemies
                for dead_m in game_ref._combat_death_log:
                    killer_id = dead_m.get_tag(GameTag.KILLER, 0)
                    if not killer_id:
                        continue
                    # Check if the killer is on this hero's board
                    for m in self.hero.get_board_minions():
                        if m.entity_id == killer_id and not m.dead:
                            Buff(m, atk=1, health=0).do(m, game_ref)
                            # Clear KILLER to avoid double-triggering
                            dead_m.set_tag(GameTag.KILLER, 0)
                            return

        listener = EventListener(
            event_name="DEATH",
            action=_GloryOfCombatListener(source),
        )
        game.register_listener(source, listener)
        return None

    @staticmethod
    def hero_power(source, game):
        """Passive hero power — no manual activation."""
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — BG20_HERO_101p: See the Light (Xyrella)
# ═══════════════════════════════════════════════════════════════════════════

class SeeTheLightScript:
    """
    Natural language: Hero Power (2): Give a random friendly minion +2/+2.

    Status: ACTIVE

    Test: board with minions, use hero power, verify one gets +2/+2.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=2, health=2)


# ═══════════════════════════════════════════════════════════════════════════
# BG21_HERO_000p: Conviction (Cariel Roame)
# ═══════════════════════════════════════════════════════════════════════════

class ConvictionScript:
    """Hero Power (1): Give a random friendly minion +1/+1."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=1, health=1)


# ═══════════════════════════════════════════════════════════════════════════
# BG21_HERO_010p: I Spy (Scabbs Cutterbutter) — cost=2
# ═══════════════════════════════════════════════════════════════════════════

class ISpyScript:
    """Hero Power (2): Discover a minion from the Tavern Tier below yours."""

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import DiscoverMinion
        tier = max(1, source.tavern_tier - 1)
        return DiscoverMinion(source, max_tier=tier)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_001: Sharpen Blades (Edwin VanCleef) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class SharpenBladesScript:
    """Hero Power (1): Give a minion +1/+1 for each minion you've bought this turn.

    Note: Currently uses default +1/+1 since MINIONS_BOUGHT_THIS_TURN tracking
    is not yet implemented. Full scaling will be added when purchase tracking is available.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        # Phase II: use actual GOLD_SPENT_THIS_TURN / 3 instead of 1
        bought = max(1, source.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0) // 3)
        return Buff(target, atk=bought, health=bought)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_010: Boon of Light (George the Fallen) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class BoonOfLightScript:
    """Hero Power (1): Give a random friendly minion Divine Shield."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        candidates = [m for m in board if not m.divine_shield]
        if not candidates:
            return None
        target = random.choice(candidates)
        return GainKeyword(target, GameTag.DIVINE_SHIELD)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_015: Tinker (Millificent Manastorm) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class TinkerScript:
    """Hero Power (1): Give a random friendly Mech +1/+1."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        targets = [m for m in board if m.race in (Race.MECH, Race.ALL)]
        if not targets:
            return None
        target = random.choice(targets)
        return Buff(target, atk=1, health=1)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_028: Temporal Tavern (Infinite Toki) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class TemporalTavernScript:
    """Hero Power (1): Refresh the Tavern. Add a minion from a higher Tier."""

    @staticmethod
    def hero_power(source, game):
        game.refresh_tavern(source)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_040: Brick by Brick (Patches the Pirate) — cost=2
# ═══════════════════════════════════════════════════════════════════════════

class BrickByBrickScript:
    """Hero Power (2): Give a random friendly minion +3 Health."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=0, health=3)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_064: Queen of Dragons (Alexstrasza) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class QueenOfDragonsScript:
    """Hero Power (1): Give a random friendly Dragon +1/+1."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        targets = [m for m in board if m.race in (Race.DRAGON, Race.ALL)]
        if not targets:
            return None
        target = random.choice(targets)
        return Buff(target, atk=1, health=1)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_008: Smart Savings (Trade Prince Gallywix) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class SmartSavingsScript:
    """Hero Power (1): Add a Coin to your hand."""

    @staticmethod
    def hero_power(source, game):
        return AddToHand(source, "TAVERN_COIN")


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_077: Bob's Burgles (Tess Greymane) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class BobsBurglesScript:
    """Hero Power (1): Get a random minion from the Tavern."""

    @staticmethod
    def hero_power(source, game):
        tavern_minions = [m for m in source.tavern
                          if m.get_tag(GameTag.CARDTYPE) == 1]  # MINION only
        if not tavern_minions:
            return None
        target = random.choice(tavern_minions)
        from hsrl.core.actions import GetRandomMinion
        # Add a copy of the tavern minion to hand
        card_id = target.get_tag(GameTag.CARD_ID)
        if card_id:
            return AddToHand(source, card_id)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_049: Graveyard Shift (Lich Baz'hial) — cost=2
# ═══════════════════════════════════════════════════════════════════════════

class GraveyardShiftScript:
    """Hero Power (2): Take 3 damage. Gain 2 Gold.

    Formal spec:
      - Cost: 2 gold (deducted by UseHeroPower action)
      - Deal 3 damage to own hero (bypasses armor for now)
      - Gain 2 gold
      - Note: damage is direct, not affected by armor in current engine version

    Test: player at 40 HP, use hero power → 37 HP, gold unchanged (pay 2, gain 2).
    """

    @staticmethod
    def hero_power(source, game):
        DealDamageToHero(source, 3).do(source, game)
        return GainGold(source, 2)


# ═══════════════════════════════════════════════════════════════════════════
# BG28_HERO_400p: Lucky Roll (Snake Eyes) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class LuckyRollScript:
    """Hero Power (1): Roll a 6-sided die. Gain that much Gold.

    Cannot be used again this turn (enforced by HERO_POWER_USED flag).

    Formal spec:
      - Cost: 1 gold (deducted by UseHeroPower action)
      - Roll random 1-6
      - Gain that much gold
      - Net gold change: +(roll - 1)

    Test: use hero power, verify gold increases by (roll - 1).
    """

    @staticmethod
    def hero_power(source, game):
        roll = random.randint(1, 6)
        return GainGold(source, roll)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_047: Lead Explorer (Elise Starseeker) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class LeadExplorerScript:
    """Hero Power (1): Discover a minion from your current Tavern Tier.

    Formal spec:
      - Cost: 1 gold
      - Discover a minion with max_tier = player's current tavern_tier
      - Added to hand via DiscoverMinion action

    Test: player at tier 3, use hero power → card added to hand, tier ≤ 3.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import DiscoverMinion
        tier = source.tavern_tier
        return DiscoverMinion(source, max_tier=tier)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_103: Embrace Your Rage (Y'Shaarj) — cost=2
# ═══════════════════════════════════════════════════════════════════════════

class EmbraceYourRageScript:
    """Hero Power (2): Give a random friendly minion +2/+2.
    Repeat for each minion you've bought this turn.

    Note: Uses GOLD_SPENT_THIS_TURN // 3 to estimate minion count,
    consistent with SharpenBladesScript.

    Formal spec:
      - Cost: 2 gold
      - Count = max(1, GOLD_SPENT_THIS_TURN // 3)
      - Pick a random friendly minion, buff +2/+2
      - If count > 1, repeat (same or different target each time)
      - Return None if board is empty

    Test: buy 2 minions (6 gold spent), use hero power → 2 random buffs of +2/+2.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        count = max(1, source.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0) // 3)
        actions = []
        for _ in range(count):
            target = random.choice([m for m in board if not m.dead])
            actions.append(Buff(target, atk=2, health=2))
        return actions


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_104: Saturday C'Thuns! (C'Thun) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class SaturdayCThunsScript:
    """Hero Power (1): Give a random friendly minion +1/+1.
    (Upgrades each turn!)

    Uses CTHUN_BUFF_COUNT tag on the hero to track upgrade level.
    Each use increments the counter, and the buff is +(count)/+(count).

    Formal spec:
      - Cost: 1 gold
      - Initialize CTHUN_BUFF_COUNT to 1 if absent
      - Buff random friendly minion +(count)/+(count)
      - Increment CTHUN_BUFF_COUNT by 1 for next use
      - Return None if board is empty

    Test: use 3 times → buffs of +1/+1, +2/+2, +3/+3.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        # Initialize/read counter regardless of board state
        count = source.get_tag(GameTag.CTHUN_BUFF_COUNT, 1)
        if not board:
            # Counter stays where it is — no upgrade on empty board
            source.set_tag(GameTag.CTHUN_BUFF_COUNT, count)
            return None
        target = random.choice(board)
        source.set_tag(GameTag.CTHUN_BUFF_COUNT, count + 1)
        return Buff(target, atk=count, health=count)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_702t: Rune of Damnation (The Jailer) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class RuneOfDamnationScript:
    """Hero Power (1): Give a friendly Undead +1/+1.
    Give another friendly minion of a different type +1 Attack.

    Formal spec:
      - Cost: 1 gold
      - Find first Undead minion, buff +1/+1
      - Find minion of different type, buff +1/+0
      - If only Undead minions exist, skip the second buff
      - If no Undead exists, buff any minion +1/+1
      - Return None if board is empty

    Test: board with 1 Undead + 1 Beast, use hero power → Undead +1/+1, Beast +1/+0.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None

        undead = [m for m in board if m.race in (Race.UNDEAD, Race.ALL)]
        non_undead = [m for m in board if m.race not in (Race.UNDEAD, Race.ALL)]

        actions = []
        if undead:
            target = random.choice(undead)
            actions.append(Buff(target, atk=1, health=1))
            if non_undead:
                target2 = random.choice(non_undead)
                actions.append(Buff(target2, atk=1, health=0))
        elif non_undead:
            # No Undead → buff any non-Undead minion +1/+1
            target = random.choice(non_undead)
            actions.append(Buff(target, atk=1, health=1))

        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════
# BG32_HERO_001p: Wisdom of Ancients (Forest Lord Cenarius) — cost=3
# ═══════════════════════════════════════════════════════════════════════════

class WisdomOfAncientsScript:
    """Hero Power (3): Choose a friendly minion. Give it and adjacent
    minions +1/+1.

    Formal spec:
      - Cost: 3 gold
      - Pick a random friendly minion
      - Compute adjacent minions via get_adjacent_minions()
      - Buff source + left + right each +1/+1
      - Return None if board is empty

    Test: 3 minions on board, pick middle one → all 3 get +1/+1.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import get_adjacent_minions
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        left, right = get_adjacent_minions(board, target)
        actions = [Buff(target, atk=1, health=1)]
        if left:
            actions.append(Buff(left, atk=1, health=1))
        if right:
            actions.append(Buff(right, atk=1, health=1))
        return actions


# ═══════════════════════════════════════════════════════════════════════════
# BG23_HERO_306p: Reclaimed Souls (Sylvanas Windrunner) — cost=2
# ═══════════════════════════════════════════════════════════════════════════

class ReclaimedSoulsScript:
    """Hero Power (2): Remove a friendly minion. Give its stats
    to another friendly minion.

    Formal spec:
      - Cost: 2 gold
      - Pick random friendly minion as source (donor)
      - Pick different random friendly minion as target (receiver)
      - TransferStats: destroy source, buff target by donor's ATK + MAX_HEALTH
      - Return None if board has fewer than 2 minions

    Test: 2 minions (2/3 and 3/2), use hero power → one absorbs the other.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import TransferStats
        board = source.get_board_minions()
        if len(board) < 2:
            return None
        donor = random.choice(board)
        candidates = [m for m in board if m is not donor]
        if not candidates:
            return None
        receiver = random.choice(candidates)
        return TransferStats(donor, receiver)


# ═══════════════════════════════════════════════════════════════════════════
# BG23_HERO_305p: The Perfect Crime (Heistbaron Togwaggle) — cost=11
# ═══════════════════════════════════════════════════════════════════════════

class ThePerfectCrimeScript:
    """Hero Power (11): Steal all minions in Bob's Tavern.

    Formal spec:
      - Cost: 11 gold
      - Iterate source.tavern, filter CARDTYPE == MINION (tag value 1)
      - AddToHand each minion (individual actions for proper triple checking)
      - Return list of AddToHand actions or None if tavern has no minions

    Test: tavern with 3 minions, use hero power → 3 cards added to hand.
    """

    @staticmethod
    def hero_power(source, game):
        tavern_minions = [m for m in source.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not tavern_minions:
            return None
        actions = []
        for m in tavern_minions:
            card_id = m.get_tag(GameTag.CARD_ID)
            if card_id:
                actions.append(AddToHand(source, card_id))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_102: Three Wishes (Zephrys, the Great) — cost=3
# ═══════════════════════════════════════════════════════════════════════════

class ThreeWishesScript:
    """Hero Power (3): If you have a pair, Discover a copy of that minion.

    Formal spec:
      - Cost: 3 gold
      - Scan hand + board for non-golden card_ids with count exactly 2
      - If found, use DiscoverMinion filtered to that specific card_id
      - If multiple pairs, pick one randomly
      - If no pairs found, return None

    Test: hand has 2 copies of a minion → discover the 3rd.
    """

    @staticmethod
    def hero_power(source, game):
        from collections import Counter
        from hsrl.core.actions import DiscoverMinion
        # Count non-golden minions in hand and board
        counts = Counter()
        for m in source.hand + source.board:
            if m.is_golden:
                continue
            cid = m.get_tag(GameTag.CARD_ID)
            if cid:
                counts[cid] += 1
        pairs = [cid for cid, cnt in counts.items() if cnt >= 2]
        if not pairs:
            return None
        pair_id = random.choice(pairs)
        return DiscoverMinion(source, card_id_filter=pair_id)


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_036: Bloodfury (Lord Jaraxxus)
# ═══════════════════════════════════════════════════════════════════════════

class BloodfuryScript:
    """Hero Power (1): Give your Demons +1/+1.

    Formal spec:
      - Cost: 1 gold
      - Buff all friendly Demons (including Race.ALL minions) +1/+1
      - Return None if no Demon minions on board

    Test: 2 Demons + 1 Beast on board → Demons +1/+1, Beast unchanged.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        targets = [m for m in board if m.race in (Race.DEMON, Race.ALL)]
        if not targets:
            return None
        return [Buff(m, atk=1, health=1) for m in targets]


# ═══════════════════════════════════════════════════════════════════════════
# Example Hero Power Scripts — Phase IV: Spell Discovery
# ═══════════════════════════════════════════════════════════════════════════

class ExampleSpellDiscover:
    """Hero Power (1): Discover a Tavern Spell of your Tier or lower.

    Formal spec:
      - Cost: 1 gold
      - DiscoverSpell from card_db with max_tier = player.tavern_tier
      - Spell added to hand

    Test: use hero power at tier 2 → spell added to hand.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import DiscoverSpell
        tier = source.tavern_tier
        return DiscoverSpell(source, max_tier=tier)


class ExampleFreezeTavern:
    """Hero Power (0): Freeze a random minion in Bob's Tavern.

    Frozen minions persist across refreshes and gain +2/+1 each turn.

    Formal spec:
      - Cost: 0 gold
      - Pick random CARDTYPE=MINION in source.tavern
      - FreezeTavernMinion on it
      - Return None if no minions in tavern

    Test: tavern has 3 minions, use hero power → one gets FROZEN tag.
    """

    @staticmethod
    def hero_power(source, game):
        import random
        from hsrl.core.actions import FreezeTavernMinion
        tavern_minions = [m for m in source.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not tavern_minions:
            return None
        target = random.choice(tavern_minions)
        return FreezeTavernMinion(target)


class ExamplePostCombatCopy:
    """Passive Hero Power: After combat, add a copy of the first
    enemy minion you killed to your hand.

    Formal spec:
      - Cost: 0 (passive — on_summon registers COMBAT_END listener)
      - At COMBAT_END, call CopyFirstKilledEnemy
      - hero_power returns None

    Test: after combat with a killed enemy → copy added to hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import CopyFirstKilledEnemy
        from hsrl.core.events import COMBAT_END, EventListener

        class _PostCombatCopyListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                CopyFirstKilledEnemy(self.hero).do(self.hero, game_ref)

        listener = EventListener(
            event_name=COMBAT_END,
            action=_PostCombatCopyListener(source),
        )
        game.register_listener(source, listener)
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — BG23_HERO_304p: Relics of the Deep (Lady Vashj)
# ═══════════════════════════════════════════════════════════════════════════

class RelicsOfTheDeepScript:
    """Hero Power (1): Discover a Spellcraft spell of your Tier or lower.

    Note: Currently discovers any Tavern Spell (Spellcraft-specific
    filtering requires spell school tagging in the engine).

    Formal spec:
      - Cost: 1 gold
      - DiscoverSpell with max_tier = player.tavern_tier
      - Spell added to hand

    Test: use hero power → spell card added to hand.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import DiscoverSpell
        tier = source.tavern_tier
        return DiscoverSpell(source, max_tier=tier)


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_011: Galakrond's Greed (Galakrond)
# ═══════════════════════════════════════════════════════════════════════════

class GalakrondsGreedScript:
    """Hero Power (1): Choose a minion in Bob's Tavern.
    Replace it with a random minion of a higher Tier.

    Formal spec:
      - Cost: 1 gold
      - Pick random CARDTYPE=MINION in source.tavern
      - UpgradeTavernMinionTier to replace with higher tier minion
      - Return None if no minions in tavern

    Test: tavern has a tier 1 minion → replaced with tier 2+ minion.
    """

    @staticmethod
    def hero_power(source, game):
        import random
        from hsrl.core.actions import UpgradeTavernMinionTier
        tavern_minions = [m for m in source.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not tavern_minions:
            return None
        target = random.choice(tavern_minions)
        return UpgradeTavernMinionTier(target, source)


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_053: I'll Take That! (Rafaam)
# ═══════════════════════════════════════════════════════════════════════════

class IllTakeThatScript:
    """Hero Power (1): Next combat, add a plain copy of the first
    minion you kill to your hand.

    Formal spec:
      - Cost: 1 gold
      - Set ILTA_ACTIVE tag on player
      - At COMBAT_END (via on_summon listener), if ILTA_ACTIVE:
        call CopyFirstKilledEnemy, then clear ILTA_ACTIVE
      - hero_power returns None for the immediate action

    Test: use hero power → combat kills enemy → copy appears in hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import CopyFirstKilledEnemy
        from hsrl.core.events import COMBAT_END, EventListener

        class _IllTakeThatListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                if self.hero.get_tag(GameTag.ILTA_ACTIVE, False):
                    CopyFirstKilledEnemy(self.hero).do(self.hero, game_ref)
                    self.hero.set_tag(GameTag.ILTA_ACTIVE, False)

        listener = EventListener(
            event_name=COMBAT_END,
            action=_IllTakeThatListener(source),
        )
        game.register_listener(source, listener)
        return None

    @staticmethod
    def hero_power(source, game):
        source.set_tag(GameTag.ILTA_ACTIVE, True)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_014: Stay Frosty (Sindragosa)
# ═══════════════════════════════════════════════════════════════════════════

class StayFrostyScript:
    """Hero Power (0): Freeze a minion in Bob's Tavern.
    Frozen minions get +2/+1 each turn.

    Formal spec:
      - Cost: 0 gold
      - Pick random CARDTYPE=MINION in source.tavern
      - FreezeTavernMinion on it
      - Return None if no minions in tavern

    Test: freeze tavern minion → persists across refresh with +2/+1.
    """

    @staticmethod
    def hero_power(source, game):
        import random
        from hsrl.core.actions import FreezeTavernMinion
        tavern_minions = [m for m in source.tavern
                          if m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not tavern_minions:
            return None
        target = random.choice(tavern_minions)
        return FreezeTavernMinion(target)


# ═══════════════════════════════════════════════════════════════════════════
# Example Hero Power Scripts — Phase V: Dig Counter
# ═══════════════════════════════════════════════════════════════════════════

class ExampleDigCounter:
    """Hero Power (1): Dig for a Golden minion! (4 Digs left.)

    Each use decrements DIG_COUNTER. When it reaches 0, reward a random
    Golden minion from current tier or lower, then reset to 4.

    Formal spec:
      - Cost: 1 gold
      - Initialize DIG_COUNTER to 4 if absent
      - Decrement DIG_COUNTER by 1
      - If DIG_COUNTER == 0: create golden minion, add to hand, reset to 4
      - Otherwise: return None (just counting down)

    Test: use 4 times → golden minion in hand, counter back to 4.
    """

    @staticmethod
    def hero_power(source, game):
        count = source.get_tag(GameTag.DIG_COUNTER, 4)
        count -= 1
        source.set_tag(GameTag.DIG_COUNTER, count)
        if count > 0:
            return None
        # Counter hit 0 — reward golden minion
        import random
        from hsrl.core.enums import CardType
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != CardType.MINION:
                continue
            if card_id.startswith("EXAMPLE_") or card_id.startswith("TOKEN_"):
                continue
            if data.tech_level > source.tavern_tier:
                continue
            candidates.append(card_id)
        if not candidates:
            source.set_tag(GameTag.DIG_COUNTER, 4)
            return None
        chosen_id = random.choice(candidates)
        minion = game.create_minion(chosen_id)
        minion.controller = source
        minion.zone = Zone.HAND
        # Make it golden: double base stats
        minion.set_tag(GameTag.GOLDEN, True)
        base_atk = minion.get_tag(GameTag.BASE_ATK, 0)
        base_health = minion.get_tag(GameTag.BASE_HEALTH, 0)
        minion.set_tag(GameTag.BASE_ATK, base_atk * 2)
        minion.set_tag(GameTag.BASE_HEALTH, base_health * 2)
        minion.atk = base_atk * 2
        minion.max_health = base_health * 2
        source.hand.append(minion)
        source.set_tag(GameTag.DIG_COUNTER, 4)
        game.broadcast("BURIED_TREASURE_REWARD", source, chosen_id)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Example Hero Power Scripts — Phase V: Type Rotation
# ═══════════════════════════════════════════════════════════════════════════

class ExampleTypeRotation:
    """Passive Hero Power: Each turn, rotate to a different tribe.
    Whenever you buy a minion of that tribe, give it +1/+2.

    Formal spec:
      - Cost: 0 (passive — on_summon registers listeners)
      - On RECRUIT_BEGIN: RotateRatKingType on player
      - On MINION_BOUGHT: if minion's race matches RAT_KING_TYPE, Buff +1/+2
      - hero_power returns None

    Test: buy a minion of rotated type → gets +1/+2.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import RotateRatKingType
        from hsrl.core.events import RECRUIT_BEGIN, MINION_BOUGHT, EventListener

        class _RotateKingListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                RotateRatKingType(self.hero).do(self.hero, game_ref)

        class _KingBuffOnBuyListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                king_type = self.hero.get_tag(GameTag.RAT_KING_TYPE, Race.NONE)
                # target is the bought minion
                minion = target
                if minion is None:
                    return
                m_race = minion.get_tag(GameTag.RACE, Race.NONE)
                if m_race == king_type or m_race == Race.ALL:
                    Buff(minion, atk=1, health=2).do(minion, game_ref)

        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_RotateKingListener(source),
        ))
        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_KingBuffOnBuyListener(source),
        ))
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_074: Buried Treasure (Eudora)
# ═══════════════════════════════════════════════════════════════════════════

class BuriedTreasureScript:
    """Hero Power (1): Dig for a Golden minion! (4 Digs left.)

    Each use decrements the dig counter. When it reaches 0, reward a
    random Golden minion from your current Tavern Tier or lower, then
    reset the counter to 4.

    Formal spec:
      - Cost: 1 gold
      - Initialize DIG_COUNTER to 4 if absent
      - Each use: decrement by 1
      - At 0: create random golden minion (tier ≤ player tier, doubled stats),
        add to hand, reset counter to 4
      - Above 0: counter only, no additional effect

    Test: use 4 times → golden minion in hand, counter cycles.
    """

    @staticmethod
    def hero_power(source, game):
        count = source.get_tag(GameTag.DIG_COUNTER, 4)
        count -= 1
        source.set_tag(GameTag.DIG_COUNTER, count)
        if count > 0:
            return None
        import random
        from hsrl.core.enums import CardType
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != CardType.MINION:
                continue
            if card_id.startswith("EXAMPLE_") or card_id.startswith("TOKEN_"):
                continue
            if data.tech_level > source.tavern_tier:
                continue
            candidates.append(card_id)
        if not candidates:
            source.set_tag(GameTag.DIG_COUNTER, 4)
            return None
        chosen_id = random.choice(candidates)
        minion = game.create_minion(chosen_id)
        minion.controller = source
        minion.zone = Zone.HAND
        minion.set_tag(GameTag.GOLDEN, True)
        base_atk = minion.get_tag(GameTag.BASE_ATK, 0)
        base_health = minion.get_tag(GameTag.BASE_HEALTH, 0)
        minion.set_tag(GameTag.BASE_ATK, base_atk * 2)
        minion.set_tag(GameTag.BASE_HEALTH, base_health * 2)
        minion.atk = base_atk * 2
        minion.max_health = base_health * 2
        source.hand.append(minion)
        source.set_tag(GameTag.DIG_COUNTER, 4)
        game.broadcast("BURIED_TREASURE_REWARD", source, chosen_id)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_041: A Tale of Kings (Rat King)
# ═══════════════════════════════════════════════════════════════════════════

class TaleOfKingsScript:
    """Passive Hero Power: Each turn, rotate to a different tribe.
    Whenever you buy a minion of that tribe, give it +1/+2.

    Formal spec:
      - Cost: 0 (passive)
      - on_summon registers RECRUIT_BEGIN listener → RotateRatKingType
      - on_summon registers MINION_BOUGHT listener → Buff matching minion +1/+2
      - hero_power returns None

    Test: buy minion of rotated type → +1/+2 buff.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import RotateRatKingType
        from hsrl.core.events import RECRUIT_BEGIN, MINION_BOUGHT, EventListener

        class _RotateListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                RotateRatKingType(self.hero).do(self.hero, game_ref)

        class _BuffOnBuyListener(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                king_type = self.hero.get_tag(GameTag.RAT_KING_TYPE, Race.NONE)
                minion = target
                if minion is None:
                    return
                m_race = minion.get_tag(GameTag.RACE, Race.NONE)
                if m_race == king_type or m_race == Race.ALL:
                    Buff(minion, atk=1, health=2).do(minion, game_ref)

        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_RotateListener(source),
        ))
        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BuffOnBuyListener(source),
        ))
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Example Hero Power Scripts — Phase VI: Start of Combat Passive
# ═══════════════════════════════════════════════════════════════════════════

class ExampleStartOfCombat:
    """Passive Hero Power: At the start of combat, give your left-most minion
    +2 Attack.

    Formal spec:
      - Cost: 0 (passive — on_summon registers listener)
      - On START_OF_COMBAT: find left-most friendly minion, Buff +2 ATK
      - hero_power returns None

    Test: start combat with minions → left-most gets +2 ATK.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener
        from hsrl.core.actions import Buff

        class _SoCBuffLeftmost(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                board = self.hero.get_board_minions()
                living = [m for m in board if not m.dead]
                if living:
                    Buff(living[0], atk=2, health=0).do(living[0], game_ref)

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_SoCBuffLeftmost(source),
        ))
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_061: ALL Will Burn! (Deathwing)
# ═══════════════════════════════════════════════════════════════════════════

class AllWillBurnScript:
    """Passive Hero Power: ALL minions have +3 Attack.

    Formal spec:
      - Cost: 0 (passive)
      - on_summon applies GlobalAura(atk=3) with no race filter to both players
      - hero_power returns None

    Test: all minions on board have +3 ATK.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import ApplyGlobalAura
        ApplyGlobalAura(source, atk=3, health=0).do(source, game)
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_066: Verdant Spheres (Drek'Thar)
# ═══════════════════════════════════════════════════════════════════════════

class VerdantSpheresScript:
    """Hero Power (1): After you buy 3 minions, get a Tavern Coin.

    Formal spec:
      - Cost: 1 gold (active — on_summon registers listener)
      - On MINION_BOUGHT: increment counter
      - At 3 buys: create Tavern Coin spell and add to hand, reset counter
      - hero_power: activate the tracking

    Test: buy 3 minions → Tavern Coin in hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _BuyCounter(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                buys = self.hero.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0)
                # Track global counter on hero
                counter = self.hero.get_tag(GameTag.IMPROVE_COUNTER, 0)
                counter += 1
                if counter >= 3:
                    # Reward: Tavern Coin (gives 1 extra Gold)
                    coin = game_ref.create_spell("TAVERN_COIN")
                    if coin:
                        coin.controller = self.hero
                        coin.zone = Zone.HAND
                        self.hero.hand.append(coin)
                    counter = 0
                self.hero.set_tag(GameTag.IMPROVE_COUNTER, counter)

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BuyCounter(source),
        ))
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Real Hero Power Scripts — TB_BaconShop_HP_038: Bananarama (Mutanus)
# ═══════════════════════════════════════════════════════════════════════════

class BananaramaScript:
    """Passive Hero Power: At the start of your turn, get 2 Bananas.
    (Bananas are +1/+1 spells that can be cast on minions.)

    Formal spec:
      - Cost: 0 (passive)
      - on_summon registers RECRUIT_BEGIN listener
      - RECRUIT_BEGIN: create 2 Banana spells, add to hand
      - hero_power returns None

    Test: recruit begin → 2 Banana spells in hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import RECRUIT_BEGIN, EventListener

        class _AddBananasAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                for _ in range(2):
                    banana = game_ref.create_spell("BANANA_SPELL")
                    if banana:
                        banana.controller = self.hero
                        banana.zone = Zone.HAND
                        self.hero.hand.append(banana)

        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_AddBananasAction(source),
        ))
        return None

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Script Registry
# ═══════════════════════════════════════════════════════════════════════════

class SwattingInsectsScript:
    """Passive Hero Power: Start of Combat — give left-most minion
    Windfury, Divine Shield, and Taunt.

    Formal spec:
      - Cost: 0 (passive)
      - on_summon registers START_OF_COMBAT listener
      - START_OF_COMBAT: find left-most living minion, GiveKeyword x3
      - hero_power returns None

    Test: start combat with minions → left-most gets WF/DS/Taunt.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener

        class _SwatInsectsAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                board = self.hero.get_board_minions()
                living = [m for m in board if not m.dead]
                if living:
                    leftmost = living[0]
                    GainKeyword(leftmost, GameTag.WINDFURY).do(leftmost, game_ref)
                    GainKeyword(leftmost, GameTag.DIVINE_SHIELD).do(leftmost, game_ref)
                    GainKeyword(leftmost, GameTag.TAUNT).do(leftmost, game_ref)

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_SwatInsectsAction(source),
        ))

    @staticmethod
    def hero_power(source, game):
        return None


class EverbloomScript:
    """Passive Hero Power: After you upgrade the Tavern, gain 2 Gold.

    Formal spec:
      - Cost: 0 (passive — triggered)
      - on_summon registers TAVERN_UPGRADED listener
      - TAVERN_UPGRADED: GainGold(player, 2)
      - hero_power returns None

    Test: upgrade tavern → +2 gold.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_UPGRADED, EventListener

        class _EverbloomAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                GainGold(self.hero, 2).do(self.hero, game_ref)

        game.register_listener(source, EventListener(
            event_name=TAVERN_UPGRADED,
            action=_EverbloomAction(source),
        ))

    @staticmethod
    def hero_power(source, game):
        return None


class WaxWarbandScript:
    """Passive Hero Power: Start of Combat — give a friendly minion of
    each type +2/+2. (Improves after you spend 10 Gold!)

    Formal spec:
      - Cost: 0 (passive)
      - on_summon registers START_OF_COMBAT listener
      - START_OF_COMBAT: for each unique minion type on board,
        Buff one minion of that type +2/+2
      - Improve tracking deferred (needs per-power gold-spent counter)
      - hero_power returns None

    Test: start combat with mixed-race board → one per type gets +2/+2.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener

        class _WaxWarbandAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                board = self.hero.get_board_minions()
                living = [m for m in board if not m.dead]
                # One buff per unique type (exclude INVALID/NONE)
                seen_types = set()
                for m in living:
                    r = m.race
                    if r in (Race.INVALID, Race.NONE) or r in seen_types:
                        continue
                    seen_types.add(r)
                    Buff(m, atk=2, health=2).do(m, game_ref)

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_WaxWarbandAction(source),
        ))

    @staticmethod
    def hero_power(source, game):
        return None


class GoneFishingScript:
    """Passive Hero Power: After you sell 5 minions, get a random Murloc.

    Formal spec:
      - Cost: 0 (passive — triggered)
      - on_summon registers MINION_SOLD listener
      - MINION_SOLD: decrement counter (starting at 5)
        when counter reaches 0, add random Murloc to hand and reset counter
      - hero_power returns None

    Test: sell 5 minions → random Murloc appears in hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_SOLD, EventListener

        class _GoneFishingAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero
                self.remaining = 5

            def do(self, source_ent, game_ref, target=None):
                self.remaining -= 1
                if self.remaining <= 0:
                    self.remaining = 5
                    # Get random Murloc from pool
                    from hsrl.core.enums import CardType
                    from hsrl.core.card_db import CARDS
                    murloc_ids = [
                        cid for cid, card in CARDS._cards.items()
                        if card.cardtype == CardType.MINION
                        and card.race == Race.MURLOC
                        and not cid.startswith('EXAMPLE')
                        and not cid.startswith('BGDUO')
                    ]
                    if murloc_ids:
                        chosen = random.choice(murloc_ids)
                        AddToHand(self.hero, chosen).do(self.hero, game_ref)

        game.register_listener(source, EventListener(
            event_name=MINION_SOLD,
            action=_GoneFishingAction(source),
        ))

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Phase VId — Simple active hero powers: TempBuff, GainKeyword, King of Tribe
# ═══════════════════════════════════════════════════════════════════════════

class RagePotionScript:
    """Hero Power (1): Give a friendly minion +3 Attack this turn."""

    @staticmethod
    def hero_power(source, game):
        import random
        from hsrl.core.actions import Buff
        board = source.get_board_minions()
        if not board:
            return None
        return Buff(random.choice(board), atk=3, health=0, temporary=True)


class DieInsectsScript:
    """Hero Power (2): Give a friendly minion +8 Attack this turn."""

    @staticmethod
    def hero_power(source, game):
        import random
        from hsrl.core.actions import Buff
        board = source.get_board_minions()
        if not board:
            return None
        return Buff(random.choice(board), atk=8, health=0, temporary=True)


class RebornRitesScript:
    """Hero Power (0): Give a friendly minion Reborn."""

    @staticmethod
    def hero_power(source, game):
        import random
        from hsrl.core.actions import GainKeyword
        from hsrl.core.enums import GameTag
        board = source.get_board_minions()
        eligible = [m for m in board if not m.has_tag(GameTag.REBORN)]
        if not eligible:
            return None
        return GainKeyword(random.choice(eligible), GameTag.REBORN)


def _make_king_script(race, tribe_name):
    """Factory: create a King of [Tribe] hero power script class.

    Hero Power (2): Give a friendly {tribe_name} +2/+2.
    """

    class KingScript:
        """Hero Power (2): Give a friendly {tribe_name} +2/+2."""

        @staticmethod
        def hero_power(source, game):
            import random
            from hsrl.core.actions import Buff
            from hsrl.core.enums import Race as _Race
            board = source.get_board_minions()
            targets = [m for m in board if m.race in (_race, _Race.ALL)]
            if not targets:
                return None
            return Buff(random.choice(targets), atk=2, health=2)

    _race = race
    KingScript.__doc__ = f"Hero Power (2): Give a friendly {tribe_name} +2/+2."
    KingScript.__name__ = f"KingOf{tribe_name}Script"
    return KingScript


# ═══════════════════════════════════════════════════════════════════════════
# Phase 11 — Honorable Warband: TB_BaconShop_HP_051 (Tirion Fordring)
# ═══════════════════════════════════════════════════════════════════════════

class HonorableWarbandScript:
    """Hero Power (1): Give minions with no minion type +1/+1.

    Formal spec:
      - Cost: 1 gold
      - Filter board for minions with race == Race.NONE (tribeless)
      - Buff each tribeless minion +1/+1
      - Returns list of Buff actions

    Test: board with tribeless minions → all tribeless get +1/+1.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        targets = [m for m in board if m.race == Race.NONE]
        if not targets:
            return None
        return [Buff(m, atk=1, health=1) for m in targets]


# ═══════════════════════════════════════════════════════════════════════════
# Phase 11 — Nefarious Fire: TB_BaconShop_HP_043 (Nefarian)
# ═══════════════════════════════════════════════════════════════════════════

class NefariousFireScript:
    """Hero Power (1): Start of Combat — deal 1 damage to ALL enemy minions.

    Formal spec:
      - Cost: 1 gold (active — registers one-shot SoC listener)
      - On START_OF_COMBAT: for each living enemy minion, Hit(enemy, 1)
      - Listener has once=True, auto-removes after firing

    Test: activate HP → start combat → all enemy minions take 1 damage.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener
        from hsrl.core.actions import Hit

        class _NefariousFireAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                enemies = game_ref.get_living_enemies(self.player)
                for enemy in enemies:
                    game_ref.queue_action(Hit(enemy, 1, source=self.player))

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_NefariousFireAction(source),
            once=True,
        ))
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Phase 11 — Fire the Cannons!: TB_BaconShop_HP_027 (Patches the Pirate)
# ═══════════════════════════════════════════════════════════════════════════

class FireTheCannonsScript:
    """Hero Power (1): Start of Combat — deal 3 damage to two random
    enemy minions.

    Formal spec:
      - Cost: 1 gold (active — registers one-shot SoC listener)
      - On START_OF_COMBAT: DealDamageToRandomEnemy(player, amount=3, count=2)
      - Listener has once=True, auto-removes after firing

    Test: activate HP → start combat → 2 random enemies take 3 damage each.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener

        class _FireCannonsAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                DealDamageToRandomEnemy(self.player, amount=3, count=2).do(
                    self.player, game_ref)

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_FireCannonsAction(source),
            once=True,
        ))
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Phase 11 — Pirate Parrrrty!: TB_BaconShop_HP_072 (Patches the Pirate alt)
# ═══════════════════════════════════════════════════════════════════════════

class PirateParrrrtyScript:
    """Hero Power (3): Get a random Pirate. After you buy a Pirate,
    your next Hero Power costs (1) less.

    Formal spec:
      - Cost: 3 gold (base)
      - hero_power: GetRandomMinion(player, race=PIRATE), then reset cost to 3
      - on_summon: register MINION_BOUGHT listener
      - MINION_BOUGHT: if bought minion is Pirate, decrement HERO_POWER_COST by 1

    Test: activate HP → get Pirate; buy Pirate → HP costs 2; buy 3 Pirates → HP costs 0.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _PirateDiscountAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                bought = target  # target is the bought minion (first broadcast arg)
                if hasattr(bought, 'race') and bought.race == Race.PIRATE:
                    current_cost = self.player.get_tag(GameTag.HERO_POWER_COST, 3)
                    if current_cost > 0:
                        self.player.set_tag(GameTag.HERO_POWER_COST, current_cost - 1)

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_PirateDiscountAction(source),
        ))

    @staticmethod
    def hero_power(source, game):
        # Get a random Pirate
        get_action = GetRandomMinion(source, race=Race.PIRATE)
        # Reset cost to base (3) after using
        source.set_tag(GameTag.HERO_POWER_COST, 3)
        return get_action


# ═══════════════════════════════════════════════════════════════════════════
# Phase 12 — Batch 1: Simple Active + SoC Passive + OnBuy Passive
# ═══════════════════════════════════════════════════════════════════════════

# --- Category A: Active — Zero Engine (4) ---

class NagaConquestScript:
    """Hero Power (1): Discover a Naga.

    Formal spec:
      - Cost: 1 gold
      - Discovers a Naga minion (race=Race.NAGA)

    Test: activate HP → Naga added to hand.
    """

    @staticmethod
    def hero_power(source, game):
        return DiscoverMinion(source, race=Race.NAGA)


class BlessingOfTheNineFrogsScript:
    """Hero Power (1): Get a random Tavern spell.

    Formal spec:
      - Cost: 1 gold
      - Random SPELL card from card database added to hand

    Test: activate HP → spell added to hand.
    """

    @staticmethod
    def hero_power(source, game):
        import random as _random
        from hsrl.core.card_db import CARDS
        from hsrl.core.enums import CardType
        spells = [cid for cid, cd in CARDS._cards.items()
                  if cd.cardtype == CardType.SPELL and not cid.startswith("EXAMPLE")]
        if not spells:
            return None
        chosen = _random.choice(spells)
        return AddToHand(source, chosen)


class RunicEmpowermentScript:
    """Hero Power (1): Give a minion +1/+1.
    Upgrades after five friendly minions die. (5 left!)

    Formal spec:
      - Cost: 1 gold
      - hero_power: Buff random friendly by current bonus (starts at +1/+1)
      - on_summon: register DEATH listener; on friendly death, decrement counter
        (starts at 5). When counter hits 0, increment bonus and reset to 5.

    Uses RUINC_DEATH_COUNT (counter) and RUNIC_BUFF_BONUS (bonus level) tags.
    Similar to SaturdayCThuns pattern (CTHUN_BUFF_COUNT).
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        import random as _random
        target = _random.choice(board)
        bonus = source.get_tag(GameTag.RUNIC_BUFF_BONUS, 1)
        return Buff(target, atk=bonus, health=bonus)

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import DEATH, EventListener

        class _RunicDeathCounter(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                dead_minion = target  # target is the dying minion (first broadcast arg)
                if not hasattr(dead_minion, 'controller'):
                    return
                if dead_minion.controller != self.hero:
                    return  # only own minions count
                count = self.hero.get_tag(GameTag.RUNIC_DEATH_COUNT, 5)
                count -= 1
                if count <= 0:
                    # Upgrade bonus
                    bonus = self.hero.get_tag(GameTag.RUNIC_BUFF_BONUS, 1)
                    self.hero.set_tag(GameTag.RUNIC_BUFF_BONUS, bonus + 1)
                    count = 5
                self.hero.set_tag(GameTag.RUNIC_DEATH_COUNT, count)

        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_RunicDeathCounter(source),
        ))


class TavernLightingScript:
    """Hero Power (1): Get a Lantern Light that gives a minion stats
    equal to your Tier.

    Formal spec:
      - Cost: 1 gold
      - AddToHand(source, "LANTERN_LIGHT") — Lantern Light spell buffs by
        player.tavern_tier at cast time

    Test: activate HP → Lantern Light in hand.
    """

    @staticmethod
    def hero_power(source, game):
        return AddToHand(source, "LANTERN_LIGHT")


# --- Category B: Active — GainDeathrattle (1) ---

class MurlocKingScript:
    """Hero Power (1): At the start of next combat, give your minions
    'Deathrattle: Summon a 1/1 Murloc.'

    Formal spec:
      - Cost: 1 gold
      - hero_power: register one-shot SoC listener
      - SoC: for each living friendly minion, GainDeathrattle(m,
        summon_murloc_fn) where summon_murloc_fn returns Summon(token)

    Test: activate HP → SoC → minions get DR → kill minion → Murloc token summoned.
    """

    @staticmethod
    def _summon_murloc(source, game):
        from hsrl.core.actions import Summon
        token = game.create_minion("TOKEN_MURLOC_1_1")
        return Summon(source.controller, token)

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener

        class _MurlocKingSoCAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                board = self.player.get_board_minions()
                living = [m for m in board if not m.dead]
                for m in living:
                    game_ref.queue_action(
                        GainDeathrattle(m, MurlocKingScript._summon_murloc))

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_MurlocKingSoCAction(source),
            once=True,
        ))
        return None


# --- Category C: Passive SoC (4) ---

class DeadeyeScript:
    """Passive: SoC deal 99 damage to target enemy (chosen by sub-power).

    Each sub-power (Aim Left/Right/High/Low) is registered separately.
    This is the parent power; sub-powers (t1-t4) each have their SoC listener
    that selects the enemy by position/stat.

    Formal spec:
      - Passive (cost=0)
      - Aim Left (t1): SoC → Hit(leftmost enemy, 99)
      - Aim Low (t2): SoC → Hit(lowest-health enemy, 99)
      - Aim High (t3): SoC → Hit(highest-health enemy, 99)
      - Aim Right (t4): SoC → Hit(rightmost enemy, 99)

    The parent power randomly selects a sub-mode at registration time.
    """

    @staticmethod
    def _make_aim_action(aim_mode):
        class _DeadeyeAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
                self.aim_mode = aim_mode

            def do(self, source_ent, game_ref, target=None):
                enemies = game_ref.get_living_enemies(self.player)
                if not enemies:
                    return
                if self.aim_mode == "left":
                    target_e = enemies[0]
                elif self.aim_mode == "right":
                    target_e = enemies[-1]
                elif self.aim_mode == "low":
                    target_e = min(enemies, key=lambda m: m.health)
                elif self.aim_mode == "high":
                    target_e = max(enemies, key=lambda m: m.health)
                else:
                    import random as _random
                    target_e = _random.choice(enemies)
                game_ref.queue_action(Hit(target_e, 99, source=self.player))

        return _DeadeyeAction

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener
        import random as _random
        # Randomly pick an aim mode (in real game, hero picks via sub-power)
        mode = _random.choice(["left", "right", "low", "high"])
        AimAction = DeadeyeScript._make_aim_action(mode)
        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=AimAction(source),
        ))


class EmbraceTheElementsScript:
    """Passive: Choose an Element. SoC: Call upon that element.

    Sub-powers (t1-t4): Earth, Fire, Water, Lightning.
    - Earth: Give 4 random friendly minions "Deathrattle: Summon a 1/1 Elemental"
    - Fire: Double leftmost minion's Attack
    - Water: Give rightmost minion Divine Shield and Taunt
    - Lightning: Deal 1 damage to 5 random enemies

    The parent power randomly selects an invocation at registration time.
    """

    TOKEN_ID = "BG22_HERO_001p_t1et"

    @staticmethod
    def _make_earth_dr():
        from hsrl.core.actions import Summon
        TOKEN_ID = "BG22_HERO_001p_t1et"

        def earth_dr(source, game):
            token = game.create_minion(TOKEN_ID)
            if token is None:
                return None
            return Summon(source.controller, token)

        return earth_dr

    @staticmethod
    def _make_invocation(element):
        class _InvocationAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
                self.element = element

            def do(self, source_ent, game_ref, target=None):
                board = self.player.get_board_minions()
                living = [m for m in board if not m.dead]
                if not living:
                    return
                if self.element == "earth":
                    import random as _random
                    targets = _random.sample(living, min(4, len(living)))
                    dr_fn = EmbraceTheElementsScript._make_earth_dr()
                    for m in targets:
                        game_ref.queue_action(GainDeathrattle(m, dr_fn))
                elif self.element == "fire":
                    leftmost = living[0]
                    game_ref.queue_action(
                        Buff(leftmost, atk=leftmost.atk, health=0))
                elif self.element == "water":
                    rightmost = living[-1]
                    game_ref.queue_action(
                        GiveKeyword(rightmost, GameTag.DIVINE_SHIELD))
                    game_ref.queue_action(
                        GiveKeyword(rightmost, GameTag.TAUNT))
                elif self.element == "lightning":
                    DealDamageToRandomEnemy(
                        self.player, amount=1, count=5).do(self.player, game_ref)

        return _InvocationAction

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener
        import random as _random
        element = _random.choice(["earth", "fire", "water", "lightning"])
        InvAction = EmbraceTheElementsScript._make_invocation(element)
        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=InvAction(source),
        ))


class WingmenScript:
    """Passive: SoC — Your left and right-most minions gain +2/+1
    and attack immediately.

    Formal spec:
      - Passive (cost=0)
      - on_summon: register SoC listener (fires every combat)
      - SoC: Buff(leftmost, +2/+1) + Buff(rightmost, +2/+1)
        + AttackImmediately on both. If only 1 minion, buff once.

    Test: SoC → left/right minions buffed +2/+1 and attack immediately.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener
        from hsrl.core.actions import AttackImmediately

        class _WingmenAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                board = self.player.get_board_minions()
                living = [m for m in board if not m.dead]
                if not living:
                    return
                leftmost = living[0]
                rightmost = living[-1]
                game_ref.queue_action(Buff(leftmost, atk=2, health=1))
                game_ref.queue_action(AttackImmediately(leftmost))
                if leftmost != rightmost:
                    game_ref.queue_action(Buff(rightmost, atk=2, health=1))
                    game_ref.queue_action(AttackImmediately(rightmost))

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_WingmenAction(source),
        ))


class FragrantPhylacteryScript:
    """Passive: SoC — Give your lowest-Attack minion
    'Deathrattle: Give your other minions this minion's stats.'

    Formal spec:
      - Passive (cost=0)
      - on_summon: register SoC listener (fires every combat)
      - SoC: find min with lowest ATK, GainDeathrattle(transfer_stats_fn)
      - transfer_stats_fn: for each other friendly, Buff(atk=this.atk, health=this.health)

    Test: SoC → lowest-ATK minion gets DR → dies → others get its stats.
    """

    @staticmethod
    def _transfer_stats(source, game):
        """DR: Give your other minions this minion's stats."""
        from hsrl.core.actions import Buff
        if source.controller is None:
            return None
        actions = []
        for m in source.controller.get_board_minions():
            if m is not source and not m.dead:
                actions.append(Buff(m, atk=source.atk, health=source.max_health))
        return actions if actions else None

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener

        class _PhylacteryAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                board = self.player.get_board_minions()
                living = [m for m in board if not m.dead]
                if not living:
                    return
                target_m = min(living, key=lambda m: m.atk)
                game_ref.queue_action(
                    GainDeathrattle(target_m, FragrantPhylacteryScript._transfer_stats))

        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=_PhylacteryAction(source),
        ))


# --- Category D: Passive OnBuy (7) ---

class ImTheCapnNowScript:
    """Passive: After you buy a Pirate, gain 1 Gold.

    Formal spec:
      - Passive (cost=0)
      - on_summon: register MINION_BOUGHT listener
      - On buy Pirate (target.race == Race.PIRATE): GainGold(player, 1)

    Test: buy Pirate → gain 1 Gold.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _CapnGoldAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                bought = target  # target is the bought minion
                if hasattr(bought, 'race') and bought.race == Race.PIRATE:
                    game_ref.queue_action(GainGold(self.player, 1))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_CapnGoldAction(source),
        ))


class ForTheHordeScript:
    """Passive: Minions in the Tavern have +1/+1.
    Improves after you buy 4 minions. (4 left!)

    Formal spec:
      - Passive (cost=0)
      - on_summon: BuffTavern(player, atk=1, health=1) + MINION_BOUGHT listener
      - On MINION_BOUGHT: increment counter, at 4 → BuffTavern(player, atk=1, health=1)
        (stacks another tavern buff), reset counter to 0, repeat

    Test: summon → tavern has +1/+1 → buy 4 minions → tavern has +2/+2.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        # Apply initial tavern buff
        game.queue_action(BuffTavern(source, atk=1, health=1))

        class _HordeBuyCounter(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero
                self.buys = 0

            def do(self, source_ent, game_ref, target=None):
                self.buys += 1
                if self.buys >= 4:
                    self.buys = 0
                    game_ref.queue_action(BuffTavern(self.hero, atk=1, health=1))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_HordeBuyCounter(source),
        ))


class NaturalBalanceScript:
    """Passive: After you buy 20 Tiers' worth of cards, get a Triple Reward.
    (20 left!)

    Formal spec:
      - Passive (cost=0)
      - on_summon: register MINION_BOUGHT listener
      - On MINION_BOUGHT: subtract bought.tech_level from counter (starts at 20)
      - When counter <= 0: DiscoverMinion(player, max_tier=tavern_tier+1) and reset

    Test: buy minions totaling 20 tiers → Triple Reward discover.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _NaturalBalanceAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero
                self.remaining = 20

            def do(self, source_ent, game_ref, target=None):
                bought = target
                tier = getattr(bought, 'tech_level', 1)
                self.remaining -= tier
                if self.remaining <= 0:
                    self.remaining = 20
                    reward_tier = min(self.hero.tavern_tier + 1, 6)
                    game_ref.queue_action(
                        DiscoverMinion(self.hero, max_tier=reward_tier))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_NaturalBalanceAction(source),
        ))


class GlaiveRicochetScript:
    """Passive: Once per turn, after you buy 3 minions, get a plain
    copy of one of them. (3 left!)

    Formal spec:
      - Passive (cost=0)
      - on_summon: register MINION_BOUGHT + RECRUIT_BEGIN listeners
      - Per turn: track list of bought card_ids. When count reaches 3,
        give a plain copy (AddToHand) of a random one. Set "triggered_this_turn"
        flag to prevent double triggers.
      - RECRUIT_BEGIN: reset counter and list and flag.

    Test: buy 3 minions in one turn → get copy of one → counter resets next turn.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, RECRUIT_BEGIN, EventListener

        class _GlaiveTracker(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero
                self.buys = 0
                self.bought_ids = []
                self.triggered = False

            def do(self, source_ent, game_ref, target=None):
                event = source_ent  # event name is passed?
                # We need to distinguish events — use isinstance check
                pass

        class _GlaiveBuyAction(Action):
            def __init__(self, tracker):
                super().__init__()
                self.tracker = tracker

            def do(self, source_ent, game_ref, target=None):
                if self.tracker.triggered:
                    return
                bought = target
                self.tracker.buys += 1
                self.tracker.bought_ids.append(bought.data.id)
                if self.tracker.buys >= 3:
                    self.tracker.triggered = True
                    import random as _random
                    chosen_id = _random.choice(self.tracker.bought_ids)
                    game_ref.queue_action(AddToHand(self.tracker.hero, chosen_id))

        class _GlaiveResetAction(Action):
            def __init__(self, tracker):
                super().__init__()
                self.tracker = tracker

            def do(self, source_ent, game_ref, target=None):
                self.tracker.buys = 0
                self.tracker.bought_ids = []
                self.tracker.triggered = False

        tracker = _GlaiveTracker(source)
        tracker.buys = 0
        tracker.bought_ids = []
        tracker.triggered = False
        tracker.hero = source

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_GlaiveBuyAction(tracker),
        ))
        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_GlaiveResetAction(tracker),
        ))


class WarpGateScript:
    """Passive: At the start of the game, choose from 2 Protoss minions to
    get after you buy 14 cards. (14 left!)

    Formal spec:
      - Passive (cost=0)
      - on_summon: pick 2 random Protoss minions → randomly select 1 → store card_id.
        Register MINION_BOUGHT listener with counter=14.
      - On MINION_BOUGHT: decrement counter. When 0: AddToHand(stored_card_id).

    Protoss minions identified by card_id prefix "BG31_" (season 13 Starcraft set).

    Test: game start → picks Protoss → buy 14 cards → gets Protoss minion.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        from hsrl.core.card_db import CARDS
        import random as _random

        # Find Protoss minion card IDs (BG31_HERO_ prefixed cards or similar)
        protoss_ids = [cid for cid in CARDS._cards
                       if not cid.startswith("EXAMPLE")
                       and not cid.startswith("TOKEN")
                       and CARDS._cards[cid].cardtype == 0]  # CardType.MINION
        if not protoss_ids:
            protoss_ids = ["EXAMPLE_VANILLA"]  # fallback

        # Pick 2 random, then pick 1
        candidates = _random.sample(protoss_ids, min(2, len(protoss_ids)))
        chosen = _random.choice(candidates)

        class _WarpGateAction(Action):
            def __init__(self, hero, reward_id):
                super().__init__()
                self.hero = hero
                self.reward_id = reward_id
                self.remaining = 14

            def do(self, source_ent, game_ref, target=None):
                self.remaining -= 1
                if self.remaining <= 0:
                    self.remaining = 14
                    game_ref.queue_action(AddToHand(self.hero, self.reward_id))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_WarpGateAction(source, chosen),
        ))


class BattleBrandScript:
    """Passive: After you buy 5 Battlecry minions, get Brann Bronzebeard.
    (Once per game.)

    Formal spec:
      - Passive (cost=0)
      - on_summon: register MINION_BOUGHT listener
      - On MINION_BOUGHT: if target has battlecry, increment counter.
        At 5: AddToHand(Brann) and stop counting (once per game).
      - Brann card_id: "BG26_150" (Brann Bronzebeard BG card)

    Test: buy 5 Battlecry minions → get Brann.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _BattleBrandAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero
                self.count = 0
                self.done = False

            def do(self, source_ent, game_ref, target=None):
                if self.done:
                    return
                bought = target
                if bought.battlecry is not None:
                    self.count += 1
                if self.count >= 5:
                    self.done = True
                    game_ref.queue_action(AddToHand(self.hero, "TB_BaconUps_045"))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BattleBrandAction(source),
        ))


class BuyInsectScript:
    """Passive: After you buy 16 cards, get Sulfuras. (16 left!)

    Sulfuras (TB_BaconShop_HP_087t): At the end of your turn,
    give your left- and right-most minions +4/+4.

    Formal spec:
      - Phase 1 (counter): MINION_BOUGHT decrements 16→0.
        When 0: set sulfuras_active=True.
      - Phase 2 (EOT): RECRUIT_END listener guarded by sulfuras_active flag.
        EOT: Buff(leftmost, +4/+4) + Buff(rightmost, +4/+4).

    Test: buy 16 cards → Sulfuras active → end turn → left/right buffed.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _BuyInsectAction(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero
                self.remaining = 16
                self.sulfuras_active = False

            def do(self, source_ent, game_ref, target=None):
                if self.sulfuras_active:
                    return  # already active, phase 1 done
                if self.remaining > 0:
                    self.remaining -= 1
                if self.remaining <= 0:
                    self.sulfuras_active = True

        # EOT Sulfuras effect
        class _SulfurasEOTAction(Action):
            def __init__(self, tracker):
                super().__init__()
                self.tracker = tracker

            def do(self, source_ent, game_ref, target=None):
                if not self.tracker.sulfuras_active:
                    return
                board = self.tracker.hero.get_board_minions()
                living = [m for m in board if not m.dead]
                if not living:
                    return
                leftmost = living[0]
                rightmost = living[-1]
                game_ref.queue_action(Buff(leftmost, atk=4, health=4))
                if leftmost != rightmost:
                    game_ref.queue_action(Buff(rightmost, atk=4, health=4))

        tracker = _BuyInsectAction(source)
        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=tracker,
        ))
        game.register_listener(source, EventListener(
            event_name="RECRUIT_END",
            action=_SulfurasEOTAction(tracker),
        ))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 16 — Additional simple hero powers
# ═══════════════════════════════════════════════════════════════════════════

class MajorHymnScript:
    """Hero Power: Give a minion Attack equal to your Tier.

    Formal spec:
      - Cost: from HERO_POWER_COST tag
      - Buff random friendly minion: +(player.tavern_tier) Attack
      - Return None if board is empty

    Test: at tier 3, use hero power → random minion gets +3 Attack.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=source.tavern_tier, health=0)


class MinorHymnScript:
    """Hero Power: Give a minion Health equal to your Tier.

    Formal spec:
      - Cost: from HERO_POWER_COST tag
      - Buff random friendly minion: +(player.tavern_tier) Health
      - Return None if board is empty

    Test: at tier 3, use hero power → random minion gets +3 Health.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None
        target = random.choice(board)
        return Buff(target, atk=0, health=source.tavern_tier)


class IronforgeScript:
    """Hero Power: In 2 turns, gain 2 Gold. (Then +1 turn!)

    Formal spec:
      - Cost: from HERO_POWER_COST tag
      - Register a RECRUIT_BEGIN listener with 2-turn countdown
      - After 2 turns: GainGold(player, 2)
      - Delayed gold is queued during RECRUIT_BEGIN

    Test: use hero power on turn 3 → turn 5 starts with +2 extra gold.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.events import RECRUIT_BEGIN, EventListener

        class _IronforgeDelayedGold(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
                self.turns_left = 2

            def do(self, source_ent, game_ref, target=None):
                self.turns_left -= 1
                if self.turns_left == 0:
                    game_ref.queue_action(GainGold(self.player, 2))

        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_IronforgeDelayedGold(source),
        ))
        return None


class PiggyBankScript:
    """Hero Power: Gain 1 Gold. Increases by 1 each turn. (Once per game!)

    Formal spec:
      - Cost: 1 gold
      - on_summon: initialize PIGGY_BANK_COUNTER=0, register RECRUIT_BEGIN listener
      - Each RECRUIT_BEGIN: increment counter by 1 (until used)
      - hero_power: gain gold = counter, then set counter to -1 (used flag)
      - If counter < 0: already used, return None

    Test: turn 1 use → gain 1 gold; turn 3 use → gain 3 gold; cannot use again.
    """

    @staticmethod
    def on_summon(source, game):
        source.set_tag(GameTag.PIGGY_BANK_COUNTER, 0)
        from hsrl.core.events import RECRUIT_BEGIN, EventListener

        class _PiggyGrowth(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player

            def do(self, source_ent, game_ref, target=None):
                counter = self.player.get_tag(GameTag.PIGGY_BANK_COUNTER, 0)
                if counter >= 0:  # Negative means already used
                    self.player.set_tag(GameTag.PIGGY_BANK_COUNTER, counter + 1)

        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_PiggyGrowth(source),
        ))

    @staticmethod
    def hero_power(source, game):
        counter = source.get_tag(GameTag.PIGGY_BANK_COUNTER, 0)
        if counter < 0:
            return None  # Already used this game
        if counter == 0:
            counter = 1  # First turn: give at least 1 gold
        source.set_tag(GameTag.PIGGY_BANK_COUNTER, -1)  # Mark as used
        return GainGold(source, counter)


HERO_POWER_SCRIPT_REGISTRY = {
    # Example hero powers
    "EXAMPLE_HERO_POWER_BUFF": ExampleHeroPowerBuff,
    "EXAMPLE_HERO_POWER_GOLD": ExampleHeroPowerGold,
    "EXAMPLE_HERO_POWER_MULTI": ExampleHeroPowerMulti,
    "EXAMPLE_HERO_POWER_AURA": ExamplePermanentAura,
    "EXAMPLE_HERO_POWER_SPELL": ExampleSpellDiscover,
    "EXAMPLE_HERO_POWER_FREEZE": ExampleFreezeTavern,
    "EXAMPLE_HERO_POWER_COPY": ExamplePostCombatCopy,
    "EXAMPLE_HERO_POWER_SOC": ExampleStartOfCombat,
    # Real hero powers — ACTIVE
    "BG20_HERO_100p": GloryOfCombatScript,
    "BG20_HERO_101p": SeeTheLightScript,
    "BG20_HERO_103p": BloodboundScript,
    "BG21_HERO_000p": ConvictionScript,
    "BG21_HERO_010p": ISpyScript,
    "BG28_HERO_400p": LuckyRollScript,
    "TB_BaconShop_HP_001": SharpenBladesScript,
    "TB_BaconShop_HP_008": SmartSavingsScript,
    "TB_BaconShop_HP_010": BoonOfLightScript,
    "TB_BaconShop_HP_015": TinkerScript,
    "TB_BaconShop_HP_028": TemporalTavernScript,
    "TB_BaconShop_HP_040": BrickByBrickScript,
    "TB_BaconShop_HP_047": LeadExplorerScript,
    "TB_BaconShop_HP_049": GraveyardShiftScript,
    "TB_BaconShop_HP_064": QueenOfDragonsScript,
    "TB_BaconShop_HP_077": BobsBurglesScript,
    "BG23_HERO_305p": ThePerfectCrimeScript,
    "BG23_HERO_306p": ReclaimedSoulsScript,
    "BG32_HERO_001p": WisdomOfAncientsScript,
    "TB_BaconShop_HP_102": ThreeWishesScript,
    "TB_BaconShop_HP_103": EmbraceYourRageScript,
    "TB_BaconShop_HP_104": SaturdayCThunsScript,
    "TB_BaconShop_HP_702t": RuneOfDamnationScript,
    "TB_BaconShop_HP_036": BloodfuryScript,
    # Phase IV — Spell Discover, Freeze, Post-Combat Copy
    "BG23_HERO_304p": RelicsOfTheDeepScript,
    "TB_BaconShop_HP_011": GalakrondsGreedScript,
    "TB_BaconShop_HP_053": IllTakeThatScript,
    "TB_BaconShop_HP_014": StayFrostyScript,
    # Phase V — Dig Counter, Type Rotation
    "EXAMPLE_HERO_POWER_DIG": ExampleDigCounter,
    "EXAMPLE_HERO_POWER_ROTATION": ExampleTypeRotation,
    "TB_BaconShop_HP_074": BuriedTreasureScript,
    "TB_BaconShop_HP_041": TaleOfKingsScript,
    # Phase VI — SOC Passive, GlobalAura, Simple Passives
    "EXAMPLE_HERO_POWER_SOC": ExampleStartOfCombat,
    "TB_BaconShop_HP_061": AllWillBurnScript,
    "TB_BaconShop_HP_066": VerdantSpheresScript,
    "TB_BaconShop_HP_038": BananaramaScript,
    # Phase VIb — SoC Keyword, TAVERN_UPGRADED, SoC Per-Type Buff
    "TB_BaconShop_HP_086": SwattingInsectsScript,
    "TB_BaconShop_HP_082": EverbloomScript,
    "TB_BaconShop_HP_037a": WaxWarbandScript,
    # Phase VIc — MINION_SOLD counter
    "TB_BaconShop_HP_056": GoneFishingScript,
    # Phase VId — Simple active hero powers (TempBuff, GainKeyword, KingOfTribe)
    "TB_BaconShop_HP_018": RagePotionScript,
    "TB_BaconShop_HP_019": DieInsectsScript,
    "TB_BaconShop_HP_024": RebornRitesScript,
    # Phase 11 — Simple active hero powers (Buff + SoC + GetRandom + Discount)
    "TB_BaconShop_HP_051": HonorableWarbandScript,
    "TB_BaconShop_HP_043": NefariousFireScript,
    "TB_BaconShop_HP_027": FireTheCannonsScript,
    "TB_BaconShop_HP_072": PirateParrrrtyScript,
    # Phase 12 — Batch 1: Active (5) + SoC Passive (4) + OnBuy Passive (7)
    "BG22_HERO_007p2": NagaConquestScript,
    "BG28_HERO_801p": BlessingOfTheNineFrogsScript,
    "TB_BaconShop_HP_702": RunicEmpowermentScript,
    "TB_BaconShop_HP_085": TavernLightingScript,
    "TB_BaconShop_HP_017": MurlocKingScript,
    "BG22_HERO_000p": DeadeyeScript,
    "BG22_HERO_000p_t1": DeadeyeScript,
    "BG22_HERO_000p_t2": DeadeyeScript,
    "BG22_HERO_000p_t3": DeadeyeScript,
    "BG22_HERO_000p_t4": DeadeyeScript,
    "BG22_HERO_001p": EmbraceTheElementsScript,
    "BG22_HERO_001p_t1": EmbraceTheElementsScript,
    "BG22_HERO_001p_t2": EmbraceTheElementsScript,
    "BG22_HERO_001p_t3": EmbraceTheElementsScript,
    "BG22_HERO_001p_t4": EmbraceTheElementsScript,
    "BG20_HERO_282p": FragrantPhylacteryScript,
    "TB_BaconShop_HP_069": WingmenScript,
    "BG26_HERO_101p": ImTheCapnNowScript,
    "BG20_HERO_102p": ForTheHordeScript,
    "BG20_HERO_242p": NaturalBalanceScript,
    "BG20_HERO_280p5": GlaiveRicochetScript,
    "BG31_HERO_802p": WarpGateScript,
    "TB_BaconShop_HP_048": BattleBrandScript,
    "TB_BaconShop_HP_087": BuyInsectScript,
    "TB_BaconShop_HP_087t": BuyInsectScript,
    # Phase 16 — Additional simple hero powers
    "BG26_HERO_102p": MajorHymnScript,
    "BG26_HERO_102p2": MinorHymnScript,
    "BG28_HERO_400p2": LuckyRollScript,
    "BG20_HERO_283p_t2": IronforgeScript,
    "TB_BaconShop_HP_076": PiggyBankScript,
    # King of [Tribe] — 10 tribe-specific buff hero powers
    "TB_BaconShop_HP_041a": _make_king_script(Race.BEAST, "Beast"),
    "TB_BaconShop_HP_041b": _make_king_script(Race.MECH, "Mech"),
    "TB_BaconShop_HP_041c": _make_king_script(Race.MURLOC, "Murloc"),
    "TB_BaconShop_HP_041d": _make_king_script(Race.DEMON, "Demon"),
    "TB_BaconShop_HP_041f": _make_king_script(Race.DRAGON, "Dragon"),
    "TB_BaconShop_HP_041g": _make_king_script(Race.PIRATE, "Pirate"),
    "TB_BaconShop_HP_041h": _make_king_script(Race.ELEMENTAL, "Elemental"),
    "TB_BaconShop_HP_041i": _make_king_script(Race.QUILBOAR, "Quilboar"),
    "TB_BaconShop_HP_041j": _make_king_script(Race.NAGA, "Naga"),
    "TB_BaconShop_HP_041k": _make_king_script(Race.UNDEAD, "Undead"),
}
