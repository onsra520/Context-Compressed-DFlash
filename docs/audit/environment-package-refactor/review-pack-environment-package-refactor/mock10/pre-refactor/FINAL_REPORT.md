# REC-3 four-condition mock10 final report

- Sealed summary SHA-256: `abb2f906e4ae6bdb6f742933438e75716694d02c6068e4bbc9f9657207324654`
- Source `config.yml` SHA-256: `4fba4138ad26104ca89a37c0a90c997a73a6332522c54ba65bd83296636cd05e`
- Active profile: **rec3**
- Overall hard gates: **PASS**
- Active fixed verification block size: **8**
- Canonical Baseline/DFlash block size: **16**; the active protocol profile does not mutate the canonical benchmark config.
- Condition success: 40/40
- Pair generated-token parity: 20/20
- Exact field quality: 40/40
- Protected question/instruction and retained evidence: 10/10
- Metric validity: PASS (40/40)
- OOM events: 0
- D-Flash peak-reserved VRAM gate: PASS
- Strict format compliance (reported separately, not an exact-quality hard gate): 36/40

## Per-condition metrics

Every p50 and mean below is across measured requests for that condition; warmups and model load/unload are excluded. Weighted D-Flash values use summed counters over the same rows.

| condition | input tokens mean | context reduction mean | target-token reduction mean | compression ms p50 / mean | prefill ms p50 / mean | decode ms p50 / mean | generation ms p50 / mean | stage-sum E2E ms p50 / mean | decode tok/s p50 / mean | peak allocated / reserved bytes | reserved gate | block | weighted tau | weighted acceptance | target forwards/output token |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline-ar | 991.2 | null | null | 0 / 0 | 765.7435915 / 730.4496471 | 890.405179 / 943.7914597 | 1654.2855675 / 1674.2903405 | 1657.03936 / 1677.2950362 | 21.3462056805 / 21.1312189678 | 3493476352 / 4609540096 | n/a | n/a | null | null | null |
| cc-dflash-r2 | 634 | 0.475272117338 | 0.35915027869 | 149.9434005 / 144.4686314 | 511.458129 / 481.0416818 | 235.7749765 / 231.6122683 | 710.752668 / 712.7358568 | 863.114988 / 860.8207242 | 82.9188814155 / 87.393415386 | 4333769728 / 4787798016 | PASS | 8 | 4.9 | 0.585714285714 | 0.242718446602 |
| dflash-r1 | 991.2 | null | null | 0 / 0 | 797.9744935 / 738.4370024 | 290.695154 / 274.5878453 | 1064.9999935 / 1013.1267734 | 1070.8357565 / 1017.9847462 | 68.4709055405 / 72.4098665958 | 4788856832 / 5781848064 | PASS | 8 | 5.10526315789 | 0.616541353383 | 0.235294117647 |
| llmlingua-ar-r2 | 634 | 0.475272117338 | 0.35915027869 | 149.9434005 / 144.4686314 | 489.337929 / 474.2929649 | 801.95732 / 795.5588567 | 1257.6104195 / 1269.9260537 | 1408.680096 / 1417.2615928 | 24.8806388972 / 24.6572387434 | 3103297536 / 3605004288 | n/a | n/a | null | null | null |

## Metric scopes

- Compression latency: synchronized LLMLingua context-compression stage; zero for original-context conditions.
- Prefill/decode/generation latency and decode tok/s: synchronized production generation request.
- Stage-sum E2E: compression plus runtime warm-request latency with separate GPU residency; excludes warmup and model load/unload.
- Validation workload wall clock: 62671.197146 ms for compressor and engine lifecycles, including warmups and 40 measured requests.
- Workload lifecycle-amortized latency: 1566.77992865 ms per measured request; not a per-condition request latency.
- Context reduction uses the LLMLingua tokenizer; target-token reduction uses paired Qwen chat-template input counts and is null for original conditions.
