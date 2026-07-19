# Source Refactor and Four-Condition Change Ledger

This ledger is append-only for this goal. `.worktrees/` is read-only and no filesystem checkpoint will be created there.

## Initial architecture audit

- Timestamp: 2026-07-19.
- Code changes before mapping: none.
- Current package: 24 Python files; seven responsibility-bearing root files plus `__init__.py`.
- Current correctness identity: `src/ccdf` matches `01-PARITY-PASS-PRE-SOURCE-REFACTOR` byte-for-byte, excluding generated caches.
- Current config identity: SHA-256 `15f829f308ab3584a09d0c211abcef7ef7c79e08bc706d5b706eef0eace4070f`, matching correctness truth and REC-2.
- Structural comparison: REC-2 uses the same flat root layout; the old main reference has richer packages but is rejected as runtime truth and will only inform dataset concepts in Stage 3.
- Existing public contracts: `ccdf.Rec2Config`, `ccdf.load_config`, `ccdf.runtime.RuntimeEngine`, `ccdf-rec2`, `GenerationOutput.to_dict()`, and canonical script subcommands.
- Existing test coupling: config/runtime/quality/sampling public paths and direct canonical-script module loading.
- Pre-existing workspace changes preserved: `.gitignore`, `config.yml`, deleted review-history `.gitkeep`, parity-repair source files, quality evaluator, `.vscode/`, `data/`, `docs/restore/`.
- Initial decision: proceed subsystem-by-subsystem in the order recorded in `SOURCE-REFACTOR-MAP.md`; do not begin Stage 2 until canonical refactor regression passes.

## Change entries

### SREF-001 — split configuration and move domain errors

- Subsystem: core/config.
- Before: root `config.py` mixed typed access, YAML loading/expansion, and validation; root `errors.py` held domain exceptions.
- After: `config/model.py`, `config/loader.py`, `config/validation.py`, public `config/__init__.py`, and `core/errors.py`.
- Reference role: behavior is preserved from correctness truth; REC-2 has the same mixed files and was not copied.
- Import contract: `ccdf.Rec2Config`, `ccdf.load_config`, and `ccdf.config` remain stable naturally through the package; no compatibility shim was added for private `ccdf.errors`.
- Behavior-preservation hypothesis: only responsibility and import location change; config keys, validation order/messages, expansion, profiles, warnings, and exceptions remain equivalent.
- Validation: compile/import PASS; 14/14 CPU tests PASS; public-import identity PASS; `validate-config` PASS with the same reserve warning; isolated Baseline and DFlash model smokes PASS; GPU released between smokes.
- Canonical impact: not run yet; deferred to the required Stage 1 full regression after all mapped refactor groups.
- Decision: ACCEPT.
- Remaining risk: configuration imports are on the critical model-load path; subsequent infrastructure moves must rerun both model smokes.

### SREF-002 — move runtime contracts and infrastructure

- Subsystem: runtime contracts/infrastructure.
- Before: root `schemas.py`, `determinism.py`, and `device.py`; importing a runtime schema through the runtime package eagerly imported the engine.
- After: `runtime/schemas.py`, `infrastructure/determinism.py`, and `infrastructure/device.py`; `runtime.RuntimeEngine` is a lazy public export that avoids the low-level schema/device/engine cycle.
- Reference role: implementations preserve correctness-truth behavior; no runtime source was taken from the old dataset-pipeline reference.
- Import contract: `from ccdf.runtime import RuntimeEngine` remains supported; no shims were added for the mapped-private root modules.
- Behavior-preservation hypothesis: data fields, derived metrics, deterministic backend settings, CUDA synchronization, placement checks, event timing, and memory-gate semantics are unchanged; only module ownership and import timing change.
- Validation: compile/import PASS; 18/18 CPU tests PASS, including four new schema/determinism/event tests; `validate-config` and `validate-env` PASS; isolated Baseline and DFlash model smokes PASS; observed peak reserved memory was 2.500 GiB and 3.512 GiB respectively, with the DFlash memory gate passing; GPU released between smokes. Ruff was not available in the locked CCDF environment and was not installed.
- Canonical impact: not run yet; deferred to the required Stage 1 full regression after all mapped refactor groups.
- Decision: ACCEPT.
- Remaining risk: the canonical path depends on exact serialization and CUDA event behavior; the final Stage 1 regression remains the authority for token and measurement equivalence.

### SREF-003 — split benchmark I/O, aggregation, and execution

