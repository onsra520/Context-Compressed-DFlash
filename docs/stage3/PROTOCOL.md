# Stage 3 n=10 four-condition protocol

## Conditions

| ID | Name | Input | Generation |
|---|---|---|---|
| C1 | Baseline-AR | original prompt | target autoregressive |
| C2 | DFlash-R1 | original prompt | DFlash |
| C3 | LLMLingua-AR-R2 | one cached compressed prompt | target autoregressive |
| C4 | CC-DFlash-R2 | the same cached compressed prompt | DFlash |

Compression runs exactly once per selected sample. C1/C2 share the exact original prompt; C3/C4 share
the exact compressed prompt hash. Every condition shares ordered sample IDs, target tokenizer/model, seed,
generation/stopping policy, parser, evaluator, and `max_new_tokens`; C2/C4 also share the drafter.

## Gate classification

Hard gates are C1/C2 exact output-token parity, C3/C4 compressed-prompt hash equality, CUDA compressor
placement, sample alignment, raw completeness, duplicate/missing/error rejection, valid parsing, and
independent metric recomputation.

C3/C4 exact generated-token parity, mock compression ratio, and the 110-120 tok/s reference are diagnostic.
A C3/C4 mismatch records sample, index, proposal/correction row type, tokens, decoded outputs, and whether
quality remains correct. This task does not modify verifier selection, broaden the correction-only one-ULP
rule, use an AR oracle, add token/prompt rules, or disguise sequential verification as block verification.

## Dataset contract

Canonical samples contain stable `sample_id`, `dataset`, `split`, `source_id` or `source_index`, `task_type`,
`question` or `query`, `context`, `reference`, `metadata`, `source_fingerprint`, and `prompt_version`.
Selection is deterministic, exactly n=10 per dataset, persisted in a reloadable manifest, and never mutated
or condition-specific.

GSM8K uses a deterministic numeric parser and exact numeric equality. QMSum uses a deterministic lexical
quality proxy (ROUGE-L F1 or normalized overlap), explicitly not semantic correctness proof. Empty output,
truncation, parser failures, and runtime failures remain explicit evidence.

## Metrics and durability

Raw records separate compressor, target-user, and target-full token spaces; generation and pipeline E2E;
compressor and generation VRAM; and DFlash draft/verification/acceptance/tau metrics. For C3/C4,
`pipeline E2E = compressor latency + generation E2E`; for C1/C2 pipeline equals generation.

Every expected row is durably flushed. Failed work produces a row with stage/type/message and available
partial metrics. Manifest-owned expected keys drive completeness and uniqueness; audit never hard-codes n=10.

## Ordered execution

1. Freeze Stage 2 evidence.
2. Canonical Baseline-first then DFlash guard: one warm-up and 5 repetitions across 10 prompts.
3. Implement and test Dataset Pipeline only after 50/50 guard parity.
4. Regress mock10 x C1-C4.
5. Run GSM8K n=10 x C1-C4.
6. Run QMSum n=10 x C1-C4.
7. Stop. No full benchmark.

