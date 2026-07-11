# Rec-T03B-R1 - Canonical Baseline and DFlash Audit n=10

Status: PASS_WITH_WORKLOAD_LIMITATION

The historical `Rec-T03B` matrix is retained unchanged and reclassified as `RUNTIME_SMOKE_ONLY`, `NONCANONICAL_FOR_PERFORMANCE`, and `NONCANONICAL_FOR_QUALITY` because it used `max_new_tokens=8`.

This R1 matrix resolves the canonical configuration before each isolated cell: GSM8K uses `256` new tokens and QMSum uses `384`. All `40/40` rows completed and carry the exact per-condition resolved configuration hash. DFlash counters and process isolation passed.

Every row still reached its configured cap, so quality remains cap-limited; QMSum semantic correctness remains `NOT_CLAIMED`. The result establishes canonical runtime behavior and must not be read as an uncaveated quality or end-to-end speed claim.
