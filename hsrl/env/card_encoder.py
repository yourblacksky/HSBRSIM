"""Card ID -> numeric encoding (deterministic, collision-safe enough).

Used by ``hsrl/advisor/state_mapper.py`` to embed card ids into feature
vectors as a float in [0, 1). Pure function of the id string, so the same
card always maps to the same value across runs.
"""

from __future__ import annotations

import hashlib


def encode_card_id(card_id: str) -> float:
    """Stable hash of a card id, normalized to [0, 1)."""
    if not card_id:
        return 0.0
    digest = hashlib.md5(card_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 2**32
