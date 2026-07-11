# Rec-T03A - Baseline-AR and DFlash-R1 Reconstruction

Status: PASS

## Scope

Rec-T03A reconstructed the Baseline-AR and DFlash-R1 runtime surface using locked local models. It did not restore old `run_mvp.py`, old benchmark glue, old dataset glue, old timing wrappers, or archive runtime imports.

The DFlash implementation was selectively reconstructed from the local drafter model source under `models/drafter/z-lab--Qwen3-4B-DFlash-b16/`, not from `.archives/`.

## Implementation

- Added `src/ccdf/inference/` for model registry, target loading, common generation, Baseline-AR, and DFlash-R1 wrappers.
- Added `src/ccdf/dflash/` for audited utility functions, config/attention checks, local drafter loading, model contract metadata, and instrumented DFlash generation.
- Added `tests/test_rec_t03a_runtime_contract.py` for config compatibility, target layer IDs, greedy sampling, prefix acceptance, counters, tokenizer local loading, and no archive imports.

## Model Contract

Target:

- Path: `models/target/unsloth--Qwen3-4B-bnb-4bit`
- Model: Qwen3-4B
- Quantization: BitsAndBytes NF4 4-bit
- Revision: `cad0bedfdd862093a12af478cb974ab2addd0e0a`
- Device in smoke: `cuda:0`

Drafter:

- Path: `models/drafter/z-lab--Qwen3-4B-DFlash-b16`
- Model: Qwen3-4B DFlash drafter
- Revision: `b74e3a329c4d963783143b1e970d95b002be72bd`
- Block size: `16`
- Target layer IDs: `[1, 9, 17, 25, 33]`
- Device in smoke: `cuda:0`

Tokenizer source:

- Target model tokenizer
- EOS token: `151645`

## Runtime Smokes

Baseline single prompt:

- Prompt: `What is 2+2? Answer:`
- Output: ` 4`
- Output tokens: `2`
- Device: `cuda:0`
- Result: PASS

DFlash single prompt:

- Prompt: `What is 2+2? Answer:`
- Output: ` 4`
- Output tokens: `2`
- Acceptance lengths: `[3]`
- Verification calls: `1`
- Tau tokens advanced per verification: `3.0`
- Result: PASS

Fixture smokes:

- GSM8K n10 first fixture: Baseline and DFlash each produced 1 token; DFlash invariant passed.
- QMSum n10 first fixture: Baseline and DFlash each produced 1 token; DFlash invariant passed.

Determinism:

- Baseline temperature-0 repeated output IDs matched.
- DFlash temperature-0 repeated output IDs matched.

These are smoke checks only. They are not benchmark latency claims and are not used as Rec-T03B matrix results.

## DFlash Counters

The reconstructed DFlash wrapper returns:

- `acceptance_lengths`
- `verification_calls`
- `draft_tokens_proposed`
- `accepted_draft_tokens`
- `rollback_tokens`
- tau counters through `metric_counters`

Invariant evidence is in `results/Rec-T03A/dflash_invariant_tests.json`.

## Checks

Commands:

```bash
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q tests/test_rec_t03a_runtime_contract.py
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python <runtime_smoke_script>
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python <fixture_smoke_script>
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python <determinism_script>
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q
```

Results:

- Rec-T03A focused tests: `7 passed`
- Full available test suite: `32 passed`
- Baseline smoke: PASS
- DFlash smoke: PASS
- Fixture smokes: PASS
- Determinism smoke: PASS

## Gate Decision

PASS.

Gate evidence:

- Target and drafter local-only loads pass.
- Baseline single prompt pass.
- DFlash single prompt pass.
- GSM8K and QMSum fixture smokes pass.
- DFlash invariant tests pass.
- Temperature-0 determinism passes.
- Benchmark mode uses no component profiler.
- Source modules have an audit trail in `archive_module_audit.csv`.
- Runtime does not import from `.archives/`.
- Old benchmark/dataset glue is not used.

Known limitation before Rec-T03B:

- Runtime smokes used tiny generation caps to prove correctness and compatibility. Rec-T03B remains responsible for the controlled n=10 benchmark matrix and performance anomaly classification.
