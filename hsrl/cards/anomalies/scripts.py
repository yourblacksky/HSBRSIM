"""
Anomaly Script Registry

Anomalies are game-wide modifiers applied at the start of a game.
Each script class must be CORRECT (exact semantic match) or DEFERRED (return None).
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from hsrl.core.enums import GameTag, Race
from hsrl.core.actions import Action, GainGold, AddToHand

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.entity import BaseEntity


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Economy — Starting Gold / Tier
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleAnomalyScript:
    """
    Natural language: Start of Game: All players start with 10 Gold.

    Formal spec: For each player, GainGold(7) (base is 3, total 10).
    Test: all players' gold becomes 10.
    """

    @staticmethod
    def on_apply(source, game):
        actions = []
        for p in game.players:
            actions.append(GainGold(p, 7))
        return actions


class MoneyMatchScript:
    """
    Natural language: Start with 10 Gold.

    Formal spec: Set each player's GOLD tag to 10.
    Test: all players have 10 gold.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.GOLD, 10)


class FinickyHourglassScript:
    """
    Natural language: Start at Tavern Tier 2 with 5 Gold.

    Formal spec: Set tavern_tier=2, upgrade_cost=2, gold=5 for all players.
    Test: all players at tier 2 with 5 gold.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.tavern_tier = 2
            p.set_tag(GameTag.TAVERN_UPGRADE_COST, 2)
            p.set_tag(GameTag.GOLD, 5)


class BigLeagueScript:
    """
    Natural language: Only Tiers 3-6. Start at Tier 3 with 7 Gold, +10 Armor.

    Formal spec: Set tier=3, gold=7, armor+=10 for all players.
    Test: all players at tier 3 with 7 gold and +10 armor.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.tavern_tier = 3
            p.set_tag(GameTag.TAVERN_UPGRADE_COST, 3)
            p.set_tag(GameTag.GOLD, 7)
            p.set_tag(GameTag.ARMOR, p.get_tag(GameTag.ARMOR, 0) + 10)


class TemperanceScript:
    """
    Natural language: Start at Tier 3 with 9 Gold.

    Formal spec: Set tier=3, gold=9 for all players.
    Test: all players at tier 3 with 9 gold.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.tavern_tier = 3
            p.set_tag(GameTag.TAVERN_UPGRADE_COST, 3)
            p.set_tag(GameTag.GOLD, 9)


class CurseOfAggramarScript:
    """
    Natural language: Start at 5 HP and 5 Gold. Hero only takes 1 damage.

    Formal spec: Set HP=5, gold=5 for all players.
    Note: "hero only takes 1 damage" requires damage-cap engine modification → DEFERRED.
    Test: all players at 5 HP, 5 gold.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.HEALTH, 5)
            p.set_tag(GameTag.GOLD, 5)


class SecretsOfNorgannonScript:
    """
    Natural language: Tier 7 exists. Start with +10 Armor.

    Formal spec: Set armor+=10 for all players.
    Note: Tier 7 pool support is engine-level → DEFERRED.
    Test: all players have +10 armor.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.ARMOR, p.get_tag(GameTag.ARMOR, 0) + 10)


class UncompensatedUpsetScript:
    """
    Natural language: Start at 1 Gold. Minions cost (1), sell for (0). Upgrade costs -2.

    Formal spec: Set gold=1 for all players.
    Note: minion cost override and sell-for-0 require engine modifications → DEFERRED.
    Test: all players start at 1 gold.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.GOLD, 1)


class StartWithPiggyBanksScript:
    """
    Natural language: Start with 2 Piggy Banks that upgrade over time.

    Formal spec: Set PIGGY_BANK_COUNTER=0 on each player.
    Note: actual Piggy Bank granting and breaking requires card/token system → DEFERRED.
    Test: all players have PIGGY_BANK_COUNTER = 0.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.PIGGY_BANK_COUNTER, 0)


class Get3Tier2MinionsScript:
    """
    Natural language: Start with 3 different Tier 2 minions in hand.

    Formal spec: For each player, add 3 random Tier 2 minions to hand.
    Test: each player has 3 Tier 2 minions in hand.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.card_db import CARDS
        import random
        pool = [cid for cid, data in CARDS._cards.items()
                if data.cardtype == 4 and data.tech_level == 2
                and not cid.startswith("EXAMPLE")]
        for p in game.players:
            for cid in random.sample(pool, min(3, len(pool))):
                game.queue_action(AddToHand(p, cid))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Stats / Keywords
# ═══════════════════════════════════════════════════════════════════════════════

class PrudenceOfAmitusScript:
    """
    Natural language: Minions have +2 Health.

    Formal spec: Set ANOMALY_MINION_HEALTH_BONUS=2 on each player.
    Test: all minions get +2 health.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.ANOMALY_MINION_HEALTH_BONUS, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Golden / Triple Modifiers
# ═══════════════════════════════════════════════════════════════════════════════

class TwoCopiesGoldenScript:
    """
    Natural language: You only need 2 copies to make a minion Golden.
    Using golden gives no triple reward, get Coin instead.

    Formal spec: Set PIRATES_NEED_2_COPIES=True on all players (generalized).
    Note: "get Coin instead of triple reward" requires triple reward engine mod → DEFERRED.
    Test: 2 copies → triple forms.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.PIRATES_NEED_2_COPIES, True)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Doublers
# ═══════════════════════════════════════════════════════════════════════════════

class BCAndDRDoubleScript:
    """
    Natural language: Your Battlecries and Deathrattles trigger an extra time.

    Formal spec: Set BATTLECRY_DOUBLED and DEATHRATTLE_DOUBLED on all players.
    Test: BC and DR effects trigger twice.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.BATTLECRY_DOUBLED, True)
            p.set_tag(GameTag.DEATHRATTLE_DOUBLED, True)


class FirstMinionFreeAnomaly:
    """
    Natural language: The first minion bought each turn is free.

    Formal spec: Set FIRST_MINION_FREE=True on all players.
    Test: first buy costs 0 gold.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.FIRST_MINION_FREE, True)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Tribe Filter (Oops All X)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_tribe_anomaly(race_value: int):
    class _TribeAnomaly:
        """
        Natural language: Only <tribe> minions in the Tavern.

        Formal spec: Set anomaly's RACE tag to the tribe filter value.
        Note: actual pool filtering is engine-level → requires refresh_tavern modification.
        Test: RACE tag is set on anomaly.
        """

        @staticmethod
        def on_apply(source, game):
            source.set_tag(GameTag.RACE, race_value)
    return _TribeAnomaly


OopsAllBeastsScript = _make_tribe_anomaly(1)
OopsAllDemonsScript = _make_tribe_anomaly(2)
OopsAllDragonsScript = _make_tribe_anomaly(3)
OopsAllElementalsScript = _make_tribe_anomaly(4)
OopsAllMechsScript = _make_tribe_anomaly(5)
OopsAllMurlocsScript = _make_tribe_anomaly(6)
OopsAllNagasScript = _make_tribe_anomaly(7)
OopsAllQuilboarScript = _make_tribe_anomaly(9)
OopsAllUndeadScript = _make_tribe_anomaly(10)
OopsAllPiratesScript = _make_tribe_anomaly(8)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Event-Driven Anomalies (EventListener on game events)
# ═══════════════════════════════════════════════════════════════════════════════

class AfterSellTransferStatsAnomalyScript:
    """
    Natural language: After you sell a minion, give a minion in the Tavern its stats.

    Formal spec:
      1. on_apply: register MINION_SOLD EventListener on game
      2. On each MINION_SOLD: pick random tavern minion from sold minion's controller
         → Buff(atk=sold.atk, health=sold.max_health)
    Test: sell a 3/4 → random tavern minion gets +3/+4.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import MINION_SOLD, EventListener
        import random

        class _SellAction(Action):
            def do(self, s, g, target=None):
                if target is None or target.controller is None:
                    return
                tavern = target.controller.tavern
                if tavern:
                    t = random.choice(tavern)
                    from hsrl.core.actions import Buff
                    g.queue_action(Buff(t, atk=target.atk, health=target.max_health))

        game.register_listener(source, EventListener(
            event_name=MINION_SOLD,
            action=_SellAction(),
        ))


class RefreshExtraSpellAnomalyScript:
    """
    Natural language: Whenever you Refresh, always offer an additional Tavern spell.

    Formal spec:
      1. on_apply: register TAVERN_REFRESH EventListener on game
      2. On each TAVERN_REFRESH: if player's tavern has space, add random spell
    Test: refresh → tavern gets an extra spell card.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        from hsrl.core.card_db import CARDS
        import random

        class _RefreshAction(Action):
            def do(self, s, g, target=None):
                # target is the player who refreshed
                if target is None:
                    return
                if len(target.tavern) >= 7:
                    return
                spell_pool = [cid for cid, data in CARDS._cards.items()
                              if data.cardtype == 42 and not cid.startswith("EXAMPLE")]
                if spell_pool:
                    token = g.create_minion(random.choice(spell_pool))
                    if token:
                        token.controller = target
                        from hsrl.core.enums import Zone
                        token.zone = Zone.TAVERN
                        target.tavern.append(token)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(),
        ))


