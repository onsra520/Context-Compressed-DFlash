# Phase 2.17 Low-Tier Diagnostic MVP Reproducibility Pack

## Summary

Phase 2.17 packages a fresh reproducibility run for `Low-Tier Diagnostic MVP v0.1` after the Phase 2.16 role-based naming cleanup.

This phase does not reopen MVP scope. It records the fresh commands, local artifacts, diagnostic counts, role-based field check, verification results, and remaining limits for reproducing the MVP diagnostic path.

## MVP Name

```text
Low-Tier Diagnostic MVP v0.1
```

## Fresh Run Commands

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
  --low-tier logs/reports/20260525T142702Z-low-tier-trace.json \
  --baseline logs/reports/20260525T142908Z-target-baseline-trace.json

.venv/bin/python scripts/inspect_eligible_records.py \
  --low-tier logs/reports/20260525T142702Z-low-tier-trace.json \
  --baseline logs/reports/20260525T142908Z-target-baseline-trace.json

.venv/bin/pytest -v
```

Verification hygiene:

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

## Fresh Artifact List

Fresh local artifacts from this phase:

```text
fresh low-tier trace:
  logs/reports/20260525T142702Z-low-tier-trace.json

fresh target-baseline trace:
  logs/reports/20260525T142908Z-target-baseline-trace.json

fresh diagnostic record selection markdown:
  logs/reports/20260525T142959Z-diagnostic-record-selection.md

fresh diagnostic record selection json:
  logs/reports/20260525T142959Z-diagnostic-record-selection.json

fresh eligible-record inspection markdown:
  logs/reports/20260525T142959Z-eligible-record-inspection.md

fresh eligible-record inspection json:
  logs/reports/20260525T142959Z-eligible-record-inspection.json

test result summary:
  174 passed

forbidden-claim scan result:
  clean, no matches

git diff check result:
  clean
```

The raw-output artifacts remain under `logs/reports/`, which is not part of the committed source pack.

## Fresh Trace Summary

```text
mvp_name: Low-Tier Diagnostic MVP v0.1
prompt_set_id: phase-2-controlled-eligibility-v2
prompt_count: 16
prompt_mode: raw
capture_raw_output: true
low_tier_trace_path: logs/reports/20260525T142702Z-low-tier-trace.json
baseline_trace_path: logs/reports/20260525T142908Z-target-baseline-trace.json

total_records: 16
valid_draft_continuation_count: 16
fallback_after_rejection_count: 0
fallback_only_count: 0
unknown_contribution_count: 0
baseline_empty_after_normalization_count: 0

drafter_device_status: ok
verifier_device_status: ok
drafter_model_file: /home/seggss/HTFS-Decoding/models/qwen3-0.6b/Qwen3-0.6B-UD-Q8_K_XL.gguf
verifier_model_file: /home/seggss/HTFS-Decoding/models/gemma-4-e2b-it/gemma-4-E2B-it-UD-Q4_K_XL.gguf
```

## Role-Based Naming Check

Fresh low-tier trace records expose canonical role-based fields:

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

Fresh target-baseline trace records expose canonical verifier fields:

```text
verifier_model_file
verifier_device_status
verifier_expected_device
verifier_n_gpu_layers
verifier_decode_tokens_per_second
verifier_output_summary
```

Compatibility aliases may still exist in fresh traces during migration, but role-based fields are canonical for current MVP-facing reports.

## Selector Summary

```text
selector_report_path: logs/reports/20260525T142959Z-diagnostic-record-selection.md
selector_json_path: logs/reports/20260525T142959Z-diagnostic-record-selection.json
selection_ready: yes
blocking_reasons: []

total_records: 16
eligible_valid_draft_record_count: 16
excluded_empty_baseline_record_count: 0
excluded_fallback_derived_record_count: 0
excluded_unknown_contribution_record_count: 0
excluded_prompt_mode_risk_record_count: 0
```

## Eligible Inspection Summary

```text
eligible_inspection_report_path: logs/reports/20260525T142959Z-eligible-record-inspection.md
eligible_inspection_json_path: logs/reports/20260525T142959Z-eligible-record-inspection.json
inspection_ready: yes
blocking_reasons: []

eligible_valid_draft_record_count: 16
excluded_empty_baseline_record_count: 0
excluded_fallback_derived_record_count: 0
excluded_unknown_contribution_record_count: 0
excluded_prompt_mode_risk_record_count: 0
```

## Verification Summary

```text
environment_check: passed
test_command: .venv/bin/pytest -v
test_count: 174
test_status: passed
forbidden_claim_scan_status: clean
git_diff_check_status: clean
```

## Reproducibility Checklist

```text
[x] Environment check passed
[x] Low-tier v2 trace generated
[x] Baseline v2 trace generated
[x] Fresh traces use role-based fields
[x] Selector report generated
[x] Eligible inspection report generated
[x] Full test suite passed
[x] Forbidden-claim scan clean
[x] Git diff check clean
[x] Non-claims preserved
[x] Raw output artifacts kept under ignored logs/reports/
```

## Artifact Map

Configuration:

```text
configs/local.example.yaml
```

Core modules:

```text
src/htfsd/types.py
src/htfsd/config.py
src/htfsd/metrics/prompt_sets.py
src/htfsd/metrics/output_compare.py
src/htfsd/metrics/output_preview.py
src/htfsd/metrics/output_diagnostics.py
src/htfsd/metrics/output_diagnostic_summary.py
src/htfsd/metrics/output_diagnostic_compare.py
src/htfsd/metrics/diagnostic_record_selection.py
src/htfsd/metrics/eligible_record_inspection.py
```

CLI scripts:

```text
scripts/check_env.py
scripts/run_low_tier_trace.py
scripts/run_baseline_trace.py
scripts/select_diagnostic_records.py
scripts/inspect_eligible_records.py
```

MVP reports:

```text
docs/reports/phase-2-15-low-tier-diagnostic-mvp-boundary-and-acceptance.md
docs/reports/phase-2-16-de-smoke-role-based-naming-refactor.md
docs/reports/phase-2-17-low-tier-diagnostic-mvp-reproducibility-pack.md
```

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
compatibility aliases remain for old configs/traces during migration
```

## Non-Claims

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

## Conclusion

`Low-Tier Diagnostic MVP v0.1` is reproducible locally through the fresh Phase 2.17 command sequence. The fresh v2 diagnostic run generated 16 low-tier records, 16 baseline records, and 16 eligible valid-draft records with role-based trace fields present.

The MVP remains a controlled diagnostic pipeline. It provides trace, readiness, classification, selection, and eligible-record inspection infrastructure without making equality, correctness, target-equivalence, lossless-generation, benchmark, throughput, draft-acceptance, or high-tier claims.

## Recommended Next Milestone

Recommended next milestone:

```text
Phase 3.0: Low-Tier Diagnostic MVP Handoff and Next-Phase Planning
```

The next phase should decide whether to deepen text-level diagnostics, design token-level verification requirements, or prepare a separate high-tier architecture plan. It should keep the same non-claim boundaries until stronger evidence exists.
