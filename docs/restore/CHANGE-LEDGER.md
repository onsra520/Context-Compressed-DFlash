# REC-2 Controlled Restore Change Ledger

This ledger is append-only for restore experiments and accepted changes. Documentation initialization and read-only preflight are recorded below but are not runtime change IDs.

## Preflight record

- Authorized workspace paths resolve to `/data/Projects/CCDF-Rework`.
- `conda` environment: `CCDF`.
- Truth-source directory manifests: PASS before changes.
- Immutable archive hashes:
  - current-best: `c2888813b8acfc1e379dae7c2defcdc270333e6278c4f7db5b77ff2fdf9bf29e`
  - REC-2 base: `9c70257e8a3481be03ee061a280936217a2b9366f363ae5efb44209708be05fa`
- Baseline/target model config SHA-256: `cf74d40352c502483cca3a94fd8037dce0d7b31c21831f1721ff6ee360b50075`.
- Drafter config SHA-256: `2de97cdf48f429628074d229d024753f1ea02b575732983d6ed2bc882bbd63c8`.
- Drafter source SHA-256: `17ab761ba665a41965b27bdc3a1c6795d1b07b285ec1f0789ad146f2ee9c1cc5`.
- Config, environment, compile, six CPU tests, Baseline model smoke, and DFlash model smoke: PASS.
- Live canonical baseline: complete in independent Baseline-AR and DFlash-R1 processes.
  - Workload: 10 prompts, 1 warm-up, 5 measured repetitions per prompt and condition.
  - Baseline-AR mean decode throughput: 31.2469 tok/s.
  - DFlash-R1 mean decode throughput: 104.3243 tok/s.
  - Decode speedup: 3.3387x.
  - Exact generated-token parity: 45/50; `mock-08` failed 0/5 at generated-token index 21.
  - Passing gates: quality, structural, memory, policy, metric validity, workload.
  - Failing gates: exact generated-token parity and REC-2 workload-performance equivalence.
  - Raw evidence: `/tmp/ccdf-rec2-restore/live-baseline/`.
  - Decision: retain as immutable pre-change evidence; do not accept as final state.

## Change entries

### REC2-R001 — full mock-08 execution-contract diagnostic (before)

- Timestamp: 2026-07-19T11:40Z.
- Issue: exact generated-token mismatch at index 21 for all five `mock-08` repetitions.
- Before files: `tests/helpers/diagnose_rec3_prompt8.py`; no production source is changed by this entry.
- Referenced truth sources: both immutable trees; their runtime bytes match current, so neither contains a fuller diagnostic.
- Function/line: diagnostic helper `main`; target forwards remain in `TargetVerifier.prefill`, `TargetVerifier.verify`, and `generate_baseline`.
- Hypothesis: the existing logit probe is insufficient because it does not preserve actual proposal IDs or prove caller/effective masks, derived `cache_position`, per-layer KV state, selection offsets, and stopping state.
- Minimal change planned: replace the helper's approximate block reconstruction with instrumented, deterministic Baseline-AR and DFlash diagnostic requests and emit a single complete JSON contract trace.
- Required tests after edit: compile helper; Tier A CPU tests; one Baseline and one DFlash `mock-08` diagnostic request; raw-run reproduction assertion; truth-source manifest guard.
- Before metrics: Baseline-AR 31.2469 tok/s; DFlash-R1 104.3243 tok/s; 3.3387x decode speedup.
- Before parity: 45/50 overall, `mock-08` 0/5, first mismatch index 21 (`353` versus `24768`).
- Tests/results: helper compile PASS; six CPU tests PASS; both immutable source manifests PASS; isolated instrumented Baseline and DFlash requests reproduce their raw rows exactly.
- Diagnostic result: same prompt IDs, prefix, 176-token logical context, selected position/cache-position 175, visible keys 0..175, 36 FP16 CUDA KV layers, selected offset, and stopping contract. Baseline has an exact maximum tie between tokens 353 and 24768; q=16 block verification separates token 24768 by one FP16 ULP (0.03125).
- Before/after metrics and parity: unchanged because this is non-production instrumentation.
- Gates: Tier A PASS; targeted diagnostic PASS; canonical gates unchanged from the live baseline.
- Decision/checkpoint: ACCEPT diagnostic helper and evidence; checkpoint `02-rec2-r001-diagnostic-accepted.tar.gz`.

### REC2-R002 — verifier-local one-ULP greedy tie handling (before)

