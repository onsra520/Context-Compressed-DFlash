# Task 37: Baseline-AR Implementation Report

Date: 2026-06-04

## Result

PASS, preliminary.

## Files Changed

- `src/ccdf/benchmark/conditions.py`
- `src/ccdf/benchmark/__init__.py`
- `scripts/run_mvp.py`
- `tests/test_conditions.py`
- `tests/test_compression.py`
- `docs/Roadmap.html`
- `docs/reports/37-baseline-ar-implementation-report.md`

## Condition Definition Summary

`Baseline-AR` is now a first-class MVP condition with:

- compression: `none`
- keep rate: `1.0`
- generation mode: `autoregressive`
- DFlash/speculative decoding: disabled
- draft model usage: disabled
- target model usage: autoregressive generation only

`scripts/run_mvp.py` now treats `Baseline-AR` as a target-only autoregressive condition, so the draft model is not loaded for this condition.

## Difference From Existing Conditions

`Baseline-AR` differs from `DFlash-R1` because it does not use DFlash, the draft model, speculative decoding, acceptance lengths, or tau.

`Baseline-AR` differs from `LLMLingua-AR-R2/R3` because it does not use LLMLingua compression and does not compress or rewrite the prompt.

`Baseline-AR` differs from `CC-LLM-R2/R3` because it uses neither compression nor DFlash speculative decoding.

## Test Coverage Added

Added `tests/test_conditions.py` to verify:

- `Baseline-AR` exists in `MVP_CONDITIONS`
- `Baseline-AR` has no compression
- `Baseline-AR` uses autoregressive generation
- `Baseline-AR` does not use DFlash
- `Baseline-AR` does not require a draft model
- existing MVP condition roles remain distinct

Updated condition helper tests in `tests/test_compression.py` to verify `Baseline-AR` dispatch uses no compression and target-only AR mode.

## Confirmation

No benchmark was run. No model, tokenizer, compressor, CUDA, target weights, or draft weights were loaded. No `results/` artifact was created or modified.

## Limitations

This task only adds implementation and unit-level dispatch coverage. It does not produce a Baseline-AR runtime artifact, speed measurement, correctness measurement, or final benchmark claim.

## Next Step

Task 38 should run the Baseline-AR smoke artifact and audit it against the existing smoke artifact contract.
