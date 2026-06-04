"""
Observation V2 builder — entity-centric observation with public opponent context.

Replaces hsrl/policy/obs_builder.py with expanded schema that includes:
  - Global context (turn, phase, alive, cap, tribes)
  - Hero self (hp, armor, gold, tier, hand/board sizes)
  - Tavern entities (7 slots × 8 features)
  - Board entities (7 slots × 8 features)
  - Hand entities (10 slots × 8 features)
  - Opponent public summaries (7 slots × 12 features)
  - History tokens (4 slots × 8 features)

Total: 30 entity slots (vs 24 in V1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hsrl.core.enums import CardType, GameTag, Step
from hsrl.rl_env.observation.entity_schema import (
    NUM_ENTITY_SLOTS, ENTITY_FEAT_DIM,
    GLOBAL_FEAT_DIM, HERO_FEAT_DIM, OPPONENT_FEAT_DIM, HISTORY_FEAT_DIM,
    TAVERN_OFFSET, BOARD_OFFSET, HAND_OFFSET,
    TAVERN_SLOTS, BOARD_SLOTS, HAND_SLOTS, OPPONENT_SLOTS, HISTORY_SLOTS,
    TokenGroup, EntityTokenLayout,
)
from hsrl.rl_env.observation.opponent_public_encoder import OpponentPublicEncoder

if TYPE_CHECKING:
    from hsrl.core.game import Game
    from hsrl.core.player import Player


def build_observation_v2(
    game: "Game", player: "Player",
    include_opponents: bool = False,
) -> dict:
    """Build the full Observation V2 dict for a single player.

    Returns keys:
        entity_stats:     (30, 8) float32 — per-slot features
        entity_mask:      (30,) bool — which slots are occupied
        entity_groups:    (30,) int — TokenGroup enum
        global_features:  (16,) float32 — global context
        hero_features:    (12,) float32 — hero self info
        opponent_features:(7, 12) float32 — opponent public summaries
        history_features: (4, 8) float32 — recent history
        card_indices:     (30,) int64 — CardIndexer indices
    """
    from hsrl.policy.entity_tokenizer_v2 import get_card_indexer
    indexer = get_card_indexer()

    # Initialize arrays
    entity_stats = np.zeros((NUM_ENTITY_SLOTS, ENTITY_FEAT_DIM), dtype=np.float32)
    entity_mask = np.zeros(NUM_ENTITY_SLOTS, dtype=bool)
    entity_groups = np.zeros(NUM_ENTITY_SLOTS, dtype=np.int32)
    card_indices = np.zeros(NUM_ENTITY_SLOTS, dtype=np.int64)

    # ── Global token (slot 0) ──
    entity_mask[0] = True
    entity_groups[0] = int(TokenGroup.GLOBAL)
    # Global features stored separately (16-dim)

    # ── Hero self (slot 1) ──
    entity_mask[1] = True
    entity_groups[1] = int(TokenGroup.HERO_SELF)
    # Hero features stored separately (12-dim)

    # ── Tavern (slots 2-8) ──
    for i, entity in enumerate(player.tavern[:TAVERN_SLOTS]):
        idx = TAVERN_OFFSET + i
        entity_stats[idx] = _encode_entity(entity)
        entity_mask[idx] = True
        entity_groups[idx] = int(TokenGroup.TAVERN)
        card_indices[idx] = indexer.encode(entity.get_tag(GameTag.CARD_ID, ""))

    # ── Board (slots 9-15) ──
    living = [m for m in player.board if not m.dead]
    for i, minion in enumerate(living[:BOARD_SLOTS]):
        idx = BOARD_OFFSET + i
        entity_stats[idx] = _encode_entity(minion)
        entity_mask[idx] = True
        entity_groups[idx] = int(TokenGroup.BOARD)
        card_indices[idx] = indexer.encode(minion.get_tag(GameTag.CARD_ID, ""))

    # ── Hand (slots 16-25) ──
    for i, card in enumerate(player.hand[:HAND_SLOTS]):
        idx = HAND_OFFSET + i
        entity_stats[idx] = _encode_entity(card)
        entity_mask[idx] = True
        entity_groups[idx] = int(TokenGroup.HAND)
        card_indices[idx] = indexer.encode(card.get_tag(GameTag.CARD_ID, ""))

    # ── Opponents (slots 26-32) ──
    # DISABLED by default: HDT plugin exposes very limited opponent info,
    # and bad opponent estimates can mislead the model at small scale.
    # Enable with include_opponents=True when opponent modeling is needed.
    if include_opponents:
        opp_encoder = OpponentPublicEncoder()
        opp_features = opp_encoder.encode_all(game, player)
    else:
        opp_features = np.zeros((OPPONENT_SLOTS, OPPONENT_FEAT_DIM), dtype=np.float32)

    # ── History (slots 33-36) ──
    history_features = np.zeros((HISTORY_SLOTS, HISTORY_FEAT_DIM), dtype=np.float32)
    for i in range(HISTORY_SLOTS):
        idx = HISTORY_SLOTS  # placeholder

    # ── Global features ──
    gf = np.zeros(GLOBAL_FEAT_DIM, dtype=np.float32)
    gf[0] = min(game.turn / 20.0, 1.0)
    gf[1] = 1.0 if game.step == Step.RECRUIT else 0.0
    alive_count = sum(1 for p in game.players if p.is_alive)
    gf[2] = alive_count / 8.0
    cap = game._get_damage_cap()
    gf[3] = (cap / 15.0) if cap is not None else 0.0
    # Tribes
    if game.active_tribes:
        gf[4] = 1.0  # has tribe filter
    # Anomaly indicator
    if game.active_anomaly and not isinstance(game.active_anomaly, bool):
        gf[5] = 1.0

    # ── Hero features ──
    hf = np.zeros(HERO_FEAT_DIM, dtype=np.float32)
    hf[0] = min(player.health / 40.0, 1.0)
    hf[1] = min(player.armor / 20.0, 1.0)
    hf[2] = min(player.gold / 10.0, 1.0)
    hf[3] = player.tavern_tier / 7.0
    hf[4] = min(player.get_tag(GameTag.TAVERN_UPGRADE_COST, 5) / 10.0, 1.0)
    hf[5] = min(len(player.hand) / 10.0, 1.0)
    hf[6] = min(len(living) / 7.0, 1.0)
    hf[7] = min(player.hero_power_cost / 10.0, 1.0)
    hf[8] = 0.0 if player.get_tag(GameTag.HERO_POWER_USED, False) else 1.0
    hf[9] = 1.0 if player.get_tag(GameTag.HERO_POWER_EXTRA_USES, 0) > 0 else 0.0
    hf[10] = 0.0  # pending triple reward tier
    hf[11] = min(player.get_tag(GameTag.FREE_REFRESH_REMAINING, 0) / 5.0, 1.0)

    return {
        "entity_stats": entity_stats,
        "entity_mask": entity_mask,
        "entity_groups": entity_groups,
        "card_indices": card_indices,
        "global_features": gf,
        "hero_features": hf,
        "opponent_features": opp_features,
        "history_features": history_features,
    }


def _encode_entity(entity) -> np.ndarray:
    """Encode a single entity into 8-dim feature vector."""
    ct = entity.get_tag(GameTag.CARDTYPE, CardType.INVALID)
    is_minion = ct == CardType.MINION
    is_spell = ct == CardType.SPELL

    arr = np.zeros(ENTITY_FEAT_DIM, dtype=np.float32)
    arr[0] = min(entity.atk / 50.0, 1.0) if is_minion else 0.0
    arr[1] = min(entity.health / 50.0, 1.0) if is_minion else 0.0
    arr[2] = entity.tech_level / 7.0
    arr[3] = min(entity.get_tag(GameTag.COST, 3) / 10.0, 1.0)
    arr[4] = float(entity.get_tag(GameTag.RACE, 0) or 0) / 12.0
    arr[5] = 1.0 if is_minion else 0.0
    arr[6] = 1.0 if is_spell else 0.0
    arr[7] = 1.0 if entity.has_tag(GameTag.GOLDEN) else 0.0
    return arr
