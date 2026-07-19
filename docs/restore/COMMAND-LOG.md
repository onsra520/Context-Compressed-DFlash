# REC-2 Restore and Repair Command Log

All Python commands ran after `conda activate CCDF`; all shell commands were issued through `rtk`. No dependency mutation or prohibited Git mutation command was used.

| Stage | Command family | Outcome |
|---|---|---|
| Preflight | path resolution, Git read-only status/diff, archive SHA-256, truth-source manifest checks, model/source identity comparison | PASS; authorized paths resolve to the same workspace; truth sources and archives verified immutable |
| Preflight | `validate-config`, `validate-env`, compileall, pytest | PASS; initial suite 6/6 |
| Preflight | canonical runner `smoke --condition baseline`, then DFlash in a separate process | PASS; GPU ownership clear between processes |
| Live baseline | canonical `run --condition baseline`, GPU cleanup check, canonical `run --condition dflash`, `summarize` | 51 rows each; 45/50 parity; DFlash mean 104.3243 tok/s |
| REC2-R001 | full mock-08 execution-contract helper | First same-process attempt hit the unchanged 6 GiB load gate at 6.031 GiB; helper was corrected to use isolated condition processes, then PASS |
| REC2-R001 | instrumented Baseline and DFlash mock-08 requests | PASS; both raw outputs reproduced and full position/mask/cache/logit/stopping contract captured |
| REC2-R002 Tier A | compileall, pytest, config/environment validation | PASS; final runtime suite 11/11 |
| REC2-R002 Tier B | both model smokes; isolated 1 warm-up + 5 measured mock-08 requests per condition | PASS; mock-08 exact 5/5, deterministic, quality and structural checks pass |
| REC2-R002 Tier C iteration 1 | full Baseline then DFlash canonical matrix | 50/50 parity; DFlash mean 102.1942 tok/s; implementation refined to avoid applying tie-band work to accepted rows |
| REC2-R002 Tier C iteration 2 | unchanged Baseline evidence plus independent DFlash canonical rerun | 50/50 parity; DFlash mean/median 101.0072/109.3424 tok/s; correctness/resource/workload gates pass |
| Performance diagnosis | 2,000-iteration out-of-band CUDA selection microbenchmark | one-row tie band 0.0265 ms versus argmax 0.0083 ms; incremental cost is too small to explain matrix variance |
| Performance diagnosis | 10-second idle `nvidia-smi dmon` sample | persistent 23–28% SM, 8% memory utilization, and PCIe traffic; `kwin_wayland` owns the display GPU |
| Component evidence | explicitly invasive 10-prompt DFlash component profile | diagnostic-only draft mean 147.847 ms and verify/accept mean 497.585 ms per request; excluded from canonical metrics |
| REC2-R003 | final audit after removing root `config-backup.yml` | Initial audit exposed an unconditional debug-file hash; optional identity repair applied; 11/11 tests and final audit PASS |
| Final guards | truth-source manifests, archive SHA-256, dependency snapshot compare, root debug/results scan, checkpoint verification | Recorded in final evidence pack |

Expected non-fatal AutoAWQ deprecation warnings were retained in command output context; no package was changed in response.
