# Stage 2 test plan

Status: **EXECUTED THROUGH R3 — R4/R5 NOT AUTHORIZED AFTER R3 PARITY FAILURE**

The test plan uses small fake compressors/models and record fixtures until the ordered GPU runs. It does not load GSM8K or QMSum.

## Required unit and contract tests

| ID | Requirement | Planned test evidence |
|---|---|---|
| T01 | protected-span segmentation | alternating spans cover the original byte-for-byte with ordered offsets/reasons |
| T02 | numbers/operators preserved | integers, decimals, fractions, percentages, currency and symbolic/word operators survive |
| T03 | units preserved | distance, volume, area, speed, count and currency unit fixtures survive |
| T04 | negation preserved | `not`, `no`, `never`, `without`, `zero` relationship fixtures survive |
| T05 | increase/decrease/add/remove preserved | generic relationship clauses remain exact |
| T06 | stop/duration time preserved | elapsed, duration, stop, minutes/hours and before/after clauses remain exact |
| T07 | output constraint preserved | final-line format, required labels, fields, quoting and literals remain exact |
| T08 | reconstruction order | protected/compressed spans reconstruct in original span-index order |
| T09 | safeguard failure | changed/missing critical token and reordered protected span produce explicit reasons |
| T10 | exact C3/C4 cache reuse | both conditions consume the same compression run and prompt hash |
| T11 | compressor GPU contract | all parameters and buffers must resolve to requested CUDA device |
| T12 | no silent CPU fallback | unavailable CUDA, CPU request, mixed tensors and bad index fail explicitly |
| T13 | pipeline E2E arithmetic | compressed pipeline latency equals compressor plus generation latency |
| T14 | generation E2E isolation | generation latency is unchanged by compressor latency |
| T15 | tokenizer spaces | compressor, target-user and target-full counts/rates remain distinct |
| T16 | duplicate raw records | duplicate composite keys fail with exact keys before indexing |
| T17 | duplicate compression rows | duplicate sample IDs fail before cache lookup |
| T18 | missing/extra records | manifest-set difference reports exact missing and unexpected keys |
| T19 | multiple repetitions | expected keys and summaries work for repetitions greater than one |
| T20 | failure rows | injected prepare/generate/serialize errors yield durable failed records |
| T21 | runtime error recomputation | error totals/stages/types derive only from raw rows |
| T22 | manifest row expectations | warm-up/measured expected counts derive from manifest schedule |
| T23 | no overwrite PASS | adding a duplicate contradictory row can never preserve PASS |
| T24 | compressor budget conflict | unequal model/memory budget fields fail config validation |
| T25 | one-ULP scope | proposal IDs use strict target argmax; one-ULP/lower-ID only selects correction row |

Additional tests will cover manifest hashes/model identities, condition/process identity, prompt-kind/hash rules, null applicability, partial metrics on failure, durable flush behavior, metric tolerance comparison, source-manifest coverage, and safeguard non-no-op behavior.

## Ordered runtime gates

| Run | Workload | Preconditions | Required result |
|---|---|---|---|
| R1 | targeted safeguard tests | T01–T09 implemented | all pass without model load |
| R2 | representative four-condition smoke | schema/runner/audit unit suite green; GPU unowned | CUDA compressor, safeguard, isolation, failure schema and metric arithmetic pass |
| R3 | canonical mock10 × C1–C4 | R2 pass | C1/C2 10/10, C3/C4 10/10, C3/C4 quality 10/10, complete manifest/raw/audit |
| R4 | canonical Baseline/DFlash | R3 pass | 50/50, mock-08 5/5, all existing gates, performance deltas reported |
| R5 | deterministic non-dataset stress suite | R4 pass | no pair mismatch or safeguard failure; policy activations and output changes reported |

If R3 mismatches, the next action is first-mismatch instrumentation and bounded diagnosis—not R4, R5, verifier policy expansion, or Stage 3.

## Final audit matrix

The final independent validator must establish completeness, uniqueness, schema validity, prompt/cache consistency, model/policy identity, pairwise parity, safeguard outcomes, quality, errors, latency/throughput formulas, all token spaces, memory scopes, runner-summary agreement, GPU-boundary isolation, dependency snapshot equality, and stored manifest integrity. Missing evidence is a failed gate, not a caveat.
