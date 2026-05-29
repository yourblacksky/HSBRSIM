"""
HSRL - Hearthstone Battlegrounds Reinforcement Learning Environment
Core Enumerations

All visible properties in Hearthstone Battlegrounds are predefined here.
Philosophy: Every tag, state, and attribute that a player can see must be
explicitly declared in this module before use.
"""

from enum import IntEnum, auto


class GameTag(IntEnum):
    """Predefined game tags for all visible entity properties."""

    # ── Identity ──
    CARD_ID = 1                     # String card identifier (e.g. "BGS_001")
    ENTITY_ID = 2                   # Unique runtime entity id
    NAME = 3                        # Display name
    TEXT = 4                        # Card text / description
    ARTIST = 5                      # Artist name (cosmetic)
    FLAVOR = 6                      # Flavor text (cosmetic)

    # ── Card Type ──
    CARDTYPE = 10                   # MINION, HERO, SPELL, etc.
    CLASS = 11                      # Hero class (mostly cosmetic in BG)
    RARITY = 12                     # Common, Rare, Epic, Legendary
    RACE = 13                       # Beast, Demon, Dragon, Elemental, Mech,
                                    # Murloc, Naga, Pirate, Quilboar, Undead,
                                    # All, None
    TECH_LEVEL = 14                 # Tavern tier (1-7)

    # ── Combat Stats ──
    ATK = 20                        # Current attack
    HEALTH = 21                     # Current health
    MAX_HEALTH = 22                 # Maximum health
    DAMAGE = 23                     # Damage taken (MAX_HEALTH - HEALTH)
    ARMOR = 24                      # Armor (for heroes)
    BASE_ATK = 25                   # Printed attack (before buffs)
    BASE_HEALTH = 26                # Printed health (before buffs)

    # ── Cost & Economy ──
    COST = 30                       # Gold cost (minions = 3, spells vary)
    TAVERN_UPGRADE_COST = 31        # Current cost to upgrade tavern
    GOLD = 32                       # Player's current gold
    MAX_GOLD = 33                   # Maximum gold (usually 99)

    # ── Zones ──
    ZONE = 40                       # Current zone
    ZONE_POSITION = 41              # Position within zone (0-based, left-to-right)
    CONTROLLER = 42                 # Entity id of controlling player

    # ── Keywords (Boolean) ──
    TAUNT = 50                      # Must be attacked first
    DIVINE_SHIELD = 51              # Blocks first damage instance
    POISONOUS = 52                  # Kill any minion damaged by this
    VENOMOUS = 53                   # Kill target if this survives combat
    REBORN = 54                     # Resummon with 1 health on death
    WINDFURY = 55                   # Attack twice per turn
    MEGA_WINDFURY = 56              # Attack four times (deprecated but present)
    CLEAVE = 57                     # Also damage adjacent minions
    MAGNETIC = 58                   # Can attach to friendly Mech
    BLOOD_GEM = 59                  # Interacts with Blood Gem mechanic
    DEATHRATTLE = 60                # Has a deathrattle effect
    BATTLECRY = 61                  # Has a battlecry effect
    Avenge = 62                     # Has an Avenge(X) trigger
    SPELLCRAFT = 63                 # Has Spellcraft mechanic
    START_OF_COMBAT = 64            # Has Start of Combat effect
    RALLY = 65                      # Has Rally mechanic
    CHARGE = 66                     # Can attack immediately (rare in BG)
    FODDER = 67                     # Demon: consumes a minion for power (Season 13)
    CHROMADRAKE = 68                # Dragon: transforms/evolves (Season 13)
    END_OF_TURN = 130               # Has an end-of-turn effect
    START_OF_TURN = 131             # Has a start-of-turn effect
    ON_SELL = 132                   # Has a "when you sell this" effect
    SPELLCRAFT_SPELL = 133          # Mark a card as a Spellcraft-generated temporary spell
    COMBAT_SUMMON = 134             # Summoned from hand for this combat only
    IMPROVE_COUNTER = 135           # "Improves after X" permanent counter
    GOLD_SPENT_THIS_TURN = 136      # Total gold spent this turn
    TAVERN_SPELLS_CAST_THIS_TURN = 137  # Total tavern spells cast this turn
    NEXT_SPELL_COST_REDUCTION = 138  # Discount on next purchased tavern spell
    FODDER_REFRESH_REMAINING = 139  # Laboratory Assistant: remaining refreshes for Fodder grant
    BATTLECRY_DOUBLED = 140         # Brann aura: battlecries trigger twice
    END_OF_TURN_DOUBLED = 141       # Drakkari aura: end-of-turn effects trigger twice
    CTHUN_BUFF_COUNT = 142          # C'Thun hero power: upgrade counter for Saturday C'Thuns!
    FREE_REFRESH_REMAINING = 143    # Number of free refreshes remaining
    ILTA_ACTIVE = 147               # "I'll Take That!" hero power active for next combat
    DIG_COUNTER = 145               # Buried Treasure: digs remaining before golden reward
    RAT_KING_TYPE = 146             # Rat King: current "King of X" tribe for A Tale of Kings
    RUNIC_BUFF_BONUS = 151          # Runic Empowerment: accumulated buff bonus
    RUNIC_DEATH_COUNT = 152         # Runic Empowerment: deaths remaining before upgrade
    TURNS_IN_HAND = 153             # Number of turns this minion has been in hand
    LAST_SPELL_CARD_ID = 154        # Card id of the last tavern spell played this turn
    CARDS_PLAYED_THIS_TURN = 155    # Number of minions played from hand this turn
    START_OF_COMBAT_DOUBLED = 156   # Player tag: SoC effects trigger an extra time
    TRINKET_COUNTER = 157            # Per-trinket counter for "After you X N times"
    TRINKET_COUNTER_TARGET = 158     # Target value for trinket counter (N in "After N times")

    # ── State Flags ──
    GOLDEN = 70                     # Is a golden (triple) minion
    FROZEN = 71                     # Bob's tavern minions are frozen
    EXHAUSTED = 72                  # Has already acted this turn
    DEAD = 73                       # Marked for death / already dead
    SILENCED = 74                   # Silenced (mechanics disabled)
    DORMANT = 75                    # Dormant (not active)
    TEMPORARY_DEATHRATTLE = 76      # Has a temporary deathrattle (cleared at turn end)

    # ── Counter / Progress ──
    AVENGE_COUNTER = 80             # Current Avenge death count
    AVENGE_TARGET = 81              # X in "Avenge(X)"
    REBORN_USED = 82                # Reborn has already triggered
    DIVINE_SHIELD_INTACT = 83       # Shield has not been popped
    WINDFURY_ATTACKS = 84           # Number of attacks made this combat
    KILLER = 85                     # Entity id of the minion that killed this one
    SAVED_MINION_ID = 86            # Card id stored for later reference (Stitched Salvager)
    MRRGLTON_COUNT = 87             # Times a Mrrglton has been played this game (deprecated)
    MAMA_MRRGLTON_COUNT = 88       # Times Mama Mrrglton has been played this game
    PAPA_MRRGLTON_COUNT = 89       # Times Papa Mrrglton has been played this game

    # ── Game State ──
    TURN = 90                       # Current turn number (1, 2, 3...)
    STEP = 91                       # RECRUIT or COMBAT
    STATE = 92                      # RUNNING, COMPLETE
    PLAYSTATE = 93                  # PLAYING, WON, LOST, TIED
    HEALTH_CAP = 94                 # Damage cap for this turn (5/10/15/none)

    # ── Mechanic-Specific Scale ──
    PLAGUERUNNER_SCALE = 122        # Plaguerunner X value (starts at 3, increments on trigger)

    # ── Hero Power ──
    HERO_POWER = 100                # Hero power card id
    HERO_POWER_USED = 101           # Hero power used this turn
    HERO_POWER_COST = 102           # Gold cost of hero power
    HERO_POWER_EXTRA_USES = 103     # Extra hero power uses available this turn

    # ── Tavern ──
    TAVERN_TIER = 110               # Player's current tavern tier (1-7)
    TRIPLE_REWARD_TIER = 111        # Tier of next triple reward discover

    # ── Mechanic Bonuses ──
    BLOOD_GEM_BONUS_ATK = 120       # Extra Attack granted by Blood Gems this game
    BLOOD_GEM_BONUS_HEALTH = 121    # Extra Health granted by Blood Gems this game
    BALLER_FIRE_BONUS = 144         # Fire Baller: accumulated Attack bonus for future Ballers
    BALLER_SNOW_BONUS = 150         # Snow Baller: accumulated Health bonus for future Ballers
    TAVERN_SPELL_ATK_BONUS = 148    # Extra Attack applied by Tavern spell casts this game
    ELEMENTAL_STAT_BONUS_ATK = 151  # Extra Attack from elemental stat buffs this game
    ELEMENTAL_STAT_BONUS_HEALTH = 152  # Extra Health from elemental stat buffs this game
    PERMANENT_SPELLCRAFT = 153      # Minion's spellcraft spell does not expire after use
    BUY_EXTRA_COPIES = 199          # Extra copies granted on next minion purchases
    TRINKET_TIER = 200              # Tier tracker for trinket improvement (Marine Signet)
    NEXT_PURCHASE_GOLDEN = 201      # Next N purchases become golden (Gold-plated Compass)
    TAVERN_SPELL_HEALTH_BONUS = 149 # Extra Health applied by Tavern spell casts this game

    # ── Trinket / Quest / Anomaly ──
    TRINKET_1 = 202                # First trinket slot (Lesser, Turn 6)
    TRINKET_2 = 203                # Second trinket slot (Greater, Turn 9)
    TRINKET_OFFERED = 204          # Trinkets have been offered this turn
    QUEST_PROGRESS = 205            # Current progress toward quest completion
    TRIPLE_REWARD_IS_PRIZE = 206    # Corrupted Tome: triple rewards use DiscoverPrize
    IMPLICATOR_CONSUME_HIGHEST = 207  # Implicator Portrait: demons eat highest-health
    NEXT_BATTLECRY_DOUBLED = 208    # Varden: next battlecry triggers twice
    MAIEV_DORMANT = 209             # Maiev: minion is in dormant stasis
    MAIEV_DORMANT_TURNS = 210       # Maiev: turns remaining in dormant
    QUEST_TARGET = 160              # Target value needed to complete quest
    QUEST_ACTIVE = 161              # Whether a quest is currently active
    REWARD_UNLOCKED = 162           # Whether quest reward has been unlocked
    ACTIVE_ANOMALY = 163            # Currently active anomaly id
    FIRST_MINION_FREE = 164          # First minion bought each turn is free
    ANOMALY_MINION_HEALTH_BONUS = 165  # Bonus health from anomaly (Prudence of Amitus)
    AUTOMATON_COUNT = 166             # Ancestral Automaton: total summoned this game
    ETERNAL_KNIGHT_DEATHS = 167       # Eternal Knight: total deaths this game
    COMBAT_DEATH_COUNT = 168           # Rot Hide Gnoll: minion deaths this combat
    DEATHRATTLE_TRIGGERED = 169       # Falling Sky Golem: deathrattles triggered
    DEATHRATTLE_DOUBLED = 170         # Titus Rivendare: deathrattles trigger twice
    TAVERN_SPELLS_CAST_THIS_GAME = 171  # Total tavern spells cast this game
    PIGGY_BANK_COUNTER = 172         # Piggy Bank: current gold value (increments each turn)
    PIRATES_NEED_2_COPIES = 173     # Designer Eyepatch: pirates only need 2 copies for golden
    SPELLCRAFT_EXTRA_CASTS = 174    # Spitescale Sushi Roll: extra spellcraft casts this turn
    MAGNETIC_COST_OVERRIDE = 175    # Electrode Attractor: override magnetic mech cost
    ARTANIS_COPY_TARGET = 176       # Artanis Sticker: card_id to copy on summon
    GUIDING_CANDLE_REFRESHES = 177  # Guiding Candle: remaining refreshes that only show tier 6
    HEALTH_COST_DEMON = 178        # Pilgrimp Sticker: one demon per turn buyable with health
    HEALTH_COST_SPELL = 179        # Bazaar Sticker: one spell per turn buyable with health
    COMBAT_PERSIST_DRAGONS = 180   # Tarecgosa Sticker: left/right dragons keep combat stats
    RALLY_DOUBLED = 181            # Rally effects trigger an extra time
    TAUGHT_SPELL_ID = 182          # Murloc teach: spell card_id stored on minion
    DIE_AFTER_ATTACK = 183         # Minions die after attacking (+7/+7 volatile venom)
    TIER_7_UNLOCKED = 184          # Tier 7 upgrade is available
    TRINKET_SCHEDULED = 185        # Next turn: offer trinket
    TIME_MARKS = 186               # Temporal Twist: time marks available
    TWIST_GREATER_COUNT = 187      # How many golden minions greater twist provides
    TRINKET_SCHEDULED_TYPE = 188   # "lesser" or "greater" for scheduled trinket offer
    DISCOVER_SECOND_HP = 189       # Discover second hero power anomaly active
    TRINKETS_ENABLED = 190         # Trinkets game mode active
    QUESTS_ENABLED = 191           # Quests game mode active
    BUDDIES_ENABLED = 192          # Buddies game mode active
    ALL_MINIONS_GOLDEN = 193       # All minions are golden (anomaly flag)
    TAVERN_MINION_COST_OVERRIDE = 194  # Override minion cost in tavern
    HERO_POWER_DOUBLED = 195       # Hero power triggers twice
    TRINKET_1_TURN = 196           # Turn for first trinket offer
    TRINKET_2_TURN = 197           # Turn for second trinket offer
    BLOOD_GEM_COUNT = 198          # Per-minion blood gem tracker


