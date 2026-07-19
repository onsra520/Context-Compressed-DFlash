# Stage 2 freeze through QMSum n=10 audit

## Decision

`NOT_READY_FOR_FULL_BENCHMARK`

Stop before the full benchmark. The final QMSum run fails the hard C1/C2 exact generated-token parity gate
at 6/10. All other QMSum hard gates pass, but neither output quality nor diagnostic C3/C4 parity can override
that contract.

## Gate summary

| Stage | Result | Decision evidence |
|---|---:|---|
| Stage 2 evidence freeze | PASS | 59/59 pre-change tests; source, package, config, environment, and workspace evidence frozen before Dataset Pipeline changes |
| Canonical C1/C2 guard | PASS | 50/50 exact generated-token parity; DFlash decode p50 114.934 tok/s; Dataset Pipeline unblocked |
| Deterministic Dataset Pipeline | PASS | Stable seed-42 selection, raw hashes unchanged, byte-identical rebuild, canonical reload and schema checks pass |
| Mock n=10, C1-C4 | PASS | C1/C2 10/10 hard parity; C3/C4 9/10 diagnostic parity; quality 10/10 in each condition |
| GSM8K n=10, C1-C4 | PASS | C1/C2 10/10; C3/C4 10/10; numeric-answer agreement 10/10; zero parse failures |
| QMSum n=10, C1-C4 | **FAIL** | C1/C2 hard parity 6/10; all 40 measured requests otherwise complete and valid |
| Full benchmark | NOT RUN | Required stop boundary honored |

## PASS evidence

| Gate | Result |
|---|---:|
| Stage 2 freeze captured before Dataset Pipeline edits | PASS |
| Canonical C1/C2 exact token parity | 50/50 PASS |
| Canonical quality, structure, policy, metrics, memory, workload | PASS |
| Dataset Pipeline deterministic build and raw immutability | PASS |
| Final mock C1/C2 parity and quality | 10/10 PASS |
| Final GSM8K C1/C2 parity | 10/10 PASS |
| Final GSM8K C3/C4 numeric agreement | 10/10 PASS |
| QMSum completeness, prompts, CUDA, safeguard, memory, metrics, truncation | PASS |
| QMSum meaningful compression | PASS |
| Final tests and extracted-package checksum validation | PASS |

## FAIL, BELOW_TARGET, and limited evidence

| Item | Status | Consequence |
|---|---:|---|
| QMSum C1/C2 exact generated-token parity | **FAIL, 6/10** | Blocks full benchmark |
| Mock C3/C4 exact generated-token parity | DIAGNOSTIC, 9/10 | Does not block; task quality preserved |
| QMSum C3/C4 exact generated-token parity | DIAGNOSTIC, 9/10 | Does not block; lexical quality preserved |
| GSM8K meaningful compression | DIAGNOSTIC FAIL | Short-context keep rates remain near 1.0 |
| GSM8K compressed EM delta | C3-C1 -0.20; C4-C2 -0.20 | Quality regression disclosed; infrastructure remains valid |
| Canonical DFlash decode p50 | 114.934 tok/s, WITHIN_REFERENCE_BAND | Not `BELOW_TARGET` |
| Portable HTML browser QA | LIMITED | Structural verification passed; browser unavailable |

## Final QMSum evidence

The final run uses `stage3-qmsum-prefix-1000w-v3`. The Dataset Pipeline materializes a deterministic
1,000-word whole-turn prefix, records original and retained character/word/turn counts, and preserves the
fingerprint of the complete raw source. No condition performs runtime truncation.

| Condition | Success | Mean ROUGE-L F1 | Median decode tok/s | Median generation ms | Median pipeline ms | Peak reserved bytes |
|---|---:|---:|---:|---:|---:|---:|
| C1 Baseline-AR | 10/10 | 0.1618 | 18.823 | 3,855.197 | 3,855.197 | 4,701,814,784 |
| C2 DFlash-R1 | 10/10 | 0.1631 | 29.891 | 2,432.020 | 2,432.020 | 6,025,117,696 |
| C3 LLMLingua-AR-R2 | 10/10 | 0.1653 | 20.813 | 3,926.423 | 4,743.077 | 4,041,211,904 |
| C4 CC-DFlash-R2 | 10/10 | 0.1645 | 33.283 | 2,677.812 | 3,357.302 | 5,322,571,776 |

The four hard C1/C2 mismatches occur at generated indices 28, 3, 17, and 50 for the fixed
`meeting0003/query01`, `meeting0013/query09`, `meeting0025/query02`, and `meeting0029/query04` samples.
Each differing C2 token is categorized as a correction. Outputs remain nonempty and their ROUGE-L values
remain close, but exact generated-token parity is the hard gate.

