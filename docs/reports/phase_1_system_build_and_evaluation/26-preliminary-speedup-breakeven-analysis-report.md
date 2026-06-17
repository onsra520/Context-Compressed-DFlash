# 26 Preliminary Speedup, Tau, Compression, and Breakeven Analysis Report

## Task Title and Date

- Task: Preliminary analysis of speedup, tau, compression, and breakeven
- Date: 2026-06-04

## Scope

This report is preliminary only. It analyzes the existing Task 24 small-matrix artifacts together with the Task 25 long-context fixture summary. It does not run new GPU benchmarks, does not claim production readiness, and does not claim that compression is proven worthwhile.

## Inputs Used

Task 24 artifacts:

- `results/task24_dflash_r1_n10.jsonl`
- `results/task24_cc_llm_r2_n10.jsonl`
- `results/task24_cc_llm_r3_n10.jsonl`
- `results/task24_llmlingua_ar_r2_n10.jsonl`
- `results/task24_llmlingua_ar_r3_n10.jsonl`

Task 25 fixture:

- `tests/fixtures/long_context_smoke.jsonl`

Analysis utility:

- `scripts/phase_1_system_build_and_evaluation/analysis/t24_matrix.py`

## Task 24 Metrics Table

| Condition | Rows | Avg tok/s | Median tok/s | Avg input tokens | Avg output tokens | Avg tau_mean | Avg t_compress_ms | Avg R_actual | Max VRAM allocated | Max VRAM reserved | Avg e2e time s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 10 | 19.72 | 16.74 | 23.80 | 11.40 | 2.52 | n/a | n/a | 3.51 GiB | 3.62 GiB | 0.50 |
| CC-LLM-R2 | 10 | 29.28 | 33.41 | 51.80 | 18.00 | 3.86 | 893.89 | 2.20 | 3.51 GiB | 3.63 GiB | 1.59 |
| CC-LLM-R3 | 10 | 29.29 | 32.19 | 43.80 | 18.00 | 3.82 | 820.11 | 3.30 | 3.51 GiB | 3.62 GiB | 1.42 |
| LLMLingua-AR-R2 | 10 | 15.15 | 16.79 | 51.80 | 18.00 | 0.00 | 845.78 | 2.20 | 2.50 GiB | 2.60 GiB | 1.95 |
| LLMLingua-AR-R3 | 10 | 15.36 | 17.47 | 43.80 | 18.00 | 0.00 | 841.26 | 3.30 | 2.50 GiB | 2.59 GiB | 1.92 |

## Generation-Only Comparison Table

These ratios use average generation tok/s only. They do not include compression overhead.

| Comparison | Ratio |
| --- | ---: |
| CC-LLM-R2 avg tok/s / DFlash-R1 avg tok/s | 1.48 |
| CC-LLM-R3 avg tok/s / DFlash-R1 avg tok/s | 1.49 |
| CC-LLM-R2 avg tok/s / LLMLingua-AR-R2 avg tok/s | 1.93 |
| CC-LLM-R3 avg tok/s / LLMLingua-AR-R3 avg tok/s | 1.91 |

## Approximate End-to-End Comparison Table

Approximate end-to-end time is defined here as:

- `generation_time_s` for non-compression rows
- `generation_time_s + t_compress_ms / 1000` for compression rows

This is still a small-matrix approximation because the prompt set is tiny and outputs are short.

| Comparison | Avg e2e time ratio |
| --- | ---: |
| CC-LLM-R2 / DFlash-R1 | 3.17 |
| CC-LLM-R3 / DFlash-R1 | 2.85 |
| CC-LLM-R2 / LLMLingua-AR-R2 | 0.81 |
| CC-LLM-R3 / LLMLingua-AR-R3 | 0.74 |

## Tau Observations

- `DFlash-R1` average `tau_mean` is 2.52.
- `CC-LLM-R2` average `tau_mean` rises to 3.86.
- `CC-LLM-R3` average `tau_mean` is 3.82.
- The AR paths intentionally report `tau_mean = 0.00` because they do not use DFlash speculative acceptance.

