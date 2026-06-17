# Task 57 — Compressed GSM8K Preview Triage Report

Date: 2026-06-11

Status: PASS, read-only triage

## Scope

Task 57 analyzes the Task 56 GSM8K `max_new_tokens=192` artifacts without running new model, compressor, CUDA, or benchmark work.

Inputs inspected:

- `results/task56_gsm8k_short_baseline_ar_n10_mnt192.jsonl`
- `results/task56_gsm8k_short_dflash_r1_n10_mnt192.jsonl`
- `results/task56_gsm8k_short_llmlingua_ar_r2_n10_mnt192.jsonl`
- `results/task56_gsm8k_short_cc_dflash_r2_n10_mnt192.jsonl`
- `data/eval/gsm8k_100.jsonl`

Task 56 was already committed before this task:

- `62e084f test: calibrate gsm8k final-answer prompt`

## Analyzer

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t57_compressed_preview_triage.py
```

Outputs:

- `results/task57_compressed_preview_triage_summary.json`
- `results/task57_compressed_preview_failure_samples.jsonl`

## Metadata Presence Summary

| Condition | Rows | Complete metadata rows | Question preserved | Missing required fields |
| --- | ---: | ---: | --- | --- |
| LLMLingua-AR-R2 | 10 | 10 | true | none |
| CC-DFlash-R2 | 10 | 10 | true | none |

Required metadata checked:

- `keep_rate`
- `t_compress_ms`
- `original_input_tokens`
- `compressed_input_tokens`
- `compression_ratio`
- `actual_compression_ratio`
- `original_context_preview`
- `compressed_context_preview`
- `original_prompt_preview`
- `compressed_prompt_preview`
- `question_preserved`

## Final-Answer Instruction Survival

| Condition | Compressed prompt previews with instruction | Original prompt previews with instruction | Interpretation |
| --- | ---: | ---: | --- |
| LLMLingua-AR-R2 | 0 / 10 | 0 / 10 | Strict final-answer policy is not visible in stored prefix previews. |
| CC-DFlash-R2 | 0 / 10 | 0 / 10 | Strict final-answer policy is not visible in stored prefix previews. |

Important caveat: the stored previews are prefix-capped, so absence from a preview alone does not prove absence from the full prompt. However, the compressed artifacts do show `question_preserved=true` while still producing no strict final-answer marker matches. This strongly suggests the next fix should protect or explicitly append the final-answer instruction outside the compressible context and store enough prompt-tail metadata to verify it.

## Failure Labels

| Label | Count |
| --- | ---: |
| PASS_MATCH | 6 |
| FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED | 10 |
| MODEL_FAIL_SHARED | 4 |

By condition:

| Condition | PASS_MATCH | FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED | MODEL_FAIL_SHARED |
| --- | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 3 | 5 | 2 |
| CC-DFlash-R2 | 3 | 5 | 2 |

## Preview Evidence For Compression Loss

| Evidence category | Count |
| --- | ---: |
| Visible numeric tokens preserved in preview | 14 |
| Critical number status unclear due prefix preview | 6 |

Direct compression-loss support from complete previews: false.

Some rows have key numbers missing from the compressed prefix preview, but those previews are truncated with `...`, so the absence is not strong enough to claim LLMLingua removed the critical information. Larger capped previews or prompt-tail previews are needed before making compression-loss claims.

## Representative Failure Examples

| Condition | Row | Expected | Extracted | Label | Hit cap | Uncompressed numeric match | Missing key numbers in compressed preview |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| LLMLingua-AR-R2 | `gsm8k_short_test_0014` | 1430 | 4 | FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED | true | Baseline-AR=true, DFlash-R1=true | none |
| LLMLingua-AR-R2 | `gsm8k_short_test_0029` | 14 | 2 | FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED | true | Baseline-AR=false, DFlash-R1=true | none |
| CC-DFlash-R2 | `gsm8k_short_test_0014` | 1430 | 4 | FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED | true | Baseline-AR=true, DFlash-R1=true | none |
| CC-DFlash-R2 | `gsm8k_short_test_0029` | 14 | 2 | FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED | true | Baseline-AR=false, DFlash-R1=true | none |
| LLMLingua-AR-R2 | `gsm8k_short_test_0004` | 12 | 5 | MODEL_FAIL_SHARED | true | Baseline-AR=false, DFlash-R1=false | none |

These examples show two distinct patterns:

- When uncompressed DFlash-R1 or Baseline-AR succeeds but compressed rows fail, the compressed preview usually preserves visible numeric tokens but does not show the final-answer instruction.
- When uncompressed rows also fail, the compressed failure is better treated as shared model/output failure rather than compression loss.

## Interpretation

- Metadata is present and usable for Task 57 triage.
- The protected question survives in all compressed rows.
- The strict `Final answer: <number>` instruction is not visible in any compressed prompt preview.
- No direct compression-loss claim is supported by complete preview evidence.
- Token-cap hits remain common, but testing `max_new_tokens=256` before protecting the final-answer instruction would confound output-length and prompt-policy effects.
- A gentler `keep_rate` such as `0.67` or `0.8` may be worth testing later, but the immediate blocker is prompt segmentation/protection evidence.

## Recommendations

1. Protect the GSM8K final-answer instruction outside the compressible context, alongside the original question, before larger GSM8K runs.
2. Add capped prompt-tail or full short-prompt preview metadata so future triage can verify that the final-answer instruction actually reaches the model.
3. After that fix, run a tiny calibration before changing `keep_rate` or increasing `n`.
4. Test `max_new_tokens=256` only if compressed rows still hit the cap after the final-answer instruction is visibly protected.
5. Test gentler keep rates such as `0.67` or `0.8` only if post-fix previews show critical numeric tokens or relations are missing.

## Validation

Validation commands and results are recorded in the final task response.

## Understand-Anything

`.understand-anything/meta.json` was read before task work. `/understand` refresh was skipped because `/understand` is not available in this environment.
