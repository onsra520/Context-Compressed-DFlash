# Phase 3.0 Low-Tier MVP Handoff and Track B→C Planning

## Summary

Phase 3.0 hands off `Low-Tier Diagnostic MVP v0.1` as a closed, reproducible diagnostic milestone and defines the next roadmap.

The recommended roadmap is:

```text
Track B first: Low-Tier Benchmark Readiness
Track C second: High-Tier Preparation
```

Benchmark Readiness comes before High-Tier Preparation so timing boundaries, repeatability policy, metrics schema, and no-claim reporting rules are clear before any high-tier backend or architecture work begins.

## Closed MVP

`Low-Tier Diagnostic MVP v0.1` is closed by Phase 2.17.

Fresh Phase 2.17 evidence:

```text
prompt_set_id: phase-2-controlled-eligibility-v2
prompt_count: 16
prompt_mode: raw
capture_raw_output: true

total_records: 16
valid_draft_continuation_count: 16
fallback_after_rejection_count: 0
fallback_only_count: 0
unknown_contribution_count: 0
baseline_empty_after_normalization_count: 0

selection_ready: yes
eligible_valid_draft_record_count: 16
excluded_empty_baseline_record_count: 0
excluded_fallback_derived_record_count: 0
excluded_unknown_contribution_record_count: 0
excluded_prompt_mode_risk_record_count: 0

pytest: 174 passed
forbidden-claim scan: clean
git diff check: clean
```

The closed MVP is diagnostic-only. It does not validate exact generation, final output quality, token-level behavior, benchmark claims, or high-tier behavior.

## Canonical Runtime Shape

The accepted low-tier runtime shape is:

```text
drafter  -> current Qwen3-0.6B on CPU
text_bridge
verifier -> current Gemma E2B on CUDA
```

The target role remains reserved for future high-tier work:

```text
target -> current/future Gemma E4B
```

## Canonical Prompt Set

The canonical MVP prompt set is:

```text
prompt_set_id: phase-2-controlled-eligibility-v2
prompt_count: 16
prompt_ids: elig2-001 through elig2-016
prompt_mode: raw
capture_raw_output: opt-in
```

This prompt set is for controlled diagnostic eligibility. It is not a broad model evaluation set.

## Canonical Commands

Fresh MVP reproduction commands:

```bash
cd ~/HTFS-Decoding
source .venv/bin/activate

.venv/bin/python scripts/check_env.py

.venv/bin/python scripts/run_low_tier_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v2

.venv/bin/python scripts/run_baseline_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v2

.venv/bin/python scripts/select_diagnostic_records.py \
  --low-tier logs/reports/<low-tier-v2-trace>.json \
  --baseline logs/reports/<baseline-v2-trace>.json

.venv/bin/python scripts/inspect_eligible_records.py \
  --low-tier logs/reports/<low-tier-v2-trace>.json \
  --baseline logs/reports/<baseline-v2-trace>.json

.venv/bin/pytest -v
```

Repository hygiene commands:

```bash
.venv/bin/python - <<'PY'
import subprocess

phrases = [
    "lossless " + "generation achieved",
    "lossless " + "equivalence",
    "output " + "equivalence achieved",
    "outputs " + "are equal",
    "output " + "parity achieved",
    "target " + "equivalence achieved",
    "2x " + "speedup",
    "4x " + "speedup",
    "benchmark " + "result",
    "performance " + "improvement",
    "draft " + "acceptance rate",
    "v" + "LLM",
    "v" + "llm",
]
pattern = "|".join(phrases)
paths = ["pyproject.toml", "src", "tests", "scripts", "configs", "README.md", "docs"]
raise SystemExit(subprocess.run(["rg", "-n", pattern, *paths]).returncode)
PY

git diff --check
```

## Canonical Artifacts

Canonical report:

```text
docs/reports/phase-2-17-low-tier-diagnostic-mvp-reproducibility-pack.md
```

Fresh Phase 2.17 local artifacts:

```text
low-tier trace:
  logs/reports/20260525T142702Z-low-tier-trace.json

target-baseline trace:
  logs/reports/20260525T142908Z-target-baseline-trace.json

diagnostic record selection:
  logs/reports/20260525T142959Z-diagnostic-record-selection.md
  logs/reports/20260525T142959Z-diagnostic-record-selection.json

eligible-record inspection:
  logs/reports/20260525T142959Z-eligible-record-inspection.md
  logs/reports/20260525T142959Z-eligible-record-inspection.json
```

Local trace artifacts under `logs/reports/` are reproducibility artifacts, not committed source artifacts.

## Stable APIs and Role-Based Names

Phase 2.16 stabilized MVP-facing names:

```text
drafter  -> current Qwen3-0.6B
verifier -> current Gemma E2B
target   -> current/future Gemma E4B
```

Canonical config keys:

```text
models.drafter
models.verifier
models.target
```

Canonical trace fields include:

```text
drafter_model_file
drafter_device_status
drafter_expected_device
drafter_n_gpu_layers
drafter_decode_tokens_per_second
verifier_model_file
verifier_device_status
verifier_expected_device
verifier_n_gpu_layers
verifier_decode_tokens_per_second
```

## Compatibility Notes

Deprecated model-specific config keys and trace aliases may remain during migration.

Compatibility aliases are useful for older local configs, fixtures, reports, and smoke-era scripts. New MVP-facing reports and trace consumers should prefer role-based fields.

## Known Limitations

