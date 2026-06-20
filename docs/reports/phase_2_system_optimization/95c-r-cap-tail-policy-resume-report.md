# Task 95C-R — Cap/Tail Policy Resume after GPU Recovery

## 1. Purpose

Task95C-R resumes only the blocked `max_new_tokens=256` portion of Task95C after GPU recovery.

The scope stayed bounded to two `n=10` runs:

- CC-DFlash-R2 large, `gsm8k_short`, seed `42`, `max_new_tokens=256`
- CC-DFlash-R2 light, `gsm8k_short`, seed `42`, `max_new_tokens=256`

Task95C remains the historical PARTIAL record. This resume report does not overwrite Task94, Task95A, Task95B, or Task95C artifacts.

## 2. GPU Recovery Gate

GPU recovery passed in the agent shell before benchmark execution:

- `nvidia-smi`: passed
- NVIDIA driver: `595.71.05`
- CUDA version reported by `nvidia-smi`: `13.2`
- torch: `2.5.1+cu121`
- `torch.cuda.is_available()`: `True`
- torch CUDA runtime: `12.1`
- GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`

No CPU fallback was used.

## 3. Setup

The setup matched Task94 and the intended Task95C resume plan:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `42`
- `n=10`
- warmup prompts: `0`
- stored generated text: yes
- resume: yes
- compressor profiles: large and light
- only changed field versus Task94: `max_new_tokens=128` to `max_new_tokens=256`

No compressor config, model loading code, or keep-rate setting was modified. No `n=30`, `n=100`, full benchmark, or LLM judge was run.

## 4. Artifacts

New Task95C-R run artifacts:

- large mnt256: `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/resume_mnt256/runs/20260621_024734_cc_dflash_r2_large_n10_mnt256.jsonl`
- light mnt256: `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/resume_mnt256/runs/20260621_024839_cc_dflash_r2_light_n10_mnt256.jsonl`

Resume summary/table artifacts:

- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/resume_mnt256/summary/task95c_r_cap_tail_summary.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/resume_mnt256/summary/task95c_r_recommendation.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/resume_mnt256/summary/task95c_r_row_delta_analysis.jsonl`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/resume_mnt256/tables/task95c_r_cap_tail_table.csv`

Row-count audit:

- large mnt256: `10` rows
- light mnt256: `10` rows

## 5. Results

| Setting | rows | calibrated strict | cap-limited incomplete | final-answer markers | strict wrong numeric | `t_compress_ms` | `R_actual` | e2e time (s) | tok/s | `tau_mean` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large mnt128 | 10 | 5/10 | 5/10 | 5/10 | 0/10 | 1190.11 | 2.67 | 3.10 | 64.46 | 6.06 |
| light mnt128 | 10 | 2/10 | 7/10 | 3/10 | 1/10 | 406.39 | 2.00 | 2.46 | 63.28 | 5.88 |
| large mnt256 | 10 | 8/10 | 1/10 | 9/10 | 1/10 | 1272.62 | 2.67 | 3.78 | 61.98 | 6.03 |
| light mnt256 | 10 | 8/10 | 1/10 | 9/10 | 1/10 | 412.97 | 2.00 | 3.09 | 61.23 | 5.88 |

Key deltas:

- large mnt128 to mnt256: strict `+3`, cap-limited `-4`, final-answer markers `+4`, e2e `+0.68s`
- light mnt128 to mnt256: strict `+6`, cap-limited `-6`, final-answer markers `+6`, e2e `+0.63s`
- large mnt256 vs light mnt256: strict gap `0`, cap-limited gap `0`, light e2e lower by `0.69s`, light `t_compress_ms` lower by `859.65ms`

## 6. Interpretation

The mnt256 resume supports cap pressure as the main explanation for the Task94/Task95B light gap in this bounded sample. Light improved from `2/10` to `8/10` calibrated strict correctness, while cap-limited incomplete rows fell from `7/10` to `1/10`.

Large also improved from `5/10` to `8/10`, so the original mnt128 cap was constraining both profiles. At mnt256, large and light tie on calibrated strict correctness and cap-limited incomplete counts in this `n=10` run.

The e2e cost increased for both profiles because outputs were allowed to run longer. Light e2e increased by about `0.63s`, but remained below large mnt256 by about `0.69s`; light also preserved a large compression-time advantage.

This remains a deterministic proxy result only. It does not establish final semantic correctness, deployment readiness, QMSum behavior, or full-benchmark performance.

## 7. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- both mnt256 jobs completed with `10` rows
- analyzer completed and wrote the required resume artifacts
- the comparison clearly shows that mnt256 reduced cap-limited rows and repaired the light strict proxy gap in this bounded sample
- no `n=30`, `n=100`, full benchmark, keep-rate tuning, model-loading change, or LLM judge was run

## 8. Recommendation

Recommendation: **bounded confirmation only**.

The mnt256 result strongly repairs the light quality proxy gap in this `n=10` sample, but it is still too small for a final quality or speedup claim. Do not move directly to `n=30` without a small follow-up confirmation that preserves the same policy boundaries.

If the confirmation holds, then consider a gated larger comparison. If it regresses, proceed to T95D/T96 keep-rate or tail-policy triage.

## 9. Claim Boundary

Task95C-R makes no:

- final speedup claim
- final quality claim
- deployment or 8GB claim
- QMSum semantic correctness claim
- full benchmark claim
- `n=30` or `n=100` claim
