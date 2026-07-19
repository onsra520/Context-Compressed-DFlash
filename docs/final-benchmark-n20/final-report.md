# Final benchmark n=20

Final status: **FINAL_BENCHMARK_COMPLETE_WITH_FAILED_CLAIMS**

The benchmark is valid and independently reproducible from the frozen raw
evidence, but GSM8K compressed-quality preservation fails. QMSum passes the
preregistered lexical-quality tolerance. This report does not claim exact-token
parity, QMSum semantic correctness, or a CC-DFlash pipeline speedup.

## Preflight and execution status

- Preflight: PASS. Frozen config hash, model identities, seed 42, temperature 0,
  SDPA-math policy, generation limits, GSM8K v5 instruction, CUDA availability,
  idle GPU ownership, selector contract, and fresh cache paths all passed.
- Focused preflight tests: 65/65 passed. Final full regression suite: 97/97
  passed.
- Deterministic input construction: two byte-identical n20 builds; the validated
  n10 cohort is the prefix and the ten-sample extension was frozen before model
  execution by seed-42 SHA-256 coordinate ranking without reference use.
- Execution: 160/160 measured rows plus eight separate warmup rows completed.
  Each condition loaded once, each cache compressed once, every row was fsynced,
  and all row-checksum sidecars validate. No interruption or resume occurred.
- Compressor: `cuda:0` for both datasets; no silent CPU fallback.

## Quality

### GSM8K n=20

| Condition | Numeric EM | Correct | Parser failures | Empty outputs |
|---|---:|---:|---:|---:|
| C1 Baseline-AR | 0.90 | 18/20 | 0 | 0 |
| C2 DFlash-R1 | 0.90 | 18/20 | 0 | 0 |
| C3 LLMLingua-AR-R2 | 0.75 | 15/20 | 1 | 0 |
| C4 CC-DFlash-R2 | 0.75 | 15/20 | 1 | 0 |

Both required GSM8K preservation gates fail: C3 is below C1 and C4 is below
C2 by 3/20, or 0.15 absolute EM. The parser itself is functional and its status
and scores independently recompute; the two compressed-condition parse failures
are model-output quality failures, not missing or corrupt benchmark evidence.

### QMSum query-aware budgeted-context benchmark

This is not full-context QMSum. ROUGE-L is a lexical proxy and semantic
correctness is `NOT_CLAIMED`.

| Condition | Precision | Recall | F1 | Empty outputs |
|---|---:|---:|---:|---:|
| C1 Baseline-AR | 0.247563 | 0.178257 | 0.191438 | 0 |
| C2 DFlash-R1 | 0.257907 | 0.181182 | 0.198417 | 0 |
| C3 LLMLingua-AR-R2 | 0.263216 | 0.192222 | 0.193270 | 0 |
| C4 CC-DFlash-R2 | 0.259353 | 0.191915 | 0.192153 | 0 |

C3 is 0.001832 above C1. C4 is 0.006264 below C2, within the
preregistered maximum absolute mean-F1 drop of 0.01. QMSum lexical-quality
preservation therefore passes.

## Token reduction by source

The sources are kept separate rather than attributing all reduction to
LLMLingua.

| Dataset and source | Before | After | Keep rate | Reduction |
|---|---:|---:|---:|---:|
| GSM8K v4 → v5 instruction, mean target-user tokens | 132.25 | 96.25 | 72.779% | 36.00 tokens |
| GSM8K LLMLingua after v5, mean target-user tokens | 96.25 | 94.05 | 97.729% | 2.20 tokens |
| GSM8K LLMLingua after v5, mean full-input tokens | 167.25 | 165.05 | 98.694% | 2.20 tokens |
| QMSum full transcript → selected context | — | — | 9.268% | 90.732% |
| QMSum selected context → LLMLingua context | — | — | 90.783% | 9.217% |
| QMSum full transcript → compressed context | — | — | 8.349% | 91.651% |

The GSM8K instruction comparison is a tokenizer-only counterfactual over the
same 20 questions; no v4 benchmark was rerun. QMSum target-user prompt tokens
average 966.25 before LLMLingua and 880.70 after it; full chat input averages
1037.25 and 951.70 respectively.

Fallbacks: **0/20 GSM8K and 0/20 QMSum**.

## Performance

All values below are means in milliseconds or tokens/second. Pipeline latency
includes compressor latency for C3/C4.

### Per-condition latency and throughput

| Dataset | Condition | Generation ms | Compressor ms | Pipeline ms | Decode tok/s | Pipeline tok/s |
|---|---|---:|---:|---:|---:|---:|
| GSM8K | C1 | 3774.178 | — | 3774.178 | 31.979 | 31.378 |
| GSM8K | C2 | 1126.055 | — | 1126.055 | 114.638 | 105.160 |
| GSM8K | C3 | 3451.959 | 87.161 | 3539.120 | 31.644 | 30.161 |
| GSM8K | C4 | 1089.115 | 87.161 | 1176.276 | 110.446 | 92.551 |
| QMSum | C1 | 3000.285 | — | 3000.285 | 22.744 | 17.006 |
| QMSum | C2 | 2012.811 | — | 2012.811 | 41.601 | 24.734 |
| QMSum | C3 | 3133.530 | 619.755 | 3753.285 | 23.860 | 14.125 |
| QMSum | C4 | 2223.292 | 619.755 | 2843.047 | 40.901 | 18.881 |