```text
diagnostic only
no target-equivalence proof
no token-level verification
no speed or throughput benchmark
no high-tier hidden-state path
GGUF/llama.cpp may limit feature-level access
results are from local controlled traces
raw outputs are opt-in and should remain under ignored logs/reports/
v2 prompt set is for controlled diagnostic eligibility, not broad model evaluation
compatibility aliases remain during migration
```

## Non-Claims To Preserve

```text
This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No performance-improvement claim is made.
No draft-acceptance metric is reported.
No high-tier implementation claim is made.
```

## Candidate Phase 3 Tracks

### Track A: Low-Tier Improvement

Goal:

```text
Improve low-tier diagnostic behavior while preserving the existing selector and non-claim boundaries.
```

What it would add:

```text
additional prompt-shape experiments
bridge normalization refinements
fallback reason analysis
low-tier output health improvements
```

What it must not claim yet:

```text
output parity
target equivalence
correctness
lossless generation
benchmark claim
draft-acceptance metric
```

Risk:

```text
It may optimize diagnostic fixtures before timing and measurement boundaries are stable.
```

Suggested first phase:

```text
Phase 3.A1: Low-Tier Diagnostic Prompt and Bridge Improvement Design
```

### Track B: Benchmark Readiness

Goal:

```text
Prepare a clean low-tier measurement layer without making benchmark claims.
```

What it would add:

```text
timing boundary definitions
warmup and repetition policy
metrics schema
run environment snapshot
artifact layout
no-claim benchmark-readiness reports
fallback-aware timing categories
```

What it must not claim yet:

```text
numeric speedup
performance-improvement claim
benchmark claim
lossless generation
target equivalence
correctness
draft-acceptance metric
```

Risk:

```text
Timing fields can be over-read if reports do not keep descriptive measurements separate from claims.
```

Suggested first phase:

```text
Phase 3.1: Low-Tier Benchmark Readiness Design
```

### Track C: High-Tier Preparation

Goal:

```text
Prepare high-tier feasibility and backend decisions without implementing high-tier logic yet.
```

What it would add:

```text
Gemma E2B to Gemma E4B role contract
verifier/target terminology
hidden-state access requirements
GGUF and llama.cpp limitation analysis
backend decision criteria
risk register
minimum future prototype plan
```

What it must not claim yet:

```text
high-tier implementation
feature-level verification
EAGLE implementation
lossless generation
target equivalence
speedup
```

Risk:

```text
High-tier design may depend on backend capabilities that the current GGUF runtime cannot expose.
```

Suggested first phase:

```text
Phase 3.4: High-Tier Feasibility and Backend Decision Design
```

## Chosen Roadmap: B then C

Recommended roadmap:

```text
1. Track B: Benchmark Readiness
2. Track C: High-Tier Preparation
```

Reason:

```text
Low-Tier Diagnostic MVP is already closed. Before high-tier work, the project should define clean timing boundaries, reproducible run structure, warmup/repetition policy, metrics schema, and no-claim benchmark-readiness reports. After that, the project can evaluate high-tier feasibility with clearer runtime and measurement boundaries.
```

Benchmark Readiness before High-Tier Preparation keeps Phase 3 grounded in reproducible measurement infrastructure before backend or hidden-state design expands the surface area.

## Track B: Benchmark Readiness Plan

Track B prepares benchmarking without making benchmark claims.

It should define:

```text
timing boundaries
load time vs generation time
warmup policy
number of repeated runs
prompt set selection
trace artifact naming
metrics schema
latency summary fields
tokens/sec summary fields
device metadata capture
run environment snapshot
fallback/valid-draft category reporting
no speedup claim policy
```

Suggested sequence:

```text
Phase 3.1 : Low-Tier Benchmark Readiness Design
Phase 3.2 : Low-Tier Timing Boundary + Metrics Scaffold
Phase 3.3 : Low-Tier Benchmark Dry Run / No-Claim Report
```

Phase 3.1 should be design-only. Phase 3.2 may add scaffold code for timing boundaries and metrics fields. Phase 3.3 should run a dry run and produce a no-claim report.

## Track C: High-Tier Preparation Plan

Track C prepares high-tier feasibility, not high-tier implementation.

It should define:

```text
Gemma E2B -> Gemma E4B role contract
verifier/target terminology
hidden-state access requirements
GGUF/llama.cpp limitations
whether llama.cpp can expose required feature-level data
whether another backend is needed for high-tier
risk register
minimum future prototype plan
```

Suggested sequence:

```text
Phase 3.4 : High-Tier Feasibility and Backend Decision Design
Phase 3.5 : High-Tier Architecture Contract
```

Track C should start only after Track B defines clean timing and metrics boundaries.

## Recommended Phase 3.1

Recommended next phase:

```text
Phase 3.1: Low-Tier Benchmark Readiness Design
```

Phase 3.1 should create:

```text
docs/reports/phase-3-1-low-tier-benchmark-readiness-design.md
```

It should define:

```text
benchmark scope
timing boundaries
metrics schema
run protocol
warmup/repetition policy
artifact layout
no-claim language
next implementation phase
```

Phase 3.1 should remain design-only and should not add runtime logic.

## Conclusion

`Low-Tier Diagnostic MVP v0.1` is handed off as a closed diagnostic milestone. The codebase now has role-based names, reproducible v2 prompt-set diagnostics, selector and inspection artifacts, and a committed reproducibility pack.

The Phase 3 roadmap should proceed with Benchmark Readiness first, then High-Tier Preparation. That order keeps measurement definitions stable before high-tier backend and architecture decisions enter the project.
