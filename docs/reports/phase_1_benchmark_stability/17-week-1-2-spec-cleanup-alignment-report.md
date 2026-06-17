# Week 1-2 Spec Cleanup Alignment Report

## Result

PASS

The implementation baseline is ready to move into LLMLingua compressor smoke work. The remaining Week 1-2 items from the CC-DFlash v4.0 roadmap are documentation and specification alignment tasks, not runtime code blockers.

## Current Stage Classification

- Gate 0: complete
- Week 1 engineering baseline: complete
- v4.0 Week 1-2 spec cleanup: still needs documentation alignment
- Week 2 LLMLingua integration: next after cleanup

## Claims To Fix Or Verify

The following claims should be treated as the current authoritative framing:

- VRAM claim must use measured local numbers from the real synthetic probe and baseline path:
  - target load: about `2.49 GiB` allocated
  - draft load: about `3.50 GiB` allocated total
  - generation: about `3.52 GiB` allocated
- DFlash-R1 `n=20` baseline artifact:
  - average tok/s: `17.38`
  - average tau_mean: `2.52`
  - max VRAM allocated: `3.510836124420166 GiB`
  - classify as a smoke-level preliminary baseline, not a final benchmark
- Any K-Flat TPU claim must not be used as a core fact unless it is explicitly sourced. Until then it should be removed from core claims or caveated as unverified external context.
- Missing `flash_attn` is a performance warning, not a correctness blocker.

## Benchmark Augmentation Pipeline Documentation Checklist

Before LLMLingua integration, the spec should explicitly document:

- dataset source
- augmentation source
- filtering rules
- prompt format
- leakage controls
- answer preservation strategy
- token length target
- artifact format

This checklist is the minimum needed so later compression comparisons can be interpreted as a controlled benchmark path instead of a moving target.

## Decision

PASS for moving to LLMLingua compressor smoke.

Reasoning:

- Gate 0 is complete.
- The raw-free DFlash baseline path is complete.
- The DFlash-R1 control artifact exists and has already been audited.
- No runtime code blocker is currently preventing a compressor dry-run or unit smoke pass.
- The remaining v4.0 Week 1-2 work is specification cleanup and claim hygiene.

## Baseline Framing

The current DFlash-R1 result is useful as a control run for Week 2. It should not be described as a paper-level number or final benchmark result because:

- it uses a tiny built-in prompt set
- it uses short generation settings
- it runs on `torch.sdpa` fallback because `flash_attn` is not installed
- it is intentionally smoke-level and repeatable, not a full condition matrix

## Next Step

- Task 18: LLMLingua compressor dry-run and unit smoke
- Keep the DFlash-R1 baseline unchanged so the next comparison uses the same control path and artifact expectations

## Verification

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: PASS
