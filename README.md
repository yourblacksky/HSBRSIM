# HSBRSIM — Hearthstone Battlegrounds Simulator

[中文文档](README_CN.md) | [English](README.md)

A clean, extensible Python engine for simulating **Hearthstone Battlegrounds Solo Mode** with mechanistic accuracy. Every keyword, trigger, and combat rule matches the official game description.

> **Scope**: Solo Mode only. Duos mode is out of scope.

## Architecture

### Action-Driven Design

All state changes flow through the Action system:

```
Action → queue → broadcast events → resolve → trigger follow-ups → check deaths
```

No hidden state. No magic numbers. Every property is declared upfront in `hsrl/core/enums.py`.

### Core Engine

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `hsrl/core/enums.py` | 311 | GameTag (310+), CardType (11), Race, Zone, Step, State |
| `hsrl/core/entity.py` | 356 | BaseEntity — tags, buffs, script hooks |
| `hsrl/core/actions.py` | 1,980 | 60+ Action classes — all game mechanics |
| `hsrl/core/game.py` | 2,100+ | Game engine — turns, combat, death, quests, trinkets |
| `hsrl/core/events.py` | 148 | EventListener + 40+ standard event constants |
| `hsrl/core/player.py` | 131 | Player — gold, health, board, hand, trinkets |
| `hsrl/core/card_db.py` | 157 | CardDB singleton + `register_card()` |
| `hsrl/core/minion.py` | 54 | Minion — combat state, can_attack |
| `hsrl/core/minion_pool.py` | 198 | Shared minion pool + `remove_all_copies` |
| `hsrl/core/spell_pool.py` | 107 | Shared spell pool |

## Implemented Mechanics

### Combat Keywords

| Keyword | Description | Status |
|---------|-------------|--------|
| Taunt | Forces attacks to target this minion first | ✅ |
| Divine Shield | Blocks the first instance of damage | ✅ |
| Poisonous | Destroys any minion damaged by this | ✅ |
| Venomous | Destroys any minion damaged by this (combat only) | ✅ |
| Reborn | Resummons with 1 Health on first death | ✅ |
| Windfury | Can attack twice per combat round | ✅ |
| Cleave | Also damages adjacent minions | ✅ |

### Card Effects

| Mechanism | Description | Status |
|-----------|-------------|--------|
| Battlecry | Triggers when played from hand | ✅ |
| Deathrattle | Triggers when the minion dies | ✅ |
| Start of Combat | Triggers at combat start | ✅ |
| End of Turn | Triggers at end of recruit phase | ✅ |
| Start of Turn | Triggers at start of recruit phase | ✅ |
| Avenge | Triggers after N friendly minions die | ✅ |
| Rally | Triggers when this minion attacks | ✅ |
| Magnetic | Attaches to a mech on board | ✅ |
| Spellcraft | One-time spell effect while in hand | ✅ |

### Subsystems

| System | Description | Status |
|--------|-------------|--------|
| Golden / Triple | Combine 3 copies → golden + discover | ✅ |
| Blood Gems | Get / Play / Improve gems | ✅ |
| Discover | Choose 1 of 3 cards (minion/spell/reward) | ✅ |
| Transform | Replace a minion with another | ✅ |
| FodderConsume | Devour a minion to gain stats | ✅ |
| Global Auras | Persistent board-wide buffs | ✅ |
| Tavern Buff | Buff minions in the tavern | ✅ |
| Combat Summon | Summon minions during combat | ✅ |
| Free Refresh | Gain free tavern refreshes | ✅ |
| Spell Discount | Reduce next spell's cost | ✅ |
| Buddy System | Hero-specific companion minions | ✅ |
| Trinkets | Trinket purchase + Lesser/Greater filtering | ✅ |
| Anomalies | Game-modifying rules | ✅ |
| Quests | Quest + reward system | ✅ |

### Card Registration Status

| Category | Count | CORRECT | DEFERRED | OOS |
|----------|-------|---------|----------|-----|
| Minion Pool | 218 | 218 | 0 | — |
| Spell Pool | 71 | ~23 | ~48 | — |
| Heroes | 119 | 119 | 0 | — |
| Hero Powers | 94 | 94 | 0 | — |
| Trinkets | 327 | 297 | 19 | 11 (Duos) |
| Anomalies | 105 | 101 | 0 | 4 (Duos) |
| Quest Rewards | 76 | 76 | 0 | — |
| **Total** | **~1,010** | **~928** | **~67** | **15** |

