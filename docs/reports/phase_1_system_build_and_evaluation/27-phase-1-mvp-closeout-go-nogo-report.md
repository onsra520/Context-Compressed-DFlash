# 27 Phase 1 MVP Closeout and Go/No-Go Report

## Title and Date

- Task: Phase 1 MVP closeout + Go/No-Go decision for Phase 2
- Date: 2026-06-04

## Executive Decision

Phase 1 status: PASS for MVP pipeline/evidence readiness.

Phase 2 recommendation: conditional GO.

Phase 2 should proceed only as a controlled longer-context experiment. It should use the existing Transformers backend, preserve current target/draft assumptions, measure end-to-end time including compression, validate answer preservation, and avoid vLLM, SGLang, Docker, scale-up work, or immediate compressor fine-tuning.

## What Phase 1 Proved

- Baseline DFlash smoke path works with local target/draft/tokenizer paths.
- Raw-free split modules and import contracts were audited.
- DFlash-R1 repeatable JSONL artifacts exist and pass contract checks.
- LLMLingua wrapper/unit smoke path works.
- Real LLMLingua CPU compression smoke works.
- LLMLingua model choice is locked to `microsoft/llmlingua-2-xlm-roberta-large-meetingbank`.
- CC-LLM-R2/R3 DFlash-backed compression paths run and emit JSONL artifacts.
- LLMLingua-AR-R2/R3 target-only baselines run and emit JSONL artifacts.
- Smoke artifact contract audit exists.
- A preliminary `n=10` small matrix exists across DFlash, CC-LLM, and LLMLingua-AR.
- A preliminary speedup/tau/compression/breakeven analysis exists.
- A synthetic long-context fixture exists for the next controlled experiment.

## What Phase 1 Did Not Prove

- No final benchmark speedup has been proven.
- No production readiness claim is supported.
- Compression is not proven worthwhile end to end.
- Long-context answer quality has not been validated yet.
- The `n=10` small matrix and short outputs are too small for final claims.
- The current setup still uses the existing Transformers backend and torch SDPA fallback, not an optimized serving stack.

## Evidence Table

| Task | Report | Artifact or output | Status |
| --- | --- | --- | --- |
| 16 | `docs/reports/16-week-1-closeout-report.md` | `results/_archives/early_smokes/dflash_r1_n20.jsonl` | PASS |
| 17 | `docs/reports/17-week-1-2-spec-cleanup-alignment-report.md` | spec alignment notes | PASS |
| 18 | `docs/reports/18-llmlingua-compressor-smoke-report.md` | `tests/test_compression.py` wrapper/unit smoke | PASS |
| 19 | `docs/reports/19-real-llmlingua-cpu-smoke-report.md` | `results/_archives/early_smokes/llmlingua_cpu_smoke.json` | PASS |
| 20 | `docs/reports/20-llmlingua-model-lock-report.md` | locked LLMLingua config | PASS |
| 21 | `docs/reports/21-cc-llm-r2-r3-smoke-comparison-report.md` | `results/_archives/early_smokes/cc_llm_r2_smoke.jsonl`, `results/_archives/early_smokes/cc_llm_r3_smoke.jsonl` | PASS |
| 22 | `docs/reports/22-llmlingua-ar-smoke-baseline-report.md` | `results/_archives/early_smokes/llmlingua_ar_r2_smoke.jsonl`, `results/_archives/early_smokes/llmlingua_ar_r3_smoke.jsonl` | PASS |
| 23 | `docs/reports/23-smoke-artifact-contract-audit-report.md` | `scripts/smoke_artifacts.py` | PASS |
| 24 | `docs/reports/24-small-condition-matrix-report.md` | `results/task24_*_n10.jsonl` | PASS, preliminary |
| 25 | `docs/reports/25-long-context-fixture-report.md` | `tests/fixtures/long_context_smoke.jsonl` | PASS |
| 26 | `docs/reports/26-preliminary-speedup-breakeven-analysis-report.md` | `scripts/phase_1_system_build_and_evaluation/analysis/t24_matrix.py` | PASS, preliminary |

## Key Metric Summary

Task 24/26 small-matrix values:

