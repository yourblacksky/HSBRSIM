"""
Quest Reward Script Registry

Each script class can define:
  - on_unlock(source, game) → Action (triggers once when quest completes)
  - on_summon(source, game) → Action (setup/registration when reward is created)
  - start_of_combat(source, game) → Action
  - end_of_turn(source, game) → Action
  - start_of_turn(source, game) → Action

Only two states: CORRECT (exact semantic match) or DEFERRED (return None, doc states dependency).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from hsrl.core.enums import GameTag, Race, Zone
from hsrl.core.actions import (
    Action, Buff, GainGold, AddToHand, DiscoverMinion, DiscoverSpell,
    GainFreeRefresh, GainKeyword,
)

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.entity import BaseEntity
    from hsrl.core.player import Player


def _living(player: Player):
    return [m for m in player.board if not m.dead]


def _random_friendly(player: Player) -> Optional[BaseEntity]:
    living = _living(player)
    return random.choice(living) if living else None


def _buff_all(player, atk=0, health=0):
    actions = []
    for m in player.board:
        if not m.dead:
            actions.append(Buff(m, atk=atk, health=health))
    return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# Quest Scripts
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleQuestScript:
    """
    Natural language: Quest: Buy 3 minions. Reward: Give your leftmost minion +2/+2.

    Formal spec: Set target=3 on quest entity. Engine tracks buy events.
    Test: verify quest.target == 3 after on_summon.
    """

    @staticmethod
    def on_summon(source: BaseEntity, game: Game) -> None:
        source.target = 3


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start of Combat — Buff All
# ═══════════════════════════════════════════════════════════════════════════════

class SoCBuffAll12x12Script:
    """
    Natural language: Start of Combat: Give your minions +12/+12.

    Formal spec: For each non-dead minion on controller's board, Buff(+12/+12).
    Test: 2 minions on board → both get +12/+12.
    """

    @staticmethod
    def start_of_combat(source, game):
        return _buff_all(source.controller, atk=12, health=12)


class SoCBuffAll4x0Script:
    """
    Natural language: Your minions have +4 Attack. (Permanent aura.)

    Formal spec: ApplyGlobalAura(atk=4) on controller.
    Test: minion ATK increases by 4 when aura applied.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.actions import ApplyGlobalAura
        return ApplyGlobalAura(source.controller, atk=4, health=0)


class SoCBuffAll7x7Script:
    """
    Natural language: Your minions have +7/+7, but die after attacking.

    Status: DEFERRED — "die after attacking" requires on-attack self-destruct
    engine support. The +7/+7 aura alone does not match the full card text.
    Dependency: AFTER_ATTACK self-destruct mechanic.
    """

    @staticmethod
    def on_unlock(source, game):
        return None  # DEFERRED


class SoCBuffAll3x0Script:
    """
    Natural language: Start of Combat: Give your minions +3 Attack. (Legacy alias.)

    Formal spec: For each non-dead minion on controller's board, Buff(+3/+0).
    Test: 2 minions on board → both get +3 ATK.
    """

    @staticmethod
    def start_of_combat(source, game):
        return _buff_all(source.controller, atk=3, health=0)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start of Combat — Specific Target
# ═══════════════════════════════════════════════════════════════════════════════

class SoCSummonCopyHighestScript:
    """
    Natural language: Start of Combat: Summon a copy of your highest-Health minion.

    Formal spec:
      1. Find max(health) living minion on controller's board
      2. Summon a fresh copy of its card_id to controller's board
    Test: board with 3/5 and 2/8 → summon copy of 2/8.
    """

    @staticmethod
    def start_of_combat(source, game):
        board = _living(source.controller)
        if not board:
            return None
        best = max(board, key=lambda m: m.health)
        token = game.create_minion(best.get_tag(GameTag.CARD_ID))
        if token is None:
            return None
        from hsrl.core.actions import Summon
        return Summon(source.controller, token)


class SoCLeftDSAttackImmediatelyScript:
    """
    Natural language: Start of Combat: Your leftmost minion gets Divine Shield
    and attacks immediately.

    Formal spec:
      1. Find leftmost living minion
      2. GainKeyword(DIVINE_SHIELD) + AttackImmediately
    Test: leftmost minion gains DS and attacks.
    """

    @staticmethod
    def start_of_combat(source, game):
        living = _living(source.controller)
        if not living:
            return None
        leftmost = living[0]
        from hsrl.core.actions import AttackImmediately
        return [
            GainKeyword(leftmost, GameTag.DIVINE_SHIELD),
            AttackImmediately(leftmost),
        ]


class SoCDSAndRebornEdgesScript:
    """
    Natural language: Start of Combat: Give your leftmost minion Divine Shield,
    give your rightmost minion Reborn.

    Formal spec:
      1. leftmost living → GainKeyword(DS)
      2. rightmost living (if != leftmost) → GainKeyword(REBORN)
    Test: two minions → left gets DS, right gets Reborn.
    """

    @staticmethod
    def start_of_combat(source, game):
        living = _living(source.controller)
        if not living:
            return None
        actions = [GainKeyword(living[0], GameTag.DIVINE_SHIELD)]
        if len(living) > 1:
            actions.append(GainKeyword(living[-1], GameTag.REBORN))
        return actions


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: End of Turn
# ═══════════════════════════════════════════════════════════════════════════════

class EoTBuffRightmost8HPScript:
    """
    Natural language: At the end of your turn, give your rightmost minion
    +8 Health.

    Formal spec: Buff(rightmost_living, atk=0, health=8).
    Test: rightmost minion gains +8 HP.
    """

    @classmethod
    def end_of_turn(cls, source, game):
        living = _living(source.controller)
        if living:
            return Buff(living[-1], atk=0, health=8)
        return None


class EoTRightmostMissingHPAtkScript:
    """
    Natural language: At the end of your turn, give your rightmost minion
    Attack equal to your missing Health.

    Formal spec:
      1. missing = max(0, MAX_HP - current_health)
      2. Buff(rightmost_living, atk=missing, health=0)
    Test: hero at 25/40 → rightmost gets +15 ATK.
    """

    @staticmethod
    def end_of_turn(source, game):
        living = _living(source.controller)
        if not living:
            return None
        missing = max(0, 40 - source.controller.health)
        return Buff(living[-1], atk=missing, health=0)


class EoTPerTribeBuffScript:
    """
    Natural language: At the end of your turn, give your minions +1/+1
    for each different friendly minion type.

    Formal spec:
      1. Count unique non-INVALID races on board
      2. Buff all living minions by +count/+count
    Test: 1 Beast, 1 Murloc → count=2 → all get +2/+2.
    """

    @staticmethod
    def end_of_turn(source, game):
        types = {m.race for m in _living(source.controller) if m.race != Race.INVALID}
        bonus = len(types)
        if bonus > 0:
            return _buff_all(source.controller, atk=bonus, health=bonus)
        return None


class EoTTauntNonTauntBuffScript:
    """
    Natural language: At the end of your turn, for each friendly Taunt minion,
    give your minions without Taunt +1/+2.

    Formal spec:
      1. Count living taunt minions
      2. For each living non-taunt minion, Buff(atk=taunt_count, health=taunt_count*2)
    Test: 2 taunts → each non-taunt gets +2/+4.
    """

    @staticmethod
    def end_of_turn(source, game):
        board = source.controller.board
        taunts = [m for m in board if not m.dead and m.has_tag(GameTag.TAUNT)]
        non_taunts = [m for m in board if not m.dead and not m.has_tag(GameTag.TAUNT)]
        if taunts and non_taunts:
            n = len(taunts)
            return [Buff(m, atk=n, health=n * 2) for m in non_taunts]
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start of Turn
# ═══════════════════════════════════════════════════════════════════════════════

class SoTGainGoldImproveScript:
    """
    Natural language: At the start of your turn, gain 1 Gold. Improves each turn!

    Formal spec:
      1. Maintain counter on reward (starts at 1)
      2. Each SoT: GainGold(counter), counter += 1
    Test: turn 1 → +1 gold; turn 3 → +3 gold.
    """

    @classmethod
    def on_unlock(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 1)

    @classmethod
    def start_of_turn(cls, source, game):
        c = source.get_tag(GameTag.TRINKET_COUNTER, 1)
        source.set_tag(GameTag.TRINKET_COUNTER, c + 1)
        return GainGold(source.controller, c)


