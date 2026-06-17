# Task 51 — Staged Two-Dataset Benchmark Expansion Report

Date: 2026-06-11

Status: PASS, preliminary staged benchmark expansion

## Scope

Task 51 expanded the Task 50 tiny two-dataset smoke in two stages:

- Stage A completed the deferred QMSum DFlash paths at `n=3`.
- Stage B ran the frozen two-dataset matrix at `n=10`.

All real runs used unique `results/task51_*` output paths, `--resume`, and `--store-generated-text`. No `--overwrite` flag was used. No `n=100` run was performed.

This is not a final benchmark and does not support final speedup, final correctness, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit.

## Task 50 Commit

Task 50 was already committed before Task 51 started:

- `8aed710 test: add tiny resume-safe benchmark smoke`

## Condition Names

The runner accepted these condition names from `scripts/run_mvp.py`:

- `Baseline-AR`
- `DFlash-R1`
- `LLMLingua-AR-R2`
- `CC-DFlash-R2`

## Stage A Results

| Dataset | Condition | Artifact | Rows | Status | Avg tok/s | Avg tau | Avg T_compress ms | Avg R_actual | Max VRAM allocated GiB | Max VRAM reserved GiB |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `qmsum_meeting_qa_long` | DFlash-R1 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_qmsum_long_dflash_r1_n3.jsonl` | 3 | PASS | 15.25 | 2.65 | 0.00 | 0.00 | 3.51 | 5.32 |
| `qmsum_meeting_qa_long` | CC-DFlash-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_qmsum_long_cc_dflash_r2_n3.jsonl` | 3 | PASS | 21.25 | 2.89 | 5027.84 | 2.06 | 3.51 | 4.39 |

Stage A completed without stall, OOM, or partial-row failure. Because Stage A passed, Stage B was executed.

## Stage B Results

| Dataset | Condition | Artifact | Rows | Status | Avg tok/s | Avg tau | Avg T_compress ms | Avg R_actual | Max VRAM allocated GiB | Max VRAM reserved GiB |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gsm8k_short` | Baseline-AR | `results/phase_1_system_build_and_evaluation/early_experiments/task51_gsm8k_short_baseline_ar_n10.jsonl` | 10 | PASS | 16.72 | 0.00 | 0.00 | 0.00 | 2.50 | 2.61 |
| `gsm8k_short` | LLMLingua-AR-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_gsm8k_short_llmlingua_ar_r2_n10.jsonl` | 10 | PASS | 16.17 | 0.00 | 771.69 | 2.67 | 2.50 | 2.60 |
| `gsm8k_short` | DFlash-R1 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_gsm8k_short_dflash_r1_n10.jsonl` | 10 | PASS | 40.85 | 4.99 | 0.00 | 0.00 | 3.51 | 3.65 |
| `gsm8k_short` | CC-DFlash-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_gsm8k_short_cc_dflash_r2_n10.jsonl` | 10 | PASS | 45.61 | 6.01 | 735.00 | 2.67 | 3.51 | 3.65 |
| `qmsum_meeting_qa_long` | Baseline-AR | `results/phase_1_system_build_and_evaluation/early_experiments/task51_qmsum_long_baseline_ar_n10.jsonl` | 10 | PASS | 12.65 | 0.00 | 0.00 | 0.00 | 2.50 | 4.32 |
| `qmsum_meeting_qa_long` | LLMLingua-AR-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_qmsum_long_llmlingua_ar_r2_n10.jsonl` | 10 | PASS | 12.98 | 0.00 | 5251.99 | 2.07 | 2.50 | 3.42 |
| `qmsum_meeting_qa_long` | DFlash-R1 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_qmsum_long_dflash_r1_n10.jsonl` | 10 | PASS | 15.53 | 2.78 | 0.00 | 0.00 | 3.51 | 5.32 |
| `qmsum_meeting_qa_long` | CC-DFlash-R2 | `results/phase_1_system_build_and_evaluation/early_experiments/task51_qmsum_long_cc_dflash_r2_n10.jsonl` | 10 | PASS | 20.87 | 3.08 | 5221.31 | 2.07 | 3.51 | 4.39 |

## Resume and Artifact Behavior

- Every real run used `--resume`.
- No run used `--overwrite`.
- All output paths were new Task 51 filenames.
- Row checks after each run confirmed the expected count.
- All summarized artifacts had `resume_enabled=True`.
- All summarized artifacts had non-empty `generated_text` in every row.

## Runtime Notes

- No stalls were observed. Long QMSum compressed runs had expected pauses during CPU compression before prompt output appeared.
- No CUDA OOM occurred.
- The highest observed reserved VRAM in this staged expansion was about 5.32 GiB for QMSum DFlash-R1.
- `flash_attn` remains unavailable and the runner used the `torch.sdpa` fallback.
- bitsandbytes emitted upstream FutureWarnings. These were non-blocking.
- QMSum compressed paths spent about 5.0–5.3 seconds per prompt in LLMLingua compression. This is a preliminary smoke observation only.

## Skipped or Deferred Runs

No requested Task 51 Stage A or Stage B run was skipped.

## Interpretation

Task 51 shows the frozen two-dataset matrix can execute at `n=10` under the current Transformers backend with resume-safe artifact writes. The result is still preliminary and should be audited before any larger run.

The numbers in this report are smoke/staged-expansion metrics only. They must not be used as final speedup or final quality claims.

## Verification To Run

- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report

Results:

- Compileall: PASS
- Pytest: PASS, 104 passed, 2 warnings
- HTML sanity: PASS
- Markdown fence balance: PASS
- Artifact row checks: PASS for all ten Task 51 JSONL artifacts

## Recommended Next Task

Task 52 should audit the Task 51 artifacts and produce a metric summary before any further benchmark expansion. Do not proceed to another blind benchmark until schema, generated text, quality proxy readiness, and anomaly checks are complete.
