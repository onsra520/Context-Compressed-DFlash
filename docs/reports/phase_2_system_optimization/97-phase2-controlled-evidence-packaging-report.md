# Task 97 — Phase 2 Controlled Evidence Packaging

## 1. Purpose

- Package the controlled Phase 2 evidence after Task96.
- Update the future roadmap plan after the bounded `n=30` `max_new_tokens=256` result.
- Repair the `docs/Roadmap.html` status-column UI overlap/clipping issue.
- This task is packaging, planning, and UI-only. No new benchmark was run.

## 2. Evidence Chain

- **T93** proved that the light compressor is integrated through the real CC-DFlash runner. In the tiny `n=3` smoke, light reduced `t_compress_ms` versus large, but quality was still unaudited.
- **T94** ran the first controlled `n=10` comparison at `max_new_tokens=128`. Light was faster but weaker on the bounded GSM8K numeric proxy: large `6/10` versus light `2/10`.
- **T95A** audited the failure rows and found `large_correct_light_wrong` cases with cap/truncation and format sensitivity rather than generic corruption.
- **T95B** calibrated the deterministic proxy and showed the gap remained under the calibrated strict policy: large `5/10`, light `2/10`. Proxy uncertainty did not explain the gap; output-cap pressure became the main triage target.
- **T95C** completed the static cap audit, but the bounded `max_new_tokens=256` rerun stayed GPU-blocked and remained a historical `PARTIAL` record.
- **T95C-R** resumed the bounded mnt256 run after GPU recovery. On seed42, large and light both reached calibrated strict `8/10` and cap-limited `1/10`; light remained much lower in `t_compress_ms` and lower in e2e time.
- **T95D** confirmed the bounded mnt256 behavior on a different seed43 sample with `0/10` fixture overlap against seed42. Seed43 was large strict `7/10` and light strict `8/10`; cap-limited counts were large `3/10` and light `2/10`.
- **T96** expanded the original seed42 path to a controlled `n=30` comparison and confirmed that light matched large on the calibrated strict proxy while preserving lower compression overhead and lower e2e time.

## 3. Main Controlled Result

Task96 `CC-DFlash-R2`, `gsm8k_short`, seed `42`, `n=30`, `max_new_tokens=256`:

| Profile | Calibrated strict | Cap-limited incomplete | Avg `t_compress_ms` | Avg e2e | Avg `R_actual` |
| --- | ---: | ---: | ---: | ---: | ---: |
| large | `22/30` | `5/30` | `1201.58` | `3.97s` | `2.67` |
| light | `22/30` | `5/30` | `363.46` | `3.23s` | `2.00` |

Light-vs-large deltas:

- calibrated strict: `0`
- cap-limited incomplete: `0`
- `t_compress_ms`: `-838.12ms`
- e2e: `-0.74s`
- `R_actual`: `-0.67`

## 4. Interpretation

- The light compressor is promising under controlled GSM8K mnt256.
- The earlier mnt128 quality drop was largely cap/tail-policy driven rather than explained by proxy uncertainty.
- Light trades less aggressive compression for lower compression overhead and lower e2e time in the bounded controlled setup.
- This supports the current Phase 2 direction, but it does not finish the full benchmark story.
- The evidence remains bounded deterministic proxy evidence only.

## 5. Roadmap Plan Update

Future Phase 2 tasks were updated as follows:

- **T98 — Optional n100 Go/No-Go Decision**: `PLANNED / GATED`
- **T99 — Light Compressor GPU Placement Feasibility**: `PLANNED / GATED`
- **T100 — Phase 2 Optimization Summary**: `PLANNED`
- **T101 — Final Claim Boundary Audit**: `PLANNED`
- **T102 — Final Report Integration**: `PLANNED`

Important plan constraints preserved:

- T98 is a decision gate only, not automatic authorization.
- T99 is feasibility work only, not a default GPU switch.
- T99 stays small and gated; start with `n=3` or `n=10`, not `n=30`.
- `n=100` remains blocked unless explicitly approved later.

## 6. Roadmap UI Fix

The roadmap table status column had long labels crowding or clipping against the right border. The fix was layout-only:

- added explicit width control for the status columns in the gate, current-status, main-task, and auxiliary-task tables
- ensured the status cells use `box-sizing: border-box`
- increased right padding in those cells
- enabled wrapping with `overflow-wrap: anywhere` and `word-break: break-word`
- kept the existing status colors and content semantics unchanged

This was a UI/layout repair only. No task meanings, claim policy, or benchmark semantics were changed by the CSS update.

## 7. Claim Boundary

Allowed bounded claims:

- light compressor is integrated through the real CC-DFlash runner
- in controlled GSM8K mnt256 comparisons, light matched large on calibrated strict proxy at `n=30`
- light reduced average `t_compress_ms` versus large in the controlled `n=30` mnt256 setup
- light reduced average e2e time versus large in the controlled `n=30` mnt256 setup
- mnt256 reduced cap-limited incompleteness relative to mnt128
- light compresses less aggressively than large: `R_actual` about `2.00` versus `2.67`

Blocked claims:

- no final speedup claim
- no final quality claim
- no deployment or 8GB readiness claim
- no QMSum semantic correctness claim
- no full benchmark claim
- no automatic n100 authorization
- no claim that GPU compressor placement is better yet

## 8. Recommendation

- Next default step: **T98 optional n100 go/no-go decision**
- Alternate bounded step: **T99 light compressor GPU placement feasibility**
- No automatic `n=100`
- Any GPU placement task must stay small and gated

## 9. Artifacts

- `results/phase_2_system_optimization/final_reruns/task97_phase2_controlled_evidence_packaging/task97_phase2_evidence_summary.json`
- `results/phase_2_system_optimization/final_reruns/task97_phase2_controlled_evidence_packaging/task97_phase2_evidence_table.csv`
- `results/phase_2_system_optimization/final_reruns/task97_phase2_controlled_evidence_packaging/task97_claim_boundary.json`
- `results/phase_2_system_optimization/final_reruns/task97_phase2_controlled_evidence_packaging/task97_next_step_recommendation.json`
- `results/phase_2_system_optimization/final_reruns/task97_phase2_controlled_evidence_packaging/task97_roadmap_plan_update.json`

## 10. Validation Scope

Task97 validation covers:

- static Python compile sanity
- Task97 packaging script help/runtime
- Task97 packaging test
- HTML parse sanity for `docs/Roadmap.html` and `docs/CC-DFlash-Overview.html`
- Markdown fence balance check for this report

No benchmark, model inference, or GPU execution belongs to this task.