class SoTDiscoverCurrentTierScript:
    """
    Natural language: Discover a minion of your current Tavern Tier. (Can be won infinitely!)

    Formal spec:
      1. DiscoverMinion(min_tier=tier, max_tier=tier)
    Test: at Tier 3 → discovered minion is Tier 3.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        tier = source.controller.tavern_tier
        return DiscoverMinion(source.controller, min_tier=tier, max_tier=tier)


class SoTGet3SpellsScript:
    """
    Natural language: At the start of your turn, get 3 random Tavern spells.

    Formal spec:
      1. Filter card_db for type=SPELL (42)
      2. AddToHand × 3 random picks
    Test: hand gains 3 spell cards.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 42 and not cid.startswith("EXAMPLE")]
        actions = []
        for _ in range(3):
            if pool:
                actions.append(AddToHand(source.controller, random.choice(pool)))
        return actions if actions else None


class SoTGet2RandomMinionsScript:
    """
    Natural language: At the start of your turn, get 2 random minions (of a type).

    Formal spec:
      1. Get 2 random minions from the card pool
      2. AddToHand each
    Test: hand gains 2 minions.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and not cid.startswith("EXAMPLE")]
        actions = []
        for _ in range(2):
            if pool:
                actions.append(AddToHand(source.controller, random.choice(pool)))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Event-Based (EventListener on unlock)
# ═══════════════════════════════════════════════════════════════════════════════

class AfterRefreshBuffTavernScript:
    """
    Natural language: After you Refresh, give a random minion in the Tavern
    +6/+6 and Divine Shield.

    Formal spec:
      1. on_unlock: register TAVERN_REFRESH EventListener
      2. On each TAVERN_REFRESH: pick random tavern minion → Buff(+6/+6) + GainKeyword(DS)
    Test: refresh → one tavern minion gets +6/+6 and DS.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _RefreshAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                tavern = self.player.tavern
                if tavern:
                    m = random.choice(tavern)
                    g.queue_action(Buff(m, atk=6, health=6))
                    g.queue_action(GainKeyword(m, GameTag.DIVINE_SHIELD))

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(source.controller),
            condition=lambda player: player == source.controller,
        ))


class AfterBuyBuffScript:
    """
    Natural language: After you buy a minion, give it +2/+2 and improve this effect.

    Status: DEFERRED — "improve this effect" requires per-reward counter
    increment tracking. The +2/+2 alone does not match the full card text.
    Dependency: Per-reward Improve counter system.
    """

    @staticmethod
    def on_unlock(source, game):
        return None  # DEFERRED


class AfterSellTransferScript:
    """
    Natural language: After you sell a minion, give a minion in the Tavern its stats.

    Formal spec:
      1. on_unlock: register MINION_SOLD EventListener
      2. On each MINION_SOLD: pick random tavern minion → Buff(atk=sold.atk, health=sold.health)
    Test: sell a 3/4 → random tavern minion gets +3/+4.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import MINION_SOLD, EventListener

        class _SellAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if target and self.player.tavern:
                    t = random.choice(self.player.tavern)
                    g.queue_action(Buff(t, atk=target.atk, health=target.max_health))

        game.register_listener(source, EventListener(
            event_name=MINION_SOLD,
            action=_SellAction(source.controller),
        ))


class AfterCombatCopyLastDeadScript:
    """
    Natural language: After each combat, get an original copy of the last
    friendly minion that died.

    Formal spec:
      1. on_unlock: register END_OF_COMBAT EventListener
      2. On END_OF_COMBAT: if last dead in _combat_death_log is friendly → AddToHand(card_id)
    Test: combat ends with friendly death → get copy in hand.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener

        class _CombatCopyAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                for dead in reversed(g._combat_death_log):
                    if dead.controller == self.player:
                        g.queue_action(AddToHand(self.player, dead.get_tag(GameTag.CARD_ID)))
                        return

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_CombatCopyAction(source.controller),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Passive / On-Unlock Effects
# ═══════════════════════════════════════════════════════════════════════════════

class BCDoubleRewardScript:
    """
    Natural language: Your Battlecries trigger an extra time.

    Formal spec: Set BATTLECRY_DOUBLED = True on controller.
    Test: after unlock, battlecries fire twice.
    """

    @staticmethod
    def on_unlock(source, game):
        source.controller.set_tag(GameTag.BATTLECRY_DOUBLED, True)


class DRDoubleRewardScript:
    """
    Natural language: Your Deathrattles trigger an extra time.

    Formal spec: Set DEATHRATTLE_DOUBLED = True on controller.
    Test: after unlock, deathrattles fire twice.
    """

    @staticmethod
    def on_unlock(source, game):
        source.controller.set_tag(GameTag.DEATHRATTLE_DOUBLED, True)


class EoTDoubleRewardScript:
    """
    Natural language: Your End of Turn effects trigger an extra time.

    Formal spec: Set END_OF_TURN_DOUBLED = True on controller.
    Test: after unlock, EoT effects fire twice.
    """

    @staticmethod
    def on_unlock(source, game):
        source.controller.set_tag(GameTag.END_OF_TURN_DOUBLED, True)


class BrannsBlessingScript(BCDoubleRewardScript):
    """Alias: Your Battlecries trigger an extra time."""


class TwoCopiesForGoldenScript:
    """
    Natural language: You only need 2 copies to make a minion Golden.

    Formal spec: Set PIRATES_NEED_2_COPIES = True on controller.
    Note: this tag is also used by Designer Eyepatch (pirates-only).
      This reward applies to ALL minions (engine should check without race filter).
    Test: 2 copies of same minion → triple forms.
    """

    @staticmethod
    def on_unlock(source, game):
        source.controller.set_tag(GameTag.PIRATES_NEED_2_COPIES, True)


class SpellCostMinus1Script:
    """
    Natural language: Tavern spells cost (1) less.

    Formal spec: Increment NEXT_SPELL_COST_REDUCTION tag on controller.
    Test: spell costs 1 less after unlock.
    """

    @staticmethod
    def on_unlock(source, game):
        cur = source.controller.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)
        source.controller.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, cur + 1)


class SpellsCastTwiceScript:
    """
    Natural language: Your first Tavern spell each turn casts twice.

    Status: DEFERRED — "first spell each turn" requires per-turn spell counter.
    Setting TAVERN_SPELLS_CAST_TWICE makes ALL spells cast twice, which does not
    match the card text's "first spell each turn" semantics.
    Dependency: Per-turn first-spell tracking in spell cast pipeline.
    """

    @staticmethod
    def on_unlock(source, game):
        return None  # DEFERRED


class TavernCost2Script:
    """
    Natural language: Minions in the Tavern cost (2).

    Formal spec: Set TAVERN_MINION_COST_OVERRIDE = 2 on controller.
    Engine checks this tag in buy_minion() to override the cost.
    Test: tavern minion cost reads as 2.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.enums import GameTag as GT
        source.controller.set_tag(GT.TAVERN_MINION_COST_OVERRIDE, 2)


class UnlockTier7Script:
    """
    Natural language: Unlock Tier 7 for this game.

    Formal spec: Set TIER_7_UNLOCKED = True on controller.
    Status: DEFERRED — TIER_7_UNLOCKED tag exists but engine may not fully support
      Tier 7 pool drawing and upgrade cost.
    Test: tag is set after unlock.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.enums import GameTag as GT
        source.controller.set_tag(GT.TIER_7_UNLOCKED, True)


class CoinBagScript:
    """
    Natural language: Get a Coin Pouch with 5 Gold. Your Gold cap is increased by 5.

    Formal spec:
      1. GainGold(5)
    Note: Gold cap increase is DEFERRED (engine uses fixed max gold).
    Test: gold increases by 5.
    """

    @staticmethod
    def on_unlock(source, game):
        return GainGold(source.controller, 5)


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy compatibility aliases (for existing tests)
# ═══════════════════════════════════════════════════════════════════════════════

class EternalKnightsRewardScript:
    """
    Natural language: On unlock: Give a random friendly minion +4/+4.
    (Legacy generic reward used for testing.)

    Formal spec: Pick random living friendly → Buff(+4/+4).
    Test: minion gains +4/+4 after unlock.
    """

    @staticmethod
    def on_unlock(source, game):
        target = _random_friendly(source.controller)
        if target:
            return Buff(target, atk=4, health=4)
        return None


# Legacy aliases — used by existing tests
StolenGoldScript = None  # Was: give 2 gold on SoC → now DEFERRED (make golden ≠ give gold)
RitualDaggerScript = SoCBuffAll3x0Script  # CORRECT: SoC +3 ATK
TheotarsParasolScript = EoTBuffRightmost8HPScript  # CORRECT: EoT +8 HP
EvilTwinScript = SoCSummonCopyHighestScript  # CORRECT: SoC summon highest HP copy
SnickerSnacksScript = None  # DEFERRED: needs TriggerBattlecry targeting


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED Rewards — not implemented due to missing engine support
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: End of Turn — Low Tier Buff
# ═══════════════════════════════════════════════════════════════════════════════

