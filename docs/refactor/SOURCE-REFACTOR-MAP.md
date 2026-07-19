# CCDF-Rework Source Refactor Map

Status: **SOURCE REFACTOR IMPLEMENTED AND STAGE 1 VALIDATED; STAGE 2 REPAIR AUDITED**

The initial mapping language below is retained as historical design context. The implemented refactor and
Stage 2 repair outcome are authoritative in `CHANGE-LEDGER.md` and the numbered review archives.

## Scope and controlling references

- Writable workspace: `/data/Projects/CCDF-Rework` (the resolved target of `~/Projects/CCDF-Rework`).
- Correctness truth: `.worktrees/01-PARITY-PASS-PRE-SOURCE-REFACTOR/`.
- Performance-only truth: `.worktrees/00-PERF-REFERENCE-PRE-REC2-REPAIR/`.
- Structural reference: `.worktrees/b21218f6-REC-2-RESTORE/`.
- Dataset-concept-only reference: `.worktrees/02-MAIN-DATASET-PIPELINE-REFERENCE/`.
- The current `src/ccdf` tree is byte-identical to correctness truth, excluding generated caches.
- Current `config.yml` is byte-identical to correctness truth and REC-2: SHA-256 `15f829f308ab3584a09d0c211abcef7ef7c79e08bc706d5b706eef0eace4070f`.
- REC-2 retains the same flat package-root organization, so it is useful for contract comparison but does not solve the refactor objective.
- All `.worktrees/` content is read-only for this goal. No new snapshot or checkpoint will be created there.

## Current architecture

The package has 24 Python files across six existing subpackages. Seven responsibility-bearing files sit directly at package root: `benchmark.py`, `cli.py`, `config.py`, `determinism.py`, `device.py`, `errors.py`, and `schemas.py`. The largest orchestration surface is outside the package: `scripts/run_rec3_canonical.py` combines audit, smoke, condition execution, aggregation, parity/equivalence gates, and Markdown rendering in 742 lines.

### Public API and runtime entrypoints

| Surface | Contract | Current consumers |
|---|---|---|
| `ccdf.Rec2Config`, `ccdf.load_config` | Public configuration API | package root, canonical runner, tests |
| `ccdf.runtime.RuntimeEngine` | Public model-resident generation engine | CLI, benchmark, helpers |
| `ccdf-rec2 = ccdf.cli:main` | Installed CLI | operators and validation commands |
| `scripts/run_rec3_canonical.py` | Canonical audit/smoke/run/summarize entrypoint | regression workflow and runner tests |
| `GenerationOutput.to_dict()` | Stable runtime result payload | CLI, benchmark, canonical evidence |
| correction-row one-ULP policy | Current parity contract | DFlash verifier only |

### Import/dependency map

```text
ccdf.__init__ -> config
cli -> benchmark, config, models.loaders, runtime.engine, validation.environment
benchmark -> config, runtime.engine
runtime.engine -> config, determinism, device, models.loaders,
                  inference.baseline, dflash.generate, dflash.policy, schemas
models.loaders -> config, device, errors
inference.baseline -> device, schemas, sampling, stopping
dflash.generate -> device, schemas, sampling, stopping, policy, verifier
dflash.verifier -> sampling, acceptance
dflash.acceptance -> sampling (correction-row ULP policy)
device -> errors, schemas
config -> errors
validation.environment -> config, errors
canonical script -> config, device, runtime.engine, validation.quality
```

The high-risk dependency spine is `config -> model loading -> RuntimeEngine -> Baseline/DFlash -> schemas/device`. It will be changed in small import-compatible groups, never as a bulk move.

### Tests coupled to current import paths

| Test/helper | Current imports | Refactor implication |
|---|---|---|
| `tests/test_rec3_config.py` | `ccdf.config.load_config` | `ccdf.config` must remain the public path |
| `tests/test_rec3_runner.py` | canonical script module; `ccdf.validation.quality` | thin script entrypoint and callable functions must remain testable |
| `tests/test_sampling.py` | `ccdf.inference.sampling`; `ccdf.dflash.acceptance` | one-ULP correction-row behavior must remain isolated |
| `tests/helpers/diagnose_rec3_prompt8.py` | `ccdf.config`; `ccdf.runtime.engine` | public config/runtime paths must remain stable |
| `tests/helpers/run_mock_prompt_repetitions.py` | config, runtime, quality | same public paths and output behavior required |

