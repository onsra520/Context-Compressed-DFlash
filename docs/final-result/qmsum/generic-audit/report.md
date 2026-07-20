# Four-condition Stage 2 audit

Conclusion: **PASS**

QMSum quality is deterministic ROUGE-L F1 lexical overlap; semantic correctness is not claimed.

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
| qmsum_outputs_nonempty | PASS |
| qmsum_context_selection_accounting | PASS |
| qmsum_selected_context_shared | PASS |
| qmsum_compressed_context_shared | PASS |

## Diagnostics

| Diagnostic | Result |
|---|:---:|
| original_generated_token_parity | False |
| compressed_generated_token_parity | False |
| meaningful_compression | True |
| meaningful_compression_status | PASS |

## Condition metrics

| ID | Condition | Success | Decode mean tok/s | Generation E2E mean tok/s | Pipeline E2E mean tok/s |
|---|---|---:|---:|---:|---:|
| C1 | Baseline-AR | 20/20 | 22.7444 | 17.0063 | 17.0063 |
| C2 | DFlash-R1 | 20/20 | 41.6012 | 24.7342 | 24.7342 |
| C3 | LLMLingua-AR-R2 | 20/20 | 23.8596 | 17.1721 | 14.1253 |
| C4 | CC-DFlash-R2 | 20/20 | 40.9009 | 24.2875 | 18.8807 |
