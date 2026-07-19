# FINAL_REPORT.md

## Overall verdict: FAIL

This report is sealed from the runtime summaries and validation records in this ZIP.

## Configuration and SDPA

- Config SHA-256: `e6809adeca0a3be74b091f8750dbd8e5228e244b96139078cac1c18ba4660baa`
- Frozen canonical profile: `attention_backend=sdpa`, `sdpa_kernel=math`, block size 16.
- Active mock10/dataset profiles: `attention_backend=sdpa`, `sdpa_kernel=auto`, block size 8.
- Auto policy leaves Flash, memory-efficient, and math available to the PyTorch dispatcher.
- The separate profiler probe records actual execution for its representative CUDA shape; enabled flags alone are not presented as execution evidence.

## Canonical math regression: PASS

- Runs: 50 Baseline + 50 DFlash.
- Rendered-input parity: 50/50.
- Generated-token parity: 50/50.
- Frozen-reference parity: 50/50.
- DFlash peak reserved: 3.625000 GiB.

## Four-condition mock10 auto: FAIL

- Successful runs: 40/40.
- Generated-token parity: 19/20.
- Exact quality: 40/40.
- Metric validity: 40/40.

## GSM8K n10 + QMSum n10 auto: FAIL

- Successful runs: 80/80.
- Rendered-input parity: 40/40.
- Generated-token parity: 25/40.
- GSM8K cap: 256 tokens.
- QMSum cap: 512 tokens; cap-hits 12/40.
- Cap-hit outputs are evaluated only as actually generated prefixes and are never marked complete.
- QMSum coverage: 100.0%; hidden truncation: 0.
- DFlash-R1 peak reserved: 5.710938 GiB.
- CC-DFlash-R2 peak reserved: 5.710938 GiB.

## Parity diagnostics

- First-divergence records: 16.
- Every failure record contains rendered input IDs/hash, AR and D-Flash tokens, verifier counters, cache/block state, and stopping state when available.
- Unisolated block-shaped numerical drift is not mislabeled as SDPA drift.

## D-Flash core blocker

- Sealed evidence shows same-input AR versus block-verification target top-1 divergence while cache progression and structural checks pass.
- Resolving the remaining parity failures would require changing the D-Flash core/numerical verification path or introducing an AR oracle fallback. Both are outside the permitted fix scope, so the blocker remains sealed as FAIL.

## Portability and source completeness

- Windows Triton bridge lock entry is project-relative: **PASS**.
- All modified/untracked production sources in the declared scope are included: **PASS**.
- D-Flash core unchanged from the sealed pre-goal snapshot: **PASS**.
- No commit or push was performed.

## Failed hard gates

- mock10_pass
- dataset_smoke_pass
- parent_process_stability_pass

## Final conclusion

**FAIL** — this verdict follows the configured hard gates; fixtures, expected answers, evaluator rules, block size, and stopping contract were not altered to manufacture a pass.
