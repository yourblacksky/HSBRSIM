"""
HSRL Adviser — Command-Line Interface

Start the trajectory collection server for HDT game state capture.

Usage:
    # Collect-only mode (no model required)
    python -m hsrl.advisor.cli --collect-only

    # Inference mode (requires trained checkpoint)
    python -m hsrl.advisor.cli --model checkpoints/best_model.zip

    # Dev mode with simulated test client
    python -m hsrl.advisor.cli --dev
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import time
from pathlib import Path

from hsrl.advisor.server import AdviserServer, build_action_mask_from_state
from hsrl.advisor.overlay_protocol import (
    GameStateMessage,
    PlayerState,
    TavernSlot,
    HandSlot,
    BoardSlot,
    TrinketSlot,
    OpponentSummary,
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="HrSRL Adviser — HDT plugin backend server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Path to MaskablePPO .zip checkpoint (optional; omit for collect-only mode)",
    )
    parser.add_argument(
        "--collect-only", action="store_true",
        help="Run in collect-only mode: record trajectories, no AI suggestions",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=9777,
        help="Listen port (default: 9777)",
    )
    parser.add_argument(
        "--data-dir", type=str, default="data/real_games",
        help="Directory for collected match data",
    )
    parser.add_argument(
        "--no-collect", action="store_true",
        help="Disable data collection",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Number of action suggestions (default: 5)",
    )
    parser.add_argument(
        "--dev", action="store_true",
        help="Run in dev mode with a simulated test client",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.dev:
        run_dev_mode(args)
    else:
        model_path = args.model

        if model_path:
            if not Path(model_path).exists():
                parser.error(f"Model file not found: {model_path}")
        elif not args.collect_only:
            print("Note: no --model provided, running in collect-only mode.")
            print("Use --model <path> for AI suggestions (requires sb3-contrib).")

        from hsrl.advisor.server import run_server
        run_server(
            model_path=model_path,
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
            collect_data=not args.no_collect,
            top_k=args.top_k,
        )


# ── Dev mode: simulated test client ──────────────────────────────────────


def run_dev_mode(args):
    """Run the server and a simulated test client for development.

    The test client sends a few fake game_state messages to verify
    the full pipeline: receive → map → infer → suggest.
    """
    server = AdviserServer(
        model_path=args.model
        if args.model
        else "checkpoints/selfplay_iter0099_20260505_171008.zip",
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        collect_data=not args.no_collect,
        top_k=args.top_k,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        # Start server in background
        server_task = asyncio.ensure_future(server.start())

        # Give server a moment to bind
        await asyncio.sleep(0.3)

        # Simulated test client
        try:
            import websockets
        except ImportError:
            print("websockets required: pip install websockets")
            server.stop()
            await server.close()
            return

        print("\n=== Dev Mode: Sending simulated game states ===\n")

        try:
            async with websockets.connect(
                f"ws://{args.host}:{args.port}"
            ) as ws:
                # Send game_start
                await ws.send(json.dumps({
                    "type": "game_start",
                    "game_id": "dev_test_001",
                    "hero_card_id": "TB_BaconShop_HERO_59",
                    "mmr": 7500,
                    "timestamp": "2026-05-05T12:00:00",
                }))
                await asyncio.sleep(0.1)

                # Send a few game_states with different scenarios
                for t in range(1, 4):
                    state = _make_test_state(turn=t)
                    await ws.send(json.dumps(state))
                    await asyncio.sleep(0.2)

                    # Receive response
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        parsed = json.loads(resp)
                        _print_suggestions(parsed)
                    except asyncio.TimeoutError:
                        print("  (no response received)")

                # Send game_end
                await ws.send(json.dumps({
                    "type": "game_end",
                    "game_id": "dev_test_001",
                    "placement": 3,
                    "mmr_change": 15,
                }))
                await asyncio.sleep(0.2)

        except Exception as e:
            print(f"Dev client error: {e}")

        print("\n=== Dev test complete. Press Ctrl+C to stop. ===\n")

        # Wait for Ctrl+C
        try:
            await server_task
        except KeyboardInterrupt:
            pass

    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        loop.run_until_complete(server.close())
        loop.close()


def _make_test_state(turn: int = 1) -> dict:
    """Create a plausible test game_state message."""
    return {
        "type": "game_state",
        "game_id": "dev_test_001",
        "turn": turn,
        "phase": "recruit",
        "player": {
            "health": 38 - turn * 2,
            "armor": 5,
            "gold": 7,
            "tavern_tier": min(turn, 7),
            "upgrade_cost": 6,
            "hero_card_id": "TB_BaconShop_HERO_59",
            "hero_power_used": False,
            "hero_power_cost": 2,
            "hero_power_extra_uses": False,
            "free_refresh_remaining": 0,
            "next_spell_cost_reduction": 0,
            "blood_gem_atk_bonus": 0,
            "blood_gem_health_bonus": 0,
            "pending_triple_reward_tier": 0,
        },
        "tavern": [
            {"card_id": "BGS_001", "atk": 2, "health": 3, "tier": 1, "cost": 3,
             "race": "BEAST", "is_minion": True, "is_spell": False,
             "taunt": False, "divine_shield": False, "poisonous": False,
             "reborn": False, "frozen": False},
            {"card_id": "BGS_030", "atk": 4, "health": 4, "tier": 2, "cost": 3,
             "race": "MECH", "is_minion": True, "is_spell": False,
             "taunt": True, "divine_shield": False, "poisonous": False,
             "reborn": False, "frozen": False},
            None, None, None, None, None,
        ],
        "hand": [
            {"card_id": "BGS_009", "atk": 3, "health": 2, "tier": 1, "cost": 1,
             "race": "MURLOC", "is_minion": True, "is_spell": False,
             "golden": False, "battlecry": True, "turns_in_hand": 0,
             "spellcraft": False},
            None, None, None, None, None, None, None, None, None,
        ],
        "board": [
            {"atk": 5, "health": 5, "max_health": 5, "tier": 1,
             "taunt": True, "divine_shield": False, "divine_shield_intact": False,
             "poisonous": False, "venomous": False, "reborn": False,
             "windfury": False, "cleave": False, "golden": False,
             "race": "DEMON", "exhausted": False},
            None, None, None, None, None, None,
        ],
        "trinkets": [None, None],
        "opponents": [
            {"health": 40, "armor": 10, "tavern_tier": 3, "board_size": 4, "alive": True},
            {"health": 35, "armor": 0, "tavern_tier": 3, "board_size": 5, "alive": True},
            {"health": 32, "armor": 5, "tavern_tier": 2, "board_size": 3, "alive": True},
            {"health": 40, "armor": 0, "tavern_tier": 4, "board_size": 6, "alive": True},
            {"health": 28, "armor": 0, "tavern_tier": 2, "board_size": 2, "alive": True},
            {"health": 40, "armor": 5, "tavern_tier": 3, "board_size": 4, "alive": True},
            {"health": 38, "armor": 0, "tavern_tier": 3, "board_size": 3, "alive": True},
        ],
        "alive_count": 8,
        "damage_cap": 15,
        "anomaly_card_id": "",
    }


def _print_suggestions(resp: dict) -> None:
    """Pretty-print a suggestions response."""
    if resp.get("type") != "suggestions":
        print(f"  Response: {json.dumps(resp, indent=2)}")
        return

    print(f"  Turn {resp['turn']} | "
          f"Value: {resp['value_estimate']:.3f} | "
          f"Predicted rank: {resp['predicted_rank']}")
    for i, act in enumerate(resp.get("actions", [])):
        marker = "★" if i == 0 else " ☆"
        print(f"  {marker} {act['name']}: {act['probability']:.3f}")
    print()


if __name__ == "__main__":
    main()
