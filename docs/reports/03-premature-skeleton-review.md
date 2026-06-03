# Premature Skeleton Review

Date: 2026-06-03

## Findings

- Real Gate 0 was not run. The current probe only checks that `config.yml` can be loaded and that the lightweight package imports resolve.
- No target or draft model was loaded during the skeleton validation pass.
- No `H_target` dtype, norm, or NaN check was performed.
- No acceptance length or `τ` measurement was collected from speculative decoding.
- `pytest` currently validates skeleton behavior only, not upstream DFlash execution.

## Scope Notes

- The upstream DFlash implementation has intentionally not been copied into the new module split yet.
- Reference files such as `src/ccdf/model_raw.py` and `src/ccdf/benchmark/benchmark_raw.py` remain untouched.

## Validation Context

- `python -m compileall src` passes for the current skeleton.
- `pytest` passes for the current skeleton-only test coverage.