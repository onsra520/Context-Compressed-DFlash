# Rec-T07 source audit

## Fixed high-severity findings

- GPU compressor conditions previously lacked explicit condition identities and
  could not prove CUDA parameter placement. Rec-T07 adds GPU-only condition
  IDs, resolves their compressor device to `cuda`, and rejects unverified CUDA
  placement.
- GPU compressor resource composition was previously labeled as CPU for
  `*-gpu` conditions. Runtime artifacts now expose GPU composition, device,
  and CUDA verification.
- LLMLingua-AR was previously vulnerable to DFlash invariant routing; it is
  kept on cached autoregressive decoding without a drafter.

## Audit outcomes

- Runtime ownership is per-worker-process; `RuntimeEngine.close()` releases
  target, drafter, compressor, tokenizer, and CUDA cache.
- CPU/GPU compression paths are explicit and short-context bypass remains
  explicit for GSM8K.
- Parent/worker/row provenance, exact task matrices, stale-artifact rejection,
  evaluator-only summaries, and hash inventories are enforced by workflow.
- The current CLI exposes canonical benchmark/evaluate/path commands through
  `ccdf.cli`; packaging uses the `ccdf` console entry point.
- Legacy `rec_t03b` / `rec_t04b` runners remain diagnostic/legacy code and are
  not used by canonical Rec-T06D or Rec-T07 paths.

## Lower-severity follow-up

- GPU compressor parameter-byte accounting is represented as verified device
  placement and peak process CUDA allocation, not a claimed isolated model-byte
  delta; this avoids inventing an unsupported attribution.
