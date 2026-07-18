# REC-3 mock02 compressed AR-DFlash blocker

## Decision

REC-3 remains blocked before dataset smoke. The compressed `rec3_mock_02` input is byte/token
identical across AR and D-Flash, but greedy AR and the D-Flash target verifier diverge reproducibly.

## Evidence

- Orders: `ar_then_dflash`, `dflash_then_ar`
- Repetitions per order: 5
- Divergences reproduced: 10/10
- First divergence indices: [2]
- Structural audits complete: True
- Cache progression internally consistent: True
- Classification: `dflash_core_target_verification_cache_numerical_path`

The first divergent D-Flash token is the token selected by the cached block target verifier while
the same-prefix greedy cached target selects another token. This places the observed mismatch in
the D-Flash target-verification/cache numerical path, not in fixture rendering, compressor config,
execution order, or output parsing.

## Separate patch proposal (not applied in this diagnostic batch)

Create a dedicated D-Flash core change that captures target top-2 logits/margins at verification
positions and evaluates an exact-compatible verification policy for near-tie NF4 logits. The patch
must keep Baseline-AR unchanged, preserve real target-forward accounting, and pass exact token parity
on both GSM8K and QMSum before acceptance. Do not adopt a silent per-token oracle fallback.
