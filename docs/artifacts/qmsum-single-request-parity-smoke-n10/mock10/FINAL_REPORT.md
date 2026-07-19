# Four-condition mock10 final report

- Sealed summary SHA-256: `07792c4171d2387a1b5a94fcdccd5c66a4ace47b13324e9524ce663079a74eb5`
- Source `config.yml` SHA-256: `362fcf0842712e9e1ecce42bedd7776b20ebe80c5e37be1b7f864c85add86bce`
- Active profile: **rec3**
- Overall hard gates: **FAIL**
- Active fixed verification block size: **8**
- Canonical Baseline/DFlash block size: **16**; the active protocol profile does not mutate the canonical benchmark config.
- Condition success: 40/40
- Pair generated-token parity: 19/20
- Exact field quality: 40/40
- Protected question/instruction and retained evidence: 10/10
- Metric validity: PASS (40/40)
- OOM events: 0
- D-Flash peak-reserved VRAM gate: PASS
- Strict format compliance (reported separately, not an exact-quality hard gate): 31/40

## Per-condition metrics

Every p50 and mean below is across measured requests for that condition; warmups and model load/unload are excluded. Weighted D-Flash values use summed counters over the same rows.

| condition | input tokens mean | context reduction mean | target-token reduction mean | compression ms p50 / mean | prefill ms p50 / mean | decode ms p50 / mean | generation ms p50 / mean | stage-sum E2E ms p50 / mean | decode tok/s p50 / mean | peak allocated / reserved bytes | reserved gate | block | weighted tau | weighted acceptance | target forwards/output token |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline-ar | 991.2 | null | null | 0 / 0 | 786.102 / 741.9498 | 2723.2074 / 2653.46742 | 3417.31575 / 3395.49573 | 3422.93265 / 3400.36054 | 7.20308930906 / 7.34256251667 | 3518361600 / 4645191680 | n/a | n/a | null | null | null |
| cc-dflash-r2 | 665.4 | 0.446620732455 | 0.327658798289 | 142.074500001 / 172.8576 | 523.4198 / 497.326000001 | 682.20965 / 704.024189999 | 1254.50725 / 1201.49803 | 1446.6646 / 1379.82845 | 28.8465527236 / 28.4840366287 | 4397017600 / 4861198336 | PASS | 8 | 4.52272727273 | 0.538961038961 | 0.258373205742 |
| dflash-r1 | 991.2 | null | null | 0 / 0 | 815.457749997 / 747.71142 | 636.049700001 / 601.56068 | 1369.94305 / 1349.46735 | 1375.21805 / 1355.9327 | 31.4450979281 / 32.8928412641 | 4814022656 / 5804916736 | PASS | 8 | 5.10526315789 | 0.616541353383 | 0.235294117647 |
| llmlingua-ar-r2 | 665.4 | 0.446620732455 | 0.327658798289 | 142.074500001 / 172.8576 | 506.627750001 / 493.95643 | 2795.1015 / 2751.09318 | 3303.43695 / 3245.13269 | 3500.1627 / 3421.7084 | 7.05561358011 / 7.24082858419 | 3166330880 / 3680501760 | n/a | n/a | null | null | null |

## Metric scopes

- Compression latency: synchronized LLMLingua context-compression stage; zero for original-context conditions.
- Prefill/decode/generation latency and decode tok/s: synchronized production generation request.
- Stage-sum E2E: compression plus runtime warm-request latency with separate GPU residency; excludes warmup and model load/unload.
- Validation workload wall clock: 148804.3258 ms for compressor and engine lifecycles, including warmups and 40 measured requests.
- Workload lifecycle-amortized latency: 3720.108145 ms per measured request; not a per-condition request latency.
- Context reduction uses the LLMLingua tokenizer; target-token reduction uses paired Qwen chat-template input counts and is null for original conditions.
