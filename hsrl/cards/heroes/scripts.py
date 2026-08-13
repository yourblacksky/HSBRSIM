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
    Destroy,
    DiscoverMinion,
    GainDeathrattle,
    GainGold,
    GainKeyword,
    GetRandomMinion,
    GiveKeyword,
    Hit,
    PlayBloodGems,
    Summon,
    TargetedAction,
    Transform,
)
from hsrl.core.actions import TransferStats  # imported lazily in some places
from hsrl.core.enums import CardType, GameTag, Race, Zone


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
        target = game.rng.choice(board)
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
        target = game.rng.choice(board)
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
        target = game.rng.choice(board)
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
        target = game.rng.choice(board)
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

    Note: Currently uses +1/+1 per MINIONS_BOUGHT_THIS_TURN tracking.
    Target is player-chosen during recruit, random in combat.
    """

    @staticmethod
    def hero_power(source, game):
        bought = max(1, source.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0) // 3)

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            return Buff(target, atk=bought, health=bought)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Sharpen Blades — +{bought}/+{bought}")


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
        target = game.rng.choice(candidates)
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
        target = game.rng.choice(targets)
        return Buff(target, atk=1, health=1)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_028: Temporal Tavern (Infinite Toki) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class TemporalTavernScript:
    """Hero Power (1): Refresh the Tavern. Add a minion from a higher Tier."""

    @staticmethod
    def hero_power(source, game):
        game.refresh_tavern(source)
        # Add a minion from a higher tier
        higher_tier = min(source.tavern_tier + 1, 6)
        if game.minion_pool is not None:
            drawn = game.minion_pool.draw(higher_tier, count=1,
                                          min_tier=higher_tier,
                                          race_filter=game.active_tribes)
            for card_id in drawn:
                minion = game.create_minion(card_id)
                if minion is not None:
                    minion.controller = source
                    minion.zone = Zone.TAVERN
                    source.tavern.append(minion)
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
        target = game.rng.choice(board)
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
        target = game.rng.choice(targets)
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
        target = game.rng.choice(tavern_minions)
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
        roll = game.rng.randint(1, 6)
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
            target = game.rng.choice([m for m in board if not m.dead])
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
        target = game.rng.choice(board)
        source.set_tag(GameTag.CTHUN_BUFF_COUNT, count + 1)
        return Buff(target, atk=count, health=count)


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_702t: Rune of Damnation (The Jailer) — cost=1
# ═══════════════════════════════════════════════════════════════════════════

class RuneOfDamnationScript:
    """Hero Power (1): Give a friendly Undead +1/+1.
    Give another friendly minion of a different type +1 Attack.

    Two-stage selection when Undead exists: player first selects Undead target,
    then selects a non-Undead target for the +1 Atk buff.

    Formal spec:
      - Cost: 1 gold
      - Stage 1: Player selects an Undead minion → Buff +1/+1
      - Stage 2: Player selects a non-Undead minion → Buff +1/+0
      - If no non-Undead exists, skip stage 2
      - If no Undead exists, select any minion for +1/+1 only
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

        if undead:
            def undead_filter():
                return [m for m in source.get_board_minions()
                        if m.race in (Race.UNDEAD, Race.ALL)]

            def undead_factory(undead_target):
                others = [m for m in source.get_board_minions()
                          if m is not undead_target
                          and m.race not in (Race.UNDEAD, Race.ALL)]
                if not others:
                    return Buff(undead_target, atk=1, health=1)

                def other_filter():
                    return [m for m in source.get_board_minions()
                            if m is not undead_target
                            and m.race not in (Race.UNDEAD, Race.ALL)]

                def other_factory(other_target):
                    return [Buff(undead_target, atk=1, health=1),
                            Buff(other_target, atk=1, health=0)]

                return TargetedAction(other_filter, other_factory,
                                      label="Rune of Damnation — choose non-Undead")

            return TargetedAction(undead_filter, undead_factory,
                                  label="Rune of Damnation — choose Undead")
        elif non_undead:
            def any_filter():
                return source.get_board_minions()

            def any_factory(target):
                return Buff(target, atk=1, health=1)

            return TargetedAction(any_filter, any_factory,
                                  label="Rune of Damnation — +1/+1 to any minion")

        return None


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

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            board = source.get_board_minions()
            left, right = get_adjacent_minions(board, target)
            actions = [Buff(target, atk=1, health=1)]
            if left:
                actions.append(Buff(left, atk=1, health=1))
            if right:
                actions.append(Buff(right, atk=1, health=1))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Wisdom of Ancients — +1/+1 to target + adjacent")


# ═══════════════════════════════════════════════════════════════════════════
# BG23_HERO_306p: Reclaimed Souls (Sylvanas Windrunner) — cost=2
# ═══════════════════════════════════════════════════════════════════════════

class ReclaimedSoulsScript:
    """Hero Power (2): Remove a friendly minion. Give its stats
    to another friendly minion.

    Two-stage selection: player first selects the donor, then selects
    the receiver from the remaining minions.

    Formal spec:
      - Cost: 2 gold
      - Stage 1: Player selects donor minion
      - Stage 2: Player selects receiver from remaining minions
      - TransferStats: destroy donor, buff receiver by donor's ATK + MAX_HEALTH
      - Return None if board has fewer than 2 minions

    Test: 2 minions (2/3 and 3/2), use hero power → one absorbs the other.
    """

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if len(board) < 2:
            return None

        def donor_filter():
            return source.get_board_minions()

        def donor_factory(donor):
            def receiver_filter():
                return [m for m in source.get_board_minions()
                        if m is not donor and not m.dead]

            if not receiver_filter():
                return None

            def receiver_factory(receiver):
                return TransferStats(donor, receiver)

            return TargetedAction(receiver_filter, receiver_factory,
                                  label="Reclaimed Souls — choose receiver")

        return TargetedAction(donor_filter, donor_factory,
                              label="Reclaimed Souls — choose donor")


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
        pair_id = game.rng.choice(pairs)
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
        target = game.rng.choice(tavern_minions)
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

    Target is player-chosen during recruit, random in combat.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import UpgradeTavernMinionTier

        def filter_fn():
            return [m for m in source.tavern
                    if m.get_tag(GameTag.CARDTYPE, 0) == 1]

        def action_factory(target):
            return UpgradeTavernMinionTier(target, source, freeze_new=True)

        return TargetedAction(filter_fn, action_factory,
                              label="Galakrond's Greed — upgrade tavern minion",
                              target_domain="tavern")


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

    Target is player-chosen during recruit, random in combat.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import FreezeTavernMinion

        def filter_fn():
            return [m for m in source.tavern
                    if m.get_tag(GameTag.CARDTYPE, 0) == 1]

        def action_factory(target):
            return FreezeTavernMinion(target)

        return TargetedAction(filter_fn, action_factory,
                              label="Stay Frosty — freeze tavern minion",
                              target_domain="tavern")


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
        chosen_id = game.rng.choice(candidates)
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
        chosen_id = game.rng.choice(candidates)
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
                        chosen = game.rng.choice(murloc_ids)
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
        board = source.get_board_minions()
        if not board:
            return None

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            return Buff(target, atk=3, health=0, temporary=True)

        return TargetedAction(filter_fn, action_factory,
                              label="Rage Potion — +3 temporary Attack")


class DieInsectsScript:
    """Hero Power (2): Give a friendly minion +8 Attack this turn."""

    @staticmethod
    def hero_power(source, game):
        board = source.get_board_minions()
        if not board:
            return None

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            return Buff(target, atk=8, health=0, temporary=True)

        return TargetedAction(filter_fn, action_factory,
                              label="Die Insects — +8 temporary Attack")


class RebornRitesScript:
    """Hero Power (0): Give a friendly minion Reborn."""

    @staticmethod
    def hero_power(source, game):
        eligible = [m for m in source.get_board_minions()
                    if not m.has_tag(GameTag.REBORN)]
        if not eligible:
            return None

        def filter_fn():
            return [m for m in source.get_board_minions()
                    if not m.has_tag(GameTag.REBORN)]

        def action_factory(target):
            return GainKeyword(target, GameTag.REBORN)

        return TargetedAction(filter_fn, action_factory,
                              label="Reborn Rites — Grant Reborn")


