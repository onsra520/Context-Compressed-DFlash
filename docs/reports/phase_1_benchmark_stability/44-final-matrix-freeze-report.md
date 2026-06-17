# Task 44 — Final Matrix Freeze


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-04

## Result

PASS, specification freeze only.

Task 44 freezes the benchmark matrix, dataset policy, output-length policy, answer-quality policy, efficiency metrics, artifact schema, and readiness gates for the next benchmark stage. No benchmark was run, no model was loaded, and no result artifact was modified.

This report does not make final speedup, correctness, deployment, 8 GB fit, or end-to-end compression-benefit claims.

## Scope

- Freeze final benchmark conditions.
- Freeze sample-mode versus full source-mode dataset policy.
- Freeze long-context output-length and generated-text retention policy.
- Freeze extraction-aware answer-quality policy.
- Freeze speed and efficiency metric set.
- Freeze benchmark artifact schema.
- Define readiness gates before Task 45.
- Update roadmap and stable overview policy wording.

## Frozen Conditions

| Condition | Status | Purpose |
| --- | --- | --- |
| `Baseline-AR` | Frozen | Target-only autoregressive reference, no compression, no DFlash |
| `DFlash-R1` | Frozen | No-compression DFlash baseline |
| `LLMLingua-AR-R2` | Frozen | Low-VRAM compression attribution baseline, no DFlash |
| `CC-LLM-R2` | Frozen | Primary compressed-context DFlash candidate |
| `CC-LLM-R3` | Watchlist / deferred | Too aggressive for the frozen first final matrix unless a separate task explicitly re-admits it |

Task 45 must not silently add conditions. Any added condition requires a new report or explicit task update before execution.

## Dataset Policy

- Sample-mode data is only for smoke, pipeline validation, and calibration.
- Final benchmark must use full source-mode GSM8K + Wikipedia augmented data.
- Final benchmark must not rely on the 5-row sample artifact.
- Full source-mode dataset must be generated with the Task 41 builder or a documented successor.
- Full source-mode dataset must pass the Task 42 audit path or a stricter documented successor before Task 45.
- Dataset artifacts must preserve question, expected answer, evidence metadata, augmentation metadata, and token or word length metadata.

## Output-Length Policy

- Long-context GSM8K-style runs must use `max_new_tokens >= 128`.
- Generated text must be stored for every benchmark row.
- Task 43.5 is the rationale: `max_new_tokens=32` caused truncation and 15/15 `NO_CONTAINMENT`; DFlash-R1 calibration at `max_new_tokens=128` produced 5/5 containment and 5/5 extracted-answer matches.
- Any future output length below 128 must be explicitly recalibrated and justified in a report before use.

## Answer-Quality Policy

Primary quality metric:

- Extracted numeric answer exact match against the expected numeric answer.

Diagnostic quality metrics:

- Exact containment.
- Normalized containment.
- `NO_CONTAINMENT`.
- `NOT_EVALUABLE`.
- Invalid output rate.
- Manual-review category for ambiguous rows when needed.

Extraction policy:

- Support `Final answer: 42`.
- Support `Answer: 42`.
- Support GSM8K-style `#### 42`.
- Support comma-formatted numbers such as `1,234`.
- Support negative and decimal numbers.
- Last standalone number fallback is allowed only as a diagnostic fallback.

Containment is diagnostic only and must not be treated as the primary correctness metric.

## Speed and Efficiency Metrics

Task 45 artifacts and summaries must report:

- `tok_per_sec`
- `generation_time_s`
- `t_compress_ms`
- `t_prefill_ms`
- `R_actual`
- `tau_mean`
- `vram_allocated_gib`
- `vram_reserved_gib`
- `input_tokens`
- `output_tokens`
- approximate end-to-end time where applicable: `generation_time_s + t_compress_ms / 1000`

## Frozen Artifact Schema

All benchmark rows must include these common fields:

| Field | Requirement |
| --- | --- |
| `timestamp` | required |
| `condition` | required |
| `prompt_id` | required |
| `prompt_hash` | required |
| `input_tokens` | required |
| `output_tokens` | required |
| `generation_time_s` | required |
| `tok_per_sec` | required |
| `acceptance_lengths` | required, empty list for AR conditions |
| `tau_mean` | required, `0.0` for AR conditions |
| `t_prefill_ms` | required |
| `t_prefill_mode` | required |
| `prefill_vram_allocated_gib` | required, nullable |
| `prefill_vram_reserved_gib` | required, nullable |
| `max_new_tokens` | required, must be at least 128 for long-context final benchmark rows |
| `block_size` | required, nullable for pure AR if not applicable |
| `device` | required |
| `target_path` | required |
| `draft_path` | required, nullable when draft is not used |
| `tokenizer_path` | required |
| `backend_warning` | required |
| `vram_allocated_gib` | required |
| `vram_reserved_gib` | required |
| `generated_text` | required |
| `generated_token_count` | required |
| `prompt_source` | required |
| `fixture_id` or dataset row id | required |
| `domain` | required |
| `expected_answer` | required |
| `evidence` | required |
| `approximate_context_words` | required when available, nullable otherwise |
| `approximate_context_tokens` | required when available, nullable otherwise |
| `t_compress_ms` | required, nullable when no compression |
| `R_actual` | required, nullable when no compression |
| `N_original` | required, nullable when no compression |
| `N_compressed` | required, nullable when no compression |
| `keep_rate` | required, nullable when no compression |
| `compressor_model` | required, nullable when no compression |
| `question_preserved` | required for compression conditions, nullable otherwise |
| `generation_mode` | required |
| `draft_used` | required |
| `extracted_answer` | required in quality summaries |
| `expected_extracted_answer` | required in quality summaries |
| `extracted_answer_match` | required in quality summaries |
| `invalid_output` | required in quality summaries |

Condition-specific fields must be nullable rather than missing when not applicable.

## Readiness Gates Before Task 45

Task 45 is conditional on all gates below:

1. Full source-mode GSM8K + Wikipedia dataset generated.
2. Full source-mode dataset audited.
3. Answer extraction tests passing.
4. Artifact schema audit passing against the frozen schema.
5. Output length fixed at `max_new_tokens >= 128`, unless an explicit recalibration report changes it.
6. Generated text enabled for all benchmark rows.
7. No final benchmark conditions added beyond the frozen list without a new task/report.
8. Existing conservative claim policy preserved.

If any gate fails, Task 45 must not be treated as the final benchmark run.

## Carry-Forward Interpretation

- `Baseline-AR`, `DFlash-R1`, `LLMLingua-AR-R2`, and `CC-LLM-R2` are the frozen first final matrix candidates.
- `CC-LLM-R3` stays on watchlist/deferred status.
- Task 43.5 resolves the immediate output-quality warning enough to freeze policy, but compressed-condition quality still needs frozen-setting evidence.
- Full source-mode data remains the gating item before any final benchmark claim.

## Validation

- Markdown fence balance for this report: required.
- HTML sanity for `docs/Roadmap.html` and `docs/CC-DFlash-Overview.html`: required because both docs are updated.
- No benchmark, model loading, compressor loading, CUDA use, dataset generation, dataset download, or result artifact modification is required for this task.

## Next Step

Task 45: final benchmark run, conditional on the readiness gates above. If the full source-mode dataset or schema audit is not ready, Task 45 must become a blocked/preparation task rather than a final benchmark claim.
