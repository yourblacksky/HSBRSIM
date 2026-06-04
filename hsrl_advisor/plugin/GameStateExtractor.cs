using System;
using System.Collections.Generic;
using System.Linq;
using HearthDb.Enums;
using Hearthstone_Deck_Tracker.API;
using Hearthstone_Deck_Tracker.Enums;
using Hearthstone_Deck_Tracker.Hearthstone;
using Hearthstone_Deck_Tracker.Hearthstone.Entities;

namespace HrSRLAdviser
{
    /// <summary>
    /// Extracts Battlegrounds game state from HDT into JSON-serializable
    /// objects matching hsrl/advisor/overlay_protocol.py.
    /// </summary>
    public class GameStateExtractor
    {
        private const int MaxTavernSlots = 7;
        private const int MaxHandSlots = 10;
        private const int MaxBoardSlots = 7;

        /// <summary>BGs minions with cleave, by card ID. HearthDb does not expose
        /// a CLEAVE GameTag, so we check against this list (same approach as
        /// HDT's BobsBuddy MinionFactory.cardIDsWithCleave).</summary>
        private static readonly HashSet<string> CleaveCardIds = new HashSet<string>
        {
            "BGS_022", // Foe Reaper 4000
            "BG21_046", // Wildfire Elemental
            "BG24_306", // Recurring Nightmare (cleave)
            "BG25_022", // Holorover
            "BG26_158", // Meteor Crasher
            "BG27_029", // Gnomelia, Polarity Ace
        };
        private const int MaxTrinketSlots = 2;
        private const int MaxOpponents = 7;

        /// <summary>
        /// Extract current Battlegrounds game state. Returns null if not in a BG game.
        /// </summary>
        private bool _loggedExtractSkip;
        private string _lastExtractSkipReason;

        private void LogSkip(string reason)
        {
            if (_lastExtractSkipReason == reason) return; // avoid spam
            _lastExtractSkipReason = reason;
            _loggedExtractSkip = true;
            AdviserPlugin.Log("Extract skip: " + reason);
        }

        public GameStateData Extract(string gameId)
        {
            var game = Core.Game;
            if (game == null)
            {
                LogSkip("Core.Game is null");
                return null;
            }
            if (!game.IsRunning)
            {
                LogSkip("game not running");
                return null;
            }
            // Use IsBattlegroundsMatch which checks CurrentGameType rather
            // than CurrentGameStats.GameMode (the latter is often still None
            // when the game start event fires).
            if (!game.IsBattlegroundsMatch)
            {
                LogSkip("not Battlegrounds match");
                return null;
            }

            // Only log when transition from skip to success
            if (_loggedExtractSkip)
            {
                AdviserPlugin.Log("Extract now succeeding (was: " +
                    _lastExtractSkipReason + ")");
                _loggedExtractSkip = false;
            }

            int playerId = game.Player.Id;
            bool inCombat = game.IsBattlegroundsCombatPhase;

            // Player state
            var playerState = ExtractPlayerState(game, playerId);

            // Entity collections
            var hand = ExtractHand(game, playerId);
            var board = ExtractBoard(game, playerId);
            var tavern = ExtractTavern(game, playerId);
            var trinkets = ExtractTrinkets(game, playerId);

            // Opponents (limited info during recruit)
            var opponents = ExtractOpponents(game, playerId);

            // Alive count
            int aliveCount = 1 + opponents.Count(o => o.alive);

            // Damage cap
            int? damageCap = opponents.Any(o => !o.alive) ? (int?)null : 15;

            // Turn number
            int turn = GetTurnNumber(game);

            return new GameStateData
            {
                type = "game_state",
                game_id = gameId,
                turn = turn,
                phase = inCombat ? "combat" : "recruit",
                player = playerState,
                tavern = tavern,
                hand = hand,
                board = board,
                trinkets = trinkets,
                opponents = opponents,
                alive_count = aliveCount,
                damage_cap = damageCap,
                anomaly_card_id = GetAnomalyCardId(game),
            };
        }

