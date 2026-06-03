# Week 1 Closeout Report

## Result

PASS

Week 1 of the CCDF DFlash baseline path is complete. Gate 0 passed, the raw-free DFlash split is in place, and the DFlash-R1 no-compression baseline path is proven end to end. The current speed number is still smoke-level, not a final benchmark claim.

## Completed Milestones

- Rules and report numbering were normalized.
- The raw-free DFlash split was implemented.
- The raw-free split audit passed.
- Local model downloads were validated with the real synthetic probe.
- The real synthetic probe / Gate 0 passed.
- The DFlash-R1 smoke benchmark passed.
- Repeatable JSONL artifact output was added.
- The `n=20` baseline run passed.
- The `n=20` artifact audit passed.

## Evidence Table

| Report | Result | Key Evidence |
| --- | --- | --- |
| [10-dflash-raw-free-split-audit-report.md](/home/quyseggs/CCDF/docs/reports/10-dflash-raw-free-split-audit-report.md) | PASS | Raw-free split validated; production `ccdf.dflash` no longer depended on raw modules. |
| [11-real-synthetic-probe-implementation-report.md](/home/quyseggs/CCDF/docs/reports/11-real-synthetic-probe-implementation-report.md) | PASS | Dry-run passed and real probe passed with local Qwen paths. |
| [12-dflash-r1-baseline-smoke-report.md](/home/quyseggs/CCDF/docs/reports/12-dflash-r1-baseline-smoke-report.md) | PASS | Smoke baseline ran on `torch.sdpa` fallback with local models. |
| [13-dflash-r1-repeatable-artifact-report.md](/home/quyseggs/CCDF/docs/reports/13-dflash-r1-repeatable-artifact-report.md) | PASS | JSONL artifact output was added and confirmed repeatable. |
| [14-dflash-r1-n20-baseline-report.md](/home/quyseggs/CCDF/docs/reports/14-dflash-r1-n20-baseline-report.md) | PASS | `n=20` short baseline completed with artifact output. |
| [15-dflash-r1-n20-baseline-audit-report.md](/home/quyseggs/CCDF/docs/reports/15-dflash-r1-n20-baseline-audit-report.md) | PASS | Artifact schema validated and metrics recomputed from JSONL. |

## Measured Baseline

Artifact: `results/dflash_r1_n20.jsonl`

- rows: 20
- condition: `DFlash-R1`
- average tok/s: 17.38
- average tau_mean: 2.52
- max VRAM allocated: 3.510836124420166 GiB
- max VRAM reserved: 3.619140625 GiB
- backend warning: `torch.sdpa` fallback because `flash_attn` is not installed

This baseline is reproducible and machine-readable. It is still a smoke-level preliminary baseline, not a final benchmark result.

## Limitations

- smoke-level baseline only
- tiny built-in prompt set
- short generation
- no `flash_attn`
- no LLMLingua or compression yet
- no dataset benchmark yet
- no full condition matrix

## Week 1 Decision

PASS for the Week 1 baseline path.

This is enough to close Week 1, but it is not a final benchmark claim. The measured tok/s is useful as a control point for the next stage, not as a paper-level speed number.

## Next Roadmap

- `17` LLMLingua compressor dry-run and unit smoke
- `18` CC-LLM-R2/R3 smoke comparison using the same JSONL schema
- `19` LLMLingua-AR baseline
- `20` small condition matrix
- `flash_attn` optimization deferred until the baseline comparison is stable

## Verification

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: PASS

## Git Hygiene

`README.md` and `config.yml` may already have pre-existing modifications in the worktree. This closeout report does not claim to change them unless a separate verification explicitly shows that.
