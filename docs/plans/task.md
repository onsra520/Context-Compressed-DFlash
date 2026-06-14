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

## Extra UI Tasks Live Tracker

| Task ID | Description | Status | Report |
| --- | --- | --- | --- |
| UI-10 | CC-DFlash Part 2 Layout Refinement | done | [ui-10-cc-dflash-part2-layout-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-10-cc-dflash-part2-layout-refine.md) |
| UI-11 | CC-DFlash Part 2 Card 2.2/2.3 Alignment | done | [ui-11-cc-dflash-part2-card22-23-align.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-11-cc-dflash-part2-card22-23-align.md) |
| UI-12 | CC-DFlash Part 2 Comparison Cards Scoped | done | [ui-12-cc-dflash-part2-comparison-cards-scoped.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-12-cc-dflash-part2-comparison-cards-scoped.md) |
| UI-13 | CC-DFlash Part 2 Card 2.2 Spacing & Wrap Fix | done | [ui-13-cc-dflash-part2-card22-spacing.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-13-cc-dflash-part2-card22-spacing.md) |
| UI-14 | CC-DFlash Part 3 Layout Refinement | done | [ui-14-cc-dflash-part3-layout-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-14-cc-dflash-part3-layout-refine.md) |
| UI-15 | CC-DFlash Part 3 &amp; 4 Spacing &amp; Layout | done | [ui-15-cc-dflash-part3-4-layout-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-15-cc-dflash-part3-4-layout-refine.md) |
| UI-16 | CC-DFlash Part 3 &amp; 4 Layout Refinement | done | [ui-16-cc-dflash-part3-4-layout-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-16-cc-dflash-part3-4-layout-refine.md) |
| UI-17 | CC-DFlash Part 5 Layout Refinement | done | [ui-17-cc-dflash-part5-layout-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-17-cc-dflash-part5-layout-refine.md) |
| UI-18 | CC-DFlash Part 6 Layout Refinement | done | [ui-18-cc-dflash-part6-layout-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-18-cc-dflash-part6-layout-refine.md) |
| UI-19 | CC-DFlash Part 6 Card 6.3/6.4 Refine | done | [ui-19-cc-dflash-part6-card63-64-refine.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-19-cc-dflash-part6-card63-64-refine.md) |
| UI-20 | CC-DFlash Script Separation | done | [ui-20-cc-dflash-script-separation.md](file:///home/quyseggs/CCDF/docs/reports/extra/ui-20-cc-dflash-script-separation.md) |
