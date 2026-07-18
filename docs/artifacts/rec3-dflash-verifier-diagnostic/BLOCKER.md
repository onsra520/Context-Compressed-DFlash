# REC-3 D-Flash verifier diagnostic blocker

## Decision

Dataset smoke remains blocked. Using the same active AWQ target and identical compressed
`rec3_mock_02` prefix, the three target-forward paths do not select the same token at output index 2.

Primary classification: `block_shape_numerical_drift_on_active_awq_path`.

## Locked contract

- Quantization: AWQ (not NF4)
- SDPA kernel: math
- AWQ split K iterations: 1
- Fixture/prompt/compression output: unchanged and hash-locked
- D-Flash core patch applied: false

## Findings

- Sequential one-token fresh-cache top-1: `425`
- Full-prefix no-cache top-1: `425`
- One-shot full-prefix cache top-1: `425`
- Production block top-1 by shape: `{'2': 425, '4': 425, '8': 425, '16': 49583}`
- Explicit-mask block top-1 by shape: `{'2': 425, '4': 425, '8': 425, '16': 49583}`
- Position/index validation: `True`
- Cache crop validation: `True`
- Attention mask changes top-1: `False`
- Semantic cache difference observed: `True`

The review pack contains per-layer key/value cache comparisons and raw full-vocabulary logits.
No D-Flash core change is made in this diagnostic batch.
