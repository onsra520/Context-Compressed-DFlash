# Rec-T06A3 Direction-B source bundle

## Base source

The bundle was reconstructed from the uploaded current-source review whose
recorded source HEAD was:

```text
676715b1dbdfbf9faa861cfcbf0ec4e9bb491b1b
```

It is intended to be applied and tested in a linked task worktree, not merged
straight into the primary branch.

## Approved boundary

```text
target_model: locked Qwen3-4B NF4
baseline_ar: standard cached autoregressive decoding
dflash_r1: efficient target-verified block decoding
cc_dflash_r2: compression followed by the same DFlash-R1 executor
exact_cached_ar_token_equivalence: NOT_CLAIMED
target_verified_block_decoding: REQUIRED_AND_AUDITED
quality_preservation_vs_baseline: EMPIRICALLY_EVALUATED
quantization_lossless: NEVER_CLAIMED
upstream_equivalence: NOT_CLAIMED
```

## Worktree and model-path behavior

- Allowed worktree paths:
  - `.worktrees/rec-<id>-ongoing`
  - `.worktrees/rec-<id>-closed`
- `scripts/worktree_manager.py` creates and moves those worktrees.
- `@shared/models/...` resolves to the primary Git checkout through the Git
  common directory.
- Checkpoints are never copied into `.worktrees/`.
- `CCDF_SHARED_ROOT` is available for a non-standard Git layout.

## Main source changes

- Split diagnostic full-prefix oracle from production target execution.
- Restored cached Baseline-AR.
- Added efficient one-target-forward-per-block DFlash verifier.
- Added structural block audit, seed-aware emitted accounting, and real target
  forward counters.
- Added dataset-aware prompt construction and shared Qwen chat-template
  encoding with `enable_thinking=false` enforcement.
- Added GSM8K final-answer stopping and QMSum output-health checks.
- Added shared model/worktree path resolution.
- Changed configuration to subset-specific fixture/manifest identities.
- Added truthful generation-only versus compression-inclusive warm timing
  fields. Final canonical timing remains deferred to Rec-T06B.
- Added validation benchmark artifacts and a model-free gate checker.
- Kept the old Rec-T03B/Rec-T04B direct benchmark modules as legacy only; new
  validation uses `ccdf.benchmark.workflow` and `RuntimeEngine`.

## Local checks performed in the build environment

```text
python -m compileall -q src scripts tests   PASS
python -m pytest -q                        36 passed, 25 skipped
pytest -q tests/test_rec_t06a3_*.py         13 passed
PYTHONPATH=src python -m ccdf --help        PASS
PYTHONPATH=src python -m ccdf paths         PASS
```

The 25 skips require resources intentionally absent from the uploaded source
review: archived raw datasets, frozen fixtures/manifests, Transformers, and
local model checkpoints.

## Not claimed by this source-only build

No real checkpoint or GPU execution was possible in the build environment.
Therefore this bundle does **not** claim that:

- Rec-T06A3 n3 or n10 has passed;
- output quality is preserved;
- target-forward savings occur on the real checkpoint;
- CC-DFlash latency is improved;
- QMSum semantic correctness is established;
- the source is ready to merge.

Those decisions require the manual result pack from the user's project
machine.

## Manual validation order

```bash
pytest -q tests/test_rec_t06a3_*.py
python -m compileall -q src scripts
python scripts/rec_t06a3_validate.py --stage n3
python scripts/rec_t06a3_gate.py --stage n3
python scripts/rec_t06a3_validate.py --stage n10
python scripts/rec_t06a3_gate.py --stage n10
```

Do not merge unless the result pack is independently audited.
