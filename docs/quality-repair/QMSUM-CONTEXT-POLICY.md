# QMSum context policy

## Benchmark identity

The implemented workload is the **QMSum query-aware budgeted-context benchmark**. It is not a full-context benchmark and no longer uses a 1,000-word prefix.

## Deterministic selection contract

The canonical pipeline renders non-empty speaker turns and groups adjacent small turns into chunks targeting 300 target-model tokens. It keeps an oversized utterance intact rather than silently cutting speaker evidence. Each chunk receives a deterministic score from normalized query-token overlap, transcript-relative rare-term weight, exact entity overlap, number overlap, and normalized phrase match. Equal scores break by source position and chunk ID.

Candidates are considered in score order, but a candidate is accepted only if the target tokenizer confirms that the combined selected context stays within the configured 1,000-token budget. Accepted chunks are finally sorted back into transcript order. The selector function has no reference-summary parameter; reference overlap is calculated only after selection as a diagnostic.

## Fairness contract

- The pipeline materializes one selected context per sample before condition execution.
- C1 and C2 consume the exact selected-context prompt.
- LLMLingua compresses the selected context once.
- C3 and C4 consume the exact same compressed-context prompt.
- Query, instruction, sample ID, source fingerprint, and prompt version remain fixed.
- Manifest and raw rows retain selected and compressed context hashes.

## Required evidence

Each canonical QMSum sample records full transcript tokens, full chunk count, selected chunk IDs, source turn ranges, selected tokens, selection keep rate, query-term/entity/number coverage, selected-context SHA-256, and reference-overlap diagnostic. Compression cache rows add compressed-context SHA-256, selected and compressed target-token counts, LLMLingua keep rate, and overall full-to-compressed keep rate.

For the locked n=10 cohort, selected contexts use at most 986 target tokens. Mean selection keep rate is 0.0819, mean LLMLingua keep rate is 0.9156, and mean overall keep rate is 0.0743.

## Parity interpretation

QMSum C1/C2 and C3/C4 exact generated-token parity are diagnostic in this repair. Input prompt and input token parity remain hard gates, as do raw completeness, hash reuse, independent metric recomputation, non-empty outputs, valid quality calculation, CUDA compression, and selector accounting. Exact mismatches remain labeled as mismatches with their first differing token, source row type, decoded outputs, quality scores, and hashes.
