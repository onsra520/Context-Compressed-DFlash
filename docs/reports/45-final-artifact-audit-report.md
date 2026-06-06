# Task 45-final-artifact-audit — Final n=100 Artifact Audit

Date: 2026-06-06

## Result

PASS for Task 45 final artifact audit.

All four expected n=100 final benchmark JSONL artifacts exist, parse cleanly, contain exactly 100 rows each, and pass the Task 45 compatibility audit. Total audited rows: 400.

This report audits artifact integrity, schema compatibility, logs, and diagnostic quality fields. It does not claim deployment readiness, confirmed 8 GB deployment, final paper speedup, final correctness, or proven end-to-end compression benefit.

## Final Artifact List

| Condition | Artifact | Rows | Schema status |
| --- | --- | ---: | --- |
| Baseline-AR | `results/task45_final_baseline_ar_n100.jsonl` | 100 | PASS, legacy schema accepted |
| DFlash-R1 | `results/task45_final_dflash_r1_n100.jsonl` | 100 | PASS, legacy schema accepted |
| LLMLingua-AR-R2 | `results/task45_final_llmlingua_ar_r2_n100.jsonl` | 100 | PASS, `per_prompt_jsonl_v1` |
| CC-LLM-R2 | `results/task45_final_cc_llm_r2_n100.jsonl` | 100 | PASS, `per_prompt_jsonl_v1` |

Row count command:

```text
100 results/task45_final_baseline_ar_n100.jsonl
100 results/task45_final_dflash_r1_n100.jsonl
100 results/task45_final_llmlingua_ar_r2_n100.jsonl
100 results/task45_final_cc_llm_r2_n100.jsonl
400 total
```

## Machine-Readable Summary

Created:

- `results/task45_final_artifact_audit_summary.json`

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_task45_final_artifacts.py --output results/task45_final_artifact_audit_summary.json
```

Result:

```text
status: PASS
total_rows: 400
```

## Schema Compatibility Result

All artifacts passed required checks for:

- JSONL parseability.
- Exactly 100 JSON object rows.
- Expected condition identity.
- Required core metrics:
  - `condition`
  - `input_tokens`
  - `output_tokens`
  - `generation_time_s`
  - `tokens_per_second` or legacy `tok_per_sec`
  - `tau_mean`
  - `t_prefill_ms`
  - `generated_text`
- Autoregressive behavior:
  - Baseline-AR and LLMLingua-AR-R2 have `acceptance_lengths == []`.
  - Baseline-AR and LLMLingua-AR-R2 have `tau_mean == 0.0`.
- Speculative behavior:
  - DFlash-R1 and CC-LLM-R2 have non-empty `acceptance_lengths`.
  - DFlash-R1 and CC-LLM-R2 have `tau_mean > 0`.
- Compressed-condition metadata:
  - `compression`
  - `t_compress_ms`
  - `R_actual`
  - `compressor_chunking_mode`
  - `compressor_chunk_token_budget`
  - `compressor_chunk_max_observed_tokens`
  - `compressor_chunk_encoder_max_length`

Baseline-AR and DFlash-R1 are legacy final artifacts generated before the runner protocol fix. Missing `benchmark_protocol_version`, `is_warmup`, `warmup_prompts`, and `benchmark_prompt_index` fields are accepted for Task 45 and recorded as legacy compatibility.

LLMLingua-AR-R2 and CC-LLM-R2 passed protocol checks:

- `benchmark_protocol_version == "per_prompt_jsonl_v1"`
- `is_warmup == false`
- `warmup_prompts == 1`
- `benchmark_prompt_index` covers `1..100` without duplicates

## Log Verification Result

Current final PASS logs:

- `logs/task45_final_llmlingua_ar_r2_n100_2026-06-06_10-21-49.log`
- `logs/task45_final_cc_llm_r2_n100_2026-06-06_11-02-41.log`

Both contain:

- `Final status: PASS`

Neither current final PASS log contains:

- `sequence length is longer`
- `Traceback`
- `RuntimeError`
- `IndexError`
- `out of memory`

Historical failed log:

- `logs/task45_final_llmlingua_ar_r2_n100_2026-06-06_00-46-05.log`

This older log contains the previous encoder-length warning and is classified as a superseded failed attempt, not the current final run.

## Summary Metrics

Metrics below are audited Task 45 measured artifact values. They are not deployment claims.

| Condition | Rows | Avg tok/s | Median tok/s | Avg tau_mean | Median tau_mean | Avg t_prefill_ms | Avg t_compress_ms | Avg R_actual | Max VRAM allocated GiB | Max VRAM reserved GiB | Avg input tokens | Avg output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 100 | 16.91 | 17.26 | 0.00 | 0.00 | 1323.82 | n/a | n/a | 2.5025 | 6.5098 | 1471.22 | 127.46 |
| DFlash-R1 | 100 | 42.87 | 42.24 | 5.27 | 5.12 | 492.37 | n/a | n/a | 3.5109 | 7.5254 | 1471.22 | 127.49 |
| LLMLingua-AR-R2 | 100 | 16.89 | 17.41 | 0.00 | 0.00 | 276.68 | 4057.67 | 2.06 | 2.4789 | 3.2031 | 778.92 | 127.77 |
| CC-LLM-R2 | 100 | 48.26 | 47.99 | 5.06 | 4.94 | 277.75 | 4179.75 | 2.06 | 3.4800 | 4.2207 | 778.92 | 127.74 |

## Diagnostic Quality Audit

The audit reused the existing extraction-aware scoring logic from `scripts/analyze_task31_answer_quality.py`.

This quality pass is diagnostic. It reports containment and numeric extracted-answer match rates from `generated_text` against `expected_answer`, but it is not a final semantic correctness benchmark.

| Condition | Generated text rows | Exact containment | Normalized containment total | Extracted numeric matches | No containment | Not evaluable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 100 | 24 | 25 | 10 | 75 | 0 |
| DFlash-R1 | 100 | 23 | 24 | 10 | 76 | 0 |
| LLMLingua-AR-R2 | 100 | 16 | 17 | 5 | 83 | 0 |
| CC-LLM-R2 | 100 | 18 | 19 | 6 | 81 | 0 |

Interpretation must remain conservative:

- Every final row contains generated text.
- Containment and extraction rates are lower than row count, so Task 46 must treat quality as a key Pareto dimension.
- This audit does not prove semantic correctness or final exact match.

## Known Caveats

- Baseline-AR and DFlash-R1 use a legacy artifact schema from before `per_prompt_jsonl_v1`.
- Compressed-condition final artifacts use the hardened runner protocol.
- Existing logs show torch SDPA fallback because `flash_attn` is not installed.
- CPU `t_compress_ms` remains substantial and must be included in Pareto/e2e analysis.
- Diagnostic answer extraction is format-sensitive and does not replace semantic evaluation.

## Validation

Commands run:

```bash
wc -l results/task45_final_baseline_ar_n100.jsonl results/task45_final_dflash_r1_n100.jsonl results/task45_final_llmlingua_ar_r2_n100.jsonl results/task45_final_cc_llm_r2_n100.jsonl
python3 scripts/analyze_task31_answer_quality.py --help 2>&1 | head -80 || true
python3 scripts/audit_frozen_benchmark_schema.py --help 2>&1 | head -80 || true
python3 scripts/audit_smoke_artifacts.py --help 2>&1 | head -80 || true
PYTHONPATH=src .venv/bin/python scripts/audit_task45_final_artifacts.py --output results/task45_final_artifact_audit_summary.json
```

Remaining validation:

- Compile and full tests were run after documentation updates and are recorded in the final response.

## Understand-Anything Status

Understand-Anything refresh was skipped because `/understand` is not available in this environment.

No graph/dashboard refresh is claimed.

## Task 45 Closeout Decision

PASS for Task 45 final artifact audit.

Task 45 final benchmark artifact set is now complete and auditable:

- 4 artifacts
- 400 rows
- required condition identities
- compatible schema
- compressed PASS logs
- machine-readable audit summary

Next step: Task 46 Pareto analysis/report using the audited Task 45 artifacts.

