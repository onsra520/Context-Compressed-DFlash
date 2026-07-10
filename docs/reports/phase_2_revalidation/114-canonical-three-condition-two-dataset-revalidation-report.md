# Task114 Canonical Three-Condition Two-Dataset Revalidation Report

Date: 2026-07-10

Status: `PASS_WITH_LIMITATIONS`

## Scope

Task114 reopened Phase 2 for a source-based canonical revalidation over the frozen GSM8K and QMSum evaluation datasets. The run used `src/` execution paths through `scripts/run_mvp.py`, not notebooks or frontend code.

Canonical runner:

- `scripts/phase_2_revalidation/task114_canonical_matrix.py`

Output root:

- `results/phase_2_revalidation/task114_canonical_matrix/`

The runner performed six `n=1` smoke gates first, then ran the full frozen `n=100` sets for both datasets and all three conditions after the smoke audit passed.

## Inputs

Datasets:

- GSM8K: `data/eval/gsm8k_100.jsonl`
- QMSum: `data/eval/qmsum_meeting_qa_100.jsonl`

Prompt policies:

- GSM8K: `gsm8k_concise_final_answer_v1`
- QMSum: `qmsum_t105b_compatible_evidence_focused_v1`

QMSum deliberately uses the final T105B-compatible policy rather than the T108B targeted repair prompt.

Conditions:

- `Baseline-AR`
- `DFlash-R1`
- `CC-DFlash-R2 Light GPU`

## Commands

Smoke gate:

```bash
.venv/bin/python scripts/phase_2_revalidation/task114_canonical_matrix.py --smoke-only
```

Full matrix:

```bash
.venv/bin/python scripts/phase_2_revalidation/task114_canonical_matrix.py --full-only
```

Artifact rebuild after full benchmark completion:

```bash
.venv/bin/python scripts/phase_2_revalidation/task114_canonical_matrix.py --build-only
```

## Smoke Gate

Smoke gate status: `PASS`

The six `n=1` smoke runs verified same precompression prompt hash and token count across conditions within each dataset row, generated full text, excluded warmup rows, uncompressed `t_compress_ms=0`, compressed formulas, split allocated/reserved VRAM, and `t_e2e_ms = t_compress_ms + t_prefill_ms + t_generation_ms`.

Audit file:

- `results/phase_2_revalidation/task114_canonical_matrix/manifests/prompt_fairness_audit.json`

## Run Files

| Dataset | Condition | Rows | Run file |
| --- | --- | ---: | --- |
| GSM8K | Baseline-AR | 100 | `results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/baseline_ar.jsonl` |
| GSM8K | DFlash-R1 | 100 | `results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/dflash_r1.jsonl` |
| GSM8K | CC-DFlash-R2 Light GPU | 100 | `results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/cc_dflash_r2_light_gpu.jsonl` |
| QMSum | Baseline-AR | 100 | `results/phase_2_revalidation/task114_canonical_matrix/runs/qmsum/baseline_ar.jsonl` |
| QMSum | DFlash-R1 | 100 | `results/phase_2_revalidation/task114_canonical_matrix/runs/qmsum/dflash_r1.jsonl` |
| QMSum | CC-DFlash-R2 Light GPU | 100 | `results/phase_2_revalidation/task114_canonical_matrix/runs/qmsum/cc_dflash_r2_light_gpu.jsonl` |

Summary CSV:

- `results/phase_2_revalidation/task114_canonical_matrix/tables/three_condition_two_dataset_summary.csv`

Per-row metric audit:

- `results/phase_2_revalidation/task114_canonical_matrix/tables/per_row_metric_audit.csv`

## Metric Contract

Timing:

- `t_compress_ms=0` for `Baseline-AR` and `DFlash-R1`
- compression rows record retained ratio, reduction percentage, and compression factor
- `t_e2e_ms` excludes model startup, model load, and warmup
- `t_e2e_ms` includes compression, prefill, and generation

VRAM:

- `peak_allocated_gib` and `peak_reserved_gib` are reported separately

Output auditing includes `cap_hit`, `finish_reason`, `output_tokens`, full generated text, component manifest, timing audit, VRAM audit, and prompt fairness audit.

## Summary Results

| Dataset | Condition | Avg e2e ms | Avg gen tok/s | Avg e2e tok/s | Peak alloc GiB | Peak reserved GiB | Quality proxy |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GSM8K | Baseline-AR | 7669.275247 | 19.720332 | 19.429144 | 2.491965 | 2.890625 | strict numeric 85/100, wrong numeric 15/100, invalid 0/100 |
| GSM8K | DFlash-R1 | 3188.892728 | 48.745954 | 46.851938 | 3.498373 | 3.824219 | strict numeric 85/100, wrong numeric 15/100, invalid 0/100 |
| GSM8K | CC-DFlash-R2 Light GPU | 3239.179187 | 58.032419 | 55.504122 | 4.162706 | 4.431641 | strict numeric 81/100, wrong numeric 18/100, invalid 1/100 |
| QMSum | Baseline-AR | 4591.599885 | 26.934336 | 22.601960 | 2.492013 | 5.033203 | recall 0.222768, precision 0.139920, invalid 0/100 |
| QMSum | DFlash-R1 | 5971.728528 | 20.105701 | 17.542280 | 3.498544 | 6.029297 | recall 0.226467, precision 0.142479, invalid 0/100 |
| QMSum | CC-DFlash-R2 Light GPU | 5379.297858 | 22.417830 | 20.271140 | 4.161240 | 5.724609 | recall 0.213530, precision 0.129606, invalid 0/100 |

Compression summary:

- GSM8K CC-DFlash-R2 Light GPU: average original input tokens `103.18`, average compressed input tokens `8.0`, retained ratio `0.080061`, reduction `91.993872%`, average compression time `19.10488 ms`.
- QMSum CC-DFlash-R2 Light GPU: average original input tokens `2070.85`, average compressed input tokens `887.17`, retained ratio `0.428869`, reduction `57.113069%`, average compression time `118.559753 ms`.

Cap hits:

- GSM8K Baseline-AR: `9/100`
- GSM8K DFlash-R1: `9/100`
- GSM8K CC-DFlash-R2 Light GPU: `17/100`
- QMSum Baseline-AR: `0/100`
- QMSum DFlash-R1: `0/100`
- QMSum CC-DFlash-R2 Light GPU: `0/100`

## Claim Boundary

Task114 supports a canonical source-runner metric snapshot only.

Allowed:

- source-based frozen two-dataset, three-condition revalidation completed
- smoke-gated metric contract passed
- GSM8K numeric proxy reported
- QMSum bounded lexical proxy reported
- timing and VRAM audits reported

Not claimed:

- no production or default pipeline switch is authorized
- no QMSum semantic correctness claim is made
- no Qwen judge claim is made for Task114
- no deployment readiness claim is made
- Task111 remains preserved as the historical `COMPLETE_WITH_CAVEATS` Phase 2 closure package