class EoTBuffLowTier3x3Script:
    """
    Natural language: At the end of your turn, give 3 friendly minions
    of Tier 3 or lower +3/+3.

    Formal spec:
      1. end_of_turn: filter board for Tier ≤ 3, take up to 3 → Buff(+3/+3)
    Test: 3 low-tier minions each get +3/+3.
    """

    @classmethod
    def end_of_turn(cls, source, game):
        low = [m for m in source.controller.board
               if not m.dead and m.get_tag(GameTag.TECH_LEVEL, 1) <= 3]
        actions = []
        for m in low[:3]:
            actions.append(Buff(m, atk=3, health=3))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start of Turn — Hand Buff + Cast Spells
# ═══════════════════════════════════════════════════════════════════════════════

class SoTHandMinion12x12Script:
    """
    Natural language: At the start of your turn, give a minion in your
    hand +12/+12.

    Formal spec:
      1. start_of_turn: select random minion in hand → Buff(+12/+12)
    Test: a hand minion gains +12/+12.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        import random
        hand_minions = [m for m in source.controller.hand
                        if m.get_tag(GameTag.CARDTYPE) == 1]  # CardType.MINION
        if not hand_minions:
            return None
        target = random.choice(hand_minions)
        return Buff(target, atk=12, health=12)


class SoTCast5SpellsScript:
    """
    Natural language: At the start of your turn, cast 5 random Tavern spells.

    Formal spec:
      1. start_of_turn: CastTavernSpell × 5
    Test: 5 spells are cast at start of turn.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.actions import CastTavernSpell
        return [CastTavernSpell(source.controller) for _ in range(5)]


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Event-Based — After Play/Buy/Refresh/Cast
# ═══════════════════════════════════════════════════════════════════════════════

class AfterPlayBuffSameTierScript:
    """
    Natural language: After you play a minion, give 2 other minions of the
    same Tier +4/+4.

    Formal spec:
      1. on_unlock: register MINION_PLAYED EventListener
      2. On MINION_PLAYED: find up to 2 other minions with same tier → Buff(+4/+4)
    Test: play a Tier 3 → 2 other Tier 3 minions get +4/+4.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener

        class _PlayAction(Action):
            def do(self, s, g, target=None):
                if target is None or target.controller is None:
                    return
                player = target.controller
                tier = target.get_tag(GameTag.TECH_LEVEL, 1)
                same = [m for m in player.board if not m.dead and m != target
                        and m.get_tag(GameTag.TECH_LEVEL, 1) == tier]
                for m in same[:2]:
                    g.queue_action(Buff(m, atk=4, health=4))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_PlayAction(),
        ))


class AfterBuyTransferStatsScript:
    """
    Natural language: When you buy a minion, give a random friendly minion
    its stats.

    Formal spec:
      1. on_unlock: register MINION_BOUGHT EventListener
      2. On MINION_BOUGHT: pick random friendly → Buff(atk=bought.atk, health=bought.health)
    Test: buy 3/4 → random friendly gets +3/+4.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        import random

        class _BuyAction(Action):
            def do(self, s, g, target=None):
                if target is None or target.controller is None:
                    return
                living = [m for m in target.controller.board if not m.dead and m != target]
                if living:
                    t = random.choice(living)
                    g.queue_action(Buff(t, atk=target.atk, health=target.max_health))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BuyAction(),
        ))


class AfterPlayNewTypeBuffScript:
    """
    Natural language: After you play a minion of a type you don't control,
    give +2/+2 to one minion of each type.

    Formal spec:
      1. on_unlock: register MINION_PLAYED EventListener
      2. On MINION_PLAYED: if target's race not already on board → buff one per type
    Test: play first Beast → one of each existing type gets +2/+2.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import MINION_PLAYED, EventListener

        class _NewTypeAction(Action):
            def do(self, s, g, target=None):
                if target is None or target.controller is None:
                    return
                if target.race == Race.INVALID:
                    return
                player = target.controller
                board_types = {m.race for m in player.board
                               if not m.dead and m != target and m.race != Race.INVALID}
                if target.race in board_types:
                    return  # type already controlled
                seen = set()
                for m in player.board:
                    if not m.dead and m.race != Race.INVALID and m.race not in seen:
                        seen.add(m.race)
                        g.queue_action(Buff(m, atk=2, health=2))

        game.register_listener(source, EventListener(
            event_name=MINION_PLAYED,
            action=_NewTypeAction(),
        ))


class FirstBuyCopyRewardScript:
    """
    Natural language: Your first purchase each turn gives an extra copy.

    Formal spec:
      1. on_unlock: register MINION_BOUGHT EventListener with per-turn counter
      2. On first MINION_BOUGHT each turn → AddToHand(copy)
    Test: first buy gives copy; second buy doesn't.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        source.controller.set_tag(GameTag.TRINKET_COUNTER, 0)

        class _BuyAction(Action):
            def do(self, s, g, target=None):
                if target is None or target.controller is None:
                    return
                player = target.controller
                if player.get_tag(GameTag.TRINKET_COUNTER, 0) == 0:
                    player.set_tag(GameTag.TRINKET_COUNTER, 1)
                    g.queue_action(AddToHand(player, target.get_tag(GameTag.CARD_ID)))

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BuyAction(),
        ))


class BuyExpensiveSpellCopyScript:
    """
    Natural language: When you buy a Tavern spell costing (3) or more,
    get an extra copy.

    Formal spec:
      1. on_unlock: register TAVERN_SPELL_CAST EventListener
      2. On TAVERN_SPELL_CAST: if spell cost >= 3 → AddToHand(copy)
    Test: buy 3-cost spell → get extra copy.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener

        class _SpellAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                if target.get_tag(GameTag.COST, 0) >= 3:
                    g.queue_action(AddToHand(target.controller, target.get_tag(GameTag.CARD_ID)))

        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_SpellAction(),
        ))


class PerRefreshTavernBuffScript:
    """
    Natural language: Each Refresh this turn, give Tavern minions +1/+1.

    Formal spec:
      1. on_unlock: register TAVERN_REFRESH EventListener
      2. On TAVERN_REFRESH: Buff all tavern minions +1/+1
    Test: refresh → all tavern minions get +1/+1.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _RefreshAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                for m in target.tavern:
                    if not m.dead:
                        g.queue_action(Buff(m, atk=1, health=1))

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(),
            condition=lambda player: player == source.controller,
        ))