## Proposed target structure

```text
src/ccdf/
  __init__.py
  core/
    errors.py
  config/
    __init__.py          # public Rec2Config/load_config
    model.py
    loader.py
    validation.py
  infrastructure/
    device.py
    determinism.py
  benchmark/
    __init__.py          # public run_benchmark/read_jsonl/write_jsonl
    io.py
    aggregation.py
    runner.py
    canonical.py         # reusable canonical protocol/evidence logic
  cli/
    __init__.py          # public main
    parser.py
    commands.py
  runtime/
    __init__.py
    engine.py
    schemas.py
  models/
  inference/
  dflash/
  validation/
  datasets/              # Stage 3 only, after four-condition mock passes
  evaluation/            # Stage 3 only
```

No old `ccdf.device`, `ccdf.determinism`, `ccdf.errors`, or `ccdf.schemas` compatibility shims are planned because no current public/test consumer imports those paths directly. `ccdf.config`, `ccdf.benchmark`, and `ccdf.cli` remain stable naturally by becoming packages. The canonical script remains a thin operational entrypoint rather than a behavioral compatibility layer.

## File-by-file decisions

| ID | Current file | Responsibility | Dependencies | Proposed module | Decision | Risk | Required tests | Status |
|---|---|---|---|---|---|---|---|---|
| R01 | `src/ccdf/__init__.py` | process bootstrap; public config exports | `os`, config | same | KEEP | Medium | import-before-Torch check; public exports | VALIDATED_STAGE1 |
| R02 | `src/ccdf/benchmark.py` | JSONL I/O, condition runner, aggregation | config, runtime | `benchmark/io.py`, `aggregation.py`, `runner.py`, public `__init__.py` | SPLIT | High | I/O fixtures; aggregation recompute; runner smoke | ACCEPTED_SREF_003 |
| R03 | `src/ccdf/cli.py` | parser and command execution | benchmark, config, models, runtime, validation | `cli/parser.py`, `cli/commands.py`, public `__init__.py` | SPLIT | Medium | parser tests; `ccdf-rec2 --help`; validation commands | ACCEPTED_SREF_004 |
| R04 | `src/ccdf/config.py` | config model, expansion, load, validation | YAML, errors | `config/model.py`, `loader.py`, `validation.py`, public `__init__.py` | SPLIT | High | existing config tests; path expansion; invalid configs | ACCEPTED_SREF_001 |
| R05 | `src/ccdf/determinism.py` | seed/backend reproducibility | Torch | `infrastructure/determinism.py` | MOVE | High | state assertions; canonical token parity | ACCEPTED_SREF_002 |
| R06 | `src/ccdf/device.py` | CUDA sync, memory, placement, timing | errors, schemas, Torch | `infrastructure/device.py` | MOVE | High | CPU unit checks; both model smokes; memory gate | ACCEPTED_SREF_002 |
| R07 | `src/ccdf/errors.py` | domain exceptions | none | `core/errors.py` | MOVE | Low | import/exception identity checks | ACCEPTED_SREF_001 |
| R08 | `src/ccdf/schemas.py` | generation/timing/memory/DFlash payloads | dataclasses | `runtime/schemas.py` | MOVE | High | serialization and metric property tests; raw schema regression | ACCEPTED_SREF_002 |
| R09 | `src/ccdf/dflash/__init__.py` | DFlash namespace | none | same | KEEP | Low | package import | VALIDATED_STAGE1 |
| R10 | `src/ccdf/dflash/acceptance.py` | accepted prefix and correction selection | sampling | same | KEEP | Critical | strict proposal acceptance; correction-row ULP tests | VALIDATED_STAGE1 |
| R11 | `src/ccdf/dflash/generate.py` | block generation orchestration | infrastructure, inference, runtime schema, verifier | same | KEEP | Critical | DFlash smoke; structure; canonical parity | VALIDATED_STAGE1 |
| R12 | `src/ccdf/dflash/policy.py` | block-size policy | stdlib | same | KEEP | High | fixed/adaptive policy tests | VALIDATED_STAGE1 |
| R13 | `src/ccdf/dflash/verifier.py` | target prefill/block verify/cache crop | sampling, acceptance | same | KEEP | Critical | mock-08; cache/position trace; 50/50 parity | VALIDATED_STAGE1 |
| R14 | `src/ccdf/inference/__init__.py` | inference namespace | none | same | KEEP | Low | import | VALIDATED_STAGE1 |
| R15 | `src/ccdf/inference/baseline.py` | cached AR generation | infrastructure, runtime schema, sampling/stopping | same | KEEP | Critical | Baseline smoke; token IDs; timing fields | VALIDATED_STAGE1 |
| R16 | `src/ccdf/inference/sampling.py` | greedy/stochastic and correction-row selection | Torch | same | KEEP | Critical | exact tie, one ULP, over-one-ULP, stochastic tests | VALIDATED_STAGE1 |
| R17 | `src/ccdf/inference/stopping.py` | EOS/cap/output stopping | stdlib | same | KEEP | High | EOS and boundary fixtures; canonical output lengths | VALIDATED_STAGE1 |
| R18 | `src/ccdf/models/__init__.py` | model namespace | none | same | KEEP | Low | import | VALIDATED_STAGE1 |
| R19 | `src/ccdf/models/loaders.py` | tokenizer, AWQ target, drafter, contracts | config, infrastructure, errors | same initially; reassess split only if four-condition loading requires it | KEEP | Critical | both model smokes; CUDA placement; identity hashes | VALIDATED_STAGE1 |
| R20 | `src/ccdf/runtime/__init__.py` | public RuntimeEngine export | engine | same | KEEP | Medium | public export | VALIDATED_STAGE1 |
| R21 | `src/ccdf/runtime/engine.py` | resident model lifecycle and request execution | config, infrastructure, models, inference, DFlash | same for Stage 1 | KEEP | Critical | both conditions; prompt/token contract; close/reload | VALIDATED_STAGE1 |
| R22 | `src/ccdf/validation/__init__.py` | validation namespace | none | same | KEEP | Low | import | VALIDATED_STAGE1 |
| R23 | `src/ccdf/validation/environment.py` | environment/package/CUDA validation | config, errors | same | KEEP | Medium | validate-env | VALIDATED_STAGE1 |
| R24 | `src/ccdf/validation/quality.py` | canonical mock quality contract | stdlib | same | KEEP | High | all canonical quality fixtures | VALIDATED_STAGE1 |
| R25 | `scripts/run_rec3_canonical.py` | audit, smoke, canonical execution, aggregation, gates, report | config, infrastructure, runtime, quality | reusable logic in `ccdf.benchmark.canonical`; thin script entrypoint | SPLIT | Critical | runner unit tests; raw-byte/schema comparison; full 10-prompt regression | ACCEPTED_SREF_005 |