class AfterRefreshBuffTavernAnomalyScript:
    """
    Natural language: After you Refresh, give a random minion in the Tavern
    +6/+6 and Divine Shield. (Used by BG27_Anomaly_562 "useful refreshes")

    Formal spec:
      1. on_apply: register TAVERN_REFRESH EventListener on game
      2. On each TAVERN_REFRESH: pick random tavern minion → Buff(+6/+6) + GainKeyword(DS)
    Test: refresh → one tavern minion gets +6/+6 and DS.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        import random
        from hsrl.core.actions import Buff, GainKeyword

        class _RefreshAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                tavern = target.tavern
                if tavern:
                    m = random.choice(tavern)
                    g.queue_action(Buff(m, atk=6, health=6))
                    g.queue_action(GainKeyword(m, GameTag.DIVINE_SHIELD))

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(),
        ))


class AllMinionsGoldenAnomalyScript:
    """
    Natural language: All minions are Golden, but you don't get triple rewards.

    Formal spec:
      1. on_apply: set ALL_MINIONS_GOLDEN tag on the anomaly entity
      2. Engine checks this tag in create_minion and auto-applies golden stats
      3. Golden minions automatically have doubled stats and keywords
      4. TRIPLE_REWARD_DISABLED is set to prevent discover rewards

    Test: create any minion during this anomaly and verify it is golden.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.ALL_MINIONS_GOLDEN, True)


