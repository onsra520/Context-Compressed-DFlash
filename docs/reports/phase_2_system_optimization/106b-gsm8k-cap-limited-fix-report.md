# Task106B — Optional GSM8K Cap-Limited Fix

## 1. Purpose

Task106B tested a narrow GSM8K-only final-answer/finalization fix for optimized `CC-DFlash-R2` Light GPU.

The goal was to reduce missing final-answer marker and near-cap failures identified by Task106A without changing broad benchmark methodology, QMSum policy, extraction policy, keep-rate, default config, or deployment/default-switch claims.

This task ran exactly one GSM8K optimized-condition rerun:

- condition: `CC-DFlash-R2`
- dataset: `gsm8k_short`
- seed: `42`
- n: `100`
- `max_new_tokens=256`
- compressor profile: `light`
- compressor device map: `cuda`
- runtime-only GSM8K policy override

It did not run QMSum, QMSum n100, full matrix, Baseline-AR, DFlash-R1, Large CPU, LLMLingua-AR-R2, GSM8K n1000/full dataset, query-aware compression, keep-rate tuning, human scoring, LLM judge, default switch, or downloads.

## 2. T106A Finding Being Tested

Task106A found that optimized `CC-DFlash-R2` Light GPU trailed the Task105A GSM8K strict proxy mainly through cap/final-marker pressure:

| Signal | T106A count |
| --- | ---: |
| CC cap-limited rows | `15/100` |
| CC-only cap-limited rows | `9/15` |
| Shared-by-all-three cap-limited rows | `6/15` |
| Missing final-answer marker among CC cap rows | `15/15` |
| Hit/near `max_new_tokens=256` among CC cap rows | `15/15` |

T100B and T105A showed the identical optimized pattern: strict `79/100`, cap-limited `15/100`, and strict wrong numeric `6/100`.

## 3. Fix Method

Task106B added a runtime-only GSM8K policy override in `scripts/run_mvp.py`, analogous to the existing QMSum runtime policy override.

Policy name:

- `gsm8k_concise_final_answer_v1`

Policy suffix:

> Keep the solution concise. End with exactly one line in the format: Final answer: `<number>`. Do not continue after the final answer.

Scope guards:

- only valid with `--dataset gsm8k_short`
- only valid with `--condition CC-DFlash-R2`
- runtime-only flag
- default GSM8K behavior unchanged unless explicitly invoked
- QMSum policy unchanged
- extraction/calibration policy unchanged

Metadata recorded in all T106B rows:

- `gsm8k_answer_policy_enabled=true`
- `gsm8k_answer_policy_type=gsm8k_concise_final_answer_v1`
- `gsm8k_answer_policy_preserved=true`
- `gsm8k_policy_suffix_override=true`
- `gsm8k_output_policy_preview`

## 4. Runtime Setup

Run artifact:

- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl`

The run completed `100/100` rows with no OOM/CUDA failure flags. CUDA was visible before runtime execution, and the run reported final status `PASS`.

Runtime summary:

| Metric | Value |
| --- | ---: |
| rows | `100/100` |
| average `T_compress_ms` | `17.457620` |
| average `R_actual` | `2.00` |
| average e2e time | `2.145689s` |
| average tok/s | `52.231247` |
| max reserved VRAM | `4.439453 GiB` |

## 5. Metadata and Scope Guard

Metadata audit result: `valid=true`.

All `100/100` rows recorded:

- `condition=CC-DFlash-R2`
- `dataset_name=gsm8k_short`
- `prompt_source=dataset`
- `max_new_tokens=256`
- `compressor_profile=light`
- `compressor_device_map=cuda`
- `requested_compressor_device_map=cuda`
- `local_files_only=true`
- `gsm8k_answer_policy_type=gsm8k_concise_final_answer_v1`
- `gsm8k_policy_suffix_override=true`
- `gsm8k_answer_policy_preserved=true`

No model/config default was changed.

## 6. Before/After GSM8K Comparison

Task106B compares the new fixed run against the Task105A optimized `CC-DFlash-R2` Light GPU run.

| Metric | Task105A optimized | T106B fixed | Delta |
| --- | ---: | ---: | ---: |
| strict correct | `79/100` | `88/100` | `+9` |
| cap-limited incomplete | `15/100` | `2/100` | `-13` |
| strict wrong numeric | `6/100` | `10/100` | `+4` |
| answer missing | `0/100` | `0/100` | `0` |
| final-answer marker count | `85/100` | `98/100` | `+13` |

Interpretation: the narrow final-answer policy substantially reduced cap-limited incomplete rows and improved the strict GSM8K proxy in this matched optimized-condition run. However, strict wrong numeric rows increased, so the result should be described as a cap/finalization improvement with caveats, not as proof that quality is solved.

## 7. Cap-Limited and Final-Marker Impact

Cap-limited row delta:

- before: `15`
- after: `2`
- resolved: `13`
- new cap-limited rows: `0`
- persistent cap-limited rows: `2`

Persistent cap-limited fixture IDs:

- `gsm8k_short_test_0028`
- `gsm8k_short_test_0078`

Resolved cap-limited fixture IDs:

- `gsm8k_short_test_0008`
- `gsm8k_short_test_0031`
- `gsm8k_short_test_0035`
- `gsm8k_short_test_0045`
- `gsm8k_short_test_0048`
- `gsm8k_short_test_0056`
- `gsm8k_short_test_0066`
- `gsm8k_short_test_0082`
- `gsm8k_short_test_0089`
- `gsm8k_short_test_0092`
- `gsm8k_short_test_0093`
- `gsm8k_short_test_0098`
- `gsm8k_short_test_0099`

## 8. Runtime Impact

Runtime comparison:

| Metric | Task105A optimized | T106B fixed | Delta |
| --- | ---: | ---: | ---: |
| average e2e time | `2.896622s` | `2.145689s` | `-0.750933s` |
| average e2e regression rate | n/a | `-0.259244` | improved |
| average `T_compress_ms` | `17.249677` | `17.457620` | `+0.207943ms` |
| average tok/s | `59.089889` | `52.231247` | `-6.858642` |
| max reserved VRAM | `4.431641 GiB` | `4.439453 GiB` | `+0.007812 GiB` |

The e2e average improved because the policy produced shorter/finalized outputs. Compressor overhead remained effectively unchanged. The tok/s average decreased, so this should not be presented as a universal runtime win independent of output length.

## 9. Claim Update

Allowed wording:

- T106B tested a narrow GSM8K final-answer/cap-limited fix for optimized `CC-DFlash-R2` Light GPU.
- The fix reduced cap-limited incomplete rows from `15/100` to `2/100` under the matched GSM8K n100 setup.
- The fix improved strict GSM8K proxy from `79/100` to `88/100` under the matched optimized-condition setup.
- The fix preserved low compressor overhead in this run, with average `T_compress_ms=17.457620`.

Blocked wording:

- quality is fully preserved
- optimized `CC-DFlash-R2` becomes default
- full benchmark speed claim is closed
- QMSum semantic risk is resolved
- the fix generalizes beyond GSM8K n100
- this proves a universal quality-speed win

## 10. Next Task Decision

Decision: `PASS_WITH_CAVEAT`.

Fix interpretation: `cap_fix_supported_with_caveat`.

Next task:

- `T106C — Optimized Default Candidate Decision`

T106C should decide candidate/default language separately. T106B does not authorize an automatic default switch.

## 11. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_fix_summary.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_condition_metrics.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_before_after_comparison.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_cap_limited_delta.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_quality_proxy_delta.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_runtime_delta.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_metadata_audit.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/summary/task106b_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/tables/task106b_gsm8k_cap_limited_fix_comparison.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task106b_gsm8k_cap_limited_fix.py`

Tests:

- `tests/test_task106b_gsm8k_cap_limited_fix.py`

## 12. Scope Confirmation

Task106B ran only the requested optimized GSM8K condition and produced the scoped fix artifacts.

It did not run QMSum, QMSum n100, full matrix, Baseline-AR, DFlash-R1, Large CPU, LLMLingua-AR-R2, GSM8K n1000/full dataset, query-aware compression, keep-rate tuning, human scoring, LLM judge, default switch, or downloads.