        /// <summary>
        /// Determine player's final placement (1-8) at game end.
        /// </summary>
        public int GetPlacement()
        {
            var game = Core.Game;
            if (game == null) return 8;

            int playerId = game.Player.Id;
            var playerEnt = GetEntityByPlayerId(game, playerId);
            int playerHp = playerEnt?.GetTag(GameTag.HEALTH) ?? 0;
            int playerAlive = playerHp > 0 ? 1 : 0;

            int rank = 1;
            foreach (var opponent in GetPlayerEntities(game))
            {
                int opId = opponent.GetTag(GameTag.PLAYER_ID);
                if (opId == playerId) continue;

                int opHp = opponent.GetTag(GameTag.HEALTH);
                int opAlive = opHp > 0 ? 1 : 0;

                // Lower placement beats higher placement
                // Alive beats dead; among alive, higher HP is better
                if (opAlive > playerAlive ||
                    (opAlive == playerAlive && opHp > playerHp))
                    rank++;
            }

            return Math.Min(rank, 8);
        }

        // ── Player state ─────────────────────────────────────────────────

        private PlayerState ExtractPlayerState(GameV2 game, int playerId)
        {
            var ent = GetEntityByPlayerId(game, playerId);
            if (ent == null)
                return new PlayerState();

            int hp = ent.GetTag(GameTag.HEALTH);
            int armor = ent.GetTag(GameTag.ARMOR);

            int resources = ent.GetTag(GameTag.RESOURCES);
            int tempResources = ent.GetTag(GameTag.TEMP_RESOURCES);
            int resourcesUsed = ent.GetTag(GameTag.RESOURCES_USED);
            int gold = resources + tempResources - resourcesUsed;
            gold = Math.Max(0, gold);

            // Fallback: try reading gold from the game entity (BG may store it there)
            if (gold == 0)
            {
                var gameEnt = game.Entities.Values.FirstOrDefault(
                    e => e.GetTag(GameTag.CARDTYPE) == (int)CardType.GAME);
                if (gameEnt != null)
                {
                    int gameResources = gameEnt.GetTag(GameTag.RESOURCES);
                    int gameTemp = gameEnt.GetTag(GameTag.TEMP_RESOURCES);
                    int gameUsed = gameEnt.GetTag(GameTag.RESOURCES_USED);
                    gold = gameResources + gameTemp - gameUsed;
                    gold = Math.Max(0, gold);
                }
            }

            // Hero entity (hero power card)
            int heroEntityId = ent.GetTag(GameTag.HERO_ENTITY);
            string heroCardId = "";
            int hpCost = 2;
            if (heroEntityId > 0 && game.Entities.TryGetValue(heroEntityId, out var heroEnt))
            {
                heroCardId = heroEnt.CardId ?? "";
                hpCost = heroEnt.GetTag(GameTag.COST);
            }

            int tavernTier = ent.GetTag(GameTag.PLAYER_TECH_LEVEL);
            // HSRL engine base costs: {2:5, 3:7, 4:8, 5:9, 6:10, 7:11}
            // Try reading real tag first; fallback to lookup table.
            int upgradeCost = ent.GetTag((GameTag)189);  // TAVERN_UPGRADE_COST
            if (upgradeCost == 0)
                upgradeCost = tavernTier switch { 1 => 5, 2 => 7, 3 => 8, 4 => 9, 5 => 10, _ => 11 };

            bool hpUsed = ent.GetTag(GameTag.EXHAUSTED) > 0;

            // More reliable: check the hero power entity itself (BobsBuddy approach)
            var hpEntity = game.Entities.Values.FirstOrDefault(e =>
                e.GetTag(GameTag.CONTROLLER) == playerId &&
                e.GetTag(GameTag.CARDTYPE) == (int)CardType.HERO_POWER);
            if (hpEntity != null)
            {
                hpUsed = hpEntity.GetTag(GameTag.EXHAUSTED) > 0
                      || hpEntity.GetTag(GameTag.BACON_HERO_POWER_ACTIVATED) > 0;
            }
            int extraHpEntityId = ent.GetTag(GameTag.ADDITIONAL_HERO_POWER_ENTITY_1);
            bool hpExtra = extraHpEntityId > 0
                && game.Entities.TryGetValue(extraHpEntityId, out var extraHpEnt)
                && extraHpEnt.GetTag(GameTag.EXHAUSTED) == 0;
            int freeRefreshes = ent.GetTag(GameTag.BACON_FREE_REFRESH_COUNT);

            // P0: read player-level persistent bonuses from their GameTags
            int spellCostReduction = ent.GetTag((GameTag)138);  // NEXT_SPELL_COST_REDUCTION
            int gemAtkBonus = ent.GetTag((GameTag)120);          // BLOOD_GEM_BONUS_ATK
            int gemHealthBonus = ent.GetTag((GameTag)121);       // BLOOD_GEM_BONUS_HEALTH

            // P1: scan hand + board for TRIPLE_REWARD_TIER (111), take max
            int tripleRewardTier = 0;
            foreach (var e in game.Entities.Values.Where(
                e => e.IsControlledBy(playerId)
                  && (e.GetTag(GameTag.ZONE) == (int)Zone.HAND
                   || e.GetTag(GameTag.ZONE) == (int)Zone.PLAY)))
            {
                int t = e.GetTag((GameTag)111);  // TRIPLE_REWARD_TIER
                if (t > tripleRewardTier) tripleRewardTier = t;
            }

            return new PlayerState
            {
                health = hp > 0 ? hp : 40,
                armor = Math.Max(armor, 0),
                gold = gold >= 0 ? gold : 3,
                tavern_tier = Math.Max(tavernTier, 1),
                upgrade_cost = upgradeCost,
                hero_card_id = heroCardId,
                hero_power_used = hpUsed,
                hero_power_cost = hpCost,
                hero_power_extra_uses = hpExtra,
                free_refresh_remaining = Math.Max(freeRefreshes, 0),
                next_spell_cost_reduction = Math.Max(spellCostReduction, 0),
                blood_gem_atk_bonus = Math.Max(gemAtkBonus, 0),
                blood_gem_health_bonus = Math.Max(gemHealthBonus, 0),
                pending_triple_reward_tier = tripleRewardTier,
            };
        }