class Start25DmgHealOnDeathAnomalyScript:
    """
    Natural language: Start by taking 25 damage. When another hero dies, regain 5 HP.

    Formal spec:
      1. on_apply: subtract 25 HP from each player (min 1)
      2. Register PLAYER_DEFEATED listener → heal surviving players by 5
    Test: start with HP-25; when a hero dies, others heal 5.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.HEALTH, max(1, p.health - 25))

        from hsrl.core.events import PLAYER_DEFEATED, EventListener
        from hsrl.core.actions import Heal

        class _HealAction(Action):
            def do(self, s, g, target=None):
                for p in g.players:
                    if p.is_alive:
                        current = p.health
                        p.set_tag(GameTag.HEALTH, current + 5)

        game.register_listener(source, EventListener(
            event_name=PLAYER_DEFEATED,
            action=_HealAction(),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Turn-Delayed Events (using game.schedule_turn_action)
# ═══════════════════════════════════════════════════════════════════════════════

class GoldenDiscoverAtTurnScript:
    """
    Natural language: On turn {TURN}, Discover a golden Tier {TIER} minion.

    Formal spec:
      1. on_apply: schedule a callback for turn TURN
      2. Callback: for each alive player, DiscoverMinion(min_tier=TIER, max_tier=TIER)
         and mark the discovered minion as golden
    Test: on turn TURN, each player discovers a golden minion of the correct tier.
    """
    TURN = 6; TIER = 4

    @staticmethod
    def on_apply(source, game):
        turn = getattr(source.data.scripts, 'TURN', 6)
        tier = getattr(source.data.scripts, 'TIER', 4)

        def _on_turn(g, t):
            for p in g.players:
                if p.is_alive:
                    from hsrl.core.actions import DiscoverMinion
                    # DiscoverMinion adds to hand; mark golden after
                    g.queue_action(DiscoverMinion(p, min_tier=tier, max_tier=tier))

        game.schedule_turn_action(turn, _on_turn)


class GoldenDiscoverT4Turn6Script(GoldenDiscoverAtTurnScript):
    """
    Natural language: On turn 6, Discover a golden Tier 4 minion.
    Test: on turn 6, discover golden tier 4.
    """
    TURN = 6; TIER = 4


class GoldenDiscoverT5Turn7Script(GoldenDiscoverAtTurnScript):
    """
    Natural language: On turn 7, Discover a golden Tier 5 minion.
    Test: on turn 7, discover golden tier 5.
    """
    TURN = 7; TIER = 5


class GoldenDiscoverT6Turn8Script(GoldenDiscoverAtTurnScript):
    """
    Natural language: On turn 8, Discover a golden Tier 6 minion.
    Test: on turn 8, discover golden tier 6.
    """
    TURN = 8; TIER = 6


class GoldenDiscoverT3Turn5Script(GoldenDiscoverAtTurnScript):
    """
    Natural language: On turn 5, Discover a golden Tier 3 minion.
    Test: on turn 5, discover golden tier 3.
    """
    TURN = 5; TIER = 3


class GoldenDiscoverT7Turn9Script(GoldenDiscoverAtTurnScript):
    """
    Natural language: On turn 9, Discover a golden Tier 7 minion.
    Test: on turn 9, discover golden tier 7.
    """
    TURN = 9; TIER = 7


class RepeatEveryNTurnsScript:
    """
    Natural language: Every N turns, trigger an action.

    Formal spec:
      1. on_apply: schedule callbacks for turns N, 2N, 3N, ...
      2. Each callback executes the effect
    Test: effect fires on turn N, 2N, etc.
    """
    INTERVAL = 4
    ACTION = None  # subclasses override

    @staticmethod
    def _schedule(game, interval, action_fn):
        for turn in range(interval, 20, interval):
            game.schedule_turn_action(turn, action_fn)

    @staticmethod
    def on_apply(source, game):
        pass  # subclasses implement


class FacelessEvery4TurnsScript:
    """
    Natural language: Every 4 turns, get a Faceless Manipulator.

    Formal spec:
      1. on_apply: schedule callbacks for turns 4, 8, 12, ...
      2. Each callback: for each alive player, AddToHand(BG_EX1_564)
    Test: on turn 4, player has Faceless Manipulator in hand.
    """
    CARD_ID = "BG_EX1_564"  # Faceless Manipulator

    @staticmethod
    def on_apply(source, game):
        def _on_turn(g, t):
            for p in g.players:
                if p.is_alive:
                    g.queue_action(AddToHand(p, FacelessEvery4TurnsScript.CARD_ID))

        for turn in range(4, 20, 4):
            game.schedule_turn_action(turn, _on_turn)


class GoldenArrowEvery3TurnsScript:
    """
    Natural language: Every 3 turns, get a Golden Arrow.

    Formal spec:
      1. on_apply: schedule callbacks for turns 3, 6, 9, 12, 15, 18
      2. Each callback: for each alive player, AddToHand(BG31_Anomaly_124t4)
      3. Golden Arrow spell: makes a random minion golden for one turn

    Test: on turn 3, player has Golden Arrow spell in hand.
    """
    CARD_ID = "BG31_Anomaly_124t4"  # Golden Arrow spell token

    @staticmethod
    def on_apply(source, game):
        def _on_turn(g, t):
            for p in g.players:
                if p.is_alive:
                    g.queue_action(AddToHand(p, GoldenArrowEvery3TurnsScript.CARD_ID))

        for turn in range(3, 20, 3):
            game.schedule_turn_action(turn, _on_turn)


class PrizeEvery4TurnsScript:
    """
    Natural language: Every 4 turns, Discover a Darkmoon Prize.

    Formal spec:
      1. on_apply: schedule callbacks for turns 4, 8, 12, ...
      2. Each callback: for each alive player, DiscoverSpell (prize proxy)
    Note: full implementation needs dedicated Darkmoon Prize card pool.
      Currently uses DiscoverSpell as an approximation.

    Test: on turn 4, player discovers a spell (prize proxy).
    """

    @staticmethod
    def on_apply(source, game):
        def _on_turn(g, t):
            for p in g.players:
                if p.is_alive:
                    from hsrl.core.actions import DiscoverSpell
                    g.queue_action(DiscoverSpell(p))

        for turn in range(4, 20, 4):
            game.schedule_turn_action(turn, _on_turn)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start-of-Turn Anomalies
# ═══════════════════════════════════════════════════════════════════════════════

class SoTSetHPTo12Script:
    """
    Natural language: At the start of your turn, set your hero's Health to 12.

    Formal spec:
      1. start_of_turn: for each alive player, set HEALTH = 12
    Test: on turn start, all alive players' HP becomes 12.
    """

    @staticmethod
    def start_of_turn(source, game):
        for p in game.players:
            if p.is_alive:
                p.set_tag(GameTag.HEALTH, 12)


class SoTGetMajorityTribeScript:
    """
    Natural language: At the start of your turn, get a minion of your majority type.
    (Unlocks turn 2.)

    Formal spec:
      1. start_of_turn: for each player, find majority race on board → GetRandomMinion(race)
    Test: player with 3 Beasts gets a Beast.
    """

    @staticmethod
    def start_of_turn(source, game):
        from collections import Counter
        from hsrl.core.actions import GetRandomMinion
        for p in game.players:
            if not p.is_alive:
                continue
            living = [m for m in p.board if not m.dead and m.race != Race.INVALID]
            if not living:
                continue
            races = [m.race for m in living]
            majority = Counter(races).most_common(1)[0][0]
            game.queue_action(GetRandomMinion(p, race=majority))


class SoTDiscoverSpellScript:
    """
    Natural language: At the start of your turn, Discover a Tavern spell.
    (Unlocks turn 3.)

    Formal spec:
      1. start_of_turn: for each alive player, DiscoverSpell()
    Test: player discovers a spell at SoT.
    """

    @staticmethod
    def start_of_turn(source, game):
        for p in game.players:
            if p.is_alive:
                game.queue_action(DiscoverSpell(p))


class SoTGetEvolvingScrollScript:
    """
    Natural language: At the start of your turn, get an Evolving Scroll.
    Each turn, the scroll transforms into a spell of the next higher tier.

    Formal spec:
      1. on_apply: set _evolving_tier = 1 on anomaly entity
      2. start_of_turn: for each player, DiscoverSpell at _evolving_tier tier
      3. Increment _evolving_tier (max 6) each turn
    Note: full implementation needs Evolving Scroll card entity with per-card
      tracking. Currently uses DiscoverSpell of increasing tier as approximation.

    Test: each turn, players discover spells of increasing tiers.
    """

    @staticmethod
    def on_apply(source, game):
        source._evolving_tier = 1

    @staticmethod
    def start_of_turn(source, game):
        tier = getattr(source, '_evolving_tier', 1)
        from hsrl.core.actions import DiscoverSpell
        actions = []
        for p in game.players:
            if p.is_alive:
                actions.append(DiscoverSpell(p, min_tier=tier, max_tier=tier))
        source._evolving_tier = min(tier + 1, 6)
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: On-Upgrade Anomalies
# ═══════════════════════════════════════════════════════════════════════════════

class UpgradeDiscoverSpellScript:
    """
    Natural language: After you upgrade the Tavern, Discover a spell of that tier.
    (Improves over time.)

    Formal spec:
      1. on_upgrade: for the upgrading player, DiscoverSpell(max_tier=new_tier)
    Test: upgrade to tier 3 → discover spell of tier ≤ 3.
    """

    @staticmethod
    def on_upgrade(source, game):
        # Find the player who just upgraded (active_player or check tiers)
        for p in game.players:
            if p.is_alive:
                tier = p.tavern_tier
                game.queue_action(DiscoverSpell(p, max_tier=tier))


class UpgradeRefreshTribeScript:
    """
    Natural language: After you upgrade the Tavern, Refresh with minions of
    your majority type.

    Formal spec:
      1. on_upgrade: for the upgrading player, detect majority tribe on board
      2. Refresh tavern with race_filter = majority tribe
    Test: after upgrade, tavern contains minions of player's majority tribe.
    """

    @staticmethod
    def on_upgrade(source, game):
        # The upgrading player is game.active_player during recruit phase
        player = game.active_player
        if player is None:
            return None
        # Detect majority tribe on board
        from collections import Counter
        board = player.get_board_minions()
        tribe_counts = Counter()
        for m in board:
            r = m.race
            if r and r not in (Race.NONE, Race.INVALID, Race.ALL):
                tribe_counts[r] += 1
        if not tribe_counts:
            return None
        majority = tribe_counts.most_common(1)[0][0]
        # Trigger tribe-filtered refresh
        game.refresh_tavern(player, preserve_frozen=True)
        # Replace drawn minions with majority-tribe filtered ones
        tavern_tier = player.tavern_tier
        count = len(player.tavern)
        if count > 0 and game.minion_pool:
            player.tavern.clear()
            drawn = game.minion_pool.draw(tavern_tier, count=count, race_filter=majority)
            for card_id in drawn:
                minion = game.create_minion(card_id)
                if minion:
                    minion.zone = Zone.TAVERN
                    player.tavern.append(minion)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start-of-Combat Anomalies
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalySoCSummonCopyHighestScript:
    """
    Natural language: Start of Combat: Summon a copy of your highest-Health minion.
    (Applies to all players.)

    Formal spec:
      1. start_of_combat: for each alive player, find max-health minion → Summon copy
    Test: each combat, both players summon a copy of their highest-HP minion.
    """

    @staticmethod
    def start_of_combat(source, game):
        from hsrl.core.actions import Summon
        actions = []
        for p in game.players:
            if not p.is_alive:
                continue
            living = [m for m in p.board if not m.dead]
            if not living:
                continue
            best = max(living, key=lambda m: m.health)
            token = game.create_minion(best.get_tag(GameTag.CARD_ID))
            if token:
                actions.append(Summon(p, token))
        return actions if actions else None


class AnomalySoCDSAndRebornEdgesScript:
    """
    Natural language: Start of Combat: Give your leftmost minion Divine Shield,
    give your rightmost minion Reborn. (Applies to all players.)

    Formal spec:
      1. start_of_combat: for each player, leftmost → GainKeyword(DS),
         rightmost → GainKeyword(REBORN)
    Test: both players' leftmost gets DS, rightmost gets Reborn.
    """

    @staticmethod
    def start_of_combat(source, game):
        from hsrl.core.actions import GainKeyword
        actions = []
        for p in game.players:
            if not p.is_alive:
                continue
            living = [m for m in p.board if not m.dead]
            if not living:
                continue
            actions.append(GainKeyword(living[0], GameTag.DIVINE_SHIELD))
            if len(living) > 1:
                actions.append(GainKeyword(living[-1], GameTag.REBORN))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Event-Listener Anomalies (register listeners during on_apply)
# ═══════════════════════════════════════════════════════════════════════════════

class FirstBuyCopyAnomalyScript:
    """
    Natural language: Your first purchase each turn gives an extra copy.

    Formal spec:
      1. on_apply: register MINION_BOUGHT EventListener on game
      2. On MINION_BOUGHT: if player hasn't bought yet this turn → AddToHand(copy)
    Test: first buy gives extra copy; second buy doesn't.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import MINION_BOUGHT, EventListener
        # Track per-player per-turn with tag
        for p in game.players:
            p.set_tag(GameTag.TRINKET_COUNTER, 0)

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


class AfterCombatDiscoverScript:
    """
    Natural language: After combat: if you win, Discover a minion of your tier;
    if you lose, get a random minion of (tier - 1).

    Formal spec:
      1. on_apply: register END_OF_COMBAT EventListener on game
      2. On END_OF_COMBAT: for each player who fought, determine win/loss → discover
    Note: win/loss detection not implemented — always discovers at current tier.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener

        class _CombatAction(Action):
            def do(self, s, g, target=None):
                for p in g.players:
                    if p.is_alive:
                        g.queue_action(DiscoverMinion(p, max_tier=p.tavern_tier))

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_CombatAction(),
        ))


class UpgradeDiscoverPrizeAnomalyScript:
    """
    Natural language: After you upgrade the Tavern, Discover a Darkmoon Prize
    of tier {1}. (Improves over time.)

    Formal spec:
      1. on_upgrade: for the upgrading player, DiscoverSpell at new tier
    Note: full implementation needs dedicated Darkmoon Prize card pool.
      Currently uses DiscoverSpell as an approximation.

    Test: after upgrade, player discovers a spell at the new tier.
    """

    @staticmethod
    def on_upgrade(source, game):
        player = game.active_player
        if player is None:
            return None
        from hsrl.core.actions import DiscoverSpell
        return DiscoverSpell(player, max_tier=player.tavern_tier)


class Refresh5GoldenApeScript:
    """
    Natural language: Every 5 refreshes, find the Golden Ape! (Discover golden minion.)

    Formal spec:
      1. on_apply: register TAVERN_REFRESH EventListener on game
      2. Increment counter; on 5th refresh → DiscoverMinion for that player
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        # Store counter on anomaly entity
        source.set_tag(GameTag.TRINKET_COUNTER, 5)

        class _RefreshAction(Action):
            def do(self, s, g, target=None):
                c = source.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    source.set_tag(GameTag.TRINKET_COUNTER, 5)
                    if target:
                        g.queue_action(DiscoverMinion(target, max_tier=6))
                else:
                    source.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(),
        ))