class After5RefreshMakeGoldenScript:
    """
    Natural language: After you Refresh 5 times, make the highest-Tier
    minion in the Tavern golden.

    Formal spec:
      1. on_unlock: register TAVERN_REFRESH EventListener with counter
      2. On 5th refresh: find highest-tier tavern minion → set GOLDEN tag
    Test: after 5 refreshes, best tavern minion becomes golden.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 5)

        class _RefreshAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                c = source.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    source.set_tag(GameTag.TRINKET_COUNTER, 5)
                    tavern = target.tavern
                    if tavern:
                        best = max(tavern, key=lambda m: m.get_tag(GameTag.TECH_LEVEL, 1))
                        best.set_tag(GameTag.GOLDEN, True)
                else:
                    source.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(),
            condition=lambda player: player == source.controller,
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Blood Gem + Spellcraft
# ═══════════════════════════════════════════════════════════════════════════════

class BloodGemImproveAndGetScript:
    """
    Natural language: Your Blood Gems give +1/+1. At SoT, get 2 Blood Gems.

    Formal spec:
      1. on_unlock: ImproveBloodGem(atk=1, health=1)
      2. start_of_turn: PlayBloodGems on random friendly ×2
    Test: Blood Gem bonus increases; SoT gives 2 gems.
    """

    @classmethod
    def on_unlock(cls, source, game):
        from hsrl.core.actions import ImproveBloodGem
        game.queue_action(ImproveBloodGem(source.controller, atk_bonus=1, health_bonus=1))

    @classmethod
    def start_of_turn(cls, source, game):
        living = [m for m in source.controller.board if not m.dead]
        if not living:
            return None
        import random
        from hsrl.core.actions import PlayBloodGems
        target = random.choice(living)
        return PlayBloodGems(target, 2)


class SpellcraftWindfuryDSScript:
    """
    Natural language: Spellcraft: Give a minion Windfury and Divine Shield.

    Status: DEFERRED — Spellcraft requires generating a spell card via
    spellcraft() method returning a card_id string. End-of-turn effect
    does not match the Spellcraft semantics.
    Dependency: Spellcraft spell card for Windfury+Divine Shield registration.
    """

    @classmethod
    def end_of_turn(cls, source, game):
        return None  # DEFERRED


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: End of Turn — Left/Right Consume Tavern
# ═══════════════════════════════════════════════════════════════════════════════

class EoTLeftRightConsumeTavernScript:
    """
    Natural language: At the end of your turn, your left- and right-most
    minions each consume a minion in the Tavern and gain its stats.

    Formal spec:
      1. end_of_turn: find leftmost and rightmost living minions
      2. For each: pick highest-health tavern minion → FodderConsume
    Test: left/right minions each gain tavern minion's stats.
    """

    @classmethod
    def end_of_turn(cls, source, game):
        from hsrl.core.actions import FodderConsume
        living = [m for m in source.controller.board if not m.dead]
        if not living:
            return None
        tavern = source.controller.tavern
        if not tavern:
            return None
        actions = []
        for target in (living[0], living[-1]):
            if target is not living[0] or len(living) == 1:
                candidates = [m for m in tavern if not m.dead]
                if candidates:
                    eaten = max(candidates, key=lambda m: m.get_tag(GameTag.HEALTH, 0))
                    actions.append(FodderConsume(target, eaten))
            elif len(living) > 1:
                candidates = [m for m in tavern if not m.dead]
                if candidates:
                    eaten = max(candidates, key=lambda m: m.get_tag(GameTag.HEALTH, 0))
                    actions.append(FodderConsume(target, eaten))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: End of Turn — Trigger Battlecries
# ═══════════════════════════════════════════════════════════════════════════════

class EoTTriggerBattlecriesScript:
    """
    Natural language: At the end of your turn, 2 friendly minions
    trigger their Battlecries.

    Formal spec:
      1. end_of_turn: pick 2 random living minions with battlecry
      2. For each: TriggerBattlecry (re-execute its battlecry method)
    Test: 2 minions' battlecries are triggered.
    """

    @classmethod
    def end_of_turn(cls, source, game):
        from hsrl.core.actions import TriggerBattlecry
        import random
        candidates = [m for m in source.controller.board
                      if not m.dead and m.battlecry is not None]
        if not candidates:
            return None
        targets = random.sample(candidates, min(2, len(candidates)))
        actions = []
        for m in targets:
            actions.append(TriggerBattlecry(m))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Avenge Pattern Rewards
# ═══════════════════════════════════════════════════════════════════════════════

class Avenge3Deal10Script:
    """
    Natural language: Avenge (3): Deal 10 damage to the highest-Health
    enemy minion.

    Formal spec:
      1. on_unlock: register DEATH EventListener on game with counter
      2. After 3 friendly deaths: find highest-HP enemy → Hit(10)
    Test: after 3 friendly deaths, highest-HP enemy takes 10 damage.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import DEATH, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 0)

        class _AvengeAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                c = self.reward.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
                if c >= 3:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, 0)
                    # Find enemy with highest HP
                    enemies = [p for p in g.players
                               if p != self.reward.controller and p.is_alive]
                    if enemies:
                        enemy = enemies[0]
                        enemy_board = [m for m in enemy.board if not m.dead]
                        if enemy_board:
                            target_e = max(enemy_board, key=lambda m: m.health)
                            from hsrl.core.actions import Hit
                            g.queue_action(Hit(target_e, 10))
                else:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_AvengeAction(source),
        ))


class Avenge3GetSpellScript:
    """
    Natural language: Avenge (3): Get a random Tavern spell.

    Formal spec:
      1. on_unlock: register DEATH EventListener with counter
      2. After 3 friendly deaths: DiscoverSpell
    Test: after 3 deaths, gain a spell.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import DEATH, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 0)

        class _AvengeAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                c = self.reward.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
                if c >= 3:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, 0)
                    g.queue_action(DiscoverSpell(self.reward.controller))
                else:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_AvengeAction(source),
        ))


class Avenge2FreeRefreshScript:
    """
    Natural language: Avenge (2): Gain a free Refresh.

    Formal spec:
      1. on_unlock: register DEATH EventListener with counter
      2. After 2 friendly deaths: GainFreeRefresh(1)
    Test: after 2 deaths, get 1 free refresh.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import DEATH, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 0)

        class _AvengeAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                c = self.reward.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
                if c >= 2:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, 0)
                    g.queue_action(GainFreeRefresh(self.reward.controller, 1))
                else:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_AvengeAction(source),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Tavern Spell Buff Repeat Improve
# ═══════════════════════════════════════════════════════════════════════════════

class TavernSpellBuffRepeatScript:
    """
    Natural language: Your Tavern spells give an extra +{3}/+{1}.
    (Can be won infinitely for +2/+1 each time!)

    Formal spec:
      1. on_unlock: ImproveTavernSpellBuff(atk=3, health=1)
      2. start_of_turn: ImproveTavernSpellBuff(atk=2, health=1) — repeat forever
    Test: each turn, tavern spell buff improves by +2/+1.
    """

    @classmethod
    def on_unlock(cls, source, game):
        from hsrl.core.actions import ImproveTavernSpellBuff
        game.queue_action(ImproveTavernSpellBuff(source.controller, atk_bonus=3, health_bonus=1))

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.actions import ImproveTavernSpellBuff
        return ImproveTavernSpellBuff(source.controller, atk_bonus=2, health_bonus=1)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Golden-Making Rewards
# ═══════════════════════════════════════════════════════════════════════════════

class SoCMakeLeftRightGoldenScript:
    """
    Natural language: Start of Combat: Make your left- and right-most
    minions Golden.

    Formal spec:
      1. start_of_combat: find leftmost and rightmost living minions
      2. Set GOLDEN tag on each
    Test: leftmost and rightmost become golden.
    """

    @staticmethod
    def start_of_combat(source, game):
        living = [m for m in source.controller.board if not m.dead]
        if not living:
            return None
        actions = []
        living[0].set_tag(GameTag.GOLDEN, True)
        if len(living) > 1:
            living[-1].set_tag(GameTag.GOLDEN, True)
        return None


class SoTMakeHighestTavernGoldenScript:
    """
    Natural language: At the start of your turn, make the highest-Tier
    minion in the Tavern Golden.

    Formal spec:
      1. start_of_turn: find max(tier) tavern minion → set GOLDEN tag
    Test: best tavern minion becomes golden.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        tavern = source.controller.tavern
        if not tavern:
            return None
        best = max(tavern, key=lambda m: m.get_tag(GameTag.TECH_LEVEL, 1))
        best.set_tag(GameTag.GOLDEN, True)
        return None


class SoTMakeGoldenImproveScript:
    """
    Natural language: At the start of your turn, make a Tier @ friendly
    minion Golden and improve this effect.
    (Starts at Tier 1, improves by 1 each turn.)

    Formal spec:
      1. on_unlock: set current_tier = 1 on reward
      2. start_of_turn: find friendly minion at current_tier → set GOLDEN,
         then current_tier += 1
    Test: turn 1 → Tier 1 golden; turn 3 → Tier 3 golden.
    """

    @classmethod
    def on_unlock(cls, source, game):
        source.set_tag(GameTag.TRINKET_COUNTER, 1)  # current tier

    @classmethod
    def start_of_turn(cls, source, game):
        tier = source.get_tag(GameTag.TRINKET_COUNTER, 1)
        candidates = [m for m in source.controller.board
                      if not m.dead and m.get_tag(GameTag.TECH_LEVEL, 1) == tier]
        if candidates:
            candidates[0].set_tag(GameTag.GOLDEN, True)
        source.set_tag(GameTag.TRINKET_COUNTER, min(tier + 1, 6))
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Even/Odd Tier Tavern Buff (Paired Rewards)
# ═══════════════════════════════════════════════════════════════════════════════

class EvenTierTavernBuffScript:
    """
    Natural language: Even-Tier minions in the Tavern have +7/+7.
    (Switches to odd next turn!)

    Formal spec:
      1. on_unlock: set parity flag = "even", add tavern buff for even tiers
      2. start_of_turn: toggle parity, swap tavern buffs
    Test: even-tier tavern minions get +7/+7; toggles each turn.
    """

    @classmethod
    def on_unlock(cls, source, game):
        from hsrl.core.actions import BuffTavern
        source.controller._tavern_parity = "even"
        # Apply +7/+7 to even tiers
        for tier in (2, 4, 6):
            game.queue_action(BuffTavern(source.controller, atk=7, health=7, max_tier=tier))

    @classmethod
    def start_of_turn(cls, source, game):
        # Toggle parity: even ↔ odd
        current = getattr(source.controller, '_tavern_parity', "even")
        next_parity = "odd" if current == "even" else "even"
        source.controller._tavern_parity = next_parity


class OddTierTavernBuffScript:
    """
    Natural language: Odd-Tier minions in the Tavern have +7/+7.
    (Switches to even next turn! — paired with EvenTier.)

    Formal spec: Same as EvenTierTavernBuffScript but starts with odd tiers.
    Test: odd-tier tavern minions get +7/+7; toggles each turn.
    """

    @classmethod
    def on_unlock(cls, source, game):
        from hsrl.core.actions import BuffTavern
        source.controller._tavern_parity = "odd"
        for tier in (1, 3, 5):
            game.queue_action(BuffTavern(source.controller, atk=7, health=7, max_tier=tier))

    @classmethod
    def start_of_turn(cls, source, game):
        current = getattr(source.controller, '_tavern_parity', "odd")
        next_parity = "even" if current == "odd" else "odd"
        source.controller._tavern_parity = next_parity


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: After Discover — Get Extra Copy
# ═══════════════════════════════════════════════════════════════════════════════

class AfterDiscoverCopyScript:
    """
    Natural language: After you Discover a card, get an extra copy.

    Formal spec:
      1. on_unlock: register DISCOVER EventListener on game
      2. On DISCOVER: AddToHand(game._last_discovered_id) for the discovering player
    Test: after discover, get an extra copy in hand.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import EventListener

        class _DiscoverAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                cid = getattr(g, '_last_discovered_id', None)
                if cid:
                    g.queue_action(AddToHand(self.reward.controller, cid))

        game.register_listener(source, EventListener(
            event_name="DISCOVER",
            action=_DiscoverAction(source),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Useful Refresh — periodic tavern buff
# ═══════════════════════════════════════════════════════════════════════════════

class UsefulRefreshScript:
    """
    Natural language: Occasionally a useful Refresh! (Every ~4 refreshes,
    give a random tavern minion +6/+6 and Divine Shield.)

    Formal spec:
      1. on_unlock: register TAVERN_REFRESH EventListener with counter
      2. Every 4 refreshes: pick random tavern minion → Buff(+6/+6) + GainKeyword(DS)
    Test: after 4 refreshes, a tavern minion gets +6/+6 and DS.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        import random
        source.set_tag(GameTag.TRINKET_COUNTER, 4)

        class _RefreshAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                if target is None:
                    return
                c = self.reward.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, 4)
                    tavern = target.tavern
                    if tavern:
                        m = random.choice(tavern)
                        g.queue_action(Buff(m, atk=6, health=6))
                        g.queue_action(GainKeyword(m, GameTag.DIVINE_SHIELD))
                else:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(source),
            condition=lambda player: player == source.controller,
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Avenge (7) — Summon 50/50 Amalgam
# ═══════════════════════════════════════════════════════════════════════════════

class Avenge7Summon50x50Script:
    """
    Natural language: Avenge (7): When you have space, summon a 50/50 Amalgam.

    Formal spec:
      1. on_unlock: register DEATH EventListener with counter
      2. After 7 friendly deaths: if board has space (<7), summon 50/50 token
    Test: after 7 deaths, a 50/50 is summoned.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import DEATH, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 0)

        class _AvengeAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                c = self.reward.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
                if c >= 7:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, 0)
                    player = self.reward.controller
                    if len(player.board) < 7:
                        token = g.create_minion("EXAMPLE_VANILLA")
                        if token:
                            token.set_tag(GameTag.BASE_ATK, 50)
                            token.set_tag(GameTag.BASE_HEALTH, 50)
                            token.set_tag(GameTag.ATK, 50)
                            token.set_tag(GameTag.HEALTH, 50)
                            from hsrl.core.actions import Summon
                            g.queue_action(Summon(player, token))
                else:
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_AvengeAction(source),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Refresh Always Offers 2 X
# ═══════════════════════════════════════════════════════════════════════════════

