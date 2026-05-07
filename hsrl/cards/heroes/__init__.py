"""
HSRL Hero Card Definitions

Heroes and hero powers follow the same registration pattern as minions.
Each hero registers with CardType.HERO, and its power with CardType.HERO_POWER.
The HERO_POWER tag on the hero card maps to the hero power card_id.
"""

from hsrl.core.enums import CardType, GameTag, Race, Rarity
from hsrl.core.card_db import register_card
from hsrl.cards.heroes.scripts import HERO_POWER_SCRIPT_REGISTRY


# ═══════════════════════════════════════════════════════════════════════════════
# Example Hero Powers
# ═══════════════════════════════════════════════════════════════════════════════

register_card(
    card_id="EXAMPLE_HERO_POWER_BUFF",
    name="Example Hero Power (Buff)",
    text="Give a random friendly minion +1/+1.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_BUFF"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_GOLD",
    name="Example Hero Power (Gold)",
    text="Gain 2 Gold.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 2},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_GOLD"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_MULTI",
    name="Example Hero Power (Multi)",
    text="Give friendly Beasts +2 Attack.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_MULTI"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_SPELL",
    name="Example Hero Power (Spell Discover)",
    text="Hero Power (1): Discover a Tavern Spell of your Tier or lower.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_SPELL"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_FREEZE",
    name="Example Hero Power (Freeze Tavern)",
    text="Hero Power (0): Freeze a random minion in Bob's Tavern.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_FREEZE"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_COPY",
    name="Example Hero Power (Post-Combat Copy)",
    text="Passive: After combat, add a copy of the first enemy killed to your hand.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_COPY"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_DIG",
    name="Example Hero Power (Dig Counter)",
    text="Hero Power (1): Dig for a Golden minion! (4 Digs left.)",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_DIG"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_ROTATION",
    name="Example Hero Power (Type Rotation)",
    text="Passive: Each turn, rotate to a different tribe. Buy minions of that tribe to give them +1/+2.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_ROTATION"],
)

register_card(
    card_id="EXAMPLE_HERO_POWER_SOC",
    name="Example Hero Power (Start of Combat)",
    text="Passive: At the start of combat, give your left-most minion +2 Attack.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_SOC"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# Real Hero Powers
# ═══════════════════════════════════════════════════════════════════════════════

register_card(
    card_id="BG20_HERO_103p",
    name="Bloodbound",
    text="Hero Power (1): Give a random friendly minion +1/+1.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_103p"],
)

register_card(
    card_id="BG20_HERO_100p",
    name="Glory of Combat",
    text="Passive Hero Power. After a friendly minion kills an enemy, give it +1 Attack permanently.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_100p"],
)

register_card(
    card_id="BG20_HERO_101p",
    name="See the Light",
    text="Hero Power (2): Give a random friendly minion +2/+2.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 2},
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_101p"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# Example Hero
# ═══════════════════════════════════════════════════════════════════════════════

register_card(
    card_id="EXAMPLE_HERO_POWER_AURA",
    name="Example Hero Power (Permanent Aura)",
    text="Passive: Your Beasts have +1/+1.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 0},
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_AURA"],
)

register_card(
    card_id="EXAMPLE_HERO_AURA",
    name="Example Hero (Aura)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_AURA",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_AURA"],
)

register_card(
    card_id="EXAMPLE_HERO_SPELL",
    name="Example Hero (Spell Discover)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_SPELL",
        GameTag.HERO_POWER_COST: 1,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_SPELL"],
)

register_card(
    card_id="EXAMPLE_HERO_FREEZE",
    name="Example Hero (Freeze Tavern)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_FREEZE",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_FREEZE"],
)

register_card(
    card_id="EXAMPLE_HERO_COPY",
    name="Example Hero (Post-Combat Copy)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_COPY",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_COPY"],
)

register_card(
    card_id="EXAMPLE_HERO_DIG",
    name="Example Hero (Dig Counter)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_DIG",
        GameTag.HERO_POWER_COST: 1,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_DIG"],
)

register_card(
    card_id="EXAMPLE_HERO_ROTATION",
    name="Example Hero (Type Rotation)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_ROTATION",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_ROTATION"],
)

register_card(
    card_id="EXAMPLE_HERO_SOC",
    name="Example Hero (Start of Combat)",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_SOC",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_SOC"],
)

register_card(
    card_id="EXAMPLE_HERO",
    name="Example Hero",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "EXAMPLE_HERO_POWER_BUFF",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["EXAMPLE_HERO_POWER_BUFF"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# Real Heroes
# ═══════════════════════════════════════════════════════════════════════════════

register_card(
    card_id="BG20_HERO_103",
    name="Death Speaker Blackthorn",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "BG20_HERO_103p",
        GameTag.HERO_POWER_COST: 1,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_103p"],
)

register_card(
    card_id="BG20_HERO_100",
    name="Rokara",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "BG20_HERO_100p",
        GameTag.HERO_POWER_COST: 0,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_100p"],
)

register_card(
    card_id="BG20_HERO_101",
    name="Xyrella",
    text="",
    cardtype=CardType.HERO,
    tech_level=1,
    tags={
        GameTag.BASE_HEALTH: 30,
        GameTag.ARMOR: 0,
        GameTag.HERO_POWER: "BG20_HERO_101p",
        GameTag.HERO_POWER_COST: 2,
    },
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_101p"],
)

# ── Phase 16: Hero powers not auto-found by pool (alt variants, standalone) ──

register_card(
    card_id="BG26_HERO_102p2",
    name="Minor Hymn",
    text="Give a minion Health equal to your Tier.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG26_HERO_102p2"],
)

register_card(
    card_id="BG28_HERO_400p2",
    name="Lucky Roll",
    text="Roll a 6-sided die. Gain that much Gold.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 2},
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG28_HERO_400p2"],
)

register_card(
    card_id="BG20_HERO_283p_t2",
    name="Ironforge",
    text="In 2 turns, gain 2 Gold.",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["BG20_HERO_283p_t2"],
)

register_card(
    card_id="TB_BaconShop_HP_076",
    name="Piggy Bank",
    text="Gain 1 Gold. Increases by 1 each turn. (Once per game!)",
    cardtype=CardType.HERO_POWER,
    tech_level=1,
    tags={GameTag.HERO_POWER_COST: 1},
    script_class=HERO_POWER_SCRIPT_REGISTRY["TB_BaconShop_HP_076"],
)

# ── Batch-register remaining heroes from data files ───────────────────
from hsrl.cards.heroes.pool import register_all_heroes  # noqa: E402,F401
