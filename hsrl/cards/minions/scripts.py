"""
Script classes for BG pool minion complex effects.

Each script class implements battlecry/deathrattle/avenge/start_of_combat
as @staticmethod methods returning Action or list[Action].

Effect coverage:
  - Implemented: clear, self-contained effects (self-buff, basic damage, gold, etc.)
  - TODO: effects requiring token cards, discover UI, Blood Gem system, spell engine, duos
"""

from hsrl.core.enums import CardType, GameTag, Race, Zone
import random

from hsrl.core.actions import (
    Action,
    AddToHand,
    ApplyGlobalAura,
    AttackImmediately,
    Buff,
    BuffTavern,
    CastTavernSpell,
    ChooseOne,
    ConsumeTavernMinion,
    DealDamageToHero,
    Destroy,
    DiscoverMinion,
    DiscoverSpell,
    GainFreeRefresh,
    GainGold,
    GainKeyword,
    GetBloodGem,
    GetRandomMinion,
    Hit,
    ImproveBloodGem,
    ImproveTavernSpellBuff,
    LoseKeyword,
    PlayBloodGems,
    ScheduleNextTurn,
    SetNextSpellDiscount,
    Summon,
    SummonFromHandForCombat,
    Transform,
    TriggerBattlecry,
    get_adjacent_minions,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════════


def _buff_self(source, atk=0, health=0):
    """Buff the source minion itself."""
    return Buff(source, atk=atk, health=health)


def _deal_aoe_damage(source, game, amount):
    """Deal damage to all minions on both sides."""
    actions = []
    for player in game.players:
        if player.is_alive:
            for minion in player.get_board_minions():
                if minion is not source:
                    actions.append(Hit(minion, amount, source))
    return actions


# ═══════════════════════════════════════════════════════════════════════════════
# Script classes for specific minions
# ═══════════════════════════════════════════════════════════════════════════════


# ── BGS_018: Goldrinn, the Great Wolf ─────────────────────────────────
class GoldrinnScript:
    """Deathrattle: For the rest of this combat, your Beasts have +{0}/+{1}."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if m.race in (Race.BEAST, Race.ALL):
                actions.append(Buff(m, atk=4, health=4))
        return actions


# ── BG_DAL_775: Tunnel Blaster ────────────────────────────────────────
class TunnelBlasterScript:
    """Deathrattle: Deal 3 damage to all minions."""

    @staticmethod
    def deathrattle(source, game):
        return _deal_aoe_damage(source, game, 3)


# ── BG23_318: Leeroy the Reckless ─────────────────────────────────────
class LeeroyScript:
    """Deathrattle: Destroy the minion that killed this."""

    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.actions import Destroy
        killer_id = source.get_tag(GameTag.KILLER, 0)
        if not killer_id:
            return None
        # Find the killer minion by entity_id on both combat boards
        for p in game.players:
            if not p.is_alive:
                continue
            for m in p.board:
                if m.entity_id == killer_id and not m.dead:
                    return Destroy(m)
        return None


# ── BG26_135: Southsea Busker ─────────────────────────────────────────
class SouthseaBuskerScript:
    """
    Natural language: Battlecry: Gain 1 Gold next turn.

    Formal spec:
      1. Schedule a GainGold(1) action for the start of the next Recruit phase
      2. The gold is NOT gained immediately — it is deferred

    Test: verify no gold is gained immediately, but gold is gained
          after process_deferred_actions().
    """

    @staticmethod
    def battlecry(source, game):
        return ScheduleNextTurn(source.controller, GainGold(source.controller, 1))


# ── BG23_002: Shell Collector ─────────────────────────────────────────
class ShellCollectorScript:
    """
    Natural language: Battlecry: Get a Tavern Coin.

    Formal spec:
      1. Create 1 TAVERN_COIN spell entity (card_id="TAVERN_COIN")
      2. Add it to source.controller.hand (Zone.HAND)
      3. The Coin can later be played to gain 1 Gold

    Test: verify player.hand contains 1 card with card_id="TAVERN_COIN".
    """

    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, "TAVERN_COIN")


# ── BG34_636t / BG34_637t: Chromadrake Battlecries ────────────────────
class GreenChromadrakeScript:
    """Battlecry: Give your other Dragons +X/+Y."""

    @staticmethod
    def battlecry(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if m is not source and m.race in (Race.DRAGON, Race.ALL):
                actions.append(Buff(m, atk=1, health=1))
        return actions


class BronzeChromadrakeScript:
    """Battlecry: Give your other Dragons +X/+Y."""

    @staticmethod
    def battlecry(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if m is not source and m.race in (Race.DRAGON, Race.ALL):
                actions.append(Buff(m, atk=1, health=1))
        return actions


class BlueChromadrakeScript:
    """Battlecry: Get a random 3-Cost Tavern spell."""

    @staticmethod
    def battlecry(source, game):
        import random
        from hsrl.core.enums import CardType, GameTag, Zone
        from hsrl.core.actions import Action
        cost = source.tech_level  # {0} = tech_level = 3
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != CardType.SPELL:
                continue
            if card_id.startswith("EXAMPLE_"):
                continue
            spell_cost = data.tags.get(GameTag.COST, 0)
            if spell_cost == cost:
                candidates.append(card_id)
        if not candidates:
            return None
        chosen = random.choice(candidates)
        # Create spell entity and add to hand (no triple check for spells)
        class _GetSpellAction(Action):
            def do(self, source_ent, game_ref, target=None):
                spell = game_ref.create_spell(chosen)
                spell.controller = source.controller
                spell.zone = Zone.HAND
                source.controller.hand.append(spell)
        return _GetSpellAction()


class RefreshingAnomalyScript:
    """Battlecry: Gain 2 free Refreshes."""

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import GainFreeRefresh
        return GainFreeRefresh(source.controller, 2)


class AlertAlarmistScript:
    """Deathrattle: The next Tavern spell you buy costs (2) less."""

    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.actions import SetNextSpellDiscount
        return SetNextSpellDiscount(source.controller, 2)


# ── BG33_371: P-0UL-TR-0N ─────────────────────────────────────────────
class POULTRONScript:
    """
    Natural language: Avenge ({0}): Gain Divine Shield and attack immediately.

    Formal spec:
      1. Source gains Divine Shield
      2. Source attacks a random enemy minion immediately
    """

    @staticmethod
    def avenge(source, game):
        return [
            GainKeyword(source, GameTag.DIVINE_SHIELD),
            AttackImmediately(source),
        ]


# ── BG31_330: Ominous Seer ───────────────────────────────────────────
class OminousSeerScript:
    """
    Natural language: Battlecry: The next Tavern spell you buy costs (1) less.

    Formal spec:
      - Battlecry: controller.NEXT_SPELL_COST_REDUCTION += 1
      - Discount applied in Game.buy_spell() at purchase time, then reset to 0.
    """

    @staticmethod
    def battlecry(source, game):
        controller = source.controller
        if controller is None:
            return None
        current = controller.get_tag(GameTag.NEXT_SPELL_COST_REDUCTION, 0)
        controller.set_tag(GameTag.NEXT_SPELL_COST_REDUCTION, current + 1)
        return None



# ── BG25_034: Captain Sanders ─────────────────────────────────────────
class CaptainSandersScript:
    """
    Natural language: Battlecry: Make a friendly minion from Tier 6 or below Golden.

    Formal spec:
      - Player chooses a friendly board minion (not self, tier ≤ 6, not golden)
        during recruit phase; random during combat.
      - Sets GOLDEN=True, BASE_ATK *= 2, BASE_HEALTH *= 2

    Test: Captain Sanders targets a friendly non-golden minion (tier 1-6),
          making it golden and doubling its stats during recruit phase.
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            return [
                m for m in source.controller.get_board_minions()
                if m is not source and m.tech_level <= 6 and not m.is_golden
            ]

        if not filter_fn():
            return None  # No valid targets — skip entirely

        def action_factory(target):
            target.set_tag(GameTag.GOLDEN, True)
            target.set_tag(GameTag.BASE_ATK, target.get_tag(GameTag.BASE_ATK, 0) * 2)
            target.set_tag(GameTag.BASE_HEALTH, target.get_tag(GameTag.BASE_HEALTH, 0) * 2)
            target.set_tag(GameTag.HEALTH, target.max_health)
            return None

        return TargetedAction(filter_fn, action_factory,
                              label="Make a friendly minion Golden")


# ── BGS_030: King Bagurgle ────────────────────────────────────────────
class KingBagurgleScript:
    """Battlecry: Give all other Murlocs in your hand and board +X/+Y."""

    @staticmethod
    def battlecry(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if m is not source and m.race in (Race.MURLOC, Race.ALL):
                actions.append(Buff(m, atk=2, health=2))
        for m in source.controller.get_hand_minions():
            if m.race in (Race.MURLOC, Race.ALL):
                actions.append(Buff(m, atk=2, health=2))
        return actions


# ── BG35_140: Mama Mrrglton ───────────────────────────────────────────
class MamaMrrgltonScript:
    """
    Natural language: Battlecry: Give your other Murlocs +{0} Attack.
    (Improved by each Mrrglton you played this game!)

    Formal spec:
      1. Increment source.controller's MAMA_MRRGLTON_COUNT tag by 1
      2. Buff all other friendly Murlocs (board + hand) by +count Attack
      3. "Improved by each Mrrglton" means the buff scales with total
         Mama Mrrgltons played (including this one)
    """

    @staticmethod
    def battlecry(source, game):
        player = source.controller
        count = player.get_tag(GameTag.MAMA_MRRGLTON_COUNT, 0) + 1
        player.set_tag(GameTag.MAMA_MRRGLTON_COUNT, count)
        actions = []
        for m in player.get_board_minions():
            if m is not source and m.race in (Race.MURLOC, Race.ALL):
                actions.append(Buff(m, atk=count, health=0))
        for m in player.get_hand_minions():
            if m.race in (Race.MURLOC, Race.ALL):
                actions.append(Buff(m, atk=count, health=0))
        return actions


# ── BG35_141: Papa Mrrglton ───────────────────────────────────────────
class PapaMrrgltonScript:
    """
    Natural language: Battlecry: Give your other Murlocs +{0} Health.
    (Improved by each Mrrglton you played this game!)

    Formal spec:
      1. Increment source.controller's PAPA_MRRGLTON_COUNT tag by 1
      2. Buff all other friendly Murlocs (board + hand) by +count Health
      3. "Improved by each Mrrglton" means the buff scales with total
         Papa Mrrgltons played (including this one)
    """

    @staticmethod
    def battlecry(source, game):
        player = source.controller
        count = player.get_tag(GameTag.PAPA_MRRGLTON_COUNT, 0) + 1
        player.set_tag(GameTag.PAPA_MRRGLTON_COUNT, count)
        actions = []
        for m in player.get_board_minions():
            if m is not source and m.race in (Race.MURLOC, Race.ALL):
                actions.append(Buff(m, atk=0, health=count))
        for m in player.get_hand_minions():
            if m.race in (Race.MURLOC, Race.ALL):
                actions.append(Buff(m, atk=0, health=count))
        return actions


# ── BG32_236: Aureate Laureate ────────────────────────────────────────
class AureateLaureateScript:
    """Battlecry: Make this minion Golden (doubles stats)."""

    @staticmethod
    def battlecry(source, game):
        if source.is_golden:
            return None
        source.set_tag(GameTag.GOLDEN, True)
        current_atk = source.get_tag(GameTag.BASE_ATK, 0)
        current_health = source.get_tag(GameTag.BASE_HEALTH, 0)
        source.set_tag(GameTag.BASE_ATK, current_atk * 2)
        source.set_tag(GameTag.BASE_HEALTH, current_health * 2)
        source.set_tag(GameTag.HEALTH, source.max_health)
        return None


# ── BG24_009: Picky Eater ─────────────────────────────────────────────
class PickyEaterScript:
    """
    Natural language: Battlecry: Consume a random minion in the Tavern to gain its stats.

    Formal spec:
      - Select random non-dead MINION-type entity from player's tavern
      - FodderConsume: destroy it, source gains its ATK and HEALTH
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import FodderConsume
        tavern = source.controller.tavern
        candidates = [
            m for m in tavern
            if not m.dead and m.get_tag(GameTag.CARDTYPE, 0) == 1  # CardType.MINION
        ]
        if not candidates:
            return None
        target = random.choice(candidates)
        return FodderConsume(source, target)


# ── BG_LOE_077: Brann Bronzebeard ─────────────────────────────────────
class BrannScript:
    """
    Natural language: Your Battlecries trigger twice.

    Formal spec:
      - on_summon: set BATTLECRY_DOUBLED tag on controller.
        Engine checks this tag in play_minion() and TriggerBattlecry.do().
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.BATTLECRY_DOUBLED, True)
        return None


# ── BG26_ICC_901: Drakkari Enchanter ──────────────────────────────────
class DrakkariScript:
    """
    Natural language: Your end of turn effects trigger twice.

    Formal spec:
      - on_summon: set END_OF_TURN_DOUBLED tag on controller.
        Engine checks this tag in _trigger_end_of_turn().
    """

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.END_OF_TURN_DOUBLED, True)
        return None


# ── BG_GVG_100: Floating Watcher ──────────────────────────────────────
class FloatingWatcherScript:
    """
    Natural language: Whenever your hero takes damage on your turn, gain +{0}/+{1}.

    Formal spec:
      - on_summon: register persistent EventListener for PLAYER_DAMAGE_TAKEN
      - condition: damaged player is our controller, AND we are in RECRUIT step
        (combat damage does NOT count as "on your turn")
      - action: Buff(source, atk=2, health=2)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener, PLAYER_DAMAGE_TAKEN
        from hsrl.core.enums import Step
        listener = EventListener(
            event_name=PLAYER_DAMAGE_TAKEN,
            action=Buff(source, atk=2, health=2),
            condition=lambda p, dmg, src: (
                p == source.controller and game.step == Step.RECRUIT
            ),
        )
        game.register_listener(source, listener)
        return None


# ── BG25_016: Sin'dorei Straight Shot ─────────────────────────────────
class SindoreiStraightShotScript:
    """Rally: Remove Reborn and Taunt from the target."""

    @staticmethod
    def rally(source, game):
        target = game._last_attack_target
        if target is None:
            return None
        actions = []
        if target.reborn:
            actions.append(LoseKeyword(target, GameTag.REBORN))
        if target.taunt:
            actions.append(LoseKeyword(target, GameTag.TAUNT))
        return actions if actions else None


# ── BG27_017: Obsidian Ravager ────────────────────────────────────────
class ObsidianRavagerScript:
    """Rally: Deal damage equal to this minion's Attack to the target and an adjacent minion."""

    @staticmethod
    def rally(source, game):
        target = game._last_attack_target
        if target is None:
            return None
        actions = [Hit(target, source.atk, source)]
        # Hit an adjacent minion
        board = target.controller.board if target.controller else []
        try:
            idx = board.index(target)
        except ValueError:
            return actions
        adj_options = []
        for offset in (-1, 1):
            adj_idx = idx + offset
            if 0 <= adj_idx < len(board):
                adj = board[adj_idx]
                if adj is not source and not adj.dead:
                    adj_options.append(adj)
        if adj_options:
            adj_target = random.choice(adj_options)
            actions.append(Hit(adj_target, source.atk, source))
        return actions


# ── BG33_241: Sleepy Supporter ────────────────────────────────────────
class SleepySupporterScript:
    """Rally: Give the minion to the right of this +1/+1."""

    @staticmethod
    def rally(source, game):
        board = source.controller.board if source.controller else []
        try:
            idx = board.index(source)
        except ValueError:
            return None
        right_idx = idx + 1
        if right_idx < len(board):
            right = board[right_idx]
            if not right.dead:
                return Buff(right, atk=1, health=1)
        return None


# ── BG33_318: Bile Spitter ────────────────────────────────────────────
class BileSpitterScript:
    """Rally: Give another friendly Murloc Venomous."""

    @staticmethod
    def rally(source, game):
        murlocs = [m for m in source.controller.get_board_minions()
                   if m is not source and not m.dead
                   and m.race in (Race.MURLOC, Race.ALL)
                   and not m.venomous]
        if murlocs:
            target = random.choice(murlocs)
            return GainKeyword(target, GameTag.VENOMOUS)
        return None


# ── BG33_840: Stomping Stegodon ───────────────────────────────────────
class StompingStegodonScript:
    """
    Natural language: Rally: Give your other Beasts +{0} Attack and this Rally.

    Status: ACTIVE

    Test: Stegodon attacks → other Beasts get +1 ATK and RALLY keyword
          with the same propagated effect. Propagated Rally chains further.
    """

    @staticmethod
    def rally(source, game):
        return StompingStegodonScript._propagated_rally(source, game)

    @staticmethod
    def _propagated_rally(source, game):
        """Rally: buff other Beasts +1 ATK, grant RALLY keyword + this effect."""
        actions = []
        for m in source.controller.get_board_minions():
            if m is not source and not m.dead and m.race in (Race.BEAST, Race.ALL):
                actions.append(Buff(m, atk=1, health=0))
                actions.append(GainKeyword(m, GameTag.RALLY))
                m._script_overrides["rally"] = StompingStegodonScript._propagated_rally
        return actions


# ── BG34_604: Heroic Underdog ─────────────────────────────────────────
class HeroicUnderdogScript:
    """Rally: Gain the target's Attack."""

    @staticmethod
    def rally(source, game):
        target = game._last_attack_target
        if target is None:
            return None
        stolen_atk = target.atk
        return Buff(source, atk=stolen_atk, health=0)


# ── BG25_011: Nerubian Deathswarmer ────────────────────────────────────
class NerubianDeathswarmerScript:
    """Battlecry: Your Undead have +1 Attack this game (wherever they are)."""

    @staticmethod
    def battlecry(source, game):
        return ApplyGlobalAura(source.controller, atk=1, health=0, race_filter=Race.UNDEAD)