def _make_king_script(race, tribe_name):
    """Factory: create a King of [Tribe] hero power script class.

    Hero Power (2): Give a friendly {tribe_name} +2/+2.
    Target is player-chosen during recruit, random in combat.
    """

    _race = race

    class KingScript:
        """Hero Power (2): Give a friendly {tribe_name} +2/+2."""

        @staticmethod
        def hero_power(source, game):
            targets = [m for m in source.get_board_minions()
                       if m.race in (_race, Race.ALL)]
            if not targets:
                return None

            def filter_fn():
                return [m for m in source.get_board_minions()
                        if m.race in (_race, Race.ALL)]

            def action_factory(target):
                return Buff(target, atk=2, health=2)

            return TargetedAction(filter_fn, action_factory,
                                  label=f"King of {tribe_name} — +2/+2")

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
        chosen = game.rng.choice(spells)
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
        bonus = source.get_tag(GameTag.RUNIC_BUFF_BONUS, 1)

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            return Buff(target, atk=bonus, health=bonus)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Runic Empowerment — +{bonus}/+{bonus}")

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
        return Summon(_hp_player(source), token)

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
    The card_id suffix determines the aim mode:
      - _t1: Aim Left (leftmost enemy)
      - _t2: Aim Low (lowest-health enemy)
      - _t3: Aim High (highest-health enemy)
      - _t4: Aim Right (rightmost enemy)
    The parent power (no suffix) picks randomly at registration.

    Formal spec:
      - Passive (cost=0)
      - Aim Left (t1): SoC → Hit(leftmost enemy, 99)
      - Aim Low (t2): SoC → Hit(lowest-health enemy, 99)
      - Aim High (t3): SoC → Hit(highest-health enemy, 99)
      - Aim Right (t4): SoC → Hit(rightmost enemy, 99)
    """

    _MODE_MAP = {
        "t1": "left",
        "t2": "low",
        "t3": "high",
        "t4": "right",
    }

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
                    target_e = game.rng.choice(enemies)
                game_ref.queue_action(Hit(target_e, 99, source=self.player))

        return _DeadeyeAction

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import START_OF_COMBAT, EventListener
        import random as _random
        # Determine aim mode from hero power card_id suffix
        power_id = source.get_tag(GameTag.HERO_POWER, '')
        mode = "left"  # fallback
        for suffix, aim in DeadeyeScript._MODE_MAP.items():
            if power_id.endswith(suffix):
                mode = aim
                break
        else:
            if not any(power_id.endswith(s) for s in DeadeyeScript._MODE_MAP):
                mode = game.rng.choice(["left", "right", "low", "high"])
        AimAction = DeadeyeScript._make_aim_action(mode)
        game.register_listener(source, EventListener(
            event_name=START_OF_COMBAT,
            action=AimAction(source),
        ))


class EmbraceTheElementsScript:
    """Passive: Choose an Element. SoC: Call upon that element.

    Sub-powers (t1-t4): Earth, Fire, Water, Lightning.
    - t1 (Earth): Give 4 random friendly minions "Deathrattle: Summon a 1/1 Elemental"
    - t2 (Fire): Double leftmost minion's Attack
    - t3 (Water): Give rightmost minion Divine Shield and Taunt
    - t4 (Lightning): Deal 1 damage to 5 random enemies

    The card_id suffix determines the element. Parent power (no suffix) picks randomly.
    """

    TOKEN_ID = "BG22_HERO_001p_t1et"
    _ELEMENT_MAP = {
        "t1": "earth",
        "t2": "fire",
        "t3": "water",
        "t4": "lightning",
    }

    @staticmethod
    def _make_earth_dr():
        from hsrl.core.actions import Summon
        TOKEN_ID = "BG22_HERO_001p_t1et"

        def earth_dr(source, game):
            token = game.create_minion(TOKEN_ID)
            if token is None:
                return None
            return Summon(_hp_player(source), token)

        return earth_dr

    @staticmethod
    def _make_invocation(element):
        class _InvocationAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
                self.element = element

            def do(self, source_ent, game_ref, target=None):
                player = self.player
                if hasattr(player, 'controller') and player.controller is not None:
                    player = player.controller
                board = player.get_board_minions()
                living = [m for m in board if not m.dead]
                if not living:
                    return
                if self.element == "earth":
                    import random as _random
                    targets = game_ref.rng.sample(living, min(4, len(living)))
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
        # Determine element from hero power card_id suffix
        power_id = source.get_tag(GameTag.HERO_POWER, '')
        element = "earth"  # fallback
        for suffix, elem in EmbraceTheElementsScript._ELEMENT_MAP.items():
            if power_id.endswith(suffix):
                element = elem
                break
        else:
            if not any(power_id.endswith(s) for s in EmbraceTheElementsScript._ELEMENT_MAP):
                element = game.rng.choice(["earth", "fire", "water", "lightning"])
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
        for m in _hp_player(source).get_board_minions():
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
                    chosen_id = game.rng.choice(self.tracker.bought_ids)
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

        # Protoss minion card IDs (Warp Gate pool)
        _PROTOSS_BASE_IDS = [
            "BG31_HERO_802pt",   # Colossus
            "BG31_HERO_802pt1",  # Carrier
            "BG31_HERO_802pt4",  # Immortal
            "BG31_HERO_802pt5",  # Void Ray
            "BG31_HERO_802pt7",  # Mothership
        ]
        protoss_ids = [cid for cid in _PROTOSS_BASE_IDS
                       if cid in CARDS._cards
                       and CARDS._cards[cid].cardtype == 0]  # CardType.MINION
        if not protoss_ids:
            protoss_ids = ["BG31_HERO_802pt"]  # fallback: Colossus

        # Pick 2 random, then pick 1
        candidates = game.rng.sample(protoss_ids, min(2, len(protoss_ids)))
        chosen = game.rng.choice(candidates)

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
        tier = source.tavern_tier

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            return Buff(target, atk=tier, health=0)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Major Hymn — +{tier} Attack")


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
        tier = source.tavern_tier

        def filter_fn():
            return source.get_board_minions()

        def action_factory(target):
            return Buff(target, atk=0, health=tier)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Minor Hymn — +{tier} Health")


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


# ═══════════════════════════════════════════════════════════════════════════════
# Generic Simple Hero Power Scripts
# ═══════════════════════════════════════════════════════════════════════════════════

def _hp_player(source):
    """Get the Player from a hero power source. Works whether source is a
    Player entity (from start_game) or a hero BaseEntity (from trinket events)."""
    return source if source.controller is None else source.controller


class StartWithMinionScript:
    """Passive: Start with a specific minion token on board."""
    MINION_ID = "EXAMPLE_VANILLA"

    @staticmethod
    def on_summon(source, game):
        player = _hp_player(source)
        minion = game.create_minion(source.data.scripts.MINION_ID)
        if minion:
            return Summon(player, minion)
        return None


class AmalgamStartScript(StartWithMinionScript):
    MINION_ID = "BG30_102"  # One-Amalgam Tour Group


class FishOfNZothStartScript(StartWithMinionScript):
    MINION_ID = "BG30_200"  # Fish of N'Zoth


class StartWithMoreHealthScript:
    """Passive: Start with more health."""
    BONUS_HEALTH = 15

    @staticmethod
    def on_summon(source, game):
        p = _hp_player(source)
        p.set_tag(GameTag.BASE_HEALTH, p.get_tag(GameTag.BASE_HEALTH, 30) + source.data.scripts.BONUS_HEALTH)
        p.set_tag(GameTag.HEALTH, p.max_health)
        return None


class PatchwerkHealthScript(StartWithMoreHealthScript):
    BONUS_HEALTH = 30  # 60 total (30 base + 30 extra)


class MinionsCost2Script:
    """Passive: Minions and Refresh cost (2) Gold. Upgrading the Tavern costs (1) more."""

    @staticmethod
    def on_summon(source, game):
        p = source if source.controller is None else _hp_player(source)
        p.set_tag(GameTag.TAVERN_MINION_COST_OVERRIDE, 2)
        p.set_tag(GameTag.TAVERN_UPGRADE_COST,
                  p.get_tag(GameTag.TAVERN_UPGRADE_COST, 5) + 1)
        return None


class SimpleBuffFriendlyScript:
    """Active: Give a friendly minion +ATK/+HEALTH (and optional keyword)."""
    ATK = 2; HEALTH = 2; KEYWORD = None

    @staticmethod
    def hero_power(player, game):
        # Find the actual script class from the hero power data
        hp_cls = player.data.scripts
        atk = getattr(hp_cls, 'ATK', 2)
        health = getattr(hp_cls, 'HEALTH', 2)
        keyword = getattr(hp_cls, 'KEYWORD', None)

        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        actions = [Buff(target, atk=atk, health=health)]
        if keyword:
            actions.append(GainKeyword(target, keyword))
        return actions


class BuffTavernHeroPowerScript:
    """Active: Give minions in the Tavern +ATK/+HEALTH."""
    ATK = 1; HEALTH = 1

    @staticmethod
    def hero_power(player, game):
        hp_cls = player.data.scripts
        atk = getattr(hp_cls, 'ATK', 1)
        health = getattr(hp_cls, 'HEALTH', 1)
        return BuffTavern(player, atk=atk, health=health)


class DiscoverPrizeHeroPowerScript:
    """Active: Discover a Darkmoon Prize."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import DiscoverPrize
        return DiscoverPrize(player)


class MakeMinionGoldenScript:
    """Active: Make a friendly minion Golden (once per game)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead and not m.is_golden]
        if not board:
            return None
        target = game.rng.choice(board)
        target.set_tag(GameTag.GOLDEN, True)
        target.set_tag(GameTag.BASE_ATK, target.get_tag(GameTag.BASE_ATK, 0) * 2)
        target.set_tag(GameTag.BASE_HEALTH, target.get_tag(GameTag.BASE_HEALTH, 0) * 2)
        target.set_tag(GameTag.HEALTH, target.max_health)
        # Once per game: set cost to 999 to prevent re-use
        player.set_tag(GameTag.HERO_POWER_COST, 999)
        return None


class AddTribeToTavernScript:
    """Passive: After you Refresh, add a minion of a specific tribe to the tavern."""
    TRIBE = Race.DRAGON

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        tribe = AddTribeToTavernScript.TRIBE

        class _AddAction(Action):
            def do(self, source_ent, game_ref, target=None):
                if game_ref.minion_pool is None:
                    return
                drawn = game_ref.minion_pool.draw(
                    _hp_player(source).tavern_tier, count=1,
                    race_filter=tribe,
                )
                if drawn:
                    for cid in drawn:
                        m = game_ref.create_minion(cid)
                        if m:
                            m.controller = _hp_player(source)
                            m.zone = Zone.TAVERN
                            _hp_player(source).tavern.append(m)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_AddAction(),
            condition=lambda player: player == _hp_player(source),
        ))


class FirstRefreshFreeScript:
    """Passive: Your first Refresh each turn costs (0)."""

    @staticmethod
    def on_summon(source, game):
        p = source if source.controller is None else _hp_player(source)
        p.set_tag(GameTag.FREE_REFRESH_REMAINING,
                  p.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) + 1)
        return None


class ReplaceMinionSameTierScript:
    """Active: Replace a friendly minion with a random one of the same tier."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        tier = target.tech_level
        # A Game owns a snapshot of the card database.  The module-global
        # registry can gain cards after that snapshot was created, which used
        # to let this hero power choose an id that the current game could not
        # instantiate and crash Transform with a None minion.
        pool = [cid for cid, data in game.card_db._cards.items()
                if data.cardtype == CardType.MINION and data.tech_level == tier
                and not cid.startswith("EXAMPLE")]
        if pool:
            return Transform(target, game.rng.choice(pool))
        return None


class AddRandomMinionScript:
    """Active: Add a random minion of a specific tier to your hand."""
    TIER = 1
    COUNT = 1

    @staticmethod
    def hero_power(player, game):
        hp_cls = player.data.scripts
        tier = getattr(hp_cls, 'TIER', 1)
        count = getattr(hp_cls, 'COUNT', 1)
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level == tier
                and not cid.startswith("EXAMPLE")]
        if pool:
            actions = []
            for _ in range(count):
                actions.append(AddToHand(player, game.rng.choice(pool)))
            return actions
        return None


