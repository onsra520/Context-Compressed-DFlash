# Dataset Pipeline reference map

Reference root: `.worktrees/02-MAIN-DATASET-PIPELINE-REFERENCE/` (read-only). The reference is an old,
known-buggy source tree. Decisions below concern concepts only; no file is copied verbatim and no model,
runtime, verifier, determinism, global-config, benchmark-execution, or validation implementation is imported.

| ID | Reference concept/file | Known issue | Decision | New implementation | Tests | Status |
|---|---|---|---|---|---|---|
| DP-01 | `datasets/schemas.py` canonical fixture fields | Old field names omit the Stage 3 `sample_id`, task, fingerprint, and prompt-version contract | REWRITE | `src/ccdf/datasets/schema.py` | canonical required fields, types, empty/reference checks | IMPLEMENTED |
| DP-02 | `datasets/gsm8k.py` raw conversion and final `####` reference extraction | Old schema and prompt provenance are tied to a prior recovery stage | PORT_CONCEPT | `src/ccdf/datasets/pipeline.py` | stable ID, numeric reference, deterministic prompt | IMPLEMENTED |
| DP-03 | `datasets/qmsum.py` meeting/query normalization | Prior version permits unversioned truncation and uses an older fixture contract | PORT_CONCEPT | `src/ccdf/datasets/pipeline.py` | query/reference, full-source fingerprint, versioned deterministic 1,000-word whole-turn prefix, explicit truncation accounting | IMPLEMENTED |
| DP-04 | `datasets/validation.py` duplicate and deterministic subset checks | Hard-coded n10/n30/n100 hierarchy is outside this n=10 audit and not manifest-driven | REWRITE | `src/ccdf/datasets/schema.py` and `pipeline.py` | manifest-owned count/order, duplicate, empty, reload checks | IMPLEMENTED |
| DP-05 | `datasets/pipeline.py` staged raw-to-eval build | Old implementation copies raw data and produces unrelated full subset families | PORT_CONCEPT | `src/ccdf/datasets/pipeline.py` | raw hashes unchanged, two-build byte identity, source lock | IMPLEMENTED |
| DP-06 | `datasets/hashing.py` canonical SHA-256 helpers | Helper is coupled to old package layout | PORT_CONCEPT | private canonical JSON/text hashing helpers | fingerprint and prompt-hash assertions | IMPLEMENTED |
| DP-07 | `evaluation/gsm8k.py` decimal exact match | It imports an output contract absent from current source | REWRITE | `src/ccdf/evaluation/datasets.py` | anchored final-line parser, Decimal equality, parse-failure status | IMPLEMENTED |
| DP-08 | `evaluation/qmsum.py` lexical reference proxy | Set overlap drops order/frequency and is not ROUGE-L | REWRITE | deterministic ROUGE-L F1 in `src/ccdf/evaluation/datasets.py` | independent LCS recomputation and empty-output handling | IMPLEMENTED |
| DP-09 | Reference model/runtime/verifier/determinism/config code | Known parity and runtime-contract bugs; explicitly outside permitted reference scope | REJECT | Current Stage 2 source remains authoritative | canonical 50/50 guard | COMPLETE |
| DP-10 | Reference benchmark/workflow/process-isolation code | Does not implement the current four-condition raw schema or gate policy | REJECT | Current `benchmark/four_condition` runner is extended in place | mock10, GSM8K n=10, and QMSum n=10 four-condition audits | COMPLETE |

## Selection and mutation boundary

The selection manifest stores source coordinates, seed 42, selected stable IDs, source fingerprints, and
prompt hashes. The builder reads `data/raw/` without modifying it and writes only canonical evaluation rows
and manifests. A condition never selects or substitutes a sample. All four conditions consume the same
manifest-owned ordered list.

QMSum preserves the complete raw source and its fingerprint, then applies the versioned Dataset Pipeline
strategy `prefix_1000_words_whole_turns` before runtime. Each sample records whether truncation occurred,
the original and retained character/word/turn counts, the 1,000-word limit, and the truncation reason.
The same materialized prompt is used by all four conditions; no runtime truncation or condition-specific
mutation is permitted.
