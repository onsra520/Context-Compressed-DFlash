# Task108A — QMSum Targeted Recheck / Fix Feasibility

## Purpose

Task108A evaluates whether a narrow QMSum targeted recheck or fix is justified after the GSM8K optimization branch. This task is static analysis only: no benchmark, model inference, QMSum rerun, n100, full matrix, human scoring, or LLM judge was run.

## Inputs

- T103D QMSum deep-fix closure decision and human-review summary.
- T105B controlled QMSum runtime matrix.
- T107B GSM8K optional policy refinement result.
- Existing QMSum residual-risk reports from T102/T103.

## QMSum Status Snapshot

T105B remains the current controlled QMSum runtime reference:

| Condition | Rows | Avg e2e (s) | Empty/malformed | Cap-limited/incomplete | Low reference overlap | Max reserved VRAM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 30 | 3.770054 | 0 | 0 | 15/30 | 4.308594 GiB |
| DFlash-R1 | 30 | 5.188113 | 0 | 0 | 15/30 | 5.361328 GiB |
| CC-DFlash-R2 Light GPU | 30 | 5.235310 | 0 | 0 | 14/30 | 5.414062 GiB |

The QMSum Light GPU path completed all rows without cap-limited or malformed output, but it did not beat Baseline-AR or DFlash-R1 on average e2e time. Therefore T105B supports bounded QMSum runtime/completion evidence only, not a faster-than-reference QMSum claim.

## Residual Risk Evidence

T103D closed the QMSum deep-fix branch with persistent residual risk:

- QMSum deep-fix status: `CLOSED_WITH_PERSISTENT_RESIDUAL_RISK`.
- QMSum semantic correctness: `NOT_CLAIMED`.
- QMSum quality risk eliminated: `NO`.
- Fixed six-row human review labels: `0` correct-supported, `2` partially-correct/incomplete, `1` unsupported/wrong, and `3` cannot-determine from available context.

This means the remaining issue is not an obvious output-shape or cap problem. It is a semantic/reference/evidence-grounding risk that prior targeted remediation, evidence selection, Baseline-AR mini-check, and human review did not close.

## Fix Candidate Matrix

| Candidate | Feasibility | Recommendation | Rationale |
| --- | --- | --- | --- |
| No rerun; keep caveat | Supported | Primary | Existing T103D/T105B evidence already supports closure with mandatory QMSum caveat. |
| Small targeted QMSum policy recheck | Weak / not justified | Do not run by default | No clear mechanical target remains; prior target-row remediation did not close risk. |
| Reference-overlap proxy repair only | Static optional only | Not required for closure | Can refine wording, but cannot prove semantic correctness. |
| Human-review expansion | Reserved / explicit approval | Optional only | Would be a new human-review scope. |
| LLM judge review | Reserved / explicit approval | Not default | Out of scope for T108A and prior closure rules. |
| Query-aware compression experiment | Reserved / not default | Defer | Deeper algorithmic work, not closure-pack requirement. |
| QMSum full rerun or n100 | Blocked | Do not run | Outside T108A scope and not justified by current evidence. |

## T108B Recommendation

T108B is not justified by default. The recommended path is `NO_RERUN_KEEP_CAVEAT` and proceed to T109 closure packaging.

A future T108B would require explicit approval and should remain narrow. It should not run QMSum n100, a full matrix, Large CPU, DFlash-R1, LLMLingua-AR-R2, query-aware compression, or any default switch unless a separate task explicitly authorizes that scope.

## Claim Update

Allowed wording:

- QMSum remains runtime/feasibility and residual-risk evidence.
- T105B supports bounded QMSum output-completion/runtime observations for the controlled n30 matrix.
- T103D supports preserving a mandatory QMSum residual-risk caveat.
- T108A supports proceeding to closure packaging without a default QMSum rerun.

Blocked wording:

- QMSum semantic correctness is proven.
- QMSum residual risk is eliminated.
- CC-DFlash wins QMSum runtime against Baseline-AR or DFlash-R1.
- QMSum n100 or full rerun is authorized automatically.
- Query-aware compression is ready or default.
- A targeted T108B rerun is required by the current evidence.
- The optimized Light GPU path is a default/global winner.

## Decision

`PASS_WITH_CAVEAT`

T108A completes the QMSum recheck/fix feasibility audit and finds no justified default T108B. QMSum remains caveated runtime/feasibility evidence with persistent residual semantic risk.

## Next Task

Proceed to T109 — Phase 2 Optimization Closure Pack. T103B and broader QMSum semantic review remain deferred/reserved unless explicitly approved later.
