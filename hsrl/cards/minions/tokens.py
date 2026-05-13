"""
Token minions and spells summoned/referenced by deathrattles, battlecries,
and other effects.

Tokens are NOT buyable from the tavern. They are created dynamically
during gameplay by other cards' effects.

All tokens use Blizzard's original card IDs for consistency.
"""

from hsrl.core.card_db import register_card
from hsrl.core.enums import CardType, GameTag, Race, Rarity


class _SlimyShieldScript:
    """Give a minion +1/+1 and Taunt."""

    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import Buff, GainKeyword, TargetedAction

        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            return [Buff(target, atk=1, health=1),
                    GainKeyword(target, GameTag.TAUNT)]

        return TargetedAction(filter_fn, action_factory,
                              label="Slimy Shield — +1/+1 + Taunt")


class _ForestBountyScript:
    """Give a friendly minion +1/+1 for each friendly minion type."""

    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import Buff, TargetedAction

        board = [m for m in source.controller.board if not m.dead]
        unique_types = set()
        for m in board:
            r = m.race
            if r and r not in (Race.INVALID, Race.NONE, Race.ALL):
                unique_types.add(r)
        bonus = len(unique_types)

        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            return Buff(target, atk=bonus, health=bonus)

        return TargetedAction(filter_fn, action_factory,
                              label=f"Forest's Bounty — +{bonus}/+{bonus}")


class _SparePartScript:
    """Give a minion +5/+5 and a random bonus effect."""

    @staticmethod
    def on_play(source, game):
        import random
        from hsrl.core.actions import Buff, GainKeyword, TargetedAction

        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            actions = [Buff(target, atk=5, health=5)]
            # Random bonus: Taunt, DS, Windfury, or Reborn
            bonus = random.choice([GameTag.TAUNT, GameTag.DIVINE_SHIELD,
                                   GameTag.WINDFURY, GameTag.REBORN])
            actions.append(GainKeyword(target, bonus))
            return actions

        return TargetedAction(filter_fn, action_factory,
                              label="Spare Part — +5/+5 + random keyword")


class _WindfuryDSScript:
    """Give a friendly minion Windfury and Divine Shield."""

    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import GainKeyword, TargetedAction

        def filter_fn():
            return [m for m in source.controller.board if not m.dead]

        def action_factory(target):
            return [GainKeyword(target, GameTag.WINDFURY),
                    GainKeyword(target, GameTag.DIVINE_SHIELD)]

        return TargetedAction(filter_fn, action_factory,
                              label="Windfury + Divine Shield")