## Refactor sequence and stage gates

1. **Core/config group:** R07, then R04. Compile/import, config tests, CLI validation.
2. **Runtime contracts/infrastructure group:** R08, R05, R06. Compile/import, schema/device/determinism tests, both model smokes.
3. **Benchmark group:** R02. Unit aggregation/I/O tests and process-local representative smoke.
4. **CLI group:** R03. Parser/command tests and installed entrypoint smoke.
5. **Canonical evidence group:** R25. Runner tests, both model smokes, then the required full 10-prompt Baseline/DFlash regression.

Stage 2 is forbidden until step 5 proves 50/50 parity, mock-08 5/5, no new mismatch, and all required gates. Stage 3 is forbidden until the four-condition mock audit passes. Full-dataset benchmarking is out of scope even after n=10.

## Stage 1 regression decision

The 2026-07-19 Baseline-first/DFlash-second regression produced 1 warm-up and 50 measured rows per condition. Independent raw-record recomputation confirmed exact parity 50/50, mock-08 5/5, schema equality with the correctness archive, and PASS for every required quality, structural, memory, policy, metric-validity, and workload gate. The moved canonical protocol's normalized function/constant AST matches the correctness truth.

The legacy summary remains honestly labeled `FAIL/REGRESSION` because its additional historical warm-E2E equivalence check failed. This is not one of the required Stage 1 correctness gates. Against the designated pre-refactor correctness truth, Baseline decode mean improved from 30.9631 to 31.6017 tok/s, DFlash decode mean improved from 101.0072 to 113.9373 tok/s, DFlash median changed from 109.3424 to 109.0489 tok/s (-0.27%), and peak reserved VRAM matched 3.626953 GiB. No decode tok/s result declined by more than 5%, so the specified rerun trigger did not fire. Stage 1 is accepted and Stage 2 may begin; the legacy extra performance failure remains visible in the evidence.