## Project Structure

```
HSBRSIM/
├── hsrl/                              # Main Python package
│   ├── core/                          # Game engine (7,000+ lines)
│   │   ├── enums.py                   # GameTag, CardType, Race, Zone, Step
│   │   ├── entity.py                  # BaseEntity — tags, buffs, hooks
│   │   ├── minion.py                  # Minion — combat state
│   │   ├── player.py                  # Player — gold, health, board
│   │   ├── actions.py                 # Action system (60+ Action classes)
│   │   ├── events.py                  # EventListener + 40+ event constants
│   │   ├── game.py                    # Game engine — turns, combat, death
│   │   ├── minion_pool.py             # Shared minion pool
│   │   ├── spell_pool.py              # Shared spell pool
│   │   ├── card_db.py                 # CardDB + register_card()
│   │   ├── quest.py                   # Quest + QuestReward entities
│   │   ├── anomaly.py                 # Anomaly entity
│   │   └── trinket.py                 # Trinket entity
│   ├── cards/                         # Card definitions (20 files)
│   │   ├── minions/                   # Minion cards (pool, scripts, tokens)
│   │   ├── heroes/                    # Hero cards (pool, scripts)
│   │   ├── spells/                    # Spell cards
│   │   ├── rewards/                   # Quest reward cards
│   │   ├── trinkets/                  # Trinket cards
│   │   └── anomalies/                 # Anomaly cards
│   ├── agents/                        # AI agents (Search, AZ MCTS, heuristic)
│   │   ├── search_agent.py            # Hybrid search + value network agent
│   │   ├── az_agent.py                # AlphaZero MCTS agent
│   │   ├── agent_utils.py             # Action simulation utilities
│   │   └── *_demo.py                  # Demo scripts
│   ├── policy/                        # Entity-Token Transformer policy (5.25M)
│   │   ├── model_5m.py                # ScaledModel: d=256, 6-layer Transformer
│   │   ├── entity_tokenizer_v2.py     # 37-slot tokenizer w/ card embeddings
│   │   ├── transformer.py             # Multi-head attention over entity tokens
│   │   ├── heads.py                   # Hierarchical action head (type + pointer)
│   │   ├── value_head.py              # Distributional value head P(rank)→V(s)
│   │   ├── bc_train.py                # BC training from heuristic teacher
│   │   └── iter_train.py              # Iterative BC: multi-round self-improvement
│   ├── rl_env/                        # Next-gen RL environment (entity-centric)
│   │   ├── observation/               # ObservationV2: 37 entity-slot layout
│   │   ├── action/                    # Hierarchical action space grammar
│   │   ├── reward/                    # Board score v2 + reward components
│   │   ├── envs/                      # BoardBuildingEnv, TurnRecruitEnv
│   │   └── teachers/                  # Plan search teacher
│   ├── advisor/                       # HDT plugin backend
│   │   ├── server.py                  # WebSocket server
│   │   ├── state_mapper.py            # Game state → feature vector
│   │   ├── collector.py               # Trajectory recorder (JSONL)
│   │   ├── overlay_protocol.py        # C# ↔ Python message schema
│   │   ├── inference.py               # Model inference (requires sb3-contrib)
│   │   └── cli.py                     # Command-line interface
│   ├── trajectory/                    # Trajectory opponent system
│   │   ├── record.py                  # MinionSnapshot, TurnSnapshot, Trajectory
│   │   ├── generate.py                # Batch trajectory generation
│   │   ├── opponent.py                # Trajectory opponent loader
│   │   └── pool.py                    # Trajectory pool sampling
│   └── tests/                         # Test suite (772 tests)
│       ├── test_core_mechanics.py      # Core mechanics tests
│       ├── test_token_cards.py        # Token card tests
│       ├── test_heroes.py             # Hero power tests
│       ├── test_advisor.py            # Advisor pipeline tests
│       └── test_logger.py             # Logger tests
├── hsrl_advisor/                      # HDT plugin (C#)
│   └── plugin/                        # HDT plugin source
│       ├── plugin.json                # Plugin manifest
│       ├── HrSRLAdviser.csproj        # .NET 4.7.2 project
│       ├── AdviserPlugin.cs           # Plugin entry point
│       ├── GameStateExtractor.cs      # Game state extraction (~617 lines)
│       ├── SuggestionOverlay.cs        # WPF overlay panel
│       └── WebSocketClient.cs         # WebSocket client
├── data/                              # Card data (JSON)
│   ├── bg_cards.json                  # Full BG cards (5,189)
│   ├── bg_pool_minions.json           # Minion pool (270)
│   ├── bg_pool_spells.json            # Spell pool (71)
│   ├── bg_heroes.json                 # Hero definitions (119)
│   ├── bg_hero_powers.json            # Hero powers (164)
│   ├── bg_trinkets.json               # Trinkets (326)
│   ├── bg_anomalies.json              # Anomalies (104)
│   └── bg_quest_rewards.json          # Quest rewards (73)
├── docs/                              # Reference documentation
│   ├── BATTLEGROUNDS_RULES.md         # Authoritative rules manual
│   ├── MECHANICS_REFERENCE.md         # Mechanics implementation reference
│   ├── CARD_REGISTRATION_GUIDE.md     # Card registration guide
│   └── wiki_crawls/                   # Cached wiki data
├── hsdata/                            # CardDefs.xml (git submodule)
├── pyproject.toml                     # Build configuration
└── README.md                          # This file
```

