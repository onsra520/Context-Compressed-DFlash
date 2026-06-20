# Task 95C — Cap/Tail Policy Triage

## 1. Purpose

Task95C tests whether the Task94/Task95B light-vs-large quality gap is partly caused by `max_new_tokens=128` being too low.

The intended safe run plan was bounded:

- keep compressor profiles unchanged
- keep condition, dataset, seed, and `n=10` unchanged from Task94
- only change `max_new_tokens` from `128` to `256`
- run exactly two jobs: CC-DFlash-R2 large `n=10` and CC-DFlash-R2 light `n=10`
- do not tune `keep_rate`
- do not run `n=30`, `n=100`, or a full benchmark

## 2. Inputs

Task94 `max_new_tokens=128` artifacts:

- large: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192758_cc_dflash_r2_large_n10.jsonl`
- light: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192904_cc_dflash_r2_light_n10.jsonl`

Task95B calibration artifacts:

- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_calibrated_quality_summary.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_calibrated_row_labels.jsonl`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_recommendation.json`

Task95C `max_new_tokens=256` artifacts:

- not produced in this run because the GPU gate failed before benchmark execution

## 3. Setup

The intended Task95C setup matched Task94 except for the output cap:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `42`
- `n=10`
- warmup prompts: `0`
- stored generated text: yes
- resume: yes
- compressor profiles: large and light
- only changed field: `max_new_tokens=128` to `max_new_tokens=256`

No compressor config, model loading code, or keep-rate setting was modified.

## 4. Static Cap Audit

Before running models, Task94/Task95B outputs were inspected with the Task95B calibrated policy.

| Profile | rows | calibrated strict | cap-limited incomplete | missing final-answer marker | rows at token cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| large mnt128 | 10 | 5/10 | 5/10 | 5/10 | 6/10 |
| light mnt128 | 10 | 2/10 | 7/10 | 7/10 | 7/10 |

The cap-limited rows lacked final-answer markers. Their tails appeared cut at or near `max_new_tokens=128`; examples ended mid-equation, mid-sentence, or before the required final answer line.

The light profile has more incomplete rows than the large profile, so the static audit supports the bounded `max_new_tokens=256` test. This does not change the rule that the task must remain `n=10` only.

## 5. GPU Gate

The GPU gate failed:

- `nvidia-smi`: failed because it could not communicate with the NVIDIA driver
- torch: `2.5.1+cu121`
- `torch.cuda.is_available()`: `False`
- torch CUDA runtime: `12.1`
- visible GPU from torch: `NONE`

Per the task rules, no benchmark was run and no CPU fallback was attempted.

## 6. Results

Task95C mnt256 comparison results are not available in this run.

| Setting | rows | strict calibrated correctness | cap-limited incomplete | `t_compress_ms` | `R_actual` | e2e time | tok/s | `tau_mean` | final-answer markers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large mnt128 | 10 | 5/10 | 5/10 | 1190.11 | 2.67 | see Task94 | see Task94 | see Task94 | 5/10 |
| light mnt128 | 10 | 2/10 | 7/10 | 406.39 | 2.00 | see Task94 | see Task94 | see Task94 | 3/10 |
| large mnt256 | 0 | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |
| light mnt256 | 0 | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |

Structured PARTIAL artifacts:

- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/summary/task95c_cap_tail_summary.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/summary/task95c_recommendation.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/summary/task95c_row_delta_analysis.jsonl`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95c_cap_tail_policy_triage/tables/task95c_cap_tail_table.csv`

## 7. Interpretation

The static evidence is consistent with output-cap pressure being a plausible contributor to the Task94/T95B quality gap:

- light has more cap-limited incomplete rows than large
- cap-limited rows usually lack the required final answer marker
- row tails appear cut at `max_new_tokens=128`

However, the central mnt256 comparison could not be run because CUDA was unavailable. Therefore Task95C cannot yet say whether increasing the cap improves light strict correctness, reduces cap-limited outputs, preserves a meaningful `T_compress` advantage, or raises e2e cost too much.

No semantic correctness claim is made.

## 8. Decision

Decision: **PARTIAL**.

Reason:

- static cap audit completed
- GPU gate failed before benchmark execution
- no mnt256 Task95C benchmark rows were produced
- no n=30, n=100, full benchmark, keep-rate tuning, or CPU fallback was run

## 9. Recommendation

Restore GPU availability and rerun only the bounded Task95C plan:

- CC-DFlash-R2 large, `gsm8k_short`, seed `42`, `n=10`, `max_new_tokens=256`
- CC-DFlash-R2 light, `gsm8k_short`, seed `42`, `n=10`, `max_new_tokens=256`

Do not run `n=30` yet. Do not tune `keep_rate` inside Task95C. If the mnt256 rerun reduces cap-limited light rows but light strict correctness remains worse, proceed to T95D/T96 keep-rate or tail-policy triage.

## 10. Claim Boundary

Task95C currently makes no:

- final speedup claim
- final quality claim
- deployment or 8GB claim
- QMSum semantic correctness claim
- full benchmark claim
- n=30 or n=100 claim