### Required comparisons

| Dataset | Comparison | Pipeline latency delta | Delta % | Decode tok/s delta | Pipeline tok/s delta |
|---|---|---:|---:|---:|---:|
| GSM8K | C1 → C2, DFlash uncompressed | -2648.123 ms | -70.164% | +82.660 | +73.782 |
| GSM8K | C3 → C4, DFlash compressed | -2362.843 ms | -66.764% | +78.802 | +62.390 |
| GSM8K | C1 → C3, compression on AR | -235.058 ms | -6.228% | -0.334 | -1.217 |
| GSM8K | C2 → C4, CC-DFlash vs DFlash | **+50.222 ms** | **+4.460%** | -4.192 | -12.610 |
| QMSum | C1 → C2, DFlash uncompressed | -987.473 ms | -32.913% | +18.857 | +7.728 |
| QMSum | C3 → C4, DFlash compressed | -910.238 ms | -24.252% | +17.041 | +4.755 |
| QMSum | C1 → C3, compression on AR | +753.000 ms | +25.098% | +1.115 | -2.881 |
| QMSum | C2 → C4, CC-DFlash vs DFlash | **+830.236 ms** | **+41.248%** | -0.700 | -5.854 |

C4 is slower than C2 end-to-end for both datasets after compressor overhead.
No CC-DFlash pipeline speedup claim is supported.

## Exact-token parity diagnostic

Verifier and canonical parity policy were unchanged.

| Dataset | C1/C2 exact | C3/C4 exact |
|---|---:|---:|
| GSM8K | 15/20 | 17/20 |
| QMSum | 15/20 | 17/20 |

Mismatch sample IDs and first mismatch indices are retained in
`parity-diagnostics.json`. These diagnostic mismatches are not relabeled PASS.

## Hard validity and integrity gates

| Gate | Result | Evidence boundary |
|---|:---:|---|
| Deterministic n20 selection | PASS | 20 unique locked IDs per dataset; double-build hashes match |
| Raw completeness | PASS | 84/84 rows per dataset, including four warmups |
| Raw uniqueness and order | PASS | Unique composite keys in manifest order |
| Raw and cache row checksums | PASS | Every sidecar SHA-256 matches canonical row bytes |
| Independent metric recomputation | PASS | No row-level metric or evaluator mismatch |
| C1/C2 original-prompt fairness | PASS | 20/20 prompt hashes match per dataset |
| C3/C4 compressed-cache fairness | PASS | 20/20 prompt/cache hashes match per dataset |
| Samples and references shared | PASS | Same ordered IDs and references across C1-C4 |
| Compression cache freshness | PASS | New single run ID per dataset; 20 unique ordered rows |
| Compressor CUDA | PASS | Requested and resolved `cuda:0`; no CPU fallback |
| Parser/evaluator functioning | PASS | Independent status and score recomputation matches raw |
| Output non-empty | PASS | 0 empty outputs in all eight conditions |
| QMSum selector deterministic/shared | PASS | Same selection and selected-context hash across C1-C4; no reference input |
| Config/runtime consistency | PASS | Frozen config hash, seed, SDPA math, models, and generation policy match |
| Condition isolation/GPU release | PASS | Eight empty pre/post compute-process boundaries per dataset |
| Package input source hashes | PASS | Source/config unchanged since preflight |

## Failed claims and limitations

- GSM8K compressed quality preservation fails at 15/20 versus 18/20 for both
  AR and DFlash pairs; C3 and C4 each have one parse failure.
- QMSum is query-aware selected-context evaluation. Its lexical ROUGE-L proxy
  does not establish semantic sufficiency or full-transcript quality.
- Exact generated-token parity is 15/20 and 17/20 for each dataset pair; it is
  diagnostic only.
- C4 pipeline E2E is slower than C2 for both datasets, so decode-only gains do
  not support a CC-DFlash speedup claim.
- Timing comes from one RTX 4070 Laptop GPU, one warmup, and one measured
  repetition per sample; variance and host conditions limit generalization.
- LLMLingua emitted a tokenizer maximum-length warning during QMSum compression,
  but all 20 cache rows completed, passed safeguard validation, and were reused
  consistently. This remains an environment/model-limit caveat.
- The n20 extension is a preregistered seed-42 coordinate-hash extension of the
  validated n10 prefix, not a post-result sample substitution.

The first derived classification that conflated GSM8K model-output quality with
pipeline invalidity is preserved as `gsm8k/audit-preclassification.json` and
`final-decision-preclassification.json`, with its original stdout in
`finalize.initial.stdout.json`. `classification-audit.json` records the
policy-correct separation; no raw evidence was modified.
