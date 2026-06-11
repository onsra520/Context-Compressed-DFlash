# Task 54 — Compressed GSM8K Quality Triage Report

Date: 2026-06-11

Status: PASS, preliminary artifact triage

## Scope

Task 54 analyzes existing Task 53 GSM8K `max_new_tokens=128` artifacts only:

- `results/task53_gsm8k_short_baseline_ar_n10_mnt128.jsonl`
- `results/task53_gsm8k_short_dflash_r1_n10_mnt128.jsonl`
- `results/task53_gsm8k_short_llmlingua_ar_r2_n10_mnt128.jsonl`
- `results/task53_gsm8k_short_cc_dflash_r2_n10_mnt128.jsonl`
- `data/eval/gsm8k_100.jsonl`

No new model, compressor, CUDA, or benchmark run was performed. Existing Task 53 artifacts were read only and not modified.

Task 53 was already committed before this task:

- `107d974 test: calibrate gsm8k quality token budget`

## Outputs

- `scripts/analyze_task54_compressed_gsm8k_triage.py`
- `results/task54_compressed_gsm8k_failure_triage.json`
- `results/task54_compressed_gsm8k_failure_samples.jsonl`

## Command

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_task54_compressed_gsm8k_triage.py
```

## Per-Condition Quality Summary

Numeric extraction is treated as the primary GSM8K quality proxy. Exact containment is diagnostic because short numeric answers can appear as unrelated intermediate numbers.

| Condition | Rows | Exact containment | Numeric extraction match | Hit max_new_tokens | Primary labels |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline-AR | 10 | 5 | 2 | 10 | MODEL_FAIL_UNCOMPRESSED: 8; PASS_MATCH: 2 |
| DFlash-R1 | 10 | 5 | 2 | 10 | MODEL_FAIL_UNCOMPRESSED: 8; PASS_MATCH: 2 |
| LLMLingua-AR-R2 | 10 | 3 | 0 | 10 | TRUNCATION_LIKELY: 8; COMPRESSION_LOSS_LIKELY: 2 |
| CC-DFlash-R2 | 10 | 3 | 0 | 10 | TRUNCATION_LIKELY: 8; COMPRESSION_LOSS_LIKELY: 2 |

Overall label counts across all 40 condition rows:

| Label | Count |
| --- | ---: |
| MODEL_FAIL_UNCOMPRESSED | 16 |
| TRUNCATION_LIKELY | 16 |
| COMPRESSION_LOSS_LIKELY | 4 |
| PASS_MATCH | 4 |

## Representative Failure Examples

| Fixture | Condition | Expected | Extracted | Label | Notes |
| --- | --- | ---: | ---: | --- | --- |
| `gsm8k_short_test_0014` | LLMLingua-AR-R2 | 1430 | 80 | TRUNCATION_LIKELY | Output stops while computing `500 + 80...`; answer not reached. |
| `gsm8k_short_test_0014` | CC-DFlash-R2 | 1430 | 10 | TRUNCATION_LIKELY | Output reaches insurance step but stops before final calculation. |
| `gsm8k_short_test_0018` | LLMLingua-AR-R2 | 66 | 2 | COMPRESSION_LOSS_LIKELY | Baseline-AR and DFlash-R1 reached numeric answer 66; compressed output stops during pencil calculation. |
| `gsm8k_short_test_0018` | CC-DFlash-R2 | 66 | 2 | COMPRESSION_LOSS_LIKELY | Same sample fails after compression while uncompressed conditions succeed. |
| `gsm8k_short_test_0029` | LLMLingua-AR-R2 | 14 | 20 | TRUNCATION_LIKELY | Output restates bus counts and stops at the 20-person condition without solving for the initial count. |

## Compression Loss Assessment

Compression loss is likely in a small subset, but not proven directly from these artifacts:

- 4 compressed rows are labeled `COMPRESSION_LOSS_LIKELY`.
- These cases occur where uncompressed rows produce the correct numeric answer while compressed rows do not.
- Task 53 artifacts do not store the compressed prompt text, so direct auditing of removed numbers/relations is not possible from existing rows.
- `question_preserved=True` is present on compressed rows, but that does not prove all reasoning-critical context or prompt structure survived compression.

The strongest current explanation is mixed:

1. **Truncation / no final-answer line dominates**: every row hit `max_new_tokens=128`, and many outputs are mid-reasoning.
2. **Compression risk is present**: some compressed rows fail when uncompressed rows succeed.
3. **Exact containment is noisy**: short answers such as `5`, `6`, or `12` can appear as unrelated intermediate numbers, so numeric extraction should remain primary.

## Should max_new_tokens=192/256 Be Tested?

Yes, but only as a tiny calibration, not a larger benchmark.

Rationale:

- 128 still leaves many outputs capped mid-reasoning.
- A slightly larger cap may reveal whether failures are simply unfinished reasoning.
- It should be paired with prompt formatting changes so the model is encouraged to emit a short extractable final answer instead of extended derivations.

## Should Prompt Format Be Changed?

Yes.

Recommended prompt adjustment before another quality run:

- Preserve the existing math question.
- Add a stricter final-answer requirement, for example: `End with exactly one line: Final answer: <number>`.
- Keep generated text stored for audit.
- For compressed conditions, store enough compressed-prompt metadata or a safe excerpt to audit whether compression removed critical numbers or relations.

## Conservative Next-Run Recommendation

Do not run n=100 yet.

Recommended next task:

1. Add a prompt-format calibration for GSM8K that requires a short final-answer line.
2. Add optional compressed-prompt audit metadata for compressed GSM8K smoke artifacts.
3. Run a tiny GSM8K calibration, for example n=10 with `max_new_tokens=192` or `256`, only after the prompt/output policy is updated.
4. Continue treating all results as preliminary until larger and cleaner quality evidence exists.

## Validation

Commands run:

- `PYTHONPATH=src .venv/bin/python scripts/analyze_task54_compressed_gsm8k_triage.py`
- `python3 -m json.tool results/task54_compressed_gsm8k_failure_triage.json`
- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report

Validation results are recorded in the final task response.

## Understand-Anything

`.understand-anything/meta.json` was read before task completion. `/understand` refresh was skipped because `/understand` is not available in this environment.