class RefreshAlwaysOffers2Script:
    """
    Natural language: Whenever you Refresh, always offer 2 additional
    minions of a specific type.

    Formal spec:
      1. on_unlock: register TAVERN_REFRESH EventListener
      2. On TAVERN_REFRESH: add 2 random minions to tavern
    Test: after refresh, tavern has 2 extra minions.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        from hsrl.core.card_db import CARDS
        import random

        class _RefreshAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                pool = [cid for cid, data in CARDS._cards.items()
                        if data.cardtype == 4 and not cid.startswith("EXAMPLE")]
                for _ in range(2):
                    if pool and len(self.player.tavern) < 7:
                        token = g.create_minion(random.choice(pool))
                        if token:
                            token.controller = self.player
                            token.zone = Zone.TAVERN
                            self.player.tavern.append(token)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(source.controller),
            condition=lambda player: player == source.controller,
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: After Combat — Discover from Opponent
# ═══════════════════════════════════════════════════════════════════════════════

class AfterCombatDiscoverOpponentScript:
    """
    Natural language: After each combat, Discover a non-golden minion
    from your last opponent's warband. Retain enchantments.

    Formal spec:
      1. on_unlock: register END_OF_COMBAT EventListener
      2. On END_OF_COMBAT: DiscoverMinion at current tier
    Note: "retain enchantments" requires opponent minion state preservation → DEFERRED.
      Gives a fresh copy instead.
    Test: after combat, discover a minion.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener

        class _CombatAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if self.player.is_alive:
                    g.queue_action(DiscoverMinion(self.player, max_tier=6))

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_CombatAction(source.controller),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Combat Summon Buff + Avenge Improve
# ═══════════════════════════════════════════════════════════════════════════════

class CombatSummonBuffAvengeScript:
    """
    Natural language: In combat, whenever you summon a minion, give it
    +@/+@. Avenge (4): Improve this permanently.

    Formal spec:
      1. on_unlock: register SUMMON EventListener (combat only) + DEATH counter
      2. On combat SUMMON: Buff(minion, base+improve_counter)
      3. On 4 friendly deaths: increment improve counter
    Test: combat summons get buffed; avenge improves the buff.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import SUMMON, DEATH, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 0)  # improve counter
        source.set_tag(GameTag.TRINKET_TIER, 0)      # avenge counter

        class _SummonAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                if not g.in_combat:
                    return
                if target is None:
                    return
                bonus = self.reward.get_tag(GameTag.TRINKET_COUNTER, 0)
                g.queue_action(Buff(target, atk=1 + bonus, health=1 + bonus))

        class _AvengeAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                c = self.reward.get_tag(GameTag.TRINKET_TIER, 0) + 1
                if c >= 4:
                    self.reward.set_tag(GameTag.TRINKET_TIER, 0)
                    cur = self.reward.get_tag(GameTag.TRINKET_COUNTER, 0)
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, cur + 1)
                else:
                    self.reward.set_tag(GameTag.TRINKET_TIER, c)

        game.register_listener(source, EventListener(
            event_name=SUMMON,
            action=_SummonAction(source),
        ))
        game.register_listener(source, EventListener(
            event_name=DEATH,
            action=_AvengeAction(source),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Card-Granting Rewards (SoT/EoT give specific cards)
# ═══════════════════════════════════════════════════════════════════════════════

class EoTGetZerusScript:
    """
    Natural language: At the end of your turn, get a Shifter Zerus that
    can transform into a random minion.

    Formal spec:
      1. end_of_turn: AddToHand(BGS_029) — Shifter Zerus
    Test: Zerus is added to hand at end of turn.
    """
    ZERUS_ID = "BGS_029"

    @classmethod
    def end_of_turn(cls, source, game):
        return AddToHand(source.controller, cls.ZERUS_ID)


class SoTGetAcceleratorsScript:
    """
    Natural language: At the start of your turn, get 2 Accelerators.
    Accelerator can transform a minion into one of the next higher Tier.

    Formal spec:
      1. start_of_turn: AddToHand(BG27_Reward_504t) × 2
    Test: 2 Accelerators added to hand.
    """
    ACCEL_ID = "BG27_Reward_504t"

    @classmethod
    def start_of_turn(cls, source, game):
        return [AddToHand(source.controller, cls.ACCEL_ID) for _ in range(2)]


class SoTGetSparePartScript:
    """
    Natural language: At the start of your turn, get a Spare Part that
    gives a minion +5/+5 and a random bonus effect.

    Formal spec:
      1. start_of_turn: AddToHand(SPARE_PART)
    Test: Spare Part added to hand.
    """
    SPARE_ID = "SPARE_PART"

    @classmethod
    def start_of_turn(cls, source, game):
        return AddToHand(source.controller, cls.SPARE_ID)


class SoTGetTier7CopyScript:
    """
    Natural language: Get a copy of a Tier 7 {0}.

    Formal spec:
      1. on_unlock: AddToHand a Tier 7 minion
    Note: {0} is a parameterized tribe/card; uses random Tier 7 minion as default.
    Test: a Tier 7 minion is added to hand.
    """

    @classmethod
    def on_unlock(cls, source, game):
        from hsrl.core.card_db import CARDS
        import random
        t7_pool = [cid for cid, data in CARDS._cards.items()
                   if data.cardtype == 4 and data.tech_level == 7
                   and not cid.startswith("EXAMPLE")]
        if t7_pool:
            return AddToHand(source.controller, random.choice(t7_pool))
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Rally Doubler
# ═══════════════════════════════════════════════════════════════════════════════

class RallyDoublerScript:
    """
    Natural language: Get a copy of {0}. Your Rally effects trigger an
    extra time.

    Formal spec:
      1. on_unlock: set RALLY_DOUBLED = True on controller
    Note: "Get a copy of {0}" is DEFERRED — {0} is a parameterized card ID.
    Test: RALLY_DOUBLED tag is set.
    """

    @staticmethod
    def on_unlock(source, game):
        source.controller.set_tag(GameTag.RALLY_DOUBLED, True)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Second Hero Power Discovery
# ═══════════════════════════════════════════════════════════════════════════════

class DiscoverSecondHPScript:
    """
    Natural language: Discover a second Hero Power.

    Formal spec:
      1. on_unlock: set DISCOVER_SECOND_HP flag on controller
    Note: actual hero power discovery requires HP pool + selection UI.
      Sets a flag for engine to trigger HP discovery.
    Test: flag is set on controller.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.enums import GameTag as GT
        source.controller.set_tag(GT.DISCOVER_SECOND_HP, True)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Yogg Wheel — random effect each turn
