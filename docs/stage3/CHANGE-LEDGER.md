# Stage 3 change ledger

The ledger is append-only for the Stage 2 freeze through QMSum n=10 audit. No `.worktrees/` mutation,
dependency change, Git history operation, branch, commit, or push is permitted.

## S3-000 - pre-change evidence freeze

- Status: COMPLETE.
- Source/package manifests, config, environment, selected package versions, and workspace state were saved
  before Dataset Pipeline code changes.
- Frozen status: tests 59/59; mock C1/C2 10/10; C3/C4 9/10 diagnostic at `mock-04`; quality and safeguard
  10/10; CUDA compressor PASS; canonical 50-run and stress NOT RUN.
- Decision: proceed only to canonical C1/C2 guard. Dataset source remains untouched until that guard passes.

## S3-001 - canonical C1/C2 guard

- Status: PASS for the Stage 3 hard-gate contract.
- Execution order: Baseline-AR first, GPU boundary clear, then DFlash-R1; one warm-up plus 50 measured
  requests per condition under deterministic SDPA-math.
- Exact generated-token parity: 50/50. The archived `mock-08` five-repetition check remains 5/5.
- Quality, structural, policy, metric-validity, memory, and workload gates: PASS.
- DFlash decode p50: 114.9341 tok/s. Delta versus 101.01: +13.9241; versus 113.94: +0.9941;
  versus 115.63: -0.6959 tok/s. Status: WITHIN_REFERENCE_BAND, not BELOW_TARGET.
- The legacy independent validator reports one schema check false because Stage 2 intentionally added the
  telemetry-only runtime key `component_profiling_enabled`. Baseline schema is unchanged, DFlash output
  tokens are exact, and no field was removed or retyped. This additive delta is recorded as a caveat, not
  relabeled as a Stage 3 hard-gate failure.
- Decision: Dataset Pipeline implementation is unblocked. No verifier or generation policy change was made.

## S3-002 - deterministic Dataset Pipeline

- Status: COMPLETE; pipeline audit PASS and 64/64 tests PASS.
- Added a canonical sample contract, read-only raw conversion, locked-coordinate seed-42 selection,
  source fingerprints, stable IDs, prompt versions, explicit QMSum full-transcript accounting, an anchored
  GSM8K numeric evaluator, and dependency-free QMSum ROUGE-L F1.
- Raw GSM8K and QMSum SHA-256 values match the source lock before and after the build. A second in-memory
  build was byte-identical, and both canonical n=10 files reload under the same validation contract.
- Reference decisions are recorded in `DATASET-PIPELINE-MAP.md`; all old runtime/verifier/benchmark code is
  REJECTED.

## S3-003 - shared-runner mock10 four-condition regression

- Status: PASS for all hard gates.
- C1/C2 exact generated-token parity: 10/10. Original prompt hashes: 10/10. C3/C4 compressed prompt hashes:
  10/10. Quality: 10/10 for each condition. CUDA compressor, safeguard, completeness, order, isolation,
  failure accounting, and independent metric recomputation: PASS.
- Diagnostic C3/C4 exact token parity: 9/10. `mock-04` first differs at generated index 1: C3 token 353
  (`autoregressive`) versus C4 token 9 (`correction`). Both decode to a correct final answer of 27 and both
  quality scores are 1.0.
- Mock target-token reduction remains diagnostic and is not used as evidence of long-context compression.
- Decision: GSM8K n=10 is unblocked. No verifier change was made.

## S3-004 - GSM8K n=10 four-condition audit

- Status: PASS for every hard gate after two documented prompt-contract iterations and final batch-size
  validation. Failed candidates remain under `gsm8k-attempt1-failed/`, `gsm8k-attempt2-failed/`, and
  `gsm8k-attempt3-c1c2/`; no sample was replaced and source IDs/order stayed fixed.
- Final general prompt version: `stage3-gsm8k-calculation-v4`. It requires a brief calculation plus an
  anchored finite-decimal final answer; the parser matches only a labeled numeric answer at output end and
  never uses substring matching.
- C1/C2 exact token parity: 10/10. C3/C4 exact token parity: 10/10. C3/C4 numeric-answer agreement: 10/10.
  Parse failures: 0 in every condition. All completeness, prompt hash, CUDA, safeguard, isolation, metric,
  duplicate/missing/error, and reference checks: PASS.
- Numeric EM: C1 0.50, C2 0.50, C3 0.30, C4 0.30. Compression delta: C3-C1 -0.20 and C4-C2 -0.20.
  This is a quality regression, not hidden or relabeled; protocol permits QMSum because infrastructure and
  hard audit are valid.
- Mean target-user keep rate: 0.9522; mean target-full keep rate: 0.9693. Meaningful compression is FAIL
  diagnostically on this short-context workload.
- Compressor no-op rows are valid when all semantic spans are protected. Preservation remains a hard gate;
  effective reduction is diagnostic. GPU batch size is fixed at 1 to remain under the 2.25 GiB reserved
  compressor budget and is emitted in compressor audit evidence.

## S3-005 - QMSum n=10 four-condition audit and stop decision

- Status: FAIL one hard gate; final decision `NOT_READY_FOR_FULL_BENCHMARK`. The full benchmark was not executed.
- The fixed seed-42 source IDs and order were retained across all attempts. The full-transcript attempt
  produced explicit target OOM failure rows. The explicit 1,500-word prefix attempt exceeded the 6 GiB
  DFlash request-memory budget on most rows. Both attempts remain archived as failed evidence.
- Final prompt version: `stage3-qmsum-prefix-1000w-v3`. The Dataset Pipeline, not the runtime, applies an
  explicit 1,000-word whole-turn prefix while retaining the full raw-source fingerprint and original versus
  retained character, word, and turn counts for every sample.
- Final execution completed 10/10 measured rows in each condition with no runtime failure, empty output, or
  hidden sample replacement. Schema, completeness, order, prompt hashes, CUDA compressor, 2.25 GiB
  compressor budget, 6 GiB request-memory budget, safeguard, isolation, metric recomputation, quality
  validity, truncation accounting, and C3/C4 compressed-input parity all PASS.
- Hard C1/C2 exact generated-token parity is 6/10 and therefore FAIL. The four mismatches are
  `meeting0003/query01` (index 28), `meeting0013/query09` (index 3), `meeting0025/query02` (index 17), and
  `meeting0029/query04` (index 50); each DFlash mismatch row is a correction. This hard gate is not relabeled
  by nonempty output or similar ROUGE-L.
- Diagnostic C3/C4 exact generated-token parity is 9/10. The mismatch is `meeting0018/query00` at index 30,
  where C4 uses an accepted proposal; both outputs are nonempty and retain measurable lexical quality.
- Mean ROUGE-L F1 is C1 0.1618, C2 0.1631, C3 0.1653, and C4 0.1645. Compression is meaningful on this
  workload: mean target-user keep rate 0.8887 and target-full keep rate 0.8944. The compressor reserved peak
  is 2,285,895,680 bytes, within its 2.25 GiB budget.
- Decision: stop before the full benchmark. No verifier, generation-policy, sample-selection, or environment
  change is authorized by this failure.
