# Rec-T06B trusted n3 measurement validation

## Scope and boundary

Rec-T06B establishes trusted measurement, artifact integrity, provenance, and
worker isolation for later n30 work. It does not run n30 or reopen A3 parity:
exact cached-AR token equivalence remains **NOT_CLAIMED**, structural target
verification remains **REQUIRED_AND_AUDITED**, and quality preservation remains
**EMPIRICALLY_EVALUATED**.

## Canonical path

Each Baseline-AR, DFlash-R1, and CC-DFlash-R2 condition ran in a distinct real
worker subprocess using `RuntimeEngine`. Worker manifests record PID,
environment, config hash, timing, resource fields, output hash, and successful
exit status. Evaluation reads only the manifest-listed JSONL files and never
loads models or reruns generation.

## Timing and resource contract

`generation_request_e2e_ms` excludes compression. `warm_request_e2e_ms`
includes compression for CC-DFlash. `cold_start_e2e_ms` includes model
initialization plus one request. Generation-only values are never called total
E2E; CC-DFlash comparisons use compression-inclusive warm E2E.

Peak CUDA allocated/reserved, composition, process RSS around compressor load,
CPU compressor delta, and A3 forward counters are emitted. Unavailable
target-only and drafter-incremental GPU deltas are explicit `null` fields with
an unsupported-field inventory rather than invented values.

## n3 result

GSM8K and QMSum each completed three rows for all three conditions with clean
worker exits, verified hashes, valid structural DFlash accounting, and no
cap/repetition/instruction-echo/runtime failures. QMSum semantic correctness
remains **NOT_CLAIMED**.

For QMSum n3, CC-DFlash warm E2E was 5742.79 ms while generation-only E2E was
2700.28 ms and compression was 3025.14 ms, demonstrating that the reported
warm comparison includes compression.

No n30, Rec-T06C, Rec-T06D, archive changes, or push occurred.
