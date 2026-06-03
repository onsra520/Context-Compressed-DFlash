# CCDF Task Plan

## Phase 0 - Safety Cleanup

- Keep the module architecture unchanged.
- Use reference files only as local source material.
- Avoid running `setup.sh` during review or cleanup passes.

## Phase 1 - Upstream Split

- Copy upstream DFlash logic into the new `src/ccdf/dflash/` split when implementation work resumes.
- Keep speculative decoding behavior isolated from compression logic.
- Preserve the raw reference files until the split is fully verified.

## Phase 2 - Compression Wiring

- Implement real compressors behind the `CompressorBase` interface.
- Keep the passthrough baseline available for controlled comparisons.
- Align segmentation and prompt assembly with the runtime contract.

## Phase 3 - Benchmark Validation

- Replace skeleton metrics with real EM, invalid-output, and `tau` measurements.
- Validate benchmark conditions against the final experiment matrix.
- Run the real Gate 0 synthetic probe only after model wiring exists.

## Phase 4 - Reporting

- Keep all review and change reports under `docs/reports/`.
- Preserve any legacy placeholder logs in `docs/reports/` when they are useful as traceability.
