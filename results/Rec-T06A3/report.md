# Rec-T06A3 final validation report

## Claim boundary

- Target: locked Qwen3-4B NF4 (`bitsandbytes-nf4-bfloat16`).
- Baseline: cached autoregressive decoding.
- DFlash: one target verification forward per proposed draft block.
- Exact cached-AR token equivalence: **NOT_CLAIMED**.
- Structural target-verification correctness: **REQUIRED_AND_AUDITED**.
- GSM8K quality preservation: **EMPIRICALLY_EVALUATED**.
- QMSum semantic correctness: **NOT_CLAIMED**.
- Quantization is never described as lossless.

## Environment and provenance

- Worktree: `.worktrees/rec-6a3-ongoing` on `rec-t06a3-structural`.
- Environment: root `.venv`; `PYTHONPATH=$PWD/src`.
- Config: `configs/reconstruction.yml`, version
  `rec-t06a3.reconstruction.v2`.
- Frozen GSM8K fixture hash:
  `45d50bac9cd425b509bdcda119c5b7ce295e1acac655ffec1eb0ca3ab21240b7`.
- Frozen QMSum fixture hash:
  `429a8aac613a9def9e81761d510df68a2c38d6e8fb097b8ffb1b2cfb11160152`.

## Output-contract repair

`Final answer: <number>` is accepted at line start or after a completed
sentence boundary, but not as incidental ordinary prose. Raw output is kept;
an incorrect parsed answer remains `wrong_numeric`.

The four targeted GSM8K diagnostic rows (fixtures 000007 and 000008, each
under Baseline-AR and DFlash-R1) had zero caps, completed output contracts,
and validated numeric answers. Their numeric values were intentionally not
promoted: each remains `wrong_numeric` against its frozen reference.

## Validation results

Focused Rec-T06A3 tests: `17 passed`.

Full test suite: `66 passed in 48.51s`.

`n3` gate: `PASS`; no GSM8K/QMSum cap, repetition, instruction-echo, runtime,
or structural failures. Observed exact-token match rate: `1.0` (evidence only,
not a claim).

`n10` gate: `PASS`.

- GSM8K: Baseline `7/10` strict correct; DFlash `7/10`; zero cap hits and all
  Baseline/DFlash rows completed the final-answer contract.
- QMSum: zero cap hits per condition; zero repetition, instruction echo, and
  invalid runtime rows; semantic correctness remains `NOT_CLAIMED`.
- Observed exact-token match rate: `0.85` (evidence only, not a claim).
- DFlash rows passed acceptance-prefix, correction-index, cache progression,
  seed-aware emitted accounting, and no-hidden-target-call checks. Production
  oracle calls and per-proposal target calls are zero. Real target-forward
  savings were demonstrated: n10 GSM8K DFlash used
  `0.21721311475409835` target forwards per output token, versus Baseline 1.0.

The condition workers were process-isolated to avoid transient GPU allocator
contention while preserving the same frozen fixtures, configuration, row
contract, and gate checks.

No n30, Rec-T06B/C/D, or push occurred.