Preliminary reading:

- In this small matrix, compression plus DFlash is associated with higher average tau than the no-compression DFlash control.
- That is interesting, but not enough by itself to establish end-to-end value because compression time is non-trivial and the prompt cycle is tiny.

## Compression Overhead Observations

- `CC-LLM-R2` average `t_compress_ms`: 893.89
- `CC-LLM-R3` average `t_compress_ms`: 820.11
- `LLMLingua-AR-R2` average `t_compress_ms`: 845.78
- `LLMLingua-AR-R3` average `t_compress_ms`: 841.26

Preliminary reading:

- Compression cost is currently around 0.82 to 0.89 seconds per prompt in this environment.
- That overhead dominates the tiny DFlash-R1 end-to-end baseline in Task 24, which is why the approximate e2e ratios against `DFlash-R1` are unfavorable even when generation-only tok/s is higher for `CC-LLM`.

## VRAM Observations

- `DFlash-R1`, `CC-LLM-R2`, and `CC-LLM-R3` all peak around 3.51 GiB allocated and 3.62 to 3.63 GiB reserved.
- `LLMLingua-AR-R2` and `LLMLingua-AR-R3` peak around 2.50 GiB allocated and about 2.59 to 2.60 GiB reserved.

Preliminary reading:

- The target-only AR paths keep a materially smaller VRAM footprint because they do not load the draft model.
- The DFlash-backed paths trade higher VRAM for higher generation-only throughput and non-zero tau.

## Long-Context Fixture Summary

From `tests/fixtures/long_context_smoke.jsonl`:

- example count: 6
- average approximate context words: 134.17
- min approximate context words: 127
- max approximate context words: 144
- domains: `compliance`, `education_ops`, `finance`, `health_admin`, `operations`, `public_services`

Why this matters for the next step:

- Task 24 used a tiny repeated prompt cycle with short outputs, which is useful for smoke benchmarking but weak for breakeven analysis.
- The long-context fixture introduces longer contexts with explicit distractors and recoverable answers, which is a fairer setup for testing whether compression overhead can be offset by longer downstream generation savings.
- It also gives us a controlled place to compare preserved-question behavior and answer retention under compression without bringing in a large external dataset.

## Breakeven Interpretation

What current evidence suggests:

- On generation-only tok/s, the DFlash-backed CC-LLM paths outperform both the DFlash no-compression control and the target-only AR baselines in this `n=10` small matrix.
- On approximate end-to-end time, the compression overhead is large enough that `CC-LLM-R2` and `CC-LLM-R3` are slower than `DFlash-R1` in this tiny prompt regime.
- Against the target-only AR paths, the DFlash-backed compressed paths look better even after including approximate compression cost.

Why this is not enough for final claims:

- The prompt cycle is tiny and repeated.
- Output lengths are short.
- Context lengths are still modest compared with the longer-context use case compression is meant to help.
- Compression overhead is measured in the same environment, but the downstream savings opportunity is not yet stressed enough.
- `n=10` is useful for direction, not for stable benchmark conclusions.

What Task 27 should decide:

- whether the current evidence is strong enough to close Phase 1 MVP as a successful exploratory baseline
- whether Phase 2 should proceed to a controlled longer-context experiment using the Task 25 fixture or a closely related artifact
- whether the next step should prioritize end-to-end breakeven on longer contexts over further short-prompt smoke expansion

## Validation Commands and Results

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py -q`: PASS
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t24_matrix.py`: PASS

## Limitations

- Preliminary only.
- Uses Task 24 `n=10` artifacts, not a larger benchmark matrix.
- Uses approximate end-to-end timing from per-row generation time plus compression time.
- Does not validate answer quality on the long-context fixture yet.
- Does not prove compression breakeven.
- Does not establish production readiness.

## Next Step

Task 27: Phase 1 MVP closeout plus Go/No-Go decision for Phase 2.
