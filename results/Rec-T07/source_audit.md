# Rec-T07 full source audit

Result: **PASS_WITH_ENVIRONMENT_LIMITATION**. This is a full-repository review of runtime ownership, CUDA fallback, cleanup, benchmark/evaluator integrity, task/path drift, CLI/packaging, resources, tests, and documentation. It does not alter preserved Rec-T06D or Rec-T07 n=100 evidence.

## Fixed critical/high issues

- CUDA compressor verification now inventories every discoverable backend parameter and buffer. A CUDA request fails for an empty inventory, a CPU tensor, or mixed/offloaded placement. It records unique devices, total/CUDA parameter and buffer counts, byte counts, and `resident`/`staged` mode.
- The runtime now measures CUDA allocated and reserved deltas around compressor construction. If CUDA telemetry is unavailable, it emits `null` and names the unsupported field; it never writes a fabricated zero.
- Composition derives from actual residency. GSM8K short-context GPU conditions explicitly say `compressor bypassed and not loaded`; QMSum GPU variants say GPU compressor only when one was loaded.
- The audit exposed an offline environment dependency: LLMLingua may need a locally cached tiktoken encoding. The README makes it a prerequisite and does not suggest network download during runtime.

## Audit outcomes

- `RuntimeEngine.close()` drops target, drafter, compressor, tokenizer, then garbage-collects and releases CUDA cache/IPC. Canonical workers are process isolated.
- Parent/worker hashes, fixture order, condition matrices, source state, evaluator manifests, and stale-artifact checks protect benchmark/evaluator integrity.
- QMSum reports lexical/reference proxy metrics only. Semantic correctness is **NOT_CLAIMED**.
- CLI and package entry point are `ccdf` / `python -m ccdf`: `run`, `benchmark`, `evaluate`, and `paths`. Legacy Rec-T03/Rec-T04 runners are explicitly noncanonical diagnostic code.
- Current RSS, peak RSS, peak CUDA allocated/reserved, model composition, and unsupported attributions have distinct meanings and are no longer conflated.

## Lower-severity findings

- Target-only and drafter-incremental VRAM cannot be truthfully isolated under a shared CUDA allocator; fields remain null with metadata.
- This root checkout’s `.venv` currently reports no visible CUDA device, so the real GPU probe was not possible. No n=3 or n=100 benchmark was rerun; focused device-placement tests cover resident and rejected-fallback paths.
- Historical Rec-T03/Rec-T04 task labels remain in clearly marked noncanonical modules; they are not active Rec-T06D/Rec-T07 paths.