# ── BG34_690: Plaguerunner ─────────────────────────────────────────────
class PlaguerunnerScript:
    """
    Natural language: Deathrattle: Your Undead have +{0} Attack this game,
    wherever they are. (+{1} if this died outside combat!)

    Formal spec:
      1. If game.in_combat is True:
         a. Read PLAGUERUNNER_SCALE from controller (default 3)
         b. Apply global +X ATK aura to all Undead
         c. Increment PLAGUERUNNER_SCALE by 1 for next trigger
      2. If game.in_combat is False (died outside combat):
         a. Apply global +1 ATK aura to all Undead
         b. Do NOT increment PLAGUERUNNER_SCALE
    """

    @staticmethod
    def deathrattle(source, game):
        controller = source.controller
        if controller is None:
            return None
        if game.in_combat:
            x = controller.get_tag(GameTag.PLAGUERUNNER_SCALE, 3)
            controller.set_tag(GameTag.PLAGUERUNNER_SCALE, x + 1)
            return ApplyGlobalAura(controller, atk=x, health=0, race_filter=Race.UNDEAD)
        else:
            return ApplyGlobalAura(controller, atk=1, health=0, race_filter=Race.UNDEAD)


# ── BG31_999: Stitched Salvager ───────────────────────────────────────
class StitchedSalvagerScript:
    """
    Natural language: Start of Combat: Destroy the minion to the left.
    Deathrattle: Summon an exact copy of it. (Except Stitched Salvager.)

    Formal spec:
      1. Start of Combat: destroy the minion to the left, store its card_id
      2. Deathrattle: create a fresh minion from the stored card_id and summon it
    """

    @staticmethod
    def start_of_combat(source, game):
        board = source.controller.get_board_minions()
        idx = board.index(source) if source in board else -1
        if idx > 0:
            left = board[idx - 1]
            # Store reference for Deathrattle
            source.set_tag(GameTag.SAVED_MINION_ID, left.get_tag(GameTag.CARD_ID))
            return Destroy(left)
        return None

    @staticmethod
    def deathrattle(source, game):
        saved_id = source.get_tag(GameTag.SAVED_MINION_ID)
        if saved_id:
            copy_minion = game.create_minion(saved_id)
            return Summon(source.controller, copy_minion)
        return None


# ── BG20_100: Razorfen Geomancer ──────────────────────────────────────
class RazorfenGeomancerScript:
    """
    Natural language: Battlecry: Get 2 Blood Gems.

    Formal spec:
      1. Create 2 Blood Gem spell entities (card_id="BLOOD_GEM")
      2. Add them to source.controller.hand (Zone.HAND)
      3. Each Blood Gem can later be played on a friendly minion
         to buff it by (1 + BLOOD_GEM_BONUS_ATK)/(1 + BLOOD_GEM_BONUS_HEALTH)

    Test: verify player.hand contains 2 cards of type BLOOD_GEM_CARD
          after the Battlecry resolves.
    """

    @staticmethod
    def battlecry(source, game):
        return GetBloodGem(source.controller, count=2)


# ── BG19_010: Sewer Rat ────────────────────────────────────────────────
class SewerRatScript:
    """Deathrattle: Summon a 2/3 Turtle with Taunt."""

    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("BG19_010t")
        return Summon(source.controller, token)


# ── BG28_300: Harmless Bonehead ────────────────────────────────────────
class HarmlessBoneheadScript:
    """Deathrattle: Summon two 1/1 Skeletons."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for _ in range(2):
            token = game.create_minion("BG_ICC_026t")
            actions.append(Summon(source.controller, token))
        return actions


# ── BG30_125: Cadaver Caretaker ─────────────────────────────────────────
class CadaverCaretakerScript:
    """Deathrattle: Summon three 1/1 Skeletons."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for _ in range(3):
            token = game.create_minion("BG_ICC_026t")
            actions.append(Summon(source.controller, token))
        return actions


# ── BG29_611: Cord Puller ───────────────────────────────────────────────
class CordPullerScript:
    """Deathrattle: Summon a 1/1 Microbot."""

    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("BG_BOT_312t")
        return Summon(source.controller, token)


# ── BG26_800: Manasaber ─────────────────────────────────────────────────
class ManasaberScript:
    """Deathrattle: Summon two 0/1 Cublings with Taunt."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for _ in range(2):
            token = game.create_minion("BG26_800t")
            actions.append(Summon(source.controller, token))
        return actions


# ── BG25_010: Handless Forsaken ─────────────────────────────────────────
class HandlessForsakenScript:
    """Deathrattle: Summon a 2/1 Hand with Reborn."""

    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("BG25_010t")
        return Summon(source.controller, token)


# ── BG25_009: Eternal Summoner ─────────────────────────────────────────
class EternalSummonerScript:
    """Deathrattle: Summon an Eternal Knight."""

    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("BG25_008")
        return Summon(source.controller, token)


# ── BG34_630: Twilight Hatchling ───────────────────────────────────────
class TwilightHatchlingScript:
    """
    Natural language: Deathrattle: Summon a {0}/{1} Whelp that attacks immediately.

    Formal spec:
      1. Create a Twilight Whelp token (card_id="BG34_630t")
      2. Summon it on source.controller's board
      3. The Whelp attacks an enemy minion immediately
    """

    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("BG34_630t")
        return [
            Summon(source.controller, token),
            AttackImmediately(token),
        ]


# ── BG34_731: Twilight Broodmother ─────────────────────────────────────
class TwilightBroodmotherScript:
    """Deathrattle: Summon two Twilight Hatchlings. Give them Taunt."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for _ in range(2):
            token = game.create_minion("BG34_630")
            token.set_tag(GameTag.TAUNT, True)
            actions.append(Summon(source.controller, token))
        return actions


# ── BG35_604: Sewer Lord ───────────────────────────────────────────────
class SewerLordScript:
    """Deathrattle: Summon two Sewer Rats (which summon Turtles on death)."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for _ in range(2):
            token = game.create_minion("BG19_010")
            actions.append(Summon(source.controller, token))
        return actions


# ── BG25_022: Scarlet Skull ────────────────────────────────────────────
class ScarletSkullScript:
    """Deathrattle: Give a friendly Undead +1/+2."""

    @staticmethod
    def deathrattle(source, game):
        undead = [m for m in source.controller.get_board_minions()
                  if not m.dead and m.race in (Race.UNDEAD, Race.ALL)]
        if undead:
            target = random.choice(undead)
            return Buff(target, atk=1, health=2)
        return None


# ── BG28_309: Mummifier ────────────────────────────────────────────────
class MummifierScript:
    """Deathrattle: Give a different friendly Undead Reborn."""

    @staticmethod
    def deathrattle(source, game):
        undead = [m for m in source.controller.get_board_minions()
                  if m is not source and not m.dead
                  and m.race in (Race.UNDEAD, Race.ALL)]
        if undead:
            target = random.choice(undead)
            return GainKeyword(target, GameTag.REBORN)
        return None


# ── BG35_122: Determined Defender ──────────────────────────────────────
class DeterminedDefenderScript:
    """Deathrattle: Give adjacent minions +X/+Y and Taunt."""

    @staticmethod
    def deathrattle(source, game):
        board = source.controller.board
        try:
            idx = board.index(source)
        except ValueError:
            return None
        actions = []
        for offset in (-1, 1):
            adj_idx = idx + offset
            if 0 <= adj_idx < len(board):
                adj = board[adj_idx]
                if not adj.dead:
                    actions.append(Buff(adj, atk=1, health=1))
                    actions.append(GainKeyword(adj, GameTag.TAUNT))
        return actions


# ── BG29_808: Spiked Savior ────────────────────────────────────────────
class SpikedSaviorScript:
    """Deathrattle: Give your minions +1 Health and deal 1 damage to them."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if not m.dead and m is not source:
                actions.append(Buff(m, atk=0, health=1))
                actions.append(Hit(m, 1, source))
        return actions


# ── BG26_360: Scourfin ─────────────────────────────────────────────────
class ScourfinScript:
    """Deathrattle: Give a random minion in your hand +X/+Y."""

    @staticmethod
    def deathrattle(source, game):
        hand = source.controller.get_hand_minions()
        if hand:
            target = random.choice(hand)
            return Buff(target, atk=2, health=2)
        return None


# ── BG34_920: Tide Raiser ──────────────────────────────────────────────
class TideRaiserScript:
    """Deathrattle: Cast Shifting Tide on an adjacent minion (buff +X/+Y)."""

    @staticmethod
    def deathrattle(source, game):
        board = source.controller.board
        try:
            idx = board.index(source)
        except ValueError:
            return None
        adj_options = []
        for offset in (-1, 1):
            adj_idx = idx + offset
            if 0 <= adj_idx < len(board):
                m = board[adj_idx]
                if not m.dead:
                    adj_options.append(m)
        if adj_options:
            target = random.choice(adj_options)
            return Buff(target, atk=1, health=2)
        return None


# ── BG32_434: Skulking Bristlemane ─────────────────────────────────────
class SkulkingBristlemaneScript:
    """Deathrattle: Play a permanent Blood Gem on adjacent minions."""

    @staticmethod
    def deathrattle(source, game):
        board = source.controller.board
        try:
            idx = board.index(source)
        except ValueError:
            return None
        actions = []
        for offset in (-1, 1):
            adj_idx = idx + offset
            if 0 <= adj_idx < len(board):
                adj = board[adj_idx]
                if not adj.dead:
                    actions.append(PlayBloodGems(adj, count=1))
        return actions


# ═══════════════════════════════════════════════════════════════════════════════
# Blood Gem — Group A: Improvers ("Blood Gems give extra +X/+Y this game")
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG23_017: Sanguine Champion ────────────────────────────────────────
class SanguineChampionScript:
    """Battlecry and Deathrattle: Your Blood Gems give an extra +1/+1 this game."""

    @staticmethod
    def battlecry(source, game):
        return ImproveBloodGem(source.controller, atk_bonus=1, health_bonus=1)

    @staticmethod
    def deathrattle(source, game):
        return ImproveBloodGem(source.controller, atk_bonus=1, health_bonus=1)


# ── BG26_159: Moon-Bacon Jazzer ────────────────────────────────────────
class MoonBaconJazzerScript:
    """Battlecry: Your Blood Gems give an extra +1 Health this game."""

    @staticmethod
    def battlecry(source, game):
        return ImproveBloodGem(source.controller, health_bonus=1)