## Quick Start

### Installation

```bash
pip install -e .
# or with dev dependencies:
pip install -e ".[dev]"
```

### Basic Usage — 1v1 Combat Sandbox

```python
from hsrl.core.game import Game
from hsrl.core.player import Player
from hsrl.core.card_db import CARDS
import hsrl.cards.minions  # register standard example cards

# Create a sandbox game with 2 players
game = Game([])
game.card_db = CARDS

p1 = Player(CARDS.get("EXAMPLE_VANILLA"), game=game)
p2 = Player(CARDS.get("EXAMPLE_VANILLA"), game=game)
game.players = [p1, p2]

# Summon minions onto each player's board
m1 = game.create_minion("EXAMPLE_TAUNT")
m2 = game.create_minion("EXAMPLE_POISONOUS")
game.summon(p1, m1)
game.summon(p2, m2)

# Run a single combat between them
game._run_combat(p1, p2)
print(f"P1 HP: {p1.health}, P2 HP: {p2.health}")
```

### Running a Full 8-Player Game

Battlegrounds is fundamentally an 8-player game. The engine provides a built-in heuristic agent and a one-line API to simulate a complete match:

```python
# Imports trigger all card registrations (heroes, minions, spells, trinkets, etc.)
import hsrl.cards.heroes
import hsrl.cards.minions
import hsrl.cards.spells

from hsrl.core.game import Game
from hsrl.core.enums import GameTag

# 8-player game: one-line run with built-in heuristic agents
# Each agent uses a greedy strategy: buy best stats → play → upgrade → refresh
game = Game.run_game(
    hero_ids=[
        "BG20_HERO_100",  # Rokara
        "BG20_HERO_101",  # Xyrella
        "BG20_HERO_103",  # Death Speaker Blackthorn
        "EXAMPLE_HERO",
        "EXAMPLE_HERO_FREEZE",
        "EXAMPLE_HERO_COPY",
        "EXAMPLE_HERO_SPELL",
        "EXAMPLE_HERO_AURA",
    ],
    max_turns=50,
)

# Print results
print(f"Game complete in {game.turn} turns")
for i, p in enumerate(game.players):
    name = p.get_tag(GameTag.NAME, f"Player {i}")
    status = "WINNER" if p.health > 0 else "defeated"
    board = p.get_board_minions()
    print(f"  {name}: HP={p.health} Tier={p.tavern_tier} "
          f"Board={len(board)} [{status}]")
```

For step-by-step control, use `Game.create_game()` + `game.run_turn()`:

```python
# Manual turn-by-turn control
game = Game.create_game(hero_ids, card_db=None, apply_anomaly=False)

while game.state == game.state.RUNNING:
    game.run_turn()  # one full turn: recruit → combat → damage
    print(f"Turn {game.turn} done")

winner = [p for p in game.players if p.health > 0][0]
```

