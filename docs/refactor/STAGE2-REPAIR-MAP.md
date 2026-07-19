# Stage 2 repair map

Status: **REPAIRS IMPLEMENTED AND AUDITED — FINAL GATE BLOCKED BY C3/C4 9/10 PARITY**

Final implementation closes the safeguard, schema, durable failure evidence, manifest, metric-space,
configuration, and audit-integrity failures. The retained blocker is S2-F20: one fully instrumented
query-shape-sensitive FP16 correction-row mismatch on `mock-04`. R4/R5 were not opened because R3 failed.

Scope is limited to the completed source refactor and four-condition runtime. No dataset module, GSM8K loader, QMSum loader, or Stage 3 implementation is allowed.

## Preserved truth

- Canonical Baseline/DFlash exact parity: 50/50; mock-08: 5/5.
- Post-refactor Baseline decode mean: 31.6017 tok/s.
- Post-refactor DFlash decode mean/median: 113.9373/109.0489 tok/s.
- DFlash peak reserved: 3.626953 GiB.
- Compressor: strict CUDA placement with no silent CPU fallback.
- Existing test baseline: 30 passed.

## Failure-mode inventory

| ID | Failure mode | Current evidence | Risk | Planned repair | Required proof | Status |
|---|---|---|---|---|---|---|
| S2-F01 | Whole prompt is sent to LLMLingua | `compress_samples()` passes `[original]`; cached prompts dropped semantic/output language | C3/C4 quality 2/10; unstable near-tie inputs | generic protected-span segmentation, compress only allowed spans, reconstruct in order | protected-span unit suite; non-no-op compression; 10/10 safeguard validation | MAPPED |
| S2-F02 | No safeguard evidence or validator | cache lacks protected/compressible/compressed spans and validation reasons | corrupted prompts can reach generation | persist segmentation and validation evidence; block generation on failed cache rows | validation-failure test and failure-row smoke | MAPPED |
| S2-F03 | Compression failure aborts the whole cache | exceptions escape before durable cache write | previously completed sample evidence is lost | per-sample compression rows with success/failed status and immediate flush | injected compressor/validator failure test | MAPPED |
| S2-F04 | Compression-cache duplicates overwrite silently | runner constructs `{sample_id: row}` directly | duplicate evidence can masquerade as one valid sample | explicit uniqueness validator before indexing | duplicate-cache row test with exact key report | MAPPED |
| S2-F05 | Generation rows are buffered until process end | CLI calls `run_condition()` then writes all rows | crash loses prior successful/failure records | stream one record at a time with flush/checkpoint | interrupted/injected failure durability test | MAPPED |
| S2-F06 | Generation exception loses the expected row | no per-schedule exception capture | missing evidence and undercounted errors | emit schema-valid `status=failed` row with stage/type/message and partial metrics | failure-row and runtime-error recomputation tests | MAPPED |
| S2-F07 | End-to-end metric is generation-only for C3/C4 | `warm_e2e_time_ms` maps directly to runtime warm request | pipeline latency/throughput claims are understated | distinct generation/pipeline E2E fields and formulas | arithmetic tests plus raw recomputation | MAPPED |
| S2-F08 | Token spaces are conflated | one target-full `keep_rate` and `compression_ratio`; compressor counts use different tokenizer | compression claims are ambiguous | report compressor, target-user, and target-full token spaces separately | deterministic tokenizer-space fixture tests | MAPPED |
| S2-F09 | Condition memory can be misread as simultaneous E2E peak | `max(staged compressor, generation)` is named condition peak without process scope | misleading VRAM claims | preserve separate peaks; condition process peak only when actually measured; explicit scope/status | schema/nullability and aggregation tests | MAPPED |
| S2-F10 | Audit hard-codes mock10 cardinality | gates require 10 measured, 1 warm-up, four fixed row counts | audit cannot validate other repetitions or stress workloads | manifest-driven expected keys and counts | multiple-repetition and manifest expectation tests | MAPPED |
| S2-F11 | Duplicate raw keys overwrite in parity | `_pair_parity()` dictionary comprehensions overwrite later keys | false parity PASS | reject duplicates before any dictionary/index construction | duplicate-raw test and overwrite-regression test | MAPPED |
| S2-F12 | Missing/unexpected/extra rows are incompletely detected | audit checks aggregate lengths only | wrong grain can pass | exact expected-key set comparison from manifest | missing, unexpected, extra-repetition tests | MAPPED |
| S2-F13 | Sample selection and cache ordering are trusted indirectly | expected order comes from compression rows | corrupted cache can redefine truth | manifest owns sample IDs/order; selection and cache each validated against it | wrong-order/hash tests | MAPPED |
| S2-F14 | Error summary is hard-coded | CLI writes `runtime_error_count: 0` | false clean-run claim | recompute error counts/stages/types from raw | runtime-error recomputation test | MAPPED |
| S2-F15 | Runner/audit recomputation contract is absent | only audit summary exists; no tolerance comparison | formulas can drift silently | independent audit summary plus runner-side summary comparison with explicit tolerance | calculation spot-check tests | MAPPED |
| S2-F16 | Compressor memory budget has two sources | model and memory values both 2.25, only memory value is consumed | future config conflict is silent | require both and enforce exact equality; expose canonical source | conflict and equality tests | MAPPED |
| S2-F17 | LLMLingua dependency is installed but undeclared | environment has `llmlingua 0.2.2`; `pyproject.toml` omits it | fresh install metadata is incomplete | evidence-only dependency note/proposal; no install or environment mutation | before/after environment snapshot equality | MAPPED |
| S2-F18 | Documentation has stale pre-refactor status | source map retained its old initial-status marker | audit trail contradicts current code | update status and Stage 2 documents | stale-string search | IMPLEMENTED |
| S2-F19 | Final manifest scope is incomplete | prior source manifest omitted config, pyproject and Stage 2 docs | source integrity claim is partial | package manifest covers all named roots/files | stored-manifest verification | MAPPED |
| S2-F20 | C3/C4 parity is 8/10 | mock-02 correction mismatch; mock-10 accepted proposal mismatch | Stage 3 hard blocker | rerun after safeguard before any verifier edit | C3/C4 10/10 or first-mismatch evidence | MAPPED |
| S2-F21 | C3/C4 quality is 2/10 | compressed prompts lost task/output semantics | Stage 3 hard blocker | protected semantic clauses and output contracts | C3/C4 quality 10/10 with measured token reduction | MAPPED |
| S2-F22 | Existing correction-row ULP policy could be widened casually | policy currently isolated in acceptance correction selection | accepted proposals could violate strict verifier contract | preserve scope; any later policy change requires a generic ablation before acceptance | explicit scope unit test and activation counts | MAPPED |
| S2-F23 | Stress coverage is missing | only canonical ten prompts were run | prompt-specific success could be mistaken for generic correctness | deterministic non-dataset stress prompt suite | stress C1/C2 and C3/C4 parity with no new mismatch | MAPPED |
| S2-F24 | Post-repair canonical regression is missing | last 50-request run predates safeguard/evidence changes | protected C1/C2 truth is unproven after repairs | rerun Baseline then DFlash, 1 warm-up + 5 repetitions | parity 50/50, mock-08 5/5, all existing gates | MAPPED |
| S2-F25 | Run identity/policy expectations are implicit | raw rows have run ID but no authoritative run manifest | audit cannot prove model/policy/row contract | durable manifest with policy hash, identities and exact expected keys | manifest schema/hash tests | MAPPED |

## Repair sequence and acceptance boundaries

1. Add safeguard models, segmentation, validation and focused CPU tests. No model load.
2. Integrate per-sample durable compression evidence and strict GPU/budget contracts.
3. Replace the unified raw schema and runner with manifest-driven streaming success/failure rows and separated metric spaces.
4. Replace hard-coded audit logic with uniqueness/completeness/validity checks before any indexing, then independently recompute every metric/error count.
5. Run a representative four-condition smoke, then canonical mock10 C1–C4.
6. Only if safeguarded C3/C4 still mismatch, capture the first mismatch contract. Do not edit verifier policy before this evidence exists.
7. If a production-valid generic policy is proposed, record activation counts and run its required ablation. Oracle, AR replay, sequential disguise, prompt/token rules and arbitrary epsilon remain rejected.
8. Rerun canonical 50-request regression and the external deterministic stress suite.
9. Package the report/evidence and emit only the strict Stage 3 gate conclusion.

No later step can waive an earlier failed correctness, quality, evidence-integrity, CUDA-placement, or environment-integrity gate.
