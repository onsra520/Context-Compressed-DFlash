# Stage 2 freeze before Dataset Pipeline

Freeze date: 2026-07-19. Workspace: `/data/Projects/CCDF-Rework`.

This is an evidence freeze, not a `.worktrees/` snapshot. The user-managed `.worktrees/` tree remains
read-only. Pre-change hashes, config, environment, package versions, and workspace status are stored under
`docs/reviews/9-stage2-freeze-to-qmsum-n10-audit/freeze/` and `environment/`.

## PASS

- CPU/contract tests: 59/59.
- Four-condition mock C1/C2 exact token parity: 10/10.
- C1-C4 canonical mock quality: 10/10 each.
- Safeguard validation: 10/10.
- Compressor CUDA placement and no-fallback contract: PASS.
- Four-condition evidence completeness, uniqueness, order, prompt hashes, metric recomputation, failure
  accounting, and staged memory scope: PASS.
- Four-condition mock DFlash decode mean was approximately 119 tok/s; peak reserved remained approximately
  3.627 GiB.

## FAIL

- Four-condition mock C3/C4 exact generated-token parity: 9/10.
- Known failing sample: `mock-04`, generated index 1, Baseline token 353 versus DFlash token 9.

Under the Stage 3 protocol this exact C3/C4 token parity is diagnostic, not a Dataset Pipeline hard gate,
provided the cached compressed prompt matches and both outputs preserve task quality.

## NOT RUN

- Post-repair canonical C1/C2 guard: 10 prompts x 5 measured repetitions.
- External parity stress suite.
- Dataset Pipeline implementation and its shared-runner regression.
- GSM8K n=10 x C1-C4.
- QMSum n=10 x C1-C4.
- Any full benchmark.

## KNOWN DIAGNOSTIC

- The mock prompts are short. Target-user keep rate was approximately 98.3% and target-full keep rate
  approximately 99.3%; this is evidence that compression ran, not evidence of meaningful compression.
- `mock-04` divergence is a query-shape-sensitive FP16/AWQ SDPA winner change with identical prompt IDs,
  logical prefix, position, cache position, and cache length.
- Block-size, eager, explicit-mask, and FP32 experiments did not yield a generic production-safe exact
  parity repair. The production verifier remains unchanged.

## Deferred issues

- Meaningful compression is evaluated on long QMSum contexts, not on canonical mock prompts.
- C3/C4 token parity remains diagnostic and must record first mismatch, row type, token IDs, decoded outputs,
  and quality preservation.
- `llmlingua==0.2.2` and `tiktoken==0.13.0` are installed but LLMLingua is not declared in
  `pyproject.toml`. Dependency metadata remains a separate change; this task must not mutate the environment.
- Conda metadata may be incomplete for the active prefix. The working interpreter and direct package
  versions are authoritative for this task and are frozen in the review evidence.

