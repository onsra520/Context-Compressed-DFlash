# Task102B — QMSum Output + Semantic-Risk Analysis

## 1. Purpose

Task102B analyzes the Task102 QMSum Light GPU `n=30` output with deterministic semantic-risk and lexical/evidence proxy checks.

This task is analysis-only. It ran no benchmark, model inference, GPU job, QMSum rerun, QMSum `n=100`, GSM8K run, Baseline-AR run, DFlash-R1 runtime job, Large CPU runtime job, full matrix, keep-rate tuning, default config switch, model download, or LLM judge.

## 2. Inputs

Primary Task102 QMSum artifact:

- `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/runs/20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl`

Task102 setup:

- condition: `CC-DFlash-R2`
- dataset: `qmsum_meeting_qa_long`
- seed: `42`
- rows: `30`
- `max_new_tokens`: `384`
- compressor profile: `light`
- compressor placement: runtime `cuda`

Context:

- Task100B GSM8K Light GPU `n=100`: strict `79/100`, cap-limited `15/100`, average `t_compress_ms=17.35`, average e2e `2.88s`, max reserved VRAM `4.43GiB`, no recorded OOM/CUDA flags.
- Task101 claim boundary: no final speedup, no final quality, no QMSum semantic correctness, no deployment readiness, no universal 8GB guarantee, and no default GPU switch.

## 3. Output / Proxy Quality Analysis

Task102B labeled all `30` QMSum rows with deterministic heuristics only:

| Label | Count |
| --- | ---: |
| completed answer | `30/30` |
| empty or malformed | `0/30` |
| cap-limited or incomplete | `0/30` |
| low reference overlap | `18/30` |
| possible evidence miss | `3/30` |
| source/reference mismatch possible | `18/30` |
| too short or generic | `0/30` |
| proxy uncertain | `18/30` |
| acceptable proxy signal | `10/30` |

Interpretation:

- The run is output-complete: there were no empty rows and no cap-limited/incomplete rows under the deterministic heuristics.
- The dominant quality risk is lexical/proxy weakness: `18/30` rows had low reference overlap and `18/30` remained proxy-uncertain.
- The semantic-risk signal is therefore useful for bounded benchmark-scoped reporting, but it does not prove QMSum semantic correctness.

Row-level artifacts:

- `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_row_labels.jsonl`
- `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_low_proxy_rows.jsonl`
- `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_cap_or_incomplete_rows.jsonl`

## 4. Runtime / Latency Analysis

| Metric | avg | min | max | p95 |
| --- | ---: | ---: | ---: | ---: |
| `t_compress_ms` | `125.26` | `97.24` | `236.32` | `153.61` |
| e2e / generation time | `5.00s` | `1.25s` | `7.44s` | `6.97s` |
| tok/s | `21.34` | `17.62` | `26.67` | `25.29` |
| `tau_mean` | `2.16` | `1.72` | `2.79` | `2.59` |
| `t_prefill_ms` | `363.83` | `333.46` | `455.88` | `383.13` |
| output tokens | `106.80` | `22` | `164` | `158` |
| reference unigram recall proxy | `0.2113` | `0.0000` | `0.5556` | `0.5333` |

Slowest-row records were written to:

- `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_slowest_rows.jsonl`

Bottleneck table:

- `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_bottleneck_table.csv`

## 5. Compression / GPU / VRAM Stability

- Average `R_actual`: `2.19`
- `R_actual` range: `2.13` to `2.25`
- Average `t_compress_ms`: `125.26`
- p95 `t_compress_ms`: `153.61`
- Max VRAM allocated: `4.16GiB`
- Max VRAM reserved: `5.41GiB`
- OOM/CUDA failure flags: `0`
- Metadata confirmed `compressor_profile=light`, `compressor_device_map=cuda`, `requested_compressor_device_map=cuda`, `local_files_only=true`, and `qmsum_answer_policy_type=evidence_focused`.

Local 8GB-class interpretation:

- Task100B GSM8K Light GPU `n=100` max reserved VRAM: `4.43GiB`
- Task102 QMSum Light GPU `n=30` max reserved VRAM: `5.41GiB`
- This supports local RTX 4070 8GB-class feasibility observations only. It is not a universal 8GB deployment guarantee.

## 6. Claim Update

Task102B wrote claim updates to:

- `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_claim_update.json`

Claim status:

- QMSum claim: `SCOPED_WITH_RISK`
- Local 8GB-class feasibility: `STRENGTHENED_LOCAL_OBSERVATION`
- Benchmark-scoped quality: `GSM8K_NUMERIC_PLUS_QMSUM_PROXY`
- Speed: `PENDING_T103_REFERENCE_ALIGNMENT`
- Full matrix: `PENDING_T104`
- GPU default: `PENDING_T105`
- DFlash-R1 broken: `REMOVED`

Allowed wording:

- "QMSum-style long-context prompts were covered by Light GPU feasibility plus deterministic semantic-risk/proxy analysis."
- "Quality evidence covers GSM8K deterministic numeric proxy and QMSum deterministic semantic-risk/proxy audit."

Blocked wording:

- "QMSum semantic correctness is proven."
- "Final semantic correctness is proven."
- "Universal 8GB deployment readiness is proven."

## 7. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- Task102 QMSum `n=30` was complete and readable.
- All rows were labeled.
- Runtime, latency, compression, and VRAM summaries were produced.
- No empty/malformed rows, no cap-limited/incomplete rows, and no OOM/CUDA flags were found.
- Low lexical overlap and proxy uncertainty remained substantial, so QMSum is closed only as benchmark-scoped proxy/risk evidence.

## 8. Next Task

Next task: **T103 — Reference Alignment for Speed Claim**.

Reason:

- QMSum feasibility and deterministic semantic-risk/proxy analysis are complete enough to proceed to reference alignment.
- T102A is not activated because no severe malformed/cap/metadata issue was found.

## 9. Scope Confirmation

Task102B did not run:

- benchmark execution
- model inference
- QMSum rerun
- QMSum `n=100`
- full matrix
- other runtime conditions
- keep-rate tuning
- default GPU switch
- model download
- LLM judge

Task102B makes no QMSum semantic-correctness claim.
