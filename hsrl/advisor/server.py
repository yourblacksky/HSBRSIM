"""
HSRL Adviser — WebSocket Server

Runs a local WebSocket server that receives Battlegrounds game state from
the C# HDT plugin, runs model inference, and returns action suggestions.

Usage:
    python -m hsrl.advisor.cli --model checkpoints/best_model.zip
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
import signal
from typing import Optional

import numpy as np

from hsrl.advisor.collector import DataCollector
from hsrl.advisor.inference import ModelInference
from hsrl.advisor.overlay_protocol import (
    ActionSuggestion,
    ErrorMessage,
    SuggestionsMessage,
    parse_game_end,
    parse_game_start,
    parse_game_state,
)
from hsrl.advisor.state_mapper import StateMapper
from hsrl.advisor.action_constants import (
    BUY_OFFSET,
    END_TURN,
    FREEZE,
    GET_BUDDY,
    HERO_POWER,
    NUM_ACTIONS,
    PLAY_OFFSET,
    REARRANGE,
    REFRESH,
    SELL_OFFSET,
    UPGRADE,
)

logger = logging.getLogger(__name__)


class AdviserServer:
    """WebSocket server that bridges HDT game state to model inference.

    When model_path is None, runs in collect-only mode: records game
    trajectories without providing action suggestions.

    Args:
        model_path: Path to a MaskablePPO .zip checkpoint (optional).
        host: Bind address (default: 127.0.0.1).
        port: Listen port (default: 9777).
        data_dir: Directory for collected match data.
        collect_data: Whether to save match trajectories.
        top_k: Number of action suggestions to return.
    """

    def __init__(
        self,
        model_path: str | None = None,
        host: str = "127.0.0.1",
        port: int = 9777,
        data_dir: str = "data/real_games",
        collect_data: bool = True,
        top_k: int = 5,
    ):
        self.host = host
        self.port = port
        self.top_k = top_k

        self.mapper = StateMapper()
        self.inference = None
        if model_path is not None:
            self.inference = ModelInference(model_path)
        self.collector = DataCollector(data_dir, enabled=collect_data)

        self._server = None
        self._shutdown = False

        mode = "inference" if self.inference else "collect-only"
        logger.info(
            "AdviserServer initialized: mode=%s, %s:%d, collect=%s",
            mode, host, port, collect_data,
        )

    # ── Public API ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the WebSocket server (blocks until shutdown)."""
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "websockets package required. Install with: pip install websockets"
            )

        self._shutdown = False

        async def handler(websocket):
            await self._handle_connection(websocket)

        self._server = await websockets.serve(
            handler, self.host, self.port,
        )

        logger.info("Adviser server listening on ws://%s:%d", self.host, self.port)
        print(f"HrSRL Adviser server listening on ws://{self.host}:{self.port}")

        # Wait until shutdown
        while not self._shutdown:
            await asyncio.sleep(0.5)

    def stop(self) -> None:
        """Signal the server to shut down."""
        self._shutdown = True

    async def close(self) -> None:
        """Close the server and cleanup."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Adviser server stopped.")

    @property
    def stats(self) -> dict:
        """Return server statistics."""
        return {
            "mode": "inference" if self.inference else "collect-only",
            "model_device": self.inference.device if self.inference else "N/A",
            "games_collected": self.collector.total_games_collected(),
        }

    # ── Connection handling ───────────────────────────────────────────────

    async def _handle_connection(self, websocket) -> None:
        """Handle a single WebSocket client connection."""
        remote = websocket.remote_address
        logger.info("Client connected: %s", remote)

        try:
            async for message in websocket:
                if self._shutdown:
                    break
                try:
                    response = await self._process_message(message)
                    if response is not None:
                        await websocket.send(response)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from %s", remote)
                    err = ErrorMessage(message="Invalid JSON").__dict__
                    await websocket.send(json.dumps(err))
                except Exception:
                    logger.exception("Error processing message from %s", remote)
        except Exception:
            logger.debug("Connection closed: %s", remote)
        finally:
            logger.info("Client disconnected: %s", remote)

    async def _process_message(self, raw: str) -> Optional[str]:
        """Process one incoming message, return optional response JSON string."""
        data = json.loads(raw)
        msg_type = data.get("type", "")
        logger.info("Received: type=%s gold=%s turn=%s",
                     msg_type, data.get("player", {}).get("gold", "?"),
                     data.get("turn", "?"))

        if msg_type == "game_state":
            return await self._handle_game_state(data)
        elif msg_type == "game_start":
            self._handle_game_start(data)
            return None
        elif msg_type == "game_end":
            self._handle_game_end(data)
            return None
        else:
            logger.warning("Unknown message type: %s", msg_type)
            return json.dumps(ErrorMessage(
                message=f"Unknown message type: {msg_type}",
                game_id=data.get("game_id", ""),
            ).__dict__)

    # ── Message handlers ──────────────────────────────────────────────────

    def _handle_game_start(self, data: dict) -> None:
        """Record game start for data collection."""
        msg = parse_game_start(data)
        self.collector.start_game(msg.game_id, {
            "hero_card_id": msg.hero_card_id,
            "mmr": msg.mmr,
            "timestamp": msg.timestamp,
        })
        logger.info("Game started: %s (hero=%s, mmr=%d)",
                     msg.game_id, msg.hero_card_id, msg.mmr)

    async def _handle_game_state(self, data: dict) -> Optional[str]:
        """Process game state, return suggestions (or empty in collect-only mode)."""
        msg = parse_game_state(data)

        # Only process during recruit phase
        if msg.phase != "recruit":
            return None

        # Build action mask from HDT state
        action_mask = build_action_mask_from_state(msg)

        if self.inference is not None:
            # Map to observation and run inference
            obs = self.mapper.map(msg)
            try:
                best_action, suggestions, value = self.inference.predict(
                    obs, action_mask, top_k=self.top_k,
                )
            except Exception:
                logger.exception("Inference failed")
                return json.dumps(ErrorMessage(
                    message="Inference failed",
                    game_id=msg.game_id,
                ).__dict__)

            # Record step for data collection
            self.collector.record_step(
                state=data,
                action_taken=best_action,
                action_mask=action_mask,
                turn=msg.turn,
            )

            # Compute board arrangement suggestion
            arrangement = None
            board_n = sum(1 for s in msg.board if s is not None)
            if board_n >= 2:
                try:
                    order, v_before, v_after = self.inference.suggest_arrangement(obs)
                    arrangement = order
                    logger.info(
                        "Arrange: order=%s v_before=%.2f v_after=%.2f",
                        order, v_before, v_after,
                    )
                except Exception:
                    logger.debug("Arrangement suggestion skipped", exc_info=True)

            action_list = [
                ActionSuggestion(action=a, name=n, probability=round(p, 4))
                for a, n, p in suggestions
            ]
            predicted_rank = max(1, min(8, int(8.0 * (1.0 - (value + 10.0) / 110.0))))
            hand_n = sum(1 for s in msg.hand if s is not None)
            valid_count = int(action_mask.sum())
            top3 = [(a, n, round(p, 3)) for a, n, p in suggestions[:3]]
            logger.info(
                "Suggestions: turn=%d gold=%d hand=%d board=%d valid=%d top3=%s v=%.2f rank=%d",
                msg.turn, msg.player.gold, hand_n, board_n, valid_count, top3,
                value, predicted_rank,
            )

            resp = SuggestionsMessage(
                game_id=msg.game_id,
                turn=msg.turn,
                actions=action_list,
                value_estimate=round(value, 4),
                predicted_rank=predicted_rank,
                rearrangement=arrangement,
            )
        else:
            # Collect-only mode: record state, return empty suggestions
            self.collector.record_step(
                state=data,
                action_taken=0,
                action_mask=action_mask,
                turn=msg.turn,
            )
            logger.info(
                "Recorded: turn=%d gold=%d phase=%s",
                msg.turn, msg.player.gold, msg.phase,
            )
            resp = SuggestionsMessage(
                game_id=msg.game_id,
                turn=msg.turn,
                actions=[],
                value_estimate=0.0,
                predicted_rank=4,
            )

        return json.dumps(asdict(resp), ensure_ascii=False)

    def _handle_game_end(self, data: dict) -> None:
        """Record game end for data collection."""
        msg = parse_game_end(data)
        filepath = self.collector.end_game(msg.placement, msg.mmr_change)
        if filepath:
            logger.info("Game saved: %s (placement=%d)", filepath, msg.placement)


# ── Action mask builder for HDT state ─────────────────────────────────────


def build_action_mask_from_state(msg) -> np.ndarray:
    """Build an action mask from a GameStateMessage (no Game/Player needed).

    Mirrors the logic in hsrl/env/action.py:build_action_mask().
    """
    mask = np.zeros(NUM_ACTIONS, dtype=bool)
    ps = msg.player

    # Buy tavern slots 0-6 (can't buy if hand is full)
    hand_count = sum(1 for s in msg.hand[:10] if s is not None)
    for i, slot in enumerate(msg.tavern[:7]):
        if slot is not None and (slot.is_minion or slot.is_spell):
            # Cost defaults to 3 if tag missing or 0
            cost = slot.cost if slot.cost > 0 else 3
            if ps.gold >= cost and hand_count < 10:
                mask[BUY_OFFSET + i] = True

    # Sell board slots 7-13
    for i, slot in enumerate(msg.board[:7]):
        if slot is not None:
            mask[SELL_OFFSET + i] = True

    # Play hand cards 14-23 (spells don't need board space)
    board_count = sum(1 for s in msg.board if s is not None)
    for i, slot in enumerate(msg.hand[:10]):
        if slot is not None and (slot.is_minion or slot.is_spell):
            if slot.is_minion and board_count >= 7:
                continue  # need free board slot for minion
            mask[PLAY_OFFSET + i] = True

    # Refresh
    if ps.gold >= 1 or ps.free_refresh_remaining > 0:
        mask[REFRESH] = True

    # Upgrade tavern
    upgrade_cost = max(ps.upgrade_cost, 1)
    if ps.gold >= upgrade_cost and ps.tavern_tier < 7:
        mask[UPGRADE] = True

    # Freeze/unfreeze
    if any(s is not None for s in msg.tavern[:7]):
        mask[FREEZE] = True

    # Hero power
    if not ps.hero_power_used or ps.hero_power_extra_uses:
        if ps.gold >= ps.hero_power_cost:
            mask[HERO_POWER] = True

    # End turn (always valid)
    mask[END_TURN] = True

    # Rearrange — valid when ≥2 board minions (free, unlimited)
    if board_count >= 2:
        mask[REARRANGE] = True

    # Get Buddy — not reliably detectable from HDT state without
    # buddy meter fill tracking, so leave disabled by default.
    # C# plugin can explicitly enable it via a flag in game_state.

    return mask


# ── Standalone runner ─────────────────────────────────────────────────────


def run_server(
    model_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 9777,
    data_dir: str = "data/real_games",
    collect_data: bool = True,
    top_k: int = 5,
) -> None:
    """Run the Adviser server (synchronous entry point)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    server = AdviserServer(
        model_path=model_path,
        host=host,
        port=port,
        data_dir=data_dir,
        collect_data=collect_data,
        top_k=top_k,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle Ctrl+C gracefully
    def _sig_handler():
        print("\nShutting down...")
        server.stop()

    try:
        loop.add_signal_handler(signal.SIGINT, _sig_handler)
        loop.add_signal_handler(signal.SIGTERM, _sig_handler)
    except NotImplementedError:
        pass  # Windows doesn't support add_signal_handler

    try:
        loop.run_until_complete(server.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(server.close())
        loop.close()