class YoggWheelHeroPowerScript:
    """Active: Spin the Wheel of Yogg-Saron."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.cards.trinkets.scripts import SoTSpinYoggWheelScript
        return SoTSpinYoggWheelScript._spin(player, game)


class DiscoverTier7MinionScript:
    """Active: Discover a Tier 7 minion."""

    @staticmethod
    def hero_power(player, game):
        return DiscoverMinion(player, min_tier=7, max_tier=7)


class BuffFriendlyMechScript:
    """Active: Give a friendly Mech +2/+2."""

    @staticmethod
    def hero_power(player, game):
        mechs = [m for m in player.board if not m.dead and m.race == Race.MECH]
        if not mechs:
            return None
        target = game.rng.choice(mechs)
        return Buff(target, atk=2, health=2)


class RandomKeywordScript:
    """Active: Give a friendly minion a random keyword (DS, Taunt, or Windfury)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        kw = game.rng.choice([GameTag.DIVINE_SHIELD, GameTag.TAUNT, GameTag.WINDFURY])
        return GainKeyword(target, kw)


class RandomMechScript(AddRandomMinionScript):
    """Active: Get a random Mech (tier of tavern)."""
    @staticmethod
    def hero_power(player, game):
        tier = player.tavern_tier
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level <= tier
                and data.tags.get(GameTag.RACE) == Race.MECH
                and not cid.startswith("EXAMPLE")]
        if pool:
            return AddToHand(player, game.rng.choice(pool))
        return None


class OnyxiaBroodmotherScript:
    """Passive: Start of Combat: Summon two 2/1 Whelps."""

    @staticmethod
    def start_of_combat(source, game):
        actions = []
        for _ in range(2):
            token = game.create_minion("BG22_305t")  # Onyxia Whelp
            if token:
                actions.append(Summon(_hp_player(source), token))
        return actions if actions else None


class DiscoverHeroPowerScript:
    """Active: Discover a new Hero Power to replace your current one."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import DiscoverHeroPower
        return DiscoverHeroPower(player)


class DiscoverBuddyScript:
    """Active: Discover a Buddy minion."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import DiscoverBuddy
        return DiscoverBuddy(player)


class EnableQuestsScript:
    """Passive: Quests are enabled for this game."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.QUESTS_ENABLED, True)
        return None


class GainGoldPerTurnScript:
    """Passive: Gain +1 Gold at the start of each turn."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _GainGold(Action):
            def do(self, source_ent, game_ref, target=None):
                game_ref.queue_action(GainGold(_hp_player(source), 1))

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_GainGold(),
            condition=lambda p: p == _hp_player(source),
        ))


class GalewingFlightPathScript:
    """Active: Choose a flight path — free refresh, upgrade discount, or gold.

    Uses ChooseOne action with 3 predefined options. Auto-selects randomly
    in heuristic mode; RL agent selects via PendingChoice.
    """

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import ChooseOne

        choices = [
            ("Free Refresh", GainFreeRefresh(player, 1)),
            ("Upgrade -3", None),  # handled below
            ("Gain 4 Gold", GainGold(player, 4)),
        ]

        # Upgrade discount is a side effect, not an action
        cur = player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)

        def _apply_discount():
            player.set_tag(GameTag.TAVERN_UPGRADE_COST, max(1, cur - 3))

        # Wrap upgrade choice with the discount callback
        class _UpgradeDiscountAction(Action):
            def do(self, source_ent, game_ref, target=None):
                _apply_discount()
        choices[1] = ("Upgrade -3", _UpgradeDiscountAction())

        return ChooseOne(choices)


class SilasDarkmoonScript:
    """Active: Discover a Darkmoon Prize. (2 uses!)"""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import DiscoverPrize
        return DiscoverPrize(player)


class SwapStatsHeroPowerScript:
    """Active: Swap the Attack of two friendly minions (Vol'jin)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if len(board) < 2:
            return None
        a, b = game.rng.sample(board, 2)
        from hsrl.core.actions import SwapStats
        return SwapStats(a, b)


class TriggerLastBattlecryScript:
    """Active: Your last Battlecry triggers again (Shudderwock)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import TriggerBattlecry
        board = [m for m in player.board if not m.dead and m.battlecry]
        if not board:
            return None
        target = game.rng.choice(board)
        return TriggerBattlecry(target)


class DiscoverHigherTierScript:
    """Active: Discover a minion from a higher Tavern Tier (Faelin)."""

    @staticmethod
    def hero_power(player, game):
        return DiscoverMinion(player, min_tier=player.tavern_tier + 1)


class StatsByTierScript:
    """Active: Give a minion stats equal to its Tier (Loh)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        tier = target.tech_level
        return Buff(target, atk=tier, health=tier)


class DevourFriendlyScript:
    """Active: Destroy a friendly minion, gain its stats (Mutanus)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        atk = target.atk
        health = target.max_health
        # Find a random other friendly to gain the stats
        others = [m for m in board if m != target]
        if not others:
            return None
        receiver = game.rng.choice(others)
        return [Destroy(target), Buff(receiver, atk=atk, health=health)]


class ReplaceMinionLowerTierScript:
    """Active: Remove a friendly minion, get a random one of a lower Tier (Hooktusk)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        tier = target.tech_level
        if tier <= 1:
            return None
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level == tier - 1
                and not cid.startswith("EXAMPLE")]
        if pool:
            new_id = game.rng.choice(pool)
            return [Destroy(target), AddToHand(player, new_id)]
        return None


class OnBuyBuffScript:
    """Passive: After you buy a minion, give it +1/+1 (Deryl)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener

        class _BuffBought(Action):
            def do(self, source_ent, game_ref, target=None):
                if target and not target.dead:
                    game_ref.queue_action(Buff(target, atk=1, health=1))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BuffBought(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class BattlecryDoubledScript:
    """Passive: Your Battlecries trigger an extra time (Varden, Brann)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.BATTLECRY_DOUBLED, True)
        return None


class ImproveEachTurnScript:
    """Active: Give +1/+1. Improves each turn (Voone)."""
    BASE_ATK = 1
    BASE_HEALTH = 1

    @staticmethod
    def hero_power(player, game):
        cls = player.data.scripts
        counter = player.get_tag(GameTag.IMPROVE_COUNTER, 0)
        atk = getattr(cls, 'BASE_ATK', 1) + counter
        health = getattr(cls, 'BASE_HEALTH', 1) + counter
        player.set_tag(GameTag.IMPROVE_COUNTER, counter + 1)
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        return Buff(target, atk=atk, health=health)


class ChenvaalaFreeRefreshScript:
    """Passive: After playing 3 Elementals, next Refresh costs (0) (Chenvaala)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import ELEMENTAL_PLAYED, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountElementals(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 3:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    _hp_player(source).set_tag(GameTag.FREE_REFRESH_REMAINING,
                        _hp_player(source).get_tag(GameTag.FREE_REFRESH_REMAINING, 0) + 1)
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=ELEMENTAL_PLAYED,
            action=_CountElementals(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class ArannaRefreshCounterScript:
    """Passive: After 5 Refreshes, Bob always offers 7 minions (Aranna)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountRefreshes(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)
                if c >= 5:
                    _hp_player(source).set_tag(GameTag.ARANNA_ALWAYS_7, True)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_CountRefreshes(),
            condition=lambda player: player == _hp_player(source),
        ))


class EoTDoubledScript:
    """Passive: Your End of Turn effects trigger twice (Clocksworth, Drakkari)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.END_OF_TURN_DOUBLED, True)
        return None


class IniStormcoilScript:
    """Passive: After 9 friendly minions die, get a random Mech (Ini Stormcoil)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import DEATH, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountDeaths(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 9:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    from hsrl.core.card_db import CARDS
                    mechs = [cid for cid, data in CARDS._cards.items()
                             if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.MECH
                             and not cid.startswith("EXAMPLE")]
                    if mechs and len(_hp_player(source).hand) < 10:
                        game_ref.queue_action(AddToHand(_hp_player(source), game.rng.choice(mechs)))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_CountDeaths(),
            condition=lambda m, killer=None: m.controller == _hp_player(source),
        ))


class EnhanceOMechanoScript:
    """Passive: After each Refresh, give a minion in the Tavern a random Keyword (Enhance-o)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _BuffTavern(Action):
            def do(self, source_ent, game_ref, target=None):
                minions = [m for m in _hp_player(source).tavern
                           if not m.dead and m.get_tag(GameTag.CARDTYPE, 0) == 1]
                if not minions:
                    return
                target = game.rng.choice(minions)
                kw = game.rng.choice([GameTag.DIVINE_SHIELD, GameTag.TAUNT,
                                       GameTag.WINDFURY, GameTag.REBORN])
                game_ref.queue_action(GainKeyword(target, kw))

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_BuffTavern(),
            condition=lambda player: player == _hp_player(source),
        ))