def register_all_tokens():
    """Register all token minions and spells into the global CARDS registry."""

    # ═══════════════════════════════════════════════════════════════════════
    # Minion Tokens — summoned by other cards
    # ═══════════════════════════════════════════════════════════════════════

    # ── Half-Shell (Turtle) — summoned by Sewer Rat deathrattle ────────
    register_card(
        card_id="BG19_010t",
        name="Half-Shell",
        text="Taunt",
        cardtype=CardType.MINION,
        race=Race.BEAST,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 2,
            GameTag.BASE_HEALTH: 3,
            GameTag.TAUNT: True,
        },
    )

    # ── Skeleton — summoned by Harmless Bonehead, Cadaver Caretaker ───
    register_card(
        card_id="BG_ICC_026t",
        name="Skeleton",
        text="",
        cardtype=CardType.MINION,
        race=Race.UNDEAD,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
        },
    )

    # ── Microbot — summoned by Cord Puller deathrattle ─────────────────
    register_card(
        card_id="BG_BOT_312t",
        name="Microbot",
        text="",
        cardtype=CardType.MINION,
        race=Race.MECH,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
        },
    )

    # ── Cubling — summoned by Manasaber deathrattle ────────────────────
    register_card(
        card_id="BG26_800t",
        name="Cubling",
        text="Taunt",
        cardtype=CardType.MINION,
        race=Race.BEAST,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 0,
            GameTag.BASE_HEALTH: 1,
            GameTag.TAUNT: True,
        },
    )

    # ── Helping Hand — summoned by Handless Forsaken deathrattle ───────
    register_card(
        card_id="BG25_010t",
        name="Helping Hand",
        text="Reborn",
        cardtype=CardType.MINION,
        race=Race.UNDEAD,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 2,
            GameTag.BASE_HEALTH: 1,
            GameTag.REBORN: True,
        },
    )

    # ── Twilight Whelp — summoned by Twilight Hatchling deathrattle ────
    register_card(
        card_id="BG34_630t",
        name="Twilight Whelp",
        text="",
        cardtype=CardType.MINION,
        race=Race.DRAGON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 3,
            GameTag.BASE_HEALTH: 3,
        },
    )

    # ── Glowgullet Soldier — summoned by Glowgullet Warlord deathrattle ──
    register_card(
        card_id="BG32_430t",
        name="Glowgullet Soldier",
        text="Taunt",
        cardtype=CardType.MINION,
        race=Race.QUILBOAR,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
            GameTag.TAUNT: True,
        },
    )

    # ── Sky Pirate — summoned by Sky Pirate Flagbearer, Ship Jumper ────
    register_card(
        card_id="BGS_061t",
        name="Sky Pirate",
        text="Charge",
        cardtype=CardType.MINION,
        race=Race.PIRATE,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
            GameTag.CHARGE: True,
        },
    )

    # ── Water Droplet — from BGS_115 Sellemental on-sell ──────────────
    register_card(
        card_id="BGS_115t",
        name="Water Droplet",
        text="",
        cardtype=CardType.MINION,
        race=Race.ELEMENTAL,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 3,
            GameTag.BASE_HEALTH: 3,
        },
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Chromadrake Tokens — Dragon minions (BG34_632 Incubation Researcher)
    # ═══════════════════════════════════════════════════════════════════════

    register_card(
        card_id="BG34_634_Gt",
        name="Blue Chromadrake",
        text="",
        cardtype=CardType.MINION,
        race=Race.DRAGON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 6,
            GameTag.BASE_HEALTH: 6,
            GameTag.CHROMADRAKE: True,
        },
    )

    register_card(
        card_id="BG34_635_Gt",
        name="Black Chromadrake",
        text="Taunt",
        cardtype=CardType.MINION,
        race=Race.DRAGON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 8,
            GameTag.BASE_HEALTH: 8,
            GameTag.TAUNT: True,
            GameTag.CHROMADRAKE: True,
        },
    )

    register_card(
        card_id="BG34_636_Gt",
        name="Green Chromadrake",
        text="Divine Shield",
        cardtype=CardType.MINION,
        race=Race.DRAGON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 5,
            GameTag.BASE_HEALTH: 5,
            GameTag.DIVINE_SHIELD: True,
            GameTag.CHROMADRAKE: True,
        },
    )

    register_card(
        card_id="BG34_637_Gt",
        name="Bronze Chromadrake",
        text="Reborn",
        cardtype=CardType.MINION,
        race=Race.DRAGON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 4,
            GameTag.BASE_HEALTH: 4,
            GameTag.REBORN: True,
            GameTag.CHROMADRAKE: True,
        },
    )

    register_card(
        card_id="BG34_638_Gt",
        name="Red Chromadrake",
        text="Windfury",
        cardtype=CardType.MINION,
        race=Race.DRAGON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 7,
            GameTag.BASE_HEALTH: 7,
            GameTag.WINDFURY: True,
            GameTag.CHROMADRAKE: True,
        },
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Spell Tokens — "Get X" effects add these to hand
    # ═══════════════════════════════════════════════════════════════════════

    # ── Slimy Shield — from BG27_002 Oozeling Gladiator ────────────────
    register_card(
        card_id="BG27_002t",
        name="Slimy Shield",
        text="Give a minion +1/+1 and Taunt.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
        script_class=_SlimyShieldScript,
    )

    # ── Pointy Arrow — from BG32_170 Metallic Hunter ───────────────────
    register_card(
        card_id="EBG_Spell_014",
        name="Pointy Arrow",
        text="Give a minion +4 Attack.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
    )

    # ── Staff of Enrichment — from BG32_891 Shadowdancer ───────────────
    register_card(
        card_id="BG28_886",
        name="Staff of Enrichment",
        text="Give a minion +2/+2.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=3,
        tags={},
    )

    # ── Misplaced Tea Set — from BG32_111 Nightmare Par-tea Guest ──────
    register_card(
        card_id="BG28_888",
        name="Misplaced Tea Set",
        text="Give a friendly minion +2/+2.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    # ── Sanctify — from BG33_809 Divine Sparkbot ───────────────────────
    register_card(
        card_id="BG33_817",
        name="Sanctify",
        text="Give a friendly minion +1/+2 and Divine Shield.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=5,
        tags={},
    )

    # ── Butchering — from BG32_324 Drustfallen Butcher ─────────────────
    register_card(
        card_id="BG28_604",
        name="Butchering",
        text="Destroy a friendly minion. Give its stats to another friendly minion.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=5,
        tags={},
    )

    # ── Tomb Turning — from BG34_694 Wintergrasp Ghoul ─────────────────
    register_card(
        card_id="BG34_888",
        name="Tomb Turning",
        text="Give a minion +4/+4.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    # ── Chef's Choice — from BG34_925 Seafloor Recruiter ───────────────
    register_card(
        card_id="BG28_518",
        name="Chef's Choice",
        text="Choose a minion. Give it stats equal to your Tavern Tier.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=2,
        tags={},
    )

    # ── Queen's Command — from BG34_926 Ruthless Queensguard ───────────
    register_card(
        card_id="BG35_922",
        name="Queen's Command",
        text="Give a friendly minion +2/+2 for each of your minion types.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=5,
        tags={},
    )

    # ── Deepwater Clan — from BG35_143 Deepwater Chieftain ─────────────
    register_card(
        card_id="BG35_149",
        name="Deepwater Clan",
        text="Give a friendly Murloc +3/+3.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    # ── Arcane Absorption — from BG35_881 Leyline Surfacer ─────────────
    register_card(
        card_id="BG35_911",
        name="Arcane Absorption",
        text="Give a friendly minion +2/+2 for each spell you've cast this game.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    # ── Conflagration — from BG35_882 Firelands Fugitive ───────────────
    register_card(
        card_id="BG35_910",
        name="Conflagration",
        text="Deal 2 damage to all enemy minions.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Bounty Spells — "Get a random Bounty" (5 standard + 1 forest)
    # ═══════════════════════════════════════════════════════════════════════

    register_card(
        card_id="BG33_814",
        name="Friendly Bounty",
        text="Give a friendly minion +3/+3.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    register_card(
        card_id="BG33_811",
        name="Healthy Bounty",
        text="Give a friendly minion +4 Health.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    register_card(
        card_id="BG33_812",
        name="Hostile Bounty",
        text="Give a friendly minion +2/+2 and Taunt.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    register_card(
        card_id="BG33_813",
        name="Selfish Bounty",
        text="Give this minion +5/+5.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    register_card(
        card_id="BG33_815",
        name="Wealthy Bounty",
        text="Give a friendly minion +2/+2. Gain 1 Gold.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
    )

    register_card(
        card_id="BG31_886",
        name="Forest's Bounty",
        text="Give a friendly minion +1/+1 for each friendly minion type.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=4,
        tags={},
        script_class=_ForestBountyScript,
    )

    # ── Satellite — Magnetic token for Moonsteel Juggernaut ────────────
    register_card(
        card_id="BG31_171t",
        name="Satellite",
        text="<b>Magnetic</b>",
        cardtype=CardType.MINION,
        race=Race.MECH,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
            GameTag.MAGNETIC: True,
        },
    )

    # ── Crab Mount — Spellcraft spell token for Surf n' Surf ───────────
    register_card(
        card_id="BG27_004t",
        name="Crab Mount",
        text="Give a minion 'Deathrattle: Summon a 3/2 Crab' until next turn.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
        script_class=CrabMountScript,
    )

    # ── Crab — Token summoned by Crab Mount's deathrattle ───────────────
    register_card(
        card_id="BG27_004t2",
        name="Crab",
        text="",
        cardtype=CardType.MINION,
        race=Race.BEAST,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 3,
            GameTag.BASE_HEALTH: 2,
        },
    )

    # ── Siren's Song — Spellcraft spell token for Sea Witch Zar'jira ─────
    register_card(
        card_id="BG27_514t",
        name="Siren's Song",
        text="Choose a different minion in the Tavern to get a copy of.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
        script_class=SirensSongScript,
    )

    # ── Murloc token (1/1) — summoned by Murloc King hero power ───────────
    register_card(
        card_id="TOKEN_MURLOC_1_1",
        name="Murloc Scout",
        text="",
        cardtype=CardType.MINION,
        race=Race.MURLOC,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
        },
    )

    # ── Brann Bronzebeard — reward for Battle Brand hero power ──────────
    register_card(
        card_id="TB_BaconUps_045",
        name="Brann Bronzebeard",
        text="Your Battlecries trigger twice.",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=5,
        tags={
            GameTag.BASE_ATK: 2,
            GameTag.BASE_HEALTH: 4,
        },
    )

    # ── Battlecruiser (Raynor token) — summoned by trinkets ─────────────
    register_card(
        card_id="BG31_HERO_801pt",
        name="Battlecruiser",
        text="",
        cardtype=CardType.MINION,
        race=Race.MECH,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 2,
            GameTag.BASE_HEALTH: 2,
        },
    )

    # ── Stone Elemental (Chenvaala Earth Invocation) — 1/1 token ──────
    register_card(
        card_id="BG22_HERO_001p_t1et",
        name="Stone Elemental",
        text="",
        cardtype=CardType.MINION,
        race=Race.ELEMENTAL,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
        },
    )

    # ── Duo token cards referenced by trinkets ────────────────────────
    register_card(
        card_id="BGDUO_113",
        name="Portal in a Bottle",
        text="",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
    )

    register_card(
        card_id="BGDUO_119",
        name="Orc-estra Conductor",
        text="",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 4,
            GameTag.BASE_HEALTH: 4,
        },
    )

    # ── Might of Stormwind (spell, trinket token: BG35_MagicItem_925) ──
    register_card(
        card_id="BG35_951",
        name="Might of Stormwind",
        text="Give a friendly minion +2/+2 for each friendly minion of its type.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
    )

    # ── Soul Juggler (trinket token: BG32_MagicItem_920) ───────────────
    register_card(
        card_id="BGS_002",
        name="Soul Juggler",
        text="After a friendly Demon dies, deal 3 damage to a random enemy.",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=3,
        tags={
            GameTag.BASE_ATK: 3,
            GameTag.BASE_HEALTH: 5,
        },
    )

    # ── Slumber Sorcerer (trinket token: BG32_MagicItem_933) ───────────
    register_card(
        card_id="BG32_833",
        name="Slumber Sorcerer",
        text="Spellcraft: Give a friendly minion 'Deathrattle: Summon a 4/4 Beast.'",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=4,
        tags={
            GameTag.BASE_ATK: 5,
            GameTag.BASE_HEALTH: 4,
            GameTag.SPELLCRAFT: True,
        },
    )

    # ── Howler Driver (trinket token: BG30_MagicItem_402) ───────────────
    register_card(
        card_id="BG30_402",
        name="Howler Driver",
        text="",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 5,
            GameTag.BASE_HEALTH: 5,
        },
    )

    # ── False Implicator (trinket token: BG32_MagicItem_824) ────────────
    register_card(
        card_id="BG29_140",
        name="False Implicator",
        text="Battlecry: Eat a minion in the Tavern.",
        cardtype=CardType.MINION,
        race=Race.DEMON,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# Token Script Classes
    # ── Shifter Zerus (trinket token: BG24_Reward_362) ────────────────
    register_card(
        card_id="BGS_029",
        name="Shifter Zerus",
        text="Each turn this is in your hand, transform into a random minion.",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 1,
            GameTag.BASE_HEALTH: 1,
        },
    )

    # ── Accelerator (trinket token: BG27_Reward_504) ──────────────────
    register_card(
        card_id="BG27_Reward_504t",
        name="Accelerator",
        text="Transform a minion into one of the next higher Tier.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
    )

    # ── Spare Part (trinket token: BG24_Reward_715) ───────────────────
    register_card(
        card_id="SPARE_PART",
        name="Spare Part",
        text="Give a minion +5/+5 and a random bonus effect.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
        script_class=_SparePartScript,
    )

    # ── Temp Golden Spell (Spellcraft token: BG24_Reward_719) ──────────
    register_card(
        card_id="SC_TEMP_GOLDEN",
        name="Temporary Golden Touch",
        text="Make a friendly minion Golden until next turn.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={GameTag.SPELLCRAFT_SPELL: True},
        script_class=None,  # Effect handled by engine via GOLDEN tag
    )


    # ── Copy Non-Golden Spell (Spellcraft token: BG24_Reward_718) ─────
    register_card(
        card_id="SC_COPY_NONGOLDEN",
        name="Copy Non-Golden",
        text="Choose a non-golden card. Move it to your hand.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={GameTag.SPELLCRAFT_SPELL: True},
        script_class=None,
    )

    # ── Windfall Tornado (trinket token) ──────────────────────────────
    register_card(
        card_id="BG31_817",
        name="Windfall Tornado",
        text="",
        cardtype=CardType.MINION,
        race=Race.ELEMENTAL,
        tech_level=1,
        tags={
            GameTag.BASE_ATK: 4,
            GameTag.BASE_HEALTH: 4,
        },
    )

    # ── Windfury+DS Spell (Spellcraft token: BG33_Reward_006) ─────────
    register_card(
        card_id="SC_WINDFURY_DS",
        name="Windfury + Divine Shield",
        text="Give a friendly minion Windfury and Divine Shield.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={GameTag.SPELLCRAFT_SPELL: True},
        script_class=_WindfuryDSScript,
    )

    # ── Protoss minions (Warp Gate hero power - Artanis) ────────────────
    register_card(
        card_id="BG31_HERO_802pt",
        name="Colossus",
        text="",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=5,
        tags={GameTag.BASE_ATK: 6, GameTag.BASE_HEALTH: 12},
    )
    register_card(
        card_id="BG31_HERO_802pt1",
        name="Carrier",
        text="Avenge (1): Get an Interceptor.",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=5,
        tags={GameTag.BASE_ATK: 4, GameTag.BASE_HEALTH: 12},
    )
    register_card(
        card_id="BG31_HERO_802pt4",
        name="Immortal",
        text="",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=5,
        tags={GameTag.BASE_ATK: 8, GameTag.BASE_HEALTH: 8},
    )
    register_card(
        card_id="BG31_HERO_802pt5",
        name="Void Ray",
        text="Divine Shield",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=5,
        tags={GameTag.BASE_ATK: 7, GameTag.BASE_HEALTH: 1,
              GameTag.DIVINE_SHIELD: True},
    )
    register_card(
        card_id="BG31_HERO_802pt7",
        name="Mothership",
        text="Avenge (1): Get a random Protoss minion.",
        cardtype=CardType.MINION,
        race=Race.INVALID,
        tech_level=5,
        tags={GameTag.BASE_ATK: 6, GameTag.BASE_HEALTH: 8},
    )


