# Accepted Filesystem Checkpoints

| Checkpoint | Change | Result |
|---|---|---|
| `01-live-baseline-before-change.tar.gz` | LIVE-BASELINE | Immutable pre-change evidence only; 45/50 parity, DFlash 104.3243 tok/s |
| `02-rec2-r001-diagnostic-accepted.tar.gz` | REC2-R001 | Full mock-08 execution-contract diagnostic accepted; production runtime unchanged |
| `03-rec2-r002-accepted.tar.gz` | REC2-R002 | Correction-row one-ULP verifier selection accepted; 50/50 parity and mock-08 5/5 |
| `04-rec2-r003-accepted.tar.gz` | REC2-R003 | Final audit accepts absent root debug backup; runtime unchanged |

Each archive has adjacent `.sha256` and `.json` metadata under `.worktrees/checkpoints/`. No checkpoint was created for the replaced REC2-R002 iteration 1 implementation.
