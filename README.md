# Context-Compressed DFlash

This source bundle implements the Rec-T06A3 Direction-B runtime boundary:

- the locked Qwen3-4B NF4 target remains canonical;
- Baseline-AR uses cached autoregressive decoding;
- DFlash-R1 verifies one proposed block with one target forward;
- CC-DFlash-R2 compresses context, then calls the same production DFlash path;
- exact token-for-token equivalence with cached Baseline-AR is **not claimed**;
- structural target-verification correctness is audited;
- quality preservation is evaluated empirically on GSM8K/QMSum.

Quantization is never described as lossless.

## Linked worktree layout

Task worktrees must be direct children of `.worktrees/`:

```text
.worktrees/rec-<id>-ongoing
.worktrees/rec-<id>-closed
```

Create one from the primary repository root:

```bash
python scripts/worktree_manager.py create \
  --id 6a3 \
  --new-branch rec-t06a3-structural \
  --ref HEAD
```

Model checkpoints stay only in the primary repository:

```text
<primary>/models/
```

`configs/reconstruction.yml` uses `@shared/models/...`. In a linked worktree,
`@shared` resolves through Git's common directory to the primary checkout. No
checkpoint is copied into `.worktrees/`.

Inspect path resolution before loading a model:

```bash
cd .worktrees/rec-6a3-ongoing
python -m pip install -e . --no-deps
python -m ccdf paths
```

The reported `shared_root` must be the primary checkout and `models_root` must
be `<primary>/models`.

For non-standard layouts, set:

```bash
export CCDF_SHARED_ROOT=/absolute/path/to/primary/CCDF
```

## Validation

Use the existing project environment containing Torch, Transformers,
bitsandbytes and LLMLingua.

```bash
pytest -q tests/test_rec_t06a3_*.py
python -m compileall -q src scripts
python scripts/rec_t06a3_validate.py --stage n3
python scripts/rec_t06a3_gate.py --stage n3
python scripts/rec_t06a3_validate.py --stage n10
python scripts/rec_t06a3_gate.py --stage n10
```

See [`MANUAL_RUN_REC_T06A3.md`](MANUAL_RUN_REC_T06A3.md) for the full manual
run and result-pack procedure. Do not merge the worktree until its result pack
has been independently audited.