- Subsystem: benchmark helper.
- Before: root `benchmark.py` combined JSONL validation/writes, metric aggregation, model lifecycle, repetition loops, and summary persistence.
- After: `benchmark/io.py`, `benchmark/aggregation.py`, `benchmark/runner.py`, and a public `benchmark/__init__.py` preserving `read_jsonl`, `write_jsonl`, and `run_benchmark`; the previous private `_summarize` name remains available for compatibility.
- Reference role: functions were separated directly from correctness-truth source; no old dataset-pipeline benchmark or runtime code was used.
- Behavior-preservation hypothesis: input validation, Unicode/sorted JSONL output, warm-up/repetition order, condition-local engine lifecycle, metric formulas, memory-gate reduction, and output paths are unchanged.
- Validation: compile/import PASS; 23/23 CPU tests PASS, including JSONL round-trip and line diagnostics, independent aggregate recomputation, memory-gate reduction, engine-close behavior, and runner artifact persistence; public benchmark imports and CLI help PASS.
- Canonical impact: not run yet; deferred to the required Stage 1 full regression after all mapped refactor groups.
- Decision: ACCEPT.
- Remaining risk: this helper is distinct from the canonical runner; canonical orchestration and aggregate equivalence are still gated separately.

### SREF-004 — split CLI parsing and command dispatch

- Subsystem: CLI.
- Before: root `cli.py` combined parser construction, command dispatch, model lifecycle, benchmark invocation, and JSON rendering.
- After: `cli/parser.py`, `cli/commands.py`, public `cli/__init__.py`, and `cli/__main__.py`; the configured `ccdf-rec2 = ccdf.cli:main` target remains valid and `python -m ccdf.cli` is explicit.
- Reference role: command behavior was separated directly from correctness-truth source; no reference runtime source was copied.
- Behavior-preservation hypothesis: subcommand names, arguments, defaults, choices, validation/model/run/benchmark execution, JSON formatting, return codes, and cleanup remain unchanged.
- Validation: compile/import PASS; 26/26 CPU tests PASS, including parser defaults/rejection and exact validation JSON assertions; `python -m ccdf.cli --help` and `validate-config` PASS. The current Conda editable-install metadata exposes no `ccdf-rec2` executable despite the unchanged `pyproject.toml` declaration, so executable invocation was not claimed and the environment was not reinstalled.
- Canonical impact: not run yet; the canonical runner imports package modules directly and remains separately gated.
- Decision: ACCEPT.
- Remaining risk: installed console-script generation must be rechecked if the project is installed into a fresh environment; source target and module execution are verified here.

### SREF-005 — extract canonical evidence protocol from script entrypoint

- Subsystem: canonical benchmark protocol.
- Before: `scripts/run_rec3_canonical.py` owned environment/source audit, isolated model smoke, canonical condition execution, raw-record construction, aggregation, gates, report rendering, parser, and process entrypoint.
- After: reusable behavior lives in `ccdf.benchmark.canonical`; the script is a thin operational adapter that explicitly re-exports its previously test-consumed callables and invokes `main`.
- Reference role: the current correctness-truth runner was moved intact; no performance-reference or old dataset-pipeline runtime implementation was used.
- Behavior-preservation hypothesis: function bodies, constants, CLI arguments, condition process isolation, raw schema, metric formulas, gates, and report text are byte-preserved; only module ownership and the entrypoint adapter change.
- Validation before canonical regression: compile/import PASS; 26/26 CPU tests PASS; direct script help and environment/source `audit` command PASS with schema `ccdf.rec3.canonical.v1`, 10 prompts, CUDA available, and all six source identities present.
- Canonical impact: mandatory Baseline-first/DFlash-second regression PASS for the required contract: 1 warm-up plus 50 measured rows per condition; exact generated-token parity 50/50; mock-08 5/5; quality, structural, memory, policy, metric-validity, and workload gates all PASS; no new mismatch. Independent validation also confirmed raw schema equality and normalized protocol AST equality with correctness truth.
- Performance impact: Baseline decode mean 31.6017 tok/s (+2.06% vs correctness truth); DFlash mean 113.9373 tok/s (+12.80%); DFlash median 109.0489 tok/s (-0.27%); DFlash peak reserved 3.626953 GiB (equal). The legacy runner's extra warm-E2E REC-2 equivalence gate remains FAIL and its overall `FAIL/REGRESSION` label is preserved; no decode tok/s decline crossed the specified 5% rerun threshold.
- Decision: ACCEPT for the required Stage 1 gate contract; Stage 2 is open.
- Remaining risk: warm-E2E speedup is below the runner's older REC-2 reference and must not be presented as a passing historical-performance claim.