- Timestamp: 2026-07-19T11:52Z.
- Issue: q=16 target verification changes an exact q=1 FP16 tie into a one-ULP separation at the proven mismatch.
- Before/source/edited files: `src/ccdf/inference/sampling.py`, `src/ccdf/dflash/verifier.py`, and a focused sampling test; no model, backend, cache, draft, stopping, or metric code.
- Referenced truth source: keep byte-identical REC-2/current-best target verification and add only the compatibility rule absent from both immutable snapshots.
- Function/line: add a dedicated verifier selection helper; call it only for `TargetVerifier.verify` posterior IDs.
- Hypothesis: treating the immediately preceding representable FP value as the same greedy tie band, then choosing the lowest token ID, reproduces deterministic q=1 argmax without target replay or sequential fallback.
- Minimal change planned: for temperature-zero verifier logits only, select the lowest vocabulary ID within one dtype ULP of the maximum; preserve ordinary argmax for gaps over one ULP and preserve existing stochastic sampling.
- Required tests: exact tie, one-ULP, over-one-ULP, and stochastic-delegation unit tests; Tier A; both model smokes; isolated `mock-08`; then full canonical only if targeted parity passes.
- Before metrics/parity/gates: 31.2469 versus 104.3243 tok/s, 3.3387x, 45/50 overall, `mock-08` 0/5; quality/structural/memory/policy/metric/workload pass.
- Iteration 1: applying the band to every verifier row achieved canonical 50/50 at 102.1942 tok/s but performed unnecessary vocabulary work on accepted rows; not checkpointed.
- Iteration 2 minimal change: preserve strict proposal argmax and apply the one-ULP band only to the correction row at the first strict rejection. This is generic floating-point behavior, not an arbitrary tolerance or token-specific workaround.
- Tests: 11 CPU tests PASS; config/environment PASS; Baseline and DFlash smokes PASS; isolated `mock-08` 5/5 exact, deterministic, quality PASS, structural PASS; full canonical 50/50 exact.
- After canonical metrics: Baseline-AR 30.9631 tok/s; DFlash-R1 mean 101.0072, median 109.3424, min 39.8400, max 143.9852, stdev 25.9082 tok/s; 3.2622x decode speedup; 2.8718x warm E2E speedup; 3.626953 GiB peak reserved.
- After parity/gates: 50/50 overall, `mock-08` 5/5, no new mismatch; generated-token parity, quality, structural, memory, policy, metric validity, and workload PASS. The runner's REC-2 relative-speedup equivalence gate remains FAIL because Baseline improved 25.51% over REC-2 while DFlash improved 5.47%.
- Live-baseline delta: DFlash mean -3.18%, median +0.58%, warm throughput -1.81%, peak reserved +0.000 GiB; the required 3–5% mean band was rerun and remained within the 5% acceptance guardrail.
- Performance analysis: the tie-band microbenchmark adds about 0.018 ms per correction row versus argmax, far below request-level variance. During final runs, `kwin_wayland` held the display GPU and a 10-second out-of-band sample showed persistent 23–28% SM and 8% memory utilization plus PCIe traffic while otherwise idle. Historical evidence recorded 4 MiB GPU use; the live task recorded 42–45 MiB. This external contention explains why the preferred 110 tok/s mean was not reached. The accepted mean remains above REC-2's 95.7658 tok/s, and the median is within 2.3% of the 111.8847 current-best historical median.
- Decision/checkpoint: ACCEPT correctness repair under the explicit live-baseline guardrail and preserve the external absolute-performance blocker; checkpoint `03-rec2-r002-accepted.tar.gz`.

### REC2-R003 — optional audit identity for removed root debug backup (before)

- Timestamp: 2026-07-19T12:10Z.
- Issue: final `audit` fails after required cleanup removes root `config-backup.yml`, because the evidence runner unconditionally hashes that debug file.
- Before/source/edited files: `scripts/run_rec3_canonical.py` and focused runner test only.
- Referenced truth source: current-best runner contains the unconditional debug-file dependency; REC-2 has no canonical runner to restore.
- Function/line: `audit`, config identity fields.
- Hypothesis/minimal change: record backup path, existence, and nullable SHA-256 instead of requiring the file. Generation, models, prompts, timing, parity, and benchmark policy are untouched.
- Required tests: unit test absent identity; full Tier A; final audit; no canonical rerun because no runtime path changes.
- Before/after metrics and parity: frozen at accepted REC2-R002 evidence; no measured-run mutation.
- Tests/results: 11 CPU tests PASS; compile PASS; final audit PASS and records `backup_exists=false`, `backup_sha256=null`; root debug-file check PASS.
- Before/after metrics, parity, and gates: unchanged from REC2-R002 because the generation/runtime path is untouched.
- Decision/checkpoint: ACCEPT evidence-path compatibility; checkpoint `04-rec2-r003-accepted.tar.gz`.

Each future entry must include timestamp, issue, before/source/edited files, referenced truth source, function/line, hypothesis, minimal change, tests, before/after metrics, before/after parity, gates, ACCEPT/REVERT decision, and checkpoint.