class GreyboughCombatBuffScript:
    """Passive: Give +1/+2 and Taunt to minions you summon during combat (Greybough)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import SUMMON, EventListener

        class _BuffCombatSummon(Action):
            def do(self, source_ent, game_ref, target=None):
                if not game_ref.in_combat:
                    return
                if target is None or target.dead:
                    return
                if target.controller != _hp_player(source):
                    return
                game_ref.queue_action(Buff(target, atk=1, health=2))
                game_ref.queue_action(GainKeyword(target, GameTag.TAUNT))

        game.register_listener(source, EventListener(
            event_name=SUMMON,
            action=_BuffCombatSummon(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class ChenvaalaUpgradeScript:
    """Passive: After you play 3 Elementals, reduce Upgrade cost by (3) (Chenvaala)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import ELEMENTAL_PLAYED, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountElementals(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 3:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    cur = _hp_player(source).get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
                    _hp_player(source).set_tag(GameTag.TAVERN_UPGRADE_COST, max(1, cur - 3))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=ELEMENTAL_PLAYED,
            action=_CountElementals(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class VoljinTempSwapScript:
    """Active: Choose 2 minions. They gain each other's Attack until next turn (Vol'jin)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if len(board) < 2:
            return None
        a, b = game.rng.sample(board, 2)
        a_atk, b_atk = a.atk, b.atk
        # Apply temporary buffs: a gets b's attack, b gets a's attack
        # Buff(a, atk=b_atk - a_atk) — diff gives the swap
        return [
            Buff(a, atk=b_atk - a_atk, health=0, temporary=True),
            Buff(b, atk=a_atk - b_atk, health=0, temporary=True),
        ]


class MutanusSellScript:
    """Active: Sell a friendly minion. Give its stats to another (Mutanus)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if len(board) < 2:
            return None
        target = game.rng.choice(board)
        others = [m for m in board if m != target]
        receiver = game.rng.choice(others)
        atk = target.atk
        health = target.max_health
        # Sell: remove from board, gain 1 gold, give stats to receiver
        game.remove_from_board(target)
        target.zone = Zone.GRAVEYARD
        return [GainGold(player, 1), Buff(receiver, atk=atk, health=health)]


class ArannaFirstFreeScript:
    """Passive: The first minion you buy each turn is free (Aranna)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
        from hsrl.core.events import TURN_BEGIN, MINION_BOUGHT, EventListener

        class _ResetFlag(Action):
            def do(self, source_ent, game_ref, target=None):
                _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _TrackBuy(Action):
            def do(self, source_ent, game_ref, target=None):
                _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 1)

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN, action=_ResetFlag(),
            condition=lambda p: p == _hp_player(source),
        ))
        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT, action=_TrackBuy(),
            condition=lambda minion, player: player == _hp_player(source),
        ))
        # Set first minion cost to 0
        _hp_player(source).set_tag(GameTag.TAVERN_MINION_COST_OVERRIDE, 0)


class VooneCopyScript:
    """Passive: At the end of every 3 turns, get a copy of left-most card in hand (Voone)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
        from hsrl.core.events import TURN_END, EventListener

        class _CopyLeftmost(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 3:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    hand = _hp_player(source).hand
                    if hand and len(hand) < 10:
                        leftmost = hand[0]
                        cid = leftmost.get_tag(GameTag.CARD_ID)
                        if cid:
                            game_ref.queue_action(AddToHand(_hp_player(source), cid))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TURN_END,
            action=_CopyLeftmost(),
            condition=lambda turn: True,
        ))


class TickatusPrizeScript:
    """Passive: Every 4 turns, Discover a Darkmoon Prize (Tickatus)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
        from hsrl.core.events import TURN_END, EventListener

        class _DiscoverPrize(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 4:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    from hsrl.core.actions import DiscoverPrize
                    game_ref.queue_action(DiscoverPrize(_hp_player(source)))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TURN_END,
            action=_DiscoverPrize(),
            condition=lambda turn: True,
        ))


class SneedShredderScript:
    """Passive: Start with a 2/1 Shredder (Sneed)."""

    @staticmethod
    def on_summon(source, game):
        token = game.create_minion("BG21_030t")  # Sneed's Shredder
        if token is None:
            token = game.create_minion("EXAMPLE_VANILLA")
            if token:
                token.set_tag(GameTag.BASE_ATK, 2)
                token.set_tag(GameTag.BASE_HEALTH, 1)
                token.set_tag(GameTag.HEALTH, 1)
        if token and len(_hp_player(source).board) < 7:
            return Summon(_hp_player(source), token)
        return None


class GalewingSpellScript:
    """Passive: In 1 turn, get a random 1-Cost Tavern spell (Galewing)."""

    @staticmethod
    def on_summon(source, game):
        def _get_spell(g, t):
            p = _hp_player(source)
            if not p.is_alive:
                return
            from hsrl.core.card_db import CARDS
            spells = [cid for cid, data in CARDS._cards.items()
                      if data.cardtype == 3 and data.tech_level == 1
                      and not cid.startswith("EXAMPLE")]
            if spells and len(p.hand) < 10:
                g.queue_action(AddToHand(p, game.rng.choice(spells)))
            # Schedule again for next turn
            g.schedule_turn_action(g.turn + 1,
                lambda g2, t2: _get_spell(g2, t2))

        game.schedule_turn_action(2, _get_spell)
        return None


class DrekTharCombatScript:
    """Passive: In combat when space, summon copy of highest-Attack minion. T7 (Drek'Thar)."""

    @staticmethod
    def start_of_combat(source, game):
        if game.turn < 7:
            return None
        board = [m for m in _hp_player(source).board if not m.dead]
        if not board or len(board) >= 7:
            return None
        highest = max(board, key=lambda m: m.atk)
        copy_minion = game.create_minion(highest.get_tag(GameTag.CARD_ID))
        if copy_minion:
            return Summon(_hp_player(source), copy_minion)
        return None


class VanndarCombatScript:
    """Passive: In combat when space, summon copy of highest-Health minion. T7 (Vanndar)."""

    @staticmethod
    def start_of_combat(source, game):
        if game.turn < 7:
            return None
        board = [m for m in _hp_player(source).board if not m.dead]
        if not board or len(board) >= 7:
            return None
        highest = max(board, key=lambda m: m.max_health)
        copy_minion = game.create_minion(highest.get_tag(GameTag.CARD_ID))
        if copy_minion:
            return Summon(_hp_player(source), copy_minion)
        return None


class OnyxiaAvengeScript:
    """Passive: Avenge (4): Summon a 1/1 Whelp that attacks immediately (Onyxia)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import AVENGE_TRIGGER, EventListener

        class _SummonWhelp(Action):
            def do(self, source_ent, game_ref, target=None):
                if len(_hp_player(source).board) >= 7:
                    return
                token = game_ref.create_minion("BG22_305t")  # Onyxia Whelp
                if token is None:
                    token = game_ref.create_minion("EXAMPLE_VANILLA")
                    if token:
                        token.set_tag(GameTag.BASE_ATK, 1)
                        token.set_tag(GameTag.BASE_HEALTH, 1)
                if token:
                    game_ref.queue_action(Summon(_hp_player(source), token))

        game.register_listener(source, EventListener(
            event_name=AVENGE_TRIGGER,
            action=_SummonWhelp(),
        ))


class CookiePotScript:
    """Active: Throw a minion in your pot. At 3, Discover from their types (Cookie)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        # Remove target and track its type
        tribe = target.race
        game.remove_from_board(target)
        target.zone = Zone.GRAVEYARD
        # Count pot
        c = player.get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
        if c >= 3:
            player.set_tag(GameTag.IMPROVE_COUNTER, 0)
            from hsrl.core.actions import DiscoverMinion
            return DiscoverMinion(player, race=tribe if tribe not in (Race.NONE, Race.ALL) else None)
        player.set_tag(GameTag.IMPROVE_COUNTER, c)
        return None


class MarinTrinketScript:
    """Passive: On Turn 5, choose a Lesser Trinket to buy (Marin)."""

    @staticmethod
    def on_summon(source, game):
        def _on_turn5(g, t):
            p = _hp_player(source)
            if p.is_alive:
                from hsrl.core.actions import DiscoverTrinket
                g.queue_action(DiscoverTrinket(p, lesser_only=True))

        game.schedule_turn_action(5, _on_turn5)
        return None


class TeronMarkScript:
    """Active: Choose a friendly minion. SoC: Destroy it, resummon when space (Teron)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        target._teron_marked = True
        target._teron_cid = target.get_tag(GameTag.CARD_ID)
        return None

    @staticmethod
    def start_of_combat(source, game):
        board = [m for m in _hp_player(source).board
                 if not m.dead and getattr(m, '_teron_marked', False)]
        if not board:
            return None
        target = board[0]
        cid = getattr(target, '_teron_cid', None)
        target._teron_marked = False
        actions = [Destroy(target)]
        if cid:
            copy_minion = game.create_minion(cid)
            if copy_minion:
                actions.append(Summon(_hp_player(source), copy_minion))
        return actions


class MaievLockScript:
    """Active: Choose a card in the Tavern to lock in hand. After 2 turns, unlock (Maiev)."""

    @staticmethod
    def hero_power(player, game):
        cards = [m for m in player.tavern if not m.dead]
        if not cards:
            return None
        target = game.rng.choice(cards)
        cid = target.get_tag(GameTag.CARD_ID)
        # Remove from tavern, store for later
        player.tavern.remove(target)
        target.zone = Zone.GRAVEYARD
        player.set_tag(GameTag.IMPROVE_COUNTER, 2)  # 2 turns remaining
        player._maiev_card = cid
        return None

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _CheckMaiev(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0)
                if c <= 0:
                    return
                c -= 1
                if c <= 0:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    cid = getattr(_hp_player(source), '_maiev_card', None)
                    if cid and len(_hp_player(source).hand) < 10:
                        game_ref.queue_action(AddToHand(_hp_player(source), cid))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_CheckMaiev(),
            condition=lambda p: p == _hp_player(source),
        ))


class ThorimGoldScript:
    """Passive: Start: Discover T7. Get after spending 60 Gold (Thorim)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import DiscoverMinion
        from hsrl.core.events import GOLD_SPENT, EventListener

        p = _hp_player(source)
        p.set_tag(GameTag.IMPROVE_COUNTER, 0)
        game.queue_action(DiscoverMinion(p, min_tier=7, max_tier=7))
        # Store amount in a mutable container for the closure
        _last_amount = [0]

        class _TrackGold(Action):
            def do(self, source_ent, game_ref, target=None):
                spent = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0)
                spent += _last_amount[0]
                if spent >= 60:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    game_ref.queue_action(DiscoverMinion(_hp_player(source), min_tier=7, max_tier=7))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, spent)

        def _condition(player, amount):
            _last_amount[0] = amount
            return player == _hp_player(source)

        game.register_listener(source, EventListener(
            event_name=GOLD_SPENT,
            action=_TrackGold(),
            condition=_condition,
        ))


class JimRaynorScript:
    """Passive: Start with 2/2 Battlecruiser. Refresh→add Upgrade (Jim Raynor)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        # Summon Battlecruiser
        token = game.create_minion("BG31_801t")
        if token is None:
            token = game.create_minion("EXAMPLE_VANILLA")
            if token:
                token.set_tag(GameTag.BASE_ATK, 2)
                token.set_tag(GameTag.BASE_HEALTH, 2)
        if token and len(_hp_player(source).board) < 7:
            game.queue_action(Summon(_hp_player(source), token))

        class _AddUpgrade(Action):
            def do(self, source_ent, game_ref, target=None):
                from hsrl.core.card_db import CARDS
                spells = [cid for cid, data in CARDS._cards.items()
                          if data.cardtype == 3 and not cid.startswith("EXAMPLE")]
                if spells and len(_hp_player(source).hand) < 10:
                    game_ref.queue_action(AddToHand(_hp_player(source), game.rng.choice(spells)))

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_AddUpgrade(),
            condition=lambda player: player == _hp_player(source),
        ))


class ClocksworthGoldenScript:
    """Passive: 2 copies→Golden. Golden give Coins instead of Triple Rewards (Clocksworth)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.PIRATES_NEED_2_COPIES, True)
        return None