def _register_all_buddies():
    """Register all hero buddy minion cards from bg_cards.json."""
    import json, os
    _data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    with open(os.path.join(_data_dir, "bg_cards.json")) as f:
        cards = json.load(f)

    registered = 0
    for c in cards:
        cid = c.get('id', '')
        if '_Buddy' not in cid:
            continue
        # Skip enchantments, spells, tokens — only register minions (type=4)
        if c.get('card_type') != 4:
            continue
        name = c.get('name', cid)
        atk = c.get('atk', 3) or 3
        hp = c.get('health', 3) or 3
        race_val = c.get('card_race', 0)
        try:
            from hsrl.core.enums import DBF_RACE_TO_ENUM
            race = DBF_RACE_TO_ENUM.get(race_val, Race.NONE)
        except ValueError:
            race = Race.INVALID

        register_card(
            card_id=cid,
            name=name,
            text="",
            cardtype=CardType.MINION,
            race=race,
            tech_level=1,
            tags={
                GameTag.BASE_ATK: atk,
                GameTag.BASE_HEALTH: hp,
            },
        )
        registered += 1

    # Also register the golden versions
    for c in cards:
        cid = c.get('id', '')
        if '_Buddy_G' not in cid and not cid.endswith('Buddy_G'):
            # Check for golden suffix pattern
            if not cid.endswith('_G'):
                continue
            if '_Buddy' not in cid.replace('_G', ''):
                continue
        else:
            pass  # Already matches _Buddy_G pattern
        if c.get('card_type') != 4:
            continue
        name = c.get('name', cid)
        atk = c.get('atk', 6) or 6
        hp = c.get('health', 6) or 6
        race_val = c.get('card_race', 0)
        try:
            from hsrl.core.enums import DBF_RACE_TO_ENUM
            race = DBF_RACE_TO_ENUM.get(race_val, Race.NONE)
        except ValueError:
            race = Race.INVALID

        register_card(
            card_id=cid,
            name=name,
            text="",
            cardtype=CardType.MINION,
            race=race,
            tech_level=1,
            tags={
                GameTag.BASE_ATK: atk,
                GameTag.BASE_HEALTH: hp,
                GameTag.GOLDEN: True,
            },
        )
        registered += 1
    return registered


