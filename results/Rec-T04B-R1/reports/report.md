# Rec-T04B-R1 - Canonical CC-DFlash Audit n=30

Status: PASS_WITH_SHORT_CONTEXT_BYPASS

This canonical rerun completed `180/180` isolated rows using the resolved configuration: GSM8K uses `256` new tokens and QMSum uses `384`. Prompt fairness, token scope, DFlash invariants, and process isolation passed. QMSum semantic correctness remains `NOT_CLAIMED`.

All GSM8K rows cap-hit. QMSum Baseline and DFlash rows cap-hit; CC-DFlash had `29/30` cap hits. This remains a workload-limited quality boundary even though the configuration is canonical.

GSM8K DFlash mean E2E was `6533.469 ms` versus Baseline `7861.648 ms`; CC-DFlash remained an explicit short-context bypass (`6310.498 ms` generation E2E, `0.010 ms` mean compression). QMSum DFlash mean E2E was `7976.913 ms` versus Baseline `12493.046 ms`; CC-DFlash generation E2E was `8646.532 ms` with `2769.165 ms` mean compression cost. Compression reduced QMSum target prefill but its net latency interpretation must include that cost.