## Test Interface

### Running Tests

```bash
# Run all tests
python -m pytest hsrl/tests/ -v

# Run specific test categories
python -m pytest hsrl/tests/test_core_mechanics.py -v
python -m pytest hsrl/tests/test_token_cards.py -v
python -m pytest hsrl/tests/test_heroes.py -v

# Run a specific test
python -m pytest hsrl/tests/test_core_mechanics.py::TestCombat::test_taunt_attracts_attacks -v

# With coverage
pip install pytest-cov
python -m pytest hsrl/tests/ --cov=hsrl --cov-report=html
```

### Test Statistics

- **772 tests** passed, 1 skipped
- Categories: core mechanics (352), heroes (145), token cards (77), advisor, logger
- Coverage target: every mechanism and card script has a corresponding test

### Writing Tests

Tests follow the Arrange-Act-Assert pattern:

```python
def test_divine_shield_blocks_damage(self):
    # Arrange
    game = Game([])
    p1 = Player(...)
    p2 = Player(...)
    m1 = game.create_minion("EXAMPLE_DIVINE_SHIELD")
    m2 = game.create_minion("EXAMPLE_TAUNT")
    game.summon(p1, m1)
    game.summon(p2, m2)

    # Act
    game._run_combat(p1, p2)

    # Assert
    assert m1.get_tag(GameTag.DIVINE_SHIELD) == 0  # Shield consumed
    assert m1.health == m1.get_tag(GameTag.HEALTH)  # No health lost
```

## Card Registration Pipeline

To add a new card, follow the standard pipeline:

1. **Read the official card text** — understand the exact semantics
2. **Define a script class** with three-section docstring:
   ```python
   class BGS_999_Script:
       """Natural language: Battlecry: Give a friendly minion +2/+2.

       Formal spec:
         Battlecry → choose friendly minion → Buff(+2 ATK, +2 HP, permanent)

       Test: BGS_999_GivesBuff
       """
       battlecry = BuffFriendly(target=TARGET_SELF, atk=2, health=2)
   ```
3. **Register the card** via `register_card()`:
   ```python
   register_card(
       card_id="BGS_999",
       card_type=CardType.MINION,
       name="Example Buffer",
       attack=3, health=3, tier=2, race=Race.NEUTRAL,
       script_class=BGS_999_Script,
   )
   ```
4. **Write a test** that verifies the exact semantics
5. **Run tests** until they pass

**Card correctness standard**: Cards are either CORRECT (exact match to official text) or DEFERRED (returns None with documented dependency). Approximate implementations are not permitted.

## HDT Plugin — In-Game Trajectory Monitor

The `hsrl_advisor/plugin/` directory contains a C# plugin for **Hearthstone Deck Tracker** (HDT) that captures Battlegrounds game states in real time. Combined with the Python backend server, it records complete game trajectories as JSONL files for analysis.

### Architecture

```
[C# HDT Plugin] ──WebSocket──> [Python Server] ──> data/real_games/<date>/<game_id>.jsonl
     127.0.0.1:9777
```

### Building the Plugin

**Prerequisites**: .NET Framework 4.7.2 SDK, Hearthstone Deck Tracker installed.

```bash
# Build from command line
cd hsrl_advisor/plugin
dotnet build HrSRLAdviser.csproj

# Or open HrSRLAdviser.csproj in Visual Studio / JetBrains Rider
```