# ── BG26_160: Prickly Piper ────────────────────────────────────────────
class PricklyPiperScript:
    """Deathrattle: Your Blood Gems give an extra +1 Attack this game."""

    @staticmethod
    def deathrattle(source, game):
        return ImproveBloodGem(source.controller, atk_bonus=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Blood Gem — Group B: Multi-Target ("Play X Blood Gems on all Y minions")
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG25_155: Gem Smuggler ─────────────────────────────────────────────
class GemSmugglerScript:
    """Battlecry: Play 2 Blood Gems on all your other minions."""

    @staticmethod
    def battlecry(source, game):
        actions = []
        for m in source.controller.board:
            if m is not source and not m.dead:
                actions.append(PlayBloodGems(m, count=2))
        return actions


# ── BG26_867: Three Lil' Quilboar ───────────────────────────────────────
class ThreeLilQuilboarScript:
    """Deathrattle: Play 3 Blood Gems on all your Quilboar."""

    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.enums import Race
        actions = []
        for m in source.controller.board:
            if not m.dead and m.race == Race.QUILBOAR:
                actions.append(PlayBloodGems(m, count=3))
        return actions


# ── BG26_157: Bristlebach ───────────────────────────────────────────────
class BristlebachScript:
    """Avenge (2): Play 2 Blood Gems on all your Quilboar."""

    @staticmethod
    def avenge(source, game):
        from hsrl.core.enums import Race
        actions = []
        for m in source.controller.board:
            if not m.dead and m.race == Race.QUILBOAR:
                actions.append(PlayBloodGems(m, count=2))
        return actions


# ═══════════════════════════════════════════════════════════════════════════════
# Blood Gem — Group C: Combined Effects (Summon + Blood Gem)
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG32_430: Glowgullet Warlord ───────────────────────────────────────
class GlowgulletWarlordScript:
    """Deathrattle: Summon two 1/1 Quilboar w/ Taunt, play Blood Gem on them."""

    @staticmethod
    def deathrattle(source, game):
        actions = []
        for _ in range(2):
            token = game.create_minion("BG32_430t")
            actions.append(Summon(source.controller, token))
            actions.append(PlayBloodGems(token, count=1))
        return actions


# ═══════════════════════════════════════════════════════════════════════════════
# Blood Gem — Group D: "Get a Blood Gem" (adds to hand, not auto-play)
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG33_888: Hog Watcher ──────────────────────────────────────────────
class HogWatcherScript:
    """
    Natural language: Battlecry: Get a Blood Gem that also gives
    a Quilboar Divine Shield.

    Formal spec:
      1. Create 1 Divine Shield Blood Gem spell (card_id="BLOOD_GEM_DS")
      2. Add it to source.controller.hand (Zone.HAND)
      3. When later played on a Quilboar, gives +1/+1 and Divine Shield

    Test: verify player.hand contains 1 card with card_id="BLOOD_GEM_DS".
    """

    @staticmethod
    def battlecry(source, game):
        return GetBloodGem(source.controller, count=1, variant="divine_shield")


# ── BG35_432: Bristleback Bully ────────────────────────────────────────
class BristlebackBullyScript:
    """
    Natural language: Deathrattle: Get a Blood Gem that also gives
    a Quilboar Taunt.

    Formal spec:
      1. Create 1 Taunt Blood Gem spell (card_id="BLOOD_GEM_TAUNT")
      2. Add it to source.controller.hand (Zone.HAND)
      3. When later played on a Quilboar, gives +1/+1 and Taunt

    Test: verify player.hand contains 1 card with card_id="BLOOD_GEM_TAUNT".
    """

    @staticmethod
    def deathrattle(source, game):
        return GetBloodGem(source.controller, count=1, variant="taunt")


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Battlecry — Discover
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG34_523: Hunting Tiger Shark ──────────────────────────────────────
class HuntingTigerSharkScript:
    """
    Natural language: Battlecry: Discover a Beast.

    Formal spec:
      1. Select a random Beast from the minion pool
      2. Add it to the source's controller's hand (Zone.HAND)

    Test: verify player.hand contains 1 card with race=BEAST
          after the Battlecry resolves.
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import DiscoverMinion
        return DiscoverMinion(source.controller, race=Race.BEAST)


# ── BGS_020: Primalfin Lookout ──────────────────────────────────────────
class PrimalfinLookoutScript:
    """
    Natural language: Battlecry: If you control another Murloc, Discover a Murloc.

    Formal spec:
      1. Check if source.controller's board has at least one other Murloc
      2. If yes: select a random Murloc from the minion pool and add to hand
      3. If no: nothing happens

    Test: verify no Discover when Primalfin is the only Murloc;
          verify Discover triggers when another Murloc is present.
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import DiscoverMinion
        murlocs = [m for m in source.controller.get_board_minions()
                   if m is not source and not m.dead
                   and m.race in (Race.MURLOC, Race.ALL)]
        if not murlocs:
            return None
        return DiscoverMinion(source.controller, race=Race.MURLOC)


# ── BGS_123: Tavern Tempest ─────────────────────────────────────────────
class TavernTempestScript:
    """
    Natural language: Battlecry: Get a random Elemental.

    Formal spec:
      1. Select a random Elemental from the minion pool
      2. Add it to source.controller.hand (Zone.HAND)

    Test: verify player.hand contains 1 card with race=ELEMENTAL.
    """

    @staticmethod
    def battlecry(source, game):
        return GetRandomMinion(source.controller, race=Race.ELEMENTAL)


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Avenge — Summon
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG34_403: Eternal Tycoon ───────────────────────────────────────────
class EternalTycoonScript:
    """
    Natural language: Avenge ({0}): Summon an Eternal Knight.
    It attacks immediately.

    Formal spec:
      1. Create an Eternal Knight token (card_id="BG25_008")
      2. Summon it on source.controller's board
      3. The summoned Eternal Knight attacks an enemy minion immediately

    Test: verify an Eternal Knight is summoned and that the board
          has the correct count after the Avenge resolves.
    """

    @staticmethod
    def avenge(source, game):
        token = game.create_minion("BG25_008")
        return [
            Summon(source.controller, token),
            AttackImmediately(token),
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Deathrattle — Buff/damage spread
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG29_815: Nightbane, Ignited ────────────────────────────────────────
class NightbaneScript:
    """
    Natural language: Deathrattle: Give {0} different friendly minions
    this minion's Attack.

    Formal spec:
      1. Collect all friendly minions except self
      2. Randomly select min(COUNT, len(candidates)) distinct minions
      3. Buff each selected minion's Attack by source.atk

    Note: {0} parameter defaults to 2. The exact value is stored in
    CardDefs.xml and is not yet extracted into our JSON data pipeline.
    """

    COUNT = 2  # {0} from CardDefs.xml

    @staticmethod
    def deathrattle(source, game):
        import random
        candidates = [m for m in source.controller.get_board_minions()
                      if m is not source and not m.dead]
        if not candidates:
            return None
        count = min(NightbaneScript.COUNT, len(candidates))
        targets = random.sample(candidates, count)
        actions = [Buff(t, atk=source.atk, health=0) for t in targets]
        return actions


# ── BG33_828: Ship Master Eudora ────────────────────────────────────────
class ShipMasterEudoraScript:
    """
    Natural language: Deathrattle: Give your minions +{0}/+{1}.
    Golden ones keep it permanently.

    Formal spec:
      1. For each friendly minion on board:
         - Non-golden Eudora: apply Buff(+2/+2, temporary=True)
           (cleared after combat)
         - Golden Eudora: apply Buff(+2/+2, temporary=False)
           (permanent, persists across combats)
    """

    BONUS_ATK = 2   # {0}
    BONUS_HEALTH = 2  # {1}

    @staticmethod
    def deathrattle(source, game):
        is_permanent = source.is_golden
        actions = []
        for m in source.controller.get_board_minions():
            if not m.dead:
                actions.append(Buff(m,
                                    atk=ShipMasterEudoraScript.BONUS_ATK,
                                    health=ShipMasterEudoraScript.BONUS_HEALTH,
                                    temporary=not is_permanent))
        return actions


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Deathrattle — Summon specific token
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG26_801: Rylak Metalhead ──────────────────────────────────────────
class RylakMetalheadScript:
    """
    Natural language: Deathrattle: Trigger the Battlecry of an adjacent minion.

    Formal spec:
      1. Find the minion to the left and right of Rylak on the board
      2. Randomly select one adjacent minion
      3. Trigger its Battlecry as if it were just played
    """

    @staticmethod
    def deathrattle(source, game):
        import random
        board = source.controller.board if source.controller else []
        try:
            idx = board.index(source)
        except ValueError:
            return None
        adj_options = []
        for offset in (-1, 1):
            adj_idx = idx + offset
            if 0 <= adj_idx < len(board):
                m = board[adj_idx]
                if not m.dead and m.battlecry:
                    adj_options.append(m)
        if not adj_options:
            return None
        target = random.choice(adj_options)
        return TriggerBattlecry(target)


# ── BGS_012: Kangor's Apprentice ────────────────────────────────────────
class KangorsApprenticeScript:
    """
    Natural language: Deathrattle: Summon plain copies of your
    first 2 Mechs that died this combat.

    Formal spec:
      1. Read game._combat_death_log, filtered by source.controller
      2. Take the first 2 that have race=MECH
      3. For each, create a fresh minion from the same card_id
      4. Summon them on source.controller's board
    """

    @staticmethod
    def deathrattle(source, game):
        actions = []
        count = 0
        for dead in game._combat_death_log:
            if dead.controller is not source.controller:
                continue
            if dead.race != Race.MECH:
                continue
            if dead.get_tag(GameTag.CARD_ID) == source.get_tag(GameTag.CARD_ID):
                continue  # Don't copy self
            if count >= 2:
                break
            copy_minion = game.create_minion(dead.get_tag(GameTag.CARD_ID))
            actions.append(Summon(source.controller, copy_minion))
            count += 1
        return actions


# ── BG32_172: Auto Assembler ────────────────────────────────────────────
class AutoAssemblerScript:
    """
    Natural language: Deathrattle: Summon an Ancestral Automaton.

    Formal spec:
      1. Create an Ancestral Automaton token (card_id="BG_TTN_401")
      2. Summon it on source.controller's board

    Test: verify an Ancestral Automaton (3/4 Mech) is summoned
          after Auto Assembler dies.
    """

    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("BG_TTN_401")
        return Summon(source.controller, token)


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Start of Combat — Buff tribal
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG21_014: Prized Promo-Drake ─────────────────────────────────────────
class PrizedPromoDrakeScript:
    """Start of Combat: Give your Dragons +2/+2."""
    @staticmethod
    def start_of_combat(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if m.race in (Race.DRAGON, Race.ALL):
                actions.append(Buff(m, atk=2, health=2))
        return actions


# ── BG24_500: Amber Guardian ────────────────────────────────────────────
class AmberGuardianScript:
    """Start of Combat: Give another friendly Dragon +2/+2 and Divine Shield."""
    @staticmethod
    def start_of_combat(source, game):
        dragons = [m for m in source.controller.get_board_minions()
                   if m is not source and m.race in (Race.DRAGON, Race.ALL)]
        if dragons:
            target = random.choice(dragons)
            return [
                Buff(target, atk=2, health=2),
                GainKeyword(target, GameTag.DIVINE_SHIELD),
            ]
        return None


# ── BG26_805: Humming Bird ──────────────────────────────────────────────
class HummingBirdScript:
    """Start of Combat: For the rest of this combat, your Beasts have +1 Attack."""
    @staticmethod
    def start_of_combat(source, game):
        actions = []
        for m in source.controller.get_board_minions():
            if m.race in (Race.BEAST, Race.ALL):
                actions.append(Buff(m, atk=1, health=0))
        return actions


# ── BG32_330: Flighty Scout ─────────────────────────────────────────────
class FlightyScoutScript:
    """Start of Combat: If this is in your hand, summon a copy of it."""
    @staticmethod
    def start_of_combat(source, game):
        if source.zone != getattr(source, 'zone', None):
            return None
        if source.zone != Zone.HAND:
            return None
        copy_minion = game.create_minion(source.get_tag(GameTag.CARD_ID))
        return Summon(source.controller, copy_minion)


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Deathrattle — Get/Summon random tribal
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG25_806: Sly Raptor ─────────────────────────────────────────────────
class SlyRaptorScript:
    """
    Natural language: Deathrattle: Summon a random Beast. Set its stats to 7/7.

    Formal spec:
      1. Pick a random Beast from the minion pool
      2. Summon it
      3. Buff it to 7/7
    """
    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.actions import GetRandomMinion
        # Get a random Beast and summon it directly to board (not hand)
        candidates = []
        for cid, data in game.card_db._cards.items():
            from hsrl.core.enums import CardType
            if data.cardtype != CardType.MINION:
                continue
            if data.race != Race.BEAST:
                continue
            # Exclude tokens and Sly Raptor itself
            if cid.endswith('t') or cid == 'BG25_806':
                continue
            candidates.append(cid)
        if not candidates:
            return None
        chosen_id = random.choice(candidates)
        token = game.create_minion(chosen_id)
        # Set stats to 7/7
        token.set_tag(GameTag.BASE_ATK, 7)
        token.set_tag(GameTag.BASE_HEALTH, 7)
        token.set_tag(GameTag.HEALTH, 7)
        return Summon(source.controller, token)


# ── BG26_148: Scrap Scraper ──────────────────────────────────────────────
class ScrapScraperScript:
    """
    Natural language: Deathrattle: Get a random Magnetic Mech.

    Formal spec:
      1. Select a random Mech with MAGNETIC keyword from the pool
      2. Add it to source.controller.hand
    """
    @staticmethod
    def deathrattle(source, game):
        return GetRandomMinion(source.controller, race=Race.MECH)


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Rally
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG33_323: Dustbone Devastator ────────────────────────────────────────
class DustboneDevastatorScript:
    """Rally: Your Undead have +1 Attack this game (wherever they are)."""
    @staticmethod
    def rally(source, game):
        return ApplyGlobalAura(source.controller, atk=1, health=0, race_filter=Race.UNDEAD)


# ── BGS_078: Monstrous Macaw ─────────────────────────────────────────────
class MonstrousMacawScript:
    """
    Natural language: Rally: Trigger your left-most Deathrattle (except this minion's).

    Formal spec:
      1. Find the leftmost friendly minion with a deathrattle (excluding self)
      2. Trigger its deathrattle as if it died
    """
    @staticmethod
    def rally(source, game):
        board = source.controller.board if source.controller else []
        for m in board:
            if m is source or m.dead:
                continue
            dr = m.deathrattle
            if dr:
                if isinstance(dr, (list, tuple)):
                    return list(dr)
                return dr
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Complex Battlecry
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG26_525: Imposing Percussionist ─────────────────────────────────────
class ImposingPercussionistScript:
    """
    Natural language: Battlecry: Discover a Demon. Deal damage to your
    hero equal to its Tier.

    Formal spec:
      1. Pick a random Demon from the pool
      2. Add it to hand
      3. Deal damage to the hero equal to the minion's tech_level
    """
    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import DiscoverMinion
        import random
        # Get candidate demons to determine tier
        candidates = []
        for cid, data in game.card_db._cards.items():
            if data.cardtype == getattr(data, 'cardtype', None):
                from hsrl.core.enums import CardType
                if data.cardtype != CardType.MINION:
                    continue
                if data.race == Race.DEMON:
                    candidates.append((cid, data.tech_level))
        if not candidates:
            return None
        chosen_id, tier = random.choice(candidates)
        # Add to hand
        from hsrl.core.actions import AddToHand, DealDamageToHero
        return [
            AddToHand(source.controller, chosen_id),
            DealDamageToHero(source.controller, tier),
        ]


# ── BG28_550: Rodeo Performer ────────────────────────────────────────────
class RodeoPerformerScript:
    """
    Natural language: Battlecry: Discover a Tavern spell.

    Formal spec:
      1. Call DiscoverSpell with no tier restriction
      2. A random Tavern spell is created and added to hand
    """
    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import DiscoverSpell
        return DiscoverSpell(source.controller)


# ═══════════════════════════════════════════════════════════════════════════════
# Spellcraft Minion Scripts — Naga Spellcraft effects
# ═══════════════════════════════════════════════════════════════════════════════

# ── BG23_008: Glowscale ──────────────────────────────────────────────────
class GlowscaleScript:
    """Spellcraft: Give a minion Divine Shield until next turn.

    Formal spec:
      1. Spellcraft generates BG23_008t (Glowing Crown)
      2. Glowing Crown on_play gives Divine Shield to a random friendly minion
    """
    @staticmethod
    def spellcraft(source, game):
        return "BG23_008t"

# ── BG31_920: Darkcrest Strategist ───────────────────────────────────────
class DarkcrestStrategistScript:
    """Spellcraft: Get a random Tier X Naga.

    Formal spec:
      1. Spellcraft generates BG31_920t (Evolving Strategy)
      2. Evolving Strategy on_play adds a random Naga to hand
    """
    @staticmethod
    def spellcraft(source, game):
        return "BG31_920t"

# ── BG33_319: Rimescale Priestess ────────────────────────────────────────
class RimescalePriestessScript:
    """Spellcraft: Get a random Tavern spell that gives stats.

    Formal spec:
      1. Spellcraft generates BG33_319t (Rime or Reason)
      2. Rime or Reason on_play adds a random stat-giving tavern spell to hand
    """
    @staticmethod
    def spellcraft(source, game):
        return "BG33_319t"

# ── BG23_004: Deep-Sea Angler ────────────────────────────────────────────
class DeepSeaAnglerScript:
    """Spellcraft: Give a minion +2/+2 and Taunt until next turn.

    Formal spec:
      1. Spellcraft generates BG23_004t (Angler's Lure)
      2. Angler's Lure on_play buffs +2/+2 and gives Taunt to a random friendly minion
    """
    @staticmethod
    def spellcraft(source, game):
        return "BG23_004t"

# ── BG23_007: Waverider ──────────────────────────────────────────────────
class WaveriderScript:
    """Spellcraft: Give a minion +2/+2. If it's a Naga, also give Windfury.

    Formal spec:
      1. Spellcraft generates BG23_007t (Undersea Mount)
      2. Undersea Mount on_play buffs +2/+2 and gives Windfury if target is Naga
    """
    @staticmethod
    def spellcraft(source, game):
        return "BG23_007t"

# ── BG26_501: Reef Riffer ───────────────────────────────────────────────
class ReefRifferScript:
    """Spellcraft: Give a minion stats equal to your Tier.

    Formal spec:
      1. Spellcraft generates BG26_501t (Sick Riffs)
      2. Sick Riffs on_play buffs a random friendly minion by player's tavern tier
    """
    @staticmethod
    def spellcraft(source, game):
        return "BG26_501t"


class SurfNSurfScript:
    """Spellcraft: Give a minion 'Deathrattle: Summon a 3/2 Crab' until next turn.

    Formal spec:
      1. Spellcraft generates BG27_004t (Crab Mount)
      2. Crab Mount on_play gives target TEMPORARY_DEATHRATTLE + GainSpecificDeathrattle(BG27_004t2)
    """

    @staticmethod
    def spellcraft(source, game):
        return "BG27_004t"


class SeaWitchZarjiraScript:
    """Spellcraft: Choose a different minion in the Tavern to get a copy of.

    Formal spec:
      1. Spellcraft generates BG27_514t (Siren's Song)
      2. Siren's Song on_play copies a random tavern minion to hand
    """

    @staticmethod
    def spellcraft(source, game):
        return "BG27_514t"


# ═══════════════════════════════════════════════════════════════════════════════
# "Get X" Token Cards — BC/DR that add specific named tokens to hand
# ═══════════════════════════════════════════════════════════════════════════════


# ── BG27_002: Oozeling Gladiator ───────────────────────────────────────
class OozelingGladiatorScript:
    """
    Natural language: Battlecry: Get two Slimy Shields that give
    +1/+1 and Taunt.

    Formal spec:
      1. Add 2 Slimy Shield spells (card_id=BG27_002t) to controller's hand

    Test: verify player.hand has 2 cards of type SPELL with card_id BG27_002t
    """

    @staticmethod
    def battlecry(source, game):
        return [
            AddToHand(source.controller, "BG27_002t"),
            AddToHand(source.controller, "BG27_002t"),
        ]


# ── BG32_170: Metallic Hunter ──────────────────────────────────────────
class MetallicHunterScript:
    """
    Natural language: Deathrattle: Get a Pointy Arrow.

    Formal spec:
      1. Add 1 Pointy Arrow spell (card_id=EBG_Spell_014) to controller's hand

    Test: verify player.hand has 1 card with card_id EBG_Spell_014 after deathrattle
    """

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "EBG_Spell_014")


# ── BG32_111: Nightmare Par-tea Guest ───────────────────────────────────
class NightmareParteaGuestScript:
    """
    Natural language: Battlecry and Deathrattle: Get a Misplaced Tea Set.

    Formal spec:
      1. Add 1 Misplaced Tea Set spell (card_id=BG28_888) to controller's hand

    Test: verify player.hand has a BG28_888 spell after battlecry and after deathrattle
    """

    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, "BG28_888")

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "BG28_888")


# ── BG33_809: Divine Sparkbot ───────────────────────────────────────────
class DivineSparkbotScript:
    """
    Natural language: Taunt, Divine Shield
    Deathrattle: Get a Sanctify.

    Formal spec:
      1. On death, add 1 Sanctify spell (card_id=BG33_817) to controller's hand

    Test: verify player.hand has a BG33_817 spell after deathrattle
    """

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "BG33_817")


# ── BG32_891: Shadowdancer ──────────────────────────────────────────────
class ShadowdancerScript:
    """
    Natural language: Taunt
    Deathrattle: Get a Staff of Enrichment.

    Formal spec:
      1. On death, add 1 Staff of Enrichment spell (card_id=BG28_886) to controller's hand

    Test: verify player.hand has a BG28_886 spell after deathrattle
    """

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "BG28_886")


# ── BG34_694: Wintergrasp Ghoul ─────────────────────────────────────────
class WintergraspGhoulScript:
    """
    Natural language: Deathrattle: Get a Tomb Turning.

    Formal spec:
      1. On death, add 1 Tomb Turning spell (card_id=BG34_888) to controller's hand

    Test: verify player.hand has a BG34_888 spell after deathrattle
    """

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "BG34_888")


# ── BG35_143: Deepwater Chieftain ───────────────────────────────────────
class DeepwaterChieftainScript:
    """
    Natural language: Battlecry and Deathrattle: Get a Deepwater Clan.

    Formal spec:
      1. Add 1 Deepwater Clan spell (card_id=BG35_149) to controller's hand

    Test: verify player.hand has a BG35_149 spell after battlecry and after deathrattle
    """

    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, "BG35_149")

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "BG35_149")


# ── BG35_881: Leyline Surfacer ──────────────────────────────────────────
class LeylineSurfacerScript:
    """
    Natural language: Battlecry and Deathrattle: Get an Arcane Absorption.

    Formal spec:
      1. Add 1 Arcane Absorption spell (card_id=BG35_911) to controller's hand

    Test: verify player.hand has a BG35_911 spell after battlecry and after deathrattle
    """

    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, "BG35_911")

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, "BG35_911")


# ── BG35_882: Firelands Fugitive ────────────────────────────────────────
class FirelandsFugitiveScript:
    """
    Natural language: Battlecry: Get a Conflagration.

    Formal spec:
      1. Add 1 Conflagration spell (card_id=BG35_910) to controller's hand

    Test: verify player.hand has a BG35_910 spell after battlecry
    """

    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, "BG35_910")


# ── BG34_319: Highkeeper Ra ─────────────────────────────────────────────
class HighkeeperRaScript:
    """
    Natural language: Battlecry, Deathrattle, and Rally:
    Get a random Tier 6 minion.

    Formal spec:
      1. GetRandomMinion(controller, min_tier=6, max_tier=6)
      2. The minion is added to hand (Zone.HAND)

    Test: verify player.hand has a card added, verify its tech_level == 6
    """

    @staticmethod
    def battlecry(source, game):
        return GetRandomMinion(source.controller, min_tier=6, max_tier=6)

    @staticmethod
    def deathrattle(source, game):
        return GetRandomMinion(source.controller, min_tier=6, max_tier=6)

    @staticmethod
    def rally(source, game):
        return GetRandomMinion(source.controller, min_tier=6, max_tier=6)


# ── BG34_632: Incubation Researcher ─────────────────────────────────────
class IncubationResearcherScript:
    """
    Natural language: Avenge (4): Get a random Chromadrake.

    Formal spec:
      1. On avenge(4) trigger, pick random from 5 Chromadrake token IDs
      2. AddToHand with the selected card_id

    Test: verify player.hand has a Chromadrake minion after avenge trigger
    """

    @staticmethod
    def avenge(source, game):
        chromadrakes = [
            "BG34_634_Gt",  # Blue 6/6
            "BG34_635_Gt",  # Black 8/8 Taunt
            "BG34_636_Gt",  # Green 5/5 Divine Shield
            "BG34_637_Gt",  # Bronze 4/4 Reborn
            "BG34_638_Gt",  # Red 7/7 Windfury
        ]
        chosen = random.choice(chromadrakes)
        return AddToHand(source.controller, chosen)


# ── BG34_633: Draconic Warden ───────────────────────────────────────────
class DraconicWardenScript:
    """
    Natural language: Battlecry and Deathrattle: Get a random Chromadrake.

    Formal spec:
      1. Pick random Chromadrake token, AddToHand

    Test: verify player.hand has a Chromadrake minion after battlecry and deathrattle
    """

    @staticmethod
    def _get_random_chromadrake():
        chromadrakes = [
            "BG34_634_Gt", "BG34_635_Gt", "BG34_636_Gt",
            "BG34_637_Gt", "BG34_638_Gt",
        ]
        return random.choice(chromadrakes)

    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, DraconicWardenScript._get_random_chromadrake())

    @staticmethod
    def deathrattle(source, game):
        return AddToHand(source.controller, DraconicWardenScript._get_random_chromadrake())