class DerylHatScript:
    """Passive: When you play a minion, give it +1/+1. Hat passes when sold (Deryl)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_PLAYED, MINION_SOLD, EventListener

        class _GiveHat(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                target.set_tag(GameTag.IMPROVE_COUNTER,
                               target.get_tag(GameTag.IMPROVE_COUNTER, 0) + 1)
                game_ref.queue_action(Buff(target, atk=1, health=1))

        class _PassHat(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is None:
                    return
                hat_count = target.get_tag(GameTag.IMPROVE_COUNTER, 0)
                if hat_count <= 0:
                    return
                board = [m for m in _hp_player(source).board if not m.dead]
                if not board:
                    return
                receiver = game.rng.choice(board)
                receiver.set_tag(GameTag.IMPROVE_COUNTER,
                                 receiver.get_tag(GameTag.IMPROVE_COUNTER, 0) + hat_count)
                game_ref.queue_action(Buff(receiver, atk=hat_count, health=hat_count))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_GiveHat(),
            condition=lambda minion, player: player == _hp_player(source),
        ))
        game.register_listener(source, EventListener(
            event_name=MINION_SOLD,
            action=_PassHat(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class AlexstraszaDragonScript:
    """Active: Discover a Dragon. (Unlocks at Tier 4.) (Alexstrasza)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.HERO_POWER_COST, 99)
        from hsrl.core.events import TAVERN_UPGRADED, EventListener

        class _UnlockAtT4(Action):
            def do(self, source_ent, game_ref, target=None):
                if _hp_player(source).tavern_tier >= 4:
                    _hp_player(source).set_tag(GameTag.HERO_POWER_COST, 0)

        game.register_listener(source, EventListener(
            event_name=TAVERN_UPGRADED,
            action=_UnlockAtT4(),
            condition=lambda player: player == _hp_player(source),
        ))

    @staticmethod
    def hero_power(player, game):
        return DiscoverMinion(player, race=Race.DRAGON, max_tier=player.tavern_tier)


class FaelinDiscoverScript:
    """Active: Discover a minion from a higher Tavern Tier (Faelin)."""

    @staticmethod
    def hero_power(player, game):
        return DiscoverMinion(player, min_tier=player.tavern_tier + 1)


class BigglesworthDiscoverScript:
    """Passive: After another hero dies, Discover from their warband (Mr. Bigglesworth)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import PLAYER_DEFEATED, EventListener

        class _DiscoverFromDead(Action):
            def do(self, source_ent, game_ref, target=None):
                dead = target
                if dead is None or not hasattr(dead, 'board'):
                    return
                board = [m for m in dead.board if not m.dead]
                if not board:
                    return
                pool = [m.get_tag(GameTag.CARD_ID) for m in board if m.get_tag(GameTag.CARD_ID)]
                if not pool:
                    return
                from hsrl.core.actions import DiscoverMinion
                game_ref.queue_action(DiscoverMinion(_hp_player(source),
                                       card_id_filter=pool))

        game.register_listener(source, EventListener(
            event_name=PLAYER_DEFEATED,
            action=_DiscoverFromDead(),
        ))


class ZerekCloneScript:
    """Active: Once per game, summon an exact copy of a friendly minion (Zerek)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board or len(board) >= 7:
            return None
        target = game.rng.choice(board)
        cid = target.get_tag(GameTag.CARD_ID)
        copy_minion = game.create_minion(cid)
        if copy_minion:
            copy_minion.set_tag(GameTag.BASE_ATK, target.atk)
            copy_minion.set_tag(GameTag.BASE_HEALTH, target.max_health)
            copy_minion.set_tag(GameTag.HEALTH, target.health)
            if target.is_golden:
                copy_minion.set_tag(GameTag.GOLDEN, True)
            # Once per game: set cost to 999
            player.set_tag(GameTag.HERO_POWER_COST, 999)
            return Summon(player, copy_minion)
        return None


class AFKayScript:
    """Passive: Skip first 2 turns. Turn 3: Discover T3 and T4 (A.F. Kay)."""

    @staticmethod
    def on_summon(source, game):
        def _on_turn3(g, t):
            p = _hp_player(source)
            if p.is_alive:
                g.queue_action(DiscoverMinion(p, min_tier=3, max_tier=3))
                g.queue_action(DiscoverMinion(p, min_tier=4, max_tier=4))

        game.schedule_turn_action(3, _on_turn3)
        return None


class LohStatsByTierScript:
    """Active: Give a friendly minion stats equal to its Tier (Loh)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        tier = target.tech_level
        return Buff(target, atk=tier, health=tier)


class OzumatTentacleScript:
    """Passive: When space in combat, summon 2/2 Tentacle with Taunt. +1/+1 on sell (Ozumat)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
        from hsrl.core.events import MINION_SOLD, EventListener

        class _ImproveTentacle(Action):
            def do(self, source_ent, game_ref, target=None):
                _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER,
                    _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1)

        game.register_listener(source, EventListener(
            event_name=MINION_SOLD,
            action=_ImproveTentacle(),
            condition=lambda minion, player: player == _hp_player(source),
        ))

    @staticmethod
    def start_of_combat(source, game):
        if len(_hp_player(source).board) >= 7:
            return None
        bonus = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0)
        token = game.create_minion("EXAMPLE_VANILLA")
        if token:
            token.set_tag(GameTag.BASE_ATK, 2 + bonus)
            token.set_tag(GameTag.BASE_HEALTH, 2 + bonus)
            token.set_tag(GameTag.HEALTH, 2 + bonus)
            token.set_tag(GameTag.TAUNT, True)
            return Summon(_hp_player(source), token)
        return None


class RakanishuSpellBuffScript:
    """Passive: Tavern spells give extra +1/+1. Improves every 4 turns (Rakanishu)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
        from hsrl.core.events import TURN_END, EventListener

        class _ImproveEvery4(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 4:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    cur = _hp_player(source).get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)
                    _hp_player(source).set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, cur + 1)
                    _hp_player(source).set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS,
                        _hp_player(source).get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0) + 1)
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TURN_END,
            action=_ImproveEvery4(),
            condition=lambda turn: True,
        ))
        _hp_player(source).set_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 1)
        _hp_player(source).set_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 1)


class NobundoHandScript:
    """Active: Replace your hand with random minions from a higher Tier (Nobundo)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.card_db import CARDS
        count = len(player.hand)
        for m in list(player.hand):
            player.hand.remove(m)
            m.zone = Zone.GRAVEYARD
        tier = min(player.tavern_tier + 1, 7)
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level == tier
                and not cid.startswith("EXAMPLE")]
        if not pool:
            return None
        actions = []
        for _ in range(min(count, 10)):
            actions.append(AddToHand(player, game.rng.choice(pool)))
        return actions if actions else None


class LordBarovGuessScript:
    """Active: Guess which player wins next combat. Correct→3 Gold (Lord Barov)."""

    @staticmethod
    def hero_power(player, game):
        opponents = [p for p in game.players if p != player and p.is_alive]
        if not opponents:
            return None
        guess = game.rng.choice(opponents)
        player._barov_guess_id = id(guess)
        # Check after combat via listener
        return None

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import COMBAT_END, EventListener

        class _CheckGuess(Action):
            def do(self, source_ent, game_ref, target=None):
                p = _hp_player(source)
                guess_id = getattr(p, '_barov_guess_id', None)
                if guess_id is None:
                    return
                p._barov_guess_id = None
                # Check if guessed player won their combat
                # Use last combat results
                if hasattr(game_ref, '_last_combat_winner'):
                    winner = game_ref._last_combat_winner
                    if winner is not None and id(winner) == guess_id:
                        game_ref.queue_action(GainGold(p, 3))

        game.register_listener(source, EventListener(
            event_name=COMBAT_END,
            action=_CheckGuess(),
        ))


class ETCDiscoverBuddyScript:
    """Active: Discover a Buddy (E.T.C.)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import DiscoverBuddy
        return DiscoverBuddy(player)


class AkazamzarakSecretScript:
    """Active: Choose a Secret. Put it into the battlefield (Akazamzarak).

    Secrets are represented as random spells from a curated pool.
    """

    SECRET_IDS = ["BG28_503", "BG28_504", "BG28_512"]  # Fortify, Recruit, Lasso

    @staticmethod
    def hero_power(player, game):
        cid = game.rng.choice(AkazamzarakSecretScript.SECRET_IDS)
        spell = game.create_spell(cid)
        if spell:
            spell.controller = player
            spell.zone = Zone.HAND
            player.hand.append(spell)
            # Auto-cast if it targets
            on_play = spell.on_play
            if on_play:
                if isinstance(on_play, (list, tuple)):
                    return list(on_play)
                return on_play
        return None


class MurozondTimewarpScript:
    """Passive: On Turn 8, visit the Major Timewarp (Murozond)."""

    @staticmethod
    def on_summon(source, game):
        def _on_turn8(g, t):
            p = _hp_player(source)
            if p.is_alive:
                from hsrl.core.actions import DiscoverTrinket
                g.queue_action(DiscoverTrinket(p, greater_only=True))

        game.schedule_turn_action(8, _on_turn8)
        return None


class MorchieTimewarpScript:
    """Passive: On Turn 5, visit the Minor Timewarp (Morchie)."""

    @staticmethod
    def on_summon(source, game):
        def _on_turn5(g, t):
            p = _hp_player(source)
            if p.is_alive:
                from hsrl.core.actions import DiscoverTrinket
                g.queue_action(DiscoverTrinket(p, lesser_only=True))

        game.schedule_turn_action(5, _on_turn5)
        return None


class SilasTicketScript:
    """Passive: Darkmoon Tickets in Tavern. Get 3→Discover minion of your Tier (Silas)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _AddTicket(Action):
            def do(self, source_ent, game_ref, target=None):
                # Add a Ticket as a special spell in tavern
                ticket = game_ref.create_spell("BG28_503")  # Fortify as ticket proxy
                if ticket and len(_hp_player(source).tavern) < 7:
                    ticket.controller = _hp_player(source)
                    ticket.zone = Zone.TAVERN
                    _hp_player(source).tavern.append(ticket)

        class _CollectTickets(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 3:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    game_ref.queue_action(
                        DiscoverMinion(_hp_player(source),
                                       max_tier=_hp_player(source).tavern_tier))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_AddTicket(),
            condition=lambda player: player == _hp_player(source),
        ))
        # Ticket "collection" happens when buying/playing the ticket spell
        from hsrl.core.events import TAVERN_SPELL_CAST
        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_CollectTickets(),
            condition=lambda spell, player: player == _hp_player(source),
        ))