The `.csproj` PostBuild target automatically copies the built DLL and `plugin.json` to `%AppData%\HearthstoneDeckTracker\Plugins\HrSRLAdviser\`.

### Manual Installation

If the auto-deploy fails, manually copy:

```
hsrl_advisor/plugin/bin/Debug/net472/HrSRLAdviser.dll  →  %AppData%\HearthstoneDeckTracker\Plugins\HrSRLAdviser\
hsrl_advisor/plugin/plugin.json                         →  %AppData%\HearthstoneDeckTracker\Plugins\HrSRLAdviser\
```

### Running the Server

**Collect-only mode** (no AI model required — records trajectories only):

```bash
python -m hsrl.advisor.cli --collect-only
```

**Inference mode** (requires `sb3-contrib` and a trained checkpoint):

```bash
pip install sb3-contrib websockets
python -m hsrl.advisor.cli --model path/to/checkpoint.zip
```

### Trajectory Data Format

Each game produces one `.jsonl` file (one JSON object per line):

```jsonl
{"type": "game_start", "game_id": "abc123", "hero": "TB_BaconShop_HERO_59", "mmr": 7500, "timestamp": "2026-05-07T12:00:00"}
{"type": "step", "turn": 3, "action_taken": 0, "action_mask": [true, true, false, ...], "state": {...}}
{"type": "step", "turn": 4, "action_taken": 24, "action_mask": [...], "state": {...}}
...
{"type": "game_end", "game_id": "abc123", "placement": 3, "mmr_change": 15, "timestamp": "2026-05-07T12:15:00"}
```

The `state` object contains the full game state extracted from HDT: player status, tavern offerings, hand cards, board minions, trinkets, and opponent summaries. See `hsrl/advisor/overlay_protocol.py` for the complete schema.

### Plugin Features

- **Real-time state extraction**: Reads HDT's internal entity dictionary to capture the exact game state
- **Timed updates**: Sends game state to the server every 250ms during the recruit phase
- **WPF overlay**: Displays the connection status in HDT's overlay canvas
- **Auto-reconnect**: WebSocket client reconnects with exponential backoff on connection loss
- **Graceful degradation**: If the Python server is not running, the plugin simply doesn't display suggestions — HDT functions normally

## Data Sources

Card data is sourced from HearthSim's [hsdata](https://github.com/HearthSim/hsdata) (CardDefs.xml) and the [Amalgadon API](https://bgknowhow.com/), cleaned and cached in `data/` as structured JSON files.

**Data version**: Patch 35.6.0.243002 | Season 15

### Action-level replay evaluation (P4)

Evaluate normalized expert replays with next-action accuracy, expert-action
Top-3 coverage, board-score regret, economy/commit/refresh/enabler/upgrade/
positioning diagnostics, placement, and Top-4 rate:

```bash
python -m hsrl.evaluation.replay_action_eval replay.jsonl --format markdown
```

Every metric reports sample coverage; unavailable counterfactual data is shown
as `N/A`. See `docs/REPLAY_ACTION_EVALUATION.md` for the schema and capture gaps.

## RL Training

The project includes an entity-token Transformer policy (5.25M parameters) and iterative BC training pipeline:

```bash
# Phase 0: BC from heuristic teacher (single round)
python hsrl/policy/bc_train.py

# Phase 1: Iterative BC (multi-round self-improvement)
python hsrl/policy/iter_train.py
```

### Policy Architecture

```
build_observation_v2() → 37 entity slots → EntityTokenizerV2 → EntityTransformer → Heads
  ├─ EntityTokenizerV2: card embedding (1500×128) + entity MLP + summary projectors
  ├─ EntityTransformer: d=256, h=4, 6 layers — MHA over entity tokens
  ├─ HierarchicalActionHead: 8-way type + 24-way pointer → Discrete(50)
  └─ DistributionalValueHead: P(rank=1..8) → V(s)
```

The action space is hierarchical — a Discrete(50) action ID decomposes into an 8-way type (BUY/SELL/PLAY/REFRESH/UPGRADE/FREEZE/HERO_POWER/END_TURN) and a 24-way pointer (which minion to buy/sell/play).

### Current Results

| Method | avg board_score | avg raw (atk+hp) | vs Random |
|--------|----------------|-------------------|-----------|
| Iterative BC (Round 0: heuristic) | 2.2 | 33 | +0.8 |
| Iterative BC (Round 3: BC→BC) | 2.3 | 38 | +0.7 |
| Random baseline | 1.4 | 25-39 | — |

See `docs/AGENT_TRAINING_STATUS.md` for detailed training history and next steps.

## Design Philosophy

1. **Semantic precision**: Code matches card text exactly. "Get" ≠ "Play", "Summon" ≠ "Add to hand".
2. **No hidden state**: Every property is declared in `enums.py`. No magic numbers.
3. **Action-driven**: All state changes go through the Action system with event broadcasting.
4. **Cards are CORRECT or DEFERRED**: Approximations are bugs, not simplifications.
5. **Documentation is frozen**: Rules and mechanics are documented in `docs/` — no live wiki dependency.

## License

MIT