        // ── Tavern (Bob's shop) ──────────────────────────────────────────

        private TavernSlot[] ExtractTavern(GameV2 game, int playerId)
        {
            var result = new TavernSlot[MaxTavernSlots];
            var entities = GetShopEntities(game, playerId);

            for (int i = 0; i < Math.Min(entities.Count, MaxTavernSlots); i++)
                result[i] = EntityToTavernSlot(entities[i]);

            return result;
        }

        private TavernSlot EntityToTavernSlot(Entity e)
        {
            int cardTypeVal = e.GetTag(GameTag.CARDTYPE);
            bool isMinion = cardTypeVal == (int)CardType.MINION;
            bool isSpell = cardTypeVal == (int)CardType.SPELL
                        || cardTypeVal == (int)CardType.BATTLEGROUND_SPELL;

            return new TavernSlot
            {
                card_id = e.CardId ?? "",
                atk = e.GetTag(GameTag.ATK),
                health = e.GetTag(GameTag.HEALTH),
                tier = e.GetTag(GameTag.TECH_LEVEL),
                cost = e.GetTag(GameTag.COST),
                race = RaceToString(e.GetTag(GameTag.CARDRACE)),
                is_minion = isMinion,
                is_spell = isSpell,
                taunt = e.GetTag(GameTag.TAUNT) > 0,
                divine_shield = e.GetTag(GameTag.DIVINE_SHIELD) > 0,
                poisonous = e.GetTag(GameTag.POISONOUS) > 0,
                reborn = e.GetTag(GameTag.REBORN) > 0,
                frozen = e.GetTag(GameTag.FROZEN) > 0,
            };
        }

        // ── Hand ─────────────────────────────────────────────────────────

        private HandSlot[] ExtractHand(GameV2 game, int playerId)
        {
            var result = new HandSlot[MaxHandSlots];
            var entities = GetZoneEntities(game, playerId, (int)Zone.HAND);

            for (int i = 0; i < Math.Min(entities.Count, MaxHandSlots); i++)
                result[i] = EntityToHandSlot(entities[i]);

            return result;
        }

