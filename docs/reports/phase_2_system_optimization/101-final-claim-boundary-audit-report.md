# Task101 - Final Claim Boundary Audit

## 1. Purpose

Task101 finalizes the allowed and blocked claim boundaries before final report/demo integration.

This task is audit/report/static only. It ran no benchmark, model inference, GPU job, `n=100` rerun, `n=30`, QMSum run, full matrix, keep-rate tuning, model/config change, model download, or LLM judge.

## 2. Evidence Base

Task101 uses the following bounded evidence base:

- **Task96**: controlled `CC-DFlash-R2` large CPU versus light CPU `n=30`, `gsm8k_short`, `max_new_tokens=256`; strict `22/30` versus `22/30`, cap-limited `5/30` versus `5/30`, with light CPU lower on `t_compress_ms` and e2e.
- **Task99-R**: bounded Light GPU placement resume at `n=3` smoke and `n=10`; metadata confirmed light + cuda placement; no OOM/CUDA failure fields were recorded in that bounded run.
- **Task100A**: supported evidence summary separated Light CPU as supported controlled CPU result, Large CPU as historical/control reference, Light GPU as promising bounded candidate, and DFlash-R1 as historical-only reference.
- **Task100B**: one controlled Light GPU `n=100` GSM8K mnt256 run with strict `79/100`, cap-limited incomplete `15/100`, final-answer marker `85/100`, strict wrong numeric `6/100`, average `t_compress_ms=17.35`, average e2e `2.88s`, average tok/s `59.83`, `R_actual=2.00`, max reserved VRAM about `4.43GiB`, and no recorded OOM/CUDA failure fields.
- **Task100C**: optimization-gap analysis found cap-limited incomplete rows as the dominant remaining gap, strict wrong numeric rows as the secondary gap, low compression overhead, bounded observed VRAM, and a recommendation to proceed to final claim-boundary audit rather than run another benchmark by default.

## 3. Claim Boundary Matrix

| Claim area | Allowed wording | Blocked wording | Remaining limitation |
| --- | --- | --- | --- |
| Speed / latency | In the controlled GSM8K Light GPU `n=100` run, CC-DFlash-R2 with the light GPU compressor achieved lower average compression overhead than CPU-compressor references. Task100B provides bounded evidence of lower e2e time relative to Task96 CPU references. | Final universal speedup is proven. CC-DFlash is always faster. | No full matrix, no QMSum, and reference sample sizes differ. |
| Quality | Task100B achieved `79/100` calibrated strict GSM8K numeric proxy under deterministic evaluation. Quality evidence is deterministic GSM8K proxy evidence. | Final correctness is proven. Semantic correctness is proven. | No LLM judge, no semantic evaluation, `15/100` cap-limited rows, and `6/100` wrong numeric rows. |
| GPU / 8GB feasibility | Task100B completed on the local RTX 4070 Laptop GPU with max reserved VRAM around `4.43GiB` and no recorded OOM/CUDA failure. | Deployment readiness is proven. 8GB deployment readiness is confirmed universally. | Single local machine/run, no stress/load testing, and no deployment environment validation. |
| QMSum / long-context semantics | QMSum remains outside the Task100B Light GPU `n=100` claim. | QMSum semantic correctness is proven. Long-context semantic QA quality is solved. | No QMSum rerun in the Phase 2 Light GPU path. |
| DFlash-R1 comparison | DFlash-R1 is retained as a historical reference. | DFlash-R1 is broken. Task100B is apples-to-apples with Task88 DFlash-R1. | Task88 settings differ, including `max_new_tokens`. |
| Compressor placement/default | Light GPU placement is a promising candidate. Runtime override supports GPU placement. | GPU placement is now the default. Large CPU is invalid. | Default config remains CPU; large CPU remains historical/control reference. |
| `n=100` / full benchmark | Task100B completed one Light GPU `n=100` controlled run. | Full benchmark is complete. Full matrix is complete. | Only one condition, one dataset, one compressor profile. |

## 4. Reworded NO Badges

