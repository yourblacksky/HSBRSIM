"""
HSRL Policy Module — Entity-Token Transformer Architecture.

Shared components for 5M+ parameter models:
  - EntityTransformer: multi-head attention over entity tokens
  - HierarchicalActionHead: type classifier + pointer
  - DistributionalValueHead: P(rank) → V(s)
  - EntityTokenizerV2: 37-slot tokenizer for Observation V2
"""

from hsrl.policy.entity_tokenizer_v2 import EntityTokenizerV2
from hsrl.policy.transformer import EntityTransformer
from hsrl.policy.heads import HierarchicalActionHead
from hsrl.policy.value_head import DistributionalValueHead
from hsrl.policy.model_5m import ScaledModel, ScaledTokenizer
