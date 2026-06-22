# Task102 — QMSum Light GPU n30 Feasibility Run

## Purpose

Task102 tested whether the validated `CC-DFlash-R2` light GPU path can complete a small QMSum-style long-context feasibility run before Phase 2 claim closure.

This task also rebases the active Phase 2 roadmap away from immediate final report integration and toward benchmark-scoped claim closure. It does not make a QMSum semantic-correctness claim.

## Scope

- Ran QMSum-style long-context Light GPU only.
- Used `CC-DFlash-R2`, `qmsum_meeting_qa_long`, seed `42`, light compressor, and runtime `--compressor-device-map cuda`.
- Used `max_new_tokens=384`, the canonical Phase 2 QMSum diagnostic cap from prior QMSum tasks, not the GSM8K `mnt256` setting.
- Ran `n=3` smoke first, then `n=30` only after the smoke completed.
- Did not run QMSum `n=100`, a full matrix, GSM8K, Baseline-AR, DFlash-R1, Large CPU, keep-rate tuning, a default config switch, model download, or LLM judge.

## CUDA Gate

The agent shell saw CUDA before the run:

- `nvidia-smi` passed with NVIDIA driver `595.71.05` and CUDA `13.2`.
- PyTorch was `2.5.1+cu121`.
- `torch.cuda.is_available()` was `True`.
- GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`.

## Artifacts

- Smoke artifact: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/smoke/20260622_151043_cc_dflash_r2_light_gpu_qmsum_seed42_n3_mnt384.jsonl`
- n30 artifact: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/runs/20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl`
- Summary: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/summary/task102_qmsum_feasibility_summary.json`
- Run status: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/summary/task102_qmsum_run_status.json`
- Next-task decision: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/summary/task102_next_task_decision.json`
- Claim closure roadmap: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/summary/task102_phase2_claim_closure_roadmap.json`
- Claim status map: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/summary/task102_claim_status_map.json`
- Runtime table: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/tables/task102_qmsum_runtime_table.csv`

## Feasibility Results

### Smoke

- Rows: `3/3`
- Empty or malformed outputs: `0`
- OOM/CUDA/failure flags: `0`
- Metadata confirmed `compressor_profile=light`, `compressor_device_map=cuda`, `requested_compressor_device_map=cuda`, and `local_files_only=true`.
- Average `t_compress_ms`: `171.51`
- Average e2e/generation time: `5.66s`
- Average tok/s: `19.95`
- Average `R_actual`: `2.20`
- Max reserved VRAM: `5.10GiB`

### n30

- Rows: `30/30`
- Empty or malformed outputs: `0`
- OOM/CUDA/failure flags: `0`
- Metadata confirmed `compressor_profile=light`, `compressor_device_map=cuda`, `requested_compressor_device_map=cuda`, and `local_files_only=true`.
- Average `t_compress_ms`: `125.26`
- Average e2e/generation time: `5.00s`
- Average tok/s: `21.34`
- Average `tau_mean`: `2.16`
- Average `R_actual`: `2.19`
- Max reserved VRAM: `5.41GiB`

## Interpretation

Task102 shows that the Light GPU path can complete a bounded QMSum-style `n=30` feasibility run on the local RTX 4070 Laptop GPU without recorded OOM/CUDA failure and without malformed or empty generated outputs.

This strengthens local feasibility evidence, but it does not close QMSum semantic quality. QMSum remains long-context diagnostic evidence until the generated outputs are analyzed for semantic-risk, proxy behavior, cap behavior, latency, and VRAM patterns.

## Claim Status Update

- GSM8K Light GPU: closed as bounded `PASS_WITH_CAVEAT` evidence from Task100B.
- QMSum Light GPU: feasibility complete, pending Task102B analysis.
- Local 8GB-class feasibility: strengthened by GSM8K `n=100` and QMSum `n=30` local observations, but not deployment readiness.
- DFlash-R1 broken claim: removed; DFlash-R1 remains a reference condition.
- Final report integration: deferred outside active Phase 2 until explicitly requested after claim closure.

## Roadmap Rebase

Task102 replaces the immediate final-report-integration path with an active Phase 2 claim-closure sequence:

- T102 — QMSum Light GPU n30 Feasibility Run: `PASS_WITH_CAVEAT`
- T102A — QMSum Failure Audit / Fix: conditional only
- T102B — QMSum Output + Semantic-Risk / Proxy / Cap / Latency / VRAM Analysis: next
- T103 — Reference Alignment for Speed Claim
- T104 — Full Matrix / Benchmark-Scope Claim Closure
- T105 — Optimized Default Candidate Decision
- T106 — Phase 2 Optimization Closure Pack

## Decision

Task102 decision: `PASS_WITH_CAVEAT`.

The run is complete enough to proceed to Task102B static analysis. It is not a QMSum semantic-correctness result and does not authorize QMSum `n=100`, a full matrix, a default GPU switch, or final report integration.

## Recommendation

Proceed to T102B — QMSum Output + Semantic-Risk / Proxy / Cap / Latency / VRAM Analysis.

Do not run another benchmark by default. Do not run QMSum `n=100` or a full matrix unless explicitly approved later.
