# Four-condition Stage 2 audit

Conclusion: **FAIL**

GSM8K quality is anchored numeric exact match.

## Gates

| Gate | Result |
|---|:---:|
| manifest_valid | PASS |
| unified_schema | PASS |
| raw_unique | PASS |
| raw_complete | PASS |
| raw_order | PASS |
| row_identity_and_prompt_hash | PASS |
| condition_success | PASS |
| compression_unique_complete_ordered | PASS |
| compression_hash_and_status | PASS |
| compression_once_per_sample | PASS |
| fact_safety_resolved | PASS |
| compressed_prompt_reused | PASS |
| compressor_gpu | PASS |
| condition_process_isolation | PASS |
| gpu_release_between_conditions | PASS |
| independent_metric_recomputation | PASS |
| memory_scope_valid | PASS |
| original_input_parity | PASS |
| compressed_input_parity | PASS |
| valid_quality_parsing | PASS |
| original_generated_token_parity | FAIL |
| gsm8k_reference_valid | PASS |
| compressed_numeric_answer_agreement | FAIL |
| gsm8k_compressed_quality_non_regression | FAIL |

## Diagnostics

| Diagnostic | Result |
|---|:---:|
| original_generated_token_parity | False |
| compressed_generated_token_parity | False |
| meaningful_compression | False |
| meaningful_compression_status | FAIL |

## Condition metrics

| ID | Condition | Success | Decode mean tok/s | Generation E2E mean tok/s | Pipeline E2E mean tok/s |
|---|---|---:|---:|---:|---:|
| C1 | Baseline-AR | 20/20 | 31.9786 | 31.3785 | 31.3785 |
| C2 | DFlash-R1 | 20/20 | 114.6382 | 105.1603 | 105.1603 |
| C3 | LLMLingua-AR-R2 | 20/20 | 31.6442 | 31.0095 | 30.1611 |
| C4 | CC-DFlash-R2 | 20/20 | 110.4460 | 100.7350 | 92.5506 |