        private HandSlot EntityToHandSlot(Entity e)
        {
            int cardTypeVal = e.GetTag(GameTag.CARDTYPE);
            bool isMinion = cardTypeVal == (int)CardType.MINION;
            bool isSpell = cardTypeVal == (int)CardType.SPELL
                        || cardTypeVal == (int)CardType.BATTLEGROUND_SPELL;

            return new HandSlot
            {
                card_id = e.CardId ?? "",
                atk = e.GetTag(GameTag.ATK),
                health = e.GetTag(GameTag.HEALTH),
                tier = e.GetTag(GameTag.TECH_LEVEL),
                cost = e.GetTag(GameTag.COST),
                race = RaceToString(e.GetTag(GameTag.CARDRACE)),
                is_minion = isMinion,
                is_spell = isSpell,
                golden = e.GetTag(GameTag.PREMIUM) > 0,
                battlecry = e.GetTag(GameTag.BATTLECRY) > 0,
                turns_in_hand = e.GetTag(GameTag.NUM_TURNS_IN_PLAY),
                spellcraft = e.GetTag(GameTag.SPELLCRAFT) > 0,
            };
        }

        // ── Board ────────────────────────────────────────────────────────

        private BoardSlot[] ExtractBoard(GameV2 game, int playerId)
        {
            var result = new BoardSlot[MaxBoardSlots];
            var entities = GetPlayerBoardMinions(game, playerId);

            for (int i = 0; i < Math.Min(entities.Count, MaxBoardSlots); i++)
                result[i] = EntityToBoardSlot(entities[i]);

            return result;
        }

        private BoardSlot EntityToBoardSlot(Entity e)
        {
            int health = e.GetTag(GameTag.HEALTH);
            int damage = e.GetTag(GameTag.DAMAGE);

            return new BoardSlot
            {
                card_id = e.CardId ?? "",
                atk = e.GetTag(GameTag.ATK),
                health = health,
                max_health = health + damage,
                tier = e.GetTag(GameTag.TECH_LEVEL),
                taunt = e.GetTag(GameTag.TAUNT) > 0,
                divine_shield = e.GetTag(GameTag.DIVINE_SHIELD) > 0,
                divine_shield_intact = e.GetTag(GameTag.DIVINE_SHIELD) > 0,
                poisonous = e.GetTag(GameTag.POISONOUS) > 0,
                venomous = e.GetTag(GameTag.VENOMOUS) > 0,
                reborn = e.GetTag(GameTag.REBORN) > 0,
                windfury = e.GetTag(GameTag.WINDFURY) > 0,
                cleave = CleaveCardIds.Contains(e.CardId ?? ""),
                golden = e.GetTag(GameTag.PREMIUM) > 0,
                race = RaceToString(e.GetTag(GameTag.CARDRACE)),
                exhausted = e.GetTag(GameTag.EXHAUSTED) > 0,
            };
        }

        // ── Trinkets ─────────────────────────────────────────────────────

        private TrinketSlot[] ExtractTrinkets(GameV2 game, int playerId)
        {
            var result = new TrinketSlot[MaxTrinketSlots];
            var entities = game.Entities.Values
                .Where(e => e.GetTag(GameTag.CONTROLLER) == playerId
                         && e.GetTag(GameTag.ZONE) == (int)Zone.SECRET)
                .Take(MaxTrinketSlots)
                .ToList();

            for (int i = 0; i < entities.Count; i++)
            {
                var e = entities[i];
                result[i] = new TrinketSlot
                {
                    card_id = e.CardId ?? "",
                    cost = e.GetTag(GameTag.COST),
                    tier = e.GetTag(GameTag.TECH_LEVEL),
                    has_start_of_combat = e.GetTag(GameTag.TRIGGER_VISUAL) > 0,
                    has_end_of_turn = e.GetTag((GameTag)130) > 0,    // END_OF_TURN
                    has_start_of_turn = e.GetTag((GameTag)131) > 0,  // START_OF_TURN
                };
            }

            return result;
        }

        // ── Opponents ────────────────────────────────────────────────────

