# Task 40 — Breakeven Curve v1


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-04

## Result

PARTIAL, preliminary.

Task 40 produced a machine-readable breakeven v1 summary from existing artifacts, but it does not prove a real breakeven curve. The current data combines Task 39 Baseline-AR measured `T_prefill` with Task 31 compressed-condition `T_compress` and `R_actual`. The compressed-condition artifacts do not yet include measured `T_prefill`, so the result is a conservative planning artifact rather than a final speedup conclusion.

## Scope

- Added `scripts/breakeven_curve_v1.py`.
- Added unit tests in `tests/test_breakeven_curve_v1.py`.
- Generated `results/task40_breakeven_curve_v1_summary.json`.
- Updated `docs/Roadmap.html` to mark Task 40 as PARTIAL/preliminary and set Task 41 as next.
- Updated `docs/CC-DFlash-Overview.html` to reflect that Task 40 is a partial preliminary summary, not a confirmed breakeven curve.

No benchmarks were run. No models were loaded. No old result artifacts were overwritten.

## Inputs

| Input | Role |
| --- | --- |
| `results/task39_t_prefill_smoke.jsonl` | Baseline-AR target prefill reference |
| `results/task31_dflash_r1_longctx_text_n6.jsonl` | No-compression DFlash reference |
| `results/task31_cc_llm_r2_longctx_text_n6.jsonl` | CC-LLM R2 compression timing and ratio |
| `results/task31_cc_llm_r3_longctx_text_n6.jsonl` | CC-LLM R3 compression timing and ratio |
| `results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl` | AR R2 compression timing and ratio |
| `results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | AR R3 compression timing and ratio |

## Method

The script computes:

- average `T_prefill` from Task 39 rows
- average `T_compress` from compressed rows
- average `R_actual`
- breakeven full-prefill threshold:
  `required_full_prefill_ms = T_compress / (1 - 1 / R_actual^2)`
- reference margin against the tiny Task 39 Baseline-AR prefill
- an explicitly labeled quadratic-scaling estimate from Task 39 input length to Task 31 average original context length
- data sufficiency status per condition

Rows without compressed-condition `T_prefill` are labeled `insufficient_measured_compressed_t_prefill`.

## Exact Command

```bash
PYTHONPATH=src .venv/bin/python scripts/breakeven_curve_v1.py
```

## Generated Artifact

`results/task40_breakeven_curve_v1_summary.json`

The generated summary is valid JSON and has top-level status `PARTIAL`.

## Prefill Reference

| Field | Value |
| --- | ---: |
| Artifact | `results/task39_t_prefill_smoke.jsonl` |
| Rows | 1 |
| Condition | Baseline-AR |
| Average input tokens | 19.00 |
| Average `T_prefill` | 504.99 ms |
| Timing mode | cuda_synchronized |
| Max prefill VRAM allocated | 2.502471446990967 GiB |
| Max prefill VRAM reserved | 2.583984375 GiB |

## Condition Summary

| Condition | Status | Rows | Rows with `T_prefill` | Avg `T_compress` ms | Avg `R_actual` | Required full prefill ms | Reference margin ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | no_compression_reference | 6 | 0 | n/a | n/a | n/a | n/a |
| CC-LLM-R2 | insufficient_measured_compressed_t_prefill | 6 | 0 | 891.10 | 2.03 | 1175.39 | -508.25 |
| CC-LLM-R3 | insufficient_measured_compressed_t_prefill | 6 | 0 | 826.25 | 3.02 | 928.25 | -376.75 |
| LLMLingua-AR-R2 | insufficient_measured_compressed_t_prefill | 6 | 0 | 797.86 | 2.03 | 1052.40 | -415.01 |
| LLMLingua-AR-R3 | insufficient_measured_compressed_t_prefill | 6 | 0 | 822.23 | 3.02 | 923.73 | -372.73 |

## Interpretation

The tiny Task 39 Baseline-AR reference prefill is shorter than the Task 31 long-context compressed artifacts, so direct reference-margin values are not evidence of final breakeven behavior.

The quadratic-scaling estimate is useful only as planning math. It suggests that longer contexts may be the right place to test compression breakeven, but it does not prove that compression is worthwhile end to end. A real curve requires measuring `T_prefill` for the same compressed-condition prompts, context lengths, and model path.

Task 40 therefore supports Task 41+ planning, but it does not close the breakeven question.

## Limitations

- No compressed-condition artifact contains measured `T_prefill`.
- Task 39 prefill reference has only one Baseline-AR row.
- The quadratic estimate assumes idealized prefill scaling and should not be treated as a measured result.
- Existing Task 31 artifacts are small synthetic long-context fixtures, not final dataset benchmarks.
- No final speedup, correctness, deploy readiness, confirmed 8 GB deployment, or proven compression benefit is claimed.

## Validation

- `PYTHONPATH=src .venv/bin/python scripts/breakeven_curve_v1.py`: PASS
- `python3 -m json.tool results/task40_breakeven_curve_v1_summary.json`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_breakeven_curve_v1.py -q`: PASS, 3 passed

## Next Step

Task 41: build the GSM8K + Wikipedia augmented dataset pipeline with documented source, augmentation policy, leakage controls, and artifact format.