_register_all_buddies()


# ═══════════════════════════════════════════════════════════════════════
# Token Script Classes
# ═══════════════════════════════════════════════════════════════════════


class LanternLightScript:
    """Spell: Give a minion stats equal to your Tavern Tier (player-chosen during recruit, random in combat)."""

    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import Buff, TargetedAction

        def filter_fn():
            board = source.controller.get_board_minions()
            return [m for m in board if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            tier = source.controller.tavern_tier
            return Buff(target, atk=tier, health=tier)

        return TargetedAction(filter_fn, action_factory,
                              label="Lantern Light — stats equal to Tier")


class CrabMountScript:
    """Spell: Give a friendly minion 'Deathrattle: Summon a 3/2 Crab' until next turn (player-chosen during recruit, random in combat)."""

    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import GainSpecificDeathrattle, TargetedAction
        from hsrl.core.enums import GameTag

        def filter_fn():
            return [m for m in source.controller.get_board_minions() if not m.dead]

        if not filter_fn():
            return None

        def action_factory(target):
            target.set_tag(GameTag.TEMPORARY_DEATHRATTLE, True)
            return GainSpecificDeathrattle(target, "BG27_004t2")

        return TargetedAction(filter_fn, action_factory,
                              label="Crab Mount — Deathrattle: Summon a 3/2 Crab")


class SirensSongScript:
    """Spell: Copy a random minion from the Tavern to your hand."""

    @staticmethod
    def on_play(source, game):
        from hsrl.core.actions import CopyTavernMinion
        return CopyTavernMinion(source.controller)


def _register_lantern_light():
    """Register Lantern Light with its script class (call after register_all_tokens)."""
    register_card(
        card_id="LANTERN_LIGHT",
        name="Lantern Light",
        text="Give a minion stats equal to your Tier.",
        cardtype=CardType.SPELL,
        race=Race.INVALID,
        tech_level=1,
        tags={},
        script_class=LanternLightScript,
    )


# Auto-register on import
register_all_tokens()
_register_lantern_light()