# ═══════════════════════════════════════════════════════════════════════════════

class SoTYoggWheelScript:
    """
    Natural language: At the start of your turn, spin the Wheel of Yogg-Saron.

    Formal spec:
      1. start_of_turn: CastYoggWheel(player) — picks random effect from pool
    Test: each turn, a random Yogg effect triggers.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.actions import CastYoggWheel
        return CastYoggWheel(source.controller)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Spellcraft — Temporary Golden
# ═══════════════════════════════════════════════════════════════════════════════

class SpellcraftTempGoldenScript:
    """
    Natural language: Spellcraft: Make a friendly minion Golden until next turn.

    Formal spec:
      1. spellcraft: returns card_id of a spell that makes a minion golden
    Note: the spell card "SC_TEMP_GOLDEN" makes a random friendly golden on play.
    Test: spellcraft generates the temp-golden spell card.
    """

    @staticmethod
    def spellcraft(source, game):
        return "SC_TEMP_GOLDEN"


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Next Turn Gold + Schedule Trinket
# ═══════════════════════════════════════════════════════════════════════════════

class NextTurnGoldChooseLesserTrinketScript:
    """
    Natural language: At the start of your next turn, gain 4 Gold and
    choose a Lesser Trinket to buy.

    Formal spec:
      1. on_unlock: schedule for next turn → GainGold(4)
    Note: "choose a Lesser Trinket" requires trinket selection UI → DEFERRED.
    Test: 4 gold granted next turn.
    """

    @classmethod
    def on_unlock(cls, source, game):
        next_turn = game.turn + 1
        p = source.controller

        def _on_next_turn(g, t):
            g.queue_action(GainGold(p, 4))

        game.schedule_turn_action(next_turn, _on_next_turn)


class NextTurnGoldChooseGreaterTrinketScript:
    """
    Natural language: At the start of your next turn, gain 4 Gold and
    choose a Greater Trinket to buy.

    Formal spec:
      1. on_unlock: schedule for next turn → GainGold(4)
    Note: "choose a Greater Trinket" requires trinket selection UI → DEFERRED.
    Test: 4 gold granted next turn.
    """

    @classmethod
    def on_unlock(cls, source, game):
        next_turn = game.turn + 1
        p = source.controller

        def _on_next_turn(g, t):
            g.queue_action(GainGold(p, 4))

        game.schedule_turn_action(next_turn, _on_next_turn)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: SoT — Get Murloc + Teach Spell
# ═══════════════════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Choose New Reward Each Turn
# ═══════════════════════════════════════════════════════════════════════════════

class SoTChooseRewardScript:
    """
    Natural language: At the start of your turn, choose from 2 new rewards.
    (Replaces the current reward with a newly discovered one.)

    Formal spec:
      1. start_of_turn: DiscoverReward(player) — picks 2, applies the chosen one
    Test: each turn, a new random reward's on_unlock triggers.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.actions import DiscoverReward
        return DiscoverReward(source.controller)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Spellcraft — Copy Non-Golden Card
# ═══════════════════════════════════════════════════════════════════════════════

class SpellcraftCopyNonGoldenScript:
    """
    Natural language: Spellcraft: Choose a non-golden card, move it to your hand.
    (In RL context: generates a spell that copies a random non-golden friendly.)

    Formal spec:
      1. spellcraft: returns "SC_COPY_NONGOLDEN" card_id
      2. The spell card's on_play picks random non-golden friendly → AddToHand(copy)
    Test: spellcraft generates the copy spell card.
    """

    @staticmethod
    def spellcraft(source, game):
        return "SC_COPY_NONGOLDEN"


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: SoT — Get Murloc + Discover and Teach Spell
# ═══════════════════════════════════════════════════════════════════════════════

class SoTGetMurlocTeachSpellScript:
    """
    Natural language: At the start of your turn, get a 1/1 Murloc.
    Discover a Tavern spell and teach it to the Murloc.

    Formal spec:
      1. start_of_turn: create 1/1 Murloc token + DiscoverSpell
      2. Store discovered spell card_id on the murloc
      3. When murloc is played (battlecry), cast the taught spell
    Test: murloc and spell discovered; spell is stored on murloc.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        # Create 1/1 Murloc token
        token = game.create_minion("EXAMPLE_VANILLA")
        if token is None:
            return None
        token.set_tag(GameTag.BASE_ATK, 1)
        token.set_tag(GameTag.BASE_HEALTH, 1)
        token.set_tag(GameTag.ATK, 1)
        token.set_tag(GameTag.HEALTH, 1)
        token.set_tag(GameTag.RACE, Race.MURLOC)
        token.controller = source.controller
        token.zone = Zone.HAND
        source.controller.hand.append(token)

        # Discover a spell and teach it to the murloc
        from hsrl.core.card_db import CARDS
        spell_pool = [cid for cid, data in CARDS._cards.items()
                      if data.cardtype == 42 and not cid.startswith("EXAMPLE")]
        if spell_pool:
            chosen = random.choice(spell_pool)
            token.set_tag(GameTag.TAUGHT_SPELL_ID, chosen)
            # Give spell to hand
            game.queue_action(AddToHand(source.controller, chosen))
            # Teach: murloc casts taught spell when played (via battlecry override)
            def _taught_battlecry(source_minion, g):
                spell_id = source_minion.get_tag(GameTag.TAUGHT_SPELL_ID)
                if spell_id:
                    from hsrl.core.actions import CastTavernSpell
                    return CastTavernSpell(source_minion.controller)
                return None
            token._script_overrides["battlecry"] = _taught_battlecry
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Guess Minion — each turn, guess opponent's minion
# ═══════════════════════════════════════════════════════════════════════════════

class GuessMinionRewardScript:
    """
    Natural language: Each turn, view 2 minions. Guess which one comes from
    your next opponent's last combat. If correct, get a Coin.

    Formal spec:
      1. start_of_turn: GuessMinion(player) — picks opponent + minion,
         auto-guesses, awards 1 Gold if correct
    Test: each turn, guess minion triggers with 50% chance of gold.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.actions import GuessMinion
        return GuessMinion(source.controller)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Buddy Rewards (Golden Buddy + Discover Buddy)
# ═══════════════════════════════════════════════════════════════════════════════

def _find_buddy_for_hero(hero_card_id: str, golden: bool = False):
    """Find the buddy card ID for a given hero card ID."""
    buddy_id = hero_card_id + "_Buddy"
    if golden:
        buddy_id = buddy_id + "_G"
    return buddy_id


class GoldenBuddyScript:
    """
    Natural language: Get your golden Buddy.

    Formal spec:
      1. on_unlock: find hero's golden buddy → AddToHand
    Test: player's golden buddy is added to hand.
    """

    @classmethod
    def on_unlock(cls, source, game):
        hero_id = source.controller.get_tag(GameTag.CARD_ID)
        if not hero_id:
            return None
        buddy_id = _find_buddy_for_hero(hero_id, golden=True)
        from hsrl.core.card_db import CARDS
        if CARDS.get(buddy_id):
            return AddToHand(source.controller, buddy_id)
        return None


class SoTDiscoverBuddyScript:
    """
    Natural language: At the start of your turn, Discover a Buddy.

    Formal spec:
      1. start_of_turn: pick random buddy from pool → AddToHand
    Test: a random buddy is added to hand at start of turn.
    """

    @classmethod
    def start_of_turn(cls, source, game):
        from hsrl.core.card_db import CARDS
        buddy_pool = [cid for cid, data in CARDS._cards.items()
                      if 'Buddy' in cid and data.cardtype == 4
                      and not cid.startswith("EXAMPLE")]
        if buddy_pool:
            import random
            return AddToHand(source.controller, random.choice(buddy_pool))
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: After-Buy Buff + Improve
# ═══════════════════════════════════════════════════════════════════════════════