| Condition | Avg tok/s | Avg tau_mean | Avg t_compress_ms | Avg e2e time s | Max VRAM allocated | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DFlash-R1 | 19.72 | 2.52 | n/a | 0.50 | 3.51 GiB | no compression control |
| CC-LLM-R2 | 29.28 | 3.86 | 893.89 | 1.59 | 3.51 GiB | DFlash-backed compression |
| CC-LLM-R3 | 29.29 | 3.82 | 820.11 | 1.42 | 3.51 GiB | DFlash-backed compression |
| LLMLingua-AR-R2 | 15.15 | 0.00 | 845.78 | 1.95 | 2.50 GiB | target-only AR baseline |
| LLMLingua-AR-R3 | 15.36 | 0.00 | 841.26 | 1.92 | 2.50 GiB | target-only AR baseline |

Preliminary observations:

- CC-LLM-R2/R3 show higher generation-only tok/s and higher tau than DFlash-R1 in the `n=10` small matrix.
- Compression overhead is about 0.82 to 0.89 seconds per prompt, which makes CC-LLM-R2/R3 slower than DFlash-R1 in approximate end-to-end time for the tiny prompt regime.
- DFlash/CC paths peak around 3.51 GiB allocated, while target-only AR paths peak around 2.50 GiB allocated.
- These observations are useful for deciding what to test next, not for final speedup claims.

## Go/No-Go Recommendation

Recommendation: conditional GO to Phase 2.

Conditions for GO:

- Phase 2 is scoped to controlled longer-context experiments.
- Phase 2 uses `tests/fixtures/long_context_smoke.jsonl` or a similarly controlled fixture.
- Phase 2 measures answer preservation and expected-answer correctness.
- Phase 2 measures end-to-end time including compression.
- Phase 2 keeps the existing Transformers backend.
- Phase 2 does not introduce vLLM, SGLang, Docker, scale-up work, or immediate compressor fine-tuning.
- Phase 2 keeps all claims preliminary until longer-context evidence is collected and audited.

No-Go triggers:

- Any plan that tries to claim final speedup from Task 24 alone.
- Any plan that skips answer preservation checks.
- Any plan that changes serving stack or model assumptions before the controlled long-context experiment.
- Any plan that starts compressor fine-tuning before validating whether the current locked LLMLingua path has measurable value.

## Phase 2 First Tasks

- Task 28: add long-context runner mode using the Task 25 fixture.
- Task 29: run an `n=6` long-context pilot across DFlash, CC-LLM, and AR paths.
- Task 30: add answer preservation and expected-answer correctness checks.
- Task 31: Phase 2 breakeven analysis with end-to-end timing.
- Task 32: decide whether Gemma4-E2B compressor fine-tuning is justified based on controlled evidence.

## Risks and Mitigations

Compression CPU overhead:

- Risk: compression cost may dominate end-to-end latency.
- Mitigation: always report generation-only and end-to-end timing separately.

Short-output noise:

- Risk: tiny outputs produce unstable tok/s.
- Mitigation: use longer contexts and controlled output lengths before making claims.

Prompt quality:

- Risk: synthetic prompts may not represent real workloads.
- Mitigation: keep fixture rows explicit, auditable, and gradually expand only after contract checks pass.

Answer loss after compression:

- Risk: LLMLingua may remove evidence needed for correctness.
- Mitigation: measure expected-answer preservation and generated-answer correctness in Phase 2.

GPU memory/runtime:

- Risk: longer contexts may increase runtime or memory pressure.
- Mitigation: start with the small Task 25 fixture and keep `n` low for the first Phase 2 pilot.

## Validation Commands and Results

Commands run for this closeout:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t24_matrix.py`

Results:

- `compileall`: PASS
- pytest suite listed above: PASS
- smoke artifact audit: PASS
- Task 24 matrix analysis: PASS

## Final Conclusion

Phase 1 PASS as an MVP pipeline/evidence baseline.

Phase 2 conditional GO for controlled long-context experiments only.

No final speedup claim is supported yet. Compression is not proven worthwhile end to end yet. The next decision point should be based on longer-context evidence with answer preservation and end-to-end timing included.