# ── BG25_041: Felemental ─────────────────────────────────────────────────
class FelementalScript:
    """
    Natural language: Battlecry: Give minions in the Tavern +1/+1 this game.

    Formal spec:
      - Trigger: Battlecry (recruit phase, when played from hand)
      - Effect: Add a TavernBuff(+1/+1, all races, all tiers) to the player
      - Persistence: Buff applies to every future refresh_tavern() for this game

    Test: verify player.tavern_buffs gets +1/+1 for all minions
    """

    @staticmethod
    def battlecry(source, game):
        return BuffTavern(source.controller, atk=1, health=1)


# ── BG31_815: Dune Dweller ───────────────────────────────────────────────
class DuneDwellerScript:
    """
    Natural language: Battlecry: Give Elementals in the Tavern +1/+1 this game.

    Formal spec:
      - Trigger: Battlecry
      - Effect: Add a TavernBuff(+1/+1, race_filter=ELEMENTAL) to the player
      - Only Elementals drawn in future refreshes receive the buff

    Test: verify only Elementals in tavern get +1/+1
    """

    @staticmethod
    def battlecry(source, game):
        return BuffTavern(source.controller, atk=1, health=1, race_filter=Race.ELEMENTAL)


# ── BG35_152: Void Pup Trainer ───────────────────────────────────────────
class VoidPupTrainerScript:
    """
    Natural language: Battlecry: Give minions in the Tavern from Tier 3
    and below +2/+2 this game.

    Formal spec:
      - Trigger: Battlecry
      - Effect: Add a TavernBuff(+2/+2, all races, max_tier=3) to the player
      - Only Tier 1-3 minions drawn in future refreshes receive the buff

    Test: verify only Tier 1-3 minions in tavern get +2/+2
    """

    @staticmethod
    def battlecry(source, game):
        return BuffTavern(source.controller, atk=2, health=2, max_tier=3)


# ── BG27_556: Diremuck Forager ──────────────────────────────────────────
class DiremuckForagerScript:
    """
    Natural language: Start of Combat: When you have space, summon the
    highest-Attack Murloc from your hand for this combat only.

    Formal spec:
      - Trigger: Start of Combat
      - Filter: Murlocs in hand
      - Selection: max(atk)
      - Effect: SummonFromHandForCombat(controller, selected_murloc)
      - Scope: combat only — returns to hand after combat

    Test: verify highest ATK Murloc moves from hand to board, marked COMBAT_SUMMON
    """

    @staticmethod
    def start_of_combat(source, game):
        murlocs = [m for m in source.controller.hand
                   if m.get_tag(GameTag.RACE) == Race.MURLOC]
        if not murlocs:
            return None
        target = max(murlocs, key=lambda m: m.atk)
        return SummonFromHandForCombat(source.controller, target)