Task101 replaces rough negative labels with precise final-report labels:

| Old wording | Final wording |
| --- | --- |
| No universal speedup claim | Bounded GSM8K Light GPU speed evidence only |
| No final correctness claim | Deterministic GSM8K numeric proxy only |
| No QMSum semantic correctness claim | No Phase 2 Light GPU QMSum semantic claim |
| No deployment readiness claim | Local feasibility observed; deployment readiness not proven |
| No confirmed 8GB claim | Observed on local RTX 4070 8GB-class GPU; not universal 8GB guarantee |
| No DFlash-R1 broken claim | DFlash-R1 retained as historical reference |
| No default GPU switch | GPU placement remains runtime/gated candidate |

## 5. Final Report Language

Recommended Vietnamese snippets:

- "Trong phạm vi GSM8K mnt256, đường CC-DFlash-R2 với light compressor đặt trên GPU đã hoàn thành n=100 với 79/100 strict numeric proxy, không ghi nhận OOM/CUDA failure, và giảm mạnh T_compress so với các tham chiếu CPU trước đó."
- "Kết quả này là evidence có kiểm soát, không phải claim final speedup hay deployment readiness."
- "Light GPU là một candidate khả quan trong môi trường local đã đo, còn default config vẫn giữ CPU và mọi claim deployment vẫn bị chặn."

Recommended replacement phrasing:

- Instead of "GPU path is production-ready," use "GPU path is a promising local feasibility candidate."
- Instead of "final quality is proven," use "deterministic GSM8K numeric proxy evidence."
- Instead of "DFlash-R1 is broken," use "DFlash-R1 remains a historical reference with setting caveats."

Short English labels:

- Bounded GSM8K Light GPU speed evidence only
- Deterministic GSM8K numeric proxy only
- Local feasibility observed; deployment readiness not proven
- GPU placement remains runtime/gated candidate

## 6. Remaining Limitations

- Cap-limited incomplete rows remain: `15/100`.
- Strict wrong numeric rows remain: `6/100`.
- QMSum was not run for the Phase 2 Light GPU path.
- A full matrix was not run.
- Deployment readiness is not established.
- Universal 8GB readiness is not established.
- GPU placement is not the default.
- DFlash-R1 remains historical-only in this claim boundary.

## 7. Decision

Decision: **PASS**.

Reason:

- claim areas were audited across speed/latency, quality, GPU/8GB feasibility, QMSum, DFlash-R1, compressor placement/default, and `n=100`/full benchmark status
- allowed claims were converted to bounded wording
- blocked claims were preserved with safer replacement guidance
- rough "NO" badges were reworded into precise final-report labels
- Vietnamese and English final-report snippets were generated
- no benchmark/model run was performed

## 8. Recommendation

Proceed to **T102 - Final Report Integration**.

Do not run another benchmark by default. Do not switch GPU placement on by default. Use the Task101 allowed/blocked wording in final report/demo materials.

## 9. Artifacts

- `results/phase_2_system_optimization/final_reruns/task101_final_claim_boundary_audit/task101_claim_boundary_matrix.json`
- `results/phase_2_system_optimization/final_reruns/task101_final_claim_boundary_audit/task101_allowed_claims.json`
- `results/phase_2_system_optimization/final_reruns/task101_final_claim_boundary_audit/task101_blocked_claims.json`
- `results/phase_2_system_optimization/final_reruns/task101_final_claim_boundary_audit/task101_reworded_no_badges.json`
- `results/phase_2_system_optimization/final_reruns/task101_final_claim_boundary_audit/task101_report_language_snippets.json`
- `results/phase_2_system_optimization/final_reruns/task101_final_claim_boundary_audit/task101_final_recommendation.json`

## 10. Validation Scope

Validation covers:

- static Python compile sanity
- Task101 targeted tests
- Task101 script help
- Task101 script runtime
- HTML parse sanity
- Markdown fence balance check

No benchmark, model inference, GPU execution, QMSum run, full matrix, or keep-rate tuning belongs to Task101.
