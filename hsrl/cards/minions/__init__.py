"""
HSRL Minion Card Definitions

Standard examples for each Battlegrounds mechanism, plus all 270 pool minions.
Each card demonstrates exactly one (or a clean combination of) mechanic(s).
"""

from hsrl.core.enums import CardType, GameTag, Race, Rarity
from hsrl.core.card_db import register_card
from hsrl.core.actions import (
    AddToHand,
    ApplyGlobalAura,
    AttackImmediately,
    Buff,
    BuffRandomTavernMinion,
    BuffTavern,
    DealDamageToHero,
    DealDamageToRandomEnemy,
    Destroy,
    GainGold,
    GainKeyword,
    GetBloodGem,
    GetRandomMinion,
    Heal,
    Hit,
    ImproveBloodGem,
    ImproveTavernSpellBuff,
    IncrementImproveCounter,
    PlayBloodGems,
    ScheduleNextTurn,
    Summon,
    SummonFromHandForCombat,
    TriggerBattlecry,
    DiscoverMinion,
)
from hsrl.core.events import EventListener
from hsrl.core.enums import GameTag

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Vanilla Minion
# Natural Language: "A plain minion with no special abilities."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_VANILLA",
    name="Vanilla Test Minion",
    text="",
    cardtype=CardType.MINION,
    race=Race.BEAST,
    tech_level=1,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 3,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Taunt
# Natural Language: "Taunt."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_TAUNT",
    name="Taunt Test Minion",
    text="Taunt.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=1,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 4,
        GameTag.TAUNT: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Divine Shield
# Natural Language: "Divine Shield."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_DIVINE_SHIELD",
    name="Divine Shield Test Minion",
    text="Divine Shield.",
    cardtype=CardType.MINION,
    race=Race.MECH,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 1,
        GameTag.DIVINE_SHIELD: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Poisonous
# Natural Language: "Poisonous."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_POISONOUS",
    name="Poisonous Test Minion",
    text="Poisonous.",
    cardtype=CardType.MINION,
    race=Race.BEAST,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 1,
        GameTag.BASE_HEALTH: 1,
        GameTag.POISONOUS: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Reborn
# Natural Language: "Reborn."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_REBORN",
    name="Reborn Test Minion",
    text="Reborn.",
    cardtype=CardType.MINION,
    race=Race.UNDEAD,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.REBORN: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Windfury
# Natural Language: "Windfury."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_WINDFURY",
    name="Windfury Test Minion",
    text="Windfury.",
    cardtype=CardType.MINION,
    race=Race.DRAGON,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 4,
        GameTag.WINDFURY: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Cleave
# Natural Language: "Also damages the minions next to whomever he attacks."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_CLEAVE",
    name="Cleave Test Minion",
    text="Also damages the minions next to whomever he attacks.",
    cardtype=CardType.MINION,
    race=Race.DRAGON,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 6,
        GameTag.CLEAVE: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Token (1/1 vanilla, summoned by Deathrattle)
