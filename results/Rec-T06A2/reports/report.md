# Rec-T06A2 efficient block-verification decision

The cached Baseline-AR and one-forward-per-block DFlash verifier were restored
as a diagnostic experiment. The verifier showed real block acceptance and
target-forward savings, but the locked NF4 target diverged from cached Baseline
on the frozen QMSum fixture at emitted token 16. Cache position, correction
index, and crop arithmetic were consistent at the divergence.

Decision: NF4 does not currently support an efficient exact-token-parity
DFlash claim on this SDPA/bfloat16 path. The Rec-T06A1 oracle remains
diagnostic-only; no oracle fallback was introduced here.
