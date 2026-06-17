# Task 49 — Two-Dataset Benchmark Matrix Freeze Report

Date: 2026-06-11

Status: PASS

## Scope

Task 49 freezes the benchmark matrix and execution policy after Task 48 migrated CC-DFlash to the two-dataset evaluation setup:

- `gsm8k_short`: `data/eval/gsm8k_100.jsonl`
- `qmsum_meeting_qa_long`: `data/eval/qmsum_meeting_qa_100.jsonl`

This is a planning and specification task only. It does not run GPU/model/compressor benchmarks, does not load CUDA, and does not modify result artifacts.

## Why Task 49 Is Needed

Task 48 changed the main dataset plan from the old GSM8K+Wikipedia augmented path to two evaluation datasets reused from the LLMLingua-2-Preproduction style. The benchmark matrix needed to be frozen after that migration so future runs compare the same conditions on the same dataset roles without mixing short-context quality and long-context speed claims.

The old GSM8K+Wikipedia augmented files remain legacy/optional ablation only. They are not the main post-Task-48 dataset plan.

## Frozen Matrix

| Dataset | Condition | Purpose | Primary metrics |
| --- | --- | --- | --- |
| `gsm8k_short` | Baseline-AR | Target autoregressive baseline; no compression, no DFlash | Numeric exact-match proxy, invalid output rate; latency and tok/s secondary |
| `gsm8k_short` | DFlash-R1 | No-compression DFlash baseline on full prompt | Numeric exact-match proxy, invalid output rate; latency and tok/s secondary |
| `gsm8k_short` | LLMLingua-AR-R2 | Compression-only attribution baseline with `keep_rate=0.5`, no DFlash | Numeric exact-match proxy, invalid output rate, `T_compress`, `R_actual` |
| `gsm8k_short` | CC-DFlash-R2 / CC-LLM-R2 | Main CC-DFlash condition with `keep_rate=0.5` and DFlash decoding | Numeric exact-match proxy, invalid output rate, `T_compress`, `R_actual`, `tau_mean` |
| `qmsum_meeting_qa_long` | Baseline-AR | Target autoregressive long-context latency baseline | End-to-end latency, `T_prefill`, tok/s, VRAM |
| `qmsum_meeting_qa_long` | DFlash-R1 | No-compression DFlash long-context baseline on full prompt | End-to-end latency, `T_prefill`, tok/s, `tau_mean`, VRAM |
| `qmsum_meeting_qa_long` | LLMLingua-AR-R2 | Compression-only long-context attribution baseline with `keep_rate=0.5`, no DFlash | `T_compress`, `T_prefill`, end-to-end latency, `R_actual`, input token reduction, VRAM |
| `qmsum_meeting_qa_long` | CC-DFlash-R2 / CC-LLM-R2 | Main long-context CC-DFlash condition with `keep_rate=0.5` and DFlash decoding | `T_compress`, `T_prefill`, end-to-end latency, tok/s, `R_actual`, `tau_mean`, VRAM |

## Condition Definitions

- Baseline-AR: no compression, no DFlash, target autoregressive baseline.
- DFlash-R1: no compression, DFlash decoding, full prompt.
- LLMLingua-AR-R2: LLMLingua-2 compression, `keep_rate=0.5`, no DFlash; attribution baseline for compression-only benefit.
- CC-DFlash-R2 / CC-LLM-R2: LLMLingua-2 compression, `keep_rate=0.5`, DFlash decoding; main CC-DFlash condition.

## Dataset-Specific Metrics

### `gsm8k_short`

Main role: short-context numeric QA quality and answer extraction.

Primary metrics:

- extracted numeric exact-match proxy
- invalid output rate
- generated-text availability for audit

Secondary metrics:

- latency
- tok/s
- VRAM

Compression speedup should not be expected to be strong on this dataset because the prompts are short and LLMLingua-2 `T_compress` may dominate any prefill savings.

### `qmsum_meeting_qa_long`

Main role: long-context speed, prefill, compression overhead, and input-reduction behavior.

Primary metrics:

- end-to-end latency
- `T_compress`
- `T_prefill`
- tok/s
- compression ratio / input token reduction
- `R_actual`
- `tau_mean`
- VRAM allocated/reserved

Quality metric:

- normalized containment / long-answer proxy / manual review when needed

Do not claim exact semantic correctness on QMSum-style meeting QA without manual review or a semantic judge.

## Claim Policy

Task 49 does not support final claims. Future reports must continue to avoid claims of:

- final speedup
- final correctness
- deployment readiness
- confirmed 8 GB deployment
- proven end-to-end compression benefit
- CC-DFlash superiority over DFlash-R1 unless measured benchmark evidence supports it

CC-DFlash remains an end-to-end hypothesis evaluation. Compression is useful only if prefill savings plus DFlash decoding gain outweigh LLMLingua-2 `T_compress` while preserving quality.

## Explicitly Not Done

- No benchmark run.
- No model loading.
- No compressor loading.
- No CUDA execution.
- No `results/` artifacts modified.
- No dataset JSONL files changed.
- No legacy dataset files deleted.

## Verification

Commands to run for this task:

- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --n 3 --seed 42 --dry-run-prompts`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report.

Results are recorded in the final task response.

## Recommended Next Task

Task 50 should run a tiny dry-run/smoke benchmark execution on both datasets using the frozen matrix, with `n=3` or `n=5`, before any full `n=100` run.