# Natural Language: "A plain 1/1 Token."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_TOKEN_1_1",
    name="Example Token 1/1",
    text="",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=1,
    tags={
        GameTag.BASE_ATK: 1,
        GameTag.BASE_HEALTH: 1,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Deathrattle (summon)
# Natural Language: "Deathrattle: Summon a 1/1 Token."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleDeathrattleScript:
    """Deathrattle: Summon a 1/1 Token."""
    @staticmethod
    def deathrattle(source, game):
        token = game.create_minion("EXAMPLE_TOKEN_1_1")
        return Summon(source.controller, token)

register_card(
    card_id="EXAMPLE_DEATHRATTLE",
    name="Deathrattle Test Minion",
    text="Deathrattle: Summon a 1/1 Token.",
    cardtype=CardType.MINION,
    race=Race.BEAST,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.DEATHRATTLE: True,
    },
    script_class=ExampleDeathrattleScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Battlecry (buff self)
# Natural Language: "Battlecry: Gain +2/+2."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleBattlecryScript:
    """Script class for the Battlecry example."""
    @staticmethod
    def battlecry(source, game):
        return Buff(source, atk=2, health=2)

register_card(
    card_id="EXAMPLE_BATTLECRY",
    name="Battlecry Test Minion",
    text="Battlecry: Gain +2/+2.",
    cardtype=CardType.MINION,
    race=Race.MURLOC,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleBattlecryScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Start of Combat
# Natural Language: "Start of Combat: Deal 3 damage to a random enemy minion."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleStartOfCombatScript:
    """Script class for Start of Combat example."""
    @staticmethod
    def start_of_combat(source, game):
        return DealDamageToRandomEnemy(None, 3)

register_card(
    card_id="EXAMPLE_START_OF_COMBAT",
    name="Start of Combat Test Minion",
    text="Start of Combat: Deal 3 damage to a random enemy minion.",
    cardtype=CardType.MINION,
    race=Race.MECH,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.START_OF_COMBAT: True,
    },
    script_class=ExampleStartOfCombatScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Avenge
# Natural Language: "Avenge (3): Gain Divine Shield."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleAvengeScript:
    """Script class for Avenge example."""
    @staticmethod
    def avenge(source, game):
        return GainKeyword(source, GameTag.DIVINE_SHIELD)

register_card(
    card_id="EXAMPLE_AVENGE",
    name="Avenge Test Minion",
    text="Avenge (3): Gain Divine Shield.",
    cardtype=CardType.MINION,
    race=Race.UNDEAD,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 4,
        GameTag.Avenge: True,
        GameTag.AVENGE_TARGET: 3,
    },
    script_class=ExampleAvengeScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Rally
# Natural Language: "Rally: Deal 2 damage to the target."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleRallyScript:
    """Rally: Deal 2 damage to the attack target."""
    @staticmethod
    def rally(source, game):
        target = game._last_attack_target
        if target and not target.dead:
            return Hit(target, 2, source)
        return None

register_card(
    card_id="EXAMPLE_RALLY",
    name="Rally Test Minion",
    text="Rally: Deal 2 damage to the target.",
    cardtype=CardType.MINION,
    race=Race.DRAGON,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 4,
        GameTag.RALLY: True,
    },
    script_class=ExampleRallyScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Venomous
# Natural Language: "Venomous."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_VENOMOUS",
    name="Venomous Test Minion",
    text="Venomous.",
    cardtype=CardType.MINION,
    race=Race.BEAST,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.VENOMOUS: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Magnetic
# Natural Language: "Magnetic. Taunt."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_MAGNETIC",
    name="Magnetic Test Minion",
    text="Magnetic. Taunt.",
    cardtype=CardType.MINION,
    race=Race.MECH,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 1,
        GameTag.MAGNETIC: True,
        GameTag.TAUNT: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Magnetic with Divine Shield
# Natural Language: "Magnetic. Divine Shield."
# Used to test keyword transfer during magnetic attachment.
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_MAGNETIC_DS",
    name="Magnetic Divine Shield",
    text="Magnetic. Divine Shield.",
    cardtype=CardType.MINION,
    race=Race.MECH,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.MAGNETIC: True,
        GameTag.DIVINE_SHIELD: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Golden Minion
# Natural Language: "This is a golden minion with doubled stats."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_GOLDEN",
    name="Golden Test Minion",
    text="Golden minion.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 6,
        GameTag.BASE_HEALTH: 6,
        GameTag.GOLDEN: True,
    },
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Blood Gem
# Natural Language: "Battlecry: Play a Blood Gem on this minion."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleBloodGemScript:
    """Battlecry: Play a Blood Gem on this minion."""
    @staticmethod
    def battlecry(source, game):
        return PlayBloodGems(source, count=1)

register_card(
    card_id="EXAMPLE_BLOOD_GEM",
    name="Blood Gem Test Minion",
    text="Battlecry: Play a Blood Gem on this minion.",
    cardtype=CardType.MINION,
    race=Race.QUILBOAR,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleBloodGemScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Discover
# Natural Language: "Battlecry: Discover a Beast."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleDiscoverScript:
    """Battlecry: Discover a Beast."""
    @staticmethod
    def battlecry(source, game):
        return DiscoverMinion(source.controller, race=Race.BEAST)

register_card(
    card_id="EXAMPLE_DISCOVER",
    name="Discover Test Minion",
    text="Battlecry: Discover a Beast.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleDiscoverScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Triple Test Minion
# Natural Language: "Three of these combine into a golden version."
# ═══════════════════════════════════════════════════════════════════════════════
register_card(
    card_id="EXAMPLE_TRIPLE",
    name="Triple Test Minion",
    text="Three of these combine into a golden version.",
    cardtype=CardType.MINION,
    race=Race.BEAST,
    tech_level=1,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 3,
    },
)

# ── Tier 2 minion for Triple Reward Discover testing ──────────────────
register_card(
    card_id="EXAMPLE_TIER2",
    name="Tier 2 Test Minion",
    text="A Tier 2 minion for Discover testing.",
    cardtype=CardType.MINION,
    race=Race.MECH,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
    },
)

# ═══════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Spellcraft (AddToHand)
# Natural Language: "Battlecry: Add a Vanilla Test Minion to your hand."
# ═══════════════════════════════════════════════════════════════════════════

class ExampleSpellcraftScript:
    """Battlecry: Add a Vanilla Test Minion to your hand."""
    @staticmethod
    def battlecry(source, game):
        return AddToHand(source.controller, "EXAMPLE_VANILLA")

register_card(
    card_id="EXAMPLE_SPELLCRAFT",
    name="Spellcraft Test Minion",
    text="Battlecry: Add a Vanilla Test Minion to your hand.",
    cardtype=CardType.MINION,
    race=Race.NAGA,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
        GameTag.SPELLCRAFT: True,
    },
    script_class=ExampleSpellcraftScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Global Aura
# Natural Language: "Battlecry: Your Beasts have +1 Attack this game."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleGlobalAuraScript:
    """Battlecry: Your Beasts have +1 Attack this game (global aura)."""

    @staticmethod
    def battlecry(source, game):
        return ApplyGlobalAura(source.controller, atk=1, health=0, race_filter=Race.BEAST)


register_card(
    card_id="EXAMPLE_GLOBAL_AURA",
    name="Global Aura Test Minion",
    text="Battlecry: Your Beasts have +1 Attack this game.",
    cardtype=CardType.MINION,
    race=Race.BEAST,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 1,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleGlobalAuraScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Tavern Buff
# Natural Language: "Battlecry: Give minions in the Tavern +2/+2 this game."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleTavernBuffScript:
    """Battlecry: Give minions in the Tavern +2/+2 this game."""

    @staticmethod
    def battlecry(source, game):
        return BuffTavern(source.controller, atk=2, health=2)


register_card(
    card_id="EXAMPLE_TAVERN_BUFF",
    name="Tavern Buff Minion",
    text="Battlecry: Give minions in the Tavern +2/+2 this game.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleTavernBuffScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Summon from Hand for Combat
# Natural Language: "Start of Combat: Summon the highest-Attack minion
#                    from your hand for this combat only."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleCombatSummonScript:
    """Start of Combat: Summon the highest-Attack minion from hand for combat."""

    @staticmethod
    def start_of_combat(source, game):
        hand = source.controller.hand
        candidates = [m for m in hand if m.get_tag(GameTag.CARDTYPE) == CardType.MINION]
        if not candidates:
            return None
        target = max(candidates, key=lambda m: m.atk)
        return SummonFromHandForCombat(source.controller, target)


register_card(
    card_id="EXAMPLE_COMBAT_SUMMON",
    name="Combat Summon Minion",
    text="Start of Combat: Summon the highest-Attack minion from your hand for this combat only.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.START_OF_COMBAT: True,
    },
    script_class=ExampleCombatSummonScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Improve (scaling buff)
# Natural Language: "Start of Combat: Give a friendly minion +1/+2.
#                    Improves after you play an Elemental!"
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleImproveScript:
    """Start of Combat: Give a friendly minion +1/+2.
    Improves after you play an Elemental!"""

    @staticmethod
    def on_summon(source, game):
        listener = EventListener(
            event_name="ELEMENTAL_PLAYED",
            action=IncrementImproveCounter(source),
            condition=lambda m, p: m != source,
        )
        game.register_listener(source, listener)
        return None

    @staticmethod
    def start_of_combat(source, game):
        counter = source.get_tag(GameTag.IMPROVE_COUNTER, 0)
        board = source.controller.board
        candidates = [m for m in board if not m.dead and m != source]
        if not candidates:
            return None
        import random
        target = random.choice(candidates)
        mult = 1 + counter
        return Buff(target, atk=1 * mult, health=2 * mult)


register_card(
    card_id="EXAMPLE_IMPROVE",
    name="Improve Test Minion",
    text="Start of Combat: Give a friendly minion +1/+2. Improves after you play an Elemental!",
    cardtype=CardType.MINION,
    race=Race.ELEMENTAL,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.START_OF_COMBAT: True,
    },
    script_class=ExampleImproveScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: After Tavern Refresh
# Natural Language: "Battlecry: After the Tavern is Refreshed this game,
#                    give a random minion in it +2/+2."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleAfterRefreshScript:
    """Battlecry: After the Tavern is Refreshed this game,
    give a random minion in it +2/+2."""

    @staticmethod
    def battlecry(source, game):
        listener = EventListener(
            event_name="TAVERN_REFRESH",
            action=BuffRandomTavernMinion(source.controller, atk=2, health=2),
        )
        game.register_listener(source, listener)
        return None


register_card(
    card_id="EXAMPLE_AFTER_REFRESH",
    name="After Refresh Test Minion",
    text="Battlecry: After the Tavern is Refreshed this game, give a random minion in it +2/+2.",
    cardtype=CardType.MINION,
    race=Race.ELEMENTAL,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleAfterRefreshScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: After Battlecry Trigger
# Natural Language: "After you trigger a Battlecry, gain +1/+1."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleBattlecryTriggerScript:
    """After you trigger a Battlecry, gain +1/+1."""

    @staticmethod
    def on_summon(source, game):
        listener = EventListener(
            event_name="BATTLECRY_TRIGGER",
            action=Buff(source, atk=1, health=1),
            condition=lambda t, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


register_card(
    card_id="EXAMPLE_BATTLECRY_TRIGGER",
    name="Battlecry Trigger Test Minion",
    text="After you trigger a Battlecry, gain +1/+1.",
    cardtype=CardType.MINION,
    race=Race.DRAGON,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 4,
    },
    script_class=ExampleBattlecryTriggerScript,
)

# ── EXAMPLE_TAVERN_SPELL_CAST ──────────────────────────────────────────

class ExampleTavernSpellCastScript:
    """After you cast a Tavern spell, gain +1/+1."""

    @staticmethod
    def on_summon(source, game):
        listener = EventListener(
            event_name="TAVERN_SPELL_CAST",
            action=Buff(source, atk=1, health=1),
            condition=lambda t, p: p == source.controller,
        )
        game.register_listener(source, listener)
        return None


register_card(
    card_id="EXAMPLE_TAVERN_SPELL_CAST",
    name="Tavern Spell Cast Test Minion",
    text="After you cast a Tavern spell, gain +1/+1.",
    cardtype=CardType.MINION,
    race=Race.ELEMENTAL,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
    },
    script_class=ExampleTavernSpellCastScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Blood Gem Spell Cards
# ═══════════════════════════════════════════════════════════════════════════════

register_card(
    card_id="BLOOD_GEM",
    name="Blood Gem",
    text="Give a friendly minion +1/+1.",
    cardtype=CardType.BLOOD_GEM_CARD,
    race=Race.INVALID,
    tech_level=1,
    tags={},
)

register_card(
    card_id="BLOOD_GEM_DS",
    name="Blood Gem",
    text="Give a friendly Quilboar +1/+1 and Divine Shield.",
    cardtype=CardType.BLOOD_GEM_CARD,
    race=Race.INVALID,
    tech_level=1,
    tags={GameTag.DIVINE_SHIELD: True},
)

register_card(
    card_id="BLOOD_GEM_TAUNT",
    name="Blood Gem",
    text="Give a friendly Quilboar +1/+1 and Taunt.",
    cardtype=CardType.BLOOD_GEM_CARD,
    race=Race.INVALID,
    tech_level=1,
    tags={GameTag.TAUNT: True},
)

# ═══════════════════════════════════════════════════════════════════════════════
# Tavern Coin Spell Card
# ═══════════════════════════════════════════════════════════════════════════════

register_card(
    card_id="TAVERN_COIN",
    name="Tavern Coin",
    text="Gain 1 Gold.",
    cardtype=CardType.SPELL,
    race=Race.INVALID,
    tech_level=1,
    tags={},
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: End of Turn
# Natural Language: "At the end of your turn, give this minion +1/+1."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleEndOfTurnScript:
    """End of Turn: Give this minion +1/+1."""
    @staticmethod
    def end_of_turn(source, game):
        return Buff(source, atk=1, health=1)

register_card(
    card_id="EXAMPLE_END_OF_TURN",
    name="End of Turn Test Minion",
    text="At the end of your turn, give this minion +1/+1.",
    cardtype=CardType.MINION,
    race=Race.DEMON,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 3,
        GameTag.END_OF_TURN: True,
    },
    script_class=ExampleEndOfTurnScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Start of Turn
# Natural Language: "At the start of your turn, gain 1 Gold."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleStartOfTurnScript:
    """Start of Turn: Gain 1 Gold."""
    @staticmethod
    def start_of_turn(source, game):
        return GainGold(source.controller, 1)

register_card(
    card_id="EXAMPLE_START_OF_TURN",
    name="Start of Turn Test Minion",
    text="At the start of your turn, gain 1 Gold.",
    cardtype=CardType.MINION,
    race=Race.PIRATE,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.START_OF_TURN: True,
    },
    script_class=ExampleStartOfTurnScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: On Sell
# Natural Language: "When you sell this, get a random Murloc."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleOnSellScript:
    """When you sell this, get a random Murloc."""
    @staticmethod
    def on_sell(source, game):
        return GetRandomMinion(source.controller, race=Race.MURLOC)

register_card(
    card_id="EXAMPLE_ON_SELL",
    name="On Sell Test Minion",
    text="When you sell this, get a random Murloc.",
    cardtype=CardType.MINION,
    race=Race.MURLOC,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.ON_SELL: True,
    },
    script_class=ExampleOnSellScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: On Sell — Baller (per-card-ID counter pattern)
# Natural Language: "When you sell this, give your minions +{0} Attack.
# Improve your future Ballers."
# Pattern: Read(player_counter) → Buff(all, amount=counter) → Increment(counter)
# The counter lives on Player and accumulates across all copies of this card.
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleOnSellBallerScript:
    """When you sell this, give your minions +{0} Attack. Improves each sale."""
    @staticmethod
    def on_sell(source, game):
        from hsrl.core.actions import Action
        class _BallerAction(Action):
            def do(self, source_ent, game_ref, target=None):
                player = source.controller
                bonus = player.get_tag(GameTag.BALLER_FIRE_BONUS, 0)
                for m in player.get_board_minions():
                    if not m.dead:
                        game_ref.queue_action(Buff(m, atk=bonus))
                player.set_tag(GameTag.BALLER_FIRE_BONUS, bonus + 1)
        return _BallerAction()

register_card(
    card_id="EXAMPLE_ON_SELL_BALLER",
    name="On Sell Baller Test Minion",
    text="When you sell this, give your minions +{0} Attack. Improve your future Ballers.",
    cardtype=CardType.MINION,
    race=Race.ELEMENTAL,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 4,
        GameTag.BASE_HEALTH: 3,
        GameTag.ON_SELL: True,
    },
    script_class=ExampleOnSellBallerScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Transform (Chromadrake)
# Natural Language: "Start of Combat: Transform this into an 8/8 Dragon."
# ═══════════════════════════════════════════════════════════════════════════════

# Token minion that is the "evolved" form for the Example Transform test
register_card(
    card_id="EXAMPLE_TRANSFORMED",
    name="Transformed Dragon",
    text="",
    cardtype=CardType.MINION,
    race=Race.DRAGON,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 8,
        GameTag.BASE_HEALTH: 8,
    },
)

class ExampleTransformScript:
    """Start of Combat: Transform this into an 8/8 Dragon."""
    @staticmethod
    def start_of_combat(source, game):
        from hsrl.core.actions import Transform
        return Transform(source, "EXAMPLE_TRANSFORMED")

register_card(
    card_id="EXAMPLE_TRANSFORM",
    name="Transform Test Minion",
    text="Start of Combat: Transform this into an 8/8 Dragon.",
    cardtype=CardType.MINION,
    race=Race.DRAGON,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.START_OF_COMBAT: True,
        GameTag.CHROMADRAKE: True,
    },
    script_class=ExampleTransformScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Fodder (Demon Consume)
# Natural Language: "Fodder: Battlecry: Consume a minion in your hand to gain its stats."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleFodderScript:
    """Battlecry (Fodder): Consume a minion in your hand to gain its stats."""
    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import FodderConsume
        hand = source.controller.get_hand_minions()
        if hand:
            target = max(hand, key=lambda m: m.atk + m.max_health)
            return FodderConsume(source, target)
        return None

register_card(
    card_id="EXAMPLE_FODDER",
    name="Fodder Test Minion",
    text="Fodder: Battlecry: Consume a minion in your hand to gain its stats.",
    cardtype=CardType.MINION,
    race=Race.DEMON,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
        GameTag.FODDER: True,
    },
    script_class=ExampleFodderScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Spellcraft Spell Token
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleSCSpellScript:
    """on_play: Give a friendly minion +2/+2 (player-chosen during recruit, random in combat)."""
    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            controller = source.controller
            board = controller.get_board_minions() if controller else []
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            return Buff(target, atk=2, health=2)

        return TargetedAction(filter_fn, action_factory,
                              label="Spellcraft Spell — +2/+2")

register_card(
    card_id="EXAMPLE_SC_SPELL",
    name="Spellcraft Spell",
    text="Give a minion +2/+2 until next turn.",
    cardtype=CardType.SPELL,
    race=Race.INVALID,
    tech_level=1,
    tags={
        GameTag.SPELLCRAFT_SPELL: True,
    },
    script_class=ExampleSCSpellScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Spellcraft Spell Cards — Real Effects
# ═══════════════════════════════════════════════════════════════════════════════

class GlowingCrownScript:
    """on_play: Give a friendly minion Divine Shield (player-chosen during recruit, random in combat)."""
    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            controller = source.controller
            board = controller.get_board_minions() if controller else []
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            return GainKeyword(target, GameTag.DIVINE_SHIELD)

        return TargetedAction(filter_fn, action_factory,
                              label="Glowing Crown — give Divine Shield")

register_card(
    card_id="BG23_008t", name="Glowing Crown",
    text="Give a minion Divine Shield until next turn.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=GlowingCrownScript,
)

class EvolvingStrategyScript:
    """on_play: Add a random Naga to hand."""
    @staticmethod
    def on_play(source, game):
        import random
        from hsrl.core.card_db import CARDS
        naga_ids = [
            cid for cid, card in CARDS._cards.items()
            if card.cardtype == CardType.MINION and card.race == Race.NAGA
            and not cid.startswith('EXAMPLE') and not cid.startswith('BGDUO')
        ]
        if not naga_ids:
            return None
        chosen = random.choice(naga_ids)
        return AddToHand(source.controller, chosen)

register_card(
    card_id="BG31_920t", name="Evolving Strategy",
    text="Get a random Tier X Naga.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=EvolvingStrategyScript,
)

class RimeOrReasonScript:
    """on_play: Add a random Tavern spell that gives stats to hand."""
    @staticmethod
    def on_play(source, game):
        import random
        from hsrl.core.card_db import CARDS
        # Find spells that likely give stats (filter by name/text keywords)
        spell_ids = [
            cid for cid, card in CARDS._cards.items()
            if card.cardtype == CardType.SPELL
            and not cid.startswith('EXAMPLE')
            and not cid.startswith('BG23_008t')
            and not cid.startswith('BG31_920t')
            and not cid.startswith('BG33_319t')
            and not cid.startswith('BG23_004t')
            and not cid.startswith('BG23_007t')
            and not cid.startswith('BG26_501t')
            and not cid.startswith('BG26_502t')
            and not cid.startswith('BG27_004t')
            and not cid.startswith('BG27_514t')
            and not cid.startswith('BG32_835t')
            and '_GOLDEN' not in cid
        ]
        if not spell_ids:
            return None
        chosen = random.choice(spell_ids)
        return AddToHand(source.controller, chosen)

register_card(
    card_id="BG33_319t", name="Rime or Reason",
    text="Get a random Tavern spell that gives stats.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=RimeOrReasonScript,
)

class AnglersLureScript:
    """on_play: Give a friendly minion +2/+2 and Taunt (player-chosen during recruit, random in combat)."""
    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            controller = source.controller
            board = controller.get_board_minions() if controller else []
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            return [
                Buff(target, atk=2, health=2),
                GainKeyword(target, GameTag.TAUNT),
            ]

        return TargetedAction(filter_fn, action_factory,
                              label="Angler's Lure — +2/+2 and Taunt")

register_card(
    card_id="BG23_004t", name="Angler's Lure",
    text="Give a minion +2/+2 and Taunt until next turn.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=AnglersLureScript,
)

class UnderseaMountScript:
    """on_play: Give a friendly minion +2/+2. If Naga, also Windfury (player-chosen during recruit, random in combat)."""
    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            controller = source.controller
            board = controller.get_board_minions() if controller else []
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            actions = [Buff(target, atk=2, health=2)]
            if target.race == Race.NAGA:
                actions.append(GainKeyword(target, GameTag.WINDFURY))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Undersea Mount — +2/+2 (Windfury if Naga)")

register_card(
    card_id="BG23_007t", name="Undersea Mount",
    text="Give a minion +2/+2. If it's a Naga, also give it Windfury until next turn.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=UnderseaMountScript,
)

class SickRiffsScript:
    """on_play: Give a friendly minion stats equal to your Tier (player-chosen during recruit, random in combat)."""
    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            controller = source.controller
            board = controller.get_board_minions() if controller else []
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            tier = source.controller.tavern_tier
            return Buff(target, atk=tier, health=tier)

        return TargetedAction(filter_fn, action_factory,
                              label="Sick Riffs — stats equal to Tier")

register_card(
    card_id="BG26_501t", name="Sick Riffs",
    text="Give a minion stats equal to your Tier until next turn.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=SickRiffsScript,
)

# ── BG32_835t: Meditation (Tranquil Meditative Spellcraft token) ────────
class MeditationSpellScript:
    """Spellcraft spell: Improve future Tavern spell buffs by +1/+1."""
    @staticmethod
    def on_play(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1)

register_card(
    card_id="BG32_835t", name="Meditation",
    text="Your Tavern spells give an extra +1/+1 this game.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True},
    script_class=MeditationSpellScript,
)
register_card(
    card_id="BG32_835t_GOLDEN", name="Meditation",
    text="Your Tavern spells give an extra +1/+1 this game.",
    cardtype=CardType.SPELL, race=Race.INVALID, tech_level=1,
    tags={GameTag.SPELLCRAFT_SPELL: True, GameTag.GOLDEN: True},
    script_class=MeditationSpellScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Tavern Spell Buff Modifier
# Natural Language: "Deathrattle: Your Tavern spells give an extra +1 Health this game."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleSpellModifierScript:
    """Deathrattle: Your Tavern spells give an extra +1 Health this game."""
    @staticmethod
    def deathrattle(source, game):
        return ImproveTavernSpellBuff(source.controller, health_bonus=1)

register_card(
    card_id="EXAMPLE_SPELL_MODIFIER",
    name="Tavern Spell Modifier (Test)",
    text="Deathrattle: Your Tavern spells give an extra +1 Health this game.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=1,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.DEATHRATTLE: True,
    },
    script_class=ExampleSpellModifierScript,
)

class ExampleSpellModifierBCScript:
    """Battlecry: Your Tavern spells give an extra +1/+1 this game."""
    @staticmethod
    def battlecry(source, game):
        return ImproveTavernSpellBuff(source.controller, atk_bonus=1, health_bonus=1)

register_card(
    card_id="EXAMPLE_SPELL_MODIFIER_BC",
    name="Tavern Spell Modifier BC (Test)",
    text="Battlecry: Your Tavern spells give an extra +1/+1 this game.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=1,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleSpellModifierBCScript,
)

class ExampleBuffSpellScript:
    """on_play: Give a friendly minion +2/+2 (player-chosen during recruit, reads tavern spell modifiers)."""
    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import TargetedAction

        def filter_fn():
            controller = source.controller
            board = controller.get_board_minions()
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            atk_bonus = source.controller.get_tag(GameTag.TAVERN_SPELL_ATK_BONUS, 0)
            health_bonus = source.controller.get_tag(GameTag.TAVERN_SPELL_HEALTH_BONUS, 0)
            return Buff(target, atk=2 + atk_bonus, health=2 + health_bonus)

        return TargetedAction(filter_fn, action_factory,
                              label="Buff Spell — +2/+2 with modifiers")

register_card(
    card_id="EXAMPLE_BUFF_SPELL",
    name="Buff Spell (Test)",
    text="Give a friendly minion +2/+2.",
    cardtype=CardType.SPELL,
    race=Race.INVALID,
    tech_level=1,
    tags={GameTag.COST: 1},
    script_class=ExampleBuffSpellScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Spellcraft
# Natural Language: "Spellcraft: Give a minion +2/+2 until next turn."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleSpellcraftMinionScript:
    """Spellcraft: Give a minion +2/+2 until next turn."""
    @staticmethod
    def spellcraft(source, game):
        return "EXAMPLE_SC_SPELL"

register_card(
    card_id="EXAMPLE_SPELLCRAFT_MINION",
    name="Spellcraft Test Minion",
    text="Spellcraft: Give a minion +2/+2 until next turn.",
    cardtype=CardType.MINION,
    race=Race.NAGA,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.SPELLCRAFT: True,
    },
    script_class=ExampleSpellcraftMinionScript,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD EXAMPLE: Silence
# Natural Language: "Battlecry: Silence a random friendly minion."
# ═══════════════════════════════════════════════════════════════════════════════

class ExampleSilenceScript:
    """Battlecry: Silence a random friendly minion."""

    @staticmethod
    def battlecry(source, game):
        import random as _random
        from hsrl.core.actions import Silence
        candidates = [m for m in source.controller.get_board_minions()
                      if m is not source and not m.dead]
        if not candidates:
            return None
        target = _random.choice(candidates)
        return Silence(target)


register_card(
    card_id="EXAMPLE_SILENCE",
    name="Silence Test Minion",
    text="Battlecry: Silence a random friendly minion.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleSilenceScript,
)

# ── Standard Example: Consume Tavern ────────────────────────────────────

class ExampleConsumeTavernScript:
    """Battlecry: Consume a random minion in the Tavern to gain its stats."""

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import ConsumeTavernMinion
        return ConsumeTavernMinion(source.controller, source, mode="random")


register_card(
    card_id="EXAMPLE_CONSUME_TAVERN",
    name="Consume Tavern Test Minion",
    text="Battlecry: Consume a random minion in the Tavern to gain its stats.",
    cardtype=CardType.MINION,
    race=Race.DEMON,
    tech_level=2,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleConsumeTavernScript,
)


# ── Standard Example: Turns in Hand ───────────────────────────────────

class ExampleTurnsInHandScript:
    """Battlecry: Gain +1/+1 for each turn this has been in your hand."""

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import Buff
        turns = source.get_tag(GameTag.TURNS_IN_HAND, 0)
        if turns <= 0:
            return None
        return Buff(source, atk=turns, health=turns)


register_card(
    card_id="EXAMPLE_TURNS_IN_HAND",
    name="Turns-in-Hand Test Minion",
    text="Battlecry: Gain +1/+1 for each turn this has been in your hand.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 2,
        GameTag.BASE_HEALTH: 2,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleTurnsInHandScript,
)

# ── Standard Example: Last Spell ──────────────────────────────────────

class ExampleLastSpellScript:
    """Battlecry: Replay the last tavern spell you cast this turn."""

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import Buff
        spell_id = source.controller.get_tag(GameTag.LAST_SPELL_CARD_ID, "")
        if not spell_id:
            return None
        # For testing: buff self based on having played a spell
        return Buff(source, atk=2, health=2)


register_card(
    card_id="EXAMPLE_LAST_SPELL",
    name="Last Spell Test Minion",
    text="Battlecry: If you've cast a tavern spell this turn, gain +2/+2.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleLastSpellScript,
)

# ── Standard Example: Cards Played This Turn ───────────────────────────

class ExampleCardsPlayedScript:
    """Battlecry: If you've played 3 or more other minions this turn, gain +3/+3."""

    @staticmethod
    def battlecry(source, game):
        from hsrl.core.actions import Buff
        # source was already counted in the counter when it was played
        # So check if ≥4 (i.e., 3+ others)
        played = source.controller.get_tag(GameTag.CARDS_PLAYED_THIS_TURN, 0)
        if played >= 4:
            return Buff(source, atk=3, health=3)
        return None


register_card(
    card_id="EXAMPLE_CARDS_PLAYED",
    name="Cards Played Test Minion",
    text="Battlecry: If you've played 3 or more minions this turn, gain +3/+3.",
    cardtype=CardType.MINION,
    race=Race.NONE,
    tech_level=3,
    tags={
        GameTag.BASE_ATK: 3,
        GameTag.BASE_HEALTH: 3,
        GameTag.BATTLECRY: True,
    },
    script_class=ExampleCardsPlayedScript,
)


# ── Load token minions ────────────────────────────────────────────────
from hsrl.cards.minions.tokens import register_all_tokens  # noqa: E402

# ── Load all pool minions from data files ─────────────────────────────
from hsrl.cards.minions.pool import register_all_pool_minions  # noqa: E402