class AzsharaAttackTrackerScript:
    """Passive: When warband reaches 30 total Attack, begin Naga Conquest (Azshara)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CheckAttack(Action):
            def do(self, source_ent, game_ref, target=None):
                if _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) >= 1:
                    return  # Already triggered
                total_atk = sum(m.atk for m in _hp_player(source).board if not m.dead)
                if total_atk >= 30:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 1)
                    # Naga Conquest: buff all minions
                    for m in _hp_player(source).board:
                        if not m.dead:
                            game_ref.queue_action(Buff(m, atk=5, health=5))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_CheckAttack(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class DenathriusQuestScript:
    """Passive: At start of game, choose one of two Quests (Sire Denathrius)."""

    @staticmethod
    def on_summon(source, game):
        _hp_player(source).set_tag(GameTag.QUESTS_ENABLED, True)
        # Quest selection: auto-pick first available
        from hsrl.core.actions import DiscoverReward
        game.queue_action(DiscoverReward(_hp_player(source)))


class PutricideCraftScript:
    """Active: Discover an Undead minion (Putricide — Build-An-Undead)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.card_db import CARDS
        undead = [cid for cid, data in CARDS._cards.items()
                  if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.UNDEAD
                  and not cid.startswith("EXAMPLE")]
        if undead:
            return DiscoverMinion(player, card_id_filter=undead)
        return None


class KerriganZergScript:
    """Passive: Your minions can transform into higher-Tier Zerg (Kerrigan)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _BuffZerg(Action):
            def do(self, source_ent, game_ref, target=None):
                for m in _hp_player(source).board:
                    if not m.dead and m.get_tag(GameTag.IMPROVE_COUNTER, 0) < 3:
                        game_ref.queue_action(Buff(m, atk=1, health=1))

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_BuffZerg(),
            condition=lambda p: p == _hp_player(source),
        ))


class ButtonsTrinketScript:
    """Passive: On Turn 8, choose a Greater Trinket to buy (Buttons)."""

    @staticmethod
    def on_summon(source, game):
        def _on_turn8(g, t):
            p = _hp_player(source)
            if p.is_alive:
                from hsrl.core.actions import DiscoverTrinket
                g.queue_action(DiscoverTrinket(p, greater_only=True))

        game.schedule_turn_action(8, _on_turn8)
        return None


class JandiceSwapScript:
    """Active: Swap a friendly non-Golden minion with a random one in the Tavern (Jandice)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead and not m.is_golden]
        tavern = [m for m in player.tavern
                  if not m.dead and m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not board or not tavern:
            return None
        friendly = game.rng.choice(board)
        tavern_m = game.rng.choice(tavern)
        player.board.remove(friendly)
        player.tavern.remove(tavern_m)
        friendly.zone = Zone.TAVERN
        tavern_m.zone = Zone.PLAY
        player.tavern.append(friendly)
        player.board.append(tavern_m)
        tavern_m.set_tag(GameTag.FROZEN, True)
        friendly.set_tag(GameTag.FROZEN, True)
        return None


class HooktuskDiscoverScript:
    """Active: Remove a friendly minion. Discover one from a Tier lower (Hooktusk)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        tier = target.tech_level
        if tier <= 1:
            return None
        game.remove_from_board(target)
        target.zone = Zone.GRAVEYARD
        return DiscoverMinion(player, max_tier=tier - 1, min_tier=1)


class SirFinleyDiscoverScript:
    """Passive: At the start of the game, Discover a Hero Power (Sir Finley)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import DiscoverHeroPower

        def _on_start(g, t):
            p = _hp_player(source)
            if p.is_alive:
                g.queue_action(DiscoverHeroPower(p))

        game.schedule_turn_action(1, _on_start)
        return None


class GennTurn4DiscoverScript:
    """Passive: On turn 4, Discover 2 Hero Powers to replace this one (Genn)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.actions import DiscoverHeroPower

        def _on_turn4(g, t):
            p = _hp_player(source)
            if p.is_alive:
                g.queue_action(DiscoverHeroPower(p, count=2))

        game.schedule_turn_action(4, _on_turn4)
        return None


class SimpleBuffTargetedScript:
    """Active: Give a friendly minion +ATK/+HEALTH (Drek'Thar, Vanndar)."""
    ATK = 2; HEALTH = 2

    @staticmethod
    def hero_power(player, game):
        cls = player.data.scripts
        atk = getattr(cls, 'ATK', 2)
        health = getattr(cls, 'HEALTH', 2)
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        return Buff(game.rng.choice(board), atk=atk, health=health)


class MurozondFreeHPScript:
    """Passive: Your first Hero Power each turn costs (0) (Murozond)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _ResetHP(Action):
            def do(self, source_ent, game_ref, target=None):
                _hp_player(source).set_tag(GameTag.HERO_POWER_COST, 0)

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_ResetHP(),
            condition=lambda p: p == _hp_player(source),
        ))


class MorchieTypeBuffScript:
    """Passive: After you play a minion, give minions of that type +1/+1 (Morchie)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener

        class _BuffSameType(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                t_race = target.race
                if t_race in (Race.NONE, Race.ALL, Race.INVALID):
                    return
                for m in _hp_player(source).board:
                    if not m.dead and m.race == t_race:
                        game_ref.queue_action(Buff(m, atk=1, health=1))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_BuffSameType(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class ButtonsCoinScript:
    """Passive: Start with a Coin. After 4 buys, get another Coin (Buttons)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        game.queue_action(GainGold(_hp_player(source), 1))
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountBuys(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 4:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    game_ref.queue_action(GainGold(_hp_player(source), 1))
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_CountBuys(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class ZerekCopyScript:
    """Passive: After you play a minion, add a copy to your hand (Zerek)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener

        class _AddCopy(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is None or target.dead:
                    return
                if len(_hp_player(source).hand) < 10:
                    cid = target.get_tag(GameTag.CARD_ID)
                    game_ref.queue_action(AddToHand(_hp_player(source), cid))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_AddCopy(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class KerriganZergScript:
    """Passive: Start of Turn: Summon two 2/2 Zerglings (Kerrigan)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _SummonZergs(Action):
            def do(self, source_ent, game_ref, target=None):
                if len(_hp_player(source).board) >= 7:
                    return
                for _ in range(2):
                    if len(_hp_player(source).board) < 7:
                        token = game_ref.create_minion("BG31_811t")
                        if token is None:
                            token = game_ref.create_minion("EXAMPLE_VANILLA")
                            if token:
                                token.set_tag(GameTag.BASE_ATK, 2)
                                token.set_tag(GameTag.BASE_HEALTH, 2)
                        if token:
                            game_ref.queue_action(Summon(_hp_player(source), token))

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_SummonZergs(),
            condition=lambda p: p == _hp_player(source),
        ))


class BigglesworthCopyScript:
    """Passive: When an opponent dies, get a copy of their last minion (Mr. Bigglesworth)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import PLAYER_DEFEATED, EventListener

        class _CopyLastMinion(Action):
            def do(self, source_ent, game_ref, target=None):
                dead_player = target
                if dead_player is None or not hasattr(dead_player, 'board'):
                    return
                board = [m for m in dead_player.board if not m.dead]
                if not board and hasattr(dead_player, 'graveyard'):
                    board = dead_player.graveyard[-1:] if dead_player.graveyard else []
                if board:
                    last = board[-1]
                    cid = last.get_tag(GameTag.CARD_ID)
                    if cid and len(_hp_player(source).hand) < 10:
                        game_ref.queue_action(AddToHand(_hp_player(source), cid))

        game.register_listener(source, EventListener(
            event_name=PLAYER_DEFEATED,
            action=_CopyLastMinion(),
        ))


class SneedLegendaryScript:
    """Active: Summon a random Legendary minion (T5+) (Sneed)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level >= 5
                and not cid.startswith("EXAMPLE")]
        if not pool:
            return None
        chosen = game.rng.choice(pool)
        minion = game.create_minion(chosen)
        if minion and len(player.board) < 7:
            return Summon(player, minion)
        return None


class NobundoHandReplaceScript:
    """Active: Replace your hand with random minions from a higher Tier (Nobundo)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.card_db import CARDS
        count = len(player.hand)
        # Clear hand
        for m in list(player.hand):
            player.hand.remove(m)
            m.zone = Zone.GRAVEYARD
        # Add random higher-tier minions
        tier = player.tavern_tier + 1
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level == tier
                and not cid.startswith("EXAMPLE")]
        if not pool:
            pool = [cid for cid, data in CARDS._cards.items()
                    if data.cardtype == 4 and data.tech_level >= tier
                    and not cid.startswith("EXAMPLE")]
        if not pool:
            return None
        actions = []
        for _ in range(min(count, 10)):
            actions.append(AddToHand(player, game.rng.choice(pool)))
        return actions if actions else None


class JandiceSwapScript:
    """Active: Swap a friendly minion with a random minion in the Tavern (Jandice)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        tavern_minions = [m for m in player.tavern
                          if not m.dead and m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not board or not tavern_minions:
            return None
        friendly = game.rng.choice(board)
        tavern_m = game.rng.choice(tavern_minions)
        # Swap: remove friendly from board, add tavern to board, add friendly to tavern
        player.board.remove(friendly)
        player.tavern.remove(tavern_m)
        friendly.zone = Zone.TAVERN
        tavern_m.zone = Zone.PLAY
        player.tavern.append(friendly)
        player.board.append(tavern_m)
        friendly.controller = player
        tavern_m.controller = player
        return None


class TeronResummonScript:
    """Passive: SoC: Destroy lowest-Health minion, resummon exact copy (Teron)."""

    @staticmethod
    def start_of_combat(source, game):
        board = [m for m in _hp_player(source).board if not m.dead]
        if not board:
            return None
        target = min(board, key=lambda m: m.health)
        cid = target.get_tag(GameTag.CARD_ID)
        atk = target.atk
        health = target.health
        actions = [Destroy(target)]
        copy_minion = game.create_minion(cid)
        if copy_minion:
            copy_minion.set_tag(GameTag.BASE_ATK, atk)
            copy_minion.set_tag(GameTag.BASE_HEALTH, health)
            copy_minion.set_tag(GameTag.HEALTH, health)
            if target.golden:
                copy_minion.set_tag(GameTag.GOLDEN, True)
            actions.append(Summon(_hp_player(source), copy_minion))
        return actions


class AzsharaNagaTransformScript:
    """Passive: After you have 3 Naga, transform this HP (Azshara)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountNaga(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is None or target.race != Race.NAGA:
                    return
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)
                if c >= 3:
                    # Transform: give all Naga +2/+2
                    for m in _hp_player(source).board:
                        if not m.dead and m.race == Race.NAGA:
                            game_ref.queue_action(Buff(m, atk=2, health=2))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_CountNaga(),
            condition=lambda minion, player: player == _hp_player(source),
        ))


class MarinTreasureScript:
    """Passive: Gain a random Treasure at start of turn (Marin)."""

    TREASURES = ["BG28_503", "BG28_503", "BG28_504"]  # Fortify, Recruit a Trainee
    # Treasures are similar to small spells/gold bonuses

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _GetTreasure(Action):
            def do(self, source_ent, game_ref, target=None):
                from hsrl.core.card_db import CARDS
                # Pick random spell as treasure proxy
                spells = [cid for cid, data in CARDS._cards.items()
                          if data.cardtype == 3 and data.tech_level <= 3
                          and not cid.startswith("EXAMPLE")]
                if spells and len(_hp_player(source).hand) < 10:
                    game_ref.queue_action(AddToHand(_hp_player(source),
                                          game.rng.choice(spells)))

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_GetTreasure(),
            condition=lambda p: p == _hp_player(source),
        ))


class AkazamzarakSecretScript:
    """Active: Cast a random Secret (Akazamzarak).

    Secrets are represented as random spell casts from a small pool.
    """

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.card_db import CARDS
        spells = [cid for cid, data in CARDS._cards.items()
                  if data.cardtype == 3 and data.tech_level <= 2
                  and not cid.startswith("EXAMPLE")]
        if spells:
            spell_id = game.rng.choice(spells)
            spell = game.create_spell(spell_id)
            if spell:
                spell.controller = player
                return spell.on_play
        return None


class AFKaySkipScript:
    """Passive: Skip first 2 turns. Turn 3: Discover T3 and T4 (A.F. Kay)."""

    @staticmethod
    def on_summon(source, game):
        def _on_turn3(g, t):
            p = _hp_player(source)
            if p.is_alive:
                g.queue_action(DiscoverMinion(p, min_tier=3, max_tier=3))
                g.queue_action(DiscoverMinion(p, min_tier=4, max_tier=4))

        game.schedule_turn_action(3, _on_turn3)
        return None


class ShudderwockBattlecryScript:
    """Active: Trigger a friendly minion's Battlecry. Unlocks on Turn 3 (Shudderwock)."""

    @staticmethod
    def on_summon(source, game):
        # Set high cost to prevent use before turn 3
        _hp_player(source).set_tag(GameTag.HERO_POWER_COST, 99)

        def _unlock_on_turn3(g, t):
            p = _hp_player(source)
            if p.is_alive:
                p.set_tag(GameTag.HERO_POWER_COST, 0)

        game.schedule_turn_action(3, _unlock_on_turn3)
        return None

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead and m.battlecry]
        if not board:
            return None
        from hsrl.core.actions import TriggerBattlecry
        target = game.rng.choice(board)
        return TriggerBattlecry(target)


