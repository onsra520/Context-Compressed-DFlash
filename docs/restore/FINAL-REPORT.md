# REC-2 Controlled Restore and Regression Repair

## Outcome

Correctness repair is accepted. The final deterministic canonical matrix achieves exact generated-token parity **50/50**, including `mock-08` **5/5**, with no new mismatch. Quality, structural, memory, policy, metric-validity, and workload gates pass; peak reserved VRAM remains 3.626953 GiB.

The preferred DFlash mean target of 110 tok/s is not met: final mean is 101.0072 tok/s and median is 109.3424 tok/s. This is within the live-baseline guardrail (mean -3.18%, median +0.58%) and above REC-2 historical mean by 5.47%. A persistent external display workload is the blocker: `kwin_wayland` owns the only GPU, and a 10-second idle sample showed 23–28% SM, 8% memory utilization, and continuous PCIe traffic. The historical current-best snapshot recorded 4 MiB GPU use; this task recorded 42–45 MiB. Consequently, the runner's relative REC-2 speedup-equivalence gate remains FAIL even though absolute DFlash throughput exceeds REC-2.

## Root causes and repairs

1. **Mock-08 mismatch:** At generated index 21, Baseline and DFlash have identical prompt IDs, generated prefix, 176-token logical context, selected position/cache-position 175, visible keys 0..175, FP16 CUDA KV state, and stopping contract. Baseline q=1 yields an exact FP16 maximum tie at 37.21875 for tokens 353 and 24768, so argmax selects lower ID 353. DFlash q=16 separates token 24768 from 353 by one representable FP16 step, 37.28125 versus 37.25. REC2-R002 preserves strict proposal acceptance and applies the one-ULP/lower-ID rule only to the correction row at the existing rejection boundary. It performs no replay, oracle call, token-specific handling, or Baseline consultation.
2. **Absolute performance target:** Source, config, models, packages, driver, and deterministic policy match the current-best evidence. The final display-GPU contention is external to the workspace. The added selection operation costs about 0.018 ms per correction row in an out-of-band microbenchmark and is far too small to explain the observed run-level variance.
3. **Final audit cleanup failure:** The current-best runner unconditionally hashed root `config-backup.yml`, while project rules require that debug file to be absent. REC2-R003 records its path/existence and a nullable SHA instead; generation is untouched.

## Final canonical metrics

Canonical values below come from 50 measured requests per condition after one warm-up. Draft and verify component values are from a separate explicitly invasive 10-prompt diagnostic and are not used as canonical performance claims.

| Metric | Baseline-AR | DFlash-R1 |
|---|---:|---:|
| Input tokens, mean / median / min / max / stdev | 137.8 / 132.5 / 102 / 175 / 20.2978 | 137.8 / 132.5 / 102 / 175 / 20.2978 |
| Generated tokens, mean / median / min / max / stdev | 65.7 / 67 / 16 / 97 / 26.0966 | 65.7 / 67 / 16 / 97 / 26.0966 |
| Target prefill mean, ms | 86.4764 | 86.6379 |
| Draft component mean, ms | N/A | 147.8469 diagnostic-only |
| Verify/accept component mean, ms | N/A | 497.5845 diagnostic-only |
| Decode mean, ms | 2108.5425 | 675.4385 |
| Generation mean, ms | 2195.0508 | 762.1469 |
| Warm E2E mean, ms | 2196.3548 | 764.8080 |
| Decode tok/s mean / median / min / max / stdev | 30.9631 / 31.5610 / 27.0128 / 32.5578 / 1.3763 | 101.0072 / 109.3424 / 39.8400 / 143.9852 / 25.9082 |
| Acceptance length mean / median / min / max / stdev | N/A | 4.7226 / 3 / 1 / 16 / 3.6947 |
| Accepted / drafted tokens | N/A | 2,645 / 10,275 |
| Draft acceptance rate | N/A | 0.257421 |
| Tau mean / median / min / max / stdev | N/A | 5.0034 / 5.0625 / 2.8235 / 7.5 / 1.2988 |
| Draft / target verify calls | N/A | 685 / 685 |
| Peak allocated VRAM, GiB | 2.571929 | 3.601094 |
| Peak reserved VRAM, GiB | 2.599609 | 3.626953 |