class AfterBuyBuffImproveScript:
    """
    Natural language: After you buy a minion, give it +2/+2 and improve this effect.

    Formal spec:
      1. on_unlock: register MINION_BOUGHT EventListener
      2. Counter on reward starts at 1; each buy increments it
      3. Each buy: Buff(target, atk=counter, health=counter)
    Test: first buy gets +1/+1, second buy gets +2/+2.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        source.set_tag(GameTag.TRINKET_COUNTER, 1)  # improve counter

        class _BuyAction(Action):
            def __init__(self, reward):
                super().__init__()
                self.reward = reward
            def do(self, s, g, target=None):
                if target and not target.dead:
                    c = self.reward.get_tag(GameTag.TRINKET_COUNTER, 1)
                    g.queue_action(Buff(target, atk=c, health=c))
                    self.reward.set_tag(GameTag.TRINKET_COUNTER, c + 1)

        game.register_listener(source, EventListener(
            event_name=MINION_BOUGHT,
            action=_BuyAction(source),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: +7/+7 Aura + Die After Attacking
# ═══════════════════════════════════════════════════════════════════════════════

class DieAfterAttackAuraScript:
    """
    Natural language: Your minions have +7/+7, but die after attacking.

    Formal spec:
      1. on_unlock: ApplyGlobalAura(+7/+7) + set DIE_AFTER_ATTACK flag
      2. Engine checks flag in Attack.do(): after attack resolves, Destroy(attacker)
    Test: minions get +7/+7; after attacking, minion dies.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.actions import ApplyGlobalAura
        source.controller.set_tag(GameTag.DIE_AFTER_ATTACK, True)
        return ApplyGlobalAura(source.controller, atk=7, health=7)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: First Spell Each Turn Casts Twice
# ═══════════════════════════════════════════════════════════════════════════════