class VardenRefreshCopyScript:
    """Passive: After the Tavern is Refreshed, copy its highest-Tier minion
    and Freeze them both (Varden — Twice as Nice)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _CopyHighest(Action):
            def do(self, source_ent, game_ref, target=None):
                tavern = _hp_player(source).tavern
                minions = [m for m in tavern if not m.dead
                           and m.get_tag(GameTag.CARDTYPE, 0) == 1]
                if not minions:
                    return
                highest = max(minions, key=lambda m: m.tech_level)
                cid = highest.get_tag(GameTag.CARD_ID)
                if cid and len(tavern) < 7:
                    copy = game_ref.create_minion(cid)
                    if copy:
                        copy.controller = _hp_player(source)
                        copy.zone = Zone.TAVERN
                        tavern.append(copy)
                        highest.set_tag(GameTag.FROZEN, True)
                        copy.set_tag(GameTag.FROZEN, True)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_CopyHighest(),
            condition=lambda player: player == _hp_player(source),
        ))


class TaethelanRelicScript:
    """Passive: Every 4th Tavern spell you buy costs (0) (Tae'thelan)."""

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener
        _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)

        class _CountSpells(Action):
            def do(self, source_ent, game_ref, target=None):
                c = _hp_player(source).get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                if c >= 4:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, 0)
                    _hp_player(source).set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 999)
                else:
                    _hp_player(source).set_tag(GameTag.IMPROVE_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_CountSpells(),
            condition=lambda spell, player: player == _hp_player(source),
        ))


class OthaarArcaneScript:
    """Passive: The next Tavern spell you buy costs (1) less. Unlocks Turn 3 (Othaar)."""

    @staticmethod
    def on_summon(source, game):
        def _unlock_on_turn3(g, t):
            p = _hp_player(source)
            if p.is_alive:
                p.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 1)

        game.schedule_turn_action(3, _unlock_on_turn3)
        return None


class ChromieSpellTavernScript:
    """Active: Refresh the Tavern with Tavern spells instead of minions (Chromie)."""

    @staticmethod
    def hero_power(player, game):
        if game.spell_pool is None:
            return None
        player.tavern.clear()
        tier = player.tavern_tier
        count = {1: 3, 2: 4, 3: 4, 4: 5, 5: 5, 6: 6, 7: 6}.get(tier, 6)
        drawn = game.spell_pool.draw(tier, count=count)
        for card_id in drawn:
            spell = game.create_spell(card_id)
            if spell:
                spell.controller = player
                spell.zone = Zone.TAVERN
                player.tavern.append(spell)
        return None


class LordBarovGuessScript:
    """Active: Guess which player wins next combat. Correct → 3 Gold (Lord Barov)."""

    @staticmethod
    def hero_power(player, game):
        opponents = [p for p in game.players if p != player and p.is_alive]
        if len(opponents) < 1:
            return None
        # Auto-guess: pick a random opponent (in RL, this becomes a PendingChoice)
        guess = game.rng.choice(opponents)
        player._barov_guess = guess
        # Result checked in _check_barov_guess after combat
        return None


class MurlocHolmesGuessScript:
    """Active: Guess which minion your next opponent has. Correct → Coin (Holmes)."""

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.actions import GuessMinion
        return GuessMinion(player)


class MaievDormantScript:
    """Active: Make a minion in the Tavern Dormant. Awakens in 2 turns with +3/+3 (Maiev)."""

    @staticmethod
    def hero_power(player, game):
        tavern_minions = [m for m in player.tavern
                          if not m.dead and not m.get_tag(GameTag.MAIEV_DORMANT, False)
                          and m.get_tag(GameTag.CARDTYPE, 0) == 1]
        if not tavern_minions:
            return None
        target = game.rng.choice(tavern_minions)
        target.set_tag(GameTag.MAIEV_DORMANT, True)
        target.set_tag(GameTag.MAIEV_DORMANT_TURNS, 2)
        return None

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _CheckDormant(Action):
            def do(self, source_ent, game_ref, target=None):
                for m in list(_hp_player(source).tavern):
                    if m.get_tag(GameTag.MAIEV_DORMANT, False):
                        turns = m.get_tag(GameTag.MAIEV_DORMANT_TURNS, 0) - 1
                        if turns <= 0:
                            m.set_tag(GameTag.MAIEV_DORMANT, False)
                            m.set_tag(GameTag.MAIEV_DORMANT_TURNS, 0)
                            # Awaken with +3/+3
                            game_ref.queue_action(Buff(m, atk=3, health=3))
                        else:
                            m.set_tag(GameTag.MAIEV_DORMANT_TURNS, turns)

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_CheckDormant(),
            condition=lambda p: p == _hp_player(source),
        ))


class PutricideCraftScript:
    """Active: Discover an Undead minion (Putricide — Build-An-Undead).

    Crafting = Discover an Undead minion and add it to your hand.
    """

    @staticmethod
    def hero_power(player, game):
        from hsrl.core.card_db import CARDS
        undead_pool = [cid for cid, data in CARDS._cards.items()
                       if data.cardtype == 4 and data.tags.get(GameTag.RACE) == Race.UNDEAD
                       and not cid.startswith("EXAMPLE")]
        if undead_pool:
            return DiscoverMinion(player, card_id_filter=undead_pool)
        return None