### SREF-006 — unified four-condition runtime and GPU compressor

- Subsystem: compression/four-condition benchmark/measurement.
- Added: strict GPU-only `compression/llmlingua.py`; `benchmark/four_condition` condition definitions, schema, runner, audit, report, and CLI; thin `scripts/run_four_condition.py`; independent Stage 1 validator and four-condition diagnostic adapter; protocol and blocker documentation.
- Runtime instrumentation: DFlash component profiling now records per-block draft and verify CUDA events without synchronizing inside the decode loop. The canonical path keeps profiling disabled. AR-only and compressor-only unified fields are enforced as `null` when inapplicable.
- Fairness: exact four IDs only; one compression cache invocation reused by C3/C4; same sample order, tokenizer, seed, policy, stopping, and target; each condition in a distinct process with empty-GPU boundary evidence.
- Compressor validation: requested/resolved `cuda:0`; NVIDIA GeForce RTX 4070 Laptop GPU index 0; all parameters and buffers GPU-resident; actual dtype `float32`; no CPU fallback; model-load peak reserved 2.086 GiB and per-sample peak reserved at most 2.129 GiB; 2.25 GiB gate PASS; 10/10 non-empty cached prompts.
- Test validation: compile PASS; 30/30 tests PASS; `pip check` PASS; `git diff --check` PASS.
- Mock execution: 11 rows per condition (1 warm-up, 10 measured), four unique process IDs, all five captured GPU boundaries empty. Schema, status/error, metric applicability, sample order, cache reuse, pair input hashes/tokens, and C1/C2 exact parity 10/10 PASS.
- Blocker: C3/C4 exact parity 8/10. `mock-02` first differs at generated index 2 (553 vs 220, correction row). `mock-10` first differs at index 68 (21103 vs 284, proposal row). Target-forward diagnostics prove equal prompt IDs, logical prefix, positions, cache positions, and masks. Rowwise LM-head projection did not change the block winners, locating the drift inside the block-shaped transformer forward.
- Rejected repairs: no proposal-row ULP extension, no AR oracle/extra per-token verifier, no dtype/backend/model change, no compression/workload tuning, and no output substitution.
- Decision: protocol implementation ACCEPTED as auditable; Stage 2 gate FAIL. Stage 3 and Stage 4 remain unstarted by contract.
- Remaining risk: compressed-prompt exact parity is not supported universally by the current one-forward block verifier on this AWQ target.

Every source entry must record: change ID, subsystem, files before/after, reference role, behavior-preservation hypothesis, tests/smokes, canonical impact, decision, and remaining risk.

### S2R-001 — Stage 2 repair gate

- Subsystem: compression safeguard, four-condition evidence schema/runner/audit, configuration integrity.
- Added: generic semantic span segmentation and validation; manifest-owned schedules and prompt hashes;
  durable success/failure JSONL; separate compressor/target-user/target-full token spaces;
  generation-versus-pipeline E2E metrics; independent completeness, uniqueness, error, quality, parity,
  latency, throughput, compression, and memory recomputation.
- Changed: LLMLingua receives only compressible spans; both compressor budget declarations must match;
  cache and raw rows are fsynced individually; condition process peak is null because staged peaks were
  not measured simultaneously. No dependency or environment mutation was performed.
- Validation: 59 CPU tests PASS; R1 and representative R2 PASS; final R3 has C1/C2 10/10, C3/C4 9/10,
  compressed quality 10/10, safeguard 10/10, real target-token reduction 10/10, CUDA compressor and
  all evidence-integrity gates PASS.
- Verifier decision: unchanged. Block sizes 2/4/8/16, explicit Baseline mask, eager attention, and FP32
  attention candidates were diagnostic-only and rejected. Eager fixed `mock-04` but created a new
  proposal-row mismatch on `mock-05`; FP32 candidates changed outputs/quality. No oracle, replay,
  sequential verification, prompt/token rule, workload change, or epsilon was accepted.
- Canonical impact: the runtime verifier/source/config return to the preserved SDPA policy. R4/R5 were
  not run because the ordered R3 prerequisite failed; preserved pre-repair 50/50 evidence is referenced,
  not relabeled as a post-repair run.
- Decision: infrastructure repairs ACCEPTED; Stage 2 gate FAIL and Stage 3 remains closed.
- Remaining risk: AWQ FP16 target logits change winner between one-query and block-query forward shapes
  at `mock-04` generated index 1 (Baseline 353, DFlash 9; DFlash margin 0.28125). Resolving it under the
  prohibited-oracle/sequential/epsilon boundaries requires an external runtime/kernel change.