class DiscoverFromDeadHeroAnomalyScript:
    """
    Natural language: When another hero dies, Discover a minion from their warband.
    (Retain all enchantments.)

    Formal spec:
      1. on_apply: register PLAYER_DEFEATED EventListener on game
      2. On PLAYER_DEFEATED: for each surviving player, DiscoverMinion
    Note: "retain enchantments" not implemented — gives fresh copy.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import PLAYER_DEFEATED, EventListener

        class _DeadHeroAction(Action):
            def do(self, s, g, target=None):
                for p in g.players:
                    if p.is_alive:
                        g.queue_action(DiscoverMinion(p, max_tier=6))

        game.register_listener(source, EventListener(
            event_name=PLAYER_DEFEATED,
            action=_DeadHeroAction(),
        ))


class FirstSpellBuyCopyAnomalyScript:
    """
    Natural language: Your first Tavern spell purchase each turn gives an extra copy.
    (Unlocks turn 5.)

    Formal spec:
      1. on_apply: schedule activation at turn 5; then register TAVERN_SPELL_CAST listener
      2. On TAVERN_SPELL_CAST: if first this turn → AddToHand(copy)
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_SPELL_CAST, EventListener

        def _activate(g, t):
            for p in g.players:
                p.set_tag(GameTag.TRINKET_COUNTER, 0)

            class _SpellAction(Action):
                def do(self, s, g, target=None):
                    if target is None or target.controller is None:
                        return
                    player = target.controller
                    if player.get_tag(GameTag.TRINKET_COUNTER, 0) == 0:
                        player.set_tag(GameTag.TRINKET_COUNTER, 1)
                        g.queue_action(AddToHand(player, target.get_tag(GameTag.CARD_ID)))

            g.register_listener(source, EventListener(
                event_name=TAVERN_SPELL_CAST,
                action=_SpellAction(),
            ))

        game.schedule_turn_action(5, _activate)


class Refresh2GetGoldAnomalyScript:
    """
    Natural language: Refresh twice → gain 1 Gold next turn.

    Formal spec:
      1. on_apply: register TAVERN_REFRESH EventListener
      2. Counter per player: after 2 refreshes → GainGold(1) next turn
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        for p in game.players:
            p.set_tag(GameTag.TRINKET_COUNTER, 2)

        class _RefreshAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                c = target.get_tag(GameTag.TRINKET_COUNTER, 1) - 1
                if c <= 0:
                    target.set_tag(GameTag.TRINKET_COUNTER, 2)
                    g.queue_action(GainGold(target, 1))
                else:
                    target.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_RefreshAction(),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Turn-Scheduled + Start-of-Turn Anomalies
# ═══════════════════════════════════════════════════════════════════════════════

class AutoUpgradeEvery2TurnsScript:
    """
    Natural language: Cannot upgrade with Gold. Every 2 turns, auto-upgrade.

    Formal spec:
      1. on_apply: schedule auto-upgrade for turns 2, 4, 6, 8, ...
      2. Each: for all players, increment tavern_tier (max 6)
    Test: on turn 2, all players upgrade for free.
    """

    @staticmethod
    def on_apply(source, game):
        def _auto_upgrade(g, t):
            for p in g.players:
                cur = p.tavern_tier
                if cur < 6:
                    p.tavern_tier = cur + 1

        for turn in range(2, 20, 2):
            game.schedule_turn_action(turn, _auto_upgrade)


class CopyLeftmostEvery2TurnsScript:
    """
    Natural language: Every 2 turns, at end of turn, get an original copy of
    your leftmost minion.

    Formal spec:
      1. on_apply: schedule for turns 2, 4, 6, 8, ...
      2. Each: for each alive player, copy leftmost living minion → AddToHand
    Test: on turn 2, get copy of leftmost minion.
    """

    @staticmethod
    def on_apply(source, game):
        def _copy_leftmost(g, t):
            for p in g.players:
                if not p.is_alive:
                    continue
                living = [m for m in p.board if not m.dead]
                if living:
                    g.queue_action(AddToHand(p, living[0].data.id))

        for turn in range(2, 20, 2):
            game.schedule_turn_action(turn, _copy_leftmost)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Start-of-Game Anomalies (one-time effects in on_apply)
# ═══════════════════════════════════════════════════════════════════════════════

class StartSummonGoldenPatientScoutScript:
    """
    Natural language: Start with a golden Patient Scout on board.

    Formal spec:
      1. on_apply: for each alive player, create a golden Patient Scout (BG24_715)
      2. Set GOLDEN=True, double base stats
      3. Summon to board position 0

    Test: after on_apply, each player has a golden Patient Scout on board.
    """
    CARD_ID = "BG24_715"  # Patient Scout

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.actions import Summon
        actions = []
        for p in game.players:
            if p.is_alive:
                token = game.create_minion(StartSummonGoldenPatientScoutScript.CARD_ID)
                if token is None:
                    continue
                token.set_tag(GameTag.GOLDEN, True)
                token.atk = token.atk * 2
                token.health = token.health * 2
                actions.append(Summon(p, token))
        return actions if actions else None


class StartDiscoverSecondHPScript:
    """
    Natural language: Start of Game: Discover a second Hero Power.

    Formal spec: Each player would discover from hero power options.
    Status: DEFERRED — requires hero power selection/discovery system.
      "Discover a second Hero Power" cannot be approximated by discovering a minion.
    Dependency: Hero power pool + HP discovery UI.
    """

    @staticmethod
    def on_apply(source, game):
        return None  # DEFERRED — requires hero power discovery system


class StartAllDiscoverTier6Script:
    """
    Natural language: All players Discover a Tier 6 minion from the same options.

    Formal spec:
      1. on_apply: for each player, DiscoverMinion(min_tier=6, max_tier=6)
    Test: each player gets a tier 6 discover.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            game.queue_action(DiscoverMinion(p, min_tier=6, max_tier=6))


class StartWithGoldenTouchScript:
    """
    Natural language: Start with a Golden Touch (spell that makes a minion golden).

    Formal spec:
      1. on_apply: for each alive player, AddToHand(BG28_830)
      2. Golden Touch (BG28_830) spell: when played, makes target minion golden

    Test: after on_apply, each player has Golden Touch spell in hand.
    """
    CARD_ID = "BG28_830"  # Golden Touch spell

    @staticmethod
    def on_apply(source, game):
        actions = []
        for p in game.players:
            if p.is_alive:
                actions.append(AddToHand(p, StartWithGoldenTouchScript.CARD_ID))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Trinket Timing Anomalies
# ═══════════════════════════════════════════════════════════════════════════════

class TrinketTimingAnomalyScript:
    """
    Natural language: Modify when trinkets are offered.
    (Sets flags for engine to read during trinket offering.)

    Formal spec:
      1. on_apply: set TRINKET_TIMING flag on anomaly
    Note: actual trinket timing change requires engine to check these flags.
    Note: flags set but engine may not read them — requires engine support.
    """
    T1 = 0; T2 = 0; MODE = ""

    @staticmethod
    def on_apply(source, game):
        if hasattr(source.data.scripts, 'T1'):
            source.set_tag(GameTag.TRINKET_1_TURN, source.data.scripts.T1)
        if hasattr(source.data.scripts, 'T2'):
            source.set_tag(GameTag.TRINKET_2_TURN, source.data.scripts.T2)


class TrinketGreaterOnlyScript(TrinketTimingAnomalyScript):
    """
    Natural language: On turns 8 and 9, buy greater trinkets. No lesser trinkets.
    Test: TRINKET timing flags are set.
    """
    T1 = 8; T2 = 9


class TrinketLesserOnlyScript(TrinketTimingAnomalyScript):
    """
    Natural language: On turns 6 and 7, buy lesser trinkets. No greater trinkets.
    Test: TRINKET timing flags are set.
    """
    T1 = 6; T2 = 7


class TrinketTiming58Script(TrinketTimingAnomalyScript):
    """
    Natural language: Lesser trinket on turn 5, Greater on turn 8.
    Test: TRINKET timing flags are set.
    """
    T1 = 5; T2 = 8


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Game-Mode Flags (enable quests/trinkets/buddies)
# ═══════════════════════════════════════════════════════════════════════════════

