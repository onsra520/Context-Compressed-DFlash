# Generic compression safeguard design

Status: **IMPLEMENTED AND VALIDATED ON 10/10 CANONICAL MOCK PROMPTS**

## Objective

Reduce non-semantic wording with LLMLingua while retaining the exact clauses and literals that define the task, quantities, relationships and output contract. The safeguard is rule-based by semantic category and syntax; it never branches on mock IDs, answers or expected model outputs.

## Processing contract

```text
original prompt
  -> ordered clause/literal segmentation
  -> protected and compressible spans
  -> LLMLingua on compressible spans only
  -> span-index reconstruction
  -> independent safeguard validation
  -> success cache row or explicit failure cache row
```

Every segment has stable index, character start/end, original text, protected flag and zero or more generic reasons. The spans must be contiguous, non-overlapping and cover the original exactly before compression.

## Generic protection taxonomy

- Numeric expressions: signed integers/decimals, grouped numbers, fractions, percentages, currency amounts, arithmetic symbols and operator words.
- Units and quantities: count, currency, distance, area, volume, time, speed and percentage units, including compound forms.
- Semantic relations: increase/decrease, add/remove, buy/sell/use/remain, before/after, then, original/new/final, comparison and equality.
- Negation and zero relations: no/not/never/without/neither/nor/zero and equivalent negative constructions.
- Time and ordering: elapsed time, duration, stops, hours/minutes, sequence words and before/after conditions.
- Logic: if/unless/only/all/any/each/every/and/or and condition-bearing clauses.
- Main request: interrogative or directive clauses asking to compute, find, explain, determine, return or report the result.
- Output contract: required final line, exact form/format, labels/fields/order, rounding, units/currency, and stop requirements.
- Literals: backticked or quoted text that the response must reproduce.

Clauses containing semantic quantities, relations, logic, main requests or output constraints are protected as whole clauses so subjects/objects are not separated from critical keywords. Literal intervals are always protected. Remaining stylistic or explanatory instruction spans are eligible for compression.

## Reconstruction and validation

Compressed replacements retain safe boundary whitespace and are inserted only at their original span indices. Validation independently checks:

1. contiguous segmentation and monotonic reconstruction order;
2. exact protected-span text appearing once and in order;
3. multiset equality for numbers, operators, units, negation, relations, time/logic markers and required literals;
4. output-constraint and main-request presence;
5. non-empty reconstructed prompt;
6. at least one non-whitespace compressible span was sent to LLMLingua;
7. the reconstructed prompt differs from the original and target/compressor token evidence reports an actual reduction.

The validator emits structured check results and specific failure reasons. A failed row is not replaced by the original prompt and is not generation-eligible.

## Non-goals and rejected shortcuts

- no per-prompt rules, answer list or token-ID rules;
- no keep-rate 1.0, whole-prompt protection, compression bypass or original-as-compressed fallback;
- no semantic claim based only on string presence—the mock quality gate remains authoritative;
- no verifier change until the safeguarded four-condition rerun provides new mismatch evidence.