class GreyboughBuffScript:
    """Active: Give a friendly minion +1/+2 and Taunt (Greybough)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        target = game.rng.choice(board)
        return [Buff(target, atk=1, health=2), GainKeyword(target, GameTag.TAUNT)]


class OzumatAdjacentBuffScript:
    """Active: Give a friendly +1/+2 and adjacent minions +1/+1 (Ozumat)."""

    @staticmethod
    def hero_power(player, game):
        board = [m for m in player.board if not m.dead]
        if not board:
            return None
        idx = game.rng.randrange(len(board))
        target = board[idx]
        actions = [Buff(target, atk=1, health=2)]
        if idx > 0:
            actions.append(Buff(board[idx - 1], atk=1, health=1))
        if idx < len(board) - 1:
            actions.append(Buff(board[idx + 1], atk=1, health=1))
        return actions


def _make_buff_hp(atk, health, keyword=None):
    """Factory: create a SimpleBuffFriendlyScript subclass with given stats."""
    class _Buff(SimpleBuffFriendlyScript):
        ATK = atk
        HEALTH = health
        KEYWORD = keyword
    _Buff.__name__ = f"_BuffHP_{atk}_{health}"
    return _Buff


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_009: Skilled Bartender (passive — reduce upgrade cost by 1)
# ═══════════════════════════════════════════════════════════════════════════

class SkilledBartenderScript:
    """Passive Hero Power: Reduce the Cost of upgrading the Tavern by (1).

    Formal spec:
      - Cost: 0 (passive)
      - on_summon: reduce TAVERN_UPGRADE_COST by 1, register TAVERN_UPGRADED listener
      - TAVERN_UPGRADED: reduce new upgrade cost by 1
      - hero_power returns None

    Test: game start → upgrade cost = 4. Upgrade to T2 → upgrade cost = 4 (not 5).
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TAVERN_UPGRADED, EventListener

        current = source.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
        source.set_tag(GameTag.TAVERN_UPGRADE_COST, max(0, current - 1))

        class _ReduceNextCost(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                current_cost = self.hero.get_tag(GameTag.TAVERN_UPGRADE_COST, 5)
                self.hero.set_tag(GameTag.TAVERN_UPGRADE_COST, max(0, current_cost - 1))

        game.register_listener(source, EventListener(
            event_name=TAVERN_UPGRADED,
            action=_ReduceNextCost(source),
        ))

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_036t: Nether Portal (passive — get 2 random Demons each turn)
# ═══════════════════════════════════════════════════════════════════════════

class NetherPortalScript:
    """Passive Hero Power: At the start of each turn, get 2 random Demons.

    Formal spec:
      - Cost: 0 (passive)
      - on_summon registers TURN_BEGIN listener
      - TURN_BEGIN: GetRandomMinion(player, race=Race.DEMON) × 2
      - hero_power returns None

    Test: turn begin → 2 Demon minions in hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import TURN_BEGIN, EventListener

        class _AddTwoDemons(Action):
            def __init__(self, hero):
                super().__init__()
                self.hero = hero

            def do(self, source_ent, game_ref, target=None):
                for _ in range(2):
                    GetRandomMinion(self.hero, race=Race.DEMON).do(self.hero, game_ref)

        game.register_listener(source, EventListener(
            event_name=TURN_BEGIN,
            action=_AddTwoDemons(source),
        ))

    @staticmethod
    def hero_power(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_050: Banshee's Blessing (active — remove minion, buff adjacent)
# ═══════════════════════════════════════════════════════════════════════════

class BansheesBlessingScript:
    """Hero Power: Remove a friendly minion. Give adjacent minions +1/+1.

    Formal spec:
      - Cost: active (cost from hero power data)
      - Targets a friendly minion on board
      - Destroy(target)
      - Buff adjacent minions +1/+1
      - Returns None if board empty

    Test: board with 3 minions, use on middle → middle removed, left+right get +1/+1.
    """

    @staticmethod
    def hero_power(source, game):
        from hsrl.core.actions import get_adjacent_minions

        board = source.get_board_minions()
        if not board:
            return None

        def filter_fn():
            return [m for m in board if not m.dead]

        def action_factory(target):
            actions = []
            left, right = get_adjacent_minions(board, target)
            if left and not left.dead:
                actions.append(Buff(left, atk=1, health=1))
            if right and not right.dead:
                actions.append(Buff(right, atk=1, health=1))
            actions.append(Destroy(target))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Banshee's Blessing — remove minion, buff adjacent")


# ═══════════════════════════════════════════════════════════════════════════
# TB_BaconShop_HP_065t2: Spectral Sight (passive — first buy each turn free)
# ═══════════════════════════════════════════════════════════════════════════

class SpectralSightScript:
    """Passive Hero Power: The first minion you buy each turn is free.

    Uses FIRST_MINION_FREE tag (engine already supports this).
    Resets at the start of each turn.

    Formal spec:
      - Cost: 0 (passive)
      - on_summon: set player tag FIRST_MINION_FREE = True
      - hero_power returns None

    Test: first buy each turn costs 0 gold, second buy costs normal cost.
    """

    @staticmethod
    def on_summon(source, game):
        source.set_tag(GameTag.FIRST_MINION_FREE, True)

    @staticmethod
    def hero_power(source, game):
        return None


# ── Registry ──

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
    # ── Verified against official data (hsbattlegrounds.help) ──
    "BG23_HERO_303p2": MurlocHolmesGuessScript,            # Holmes: Look at 2 minions, guess
    "BG34_HERO_001p": ChromieSpellTavernScript,           # Chromie: Refresh with spells
    "TB_BaconShop_HP_063": FirstRefreshFreeScript,       # Nozdormu: 1st refresh free
    "TB_BaconShop_HP_062": AddTribeToTavernScript,       # Ysera: Extra Dragon on refresh
    "TB_BaconShop_HP_046": MakeMinionGoldenScript,       # Reno: Golden once per game
    "TB_BaconShop_HP_035": PatchwerkHealthScript,        # Patchwerk: +30 HP
    "TB_BaconShop_HP_033": AmalgamStartScript,           # Curator: Start with Amalgam
    "TB_BaconShop_HP_105": FishOfNZothStartScript,       # N'Zoth: Start with Fish
    "BG35_HERO_001p": GennTurn4DiscoverScript,            # Genn: Turn 4 Discover 2 HPs
    "TB_BaconShop_HP_054": MinionsCost2Script,           # Millhouse: Minions cost (2)
    "TB_BaconShop_HP_022": ShudderwockBattlecryScript,     # Shudderwock: Trigger BC (T3)
    "BG22_HERO_004p": VardenRefreshCopyScript,            # Varden: Refresh→copy highest+freeze
    "BG31_HERO_006p": OthaarArcaneScript,                 # Othaar: Next spell -1 (T3)
    "BG28_HERO_800p": TaethelanRelicScript,               # Tae'thelan: Every 4th spell free
    "BG22_HERO_200p": IniStormcoilScript,                 # Ini: 9 deaths → random Mech
    "BG24_HERO_204p": EnhanceOMechanoScript,              # Enhance-o: Refresh→keyword tavern
    "TB_BaconShop_HP_107": GreyboughCombatBuffScript,     # Greybough: Combat summon +1/+2 Taunt
    "TB_BaconShop_HP_088": ChenvaalaUpgradeScript,         # Chenvaala: 3 Elementals→upgrade -3
    "BG20_HERO_201p": VoljinTempSwapScript,               # Vol'jin: Temp swap Attack
    "BG20_HERO_301p": MutanusSellScript,                   # Mutanus: Sell, spit stats
    "TB_BaconShop_HP_065": ArannaFirstFreeScript,          # Aranna: First buy free
    "BG26_HERO_104p": VooneCopyScript,                     # Voone: Every 3 turns copy leftmost
    "TB_BaconShop_HP_106": TickatusPrizeScript,            # Tickatus: Every 4 turns Prize
    "TB_BaconShop_HP_057": SirFinleyDiscoverScript,        # Sir Finley: Start of game Discover HP
    "BG21_HERO_030p": SneedShredderScript,                 # Sneed: Start with 2/1 Shredder
    "BG20_HERO_283p": GalewingSpellScript,                 # Galewing: Every turn 1-Cost spell
    "BG22_HERO_002p": DrekTharCombatScript,                # Drek'Thar: SoC copy highest-ATK (T7)
    "BG22_HERO_003p": VanndarCombatScript,                 # Vanndar: SoC copy highest-HP (T7)
    "BG22_HERO_305p": OnyxiaAvengeScript,                 # Onyxia: Avenge(4) summon Whelp
    "BG21_HERO_020p": CookiePotScript,                     # Cookie: Pot collection→discover
    "BG30_HERO_304p": MarinTrinketScript,                  # Marin: Turn 5 Lesser Trinket
    "BG25_HERO_103p": TeronMarkScript,                     # Teron: Mark→SoC destroy+resummon
    "TB_BaconShop_HP_068": MaievLockScript,                # Maiev: Lock tavern card 2 turns
    "BG27_HERO_801p2": ThorimGoldScript,                   # Thorim: T7 discover, after 60G
    "BG31_HERO_801p": JimRaynorScript,                     # Jim Raynor: Battlecruiser+Upgrades
    "BG34_HERO_002p": ClocksworthGoldenScript,             # Clocksworth: 2 copies=Golden
    "TB_BaconShop_HP_042": DerylHatScript,                 # Deryl: Hat on play, passes on sell
    "BG22_HERO_201p": FaelinDiscoverScript,                # Faelin: Discover higher tier
    "TB_BaconShop_HP_080": BigglesworthDiscoverScript,     # Mr. Bigglesworth: Discover from dead
    "TB_BaconShop_HP_052": ReplaceMinionSameTierScript,    # Malygos: Replace same tier (2x/turn)
    "TB_BaconShop_HP_084": JandiceSwapScript,              # Jandice: Swap with tavern minion
    "TB_BaconShop_HP_075": HooktuskDiscoverScript,         # Hooktusk: Remove, Discover lower tier
    "BG20_HERO_202p": DiscoverHeroPowerScript,             # Master Nguyen: Discover new HP
    "BG31_HERO_005p": ZerekCloneScript,                   # Zerek: Once per game clone
    "BG32_HERO_002p": ButtonsTrinketScript,                # Buttons: Turn 8 Greater Trinket
    "TB_BaconShop_HP_044": AFKayScript,                   # A.F. Kay: Skip 2 turns, T3 discover
    "BG33_HERO_001p_ALT": LohStatsByTierScript,            # Loh: Stats = Tier
    "BG23_HERO_201p": OzumatTentacleScript,               # Ozumat: SoC Tentacle + on_sell scale
    "TB_BaconShop_HP_085t": RakanishuSpellBuffScript,      # Rakanishu: Spell buff + every 4 turns improve
    "BG31_HERO_003p": NobundoHandScript,                   # Nobundo: Replace hand higher tier
    "TB_BaconShop_HP_039t": YoggWheelHeroPowerScript,      # Yogg: Spin the Wheel (original impl)
    "TB_BaconShop_HP_081": LordBarovGuessScript,            # Lord Barov: Guess winner→3 Gold
    "BG25_HERO_105p": ETCDiscoverBuddyScript,              # E.T.C.: Discover a Buddy
    "TB_BaconShop_HP_020": AkazamzarakSecretScript,         # Akazamzarak: Choose Secret
    "BG34_HERO_000p": MurozondTimewarpScript,              # Murozond: Turn 8 Major Timewarp
    "BG34_HERO_004p": MorchieTimewarpScript,               # Morchie: Turn 5 Minor Timewarp
    "TB_BaconShop_HP_101": SilasTicketScript,              # Silas: Tickets→Discover
    "BG22_HERO_007p": AzsharaAttackTrackerScript,           # Azshara: 30 Attack→Naga Conquest
    "BG24_HERO_100p": DenathriusQuestScript,               # Denathrius: Choose Quest
    "BG25_HERO_100p": PutricideCraftScript,                 # Putricide: Discover Undead
    "BG31_HERO_811p": KerriganZergScript,                   # Kerrigan: Zerg buffs
    # ── Phase 1 audit: 4 missing hero powers ──
    "TB_BaconShop_HP_009": SkilledBartenderScript,          # Skilled Bartender: -1 upgrade cost
    "TB_BaconShop_HP_036t": NetherPortalScript,             # Nether Portal: 2 Demons/turn
    "TB_BaconShop_HP_050": BansheesBlessingScript,          # Banshee's Blessing: remove→buff adjacent
    "TB_BaconShop_HP_065t2": SpectralSightScript,           # Spectral Sight: first buy free
}