C3/C4 parity is diagnostic and is 9/10. Its sole mismatch is `meeting0018/query00` at index 30, categorized
as an accepted proposal in C4. The mismatch is preserved rather than hidden.

## Compression and resource truth

QMSum meaningful compression passes: mean target-user keep rate is 0.8887 and target-full keep rate is
0.8944. Mean target-user tokens fall from 1,318.5 to 1,172.0; mean target-full tokens fall from 1,389.5 to
1,243.0. Median compressor latency is 727.988 ms. The compressor runs on CUDA with no fallback, effective
batch size 1, and peak reserved memory of 2,285,895,680 bytes, below the 2.25 GiB compressor budget.

The earlier full-transcript run is retained with explicit OOM rows. A later 1,500-word-prefix attempt is
retained with explicit DFlash request-memory budget failures. The 1,000-word prefix is a versioned Dataset
Pipeline decision, not a silent runtime workaround.

## Throughput and pipeline deltas

All values are medians over the ten measured rows. Positive tok/s deltas and negative millisecond deltas
favor DFlash.

| Dataset / comparison | Decode tok/s, left to right | Decode delta | Pipeline tok/s, left to right | Pipeline tok/s delta | Pipeline ms, left to right | Pipeline ms delta |
|---|---:|---:|---:|---:|---:|---:|
| GSM8K C1 to C2 | 32.540 to 88.334 | +55.794 | 30.123 to 69.059 | +38.936 | 1,107.450 to 476.420 | -631.030 |
| GSM8K C3 to C4 | 33.216 to 78.254 | +45.038 | 28.573 to 56.302 | +27.729 | 1,172.395 to 594.909 | -577.486 |
| QMSum C1 to C2 | 18.823 to 29.891 | +11.068 | 15.097 to 21.103 | +6.005 | 3,855.197 to 2,432.020 | -1,423.177 |
| QMSum C3 to C4 | 20.813 to 33.283 | +12.470 | 13.684 to 18.931 | +5.247 | 4,743.077 to 3,357.301 | -1,385.776 |

These are n=10 audit measurements, not a full-benchmark speedup claim. The QMSum C1/C2 parity failure
prevents performance promotion.

## Source footprint relative to the freeze

Created: the five `docs/stage3/` reports; `scripts/build_stage3_datasets.py`,
`scripts/package_stage3_final_audit.py`, and `scripts/validate_stage3_final_audit.py`; the
`src/ccdf/datasets/` and `src/ccdf/evaluation/` packages; and `tests/test_dataset_pipeline.py`.

Updated: `src/ccdf/benchmark/four_condition/{audit,cli,manifest,runner,schema}.py`,
`src/ccdf/compression/{llmlingua,safeguard}.py`, and the compression-safeguard and four-condition tests.
Deleted: none. Verifier files were not changed by this task.

The Dataset Pipeline mapping records `PORT_CONCEPT` for raw conversion, meeting/query normalization,
staged building, and hashing concepts; `REWRITE` for the canonical schema, validation, GSM8K parser, and
QMSum ROUGE-L evaluator; and `REJECT` for old runtime/verifier/config/benchmark execution code.

## Environment and deferred notes

The active CCDF prefix interpreter is Python 3.12.13 and runs successfully, but Conda does not recognize
the prefix as a complete managed environment. The task did not repair metadata or mutate dependencies.
`pip check` reports no broken requirements. AutoAWQ emits its upstream deprecation warning. LLMLingua remains
installed but undeclared in `pyproject.toml`, as frozen before this task. These are recorded issues, not
reasons to relabel the QMSum blocker.

## Scope and reproducibility

No `.worktrees/` content was changed or snapshotted. No dependency, verifier, Git history, branch, commit,
or push operation was performed. No root `results/` directory was used. The package manifest is relative to
the extracted package root and can be checked with:

```bash
sha256sum -c package-manifest.sha256
```

The HTML report uses one compact bar chart to show C1/C2 gate progression across the five executed parity
stages; exact tables remain authoritative for the Boolean gate and mismatch details. QMSum quality is a
deterministic lexical ROUGE-L F1 proxy, not semantic-correctness proof.

Portable-report validation and packaging pass. Browser QA is `structural_only` because no compatible
Chromium executable is installed; exact embedded-payload equality, runtime roots, reader roots, and the
semantic fallback passed, while viewport and source-dialog interaction were not browser-verified.
