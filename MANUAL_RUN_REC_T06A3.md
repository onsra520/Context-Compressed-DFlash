# Rec-T06A3 manual validation

## 1. Apply this source bundle in a linked worktree

From the primary repository root:

```bash
python scripts/worktree_manager.py create \
  --id 6a3 \
  --new-branch rec-t06a3-structural \
  --ref HEAD
```

The path is:

```text
.worktrees/rec-6a3-ongoing
```

The configuration uses `@shared/models/...`; linked worktrees load checkpoints
from the primary repository's `models/` directory. Do not copy checkpoints.

Confirm:

```bash
cd .worktrees/rec-6a3-ongoing
python -m ccdf paths
```

`shared_root` must be the primary repository and `models_root` must point to
`<primary>/models`.

## 2. Install source in the existing environment

```bash
python -m pip install -e . --no-deps
```

Use the already validated project environment for Torch, Transformers,
bitsandbytes and LLMLingua.

## 3. Fast source tests

```bash
pytest -q tests/test_rec_t06a3_*.py
python -m compileall -q src scripts
```

## 4. One real prompt per condition

```bash
python -m ccdf run --condition baseline-ar \
  --prompt "How many positive divisors does 196 have?" --format json \
  > results/Rec-T06A3/baseline_real.json

python -m ccdf run --condition dflash-r1 \
  --prompt "How many positive divisors does 196 have?" --format json \
  > results/Rec-T06A3/dflash_real.json
```

Check DFlash JSON:

```text
target_block_verification_calls == verification_calls
target_single_token_fallback_calls == 0
target_hidden_refresh_calls == 0
total_target_forward_calls == target_prefill_calls + target_block_verification_calls
output_tokens == target_seed_tokens + sum(emitted_acceptance_lengths)
all structural_audit[*].structural_pass == true
exact_cached_ar_token_equivalence == NOT_CLAIMED
```

## 5. Coupled n3 gate

```bash
python scripts/rec_t06a3_validate.py --stage n3
python scripts/rec_t06a3_gate.py --stage n3
```

Do not continue if:

- any structural audit fails;
- production DFlash uses a per-proposal target call;
- GSM8K has no completed final answer;
- QMSum loops or echoes instructions;
- every row hits the token cap.

## 6. Coupled n10 gate

```bash
python scripts/rec_t06a3_validate.py --stage n10
python scripts/rec_t06a3_gate.py --stage n10
```

Required review boundary:

- GSM8K cap hits: 0;
- GSM8K invalid/repetition: 0;
- DFlash strict correctness no more than one row below Baseline;
- QMSum repetition/instruction echo/empty: 0;
- QMSum semantic correctness remains `NOT_CLAIMED`;
- all DFlash structural/accounting invariants pass.

The n10 stage intentionally runs Baseline-AR and DFlash-R1 only. The n3 stage
contains the CC-DFlash integration/bypass smoke. CC-DFlash n10, canonical
process isolation, and final timing belong to Rec-T06B/D after this gate.

## 7. Return evidence

Package only results and source identity:

```bash
tar -czf rec-t06a3-result-pack.tar.gz \
  results/Rec-T06A3 \
  configs/reconstruction.yml \
  MANUAL_RUN_REC_T06A3.md
```

Do not merge until the result pack is independently audited.

After acceptance, move the worktree label:

```bash
cd <primary-repository-root>
python scripts/worktree_manager.py close --id 6a3
```