        private OpponentSummary[] ExtractOpponents(GameV2 game, int playerId)
        {
            var result = new List<OpponentSummary>();
            var playerEntities = GetPlayerEntities(game);

            foreach (var ent in playerEntities)
            {
                int opId = ent.GetTag(GameTag.PLAYER_ID);
                if (opId == playerId) continue;

                result.Add(new OpponentSummary
                {
                    health = ent.GetTag(GameTag.HEALTH),
                    armor = ent.GetTag(GameTag.ARMOR),
                    tavern_tier = ent.GetTag(GameTag.PLAYER_TECH_LEVEL),
                    board_size = CountPlayerBoardMinions(game, opId),
                    alive = ent.GetTag(GameTag.HEALTH) > 0,
                });

                if (result.Count >= MaxOpponents) break;
            }

            // Pad to exactly 7 opponents
            while (result.Count < MaxOpponents)
                result.Add(new OpponentSummary { health = 40, alive = false });

            return result.ToArray();
        }

        // ── Entity query helpers ─────────────────────────────────────────

        /// <summary>Get the "player entity" (the one with PLAYER_ID tag) for a given ID.</summary>
        private Entity GetEntityByPlayerId(GameV2 game, int playerId)
        {
            return game.Entities.Values
                .FirstOrDefault(e => e.HasTag(GameTag.PLAYER_ID)
                                  && e.GetTag(GameTag.PLAYER_ID) == playerId);
        }

        /// <summary>Get all "player entities" (those with PLAYER_ID tag) in the game.</summary>
        private List<Entity> GetPlayerEntities(GameV2 game)
        {
            return game.Entities.Values
                .Where(e => e.HasTag(GameTag.PLAYER_ID)
                         && e.GetTag(GameTag.PLAYER_ID) > 0)
                .ToList();
        }

        /// <summary>Get entities in a specific zone for a player.</summary>
        private List<Entity> GetZoneEntities(GameV2 game, int playerId, int zone)
        {
            return game.Entities.Values
                .Where(e => e.GetTag(GameTag.CONTROLLER) == playerId
                         && e.GetTag(GameTag.ZONE) == zone)
                .OrderBy(e => e.GetTag(GameTag.ZONE_POSITION))
                .ToList();
        }

        /// <summary>Get player's own board minions — entities in the PLAY zone
        /// with CARDTYPE MINION that do NOT have TECH_LEVEL (shop-only tag).
        /// In HDT 1.52, board minions may lack the CONTROLLER tag during
        /// recruit phase, so we identify them by exclusion from shop.</summary>
        private List<Entity> GetPlayerBoardMinions(GameV2 game, int playerId)
        {
            return game.Entities.Values
                .Where(e => e.HasTag(GameTag.ZONE)
                         && e.GetTag(GameTag.ZONE) == (int)Zone.PLAY
                         && e.HasTag(GameTag.CARDTYPE)
                         && e.GetTag(GameTag.CARDTYPE) == (int)CardType.MINION
                         && !e.HasTag(GameTag.TECH_LEVEL))
                .OrderBy(e => e.GetTag(GameTag.ZONE_POSITION))
                .ToList();
        }

        /// <summary>Get Bob's shop entities — entities with CREATOR and TECH_LEVEL
        /// that are NOT controlled by this player (board minions also have CREATOR
        /// in HDT 1.52, but they ARE controlled by the player).</summary>
        private List<Entity> GetShopEntities(GameV2 game, int playerId)
        {
            return game.Entities.Values
                .Where(e => e.HasTag(GameTag.CREATOR)
                         && e.GetTag(GameTag.ZONE) == (int)Zone.PLAY
                         && e.HasTag(GameTag.CARDTYPE)
                         && (e.GetTag(GameTag.CARDTYPE) == (int)CardType.MINION
                          || e.GetTag(GameTag.CARDTYPE) == (int)CardType.SPELL
                          || e.GetTag(GameTag.CARDTYPE) == (int)CardType.BATTLEGROUND_SPELL)
                         && e.HasTag(GameTag.TECH_LEVEL)
                         && !(e.HasTag(GameTag.CONTROLLER)
                           && e.GetTag(GameTag.CONTROLLER) == playerId))
                .OrderBy(e => e.GetTag(GameTag.ZONE_POSITION))
                .ToList();
        }

