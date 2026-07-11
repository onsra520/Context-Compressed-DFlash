# Rec-T05C - Canonical Runtime Regression Audit

Status: PASS

The unified real runtime completed the canonical n10 regression for GSM8K Baseline/DFlash and QMSum Baseline/DFlash/CC-DFlash. All rows use real local models, real CUDA accounting, real DFlash counters, structured compression, and resolved configuration identity.

Older R1 artifact directories are retained unchanged. They are superseded only as the user-facing runtime evidence because the new CLI and benchmark route through `RuntimeEngine.execute`.
