# Task114R GSM8K Reproduction Audit

Status: `ROOT_CAUSE_IDENTIFIED`

Secondary decision: `T114_CONFIG_REGRESSION`

## Finding

T114 did not reproduce the historical T106B GSM8K candidate. The exact root cause is a prompt/config regression: T114 labeled GSM8K as `gsm8k_concise_final_answer_v1`, but its canonical runner did not pass T106B's runtime `--gsm8k-policy-suffix` override to `scripts/run_mvp.py`.

T106B used this protected suffix:

```text
Keep the solution concise. End with exactly one line in the format: Final answer: <number>. Do not continue after the final answer.
```

T114 used only the default eval-dataset GSM8K suffix:

```text
End with exactly one line:
Final answer: <number>
```

This changed every rendered GSM8K prompt before compression.

## Evidence

Static audit:

- Dataset identity: same 100 fixture IDs, same order, no missing or extra rows.
- Source fixture: `data/eval/gsm8k_100.jsonl`.
- Prompt override rows: T106B `100/100`; T114 `0/100`.
- Reconstructed rendered prompt diffs: `100/100`.
- Stored prompt-hash overlap: `0/100`.
- Difference category count: `prompt_difference=100`.
- Compressor model/profile/device/keep-rate matched.
- Target/draft/tokenizer/max-new-tokens/block-size matched.

The matched-row table is:

- `tables/t106b_vs_t114_matched_rows.csv`

Rows that were strict-correct in T106B but not strict-correct in T114:

```text
gsm8k_short_test_0008
gsm8k_short_test_0011
gsm8k_short_test_0031
gsm8k_short_test_0035
gsm8k_short_test_0048
gsm8k_short_test_0056
gsm8k_short_test_0057
gsm8k_short_test_0066
gsm8k_short_test_0070
gsm8k_short_test_0087
gsm8k_short_test_0093
gsm8k_short_test_0099
```

Rows that became T114 cap hits when T106B was not cap-hit/cap-limited:

```text
gsm8k_short_test_0008
gsm8k_short_test_0031
gsm8k_short_test_0035
gsm8k_short_test_0045
gsm8k_short_test_0048
gsm8k_short_test_0056
gsm8k_short_test_0066
gsm8k_short_test_0082
gsm8k_short_test_0088
gsm8k_short_test_0089
gsm8k_short_test_0090
gsm8k_short_test_0092
gsm8k_short_test_0093
gsm8k_short_test_0098
gsm8k_short_test_0099
```

## Controlled A/B

After the static audit, I ran only five selected regressed fixtures:

```text
gsm8k_short_test_0008
gsm8k_short_test_0011
gsm8k_short_test_0031
gsm8k_short_test_0035
gsm8k_short_test_0048
```

No full matrix rerun was performed.

Results:

- T114 config, no GSM8K policy override: `0/5` strict-correct; `4/5` cap-limited; `1/5` wrong numeric.
- T114 plus only the T106B policy suffix: `5/5` strict-correct; `0/5` cap-limited.
- Historical T106B-style command: `5/5` strict-correct; `0/5` cap-limited.

The controlled A/B table is:

- `tables/controlled_ab_results.csv`

This confirms that restoring the T106B GSM8K suffix alone flips the selected regressed rows back to the T106B behavior.

## Compression Audit

The compressor itself was not the root cause.

Both T106B and T114 used:

- compressor model: `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- compressor profile: `light`
- device map: `cuda`
- requested device map: `cuda`
- keep rate: `0.5`

Both artifacts record:

- average `N_original`: `16.0`
- average `N_compressed`: `8.0`
- average `compressed_input_tokens`: `8.0`

The T114 summary value that looked like `103 -> 8` is a metric semantic change. Task114 normalized `original_input_tokens` to precompression model chat-template prompt tokens. T106B used compressor-token `original_input_tokens` from `N_original`. Therefore `103 -> 8` does not mean the compressor compressed 103 model tokens to 8 compressor tokens.

## Generation Audit

Generation settings matched for the root-cause dimensions:

- condition: `CC-DFlash-R2`
- dataset: `gsm8k_short`
- seed: `42`
- `max_new_tokens=256`
- target: `models/Qwen3-4B`
- draft: `models/Qwen3-4B-DFlash-b16`
- tokenizer: `models/Qwen3-4B`
- block size: `16`
- device: `cuda:0`

The observed generation differences follow from the prompt suffix change. In the controlled A/B, policy-restored rows produced shorter finalized answers; no-policy rows often ran to the token cap.

## Evaluation Audit

There is also evaluation/reporting drift, separate from the prompt regression.

T106B report counts use the Task95B calibrated GSM8K proxy:

- strict correct: `88/100`
- cap-limited incomplete: `2/100`
- strict wrong numeric: `10/100`

T114 published fields use Task114's row-field evaluator:

- strict correct: `81/100`
- cap hit: `17/100`
- wrong numeric: `18/100`
- invalid: `1/100`

Recomputing the T114 rows with the Task95B evaluator gives:

- strict correct: `79/100`
- cap-limited incomplete: `15/100`
- strict wrong numeric: `6/100`

That is the old pre-fix pattern, which further supports the prompt-regression diagnosis.

## Authoritative Result

T106B remains authoritative for the scoped GSM8K candidate because T114 did not reproduce the T106B runtime policy override.

T114 is authoritative only for the configuration it actually ran: the canonical runner's no-GSM8K-policy-override GSM8K CC-DFlash condition.

## Minimal Next Repair

Run a repaired Task114 GSM8K `CC-DFlash-R2 Light GPU` condition with:

```bash
--gsm8k-policy-suffix "Keep the solution concise. End with exactly one line in the format: Final answer: <number>. Do not continue after the final answer."
--gsm8k-policy-name gsm8k_concise_final_answer_v1
```

Then rebuild the canonical summary and evaluator outputs. Do not change Phase 2 claims until the repaired configuration is verified.