        /// <summary>Count minions on a player's board.</summary>
        private int CountPlayerBoardMinions(GameV2 game, int playerId)
        {
            return game.Entities.Values.Count(e =>
                e.GetTag(GameTag.CONTROLLER) == playerId
                && e.GetTag(GameTag.ZONE) == (int)Zone.PLAY
                && e.GetTag(GameTag.CARDTYPE) == (int)CardType.MINION);
        }

        // ── Utility ──────────────────────────────────────────────────────

        private int GetTurnNumber(GameV2 game)
        {
            var playerEnt = GetEntityByPlayerId(game, game.Player.Id);
            if (playerEnt != null)
            {
                int turn = playerEnt.GetTag(GameTag.TURN);
                return Math.Max(turn, 1);
            }
            return 1;
        }

        private string GetAnomalyCardId(GameV2 game)
        {
            var anomaly = game.Entities.Values.FirstOrDefault(e =>
                e.CardId != null && e.CardId.Contains("ANOMALY"));
            return anomaly?.CardId ?? "";
        }

        private string RaceToString(int raceValue)
        {
            switch (raceValue)
            {
                case 14: return "MURLOC";
                case 15: return "DEMON";
                case 17: return "MECH";
                case 18: return "ELEMENTAL";
                case 20: return "BEAST";
                case 21: return "TOTEM";
                case 23: return "PIRATE";
                case 24: return "DRAGON";
                case 28: return "QUILBOAR";
                case 30: return "NAGA";
                case 11: return "UNDEAD";
                case 22: return "NERUBIAN";
                default: return "INVALID";
            }
        }
    }

    // ── Data types (match overlay_protocol.py) ──────────────────────────

    public class GameStateData
    {
        public string type;
        public string game_id;
        public int turn;
        public string phase;
        public PlayerState player;
        public TavernSlot[] tavern;
        public HandSlot[] hand;
        public BoardSlot[] board;
        public TrinketSlot[] trinkets;
        public OpponentSummary[] opponents;
        public int alive_count;
        public int? damage_cap;
        public string anomaly_card_id;
    }

    public class PlayerState
    {
        public int health = 40;
        public int armor;
        public int gold = 3;
        public int tavern_tier = 1;
        public int upgrade_cost = 5;
        public string hero_card_id = "";
        public bool hero_power_used;
        public int hero_power_cost = 2;
        public bool hero_power_extra_uses;
        public int free_refresh_remaining;
        public int next_spell_cost_reduction;
        public int blood_gem_atk_bonus;
        public int blood_gem_health_bonus;
        public int pending_triple_reward_tier;
    }

    public class TavernSlot
    {
        public string card_id;
        public int atk, health, tier, cost;
        public string race;
        public bool is_minion, is_spell, taunt, divine_shield, poisonous, reborn, frozen;
    }

    public class HandSlot
    {
        public string card_id;
        public int atk, health, tier, cost;
        public string race;
        public bool is_minion, is_spell, golden, battlecry, spellcraft;
        public int turns_in_hand;
    }

    public class BoardSlot
    {
        public string card_id;
        public int atk, health, max_health, tier;
        public bool taunt, divine_shield, divine_shield_intact, poisonous,
                    venomous, reborn, windfury, cleave, golden, exhausted;
        public string race;
    }

    public class TrinketSlot
    {
        public string card_id;
        public int cost, tier;
        public bool has_start_of_combat, has_end_of_turn, has_start_of_turn;
    }

    public class OpponentSummary
    {
        public int health = 40, armor, tavern_tier = 1, board_size;
        public bool alive = true;
    }

    public class SuggestionsMessage
    {
        public string type;
        public string game_id;
        public int turn;
        public List<ActionSuggestion> actions;
        public double value_estimate;
        public int predicted_rank;
        public List<int> rearrangement;  // suggested board slot order, or null
    }

    public class ActionSuggestion
    {
        public int action;
        public string name;
        public double probability;
    }
}
