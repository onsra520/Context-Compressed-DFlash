# Task100A — Phase 2 Supported Evidence Summary

## 1. Purpose

Task100A summarizes the supported Phase 2 evidence after Task99-R and prepares the next gated step, T100B.

This task is summary/planning only. It ran no benchmark, model inference, GPU job, `n=100`, `n=30`, QMSum run, keep-rate tuning, model/config loading change, model download, or LLM judge.

## 2. Evidence Classes

### Supported controlled result

**CC-DFlash-R2 Light CPU** is the supported controlled Phase 2 CPU path.

- source: Task96
- dataset: `gsm8k_short`
- `n=30`
- `max_new_tokens=256`
- calibrated strict: `22/30`
- cap-limited incomplete: `5/30`
- average `t_compress_ms`: `363.46`
- average e2e: `3.23s`
- average `R_actual`: `2.00`

### Historical/control reference

**CC-DFlash-R2 Large CPU** is superseded as the preferred Phase 2 optimization candidate, but remains a historical/control reference.

- source: Task96
- dataset: `gsm8k_short`
- `n=30`
- `max_new_tokens=256`
- calibrated strict: `22/30`
- cap-limited incomplete: `5/30`
- average `t_compress_ms`: `1201.58`
- average e2e: `3.97s`
- average `R_actual`: `2.67`

Large CPU is not deleted, invalid, or disqualified. It remains useful as a control/reference path.

### Promising bounded candidate

**CC-DFlash-R2 Light GPU** is a promising bounded candidate, not a default path and not deployment-ready.

- source: Task99-R
- dataset: `gsm8k_short`
- `n=10`
- `max_new_tokens=256`
- calibrated strict: `8/10`
- cap-limited incomplete: `1/10`
- average `t_compress_ms`: `25.57`
- average e2e: `2.67s`
- average tok/s: `62.74`
- average VRAM reserved: `4.36GiB`
- `compressor_profile`: `light`
- `compressor_device_map`: `cuda`
- `requested_compressor_device_map`: `cuda`
- no OOM/CUDA failure flags in the Task99-R bounded run

### Historical-only reference

**DFlash-R1** remains a historical-only reference from Task88.

Task88 used different settings, including `max_new_tokens=512`, so it is not apples-to-apples with Task99-R.

## 3. Main Evidence Table

| Profile / path | Source | n | mnt | Strict proxy | Cap-limited | `t_compress_ms` | e2e | `R_actual` | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CC-DFlash-R2 Light CPU | Task96 | 30 | 256 | `22/30` | `5/30` | `363.46` | `3.23s` | `2.00` | supported controlled Phase 2 CPU path |
| CC-DFlash-R2 Large CPU | Task96 | 30 | 256 | `22/30` | `5/30` | `1201.58` | `3.97s` | `2.67` | historical/control reference; superseded as preferred optimization candidate |
| CC-DFlash-R2 Light GPU | Task99-R | 10 | 256 | `8/10` | `1/10` | `25.57` | `2.67s` | `2.00` | promising bounded candidate; not default, not deployment-ready |
| DFlash-R1 | Task88 | 30 | 512 | n/a | n/a | n/a | n/a | n/a | historical-only reference; settings differ |

## 4. Interpretation

Light CPU supersedes large CPU as the preferred CPU-path optimization candidate because it matched large CPU on the Task96 calibrated strict proxy and cap-limited rows while reducing compression overhead and e2e time.

Large CPU remains a valid historical/control reference. It should not be described as deleted, invalid, or broken.

Light GPU is promising because Task99-R showed bounded `n=10` CUDA placement with much lower compression overhead and no observed OOM/CUDA failure flags in that run. It is still only a bounded candidate because the evidence is `n=10`, not `n=100`, not a full matrix, and not deployment validation.

## 5. T100B Plan

Next gated task: **T100B — Light GPU n100 Controlled Run**.

Purpose:

- scale the promising Light GPU candidate to `n=100` GSM8K mnt256

Scope:

- `CC-DFlash-R2` only
- light compressor only
- `--compressor-device-map cuda`
- `gsm8k_short`
- `max_new_tokens=256`
- `n=100`
- no large CPU `n=100`
- no Baseline-AR
- no DFlash-R1
- no QMSum
- no keep-rate tuning

Framing:

- T100B is not a full matrix
- T100B is not a final benchmark
- T100B is a scale-up validation of the preferred Light GPU candidate
- Task96 large/light CPU remains reference evidence

## 6. Claim Language

Allowed wording:

- “The light CPU compressor path is the supported controlled Phase 2 result.”
- “The light GPU placement path is a promising bounded candidate.”
- “In controlled GSM8K mnt256 n30, light CPU matched large CPU on calibrated strict proxy and reduced t_compress/e2e.”
- “In bounded n10, light GPU placement further reduced t_compress without observed OOM in that run.”

Blocked wording:

- “Light GPU is the default.”
- “Large CPU is invalid.”
- “Final speedup is proven.”
- “Final quality is proven.”
- “Deployment readiness is proven.”
- “8GB deployment readiness is confirmed.”
- “QMSum semantic correctness is proven.”
- “n100 is already completed.”
- “DFlash-R1 is broken.”

## 7. Decision

Task100A status: **PASS**.

Reason:

- static packaging artifacts were created
- supported, reference, candidate, and historical-only evidence classes were separated
- T100B scope was written as a gated plan
- claim language was explicitly bounded
- roadmap was updated

## 8. Claim Boundary

Task100A makes no:

- final speedup claim
- final quality claim
- deployment or 8GB readiness claim
- QMSum semantic correctness claim
- full benchmark claim
- automatic completion claim for `n=100`

## 9. Artifacts

- `results/phase_2_system_optimization/final_reruns/task100a_phase2_supported_evidence_summary/task100a_supported_evidence_summary.json`
- `results/phase_2_system_optimization/final_reruns/task100a_phase2_supported_evidence_summary/task100a_supported_evidence_table.csv`
- `results/phase_2_system_optimization/final_reruns/task100a_phase2_supported_evidence_summary/task100a_candidate_status.json`
- `results/phase_2_system_optimization/final_reruns/task100a_phase2_supported_evidence_summary/task100a_next_step_plan.json`
- `results/phase_2_system_optimization/final_reruns/task100a_phase2_supported_evidence_summary/task100a_claim_language.json`

## 10. Validation Scope

Validation covered:

- compile sanity
- Task100A packaging tests
- packaging script help
- packaging script runtime
- HTML parse sanity
- Markdown fence balance check

No benchmark or model inference belongs to Task100A.
