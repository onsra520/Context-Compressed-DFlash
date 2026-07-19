# Four-condition mock10 final report

- Sealed summary SHA-256: `87b7ff73b1e29a75910a29ef69c6f5e649574d71ea87ea1e5a05da1ce64cb4f5`
- Source `config.yml` SHA-256: `e6809adeca0a3be74b091f8750dbd8e5228e244b96139078cac1c18ba4660baa`
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
| baseline-ar | 991.2 | null | null | 0 / 0 | 818.134199999 / 749.633659999 | 1433.359 / 1426.93692 | 2236.6701 / 2176.64238 | 2239.7799 / 2179.60838 | 13.562445478 / 13.5962432542 | 3518361600 / 4645191680 | n/a | n/a | null | null | null |
| cc-dflash-r2 | 665.4 | 0.446620732455 | 0.327658798289 | 127.977049999 / 142.98477 | 529.247350001 / 512.9218 | 339.83325 / 361.07967 | 908.369249999 / 874.07991 | 1015.3558 / 1020.33062 | 55.9374473282 / 55.6311757343 | 4397017600 / 4861198336 | PASS | 8 | 4.52272727273 | 0.538961038961 | 0.258373205742 |
| dflash-r1 | 991.2 | null | null | 0 / 0 | 793.821400001 / 794.166570001 | 339.364899997 / 330.664609999 | 1065.4867 / 1124.92356 | 1069.22835 / 1128.9846 | 56.138064178 / 60.2299501863 | 4814022656 / 5804916736 | PASS | 8 | 5.10526315789 | 0.616541353383 | 0.235294117647 |
| llmlingua-ar-r2 | 665.4 | 0.446620732455 | 0.327658798289 | 127.977049999 / 142.98477 | 514.16225 / 500.7458 | 1502.9935 / 1511.56648 | 1969.69805 / 2012.36138 | 2109.8757 / 2157.71633 | 12.9846429529 / 13.1010808881 | 3166330880 / 3680501760 | n/a | n/a | null | null | null |

## Metric scopes

- Compression latency: synchronized LLMLingua context-compression stage; zero for original-context conditions.
- Prefill/decode/generation latency and decode tok/s: synchronized production generation request.
- Stage-sum E2E: compression plus runtime warm-request latency with separate GPU residency; excludes warmup and model load/unload.
- Validation workload wall clock: 111683.8534 ms for compressor and engine lifecycles, including warmups and 40 measured requests.
- Workload lifecycle-amortized latency: 2792.096335 ms per measured request; not a per-condition request latency.
- Context reduction uses the LLMLingua tokenizer; target-token reduction uses paired Qwen chat-template input counts and is null for original conditions.
