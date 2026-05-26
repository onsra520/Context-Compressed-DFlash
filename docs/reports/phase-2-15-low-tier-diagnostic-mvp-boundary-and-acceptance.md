# Phase 2.15 Low-Tier Diagnostic MVP Boundary and Acceptance

## Summary

Phase 2.15 defines the boundary and acceptance status for the current low-tier diagnostic work.

The MVP validates a controlled diagnostic pipeline for:

- Qwen3-0.6B CPU drafting
- Gemma E2B CUDA target/continuation path
- GGUF and llama.cpp local runtime
- raw low-tier and target-baseline traces
- fallback-aware classification
- controlled record selection
- eligible-record inspection

The MVP does not validate exact target-model equivalence, token-level verification, or high-tier hidden-state behavior.

## MVP Name

`Low-Tier Diagnostic MVP v0.1`

This name is intentionally narrow. It is a diagnostic MVP, not a speed MVP, final speculative decoding MVP, or high-tier MVP.

## MVP Boundary

The MVP includes enough infrastructure to run, classify, select, and inspect controlled low-tier diagnostic records.

The accepted runtime shape is:

```text
Qwen3-0.6B CPU
  -> text_bridge
  -> Gemma E2B CUDA
```

The accepted diagnostic shape is:

```text
low-tier raw trace
target-baseline raw trace
precheck/readiness gates
normalization preview
fallback-aware classification
record selection
eligible-record inspection
```

## Included Components

1. Runtime readiness

- Qwen3-0.6B drafter on CPU
- Gemma E2B target/continuation path on CUDA
- GGUF + llama.cpp runtime

2. Trace generation

- low-tier trace
- target-baseline trace
- controlled fallback trace

3. Controlled generation metadata

- generation settings
- prompt-set metadata
- raw output capture as opt-in behavior

4. Safety and readiness gates

- schema validation
- prompt coverage checks
- generation setting match checks
- runtime metadata match checks
- raw capture status checks

5. Diagnostic layers

- normalization preview
- fallback-aware classifier
- diagnostic exact-string summary
- controlled record selector
- eligible-record inspection

6. Refined prompt set

- `phase-2-controlled-eligibility-v2`
- 16 stable prompt IDs
- 16 eligible valid-draft records in the Phase 2.14 run

## Excluded Components

The MVP excludes:

- exact token-level speculative decoding
- target-model equivalence validation
- final-output correctness evaluation
- speed or throughput claims
- high-tier Gemma E2B to Gemma E4B hidden-state logic
- feature-level verification through GGUF hidden states
- production benchmark harnesses
- automatic raw-output archival outside ignored local logs

## Acceptance Criteria

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| AC-1 | Environment check passes. | passed | `python scripts/check_env.py` passed in Phase 2.14 verification. |
| AC-2 | Qwen and Gemma device policies are respected. | passed | Qwen device status `ok`; Gemma E2B device status `ok`. |
| AC-3 | Low-tier raw trace runs with refined v2 prompt set. | passed | `logs/reports/20260525T132815Z-low-tier-trace.json`. |
| AC-4 | Baseline raw trace runs with refined v2 prompt set. | passed | `logs/reports/20260525T132830Z-target-baseline-trace.json`. |
| AC-5 | Low-tier trace records classify as valid-draft continuation. | passed | `valid_draft_continuation_count: 16`. |
| AC-6 | Baseline outputs are non-empty for refined v2 run. | passed | `baseline_empty_after_normalization_count: 0`. |
| AC-7 | Selector marks eligible valid-draft records. | passed | `eligible_valid_draft_record_count: 16`. |
| AC-8 | Eligible inspection report is generated. | passed | `logs/reports/20260525T132845Z-eligible-record-inspection.md`. |
| AC-9 | Full test suite passes. | passed | `.venv/bin/pytest -v`: 173 passed. |
| AC-10 | Forbidden-claim scan is clean. | passed | Scan returned no matches. |
| AC-11 | Git diff check is clean. | passed | `git diff --check` returned no errors. |
| AC-12 | Reports include explicit non-claims. | passed | Phase reports include scoped non-claims. |

## Phase 2.14 Evidence

Phase 2.14 evaluated `phase-2-controlled-eligibility-v2`:

- prompt_set_id: `phase-2-controlled-eligibility-v2`
- total_records: 16
- valid_draft_continuation_count: 16
- fallback_after_rejection_count: 0
- fallback_only_count: 0
- unknown_contribution_count: 0
- baseline_empty_after_normalization_count: 0
- eligible_valid_draft_record_count: 16
- excluded_empty_baseline_record_count: 0
- excluded_fallback_derived_record_count: 0
- excluded_unknown_contribution_record_count: 0
- excluded_prompt_mode_risk_record_count: 0

Phase 2.14 artifacts:

- low-tier trace: `logs/reports/20260525T132815Z-low-tier-trace.json`
- baseline trace: `logs/reports/20260525T132830Z-target-baseline-trace.json`
- selector report: `logs/reports/20260525T132845Z-diagnostic-record-selection.md`
- eligible inspection report: `logs/reports/20260525T132845Z-eligible-record-inspection.md`

## Reproducibility Commands

```bash
cd ~/HTFS-Decoding
source .venv/bin/activate

python scripts/check_env.py

python scripts/run_low_tier_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v2

python scripts/run_baseline_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v2

python scripts/select_diagnostic_records.py \
  --low-tier logs/reports/<low-tier-v2-trace>.json \
  --baseline logs/reports/<baseline-v2-trace>.json

python scripts/inspect_eligible_records.py \
  --low-tier logs/reports/<low-tier-v2-trace>.json \
  --baseline logs/reports/<baseline-v2-trace>.json

.venv/bin/pytest -v
```

Safe-form forbidden-claim scan command:

```bash
python - <<'PY'
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
    "draft " + "acceptance " + "rate",
    "v" + "LLM",
    "v" + "llm",
]
pattern = "|".join(phrases)
paths = ["pyproject.toml", "src", "tests", "scripts", "configs", "README.md", "docs"]
raise SystemExit(subprocess.run(["rg", "-n", pattern, *paths]).returncode)
PY

git diff --check
```

## Artifact Map

Core metrics modules:

- `src/htfsd/metrics/prompt_sets.py`
- `src/htfsd/metrics/output_compare.py`
- `src/htfsd/metrics/output_preview.py`
- `src/htfsd/metrics/output_diagnostics.py`
- `src/htfsd/metrics/output_diagnostic_summary.py`
- `src/htfsd/metrics/output_diagnostic_compare.py`
- `src/htfsd/metrics/diagnostic_record_selection.py`
- `src/htfsd/metrics/eligible_record_inspection.py`

Trace and diagnostic scripts:

- `scripts/run_low_tier_trace.py`
- `scripts/run_baseline_trace.py`
- `scripts/select_diagnostic_records.py`
- `scripts/inspect_eligible_records.py`

Relevant reports:

- `docs/reports/phase-2-14-refined-eligibility-prompt-set-evaluation.md`
- `docs/reports/phase-2-15-low-tier-diagnostic-mvp-boundary-and-acceptance.md`

## Known Limitations

- Diagnostic only.
- No target-equivalence proof.
- No token-level verification.
- No speed or throughput benchmark.
- No high-tier hidden-state path.
- GGUF/llama.cpp may limit feature-level access.
- Results are from local controlled traces.
- Raw outputs are opt-in and should remain under ignored `logs/reports/`.
- The v2 prompt set is useful for controlled eligibility diagnostics, not broad model evaluation.

## Non-Claims

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No performance-improvement claim is made.
No draft-acceptance metric is reported.
No high-tier implementation claim is made.

## Recommended Next Milestone

The next milestone should be a reproducibility pack for `Low-Tier Diagnostic MVP v0.1`:

- fresh trace run
- fresh selector and inspection reports
- final command transcript summary
- stable artifact list
- no new comparison claims

## Conclusion

`Low-Tier Diagnostic MVP v0.1` is accepted as a diagnostic MVP. It demonstrates a reproducible local path for controlled low-tier trace generation, fallback-aware classification, record selection, and eligible-record inspection under the intended Qwen CPU and Gemma E2B CUDA policy.

The MVP remains explicitly diagnostic. It does not establish exact target-model behavior, final-output correctness, or high-tier readiness.
