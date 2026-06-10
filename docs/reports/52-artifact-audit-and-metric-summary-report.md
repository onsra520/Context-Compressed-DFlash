# Task 52 — Artifact Audit and Metric Summary Report

Date: 2026-06-11

Status: PASS, preliminary smoke-level audit

## Scope

Task 52 audits and summarizes existing Task 50/51 benchmark smoke artifacts only:

- `results/task50_*_n3.jsonl`
- `results/task51_*_n3.jsonl`
- `results/task51_*_n10.jsonl`

No new model, compressor, CUDA, or benchmark run was performed. No result artifact from Task 50 or Task 51 was modified.

Generated outputs:

- `scripts/analyze_task52_artifacts.py`
- `results/task52_metric_summary.json`
- `results/task52_metric_table.csv`

## Commands

Analysis command:

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_task52_artifacts.py
```

Validation command for generated JSON:

```bash
python3 -m json.tool results/task52_metric_summary.json
```

## Artifact Audit Result

The analyzer read 16 artifacts and classified all as PASS for schema and row-count consistency:

- 6 Task 50 n=3 artifacts
- 2 Task 51 Stage A n=3 artifacts
- 8 Task 51 Stage B n=10 artifacts

Every audited artifact had:

- valid JSONL rows
- stable single condition per artifact
- expected dataset metadata
- generated text present and non-empty for all rows
- `resume_enabled=True`
- `t_prefill_ms`
- VRAM allocated/reserved fields
- compression fields for LLMLingua/CC-DFlash rows
- non-empty `acceptance_lengths` for DFlash rows with generated output

## Metric Summary

| Stage | Dataset | Condition | Rows | Gen tok/s | E2E tok/s | T_compress ms | T_prefill ms | R_actual | Tau | Max VRAM reserved GiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Task 50 n=3 | `gsm8k_short` | Baseline-AR | 3 | 13.47 | 13.46 | 0.00 | 256.40 | 0.00 | 0.00 | 2.61 |
| Task 50 n=3 | `gsm8k_short` | LLMLingua-AR-R2 | 3 | 16.45 | 10.76 | 1025.21 | 215.56 | 2.67 | 0.00 | 2.60 |
| Task 50 n=3 | `gsm8k_short` | DFlash-R1 | 3 | 36.32 | 34.65 | 0.00 | 207.73 | 0.00 | 5.00 | 3.65 |
| Task 50 n=3 | `gsm8k_short` | CC-DFlash-R2 | 3 | 44.22 | 20.16 | 817.10 | 214.25 | 2.67 | 7.08 | 3.65 |
| Task 50 n=3 | `qmsum_meeting_qa_long` | Baseline-AR | 3 | 12.42 | 12.41 | 0.00 | 772.80 | 0.00 | 0.00 | 4.32 |
| Task 50 n=3 | `qmsum_meeting_qa_long` | LLMLingua-AR-R2 | 3 | 13.88 | 4.24 | 5244.05 | 455.07 | 2.06 | 0.00 | 3.42 |
| Task 51 n=3 | `qmsum_meeting_qa_long` | DFlash-R1 | 3 | 15.25 | 15.02 | 0.00 | 828.74 | 0.00 | 2.65 | 5.32 |
| Task 51 n=3 | `qmsum_meeting_qa_long` | CC-DFlash-R2 | 3 | 21.25 | 4.90 | 5027.84 | 452.70 | 2.06 | 2.89 | 4.39 |
| Task 51 n=10 | `gsm8k_short` | Baseline-AR | 10 | 16.72 | 16.70 | 0.00 | 126.96 | 0.00 | 0.00 | 2.61 |
| Task 51 n=10 | `gsm8k_short` | LLMLingua-AR-R2 | 10 | 16.17 | 11.60 | 771.69 | 130.60 | 2.67 | 0.00 | 2.60 |
| Task 51 n=10 | `gsm8k_short` | DFlash-R1 | 10 | 40.85 | 38.46 | 0.00 | 127.07 | 0.00 | 4.99 | 3.65 |
| Task 51 n=10 | `gsm8k_short` | CC-DFlash-R2 | 10 | 45.61 | 21.64 | 735.00 | 125.81 | 2.67 | 6.01 | 3.65 |
| Task 51 n=10 | `qmsum_meeting_qa_long` | Baseline-AR | 10 | 12.65 | 12.64 | 0.00 | 704.28 | 0.00 | 0.00 | 4.32 |
| Task 51 n=10 | `qmsum_meeting_qa_long` | LLMLingua-AR-R2 | 10 | 12.98 | 4.14 | 5251.99 | 425.97 | 2.07 | 0.00 | 3.42 |
| Task 51 n=10 | `qmsum_meeting_qa_long` | DFlash-R1 | 10 | 15.53 | 15.25 | 0.00 | 730.97 | 0.00 | 2.78 | 5.32 |
| Task 51 n=10 | `qmsum_meeting_qa_long` | CC-DFlash-R2 | 10 | 20.87 | 4.72 | 5221.31 | 431.35 | 2.07 | 3.08 | 4.39 |

`E2E tok/s` is computed from output tokens divided by generation time plus `T_compress` where present. It is approximate and smoke-level.

## GSM8K Quality Summary

Task 51 n=10 GSM8K numeric extraction diagnostics:

| Condition | Rows | Exact containment | Numeric extraction match | Extracted wrong | Missing/truncated final answer |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 10 | 2 | 0 | 8 | 0 |
| LLMLingua-AR-R2 | 10 | 3 | 1 | 5 | 2 |
| DFlash-R1 | 10 | 2 | 0 | 8 | 0 |
| CC-DFlash-R2 | 10 | 3 | 1 | 5 | 2 |

Interpretation:

- GSM8K quality remains weak under the current 32-token output cap.
- Exact containment counts are not final correctness.
- Numeric extraction match is the frozen deterministic proxy, but this n=10 smoke is too small for final EM claims.
- Compressed rows did not show missing generated text, but some rows lacked a final extractable numeric answer.

## QMSum Output Sanity

Task 51 n=10 QMSum-style output sanity:

| Condition | Rows | Generated text present | Empty generated text | Repetition warnings | Normalized containment |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 10 | 10 | 0 | 0 | 0 |
| LLMLingua-AR-R2 | 10 | 10 | 0 | 0 | 0 |
| DFlash-R1 | 10 | 10 | 0 | 0 | 0 |
| CC-DFlash-R2 | 10 | 10 | 0 | 0 | 0 |

Interpretation:

- QMSum generated text is present and non-empty across all audited rows.
- The simple repetition heuristic did not flag obvious repeated 4-gram loops.
- Normalized containment is 0/10 for all conditions. This is not a semantic correctness result; QMSum-style meeting QA requires manual review or a semantic judge for stronger quality claims.

## Condition Comparisons

Task 51 n=10 directional comparisons:

- `gsm8k_short`: CC-DFlash-R2 beats DFlash-R1 generation-only tok/s by about 1.12×, but loses on approximate e2e time once `T_compress` is included. CC-DFlash-R2 e2e time is about 1.78× DFlash-R1.
- `qmsum_meeting_qa_long`: CC-DFlash-R2 beats DFlash-R1 generation-only tok/s by about 1.34×, but loses on approximate e2e time once `T_compress` is included. CC-DFlash-R2 e2e time is about 3.38× DFlash-R1.
- DFlash-R1 improves generation-only tok/s over Baseline-AR in both Task 51 n=10 datasets.
- LLMLingua-AR-R2 e2e time is slower than Baseline-AR in both Task 51 n=10 datasets because compression overhead dominates.

## Conservative Interpretation

Task 52 supports these preliminary, smoke-level observations only:

- The Task 50/51 artifacts are structurally usable for analysis.
- DFlash decoding is directionally faster than Baseline-AR in generation-only terms.
- CC-DFlash-R2 is directionally faster than DFlash-R1 in generation-only tok/s, but not in approximate end-to-end time under current CPU LLMLingua compression overhead.
- LLMLingua overhead dominates the compressed conditions in both short-context and long-context smokes.
- CC-DFlash does not beat DFlash-R1 on approximate e2e time in the audited Task 51 n=10 artifacts.
- QMSum quality cannot be judged semantically from containment alone.

This does not establish final speedup, final correctness, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit.

## Next-Run Recommendation

Recommended next task:

1. Do not run another blind benchmark immediately.
2. First decide the quality path:
   - For GSM8K, rerun a small quality-calibration subset with `max_new_tokens>=128`.
   - For QMSum, add manual review or semantic judging before claiming quality.
3. If the next run is performance-oriented, use the Task 51 n=10 audit as the planning baseline and keep reporting both generation-only and e2e-with-compression metrics.
4. If the next run expands n, keep `--resume`, unique output paths, and generated-text storage.

## Validation

Commands run:

- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report
- `python3 -m json.tool results/task52_metric_summary.json`
- `PYTHONPATH=src .venv/bin/python scripts/analyze_task52_artifacts.py`

Results:

- Analyzer: PASS across 16 artifacts.
- JSON summary: valid JSON.
- Compile check: PASS.
- Pytest: PASS, 104 passed with 2 existing import warnings.
- HTML sanity: PASS, no files reported missing `<!DOCTYPE html>` or `</html>`.
- Markdown fence balance: PASS for `instruction.md` and this report.

Understand-Anything:

- `.understand-anything/meta.json` was read successfully.
- `/understand` refresh was skipped because `/understand` is not available in this environment.
