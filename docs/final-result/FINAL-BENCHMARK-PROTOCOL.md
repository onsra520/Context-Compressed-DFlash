# Final benchmark n=20 protocol

This is the frozen final validation for exactly two workloads:

- GSM8K n=20 across C1-C4;
- QMSum query-aware budgeted-context benchmark n=20 across C1-C4.

No n=30 workload is permitted. Prompt, selector, safeguard, parser/evaluator,
models, verifier, seed, dtype, attention backend, and generation configuration
are frozen before model execution.

## Frozen runtime

- C1: Baseline-AR with the selected original prompt.
- C2: DFlash-R1 with the byte-identical selected original prompt.
- C3: LLMLingua-AR-R2 with the frozen compressed cache.
- C4: CC-DFlash-R2 with the byte-identical frozen compressed cache.
- Seed 42, temperature 0, SDPA math, one warmup request, one measured
  repetition, GSM8K maximum 256 new tokens, QMSum maximum 512 new tokens.
- One model load per condition. Warmup rows are retained separately and excluded
  from measured metrics.

## Deterministic selection

The already validated n10 coordinate order remains the n20 prefix. Ten
additional coordinates are chosen before any model result exists by sorting all
remaining valid source coordinates on SHA-256 of canonical JSON containing only
the dataset name, seed 42, and coordinate. References and answer content are not
selection inputs. The resulting coordinates, raw hashes, sample IDs, references,
source fingerprints, prompt hashes, and sample-file hashes are frozen in
`selection-config.json` and `SAMPLE-MANIFEST.json`.

QMSum selection remains deterministic query-aware budgeted-context selection;
the benchmark is not full-context QMSum and semantic correctness is not claimed
from its lexical ROUGE-L proxy.

## Checkpoint and mutation boundary

Compression cache rows and condition raw rows are flushed and fsynced after each
sample. SHA-256 sidecars bind each completed row to its composite key. Resume
accepts only a schema-valid, manifest-bound, hash-valid ordered prefix and skips
those rows; corrupt or mismatched evidence stops execution. C3/C4 reuse the same
single compression cache. Generation output is never edited after completion.

Once both datasets' final raw evidence is complete, no further benchmark or
source/config edit is allowed. Only independent audit, report generation,
snapshotting, hashing, and archive packaging may follow.

## Decision policy

- `FINAL_RESULTS_FROZEN`: validity, integrity, and quality-preservation gates pass.
- `FINAL_BENCHMARK_COMPLETE_WITH_FAILED_CLAIMS`: raw benchmark validity passes,
  but a quality or E2E performance claim fails.
- `FINAL_BENCHMARK_INVALID`: fairness, completeness, uniqueness, recomputation,
  CUDA placement, selector determinism, or config/runtime consistency fails.

Exact generated-token parity and E2E speedup remain diagnostics. A parity or
speed diagnostic is reported without changing verifier policy or relabeling it.

The preregistered QMSum lexical-quality preservation tolerance is an absolute
mean ROUGE-L F1 drop of at most `0.01` for C3 versus C1 and C4 versus C2. This
threshold is fixed before model execution; it is not a semantic-correctness
claim.
