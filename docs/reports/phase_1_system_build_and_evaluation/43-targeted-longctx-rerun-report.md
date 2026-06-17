# Task 43 — Targeted Long-Context Rerun


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-04

## Result

PASS, sample-mode pipeline validation with quality warning.

Task 43 reran three targeted conditions on the audited Task 41 sample-mode GSM8K + Wikipedia dataset. The run validates the dataset-to-runner-to-artifact path with generated text stored, but it is not a final benchmark. All generated rows were scored `NO_CONTAINMENT` by the deterministic answer-quality proxy, so the sample-mode path needs inspection before any correctness claim.

## Scope

- Regenerated the Task 41 sample-mode dataset artifact with deterministic settings.
- Re-ran the dataset audit and wrote a Task 43-specific summary artifact.
- Ran three targeted conditions on the sample-mode dataset:
  - `DFlash-R1`
  - `LLMLingua-AR-R2`
  - `CC-LLM-R2`
- Stored generated text for later inspection.
- Created new Task 43 result artifacts only.
- Ran smoke artifact contract audit on all three Task 43 JSONL outputs.
- Ran deterministic answer-containment scoring on all three Task 43 JSONL outputs.

This task loaded the local target model. `DFlash-R1` and `CC-LLM-R2` loaded the draft model. LLMLingua conditions loaded the compressor. No final benchmark was run.

## Dataset

Dataset path: `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl`

Dataset command:

```bash
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --max-samples 5 --min-context-words 220 --max-context-words 360 --seed 41 --split test --source-mode sample
```

Dataset audit result:

- rows: 5
- source mode: `sample`
- builder ready: true
- sample artifact ready: true
- full benchmark dataset ready: false
- issues: 0

## Commands

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 5 --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task43_dflash_r1_sample_n5.jsonl
```

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R2 --n 5 --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task43_llmlingua_ar_r2_sample_n5.jsonl
```

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R2 --n 5 --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task43_cc_llm_r2_sample_n5.jsonl
```

## Artifacts

| Artifact | Condition | Rows |
| --- | --- | ---: |
| `results/phase_1_system_build_and_evaluation/early_experiments/task43_dflash_r1_sample_n5.jsonl` | DFlash-R1 | 5 |
| `results/phase_1_system_build_and_evaluation/early_experiments/task43_llmlingua_ar_r2_sample_n5.jsonl` | LLMLingua-AR-R2 | 5 |
| `results/phase_1_system_build_and_evaluation/early_experiments/task43_cc_llm_r2_sample_n5.jsonl` | CC-LLM-R2 | 5 |
| `results/phase_1_system_build_and_evaluation/early_experiments/task43_dataset_audit_summary.json` | dataset audit summary | 5 |
| `results/phase_1_system_build_and_evaluation/early_experiments/task43_answer_quality_summary.json` | answer-quality proxy | 3 artifacts |

Smoke artifact audit passed for all three JSONL artifacts.

## Metrics

| Condition | Rows | Avg tok/s | Avg input tokens | Avg output tokens | Avg tau | Avg `t_compress_ms` | Avg `R_actual` | Avg `t_prefill_ms` | Max VRAM allocated GiB | Max VRAM reserved GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 5 | 4.06 | 405.4 | 32.0 | 4.56 | n/a | n/a | 4093.70 | 3.5108418464660645 | 3.82421875 |
| LLMLingua-AR-R2 | 5 | 6.76 | 195.6 | 32.0 | 0.00 | 1430.60 | 2.40 | 448.55 | 2.502476692199707 | 2.677734375 |
| CC-LLM-R2 | 5 | 5.58 | 195.6 | 32.0 | 3.95 | 1181.30 | 2.40 | 1550.53 | 3.510838508605957 | 3.736328125 |

Backend warning status: `flash_attn` is not installed, so the runner used the existing `torch.sdpa` fallback.

## Answer Quality Proxy

The deterministic containment scorer was run on all Task 43 artifacts:

| Condition | Generated text rows | Exact containment | Normalized containment | NO_CONTAINMENT | Not evaluable |
| --- | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 5 | 0 | 0 | 5 | 0 |
| LLMLingua-AR-R2 | 5 | 0 | 0 | 5 | 0 |
| CC-LLM-R2 | 5 | 0 | 0 | 5 | 0 |

This should be read as a sample-limited quality warning, not final correctness. The generated text was present, but the final answers did not appear within the stored generated text. The outputs often began reasoning and were capped at 32 generated tokens.

## Interpretation

Task 43 validates that the audited sample-mode dataset can flow through DFlash, LLMLingua-AR, and CC-LLM artifact paths with generated text stored and schema checks passing.

It does not establish final speed, final correctness, deploy readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit. The current sample-mode run suggests Task 44 should freeze a matrix that explicitly handles output length, answer extraction, quality gating, and full source-mode dataset readiness.

## Limitations

- `n=5` only.
- Dataset source mode is `sample`, not full GSM8K/Wikipedia.
- `max_new_tokens` remains capped at 32 in the runner.
- Answer-quality proxy is containment-based, not semantic correctness.
- No final benchmark claim should be made from this run.

## Validation

- Dataset regeneration: PASS
- Dataset audit: PASS
- Three targeted rerun commands: PASS
- Smoke artifact audit for all three Task 43 JSONL files: PASS
- Answer-quality scorer: PASS, all rows `NO_CONTAINMENT`

## Next Step

Task 44: freeze the final benchmark matrix and schema, with explicit decisions about dataset source mode, output length, answer extraction, and quality gating.
