# T114H Canonical Prompt Policy Hotfix Report

## Root Cause

Task114 recorded prompt policy names in the matrix metadata, but the runner command did not pass the resolved canonical policy text into `scripts/run_mvp.py`. As a result, GSM8K full runs used the default dataset prompt instead of the T106B concise final-answer suffix, so Task114 was not comparable with T106B and showed inflated cap-hit counts.

The affected path was:

- `scripts/phase_2_revalidation/task114_canonical_matrix.py` built Task114 commands.
- `scripts/run_mvp.py` accepted runtime policy suffixes, but the GSM8K override was guarded to `CC-DFlash-R2` only.
- Summary artifacts were built from runs whose prompt-policy metadata did not prove that the actual inference prompt received the canonical policy text.

## Code Path Fixed

- `task114_canonical_matrix.py` now resolves canonical dataset policies to exact text and SHA-256 hashes.
- Task114 commands now pass:
  - GSM8K: `--gsm8k-policy-suffix` with the exact T106B suffix.
  - QMSum: `--qmsum-policy-suffix` with `QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION`.
- `run_mvp.py` now allows the GSM8K policy suffix for every GSM8K condition, not only `CC-DFlash-R2`.
- Normalized rows now record `resolved_prompt_policy`, `resolved_prompt_policy_text`, `resolved_prompt_policy_hash`, and `precompression_rendered_prompt_hash`.
- Summary rows now include their source `run_path`, resolved policy name/hash, and row-level policy-hash uniqueness count.

## Rerun Scope

GSM8K was rerun for all three frozen 100-row conditions:

- `results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/baseline_ar.jsonl`
- `results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/dflash_r1.jsonl`
- `results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/cc_dflash_r2_light_gpu.jsonl`

QMSum was not rerun. The existing Task114 QMSum prompts were audited against historical T105B rows for the shared 30 examples and had zero prompt-hash mismatches across all three conditions. The existing QMSum generations were preserved and metadata-normalized with the canonical T105B-compatible policy text/hash.

## Before and After

Previous committed Task114 GSM8K summary:

| Condition | Strict correct | Wrong numeric | Invalid | Cap hits |
| --- | ---: | ---: | ---: | ---: |
| Baseline-AR | 85 | 15 | 0 | 9 |
| DFlash-R1 | 85 | 15 | 0 | 9 |
| CC-DFlash-R2 Light GPU | 81 | 18 | 1 | 17 |

Repaired Task114H GSM8K summary:

| Condition | Strict correct | Wrong numeric | Invalid | Cap hits |
| --- | ---: | ---: | ---: | ---: |
| Baseline-AR | 90 | 9 | 0 | 1 |
| DFlash-R1 | 89 | 10 | 0 | 1 |
| CC-DFlash-R2 Light GPU | 88 | 10 | 0 | 2 |

The repaired cap-hit profile now approaches the historical T106B expectation. CC-DFlash-R2 retains the intended speed shape on GSM8K: `avg_e2e_tok_s=50.856130` versus Baseline-AR `30.013912`, with `cap_hit_count=2`.

## Authority Boundary

Task114H supersedes the prior Task114 GSM8K rows and derived summaries. It is the authoritative Task114 result for GSM8K canonical-policy comparisons.

Task114 QMSum remains authoritative as a preserved run after the T105B prompt audit, with updated metadata proving the resolved canonical policy. QMSum quality remains proxy-only; no semantic correctness claim or production default switch is authorized by Task114.

## Verification

- `pytest tests/test_task114_canonical_matrix.py tests/test_task106b_gsm8k_cap_limited_fix.py tests/test_task107b_gsm8k_policy_refinement_fix.py tests/test_task109_gsm8k_balanced_numeric_residual_repair.py -q`
- `python -m py_compile scripts/run_mvp.py scripts/phase_2_revalidation/task114_canonical_matrix.py`
- `python scripts/phase_2_revalidation/task114_canonical_matrix.py --smoke-only`
- `python scripts/phase_2_revalidation/task114_canonical_matrix.py --full-only --dataset gsm8k`
- `python scripts/phase_2_revalidation/task114_canonical_matrix.py --build-only`
- Artifact audit: all six full run files have 100 rows, exactly one resolved policy hash per dataset, matching precompression prompt hashes across the three conditions for every prompt index, and six distinct source run paths in the summary.