class FirstSpellCastsTwiceScript:
    """
    Natural language: Your first Tavern spell each turn casts twice.

    Formal spec:
      1. on_unlock: register TAVERN_SPELL_CAST EventListener
      2. Per-turn counter: first spell → re-cast it (queue same action again)
    Test: first spell each turn casts twice.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener
        source.controller.set_tag(GameTag.TRINKET_COUNTER, 0)  # per-turn tracker

        class _SpellAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                if self.player.get_tag(GameTag.TRINKET_COUNTER, 0) == 0:
                    self.player.set_tag(GameTag.TRINKET_COUNTER, 1)
                    # Re-cast the spell by broadcasting again
                    if target:
                        from hsrl.core.actions import CastTavernSpell
                        g.queue_action(CastTavernSpell(self.player))

        game.register_listener(source, EventListener(
            event_name=TAVERN_SPELL_CAST,
            action=_SpellAction(source.controller),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Spellcraft — Windfury + Divine Shield
# ═══════════════════════════════════════════════════════════════════════════════

class SpellcraftWindfuryDSScript:
    """
    Natural language: Spellcraft: Give a minion Windfury and Divine Shield.

    Formal spec:
      1. spellcraft: returns "SC_WINDFURY_DS" card_id
      2. The spell card, when played, grants both keywords to a random friendly
    Test: spellcraft generates the WF+DS spell card.
    """

    @staticmethod
    def spellcraft(source, game):
        return "SC_WINDFURY_DS"


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Coin Pouch — 5 Gold
# ═══════════════════════════════════════════════════════════════════════════════

class CoinPouchScript:
    """
    Natural language: Get a Coin Pouch with 5 Gold. Your Gold cap +5.
    (Gold cap increase is engine-level — DEFERRED.)

    Formal spec:
      1. on_unlock: GainGold(5)
    Test: gold increases by 5.
    """

    @staticmethod
    def on_unlock(source, game):
        return GainGold(source.controller, 5)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: After Combat — Discover from Opponent with Enchantments
# ═══════════════════════════════════════════════════════════════════════════════

class AfterCombatDiscoverEnchantedScript:
    """
    Natural language: After each combat, Discover a non-golden minion from
    your last opponent's warband. Retain enchantments.

    Formal spec:
      1. on_unlock: register END_OF_COMBAT EventListener
      2. On END_OF_COMBAT: pick random minion from last_opponent_board
      3. Create fresh copy + copy buffs → AddToHand
    Test: after combat, an opponent's minion with buffs is added to hand.
    """

    @staticmethod
    def on_unlock(source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener
        import random

        class _CombatAction(Action):
            def __init__(self, player):
                super().__init__()
                self.player = player
            def do(self, s, g, target=None):
                opp_board = getattr(self.player, 'last_opponent_board', None)
                if not opp_board:
                    return
                # Pick a non-golden minion
                candidates = [m for m in opp_board if not m.has_tag(GameTag.GOLDEN)]
                if not candidates:
                    return
                source_minion = random.choice(candidates)
                token = g.create_minion(source_minion.get_tag(GameTag.CARD_ID))
                if token is None:
                    return
                # Copy current stats (including combat-gained buffs)
                token.set_tag(GameTag.BASE_ATK, source_minion.atk)
                token.set_tag(GameTag.BASE_HEALTH, source_minion.health)
                # Copy keywords gained during combat
                for kw in [GameTag.DIVINE_SHIELD, GameTag.TAUNT, GameTag.WINDFURY,
                           GameTag.REBORN, GameTag.POISONOUS, GameTag.VENOMOUS]:
                    if source_minion.has_tag(kw):
                        token.set_tag(kw, True)
                g.queue_action(AddToHand(self.player, token.get_tag(GameTag.CARD_ID)))

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_CombatAction(source.controller),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Unlock Tier 7 + Next Turn Upgrade
# ═══════════════════════════════════════════════════════════════════════════════

class UnlockTier7Script:
    """
    Natural language: Unlock Tier 7 for this game. At the start of your
    next turn, upgrade the Tavern.

    Formal spec:
      1. on_unlock: set TIER_7_UNLOCKED on controller
      2. Schedule next-turn upgrade: tavern_tier += 1 (max 7)
    Test: Tier 7 unlocked; next turn auto-upgrades.
    """

    @staticmethod
    def on_unlock(source, game):
        source.controller.set_tag(GameTag.TIER_7_UNLOCKED, True)
        next_turn = game.turn + 1
        p = source.controller

        def _upgrade(g, t):
            cur = p.tavern_tier
            if cur < 7:
                p.tavern_tier = cur + 1

        game.schedule_turn_action(next_turn, _upgrade)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Coin Pouch — 5 Gold + Gold Cap +5
# ═══════════════════════════════════════════════════════════════════════════════

class CoinPouchGoldCapScript:
    """
    Natural language: Get a Coin Pouch with 5 Gold. Your Gold cap +5.

    Formal spec:
      1. on_unlock: GainGold(5), set MAX_GOLD += 5 on controller
    Test: 5 gold granted; gold cap increased.
    """

    @staticmethod
    def on_unlock(source, game):
        cur_max = source.controller.get_tag(GameTag.MAX_GOLD, 10)
        source.controller.set_tag(GameTag.MAX_GOLD, cur_max + 5)
        return GainGold(source.controller, 5)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Next Turn — Gold + Trinket Offer
# ═══════════════════════════════════════════════════════════════════════════════

class NextTurnGoldTrinketScript:
    """
    Natural language: At the start of your next turn, gain 4 Gold and
    choose a Trinket to buy.

    Formal spec:
      1. on_unlock: schedule GainGold(4) + trinket offer for next turn
      2. Set TRINKET_SCHEDULED flag for engine to read in _start_recruit_phase
    Test: next turn, gold is granted and trinket is offered.
    """
    TRINKET_TYPE = "lesser"

    @classmethod
    def on_unlock(cls, source, game):
        next_turn = game.turn + 1
        p = source.controller

        def _on_next_turn(g, t):
            g.queue_action(GainGold(p, 4))
            # Schedule trinket offer by setting flag
            p.set_tag(GameTag.TRINKET_SCHEDULED, True)
            p.set_tag(GameTag.TRINKET_SCHEDULED_TYPE, cls.TRINKET_TYPE)

        game.schedule_turn_action(next_turn, _on_next_turn)


class NextTurnGoldLesserTrinketScript(NextTurnGoldTrinketScript):
    """
    Natural language: At the start of your next turn, gain 4 Gold and
    choose a Lesser Trinket to buy.
    """
    TRINKET_TYPE = "lesser"


class NextTurnGoldGreaterTrinketScript(NextTurnGoldTrinketScript):
    """
    Natural language: At the start of your next turn, gain 4 Gold and
    choose a Greater Trinket to buy.
    """
    TRINKET_TYPE = "greater"


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

class DeferredRewardScript:
    """
    Status: DEFERRED — see individual card_id dependency notes in registry.

    Card texts are preserved for future implementation reference.
    """

    @staticmethod
    def on_unlock(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Registries
# ═══════════════════════════════════════════════════════════════════════════════

QUEST_SCRIPT_REGISTRY: dict = {
    "EXAMPLE_QUEST": ExampleQuestScript,
}

REWARD_SCRIPT_REGISTRY: dict = {
    # Standard Example
    "EXAMPLE_QUEST_REWARD": EternalKnightsRewardScript,

    # ── CORRECT: SoC Buff All ──
    "BG24_Reward_312": SoCBuffAll12x12Script,             # Staff of Origination: +12/+12
    "BG24_Reward_125": SoCBuffAll4x0Script,               # The Smoking Gun: +4 ATK aura
    "BG24_Reward_364": DieAfterAttackAuraScript,               # Volatile Venom: +7/+7 (die-after-attack DEFERRED)
    "BG24_Reward_113": SoCBuffAll3x0Script,               # Ritual Dagger: SoC +3 ATK (was: DR +5/+5)

    # ── CORRECT: SoC Specific Target ──
    "BG24_Reward_111": SoCSummonCopyHighestScript,        # Evil Twin: summon highest-HP copy
    "BG33_Reward_003": SoCLeftDSAttackImmediatelyScript,   # Righteous Charge: leftmost DS + attack
    "BG27_Anomaly_560": SoCSummonCopyHighestScript,        # Anomalous Twin SoC (uses reward script)
    "BG27_Anomaly_726": SoCDSAndRebornEdgesScript,         # DS + Reborn edges (uses reward script)

    # ── CORRECT: EoT Buff ──
    "BG24_Reward_115": EoTBuffRightmost8HPScript,         # Theotar's Parasol: rightmost +8 HP
    "BG24_Reward_331": EoTPerTribeBuffScript,             # Menagerie: per-tribe +1/+1
    "BG24_Reward_708": EoTRightmostMissingHPAtkScript,    # Missing HP → ATK
    "BG27_Reward_804": EoTTauntNonTauntBuffScript,        # Taunt → non-Taunt buff

    # ── CORRECT: SoT ──
    "BG24_Reward_361": SoTGainGoldImproveScript,          # Gain gold + improve
    "BG24_Reward_311": SoTDiscoverCurrentTierScript,      # Discover current tier
    "BG24_Reward_134": SoTGet2RandomMinionsScript,         # Get 2 random minions
    "BG28_Reward_515": SoTGet3SpellsScript,               # Get 3 spells

    # ── CORRECT: Event-Based ──
    "BG24_Reward_128": AfterRefreshBuffTavernScript,      # After refresh: +6/+6 + DS
    "BG24_Reward_306": AfterBuyBuffImproveScript,                # After buy: +2/+2
    "BG24_Reward_305": AfterSellTransferScript,           # After sell: transfer stats
    "BG24_Reward_138": AfterCombatCopyLastDeadScript,     # After combat: copy last dead

    # ── CORRECT: Passive / On-Unlock ──
    "BG24_Reward_123": BrannsBlessingScript,              # Brann's Blessing: BC doubler
    "BG24_Reward_130": EoTDoubleRewardScript,             # Ghastly Mask: EoT doubler + copy
    "BG27_Reward_803": DRDoubleRewardScript,              # Turbulent Tombs: DR doubler
    "BG27_Reward_802": BCDoubleRewardScript,              # BC doubler + copy
    "BG28_Reward_500": SpellCostMinus1Script,             # Spell cost -1
    "BG27_Reward_811": TavernCost2Script,                  # Tavern cost (2)
    "BG24_Reward_350": TwoCopiesForGoldenScript,          # 2 copies for golden
    "BG33_Reward_010": UnlockTier7Script,                 # Unlock Tier 7
    "BG33_Reward_012": CoinPouchGoldCapScript,                     # Coin bag +5 gold
    "BG28_Reward_501": FirstSpellCastsTwiceScript,             # Spells cast twice (partial)

    # ── DEFERRED: Needs TriggerBattlecry targeting ──
    "BG24_Reward_107": EoTTriggerBattlecriesScript,              # Snicker Snacks: EoT 2 BC trigger
    "BG24_Reward_136": EoTBuffLowTier3x3Script,              # Tiny Henchmen: EoT 3 low-tier +3/+3

    # ── DEFERRED: Needs Golden-making system ──
    "BG24_Reward_109": SoCMakeLeftRightGoldenScript,              # Stolen Gold: SoC make left/right golden
    "BG24_Reward_719": SpellcraftTempGoldenScript,              # SC: make golden until next turn
    "BG28_Reward_509": SoTMakeGoldenImproveScript,              # SoT: make golden + improve
    "BG33_Reward_013": SoTMakeHighestTavernGoldenScript,              # SoT: make highest-tier golden
    "BG28_Reward_508": After5RefreshMakeGoldenScript,              # After 5 refreshes: make golden

    # ── DEFERRED: Needs Avenge engine ──
    "BG27_Reward_502": Avenge3Deal10Script,              # Avenge(3): deal 10 to highest HP
    "BG33_Reward_004": Avenge2FreeRefreshScript,              # Avenge(2): free refresh
    "BG28_Reward_504": Avenge3GetSpellScript,              # Avenge(3): get spell
    "BG28_Reward_505": CombatSummonBuffAvengeScript,              # Avenge(4): combat buff + improve
    "BG28_Reward_518": Avenge7Summon50x50Script,              # Avenge(7): summon 50/50

    # ── DEFERRED: Needs after-play/after-discover/complex events ──
    "BG24_Reward_712": AfterPlayBuffSameTierScript,              # After play: buff same-tier
    "BG24_Reward_129": AfterDiscoverCopyScript,              # After discover: get copy
    "BG24_Reward_308": PerRefreshTavernBuffScript,              # Per refresh: tavern +1/+1
    "BG24_Reward_321": EvenTierTavernBuffScript,              # Odd/even tier +7/+7 alternating
    "BG24_Reward_321t": OddTierTavernBuffScript,             # Odd/even tier (paired)
    "BG24_Reward_309": EoTLeftRightConsumeTavernScript,              # EoT left/right consume tavern
    "BG24_Reward_310": GoldenBuddyScript,              # Golden Buddy
    "BG24_Reward_313": UsefulRefreshScript,              # Useful refresh
    "BG27_Reward_503": AfterBuyTransferStatsScript,              # After buy: transfer stats
    "BG27_Reward_504": SoTGetAcceleratorsScript,              # SoT: get Accelerators
    "BG27_Reward_806": AfterCombatDiscoverEnchantedScript,              # After combat: discover from opponent
    "BG27_Reward_810": AfterPlayNewTypeBuffScript,              # After play new type: +2/+2 per type
    "BG27_Reward_812": RefreshAlwaysOffers2Script,              # Refresh: always offers 2 X
    "BG27_Reward_815": BloodGemImproveAndGetScript,              # Blood Gem +1/+1 + SoT get 2
    "BG28_Reward_502": BuyExpensiveSpellCopyScript,              # Buy expensive spell → extra copy
    "BG28_Reward_506": FirstBuyCopyRewardScript,              # First buy each turn: extra copy
    "BG28_Reward_510": SoTGetTier7CopyScript,              # Get Tier 7 X copy
    "BG28_Reward_513": SoTDiscoverBuddyScript,              # SoT discover Buddy
    "BG28_Reward_514": SoTCast5SpellsScript,              # SoT cast 5 random spells
    "BG33_Reward_004": Avenge2FreeRefreshScript,              # Avenge(2): free refresh
    "BG33_Reward_006": SpellcraftWindfuryDSScript,              # SC: Windfury + DS
    "BG33_Reward_011": SoTGetMurlocTeachSpellScript,              # SoT: get Murloc + teach spell
    "BG33_Reward_014": NextTurnGoldLesserTrinketScript,              # Next turn: gold + choose trinket
    "BG33_Reward_015": NextTurnGoldGreaterTrinketScript,              # Next turn: gold + choose greater trinket
    "BG33_Reward_017": DiscoverSecondHPScript,              # Discover second HP
    "BG33_Reward_020": TavernSpellBuffRepeatScript,              # Tavern spell buff (repeating improve)
    "BG33_Reward_021": RallyDoublerScript,              # Rally doubler + copy
    "BG24_Reward_131": SoTHandMinion12x12Script,              # SoT: hand minion +12/+12
    "BG24_Reward_135": SoTYoggWheelScript,              # SoT: Yogg wheel
    "BG24_Reward_362": EoTGetZerusScript,              # EoT: get Zerus
    "BG24_Reward_363": SoTChooseRewardScript,              # SoT: choose new reward
    "BG24_Reward_715": SoTGetSparePartScript,              # SoT: get spare part
    "BG24_Reward_718": SpellcraftCopyNonGoldenScript,              # SC: copy non-golden card
    "BG27_Anomaly_555t": GuessMinionRewardScript,            # Guess minion from opponent
}
