# Task 69 — GSM8K n=30 Full Matrix with Frozen Quality Setting

Date: 2026-06-13

Status: PASS, preliminary n=30 matrix

## Scope

Task 69 ran the missing uncompressed GSM8K n=30 matrix rows at the frozen quality-oriented setting and reused matching compressed Task 66 artifacts read-only. This is not an n=100 run, not QMSum, and not a final correctness or speedup claim.

Task 68 commit:

- `d743d83 docs: freeze gsm8k final settings`

## Commands Run

Prompt dry-run:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts`
- Direct formatter check confirmed sampled prompts end with `Final answer: <number>`.

Baseline-AR:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition Baseline-AR --n 30 --seed 42 --max-new-tokens 384 --output results/phase_1_system_build_and_evaluation/early_experiments/task69_gsm8k_short_baseline_ar_n30_mnt384.jsonl --resume --store-generated-text`

DFlash-R1:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition DFlash-R1 --n 30 --seed 42 --max-new-tokens 384 --output results/phase_1_system_build_and_evaluation/early_experiments/task69_gsm8k_short_dflash_r1_n30_mnt384.jsonl --resume --store-generated-text`

Analyzer:

- `PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t69_gsm8k_full_matrix.py`

## Artifact Use

New Task 69 artifacts:

| Condition | Artifact | Rows | Status |
| --- | --- | ---: | --- |
| Baseline-AR | `results/phase_1_system_build_and_evaluation/early_experiments/task69_gsm8k_short_baseline_ar_n30_mnt384.jsonl` | 30 | Created |
| DFlash-R1 | `results/phase_1_system_build_and_evaluation/early_experiments/task69_gsm8k_short_dflash_r1_n30_mnt384.jsonl` | 30 | Created |

Reused read-only artifacts:

| Condition | Artifact | Rows | Reuse check |
| --- | --- | ---: | --- |
| LLMLingua-AR-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl` | 30 | PASS |
| CC-DFlash-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl` | 30 | PASS |

Compressed reuse checks verified:

- dataset: `gsm8k_short`
- prompt source: `dataset`
- n=30 sample ids match `seed=42`
- `max_new_tokens=384`
- `keep_rate=0.50`
- `protected_suffix_preserved=30/30`
- generated text exists for every row

## Full n=30 Quality Table

| Condition | Rows | Numeric matches | Numeric rate | Exact containment | Final-answer markers | Cap hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 30 | 25 | 0.833333 | 25 | 30 | 0 |
| DFlash-R1 | 30 | 24 | 0.800000 | 25 | 30 | 1 |
| LLMLingua-AR-R2 | 30 | 24 | 0.800000 | 25 | 25 | 3 |
| CC-DFlash-R2 | 30 | 24 | 0.800000 | 25 | 26 | 3 |

## Full n=30 Latency and Speed Table

| Condition | Avg output tokens | Avg generation latency s | Avg e2e latency s | Avg T_compress ms | Gen tok/s weighted | E2E tok/s weighted | Avg tau_mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 174.83 | 9.71 | 9.71 | 0.00 | 18.01 | 18.01 | 0.00 |
| DFlash-R1 | 168.83 | 2.99 | 2.99 | 0.00 | 56.47 | 56.47 | 5.21 |
| LLMLingua-AR-R2 | 172.80 | 9.72 | 10.56 | 833.99 | 17.77 | 16.37 | 0.00 |
| CC-DFlash-R2 | 175.37 | 3.24 | 4.11 | 869.04 | 54.12 | 42.67 | 5.46 |

Compressed rows average compression ratio: `2.67`, with average original/compressed input token metadata of `16.0 -> 6.0`.

## Comparisons

Baseline-AR vs DFlash-R1:

- DFlash-R1 is much faster than Baseline-AR in this n=30 smoke matrix: e2e tok/s ratio `3.14x`.
- DFlash-R1 has one fewer numeric match than Baseline-AR: `24/30` vs `25/30`.

LLMLingua-AR-R2 vs CC-DFlash-R2:

- CC-DFlash-R2 matches LLMLingua-AR-R2 quality: both are `24/30`.
- CC-DFlash-R2 improves e2e tok/s relative to LLMLingua-AR-R2: `42.67` vs `16.37`, ratio `2.61x`.

Compressed quality vs uncompressed paths:

- Best uncompressed numeric rate: `25/30 = 0.833333`.
- Best compressed numeric rate: `24/30 = 0.800000`.
- Compressed quality gap to best uncompressed path: `-0.033333`, within 10 percentage points.

DFlash-R1 vs CC-DFlash-R2:

- Both have `24/30` numeric matches.
- DFlash-R1 remains faster on e2e tok/s: `56.47` vs `42.67`.
- CC-DFlash-R2 is therefore not the speed winner on short-context GSM8K; its main value should be judged later on long-context/QMSum-style work where compression may reduce prefill more meaningfully.

## n=100 Gate

n=100 is conditionally justified next for a bounded GSM8K matrix because:

- the comparable n=30 matrix completed,
- CC-DFlash-R2 matches LLMLingua-AR-R2 quality,
- CC-DFlash-R2 is faster than LLMLingua-AR-R2 on e2e tok/s,
- compressed quality is within 10 percentage points of the uncompressed best.

This does not justify final claims. The next n=100 run, if accepted, should remain preliminary, resume-safe, and GSM8K-only.

Recommended next task:

- Task 70: bounded GSM8K n=100 full matrix using frozen quality-oriented setting (`max_new_tokens=384`, `seed=42`, `--resume`, `--store-generated-text`, unique `results/task70_*` artifacts).

## Limitations

- n=30 is still small.
- GSM8K is short-context; compression overhead may dominate.
- Numeric extraction is a deterministic proxy, not final semantic correctness.
- QMSum long-context behavior is not covered here.
- The compressed artifacts were reused from Task 66 and not rerun.

## Validation

Commands run:

- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `python3 -m json.tool results/phase_1_system_build_and_evaluation/early_experiments/task69_gsm8k_full_matrix_summary.json >/dev/null`
- HTML sanity checks for `<!DOCTYPE html>` and `</html>`
- Markdown fence balance checks for `instruction.md` and this report

Result: validation passed.