class CardType(IntEnum):
    """Types of cards in Battlegrounds."""
    INVALID = 0
    MINION = 1
    HERO = 2
    SPELL = 3
    HERO_POWER = 4
    REWARD = 5          # Triple reward / quest reward
    TRINKET = 6         # Trinket item
    BLOOD_GEM_CARD = 7  # Blood Gem spell token
    ANOMALY = 8         # Anomaly (game-wide modifier)
    QUEST = 9           # Quest card (objectives)


class Race(IntEnum):
    """Minion tribes / races in Battlegrounds."""
    INVALID = 0
    BEAST = 1
    DEMON = 2
    DRAGON = 3
    ELEMENTAL = 4
    MECH = 5
    MURLOC = 6
    NAGA = 7
    PIRATE = 8
    QUILBOAR = 9
    UNDEAD = 10
    ALL = 11            # "All" type minions
    NONE = 12           # No tribe


# Mapping from Hearthstone DBF (CardDefs.xml) race IDs to our Race enum.
# DBF uses different numeric codes than our enum — this map MUST be used
# whenever reading card_race values from data files.
DBF_RACE_TO_ENUM = {
    None: Race.NONE,
    11: Race.UNDEAD,
    14: Race.MURLOC,
    15: Race.DEMON,
    17: Race.MECH,
    18: Race.ELEMENTAL,
    20: Race.BEAST,
    23: Race.PIRATE,
    24: Race.DRAGON,
    26: Race.ALL,
    43: Race.QUILBOAR,
    92: Race.NAGA,
}


