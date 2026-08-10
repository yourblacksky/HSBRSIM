"""
HSRL Policy Module — Entity-Token Transformer Architecture.

Shared components for 5M+ parameter models:
  - EntityTransformer: multi-head attention over entity tokens
  - HierarchicalActionHead: type classifier + pointer
  - DistributionalValueHead: P(rank) → V(s)
  - EntityTokenizerV2: 37-slot tokenizer for Observation V2

Observation encoding only needs ``get_card_indexer`` (pure Python) from
``entity_tokenizer_v2``. The torch-based model components below are imported
lazily: without torch they resolve to ``None`` so the package still imports
(e.g. for ``build_observation_v2``). Install torch to enable training.
"""

try:
    from hsrl.policy.entity_tokenizer_v2 import EntityTokenizerV2
    from hsrl.policy.transformer import EntityTransformer
    from hsrl.policy.heads import HierarchicalActionHead
    from hsrl.policy.value_head import DistributionalValueHead
    from hsrl.policy.model_5m import ScaledModel, ScaledTokenizer
except Exception:  # pragma: no cover - torch not installed
    EntityTokenizerV2 = None  # type: ignore[assignment,misc]
    EntityTransformer = None  # type: ignore[assignment,misc]
    HierarchicalActionHead = None  # type: ignore[assignment,misc]
    DistributionalValueHead = None  # type: ignore[assignment,misc]
    ScaledModel = None  # type: ignore[assignment,misc]
    ScaledTokenizer = None  # type: ignore[assignment,misc]

__all__ = [
    "EntityTokenizerV2",
    "EntityTransformer",
    "HierarchicalActionHead",
    "DistributionalValueHead",
    "ScaledModel",
    "ScaledTokenizer",
]