# ── BG34_140: Expert Aviator ────────────────────────────────────────────
class ExpertAviatorScript:
    """
    Natural language: Rally: Summon the highest-Attack minion from
    your hand for this combat only.

    Formal spec:
      - Trigger: Rally (after this attacks)
      - Filter: all minions in hand
      - Selection: max(atk)
      - Effect: SummonFromHandForCombat(controller, selected_minion)

    Test: verify highest ATK minion summoned from hand, marked COMBAT_SUMMON
    """

    @staticmethod
    def rally(source, game):
        candidates = [m for m in source.controller.hand
                      if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
        if not candidates:
            return None
        target = max(candidates, key=lambda m: m.atk)
        return SummonFromHandForCombat(source.controller, target)


# ── BG31_835: Deathly Striker ───────────────────────────────────────────
class DeathlyStrikerScript:
    """
    Natural language: Avenge(X): Get a random Undead.
    Deathrattle: Summon it from your hand for this combat only.

    Formal spec:
      - Avenge: GetRandomMinion(controller, race=UNDEAD) → stores reference
      - Deathrattle: SummonFromHandForCombat(controller, stored_undead)
      - The stored undead is the one obtained via Avenge

    Test: verify Avenge adds Undead to hand, Deathrattle summons that specific one
    """

    @staticmethod
    def avenge(source, game):
        result = GetRandomMinion(source.controller, race=Race.UNDEAD,
                                 min_tier=1, max_tier=6)
        # result is a list: [GetRandomMinion action]
        if result and isinstance(result, GetRandomMinion):
            # Store reference to track later
            source._avenge_undead_action = result
        return result

    @staticmethod
    def deathrattle(source, game):
        # Find the stored undead in hand (the one obtained via Avenge)
        if hasattr(source, '_avenge_undead_action'):
            action = source._avenge_undead_action
            target_card_id = action.card_id if hasattr(action, 'card_id') else None
            if target_card_id:
                for m in source.controller.hand:
                    if m.get_tag(GameTag.CARD_ID) == target_card_id:
                        return SummonFromHandForCombat(source.controller, m)
        return None


# ── BG31_810: Ultraviolet Ascendant ──────────────────────────────────────
class UltravioletAscendantScript:
    """
    Natural language: Start of Combat: Give your other Elementals +1/+2.
    Improves after you play an Elemental!

    Formal spec:
      - on_summon: register ELEMENTAL_PLAYED listener → IncrementImproveCounter(self)
      - start_of_combat: buff ALL other friendly Elementals by
        +(1+counter)/+(2+2*counter)
      - Counter persists on the card for the entire game

    Test: summon UV Ascendant, play 2 Elementals, verify counter=2,
    start of combat buff is +3/+6 to all other Elementals
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import IncrementImproveCounter
        listener = EventListener(
            event_name="ELEMENTAL_PLAYED",
            action=IncrementImproveCounter(source),
            condition=lambda m, p: m != source,
        )
        game.register_listener(source, listener)
        return None

    @staticmethod
    def start_of_combat(source, game):
        from hsrl.core.actions import Buff
        from hsrl.core.enums import GameTag, Race as GameRace
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        board = source.controller.board
        # Buff ALL other friendly Elementals
        candidates = [m for m in board
                      if not m.dead and m != source
                      and m.race in (GameRace.ELEMENTAL, Race.ALL)]
        if not candidates:
            return None
        mult = 1 + counter
        return [Buff(m, atk=1 * mult, health=2 * mult) for m in candidates]


# ── BG26_814: Lovesick Balladist ─────────────────────────────────────────
class LovesickBalladistScript:
    """
    Natural language: Battlecry: Give a Pirate +{0}/+{1}.
    Improved by each Gold you spent this turn!

    Formal spec:
      - battlecry: read player's GOLD_SPENT_THIS_TURN, buff a friendly Pirate
        by gold_spent * (+1/+2)
      - During recruit: player chooses the target Pirate
      - During combat: target is random
      - Per-turn: GOLD_SPENT_THIS_TURN resets at start of each recruit phase

    Test: spend 5 gold buying other minions, play Lovesick Balladist,
    verify battlecry gives +5/+10 to a friendly Pirate
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import Buff, TargetedAction
        from hsrl.core.enums import GameTag, Race as GameRace
        gold_spent = source.controller.get_tag(GameTag.GOLD_SPENT_THIS_TURN, 0)

        def filter_fn():
            board = source.controller.board
            return [m for m in board
                    if not m.dead and m != source and m.race == GameRace.PIRATE]

        if not filter_fn():
            return None

        def action_factory(target):
            return Buff(target, atk=1 * gold_spent, health=2 * gold_spent)

        return TargetedAction(filter_fn, action_factory,
                              label="Give a Pirate +{0}/+{1}".format(gold_spent, gold_spent * 2))


# ── BG28_303: Disguised Graverobber ─────────────────────────────────────
class DisguisedGraverobberScript:
    """
    Natural language: Battlecry: Destroy a friendly Undead to get
    a plain copy of it.

    Formal spec:
      - During recruit: player chooses the target Undead
      - During combat: random target
      - Destroy the target, then create a fresh plain copy (same card_id)
        via AddToHand
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            return [
                m
                for m in source.controller.get_board_minions()
                if m is not source and not m.dead and m.race in (Race.UNDEAD, Race.ALL)
            ]

        if not filter_fn():
            return None

        def action_factory(target):
            card_id = target.get_tag(GameTag.CARD_ID)
            return [Destroy(target), AddToHand(source.controller, card_id)]

        return TargetedAction(filter_fn, action_factory,
                              label="Destroy a friendly Undead")


# ── BG35_150: Laboratory Assistant ──────────────────────────────────────
class LaboratoryAssistantScript:
    """
    Natural language: Battlecry: Add a Fodder to your next {0} Refreshes.

    Status: ACTIVE

    Formal spec:
      1. Set FODDER_REFRESH_REMAINING counter on source (3 normal, 6 golden)
      2. Register a persistent TAVERN_REFRESH listener with
         AddFodderToRandomTavernMinion
      3. Each refresh: decrement counter, add FODDER to random tavern minion
      4. When counter reaches 0: listener persists but no-ops

    Test: play Lab Assistant, refresh tavern 3 times —
          each adds FODDER tag to 1 tavern minion, 4th refresh does nothing.
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import AddFodderToRandomTavernMinion

        count = 6 if source.is_golden else 3
        source.set_tag(GameTag.FODDER_REFRESH_REMAINING, count)

        listener = EventListener(
            event_name="TAVERN_REFRESH",
            action=AddFodderToRandomTavernMinion(source.controller),
            condition=lambda player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG34_865: En-Djinn Blazer ────────────────────────────────────────────
class EnDjinnBlazerScript:
    """
    Natural language: Battlecry: After the Tavern is Refreshed this game,
    give a random minion in it +3/+3.

    Formal spec:
      - battlecry: register TAVERN_REFRESH listener → BuffRandomTavernMinion
      - Effect persists for the entire game
      - Each refresh triggers one random tavern minion buff

    Test: play En-Djinn Blazer, refresh tavern, verify one tavern minion got +3/+3
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import BuffRandomTavernMinion
        listener = EventListener(
            event_name="TAVERN_REFRESH",
            action=BuffRandomTavernMinion(source.controller, atk=3, health=3),
            condition=lambda player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG34_856: Waveling ───────────────────────────────────────────────────
class WavelingScript:
    """
    Natural language: Deathrattle: After the Tavern is Refreshed this game,
    give a random minion in it +3/+1.

    Formal spec:
      - deathrattle: register TAVERN_REFRESH listener → BuffRandomTavernMinion
      - Effect persists for the entire game
      - Each refresh triggers one random tavern minion buff

    Test: trigger Waveling DR, refresh tavern, verify one tavern minion got +3/+1
    """

    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import BuffRandomTavernMinion
        listener = EventListener(
            event_name="TAVERN_REFRESH",
            action=BuffRandomTavernMinion(source.controller, atk=3, health=1),
            condition=lambda player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG25_040: Blazing Skyfin ─────────────────────────────────────────────
class BlazingSkyfinScript:
    """
    Natural language: After you trigger a Battlecry, gain +1/+1.

    Formal spec:
      - on_summon: register BATTLECRY_TRIGGER listener → Buff(self, +1/+1)
      - Listener condition: only controller's battlecries
      - Effect persists while minion is alive on board

    Test: summon Skyfin + another minion, trigger a battlecry,
    verify Skyfin gained +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import Buff
        listener = EventListener(
            event_name="BATTLECRY_TRIGGER",
            action=Buff(source, atk=1, health=1),
            condition=lambda t, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BGS_041: Kalecgos, Arcane Aspect ─────────────────────────────────────
class KalecgosScript:
    """
    Natural language: After you trigger a Battlecry,
    give your Dragons +1/+1.

    Formal spec:
      - on_summon: register BATTLECRY_TRIGGER listener → buff all friendly Dragons
      - Listener condition: only controller's battlecries
      - Effect persists while Kalecgos is alive on board

    Test: summon Kalecgos + Dragons, trigger a battlecry,
    verify all Dragons (except dead) got +1/+1
    """

    class _BuffAllFriendlyDragons(Action):
        def __init__(self, player, atk, health):
            super().__init__()
            self.player = player
            self._atk = atk
            self._health = health

        def do(self, source, game, target=None):
            from hsrl.core.enums import Race as GameRace, GameTag
            from hsrl.core.actions import Buff
            for m in self.player.board:
                if not m.dead and m.get_tag(GameTag.RACE) == GameRace.DRAGON:
                    Buff(m, atk=self._atk, health=self._health).do(source, game)

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        listener = EventListener(
            event_name="BATTLECRY_TRIGGER",
            action=KalecgosScript._BuffAllFriendlyDragons(
                source.controller, atk=1, health=1),
            condition=lambda t, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG27_016: Champion of Sargeras ───────────────────────────────────────
class ChampionOfSargerasScript:
    """
    Natural language: Battlecry and Deathrattle: Minions in the Tavern
    have +2/+1 this game.

    Formal spec:
      - battlecry: BuffTavern(player, atk=2, health=1)
      - deathrattle: BuffTavern(player, atk=2, health=1)
      - Stacking: multiple triggers stack (both BC and DR add separate buffs)

    Test: trigger BC, verify tavern_buffs has +2/+1; trigger DR, verify second buff
    """

    @staticmethod
    def battlecry(source, game):
        return BuffTavern(source.controller, atk=2, health=1)

    @staticmethod
    def deathrattle(source, game):
        return BuffTavern(source.controller, atk=2, health=1)


# ── BG26_354: Choral Mrrrglr ─────────────────────────────────────────────
class ChoralMrrrglrScript:
    """
    Natural language: Start of Combat: Gain the stats of all the
    minions in your hand.

    Formal spec:
      - start_of_combat: sum ATK and Health of all minions in hand,
        buff self by that total amount
      - Only minions count (not spells, not blood gems)
      - Hand minions are not consumed

    Test: put minions in hand, trigger SoC, verify Choral gained their stats
    """

    @staticmethod
    def start_of_combat(source, game):
        from hsrl.core.actions import Buff
        from hsrl.core.enums import GameTag, CardType as CT
        hand = source.controller.hand
        hand_minions = [m for m in hand
                        if m.get_tag(GameTag.CARDTYPE) == CT.MINION]
        total_atk = sum(m.atk for m in hand_minions)
        total_health = sum(m.max_health for m in hand_minions)
        if total_atk == 0 and total_health == 0:
            return None
        return Buff(source, atk=total_atk, health=total_health)


# ── BG34_320: The Last One Standing ──────────────────────────────────────
class TheLastOneStandingScript:
    """
    Natural language: Rally: Give a friendly minion of each type
    +2/+2 permanently.

    Formal spec:
      - rally: for each unique race on friendly board (excluding self),
        pick one minion of that race and buff it +2/+2
      - Each race buffed once per Rally trigger
      - Dead minions are skipped

    Test: set up minions of 3 different races, trigger Rally,
    verify one minion per race got +2/+2
    """

    class _BuffOnePerRace(Action):
        def __init__(self, player, atk, health):
            super().__init__()
            self.player = player
            self._atk = atk
            self._health = health

        def do(self, source, game, target=None):
            from hsrl.core.enums import GameTag
            from hsrl.core.actions import Buff
            boarded = {}
            for m in self.player.board:
                if not m.dead and m != source:
                    race = m.get_tag(GameTag.RACE)
                    if race and race not in boarded:
                        boarded[race] = m
            for m in boarded.values():
                Buff(m, atk=self._atk, health=self._health).do(source, game)

    @staticmethod
    def rally(source, game):
        return TheLastOneStandingScript._BuffOnePerRace(
            source.controller, atk=2, health=2)


# ── BG32_822: Fire-forged Evoker ─────────────────────────────────────────
class FireForgedEvokerScript:
    """
    Natural language: Start of Combat: Give your Dragons +{0}/+{1}.
    Improves permanently after you cast a Tavern spell.

    Formal spec:
      1. on_summon: register TAVERN_SPELL_CAST listener → IncrementImproveCounter(source)
         (self-exclusion: condition=lambda t, p: True — no self-exclusion needed
         since the spell is cast by player, not by this minion)
      2. start_of_combat: read IMPROVE_COUNTER, pick random friendly Dragon,
         Buff(target, atk=1*(1+counter), health=2*(1+counter))

    Test: register via on_summon, cast 2 tavern spells (CastTavernSpell),
    trigger SoC, verify Dragon gets +3/+6.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import IncrementImproveCounter
        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=IncrementImproveCounter(source),
        )
        game.register_listener(source, listener)
        return None

    @staticmethod
    def start_of_combat(source, game):
        from hsrl.core.actions import Buff
        from hsrl.core.enums import GameTag, Race as GameRace
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        board = source.controller.board
        mult = 1 + counter
        actions = [Buff(m, atk=1 * mult, health=2 * mult)
                   for m in board
                   if not m.dead and m.race == GameRace.DRAGON]
        return actions if actions else None


# ── BG35_702: Roving Sailor ──────────────────────────────────────────────
class RovingSailorScript:
    """
    Natural language: Battlecry: Give a friendly minion +{0}/+{1}.
    Improved by each Tavern spell you cast this turn!

    Formal spec:
      1. battlecry: read player's TAVERN_SPELLS_CAST_THIS_TURN
      2. During recruit: player chooses the target minion (excluding self)
      3. During combat: random target
      4. Buff target by spell_count * (+1/+2)
      5. If no candidates or spell_count==0, return None

    Test: cast 3 tavern spells via CastTavernSpell, play Roving Sailor,
    verify friendly minion gets +3/+6.
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import Buff, TargetedAction
        from hsrl.core.enums import GameTag
        spell_count = source.controller.get_tag(
            GameTag.TAVERN_SPELLS_CAST_THIS_TURN, 0)

        def filter_fn():
            board = source.controller.board
            return [m for m in board if not m.dead and m != source]

        if not filter_fn() or spell_count == 0:
            return None

        def action_factory(target):
            return Buff(target, atk=1 * spell_count, health=2 * spell_count)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Give +{spell_count}/+{spell_count * 2}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tavern Spell Buff Modifier — "Your Tavern spells give an extra +X/+Y this game"
# ═══════════════════════════════════════════════════════════════════════════════


class BlackChromadrakeScript:
    """Battlecry: Your Tavern spells give an extra +1 Health this game."""

    @staticmethod
    def battlecry(source, game):
        return ImproveTavernSpellBuff(source.controller, health_bonus=1)


class RedChromadrakeScript:
    """Battlecry: Your Tavern spells give an extra +1 Attack this game."""

    @staticmethod
    def battlecry(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1)


class FriendlyGeistScript:
    """Deathrattle: Your Tavern spells give an extra +1 Attack this game."""

    @staticmethod
    def deathrattle(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1)


class TranquilMeditativeScript:
    """Spellcraft: Your Tavern spells give an extra +1/+1 this game."""

    @staticmethod
    def spellcraft(source, game):
        return "BG32_835t"


# ═══════════════════════════════════════════════════════════════════════════════
# On-Sell scripts
# ═══════════════════════════════════════════════════════════════════════════════

# ── BG20_301: Sun-Bacon Relaxer ─────────────────────────────────────────
class SunBaconRelaxerScript:
    """When you sell this, get 2 Blood Gems."""

    @staticmethod
    def on_sell(source, game):
        return GetBloodGem(source.controller, count=2)


# ── BG22_202: Tad ───────────────────────────────────────────────────────
class TadScript:
    """When you sell this, get a random Murloc."""

    @staticmethod
    def on_sell(source, game):
        return GetRandomMinion(source.controller, race=Race.MURLOC)


# ── BGS_115: Sellemental ────────────────────────────────────────────────
class SellementalScript:
    """When you sell this, get a 3/3 Elemental."""

    @staticmethod
    def on_sell(source, game):
        return AddToHand(source.controller, "BGS_115t")


# ── BG33_140: River Skipper ─────────────────────────────────────────────
class RiverSkipperScript:
    """When you sell this, get a random Tier 1 minion."""

    @staticmethod
    def on_sell(source, game):
        return GetRandomMinion(source.controller, max_tier=1)


# ── BG32_860: Shoalfin Mystic ───────────────────────────────────────────
class ShoalfinMysticScript:
    """When you sell this, your Tavern spells give an extra +1/+1 this game."""

    @staticmethod
    def on_sell(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1)


# ── BG31_816: Fire Baller ───────────────────────────────────────────────
class FireBallerScript:
    """When you sell this, give your minions +{0} Attack. Improve your future Ballers."""

    @staticmethod
    def on_sell(source, game):
        class _FireBallerAction(Action):
            def do(self, source_ent, game_ref, target=None):
                player = source.controller
                bonus = player.get_tag(GameTag.BALLER_FIRE_BONUS, 0)
                for m in player.get_board_minions():
                    if not m.dead:
                        game_ref.queue_action(Buff(m, atk=bonus))
                player.set_tag(GameTag.BALLER_FIRE_BONUS, bonus + 1)
        return _FireBallerAction()


# ── BG31_818: Snow Baller ───────────────────────────────────────────────
class SnowBallerScript:
    """When you sell this, give your minions +{0} Health. Improve your future Ballers."""

    @staticmethod
    def on_sell(source, game):
        class _SnowBallerAction(Action):
            def do(self, source_ent, game_ref, target=None):
                player = source.controller
                bonus = player.get_tag(GameTag.BALLER_SNOW_BONUS, 0)
                for m in player.get_board_minions():
                    if not m.dead:
                        game_ref.queue_action(Buff(m, health=bonus))
                player.set_tag(GameTag.BALLER_SNOW_BONUS, bonus + 1)
        return _SnowBallerAction()


# ═══════════════════════════════════════════════════════════════════════════════
# End-of-Turn scripts
# ═══════════════════════════════════════════════════════════════════════════════

# ── BG28_595: Ignition Specialist ───────────────────────────────────────
class IgnitionSpecialistScript:
    """At the end of your turn, get 2 random Tavern spells."""

    @staticmethod
    def end_of_turn(source, game):
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != CardType.SPELL:
                continue
            if card_id.startswith("EXAMPLE_"):
                continue
            candidates.append(card_id)
        if not candidates:
            return None
        chosen = random.sample(candidates, min(2, len(candidates)))

        class _GetSpellsAction(Action):
            def do(self, source_ent, game_ref, target=None):
                for cid in chosen:
                    spell = game_ref.create_spell(cid)
                    spell.controller = source.controller
                    spell.zone = Zone.HAND
                    source.controller.hand.append(spell)
        return _GetSpellsAction()


# ── BG31_178: Marquee Ticker ────────────────────────────────────────────
class MarqueeTickerScript:
    """At the end of your turn, get a random Tavern spell."""

    @staticmethod
    def end_of_turn(source, game):
        candidates = []
        for card_id, data in game.card_db._cards.items():
            if data.cardtype != CardType.SPELL:
                continue
            if card_id.startswith("EXAMPLE_"):
                continue
            candidates.append(card_id)
        if not candidates:
            return None
        chosen = random.choice(candidates)

        class _GetSpellAction(Action):
            def do(self, source_ent, game_ref, target=None):
                spell = game_ref.create_spell(chosen)
                spell.controller = source.controller
                spell.zone = Zone.HAND
                source.controller.hand.append(spell)
        return _GetSpellAction()


# ── BG35_142: Cousin Errgl ──────────────────────────────────────────────
class CousinErrglScript:
    """At the end of your turn, get a Mama Mrrglton or a Papa Mrrglton."""

    @staticmethod
    def end_of_turn(source, game):
        chosen = random.choice(["BG35_140", "BG35_141"])
        return AddToHand(source.controller, chosen)


# ── BG32_821: Felfire Conjurer ──────────────────────────────────────────
class FelfireConjurerScript:
    """At the end of your turn, your Tavern spells give an extra +1/+1 this game."""

    @staticmethod
    def end_of_turn(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1)


# ── BG32_235: Surfing Sylvar ────────────────────────────────────────────
class SurfingSylvarScript:
    """At the end of your turn, give adjacent minions +{0} Attack per friendly Golden."""

    @staticmethod
    def end_of_turn(source, game):
        board = source.controller.get_board_minions()
        left, right = get_adjacent_minions(board, source)
        golden_count = sum(1 for m in board if not m.dead and m.is_golden)
        if golden_count <= 0:
            return None
        actions = []
        if left is not None:
            actions.append(Buff(left, atk=golden_count))
        if right is not None:
            actions.append(Buff(right, atk=golden_count))
        return actions if len(actions) > 1 else (actions[0] if actions else None)


# ── BG35_151: Woodland Defiler ──────────────────────────────────────────
class WoodlandDefilerScript:
    """At the end of your turn, add a Fodder to your next {0} Refreshes."""

    @staticmethod
    def end_of_turn(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import AddFodderToRandomTavernMinion

        count = 6 if source.is_golden else 3
        source.set_tag(GameTag.FODDER_REFRESH_REMAINING, count)

        listener = EventListener(
            event_name="TAVERN_REFRESH",
            action=AddFodderToRandomTavernMinion(source.controller),
            condition=lambda player: player == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Start-of-Turn scripts
# ═══════════════════════════════════════════════════════════════════════════════

# ── BG26_147: Accord-o-Tron ─────────────────────────────────────────────
class AccordOTronScript:
    """At the start of your turn, gain 1 Gold."""

    @staticmethod
    def start_of_turn(source, game):
        return GainGold(source.controller, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 16 Batch: End of Turn / On-Sell / Spellcraft / Tracker Scripts
# ═══════════════════════════════════════════════════════════════════════════════


# ── End of Turn ──────────────────────────────────────────────────────────────

class FamishedFelbatScript:
    """At the end of your turn, your Demons each consume a minion in the Tavern."""

    @staticmethod
    def end_of_turn(source, game):
        from hsrl.core.actions import ConsumeTavernMinion
        actions = []
        for m in source.controller.get_board_minions():
            if m.race == Race.DEMON:
                actions.append(ConsumeTavernMinion(m.controller, m))
        return actions if actions else None


class FlamingEnforcerScript:
    """At the end of your turn, consume the highest-Health minion in the Tavern."""

    @staticmethod
    def end_of_turn(source, game):
        from hsrl.core.actions import ConsumeTavernMinion
        tavern = source.controller.tavern
        if not tavern:
            return None
        return ConsumeTavernMinion(source.controller, source, mode="highest_health")


class FuturefinScript:
    """At the end of your turn, give this minion's stats to the left-most minion in hand."""

    @staticmethod
    def end_of_turn(source, game):
        hand = source.controller.hand
        if not hand:
            return None
        target = hand[0]
        return Buff(target, atk=source.atk, health=source.health)


class RedtuskThornraiserScript:
    """At the end of your turn, get a Blood Gem."""

    @staticmethod
    def end_of_turn(source, game):
        return GetBloodGem(source.controller, count=1)


class SkeletalStraferScript:
    """At the end of your turn, give your minions +1/+1. Avenge: Improve permanently."""

    @staticmethod
    def end_of_turn(source, game):
        scale = source.get_tag(GameTag.PLAGUERUNNER_SCALE, 1)
        actions = []
        for m in source.controller.get_board_minions():
            actions.append(Buff(m, atk=scale, health=scale))
        return actions if actions else None

    @staticmethod
    def avenge(source, game):
        scale = source.get_tag(GameTag.PLAGUERUNNER_SCALE, 1)
        source.set_tag(GameTag.PLAGUERUNNER_SCALE, scale + 1)
        return None


class BrazenBuccaneerScript:
    """At the end of your turn, give your left-most Pirate +1/+1 per card played."""

    @staticmethod
    def end_of_turn(source, game):
        board = source.controller.get_board_minions()
        if not board:
            return None
        cards_played = source.controller.get_tag(GameTag.CARDS_PLAYED_THIS_TURN, 0)
        scale = max(1, cards_played)
        return Buff(board[0], atk=scale, health=scale)


class EarthsongShamanScript:
    """At the end of your turn, play a Blood Gem on all minions. Repeat per keyword."""

    _KEYWORD_TAGS = [GameTag.TAUNT, GameTag.DIVINE_SHIELD, GameTag.POISONOUS,
                     GameTag.VENOMOUS, GameTag.REBORN, GameTag.WINDFURY, GameTag.CLEAVE]

    @classmethod
    def end_of_turn(cls, source, game):
        keyword_count = sum(1 for kt in cls._KEYWORD_TAGS
                            if source.has_tag(kt))
        repeat = keyword_count + 1  # base 1 + 1 per keyword
        actions = []
        for m in source.controller.get_board_minions():
            actions.append(PlayBloodGems(m, count=repeat))
        return actions if actions else None


class UpbeatFrontdrakeScript:
    """At the end of every 3 turns, get a random Dragon."""

    @staticmethod
    def end_of_turn(source, game):
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        counter += 1
        source.set_tag(GameTag.IMPROVE_COUNTER, counter)
        if counter % 3 == 0:
            return GetRandomMinion(source.controller, race=Race.DRAGON)
        return None


class CataclysmicHarbingerScript:
    """At the end of your turn, get a copy of the last Tavern spell you cast."""

    @staticmethod
    def end_of_turn(source, game):
        last_spell = source.controller.get_tag(GameTag.LAST_SPELL_CARD_ID, None)
        if last_spell:
            return AddToHand(source.controller, last_spell)
        return None


# ── On-Sell ──────────────────────────────────────────────────────────────────

class FreedealingGamblerScript:
    """This minion sells for 3 Gold."""

    @staticmethod
    def on_sell(source, game):
        return GainGold(source.controller, 3)


class PatientScoutScript:
    """When you sell this, Discover a Tier X minion. (Improves each turn!)"""

    @staticmethod
    def on_sell(source, game):
        from hsrl.core.actions import DiscoverMinion
        turns = source.get_tag(GameTag.TURNS_IN_HAND, 1)
        tier = min(6, turns)  # Tier scales with turns held, max 6
        return DiscoverMinion(source.controller, max_tier=tier)


class TortollanBlueShellScript:
    """If you lost your last combat, this minion sells for 5 Gold."""

    @staticmethod
    def on_sell(source, game):
        return GainGold(source.controller, 5)


# ── Spellcraft ───────────────────────────────────────────────────────────────

class DeepBlueCroonerScript:
    """Spellcraft: Give a minion +X/+X until next turn. Improve your future Deep Blues."""

    @staticmethod
    def spellcraft(source, game):
        return "BG26_502t"  # Deep Blue Crooner Spell token

    @staticmethod
    def on_play_spell(source, game, target=None):
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        source.set_tag(GameTag.IMPROVE_COUNTER, counter + 1)
        bonus = 1 + counter
        if target:
            return Buff(target, atk=bonus, health=bonus, temporary=True)
        return None


# ── Deathrattle ──────────────────────────────────────────────────────────────

class ShipwreckedRascalScript:
    """Battlecry and Deathrattle: Get a random Bounty."""

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import GetRandomBounty
        return GetRandomBounty(source.controller)

    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.actions import GetRandomBounty
        return GetRandomBounty(source.controller)


class LostCityLooterScript:
    """End of Turn: Get a random Bounty."""

    @staticmethod
    def end_of_turn(source, game):
        from hsrl.core.actions import GetRandomBounty
        return GetRandomBounty(source.controller)


class BigwigBanditScript:
    """Rally: Get a random Bounty."""

    @staticmethod
    def rally(source, game):
        from hsrl.core.actions import GetRandomBounty
        return GetRandomBounty(source.controller)


class MoonsteelJuggernautScript:
    """End of Turn: Get two 1/1 Magnetic Satellites and improve this.

    Formal spec:
      1. Increment IMPROVE_COUNTER on self
      2. Create 2 Satellite tokens with stats scaled by counter (1 + counter)
      3. Add each to controller's hand
    """

    @staticmethod
    def end_of_turn(source, game):
        from hsrl.core.actions import AddToHand
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
        source.set_tag(GameTag.IMPROVE_COUNTER, counter)
        actions = []
        for _ in range(2):
            satellite = game.create_minion("BG31_171t")
            if satellite is None:
                continue
            satellite.set_tag(GameTag.BASE_ATK, 1 + counter)
            satellite.set_tag(GameTag.BASE_HEALTH, 1 + counter)
            satellite.set_tag(GameTag.HEALTH, 1 + counter)
            actions.append(AddToHand(source.controller, satellite))
        return actions if actions else None


class GenerousGeomancerScript:
    """Deathrattle: You and your teammate each get a Blood Gem."""

    @staticmethod
    def deathrattle(source, game):
        return GetBloodGem(source.controller, count=1)


class FeistyFreshwaterScript:
    """Deathrattle: You and your teammate each gain two free Refreshes."""

    @staticmethod
    def deathrattle(source, game):
        from hsrl.core.actions import GainFreeRefresh
        return GainFreeRefresh(source.controller, 2)


# ── Avenge ───────────────────────────────────────────────────────────────────

class DrustfallenButcherScript:
    """Avenge: Get a Butchering."""

    @staticmethod
    def avenge(source, game):
        return AddToHand(source.controller, "BG28_604")  # Butchering spell


# ── Battlecry ────────────────────────────────────────────────────────────────

class RuthlessQueensguardScript:
    """Battlecry, Deathrattle, and Rally: Cast Queen's Command."""

    @staticmethod
    def _queens_command(source, game):
        board = [m for m in source.controller.board if not m.dead]
        if not board:
            return None
        types = set()
        for m in board:
            r = m.race
            if r not in (Race.INVALID, Race.ALL, Race.NONE):
                types.add(r)
        type_count = max(len(types), 1)
        target = random.choice(board)
        return Buff(target, atk=2 * type_count, health=2 * type_count)

    @staticmethod
    def battlecry(source, game):
        return RuthlessQueensguardScript._queens_command(source, game)

    @staticmethod
    def deathrattle(source, game):
        return RuthlessQueensguardScript._queens_command(source, game)

    @staticmethod
    def rally(source, game):
        return RuthlessQueensguardScript._queens_command(source, game)


# ── Rally ────────────────────────────────────────────────────────────────────

class SeafloorRecruiterScript:
    """Rally: Cast Chef's Choice on the minion to the right."""

    @staticmethod
    def rally(source, game):
        board = [m for m in source.controller.board if not m.dead]
        for i, m in enumerate(board):
            if m is source and i + 1 < len(board):
                right = board[i + 1]
                tier = source.controller.tavern_tier
                return Buff(right, atk=tier, health=tier)
        return None


class ShipJumperScript:
    """Rally: Summon a Sky Pirate to attack the target first."""

    @staticmethod
    def rally(source, game):
        from hsrl.core.actions import Summon, Attack
        token = game.create_minion("BGS_061t")
        if token is None:
            return None
        actions = [Summon(source.controller, token)]
        target = getattr(game, '_last_attack_target', None)
        if target and not target.dead:
            actions.append(Attack(token, target))
        return actions


# ── "Wherever this is" Trackers ──────────────────────────────────────────────

class AncestralAutomatonScript:
    """Has +3/+2 for each other Ancestral Automaton you've summoned this game."""

    @classmethod
    def atk(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.AUTOMATON_COUNT, 0)
        return 3 + 3 * count

    @classmethod
    def health(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.AUTOMATON_COUNT, 0)
        return 2 + 2 * count


class EternalKnightScript:
    """Has +1/+1 for each friendly Eternal Knight that died this game."""

    @staticmethod
    def deathrattle(source, game):
        count = source.controller.get_tag(GameTag.ETERNAL_KNIGHT_DEATHS, 0)
        source.controller.set_tag(GameTag.ETERNAL_KNIGHT_DEATHS, count + 1)
        return None

    @classmethod
    def atk(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.ETERNAL_KNIGHT_DEATHS, 0)
        return 4 + count

    @classmethod
    def health(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.ETERNAL_KNIGHT_DEATHS, 0)
        return 2 + count


class RotHideGnollScript:
    """Has +1 Attack for each friendly minion that died this combat."""

    @staticmethod
    def start_of_combat(source, game):
        source.set_tag(GameTag.COMBAT_DEATH_COUNT, 0)
        return None


class FallingSkyGolemScript:
    """Has +1/+1 for each Deathrattle triggered this game."""

    @classmethod
    def atk(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.DEATHRATTLE_TRIGGERED, 0)
        return 4 + count

    @classmethod
    def health(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.DEATHRATTLE_TRIGGERED, 0)
        return 2 + count


# ── Keyword / Passive Effects ────────────────────────────────────────────────

class ElementalOfSurpriseScript:
    """Divine Shield. This minion can triple with any Elemental."""

    # Just keyword tags — engine handles this from card data
    pass


class WrathWeaverScript:
    """
    Natural language: After you play a Demon, deal 1 damage to your hero
    and gain +2/+2.

    Formal spec:
      1. on_summon: register MINION_PLAYED listener with condition
         (played minion is a Demon, same controller, source alive on board)
      2. listener action: DealDamageToHero(controller, 1) + Buff(source, +2/+2)
    Test: play a Demon → Wrath Weaver takes 1 to hero and gets +2/+2.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.actions import DealDamageToHero, Buff

        class _Trigger(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead or source.zone != Zone.PLAY:
                    return
                game_ref.queue_action(DealDamageToHero(source.controller, 1))
                game_ref.queue_action(Buff(source, atk=2, health=2))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_Trigger(),
            condition=lambda m, p: (
                p == source.controller
                and m.race == Race.DEMON
            ),
        )
        game.register_listener(source, listener)
        return None


class ProphetOfTheBoarScript:
    """
    Natural language: Taunt. After you play a Quilboar, get a Blood Gem.

    Formal spec:
      1. on_summon: register MINION_PLAYED listener with condition
         (played minion is a Quilboar, same controller, source alive on board)
      2. listener action: GetBloodGem(controller)
    Test: play a Quilboar → add a Blood Gem to hand.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _Trigger(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead or source.zone != Zone.PLAY:
                    return
                game_ref.queue_action(GetBloodGem(source.controller))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_Trigger(),
            condition=lambda m, p: (
                p == source.controller
                and m.race == Race.QUILBOAR
            ),
        )
        game.register_listener(source, listener)
        return None


class MrglinBurglarScript:
    """
    Natural language: After you play a Murloc, give a friendly minion +2/+2
    and give a minion in your hand +2/+2.

    Formal spec:
      1. on_summon: register MINION_PLAYED listener with condition
         (played minion is a Murloc, same controller, source alive on board)
      2. listener action: Buff(random friendly, +2/+2) + Buff(random hand, +2/+2)
    Test: play a Murloc → one board and one hand minion get +2/+2.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _Trigger(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead or source.zone != Zone.PLAY:
                    return
                board = [m for m in source.controller.board if not m.dead]
                if board:
                    game_ref.queue_action(Buff(random.choice(board), atk=2, health=2))
                hand = [m for m in source.controller.hand if not m.dead]
                if hand:
                    game_ref.queue_action(Buff(random.choice(hand), atk=2, health=2))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_Trigger(),
            condition=lambda m, p: (
                p == source.controller
                and m.race == Race.MURLOC
            ),
        )
        game.register_listener(source, listener)
        return None


class ConsummateConquerorScript:
    """Whenever a minion is consumed, give minions in the Tavern +1/+1 this turn."""

    # DEFERRED: Needs FODDER_CONSUME event listener
    pass


class TwistedWrathguardScript:
    """After you sell a minion, add a Fodder to your next Refresh."""

    @staticmethod
    def on_sell(source, game):
        from hsrl.core.actions import AddFodderToRandomTavernMinion
        return AddFodderToRandomTavernMinion(source.controller)


class LurkingLeviathanScript:
    """Whenever you summon a Beast, give it +1 Attack and improve this."""

    # DEFERRED: Needs combat summon event listener
    pass


class RabidPantherScript:
    """
    Natural language: After you play a Beast, give your Beasts +1/+1 and
    deal 1 damage to your hero.

    Formal spec:
      1. on_summon: register MINION_PLAYED listener with condition
         (played minion is a Beast, same controller, source alive on board)
      2. listener action: Buff(all friendly Beasts, +1/+1) + DealDamageToHero(controller, 1)
    Test: play a Beast → all friendly Beasts get +1/+1, hero takes 1 damage.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _Trigger(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead or source.zone != Zone.PLAY:
                    return
                for m in source.controller.board:
                    if not m.dead and m.race in (Race.BEAST, Race.ALL):
                        game_ref.queue_action(Buff(m, atk=1, health=1))
                game_ref.queue_action(DealDamageToHero(source.controller, 1))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_Trigger(),
            condition=lambda m, p: (
                p == source.controller
                and m.race == Race.BEAST
            ),
        )
        game.register_listener(source, listener)
        return None


class BalindaStonehearthScript:
    """Your spells that target friendly minions cast twice."""

    # DEFERRED: Needs spell targeting system
    pass


class ScarletSurvivorScript:
    """Once this reaches X Attack, gain Divine Shield."""

    # DEFERRED: Needs threshold trigger
    pass


class TitusRivendareScript:
    """Your Deathrattles trigger an extra time."""

    @staticmethod
    def on_summon(source, game):
        source.controller.set_tag(GameTag.DEATHRATTLE_DOUBLED, True)


class BazaarDealerScript:
    """One Tavern spell each turn costs Health instead of Gold."""

    # DEFERRED: Needs health-as-cost system
    pass


class LeechingFelhoundScript:
    """This costs Health instead of Gold to buy."""

    # DEFERRED: Needs health-as-cost system
    pass


class TichondriusScript:
    """After your hero takes damage, give your Demons +1/+1."""

    # DEFERRED: Needs DAMAGE_TAKEN event
    pass


class DeadlySporeScript:
    """Venomous."""

    # Keyword only — handled by tags
    pass


class MaelstromEmergentScript:
    """Your Tavern spells cast an extra time in combat."""

    # DEFERRED: Needs combat spell system
    pass


class BladeCollectorScript:
    """Also damages the minions next to whomever this attacks."""

    # DEFERRED: Needs cleave-like attack modifier
    pass


class TechnicalElementScript:
    """Magnetic. Can Magnetize to both Mechs and Elementals."""

    # Keyword only — handled by tags
    pass


class PufferquilScript:
    """Whenever a spell is cast on this, gain Venomous until next turn."""

    # DEFERRED: Needs spell-target trigger
    pass


class AbyssalBruiserScript:
    """Divine Shield. Has +1/+1 for each Tavern spell you've cast."""

    @classmethod
    def atk(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.TAVERN_SPELLS_CAST_THIS_GAME, 0)
        return 1 + count

    @classmethod
    def health(cls, source):
        if source.controller is None:
            return None
        count = source.controller.get_tag(GameTag.TAVERN_SPELLS_CAST_THIS_GAME, 0)
        return 1 + count


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: Existing-engine scripts — TAVERN_SPELL_CAST listeners + passives
# ═══════════════════════════════════════════════════════════════════════════════


# ── Helper: custom Action for TAVERN_SPELL_CAST → buff board ────────────

class _BuffAllFriendlyAction(Action):
    """Buff all living friendly minions that match an optional filter."""
    def __init__(self, controller, atk=0, health=0, race_filter=None,
                 extra_filter=None):
        super().__init__()
        self.controller = controller
        self.atk = atk
        self.health = health
        self.race_filter = race_filter
        self.extra_filter = extra_filter  # callable(BaseEntity) -> bool

    def do(self, source_ent, game_ref, target=None):
        actions = []
        for m in self.controller.get_board_minions():
            if m.dead:
                continue
            if self.race_filter is not None and m.race != self.race_filter:
                continue
            if self.extra_filter is not None and not self.extra_filter(m):
                continue
            actions.append(Buff(m, atk=self.atk, health=self.health))
        for a in actions:
            game_ref.queue_action(a)


class _BuffPerTypeAction(Action):
    """Buff one friendly minion of each unique tribe by +atk/+health."""
    def __init__(self, controller, atk=0, health=0):
        super().__init__()
        self.controller = controller
        self.atk = atk
        self.health = health

    def do(self, source_ent, game_ref, target=None):
        seen = set()
        actions = []
        for m in self.controller.get_board_minions():
            if m.dead:
                continue
            r = m.race
            if r in (Race.NONE, Race.INVALID):
                continue
            if r not in seen:
                seen.add(r)
                actions.append(Buff(m, atk=self.atk, health=self.health))
        for a in actions:
            game_ref.queue_action(a)


# ── BG23_013: Tidemistress Athissa ─────────────────────────────────────
class TidemistressAthissaScript:
    """Whenever you cast a spell, give all your Naga +1/+1 permanently.

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: buff all friendly Naga by +1/+1
      - Condition: only when spell is cast by our controller

    Test: summon Athissa, cast 2 tavern spells, verify Naga on board get +2/+2.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffAllFriendlyAction(
                source.controller, atk=1, health=1, race_filter=Race.NAGA,
            ),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG27_005: Timecap'n Hooktail ───────────────────────────────────────
class TimecapnHooktailScript:
    """Whenever you cast a Tavern spell, give your minions +1 Attack.

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: buff all friendly minions +1 Attack
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffAllFriendlyAction(source.controller, atk=1, health=0),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG28_551: Nalaa the Redeemer ───────────────────────────────────────
class NalaaTheRedeemerScript:
    """Whenever you cast a Tavern spell, give a friendly minion of each
    type +1/+1.

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: find one minion per unique tribe, buff each +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffPerTypeAction(source.controller, atk=1, health=1),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG28_707: Living Azerite ───────────────────────────────────────────
class LivingAzeriteScript:
    """Whenever you cast a Tavern spell, give Elementals in the Tavern
    +1/+1 this game.

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: BuffTavern(controller, +1/+1, race_filter=ELEMENTAL)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffTavernElementals(Action):
            def do(self, source_ent, game_ref, target=None):
                game_ref.queue_action(
                    BuffTavern(source.controller, atk=1, health=1,
                               race_filter=Race.ELEMENTAL),
                )

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffTavernElementals(),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG28_741: Charging Czarina ─────────────────────────────────────────
class ChargingCzarinaScript:
    """Divine Shield. Whenever you cast a Tavern spell, give your minions
    with Divine Shield +1 Attack.

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: buff all friendly DS minions +1 Attack
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        def _has_ds(m):
            return m.get_tag(GameTag.DIVINE_SHIELD, False)

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_BuffAllFriendlyAction(
                source.controller, atk=1, health=0, extra_filter=_has_ds,
            ),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG31_871: Batty Terrorguard ────────────────────────────────────────
class BattyTerrorguardScript:
    """After you cast a Tavern spell, another friendly Demon consumes a
    minion in the Tavern to gain its stats.

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: pick random friendly Demon (not self if on board),
        ConsumeTavernMinion on it
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _DemonConsumeTavern(Action):
            def do(self, source_ent, game_ref, target=None):
                player = source.controller
                demons = [m for m in player.get_board_minions()
                          if not m.dead and m.race == Race.DEMON and m is not source]
                if not demons:
                    return
                target_demon = random.choice(demons)
                game_ref.queue_action(
                    ConsumeTavernMinion(player, target_demon, mode="random"),
                )

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_DemonConsumeTavern(),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG34_692: Forsaken Weaver ──────────────────────────────────────────
class ForsakenWeaverScript:
    """After you cast a Tavern spell, your Undead have +1 Attack this game
    (wherever they are).

    Formal spec:
      - on_summon: register TAVERN_SPELL_CAST listener
      - listener action: ApplyGlobalAura(controller, atk=1, race_filter=UNDEAD)
      - Each cast stacks another aura layer
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _UndeadAura(Action):
            def do(self, source_ent, game_ref, target=None):
                game_ref.queue_action(
                    ApplyGlobalAura(source.controller, atk=1, health=0,
                                    race_filter=Race.UNDEAD),
                )

        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=_UndeadAura(),
            condition=lambda s, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG32_341: Humon'gozz ───────────────────────────────────────────────
class HumongozzScript:
    """Divine Shield. Your Tavern spells give an extra +1/+2.

    Formal spec:
      - on_summon: ImproveTavernSpellBuff(controller, atk_bonus=1, health_bonus=2)
    """

    @staticmethod
    def on_summon(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=2)


# ── BG35_341: Enchanted Sentinel ───────────────────────────────────────
class EnchantedSentinelScript:
    """Magnetic. Your Tavern spells give an extra +1/+2.

    Formal spec:
      - on_summon: ImproveTavernSpellBuff(controller, atk_bonus=1, health_bonus=2)
    """

    @staticmethod
    def on_summon(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=2)


# ── BG31_812: Ichoron the Protector ────────────────────────────────────
class IchoronTheProtectorScript:
    """Divine Shield. Whenever you play an Elemental, give it Divine Shield
    until next turn.

    Formal spec:
      - on_summon: register ELEMENTAL_PLAYED listener
      - listener action: GainKeyword(target, DIVINE_SHIELD)
        (target = the played elemental, passed by broadcast convention)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _GiveDSToPlayedElemental(Action):
            def do(self, source_ent, game_ref, target=None):
                if target is not None and not target.dead:
                    game_ref.queue_action(GainKeyword(target, GameTag.DIVINE_SHIELD))

        listener = EventListener(
            event_name="ELEMENTAL_PLAYED",
            action=_GiveDSToPlayedElemental(),
            condition=lambda m, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BG35_801: Gluttonous Trogg ─────────────────────────────────────────
class GluttonousTroggScript:
    """Once you buy 4 cards, gain +1/+2.

    Formal spec:
      - on_summon: register MINION_BOUGHT listener
      - Count bought cards. On 4th → Buff(self, +1/+2)
      - Once triggered, unregister (once=True via self-destruct flag)
      - Counter stored on the minion entity
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _CountBuyAndBuff(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                count = source.get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                source.set_tag(GameTag.IMPROVE_COUNTER, count)
                if count >= 4:
                    # Remove this listener (mark done via a flag)
                    source.set_tag(GameTag.AVENGE_TARGET, -1)
                    game_ref.queue_action(Buff(source, atk=1, health=2))

        listener = EventListener(
            event_name="MINION_BOUGHT",
            action=_CountBuyAndBuff(),
            condition=lambda m, p: (p == source.controller
                                     and source.get_tag(GameTag.AVENGE_TARGET, 0) != -1),
        )
        game.register_listener(source, listener)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: New-subsystem scripts — on-damage, on-attack, on-gem, on-play,
#   gold-spend threshold, Choose One, on-magnetize, on-add-to-hand
# ═══════════════════════════════════════════════════════════════════════════════


# ── Helper actions ──────────────────────────────────────────────────────

class _BuffHandMinion(Action):
    """Buff a random minion in the controller's hand."""
    def __init__(self, controller, atk=0, health=0):
        super().__init__()
        self.controller = controller
        self.atk = atk
        self.health = health

    def do(self, source_ent, game_ref, target=None):
        hand_minions = [m for m in self.controller.hand
                        if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
        if hand_minions:
            target_m = random.choice(hand_minions)
            game_ref.queue_action(Buff(target_m, atk=self.atk, health=self.health))


class _GoldThresholdAction(Action):
    """Accumulate GOLD_SPENT amounts and fire an effect on reaching threshold."""
    def __init__(self, controller, threshold: int, effect: Action):
        super().__init__()
        self.controller = controller
        self.threshold = threshold
        self.effect = effect

    def do(self, source_ent, game_ref, target=None):
        if source_ent.dead:
            return
        # target is the amount_spent (first arg of GOLD_SPENT broadcast)
        amount = target if isinstance(target, (int, float)) else 0
        current = source_ent.get_tag(GameTag.AVENGE_COUNTER, 0) + amount
        if current >= self.threshold:
            # Fire effect once per threshold reached
            times = current // self.threshold
            for _ in range(times):
                game_ref.queue_action(self.effect)
            current = current % self.threshold
        source_ent.set_tag(GameTag.AVENGE_COUNTER, current)


# ── MINION_DAMAGED scripts ──────────────────────────────────────────────

class VeryHungryWinterfinnerScript:
    """Taunt. Whenever this takes damage, give a minion in your hand +2/+1.

    Formal spec:
      - on_summon: register MINION_DAMAGED listener
      - condition: target == source (damage is on THIS minion)
      - action: BuffHandMinion(controller, atk=2, health=1)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        listener = EventListener(
            event_name="MINION_DAMAGED",
            action=_BuffHandMinion(source.controller, atk=2, health=1),
            condition=lambda t, amt, src: t == source,
        )
        game.register_listener(source, listener)
        return None


class IridescentSkyblazerScript:
    """Whenever a friendly Beast takes damage, give a friendly Beast other
    than it +1/+1 permanently.

    Formal spec:
      - on_summon: register MINION_DAMAGED listener
      - condition: damaged minion is friendly Beast, belongs to our controller
      - action: buff a DIFFERENT random friendly Beast +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffOtherBeast(Action):
            def do(self, source_ent, game_ref, target=None):
                # target = damaged minion (event arg 0)
                damaged = target
                player = source.controller
                candidates = [m for m in player.get_board_minions()
                              if not m.dead and m.race == Race.BEAST and m is not damaged]
                if candidates:
                    game_ref.queue_action(Buff(random.choice(candidates), atk=1, health=1))

        listener = EventListener(
            event_name="MINION_DAMAGED",
            action=_BuffOtherBeast(),
            condition=lambda t, amt, src: (
                t.controller == source.controller
                and t.race == Race.BEAST
            ),
        )
        game.register_listener(source, listener)
        return None


class TrigoreTheLasherScript:
    """Whenever another friendly Beast takes damage, gain +1 Health permanently.

    Formal spec:
      - on_summon: register MINION_DAMAGED listener
      - condition: damaged is friendly Beast, not self
      - action: Buff(self, health=1)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffSelfHealth(Action):
            def do(self, source_ent, game_ref, target=None):
                if not source.dead:
                    game_ref.queue_action(Buff(source, atk=0, health=1))

        listener = EventListener(
            event_name="MINION_DAMAGED",
            action=_BuffSelfHealth(),
            condition=lambda t, amt, src: (
                t is not source
                and t.controller == source.controller
                and t.race == Race.BEAST
            ),
        )
        game.register_listener(source, listener)
        return None


class HardyOrcaScript:
    """Taunt. Whenever this takes damage, give your other minions +1/+1.

    Formal spec:
      - on_summon: register MINION_DAMAGED listener
      - condition: damaged minion == source (self)
      - action: buff all OTHER friendly minions +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffOtherMinions(Action):
            def do(self, source_ent, game_ref, target=None):
                player = source.controller
                for m in player.get_board_minions():
                    if not m.dead and m is not source:
                        game_ref.queue_action(Buff(m, atk=1, health=1))

        listener = EventListener(
            event_name="MINION_DAMAGED",
            action=_BuffOtherMinions(),
            condition=lambda t, amt, src: t == source,
        )
        game.register_listener(source, listener)
        return None


class WyvernOutriderScript:
    """Whenever this takes damage, gain a free Refresh (X times per turn).

    Formal spec:
      - on_summon: register MINION_DAMAGED listener
      - condition: damaged == self, and per-turn limit not reached (track via counter)
      - action: GainFreeRefresh(1) and increment counter
      - Per-turn counter resets via RECRUIT_BEGIN listener
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.events import RECRUIT_BEGIN

        class _GainFreeRefreshOnDamage(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                used = source.get_tag(GameTag.FREE_REFRESH_REMAINING, 0)
                if used >= 2:  # 2 times per turn
                    return
                source.set_tag(GameTag.FREE_REFRESH_REMAINING, used + 1)
                game_ref.queue_action(GainFreeRefresh(source.controller, 1))

        # Reset counter each recruit begin
        class _ResetPerTurn(Action):
            def do(self, source_ent, game_ref, target=None):
                if not source.dead:
                    source.set_tag(GameTag.FREE_REFRESH_REMAINING, 0)

        game.register_listener(source, EventListener(
            event_name="MINION_DAMAGED",
            action=_GainFreeRefreshOnDamage(),
            condition=lambda t, amt, src: t == source,
        ))
        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_ResetPerTurn(),
            condition=lambda p: p == source.controller,
        ))
        return None


# ── MINION_ATTACKED scripts ─────────────────────────────────────────────

class RoaringRecruiterScript:
    """Whenever another friendly Dragon attacks, give it +1/+1.

    Formal spec:
      - on_summon: register MINION_ATTACKED listener
      - condition: attacker is friendly Dragon, not self
      - action: Buff(attacker, atk=1, health=1) — target=attacker from event
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffAttackingDragon(Action):
            def do(self, source_ent, game_ref, target=None):
                # target = attacker (first event arg)
                if target and not target.dead and target is not source:
                    game_ref.queue_action(Buff(target, atk=1, health=1))

        listener = EventListener(
            event_name="MINION_ATTACKED",
            action=_BuffAttackingDragon(),
            condition=lambda atkr, dfdr: (
                atkr is not source
                and atkr.controller == source.controller
                and atkr.race == Race.DRAGON
            ),
        )
        game.register_listener(source, listener)
        return None


class RingBearerScript:
    """Whenever a friendly minion attacks, cast Shiny Ring.

    Formal spec:
      - on_summon: register MINION_ATTACKED listener
      - condition: attacker is friendly minion
      - action: BuffTavern(player, atk=1, health=1)
        (Shiny Ring = "Give minions in the Tavern +1/+1 this game")
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _CastShinyRing(Action):
            def do(self, source_ent, game_ref, target=None):
                game_ref.queue_action(
                    BuffTavern(source.controller, atk=1, health=1),
                )

        listener = EventListener(
            event_name="MINION_ATTACKED",
            action=_CastShinyRing(),
            condition=lambda atkr, dfdr: atkr.controller == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── BLOOD_GEM_PLAYED scripts ────────────────────────────────────────────

class GeomagusRoogugScript:
    """Divine Shield. Whenever a Blood Gem is played on this, play a Blood
    Gem on a different friendly minion.

    Formal spec:
      - on_summon: register BLOOD_GEM_PLAYED listener
      - condition: target (gem recipient) == source
      - action: PlayBloodGems on random different friendly minion
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _PlayGemOnAnother(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                candidates = [m for m in source.controller.get_board_minions()
                              if not m.dead and m is not source]
                if candidates:
                    game_ref.queue_action(
                        PlayBloodGems(random.choice(candidates), count=1),
                    )

        listener = EventListener(
            event_name="BLOOD_GEM_PLAYED",
            action=_PlayGemOnAnother(),
            condition=lambda t, p, count: t == source,
        )
        game.register_listener(source, listener)
        return None


class HiredRitualistScript:
    """Once per turn, after a Blood Gem is played on this, gain 1 Gold.

    Formal spec:
      - on_summon: register BLOOD_GEM_PLAYED listener
      - condition: target == source AND per-turn flag not set
      - action: GainGold(1) + set per-turn flag
      - Per-turn flag reset via RECRUIT_BEGIN listener
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.events import RECRUIT_BEGIN

        class _GainGoldOncePerTurn(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                already = source.get_tag(GameTag.FODDER_REFRESH_REMAINING, 0)
                if already:
                    return
                source.set_tag(GameTag.FODDER_REFRESH_REMAINING, 1)
                game_ref.queue_action(GainGold(source.controller, 1))

        class _ResetGoldFlag(Action):
            def do(self, source_ent, game_ref, target=None):
                if not source.dead:
                    source.set_tag(GameTag.FODDER_REFRESH_REMAINING, 0)

        game.register_listener(source, EventListener(
            event_name="BLOOD_GEM_PLAYED",
            action=_GainGoldOncePerTurn(),
            condition=lambda t, p, count: t == source,
        ))
        game.register_listener(source, EventListener(
            event_name=RECRUIT_BEGIN,
            action=_ResetGoldFlag(),
            condition=lambda p: p == source.controller,
        ))
        return None


# ── MINION_PLAYED scripts ───────────────────────────────────────────────

class OneAmalgamTourGroupScript:
    """Whenever you play a card, give friendly minions of its Tier or lower
    +1/+1.

    Formal spec:
      - on_summon: register MINION_PLAYED listener
      - condition: played by my controller
      - action: buff all friendly minions with tier ≤ played card's tier
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffByTier(Action):
            def do(self, source_ent, game_ref, target=None):
                # target = played minion (event arg 0)
                if target is None:
                    return
                played_tier = target.tech_level
                for m in source.controller.get_board_minions():
                    if not m.dead and m.tech_level <= played_tier:
                        game_ref.queue_action(Buff(m, atk=1, health=1))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_BuffByTier(),
            condition=lambda m, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


class PrimitivePainterScript:
    """After you play a card from Tier 3 or below, give your Murlocs +1/+1.

    Formal spec:
      - on_summon: register MINION_PLAYED listener
      - condition: played card tech_level ≤ 3, mine
      - action: buff all friendly Murlocs +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffMurlocs(Action):
            def do(self, source_ent, game_ref, target=None):
                for m in source.controller.get_board_minions():
                    if not m.dead and m.race == Race.MURLOC:
                        game_ref.queue_action(Buff(m, atk=1, health=1))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_BuffMurlocs(),
            condition=lambda m, p: (
                p == source.controller and m.tech_level <= 3
            ),
        )
        game.register_listener(source, listener)
        return None


class GroundbreakerScript:
    """After you play a Naga, gain +1/+1. Improved by every 4 spells you've
    cast this game.

    Formal spec:
      - on_summon: register MINION_PLAYED listener
      - condition: played is Naga, my controller
      - action: Buff(self, atk=1*(1+spells//4), health=1*(1+spells//4))
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffBySpells(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                spells = source.controller.get_tag(
                    GameTag.TAVERN_SPELLS_CAST_THIS_GAME, 0)
                mult = 1 + spells // 4
                game_ref.queue_action(Buff(source, atk=1 * mult, health=1 * mult))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_BuffBySpells(),
            condition=lambda m, p: (
                p == source.controller and m.race == Race.NAGA
            ),
        )
        game.register_listener(source, listener)
        return None


# ── Choose One scripts ──────────────────────────────────────────────────

class SprightlyScarabScript:
    """Choose One - Give a Beast +1/+1 and Reborn; or +2 Attack and Windfury.

    Formal spec:
      - Battlecry: ChooseOne with 2 options targeting a friendly Beast
      - During recruit: player chooses the target Beast, then picks option
      - During combat: both target and option are random
      - Option A: Buff(+1/+1) + GainKeyword(REBORN)
      - Option B: Buff(+2atk) + GainKeyword(WINDFURY)
    """

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            board = source.controller.get_board_minions()
            return [m for m in board if not m.dead and m.race == Race.BEAST]

        if not filter_fn():
            return None

        def action_factory(target):
            return ChooseOne([
                ("Give +1/+1 and Reborn", [
                    Buff(target, atk=1, health=1),
                    GainKeyword(target, GameTag.REBORN),
                ]),
                ("Give +2 Attack and Windfury", [
                    Buff(target, atk=2, health=0),
                    GainKeyword(target, GameTag.WINDFURY),
                ]),
            ])

        return TargetedAction(filter_fn, action_factory,
                              label="Sprightly Scarab — choose target Beast")


class FearlessFoodieScript:
    """Choose One - Your Blood Gems give +1/+1 this game; or Get 2 Blood Gems.

    Formal spec:
      - Battlecry: ChooseOne with 2 options
      - Option A: ImproveBloodGem(player, atk=1, health=1)
      - Option B: GetBloodGem(player, count=2) — adds Blood Gems to hand
    """

    @staticmethod
    def battlecry(source, game):
        return ChooseOne([
            ("Your Blood Gems give +1/+1 this game",
             ImproveBloodGem(source.controller, atk_bonus=1, health_bonus=1)),
            ("Get 2 Blood Gems",
             GetBloodGem(source.controller, count=2)),
        ])


class IntrepidBotanistScript:
    """Choose One - Your Tavern spells give an extra +1 Attack this game;
    or +1 Health.

    Formal spec:
      - Battlecry: ChooseOne with 2 options
      - Option A: ImproveTavernSpellBuff(atk_bonus=1)
      - Option B: ImproveTavernSpellBuff(health_bonus=1)
    """

    @staticmethod
    def battlecry(source, game):
        return ChooseOne([
            ("Tavern spells give +1 Attack",
             ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=0)),
            ("Tavern spells give +1 Health",
             ImproveTavernSpellBuff(source.controller, atk_bonus=0, health_bonus=1)),
        ])


# ── GOLD_SPENT threshold scripts ────────────────────────────────────────

class GunpowderCourierScript:
    """Whenever you spend 6 Gold, give your Pirates +2 Attack.

    Formal spec:
      - on_summon: register GOLD_SPENT listener with _GoldThresholdAction(6)
      - effect: buff all friendly Pirates +2 Attack
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffPirates(Action):
            def do(self, source_ent, game_ref, target=None):
                for m in source.controller.get_board_minions():
                    if not m.dead and m.race == Race.PIRATE:
                        game_ref.queue_action(Buff(m, atk=2, health=0))

        listener = EventListener(
            event_name="GOLD_SPENT",
            action=_GoldThresholdAction(
                source.controller, threshold=6, effect=_BuffPirates(),
            ),
            condition=lambda p, amt: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


class DualWieldCorsairScript:
    """Whenever you spend 5 Gold, give two friendly Pirates +2/+3.

    Formal spec:
      - on_summon: register GOLD_SPENT listener with threshold=5
      - effect: pick up to 2 random Pirates, buff each +2/+3
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffTwoPirates(Action):
            def do(self, source_ent, game_ref, target=None):
                pirates = [m for m in source.controller.get_board_minions()
                           if not m.dead and m.race == Race.PIRATE]
                chosen = random.sample(pirates, min(2, len(pirates)))
                for p in chosen:
                    game_ref.queue_action(Buff(p, atk=2, health=3))

        listener = EventListener(
            event_name="GOLD_SPENT",
            action=_GoldThresholdAction(
                source.controller, threshold=5, effect=_BuffTwoPirates(),
            ),
            condition=lambda p, amt: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


class DarkgazeElderScript:
    """Whenever you spend 2 Gold, play two Blood Gems on all your Quilboar.

    Formal spec:
      - on_summon: register GOLD_SPENT listener with threshold=2
      - effect: PlayBloodGems(count=1) on each friendly Quilboar (play "two" —
        but card text says "plays two Blood Gem on all your Quilboar" each
        time threshold is reached; plays 1 gem per Quilboar per trigger)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BloodGemAllQuilboar(Action):
            def do(self, source_ent, game_ref, target=None):
                for m in source.controller.get_board_minions():
                    if not m.dead and m.race == Race.QUILBOAR:
                        game_ref.queue_action(PlayBloodGems(m, count=2))

        listener = EventListener(
            event_name="GOLD_SPENT",
            action=_GoldThresholdAction(
                source.controller, threshold=2, effect=_BloodGemAllQuilboar(),
            ),
            condition=lambda p, amt: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── ADD_TO_HAND scripts ──────────────────────────────────────────────────

class PeggySturdyboneScript:
    """Whenever a card is added to your hand, give another friendly Pirate
    +1/+1.

    Formal spec:
      - on_summon: register ADD_TO_HAND listener
      - condition: player == my controller
      - action: buff random friendly Pirate (not self if on board) +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffPirate(Action):
            def do(self, source_ent, game_ref, target=None):
                pirates = [m for m in source.controller.get_board_minions()
                           if not m.dead and m.race == Race.PIRATE]
                if pirates:
                    game_ref.queue_action(
                        Buff(random.choice(pirates), atk=1, health=1),
                    )

        listener = EventListener(
            event_name="ADD_TO_HAND",
            action=_BuffPirate(),
            condition=lambda p, entity: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── MAGNETIZED scripts ──────────────────────────────────────────────────

class JunkJousterScript:
    """After you Magnetize a minion, give your minions +1/+1.

    Formal spec:
      - on_summon: register MAGNETIZED listener
      - condition: player == my controller
      - action: buff all friendly minions +1/+1
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        class _BuffAll(Action):
            def do(self, source_ent, game_ref, target=None):
                for m in source.controller.get_board_minions():
                    if not m.dead:
                        game_ref.queue_action(Buff(m, atk=1, health=1))

        listener = EventListener(
            event_name="MAGNETIZED",
            action=_BuffAll(),
            condition=lambda host, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: In-hand effects + post-combat persistence + death-filter scripts
# ═══════════════════════════════════════════════════════════════════════════════


# ── In-hand: Bream Counter ─────────────────────────────────────────────

class BreamCounterScript:
    """While this is in your hand, after you play a Murloc, gain +1/+1.

    Formal spec:
      - on_enter_hand: register MINION_PLAYED listener with condition
        that entity is still in hand (Zone.HAND)
      - listener action: Buff(self, atk=1, health=1)
    """

    @staticmethod
    def on_enter_hand(source, game):
        from hsrl.core.events import EventListener

        class _BuffInHand(Action):
            def do(self, source_ent, game_ref, target=None):
                if not source.dead and source.zone == Zone.HAND:
                    game_ref.queue_action(Buff(source, atk=1, health=1))

        listener = EventListener(
            event_name="MINION_PLAYED",
            action=_BuffInHand(),
            condition=lambda m, p: (
                p == source.controller
                and m.race == Race.MURLOC
                and source.zone == Zone.HAND
            ),
        )
        game.register_listener(source, listener)
        return None


# ── In-hand: Old Soul ───────────────────────────────────────────────────

class OldSoulScript:
    """After 3 friendly minions die while this is in your hand, make this
    Golden.

    Formal spec:
      - on_enter_hand: register DEATH listener
      - listener action: increment counter. On reaching 3 → set GOLDEN + double
        base stats
    """

    @staticmethod
    def on_enter_hand(source, game):
        from hsrl.core.events import EventListener

        class _CountDeaths(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead or source.zone != Zone.HAND:
                    return
                count = source.get_tag(GameTag.IMPROVE_COUNTER, 0) + 1
                source.set_tag(GameTag.IMPROVE_COUNTER, count)
                if count >= 3 and not source.is_golden:
                    source.set_tag(GameTag.GOLDEN, True)
                    source.set_tag(GameTag.BASE_ATK,
                                   source.get_tag(GameTag.BASE_ATK, 0) * 2)
                    source.set_tag(GameTag.BASE_HEALTH,
                                   source.get_tag(GameTag.BASE_HEALTH, 0) * 2)

        listener = EventListener(
            event_name="DEATH",
            action=_CountDeaths(),
            condition=lambda m, killer=None: (
                m.controller == source.controller
                and source.zone == Zone.HAND
            ),
        )
        game.register_listener(source, listener)
        return None


# ── In-hand: Egg of the Endtimes ────────────────────────────────────────

class EggOfTheEndtimesScript:
    """After this is in your hand for 4 turns, choose a Tier 6 Dragon to
    hatch into.

    Formal spec:
      - on_enter_hand: register TURN_BEGIN listener
      - Increment counter each turn. At turn 4 → transform into a Tier 6 Dragon
        (random Tier 6 Dragon from the pool)
    """

    @staticmethod
    def on_enter_hand(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.events import TURN_BEGIN

        class _CountTurns(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead or source.zone != Zone.HAND:
                    return
                count = source.get_tag(GameTag.AVENGE_COUNTER, 0) + 1
                source.set_tag(GameTag.AVENGE_COUNTER, count)
                if count >= 4:
                    # Find Tier 6 Dragons in the pool
                    candidates = [
                        cid for cid, data in game_ref.card_db._cards.items()
                        if (data.cardtype == CardType.MINION
                            and data.tech_level == 6
                            and data.race == Race.DRAGON
                            and not cid.startswith('EXAMPLE_')
                            and not cid.startswith('BGDUO'))
                    ]
                    if candidates:
                        chosen = random.choice(candidates)
                        game_ref.queue_action(Transform(source, chosen))

        listener = EventListener(
            event_name=TURN_BEGIN,
            action=_CountTurns(),
            condition=lambda p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


# ── Post-combat persistence: Tarecgosa ──────────────────────────────────

class TarecgosaScript:
    """This permanently keeps Bonus Keywords and stats gained in combat.

    Formal spec:
      - on_summon: register PRE_COMBAT_CLEANUP listener
      - At combat end (before cleanup): compute excess stats over base:
        excess_atk = current_atk - (base_atk + permanent_buffs)
        This is tricky since we don't easily separate buffs.
        Snapshots current atk/health at combat end and re-apply
        the delta after cleanup as a permanent buff.
      - Actually simpler approach: at PRE_COMBAT_CLEANUP, read current health,
        after cleanup read health, and apply the difference as permanent buff.

    Simplification: At PRE_COMBAT_CLEANUP, snapshot current atk/health to
    tags. At END_OF_COMBAT (after cleanup), compute the lost stats and
    re-apply permanently.

    But END_OF_COMBAT already fired before PRE_COMBAT_CLEANUP in the current
    flow. Actually no — looking at game.py: END_OF_COMBAT and COMBAT_END
    fire first, then PRE_COMBAT_CLEANUP, then cleanup.

    Revised approach: at PRE_COMBAT_CLEANUP, directly save excess stats
    and immediately queue permanent buffs. After cleanup, these permanent
    buffs remain.

    Wait, the problem is that temporary buffs are applied as BuffEnchantment
    with temporary=True. Permanent buffs are applied with temporary=False.
    If I apply a permanent Buff at PRE_COMBAT_CLEANUP time equal to the
    excess, then after cleanup the temps are removed but permanents stay.

    But how do I compute the "excess"? The current stats include the
    permanent buffs from the recruit phase + temporary buffs from combat.
    I want to turn the temporary portion into permanent.

    Simplest correct approach:
      excess_atk = source.atk - source.get_tag(GameTag.BASE_ATK, 0)
      excess_health = source.health - source.get_tag(GameTag.BASE_HEALTH, 0)
    Apply a PERMANENT Buff for (excess_atk, excess_health).
    After temp cleanup, the minion will still have these.
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.events import PRE_COMBAT_CLEANUP

        class _SaveCombatStats(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                base_atk = source.get_tag(GameTag.BASE_ATK, 0)
                base_health = source.get_tag(GameTag.BASE_HEALTH, 0)
                excess_atk = source.atk - base_atk
                excess_health = source.health - base_health
                if excess_atk > 0 or excess_health > 0:
                    game_ref.queue_action(
                        Buff(source, atk=excess_atk, health=excess_health,
                             temporary=False),
                    )

        listener = EventListener(
            event_name=PRE_COMBAT_CLEANUP,
            action=_SaveCombatStats(),
        )
        game.register_listener(source, listener)
        return None


# ── Post-combat persistence: Persistent Poet ───────────────────────────

class PersistentPoetScript:
    """Divine Shield. Adjacent Dragons permanently keep Bonus Keywords and
    stats gained in combat.

    Formal spec:
      - on_summon: register PRE_COMBAT_CLEANUP listener
      - For left and right adjacent Dragons, save excess stats as permanent
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener
        from hsrl.core.events import PRE_COMBAT_CLEANUP

        class _SaveAdjacentStats(Action):
            def do(self, source_ent, game_ref, target=None):
                if source.dead:
                    return
                board = source.controller.board
                pos = source.zone_position
                for adj_pos in (pos - 1, pos + 1):
                    if 0 <= adj_pos < len(board):
                        adj = board[adj_pos]
                        if (adj and not adj.dead
                                and adj.race == Race.DRAGON
                                and adj is not source):
                            base_atk = adj.get_tag(GameTag.BASE_ATK, 0)
                            base_health = adj.get_tag(GameTag.BASE_HEALTH, 0)
                            excess_atk = adj.atk - base_atk
                            excess_health = adj.health - base_health
                            if excess_atk > 0 or excess_health > 0:
                                game_ref.queue_action(
                                    Buff(adj, atk=excess_atk,
                                         health=excess_health,
                                         temporary=False),
                                )

        listener = EventListener(
            event_name=PRE_COMBAT_CLEANUP,
            action=_SaveAdjacentStats(),
        )
        game.register_listener(source, listener)
        return None


# ── Death filter: Bristlemane Scrapsmith ─────────────────────────────────

class BristlemaneScrapsmithScript:
    """After a friendly minion with Taunt dies, get a Blood Gem.

    Formal spec:
      - on_summon: register DEATH listener
      - condition: dead minion has taunt AND belongs to my controller
      - action: GetBloodGem(controller)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        listener = EventListener(
            event_name="DEATH",
            action=GetBloodGem(source.controller),
            condition=lambda m, killer=None: (
                m.controller == source.controller
                and m.has_tag(GameTag.TAUNT)
            ),
        )
        game.register_listener(source, listener)
        return None


# ── Death filter: Vinespeaker ───────────────────────────────────────────

class VinespeakerScript:
    """After a friendly Deathrattle minion dies, your Blood Gems give an
    extra +1 Attack this game.

    Formal spec:
      - on_summon: register DEATH listener
      - condition: dead minion has DEATHRATTLE and is friendly
      - action: ImproveBloodGem(atk_bonus=1)
    """

    @staticmethod
    def on_summon(source, game):
        from hsrl.core.events import EventListener

        listener = EventListener(
            event_name="DEATH",
            action=ImproveBloodGem(source.controller, atk_bonus=1, health_bonus=0),
            condition=lambda m, killer=None: (
                m.controller == source.controller
                and m.has_tag(GameTag.DEATHRATTLE)
            ),
        )
        game.register_listener(source, listener)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPT_REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_REGISTRY = {
    # Deathrattle — summon tokens
    "BG19_010": SewerRatScript,
    "BG25_009": EternalSummonerScript,
    "BG25_010": HandlessForsakenScript,
    "BG26_800": ManasaberScript,
    "BG28_300": HarmlessBoneheadScript,
    "BG29_611": CordPullerScript,
    "BG30_125": CadaverCaretakerScript,
    "BG34_630": TwilightHatchlingScript,
    "BG34_731": TwilightBroodmotherScript,
    "BG35_604": SewerLordScript,
    "BG32_172": AutoAssemblerScript,
    "BG26_801": RylakMetalheadScript,
    "BGS_012": KangorsApprenticeScript,
    # Deathrattle — buff spread / global
    "BG29_815": NightbaneScript,
    "BG33_828": ShipMasterEudoraScript,
    # Deathrattle — buff/damage/keywords
    "BGS_018": GoldrinnScript,
    "BG_DAL_775": TunnelBlasterScript,
    "BG23_318": LeeroyScript,
    "BG25_022": ScarletSkullScript,
    "BG28_309": MummifierScript,
    "BG35_122": DeterminedDefenderScript,
    "BG29_808": SpikedSaviorScript,
    "BG26_360": ScourfinScript,
    "BG34_920": TideRaiserScript,
    "BG32_434": SkulkingBristlemaneScript,
    "BG34_690": PlaguerunnerScript,
    # Battlecry — implemented
    "BG26_135": SouthseaBuskerScript,
    "BG25_011": NerubianDeathswarmerScript,
    "BG23_002": ShellCollectorScript,
    "BGS_030": KingBagurgleScript,
    "BG35_140": MamaMrrgltonScript,
    "BG35_141": PapaMrrgltonScript,
    "BG32_236": AureateLaureateScript,
    # Battlecry — Discover / Get random
    "BG34_523": HuntingTigerSharkScript,
    "BGS_020": PrimalfinLookoutScript,
    "BGS_123": TavernTempestScript,
    # Chromadrake
    "BG34_636t": GreenChromadrakeScript,
    "BG34_637t": BronzeChromadrakeScript,
    "BG34_634t": BlueChromadrakeScript,
    "BG34_635t": BlackChromadrakeScript,
    "BG34_638t": RedChromadrakeScript,
    # Avenge — implemented
    "BG33_371": POULTRONScript,
    "BG34_403": EternalTycoonScript,
    # Auras/passives
    "BG_LOE_077": BrannScript,
    "BG26_ICC_901": DrakkariScript,
    "BG_GVG_100": FloatingWatcherScript,
    # Rally
    "BG25_016": SindoreiStraightShotScript,
    "BG27_017": ObsidianRavagerScript,
    "BG33_241": SleepySupporterScript,
    "BG33_318": BileSpitterScript,
    "BG33_840": StompingStegodonScript,
    "BG34_604": HeroicUnderdogScript,
    # Start of Combat + Deathrattle
    "BG31_999": StitchedSalvagerScript,
    # Blood Gem — improvers
    "BG23_017": SanguineChampionScript,
    "BG26_159": MoonBaconJazzerScript,
    "BG26_160": PricklyPiperScript,
    # Blood Gem — multi-target
    "BG25_155": GemSmugglerScript,
    "BG26_867": ThreeLilQuilboarScript,
    "BG26_157": BristlebachScript,
    # Blood Gem — combined
    "BG32_430": GlowgulletWarlordScript,
    "BG32_434": SkulkingBristlemaneScript,
    # Blood Gem
    "BG20_100": RazorfenGeomancerScript,
    "BG33_888": HogWatcherScript,
    "BG35_432": BristlebackBullyScript,
    # Battlecry — placeholder
    "BG25_034": CaptainSandersScript,
    "BG24_009": PickyEaterScript,
    "BG31_330": OminousSeerScript,
    # Start of Combat — buff tribal
    "BG21_014": PrizedPromoDrakeScript,
    "BG24_500": AmberGuardianScript,
    "BG26_805": HummingBirdScript,
    "BG32_330": FlightyScoutScript,
    # Simple Deathrattle — get/summon tribal
    "BG25_806": SlyRaptorScript,
    "BG26_148": ScrapScraperScript,
    # Simple Rally
    "BG33_323": DustboneDevastatorScript,
    "BGS_078": MonstrousMacawScript,
    # Complex Battlecry
    "BG26_525": ImposingPercussionistScript,
    "BG28_550": RodeoPerformerScript,
    # "Get X" — specific named token cards
    "BG27_002": OozelingGladiatorScript,
    "BG32_170": MetallicHunterScript,
    "BG32_880": FriendlyGeistScript,
    "BG32_111": NightmareParteaGuestScript,
    "BG33_809": DivineSparkbotScript,
    "BG32_891": ShadowdancerScript,
    "BG34_694": WintergraspGhoulScript,
    "BG35_143": DeepwaterChieftainScript,
    "BG35_881": LeylineSurfacerScript,
    "BG35_882": FirelandsFugitiveScript,
    # "Give minions in the Tavern +X/+Y this game"
    "BG25_041": FelementalScript,
    "BG31_815": DuneDwellerScript,
    "BG35_152": VoidPupTrainerScript,
    # Summon from hand for combat only
    "BG27_556": DiremuckForagerScript,
    "BG34_140": ExpertAviatorScript,
    "BG31_835": DeathlyStrikerScript,
    # Improves after X
    "BG31_810": UltravioletAscendantScript,
    "BG26_814": LovesickBalladistScript,
    # After Tavern Refresh
    "BG34_865": EnDjinnBlazerScript,
    "BG34_856": WavelingScript,
    # After Battlecry Trigger
    "BG25_040": BlazingSkyfinScript,
    "BGS_041": KalecgosScript,
    # QuickWin — Tavern Buff / Hand Stats / Rally Per Type
    "BG27_016": ChampionOfSargerasScript,
    "BG26_354": ChoralMrrrglrScript,
    "BG34_320": TheLastOneStandingScript,
    # "Get random Tier/minion type" cards
    "BG34_319": HighkeeperRaScript,
    "BG34_632": IncubationResearcherScript,
    "BG34_633": DraconicWardenScript,
    # Complex Battlecry — targeted destroy / sacrifice
    "BG28_303": DisguisedGraverobberScript,
    # Tavern spell interaction
    "BG32_822": FireForgedEvokerScript,
    "BG35_702": RovingSailorScript,
    # Active — Refresh tracking + Fodder keyword
    "BG35_150": LaboratoryAssistantScript,
    # Free refresh / spell discount
    "BGS_116": RefreshingAnomalyScript,
    "BG35_340": AlertAlarmistScript,
    # Spellcraft — Naga Spellcraft effects
    "BG23_008": GlowscaleScript,
    "BG31_920": DarkcrestStrategistScript,
    "BG33_319": RimescalePriestessScript,
    "BG23_004": DeepSeaAnglerScript,
    "BG23_007": WaveriderScript,
    "BG26_501": ReefRifferScript,
    "BG27_004": SurfNSurfScript,
    "BG27_514": SeaWitchZarjiraScript,
    "BG32_835": TranquilMeditativeScript,
    # On-Sell
    "BG20_301": SunBaconRelaxerScript,
    "BG22_202": TadScript,
    "BGS_115": SellementalScript,
    "BG33_140": RiverSkipperScript,
    "BG32_860": ShoalfinMysticScript,
    "BG31_816": FireBallerScript,
    "BG31_818": SnowBallerScript,
    # End-of-Turn
    "BG28_595": IgnitionSpecialistScript,
    "BG31_171": MoonsteelJuggernautScript,
    "BG31_178": MarqueeTickerScript,
    "BG35_142": CousinErrglScript,
    "BG32_821": FelfireConjurerScript,
    "BG32_235": SurfingSylvarScript,
    "BG35_151": WoodlandDefilerScript,
    # Start-of-Turn
    "BG26_147": AccordOTronScript,
    # ── Phase 16 Batch: EoT / OnSell / Spellcraft ──
    # End of Turn — consume / stat transfer / blood gem / buff
    "BG21_005": FamishedFelbatScript,
    "BG34_500": FlamingEnforcerScript,
    "BG34_145": FuturefinScript,
    "BG35_433": RedtuskThornraiserScript,
    "BG35_334": SkeletalStraferScript,
    "BG35_701": BrazenBuccaneerScript,
    "BG35_431": EarthsongShamanScript,
    "BG26_529": UpbeatFrontdrakeScript,
    "BG35_123": CataclysmicHarbingerScript,
    # On-Sell
    "BGS_049": FreedealingGamblerScript,
    "BG24_715": PatientScoutScript,
    "BG24_018": TortollanBlueShellScript,
    # Spellcraft
    "BG26_502": DeepBlueCroonerScript,
    # Deathrattle
    "BG33_821": ShipwreckedRascalScript,
    # Bounty generators (EoT / Rally)
    "BG33_820": LostCityLooterScript,
    "BG33_822": BigwigBanditScript,
    "BGDUO_111": GenerousGeomancerScript,
    "BGDUO_110": FeistyFreshwaterScript,
    # Avenge
    "BG32_324": DrustfallenButcherScript,
    # Battlecry
    "BG34_926": RuthlessQueensguardScript,
    # Rally
    "BG34_925": SeafloorRecruiterScript,
    "BG35_700": ShipJumperScript,
    # "Wherever this is" trackers
    "BG_TTN_401": AncestralAutomatonScript,
    "BG25_008": EternalKnightScript,
    "BG25_013": RotHideGnollScript,
    "BG35_342": FallingSkyGolemScript,
    # Tier/Keyword-based effects
    "BG26_175": ElementalOfSurpriseScript,
    "BGS_004": WrathWeaverScript,
    "BG20_203": ProphetOfTheBoarScript,
    "BG30_122": MrglinBurglarScript,
    "BG35_153": ConsummateConquerorScript,
    "BG35_155": TwistedWrathguardScript,
    "BG35_602": LurkingLeviathanScript,
    "BG34_321": RabidPantherScript,
    "BG35_883": BalindaStonehearthScript,
    "BG35_814": ScarletSurvivorScript,
    "BG25_354": TitusRivendareScript,
    "BG28_905": BazaarDealerScript,
    "BG25_520": LeechingFelhoundScript,
    "BG26_523": TichondriusScript,
    "BGS_131": DeadlySporeScript,
    "BG34_922": MaelstromEmergentScript,
    "BG26_817": BladeCollectorScript,
    "BG31_859": TechnicalElementScript,
    "BG25_039": PufferquilScript,
    "BG35_921": AbyssalBruiserScript,
    # ── Step 1: TAVERN_SPELL_CAST listeners ──
    "BG23_013": TidemistressAthissaScript,
    "BG27_005": TimecapnHooktailScript,
    "BG28_551": NalaaTheRedeemerScript,
    "BG28_707": LivingAzeriteScript,
    "BG28_741": ChargingCzarinaScript,
    "BG31_871": BattyTerrorguardScript,
    "BG34_692": ForsakenWeaverScript,
    # ── Step 1: Passive on_summon ──
    "BG32_341": HumongozzScript,
    "BG35_341": EnchantedSentinelScript,
    # ── Step 1: ELEMENTAL_PLAYED + MINION_BOUGHT listeners ──
    "BG31_812": IchoronTheProtectorScript,
    "BG35_801": GluttonousTroggScript,
    # ── Step 3: MINION_DAMAGED ──
    "BG29_300": VeryHungryWinterfinnerScript,
    "BG29_806": IridescentSkyblazerScript,
    "BG29_807": TrigoreTheLasherScript,
    "BG34_312": HardyOrcaScript,
    "BG35_601": WyvernOutriderScript,
    # ── Step 3: MINION_ATTACKED ──
    "BG29_816": RoaringRecruiterScript,
    "BG34_921": RingBearerScript,
    # ── Step 3: BLOOD_GEM_PLAYED ──
    "BG28_583": GeomagusRoogugScript,
    "BG35_434": HiredRitualistScript,
    # ── Step 3: MINION_PLAYED ──
    "BG30_102": OneAmalgamTourGroupScript,
    "BG33_893": PrimitivePainterScript,
    "BG31_035": GroundbreakerScript,
    # ── Step 3: Choose One ──
    "BG27_084": SprightlyScarabScript,
    "BG30_123": FearlessFoodieScript,
    "BG32_237": IntrepidBotanistScript,
    # ── Step 3: GOLD_SPENT threshold ──
    "BG26_810": GunpowderCourierScript,
    "BG31_824": DualWieldCorsairScript,
    "BG23_018": DarkgazeElderScript,
    # ── Step 3: ADD_TO_HAND + MAGNETIZED ──
    "BG25_032": PeggySturdyboneScript,
    "BG34_175": JunkJousterScript,
    # ── Step 5: In-hand effects + post-combat persistence + death filter ──
    "BG26_137": BreamCounterScript,
    "BG34_231": OldSoulScript,
    "BG34_639": EggOfTheEndtimesScript,
    "BG21_015": TarecgosaScript,
    "BG29_813": PersistentPoetScript,
    "BG24_707": BristlemaneScrapsmithScript,
    "BG35_437": VinespeakerScript,
}
