# Quality repair map

## Scope and frozen boundary

This repair changes prompt compression safety, the QMSum context-selection policy, four-condition evidence fields, and their tests. It does not change the DFlash verifier, generation policy, attention backend, dtype, model inventory, dependencies, or `.worktrees/`. The pre-change source, package, environment, config, workspace status, and 68-test baseline are frozen under `docs/reviews/10-quality-repair-gsm8k-qmsum-n10/freeze/` and `environment/`.

## Root causes and repairs

| Area | Root cause | Repair | Proof |
|---|---|---|---|
| Sentence-final currency | The protector number regex ended with `(?![\w.])`, so the sentence-ending dot after `$20` invalidated the whole match. | End the numeric match before punctuation with `(?!\w)`; a dot belongs to a decimal only through `\.\d+`. | Unit cases for `$20.`, `$20,`, `3.5`, `1,200`, and `20%`; real source row 158 preserves `$20.`. |
| Written fractions | The protector had numeric fractions but no written-fraction category, and relation vocabulary omitted `remaining`, `left`, and `of`. | Add written-fraction recognition and protect complete semantic clauses containing fractions or relations. | Real source row 104 preserves `a quarter of the pieces` and `a third of the remaining pieces`. |
| Correlated validation | Protector and validator used the same pattern inventory, allowing a shared extractor defect to pass unnoticed. | Add `compression/fact_validation.py` with independent normalized extractors and before/after inventories. | Broken currency and fraction candidates fail independent validation. |
| Fixed compression rate | One fixed 0.50 rate was applied irrespective of target prompt length. | Select 0.85 below 128 target-user tokens, 0.70 for 128–512, and 0.55 above 512 from validated config. | Boundary tests and cache rows record target token count plus requested rate. |
| Silent safety failure | A failed safeguard made the compression row unusable and prevented generation. | Retry once at 0.90; if still unsafe, cache the original prompt with explicit `FACT_SAFETY_FALLBACK`. | Retry/fallback tests and zero-fallback workload summaries. |
| QMSum prefix | A hard-coded 1,000-word prefix ignored the query and used the wrong token unit. | Build speaker-turn chunks, score them lexically against the query, select within a 1,000 target-token budget, then restore transcript order. | Byte-identical double build, 10 selected-context hashes, max 986 selected tokens. |

## Runtime flow

1. The target tokenizer counts the complete user prompt.
2. Config selects the requested LLMLingua keep rate.
3. For QMSum, deterministic context selection has already produced one selected context shared by C1–C4.
4. The protector identifies full semantic spans; LLMLingua sees only compressible spans.
5. The independent validator compares normalized fact inventories.
6. Unsafe output retries at 0.90, then explicitly falls back to the original prompt if needed.
7. One cached result is shared by C3/C4. Fallback remains generation-eligible but is excluded from compression-success and ratio summaries.

## Touched implementation surfaces

- `config.yml`: adaptive rates and QMSum token policy.
- `src/ccdf/compression/fact_validation.py`: independent validator.
- `src/ccdf/compression/safeguard.py`: span protection and numeric parsing.
- `src/ccdf/compression/llmlingua.py`: target-token policy, retry/fallback, context-only QMSum compression, and metrics.
- `src/ccdf/datasets/qmsum_context.py`: deterministic selector.
- `src/ccdf/datasets/pipeline.py` and `schema.py`: canonical selected-context materialization and validation.
- `src/ccdf/benchmark/four_condition/`: manifest, raw record, runner, audit, parity, and metric separation.
- `tests/`: 95-test targeted and regression suite.

No DFlash verifier file was changed by this repair.