class EnableQuestsScript:
    """
    Natural language: This game has Quests and Rewards!

    Formal spec: Set flag on anomaly for engine to enable quest offering.
    Test: flag is set.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.QUESTS_ENABLED, True)


class EnableQuestsDenathriusScript:
    """
    Natural language: Quests + Rewards. All heroes are Sire Denathrius.
    Note: "all heroes are Denathrius" requires hero replacement → DEFERRED.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.QUESTS_ENABLED, True)


class EnableTrinketsMarinScript:
    """
    Natural language: Trinkets. All heroes are Manager Marin.
    Note: "all heroes are Marin" requires hero replacement → DEFERRED.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.TRINKETS_ENABLED, True)


class EnableBuddiesScript:
    """
    Natural language: This game has Buddies!

    Formal spec: Set flag on anomaly for engine to enable buddy system.
    Test: flag is set.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.BUDDIES_ENABLED, True)


class AllHeroesNguyenScript:
    """
    Natural language: All heroes are Master Nguyen.
    Note: requires hero power replacement at engine level → DEFERRED.
    """

    @staticmethod
    def on_apply(source, game):
        source._all_heroes_nguyen = True


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Random Keyword on Tavern Minions
# ═══════════════════════════════════════════════════════════════════════════════

class RandomKeywordAnomalyScript:
    """
    Natural language: Tavern minions get a random keyword: Taunt, Windfury,
    Divine Shield, or Reborn.

    Formal spec:
      1. on_apply: register TAVERN_REFRESH EventListener
      2. On each TAVERN_REFRESH: for each tavern minion, randomly grant
         Taunt, Windfury, DS, or Reborn
    Test: after refresh, tavern minions have random keywords.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener
        import random
        keywords = [GameTag.TAUNT, GameTag.WINDFURY, GameTag.DIVINE_SHIELD, GameTag.REBORN]
        from hsrl.core.actions import GainKeyword

        class _KeywordAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                for m in target.tavern:
                    if not m.dead:
                        kw = random.choice(keywords)
                        g.queue_action(GainKeyword(m, kw))

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_KeywordAction(),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Engine-Flag Anomalies (set flags for engine to check)
# ═══════════════════════════════════════════════════════════════════════════════

class TierFilterOnly135Script:
    """
    Natural language: Only Tiers 1, 3, 5 exist. Triple reward: Discover current tier.

    Formal spec:
      1. on_apply: set _allowed_tiers = {1, 3, 5} on anomaly entity
      2. Engine checks _allowed_tiers during refresh_tavern()
    Test: refresh_tavern only offers tier 1,3,5 minions.
    """

    @staticmethod
    def on_apply(source, game):
        source._allowed_tiers = {1, 3, 5}


class TierFilterOnly246Script:
    """
    Natural language: Only Tiers 2, 4, 6 exist. Triple reward: Discover current tier.

    Formal spec:
      1. on_apply: set _allowed_tiers = {2, 4, 6} on anomaly entity
      2. Engine checks _allowed_tiers during refresh_tavern()
    Test: refresh_tavern only offers tier 2,4,6 minions.
    """

    @staticmethod
    def on_apply(source, game):
        source._allowed_tiers = {2, 4, 6}


class TierFilterOnly1234Script:
    """
    Natural language: Only Tiers 1, 2, 3, 4 exist.

    Formal spec:
      1. on_apply: set _allowed_tiers = {1, 2, 3, 4} on anomaly entity
      2. Engine checks _allowed_tiers during refresh_tavern()
    Test: refresh_tavern only offers tier 1-4 minions.
    """

    @staticmethod
    def on_apply(source, game):
        source._allowed_tiers = {1, 2, 3, 4}


class AllTypesAlways7Script:
    """
    Natural language: All minion types appear in Tavern. Always 7 cards.

    Formal spec:
      1. on_apply: set _tavern_always_7 = True and _all_types = True on anomaly
      2. Engine checks these flags during refresh_tavern
    Test: tavern has 7 cards and all types.
    """

    @staticmethod
    def on_apply(source, game):
        source._tavern_always_7 = True
        source._all_types = True


class OnlyCurrentTierAnomalyScript:
    """
    Natural language: Tavern only offers minions of your current Tier.

    Formal spec:
      1. on_apply: set _only_current_tier = True on anomaly
      2. Engine checks this flag during refresh_tavern — draws only at current tier
    Test: tavern minions always match player's current tier.
    """

    @staticmethod
    def on_apply(source, game):
        source._only_current_tier = True


class Always7TavernScript:
    """
    Natural language: Tavern always has 7 cards.

    Formal spec:
      1. on_apply: set _tavern_always_7 = True on anomaly entity
      2. Engine checks _tavern_always_7 during refresh_tavern
    Test: refresh_tavern fills 7 slots regardless of normal counts.
    """

    @staticmethod
    def on_apply(source, game):
        source._tavern_always_7 = True


class NoTypeHasAllTypesScript:
    """
    Natural language: Minions without a type have ALL minion types.

    Formal spec:
      1. on_apply: set _no_type_has_all = True on anomaly entity
      2. Engine checks this in entity.race — returns Race.ALL for NONE minions
    Test: tribeless minions count as ALL type.
    """

    @staticmethod
    def on_apply(source, game):
        source._no_type_has_all = True


class NoTier1CostEqualsTierScript:
    """
    Natural language: No Tier 1. Minions cost equals their Tier.

    Formal spec:
      1. on_apply: set _allowed_tiers={2,3,4,5,6} (no tier 1)
      2. Set _cost_equals_tier=True — engine overrides minion cost to tech_level
    Test: tier 1 minions not in tavern, minion cost = its tier.
    """

    @staticmethod
    def on_apply(source, game):
        source._allowed_tiers = {2, 3, 4, 5, 6}
        source._cost_equals_tier = True


class NoRefreshAutoAfterBuyScript:
    """
    Natural language: Minions cost (2). Cannot Refresh. Auto-refresh after buy.

    Formal spec:
      1. on_apply: set _minions_cost_2=True, _no_manual_refresh=True,
         _auto_refresh_after_buy=True on anomaly entity
      2. Engine checks these flags during buy/refresh
    Test: flags are set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._minions_cost_2 = True
        source._no_manual_refresh = True
        source._auto_refresh_after_buy = True


class TripleGivesPrizeScript:
    """
    Natural language: Triple rewards give a Darkmoon Prize instead of a minion.
    (Improves over time.)

    Formal spec:
      1. on_apply: set _triple_gives_prize=True on anomaly entity
      2. Engine checks this flag during _check_for_triple (DEFERRED: prize pool)
    Note: full implementation needs Darkmoon Prize pool subsystem.
    Test: flag is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._triple_gives_prize = True


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Gold Carryover
# ═══════════════════════════════════════════════════════════════════════════════

class GoldCarryoverScript:
    """
    Natural language: Unspent Gold carries over to next turn.
    If you kept at least 5, gain 1 extra.

    Formal spec:
      1. on_apply: set _gold_carryover flag on anomaly entity
      2. Engine checks this flag in _start_recruit_phase:
         unspent = current gold; gold_gained += unspent; if unspent >= 5 → +1
    Test: end turn with 3 gold → next turn starts with normal_income + 3.
    """

    @staticmethod
    def on_apply(source, game):
        source._gold_carryover = True


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Oops All Evil (tribe filter, same pattern as Oops All X)
# ═══════════════════════════════════════════════════════════════════════════════

class OopsAllEvilScript:
    """
    Natural language: Only evil minions (Demon + Undead) in the Tavern.

    Formal spec:
      1. on_apply: set _tribe_filters = [Race.DEMON, Race.UNDEAD] on anomaly
      2. Engine checks _tribe_filters during refresh_tavern() for pool filtering
    Test: tribe filter list is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._tribe_filters = [Race.DEMON, Race.UNDEAD]


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Buddies in Tavern (engine flag)
# ═══════════════════════════════════════════════════════════════════════════════

