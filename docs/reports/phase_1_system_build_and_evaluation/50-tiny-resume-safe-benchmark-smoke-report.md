# Task 50 — Tiny Resume-Safe Two-Dataset Benchmark Smoke Report

Date: 2026-06-11

Status: PASS, preliminary smoke only

## Scope

Task 50 ran a tiny real benchmark smoke on the post-Task-48 two-dataset setup to verify that the frozen Task 49 matrix can execute beyond prompt dry-run. This was intentionally not a full benchmark.

No full `n=100` run was performed. All real runs used `n=3`, `seed=42`, unique `results/phase_1_system_build_and_evaluation/early_experiments/task50_*` output filenames, `--resume`, and `--store-generated-text`.

## Task 49 Commit

Task 49 was already committed before Task 50 execution:

- `deefa3f docs: freeze two-dataset benchmark matrix`

## Prompt Dry-Runs

Commands:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --n 3 --seed 42 --dry-run-prompts`

Results:

- `gsm8k_short`: DRY-RUN-PASS
- `qmsum_meeting_qa_long`: DRY-RUN-PASS

## Execution Order

The run order followed the requested lightest-first policy:

1. `gsm8k_short` Baseline-AR
2. `gsm8k_short` LLMLingua-AR-R2
3. `gsm8k_short` DFlash-R1
4. `gsm8k_short` CC-DFlash-R2
5. `qmsum_meeting_qa_long` Baseline-AR
6. `qmsum_meeting_qa_long` LLMLingua-AR-R2

QMSum DFlash-R1 and QMSum CC-DFlash-R2 were intentionally deferred to avoid expanding this tiny smoke into a heavier long-context DFlash run.

## Commands Executed

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition Baseline-AR --n 3 --seed 42 --output results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_baseline_ar_n3.jsonl --resume --store-generated-text

PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 3 --seed 42 --output results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_llmlingua_ar_r2_n3.jsonl --resume --store-generated-text

PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition DFlash-R1 --n 3 --seed 42 --output results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_dflash_r1_n3.jsonl --resume --store-generated-text

PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 3 --seed 42 --output results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_cc_dflash_r2_n3.jsonl --resume --store-generated-text

PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition Baseline-AR --n 3 --seed 42 --output results/phase_1_system_build_and_evaluation/early_experiments/task50_qmsum_long_baseline_ar_n3.jsonl --resume --store-generated-text

PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition LLMLingua-AR-R2 --n 3 --seed 42 --output results/phase_1_system_build_and_evaluation/early_experiments/task50_qmsum_long_llmlingua_ar_r2_n3.jsonl --resume --store-generated-text
```

## Completed Runs and Artifacts

| Dataset | Condition | Artifact | Rows | Status | Avg tok/s | Avg tau | Avg T_compress ms | Avg R_actual | Max VRAM allocated GiB | Max VRAM reserved GiB |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gsm8k_short` | Baseline-AR | `results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_baseline_ar_n3.jsonl` | 3 | PASS | 13.47 | 0.00 | 0.00 | 0.00 | 2.50 | 2.61 |
| `gsm8k_short` | LLMLingua-AR-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_llmlingua_ar_r2_n3.jsonl` | 3 | PASS | 16.45 | 0.00 | 1025.21 | 2.67 | 2.50 | 2.60 |
| `gsm8k_short` | DFlash-R1 | `results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_dflash_r1_n3.jsonl` | 3 | PASS | 36.32 | 5.00 | 0.00 | 0.00 | 3.51 | 3.65 |
| `gsm8k_short` | CC-DFlash-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task50_gsm8k_short_cc_dflash_r2_n3.jsonl` | 3 | PASS | 44.22 | 7.08 | 817.10 | 2.67 | 3.51 | 3.65 |
| `qmsum_meeting_qa_long` | Baseline-AR | `results/phase_1_system_build_and_evaluation/early_experiments/task50_qmsum_long_baseline_ar_n3.jsonl` | 3 | PASS | 12.42 | 0.00 | 0.00 | 0.00 | 2.50 | 4.32 |
| `qmsum_meeting_qa_long` | LLMLingua-AR-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task50_qmsum_long_llmlingua_ar_r2_n3.jsonl` | 3 | PASS | 13.88 | 0.00 | 5244.05 | 2.06 | 2.50 | 3.42 |

All completed artifacts contain generated text.

## Resume Behavior

All real runs used `--resume`.

Each output file was unique to Task 50 and had `Resumed from rows: 0` at run start. The runner used `write_new_resume` mode and wrote rows incrementally.

No `--overwrite` flag was used.

## Skipped or Deferred Runs

Deferred:

- `qmsum_meeting_qa_long` DFlash-R1
- `qmsum_meeting_qa_long` CC-DFlash-R2 / CC-LLM-R2

Reason: the task asked to run QMSum DFlash/CC-DFlash only if still stable and allowed deferral for runtime/VRAM risk. The lightweight QMSum AR paths passed and are enough to verify the dataset path plus compression path without expanding this task into a heavier long-context DFlash run.

## Runtime Notes

- No stalls were observed.
- No OOM occurred.
- `flash_attn` remains unavailable, so the backend warning was `torch.sdpa` fallback.
- bitsandbytes emitted upstream FutureWarnings; these are non-blocking library warnings already known from prior tasks.
- QMSum LLMLingua-AR-R2 showed materially higher CPU compression time than GSM8K, as expected for longer context, but this is a tiny smoke observation only.

## Claim Policy

This task does not establish final speedup, final correctness, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit.

The reported numbers are preliminary smoke metrics only.

## Verification

Commands run:

- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report
- Task 50 artifact row check for row count, `resume_enabled`, and `generated_text`

Results:

- Compileall: PASS
- Pytest: PASS, 104 passed, 2 warnings
- HTML sanity: PASS
- Markdown fence balance: PASS
- Artifact row check: all six Task 50 artifacts have 3 rows, `resume_enabled=True`, and `generated_text`

## Understand-Anything

`.understand-anything/meta.json` was read. The latest metadata reports:

- `lastAnalyzedAt`: `2026-06-05T13:38:38.313379Z`
- `gitCommitHash`: `6e87fd48065a9b568ef27aa1ed3dfa245c4b0fd8`
- `analyzedFiles`: 163

Understand-Anything refresh was skipped because `/understand` is not available as a slash command in this environment.

## Recommendation

Next task: audit Task 50 artifacts and quality fields, then decide whether to run the deferred QMSum DFlash/CC-DFlash smoke or proceed to a slightly larger two-dataset benchmark. Keep using unique output filenames and `--resume`.