class Zone(IntEnum):
    """Zones an entity can exist in."""
    INVALID = 0
    PLAY = 1            # On the board (combat or recruit)
    HAND = 2            # In hand
    DECK = 3            # In deck (rarely used in BG)
    GRAVEYARD = 4       # Dead minions
    SETASIDE = 5        # Set aside (triple combining, discover)
    REMOVED = 6         # Removed from game
    TAVERN = 7          # Bob's tavern offerings
    SECRET = 8          # Secret zone (rare in BG)


class Step(IntEnum):
    """Game phase steps."""
    INVALID = 0
    BEGIN_RECRUIT = 1
    RECRUIT = 2
    END_RECRUIT = 3
    BEGIN_COMBAT = 4
    COMBAT = 5
    END_COMBAT = 6


class State(IntEnum):
    """Overall game state."""
    INVALID = 0
    RUNNING = 1
    COMPLETE = 2


class PlayState(IntEnum):
    """Player's current standing."""
    INVALID = 0
    PLAYING = 1
    WON = 2
    LOST = 3
    TIED = 4


class Rarity(IntEnum):
    """Card rarity."""
    INVALID = 0
    COMMON = 1
    RARE = 2
    EPIC = 3
    LEGENDARY = 4


# ── Convenience keyword sets ──
KEYWORD_TAGS = {
    GameTag.TAUNT,
    GameTag.DIVINE_SHIELD,
    GameTag.POISONOUS,
    GameTag.VENOMOUS,
    GameTag.REBORN,
    GameTag.WINDFURY,
    GameTag.MEGA_WINDFURY,
    GameTag.CLEAVE,
    GameTag.MAGNETIC,
    GameTag.BLOOD_GEM,
    GameTag.DEATHRATTLE,
    GameTag.BATTLECRY,
    GameTag.Avenge,
    GameTag.SPELLCRAFT,
    GameTag.START_OF_COMBAT,
    GameTag.RALLY,
    GameTag.CHARGE,
    GameTag.FODDER,
    GameTag.CHROMADRAKE,
    GameTag.END_OF_TURN,
    GameTag.START_OF_TURN,
    GameTag.ON_SELL,
}

STAT_TAGS = {
    GameTag.ATK,
    GameTag.HEALTH,
    GameTag.MAX_HEALTH,
    GameTag.DAMAGE,
    GameTag.BASE_ATK,
    GameTag.BASE_HEALTH,
}