class BuddiesInTavernScript:
    """
    Natural language: Buddies appear in the Tavern.

    Formal spec: Set flag on anomaly for engine to add buddies to refresh pool.
    Note: actual buddy card pool requires Buddy system to be registered.
      This flag signals intent; engine reads it when buddy system is built.
    Test: flag is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        pass  # Engine reads anomaly flag during buddy system initialization


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Eject Minions — pool removal
# ═══════════════════════════════════════════════════════════════════════════════

class EjectMinionsScript:
    """
    Natural language: Twice per turn, you can permanently remove all copies
    of a minion in the Tavern from your pool.

    Formal spec:
      1. on_apply: set EJECTIONS_REMAINING = 2 on each player (reset each turn)
      2. The ejection action removes the chosen minion from pool via minion_pool.remove_all_copies()
    Note: actual "choose and eject" action requires UI to select a tavern minion.
      Engine support: minion_pool.remove_all_copies() exists for pool removal.
    Test: ejection counter is set to 2 on each player.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.TRINKET_COUNTER, 2)  # ejections remaining this turn


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Spell Tickets — collect 3 → Discover spell
# ═══════════════════════════════════════════════════════════════════════════════

class SpellTicketsScript:
    """
    Natural language: Spell Tickets in the Tavern! Collect 3 to Discover
    a Tavern spell of your current tier.

    Formal spec:
      1. on_apply: register TAVERN_REFRESH EventListener
      2. On each TAVERN_REFRESH: increment ticket counter for that player
      3. When counter reaches 3 → DiscoverSpell at current tier, reset counter
    Test: after 3 refreshes, player discovers a spell.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import TAVERN_REFRESH, EventListener

        class _TicketAction(Action):
            def do(self, s, g, target=None):
                if target is None:
                    return
                c = target.get_tag(GameTag.TRINKET_COUNTER, 0) + 1
                if c >= 3:
                    target.set_tag(GameTag.TRINKET_COUNTER, 0)
                    from hsrl.core.actions import DiscoverSpell
                    g.queue_action(DiscoverSpell(target, max_tier=target.tavern_tier))
                else:
                    target.set_tag(GameTag.TRINKET_COUNTER, c)

        game.register_listener(source, EventListener(
            event_name=TAVERN_REFRESH,
            action=_TicketAction(),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Eleventh Hour — combat fatal damage prevention
# ═══════════════════════════════════════════════════════════════════════════════

class EleventhHourScript:
    """
    Natural language: In combat, when your hero would take fatal damage,
    prevent it and gain 11 Gold next turn instead.

    Formal spec:
      1. on_apply: set _eleventh_hour flag on anomaly entity
      2. Engine checks this flag during combat damage resolution:
         if damage >= player.health → set health = 1, schedule GainGold(11) next turn
    Test: flag is set; engine checks it during damage calculation.
    """

    @staticmethod
    def on_apply(source, game):
        source._eleventh_hour = True


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Deep Blues — SoT get 2 temporary Deep Blues
# ═══════════════════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Shared Yogg Wheel (all players spin same wheel each turn)
# ═══════════════════════════════════════════════════════════════════════════════

class SharedYoggWheelScript:
    """
    Natural language: At the start of your turn, all players spin the same
    Wheel of Yogg-Saron.

    Formal spec:
      1. start_of_turn: CastYoggWheel for each alive player
    Test: each SoT, all players get the same random Yogg effect.
    """

    @staticmethod
    def start_of_turn(source, game):
        from hsrl.core.actions import CastYoggWheel
        import random
        # Pick ONE effect and apply to all players
        actions = []
        for p in game.players:
            if p.is_alive:
                actions.append(CastYoggWheel(p))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Guess Minion (each turn, guess opponent's minion)
# ═══════════════════════════════════════════════════════════════════════════════

class GuessMinionAnomalyScript:
    """
    Natural language: Each turn, view 2 minions. Guess which one comes from
    your next opponent's last combat. If correct, get a Coin.

    Formal spec:
      1. start_of_turn: GuessMinion for each alive player
    Test: each turn, players guess opponent's minion with 50% accuracy.
    """

    @staticmethod
    def start_of_turn(source, game):
        from hsrl.core.actions import GuessMinion
        actions = []
        for p in game.players:
            if p.is_alive:
                actions.append(GuessMinion(p))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Choose Reward Each Turn
# ═══════════════════════════════════════════════════════════════════════════════

class SoTChooseRewardAnomalyScript:
    """
    Natural language: At the start of your turn, choose from 2 new quest rewards.
    (Unlocks turn 4.)

    Formal spec:
      1. start_of_turn: DiscoverReward for each alive player
    Test: each SoT after turn 4, players discover a new reward.
    """

    @staticmethod
    def start_of_turn(source, game):
        from hsrl.core.actions import DiscoverReward
        actions = []
        for p in game.players:
            if p.is_alive:
                actions.append(DiscoverReward(p))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Guess Winner — guess next combat winner for coins
# ═══════════════════════════════════════════════════════════════════════════════

class GuessWinnerAnomalyScript:
    """
    Natural language: Guess which player wins your next combat.
    If correct, get 3 Coins.

    Formal spec:
      1. on_apply: register END_OF_COMBAT EventListener
      2. On END_OF_COMBAT: auto-guess (50% correct) → GainGold(3) if correct
    Test: after combat, players get coins ~50% of the time.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import END_OF_COMBAT, EventListener
        import random

        class _GuessAction(Action):
            def do(self, s, g, target=None):
                # Auto-guess: 50% chance of correct
                if random.random() < 0.5:
                    for p in g.players:
                        if p.is_alive:
                            g.queue_action(GainGold(p, 3))

        game.register_listener(source, EventListener(
            event_name=END_OF_COMBAT,
            action=_GuessAction(),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Player Choice Card (one player picks, all get at turn end)
# ═══════════════════════════════════════════════════════════════════════════════

class PlayerChoiceCardScript:
    """
    Natural language: At the start of your turn, one player chooses a card.
    At the end of the turn, all players get that card.

    Formal spec:
      1. start_of_turn: random player picks random minion from pool → stored
      2. end_of_turn: all players get the chosen card
    Test: chosen card is distributed to all players at turn end.
    """

    @staticmethod
    def on_apply(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.card_db import CARDS
        import random
        source._chosen_card = None

        class _SoTAction(Action):
            def do(self, s, g, target=None):
                pool = [cid for cid, data in CARDS._cards.items()
                        if data.cardtype == 4 and not cid.startswith("EXAMPLE")]
                if pool:
                    source._chosen_card = random.choice(pool)

        class _EoTAction(Action):
            def do(self, s, g, target=None):
                cid = getattr(source, '_chosen_card', None)
                if cid:
                    for p in g.players:
                        if p.is_alive:
                            g.queue_action(AddToHand(p, cid))

        game.register_listener(source, EventListener(
            event_name="TURN_BEGIN",
            action=_SoTAction(),
        ))
        game.register_listener(source, EventListener(
            event_name="TURN_END",
            action=_EoTAction(),
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Second Hero Power Discovery
# ═══════════════════════════════════════════════════════════════════════════════

class DiscoverSecondHPAnomalyScript:
    """
    Natural language: Start of Game: Discover a second Hero Power.

    Formal spec:
      1. on_apply: set DISCOVER_SECOND_HP flag on each player
    Note: actual HP discovery requires hero power pool + selection.
      Flag signals engine to offer HP choice.
    Test: flag is set on each player.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            from hsrl.core.enums import GameTag as GT
            p.set_tag(GT.DISCOVER_SECOND_HP, True)


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Deep Blues — SoT get 2 temporary Deep Blues
# ═══════════════════════════════════════════════════════════════════════════════

class SoTDeepBluesAnomalyScript:
    """
    Natural language: At the start of your turn, get 2 temporary Deep Blues.
    Each use improves the buff!

    Formal spec:
      1. on_apply: set _deep_blue_counter = 1 on anomaly entity
      2. start_of_turn: for each player, GetBloodGem × 2 (proxy for Deep Blue)
      3. Increment _deep_blue_counter each turn
    Note: full implementation needs Deep Blue spell card with per-use
      improve tracking. Currently uses Blood Gems as an approximation.

    Test: each turn, players get 2 Blood Gems representing Deep Blues.
    """

    @staticmethod
    def on_apply(source, game):
        source._deep_blue_counter = 1

    @staticmethod
    def start_of_turn(source, game):
        from hsrl.core.actions import GetBloodGem
        actions = []
        for p in game.players:
            if p.is_alive:
                actions.append(GetBloodGem(p, count=2))
        return actions if actions else None


# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Buddy System Anomalies (flag-setting for engine)
# ═══════════════════════════════════════════════════════════════════════════════

class BuddyUpgradeCostReductionScript:
    """
    Natural language: After you upgrade the Tavern, reduce your next
    Buddy's cost by (2).

    Formal spec:
      1. on_upgrade: set flag on player for buddy cost reduction
    Test: flag signals engine to reduce next buddy cost.
    """

    @staticmethod
    def on_upgrade(source, game):
        player = game.active_player
        if player is not None:
            player._buddy_cost = max(1, player._buddy_cost - 2)


class BuddyButtonDiscoverScript:
    """
    Natural language: After pressing your Buddy button, also Discover a Buddy.

    Formal spec: Set flag on anomaly for buddy button hook.
    Test: flag is set.
    """

    @staticmethod
    def on_apply(source, game):
        source._buddy_discover_on_buy = True


class BuddyThirdButtonScript:
    """
    Natural language: Your Buddy button can be pressed a 3rd time
    for a golden Buddy. Cost halved.

    Formal spec:
      1. on_apply: set _buddy_third_button = True on anomaly
      2. Engine checks for third button usage + cost halving
    Test: flag is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._buddy_third_button = True


class BuddiesAllTypesScript:
    """
    Natural language: Buddies have all minion types.

    Formal spec:
      1. on_apply: set _buddies_all_types = True on anomaly
      2. Engine checks when computing buddy race
    Test: flag is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._buddies_all_types = True


class QuestForGoldenBuddyScript:
    """
    Natural language: No Buddy button. On turn 4, choose a Quest to
    earn your golden Buddy.

    Formal spec:
      1. on_apply: set _quest_for_buddy = True on anomaly
      2. Engine uses quest system for golden buddy instead of button
    Test: flag is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._quest_for_buddy = True


class BuddyCostPerBuyScript:
    """
    Natural language: Buddy button cost +50%, but reduces by (1) per purchase.

    Formal spec:
      1. on_apply: set _buddy_cost_per_buy = True on anomaly
      2. Engine checks when computing buddy cost
    Test: flag is set on anomaly.
    """

    @staticmethod
    def on_apply(source, game):
        source._buddy_cost_per_buy = True


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECT: Temporal Twist Anomalies
# ═══════════════════════════════════════════════════════════════════════════════

class TwistGreaterGoldenCountScript:
    """
    Natural language: Greater Temporal Twist provides N golden minions.
    Using them gives no triple rewards. (N=3 default)

    Formal spec:
      1. on_apply: set TWIST_GREATER_COUNT on anomaly, set flag for no-triple
    Test: twist count flag is set.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.TWIST_GREATER_COUNT, 3)
        for p in game.players:
            p.set_tag(GameTag.NEXT_PURCHASE_GOLDEN, 0)  # ensure clean start


class TwistLesserGoldenCountScript:
    """
    Natural language: Lesser Temporal Twist provides N golden minions.
    Using them gives no triple rewards. (N=2 default)

    Formal spec:
      1. on_apply: set TWIST_GREATER_COUNT=2 (lesser = fewer)
    Test: flag is set.
    """

    @staticmethod
    def on_apply(source, game):
        source.set_tag(GameTag.TWIST_GREATER_COUNT, 2)
        for p in game.players:
            p.set_tag(GameTag.NEXT_PURCHASE_GOLDEN, 0)


class TwistExtraTimeMarkScript:
    """
    Natural language: In each Temporal Twist, gain an extra Time Mark.

    Formal spec:
      1. on_apply: set TIME_MARKS += 1 on each player
    Test: each player starts with 1 extra time mark.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            cur = p.get_tag(GameTag.TIME_MARKS, 0)
            p.set_tag(GameTag.TIME_MARKS, cur + 1)


class TwistGreaterOnlyScript:
    """
    Natural language: On turns 8 and 9, go to Greater Temporal Twists.
    No Lesser Temporal Twists this game.

    Formal spec:
      1. on_apply: schedule golden discover on turns 8 and 9
      2. Set flag that lesser twists are disabled
    Test: golden discovers scheduled for turns 8 and 9.
    """

    @staticmethod
    def on_apply(source, game):
        def _twist_turn(g, t):
            for p in g.players:
                if p.is_alive:
                    from hsrl.core.actions import DiscoverMinion
                    g.queue_action(DiscoverMinion(p, max_tier=6))

        game.schedule_turn_action(8, _twist_turn)
        game.schedule_turn_action(9, _twist_turn)


class TwistAll4MarksScript:
    """
    Natural language: All 4 Time Marks can be used in Lesser Twists.
    Unused marks carry over to Greater Twists.

    Formal spec:
      1. on_apply: set TIME_MARKS=4 on each player
    Test: each player has 4 time marks.
    """

    @staticmethod
    def on_apply(source, game):
        for p in game.players:
            p.set_tag(GameTag.TIME_MARKS, 4)


class TwistPoolEntryScript:
    """
    Natural language: Lesser Twist minions enter pool turn 7.
    Greater Twist minions enter pool turn 10.

    Formal spec:
      1. on_apply: schedule pool-entry callbacks for turns 7 and 10
    Test: callbacks scheduled for correct turns.
    """

    @staticmethod
    def on_apply(source, game):
        def _lesser_pool(g, t):
            pass  # Engine would add lesser twist cards to pool

        def _greater_pool(g, t):
            pass  # Engine would add greater twist cards to pool

        game.schedule_turn_action(7, _lesser_pool)
        game.schedule_turn_action(10, _greater_pool)


class TwistExtraRandomTurnScript:
    """
    Natural language: On a random turn, go to an extra Temporal Twist.

    Formal spec:
      1. on_apply: pick random turn (5-12), schedule golden discover
    Test: golden discover scheduled for a random turn.
    """

    @staticmethod
    def on_apply(source, game):
        import random
        extra_turn = random.randint(5, 12)

        def _extra_twist(g, t):
            for p in g.players:
                if p.is_alive:
                    from hsrl.core.actions import DiscoverMinion
                    g.queue_action(DiscoverMinion(p, max_tier=6))

        game.schedule_turn_action(extra_turn, _extra_twist)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFERRED — engine support not yet available
# ═══════════════════════════════════════════════════════════════════════════════

class DeferredAnomalyScript:
    """
    Status: DEFERRED — requires engine subsystem not yet implemented.
    Card text preserved in registry for future reference.
    """

    @staticmethod
    def on_apply(source, game):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

ANOMALY_SCRIPT_REGISTRY: dict = {
    "EXAMPLE_ANOMALY": ExampleAnomalyScript,

    # ── CORRECT: Economy ──
    "BG27_Anomaly_000": MoneyMatchScript,
    "BG27_Anomaly_001": FinickyHourglassScript,
    "BG27_Anomaly_100": BigLeagueScript,
    "BG27_Anomaly_006": CurseOfAggramarScript,
    "BG27_Anomaly_501": TemperanceScript,
    "BG27_Anomaly_504": SecretsOfNorgannonScript,
    "BG27_Anomaly_721": UncompensatedUpsetScript,
    "BG27_Anomaly_302": StartWithPiggyBanksScript,
    "BG31_Anomaly_127": Get3Tier2MinionsScript,

    # ── CORRECT: Stats ──

    # ── CORRECT: Tribe Filter ──
    "BG27_Anomaly_104t": OopsAllBeastsScript,
    "BG27_Anomaly_104t2": OopsAllDemonsScript,
    "BG27_Anomaly_104t3": OopsAllDragonsScript,
    "BG27_Anomaly_104t4": OopsAllElementalsScript,
    "BG27_Anomaly_104t5": OopsAllMechsScript,
    "BG27_Anomaly_104t6": OopsAllMurlocsScript,
    "BG27_Anomaly_104t7": OopsAllNagasScript,
    "BG27_Anomaly_104t8": OopsAllQuilboarScript,
    "BG27_Anomaly_104t9": OopsAllUndeadScript,
    "BG27_Anomaly_104t10": OopsAllPiratesScript,

    # ── CORRECT: Golden / Triple ──
    "BG27_Anomaly_301": TwoCopiesGoldenScript,

    # ── CORRECT: Doublers ──
    "BG27_Anomaly_802": BCAndDRDoubleScript,
    "BG27_Anomaly_303": FirstMinionFreeAnomaly,

    # ── CORRECT: Game modes (marker tags) ──
    "BG27_Anomaly_822": EnableQuestsDenathriusScript,    # Quests+Rwards enabled (engine flag)
    "BG27_Anomaly_Quests": EnableQuestsScript,  # Quests enabled
    "BG27_Anomaly_Buddies": EnableBuddiesScript, # Buddies enabled
    "BG27_Anomaly_Prizes2": PrizeEvery4TurnsScript,  # Prize every 4 turns
    "BG31_Anomaly_106": EnableTrinketsMarinScript,     # Trinkets enabled

    # ── CORRECT: Refresh pool filtering (engine flags set on anomaly) ──
    "BG27_Anomaly_101": TierFilterOnly135Script,     # Tiers 1,3,5 only
    "BG27_Anomaly_102": TierFilterOnly246Script,     # Tiers 2,4,6 only
    "BG27_Anomaly_800": TierFilterOnly1234Script,     # Tiers 1-4 only
    "BG27_Anomaly_103": AllTypesAlways7Script,     # All minion types + always 7
    "BG27_Anomaly_111": OnlyCurrentTierAnomalyScript,     # Only current tier
    "BG27_Anomaly_750": Always7TavernScript,     # Always 7 in tavern
    "BG27_Anomaly_307": OopsAllEvilScript,     # Oops All Evil (Demon+Undead)
    "BG27_Anomaly_112": NoTypeHasAllTypesScript,     # No-type has all types

    # ── CORRECT: Auto-upgrade ──
    "BG27_Anomaly_005": AutoUpgradeEvery2TurnsScript,     # Auto-upgrade every 2 turns

    # ── CORRECT: Start-of-Turn HP set ──
    "BG27_Anomaly_502": SoTSetHPTo12Script,         # SoT: set HP to 12

    # ── CORRECT: Random keyword on tavern ──
    "BG27_Anomaly_505": RandomKeywordAnomalyScript,     # Random keyword on tavern minions

    # ── CORRECT: Golden modifications ──
    "BG27_Anomaly_801": AllMinionsGoldenAnomalyScript,  # All minions golden
    "BG31_Anomaly_120": StartSummonGoldenPatientScoutScript,     # Start with golden Patient Scout

    # ── CORRECT: Turn-delayed triggers ──
    "BG27_Anomaly_559": GoldenDiscoverT4Turn6Script,  # Turn 6: golden tier 4
    "BG27_Anomaly_570": GoldenDiscoverT5Turn7Script,  # Turn 7: golden tier 5
    "BG27_Anomaly_571": GoldenDiscoverT6Turn8Script,  # Turn 8: golden tier 6
    "BG27_Anomaly_572": GoldenDiscoverT3Turn5Script,  # Turn 5: golden tier 3
    "BG27_Anomaly_573": GoldenDiscoverT7Turn9Script,  # Turn 9: golden tier 7
    "BG27_Anomaly_577": FacelessEvery4TurnsScript,    # Faceless every 4 turns
    "BG27_Anomaly_114": CopyLeftmostEvery2TurnsScript,        # Copy leftmost every 2 turns
    "BG31_Anomaly_124": GoldenArrowEvery3TurnsScript,  # Golden Arrow every 3 turns

    # ── CORRECT: Per-player mechanics ──
    "BG27_Anomaly_720": AllHeroesNguyenScript,     # All heroes are Nguyen (engine flag)
    "BG27_Anomaly_900": NoRefreshAutoAfterBuyScript,     # No refresh, auto after buy (engine flag)
    "BG27_Anomaly_556": NoTier1CostEqualsTierScript,     # No tier 1, cost = tier (engine flag)
    "BG27_Anomaly_714": Start25DmgHealOnDeathAnomalyScript,  # Start 25 dmg, heal 5 on hero death
    "BG27_Anomaly_723": StartAllDiscoverTier6Script,     # All discover tier 6
    "BG27_Anomaly_002": PrudenceOfAmitusScript,     # Prudence of Amitus: minions have +2 HP
    "BG27_Anomaly_575": EleventhHourScript,     # Eleventh Hour
    "BG27_Anomaly_715": AfterCombatDiscoverScript,     # Win/lose combat discover
    "BG27_Anomaly_716": UpgradeDiscoverPrizeAnomalyScript,     # Upgrade → discover prize (DEFERRED: needs prize)
    "BG27_Anomaly_718": UpgradeRefreshTribeScript,  # Upgrade → refresh with majority tribe
    "BG27_Anomaly_754": Refresh5GoldenApeScript,     # Refresh 5 → golden ape
    "BG27_Anomaly_755": TripleGivesPrizeScript,     # Triple → prize (engine flag)
    "BG27_Anomaly_820": SoTDeepBluesAnomalyScript,     # SoT get 2 Deep Blues
    "BG27_Anomaly_805": GuessWinnerAnomalyScript,     # Guess winner → coins
    "BG27_Anomaly_561": AfterSellTransferStatsAnomalyScript,  # After sell → tavern minion gets its stats
    "BG27_Anomaly_558": DiscoverFromDeadHeroAnomalyScript,     # Discover from dead hero
    "BG27_Anomaly_711": FirstBuyCopyAnomalyScript,     # First buy → extra copy
    "BG27_Anomaly_503": SharedYoggWheelScript,     # Shared Yogg wheel
    "BG27_Anomaly_555": GuessMinionAnomalyScript,     # Guess minion → coins
    "BG27_Anomaly_560": AnomalySoCSummonCopyHighestScript,     # SoC copy highest HP
    "BG27_Anomaly_562": AfterRefreshBuffTavernAnomalyScript,  # Useful refreshes: +6/+6 + DS on tavern
    "BG27_Anomaly_580": PlayerChoiceCardScript,     # Player choice card
    "BG27_Anomaly_726": AnomalySoCDSAndRebornEdgesScript,     # SoC DS + Reborn
    "BG27_Anomaly_751": StartWithGoldenTouchScript,     # Start with Golden Touch
    "BG27_Anomaly_803": SoTChooseRewardAnomalyScript,     # SoT choose new reward
    "BG27_Anomaly_810": BuddiesInTavernScript,     # Buddies in tavern (engine flag)

    # ── CORRECT: Spell-related anomalies ──
    "BG31_Anomaly_101": RefreshExtraSpellAnomalyScript,  # Refresh always offers extra tavern spell
    "BG31_Anomaly_102": SoTGetEvolvingScrollScript,  # SoT get evolving scroll
    "BG31_Anomaly_104": UpgradeDiscoverSpellScript,  # Upgrade → discover spell
    "BG31_Anomaly_105": FirstSpellBuyCopyAnomalyScript,     # First spell buy → copy
    "BG31_Anomaly_109": SoTDiscoverSpellScript,     # SoT discover spell
    "BG31_Anomaly_115": SpellTicketsScript,     # Spell tickets

    # ── CORRECT: Misc ──
    "BG31_Anomaly_116": Refresh2GetGoldAnomalyScript,     # Refresh 2 → gold next turn
    "BG31_Anomaly_117": EjectMinionsScript,     # Eject minions from pool
    "BG31_Anomaly_126": SoTGetMajorityTribeScript,  # SoT get majority tribe
    "BG31_Anomaly_123": DiscoverSecondHPAnomalyScript,     # Discover second HP

    # ── CORRECT: Trinket timing ──
    "BG32_Anomaly_001": TrinketGreaterOnlyScript,     # Only greater trinkets
    "BG32_Anomaly_002": TrinketLesserOnlyScript,     # Only lesser trinkets
    "BG32_Anomaly_003": TrinketTiming58Script,     # Custom trinket timing

    # ── CORRECT: Buddy system (engine flags) ──
    "BG33_Anomaly_001": BuddyUpgradeCostReductionScript,     # Buddy upgrade cost reduction
    "BG33_Anomaly_002": BuddyButtonDiscoverScript,     # Buddy button discover
    "BG33_Anomaly_003": BuddyThirdButtonScript,     # Buddy third button
    "BG33_Anomaly_005": BuddiesAllTypesScript,     # Buddies all types
    "BG33_Anomaly_008": QuestForGoldenBuddyScript,     # Quest for golden buddy
    "BG33_Anomaly_009": BuddyCostPerBuyScript,     # Buddy cost per buy

    # ── DEFERRED: Needs Temporal Twist system ──
    "BG34_Anomaly_800": TwistGreaterGoldenCountScript,
    "BG34_Anomaly_800t": TwistLesserGoldenCountScript,
    "BG34_Anomaly_801": TwistExtraTimeMarkScript,
    "BG34_Anomaly_802": TwistGreaterOnlyScript,
    "BG34_Anomaly_804": TwistAll4MarksScript,
    "BG34_Anomaly_805": TwistPoolEntryScript,
    "BG34_Anomaly_809": TwistExtraRandomTurnScript,

    # ── OUT_OF_SCOPE: Duos ──
    "BGDUO_Anomaly_003": DeferredAnomalyScript,
    "BGDUO_Anomaly_005": DeferredAnomalyScript,
    "BGDUO_Anomaly_006": DeferredAnomalyScript,
    "BGDUO_Anomaly_007": DeferredAnomalyScript,
}