Decode speedup is 3.2622x; warm E2E latency speedup is 2.8718x.

## Exact parity by prompt and repetition

`P` means complete generated-token ID equality for that repetition.

| Prompt | r0 | r1 | r2 | r3 | r4 | Result |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| mock-01 | P | P | P | P | P | 5/5 |
| mock-02 | P | P | P | P | P | 5/5 |
| mock-03 | P | P | P | P | P | 5/5 |
| mock-04 | P | P | P | P | P | 5/5 |
| mock-05 | P | P | P | P | P | 5/5 |
| mock-06 | P | P | P | P | P | 5/5 |
| mock-07 | P | P | P | P | P | 5/5 |
| mock-08 | P | P | P | P | P | 5/5 |
| mock-09 | P | P | P | P | P | 5/5 |
| mock-10 | P | P | P | P | P | 5/5 |

## Gates

| Gate | Result |
|---|:---:|
| Generated-token parity | PASS |
| Quality | PASS |
| Structural | PASS |
| Memory | PASS |
| Policy | PASS |
| Metric validity | PASS |
| Workload | PASS |
| REC-2 workload-performance equivalence | **FAIL / external GPU contention** |

The last gate compares relative speedups with REC-2. Baseline is 25.51% faster than REC-2 while DFlash is 5.47% faster, so the ratio falls outside its 10% tolerance. This is reported, not relabeled.

## Performance deltas

| Comparison | Baseline mean | DFlash mean | DFlash median | Decode speedup | Warm E2E speedup | Peak reserved |
|---|---:|---:|---:|---:|---:|---:|
| Versus live pre-change baseline | -0.91% | -3.18% | +0.58% | -2.29% | +0.05% | +0.000 GiB |
| Versus current-best historical | +4.16% | -12.64% | -2.27% | -16.14% | -13.46% | +0.000 GiB |
| Versus REC-2 historical | +25.51% | +5.47% | N/A | -15.96% | -18.03% | +0.001953 GiB |

The live baseline is the primary acceptance reference. The 3–5% DFlash mean band was rerun; both final candidates retained 50/50 parity, the accepted median improved, warm latency stayed within 5%, and VRAM was unchanged.

## Restore map summary

- `KEEP_CURRENT`: runtime loading, models, dtypes, SDPA math, prompts, caches, drafting, verification forward, acceptance prefix, rollback, stopping, timing, metrics, VRAM, structure, tests, and Linux process boundaries whose contracts were proven correct.
- `MERGE`: M29 keeps the current zero-product quality wording extension; M30 keeps current-best orchestration and adds optional identity for the removed root debug backup.
- `REWRITE_MINIMAL`: M19 adds correction-row one-ULP deterministic selection.
- `RESTORE_REC2` / `PORT_CURRENT_BEST`: none; their applicable runtime bytes were already present.
- Rejected/reverted changes are enumerated in `REVERTED-AND-REJECTED.md`.

## Filesystem checkpoints

1. `.worktrees/checkpoints/01-live-baseline-before-change.tar.gz`
2. `.worktrees/checkpoints/02-rec2-r001-diagnostic-accepted.tar.gz`
3. `.worktrees/checkpoints/03-rec2-r002-accepted.tar.gz`
4. `.worktrees/checkpoints/04-rec2-r003-accepted.tar.gz`

All have adjacent SHA-256 and JSON metadata. No checkpoint was created for the replaced iteration.

## Scope and integrity confirmation

- Dependencies and environment packages were not changed.
- Workload, prompts, seed, model identities, tokenizer, generation policy, and deterministic SDPA-math were not changed.
- Both truth-source directories and immutable archives were not modified; their manifests/hashes were rechecked.
- No Git restore, checkout, reset, stash, switch, worktree, branch creation, commit, or push was used.
- No root `results/`, `prompt`, `config-backup.yml`, `debug.json`, or `tmp.py` remains.
