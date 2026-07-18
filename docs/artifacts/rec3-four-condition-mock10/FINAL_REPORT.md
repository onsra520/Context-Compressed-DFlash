# Four-condition mock10 final report

- Sealed summary SHA-256: `ef8911d8f84c23fef9485750f8d1c04727d44ebe31cb6d8de7d55b6a49d7d118`
- Source `config.yml` SHA-256: `d8a2e9bf98bf22f7d80c866b0e37fd1009fad948fe6123f97473b1157a6eb3c2`
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
| baseline-ar | 991.2 | null | null | 0 / 0 | 819.7269925 / 771.3534202 | 945.3083765 / 1004.6351906 | 1765.077574 / 1776.0367347 | 1767.7709745 / 1779.2136943 | 20.1184003174 / 19.9234056715 | 3518361600 / 4645191680 | n/a | n/a | null | null | null |
| cc-dflash-r2 | 634 | 0.475272117338 | 0.35915027869 | 161.434746499 / 151.5855573 | 518.196933 / 489.8129116 | 224.815044 / 235.3535726 | 712.752760501 / 725.2432963 | 872.59363 / 881.6379708 | 86.8685342889 / 86.5764770825 | 4358935552 / 4812963840 | PASS | 8 | 4.9 | 0.585714285714 | 0.242718446602 |
| dflash-r1 | 991.2 | null | null | 0 / 0 | 755.072434 / 714.9840175 | 277.299456001 / 266.1123002 | 1000.5867925 / 981.1813494 | 1004.8950035 / 985.9817501 | 70.3095714377 / 74.8293655849 | 4814022656 / 5807013888 | PASS | 8 | 5.10526315789 | 0.616541353383 | 0.235294117647 |
| llmlingua-ar-r2 | 634 | 0.475272117338 | 0.35915027869 | 161.434746499 / 151.5855573 | 484.51249 / 460.4752037 | 787.913950501 / 797.7477183 | 1251.816866 / 1258.2925711 | 1410.526613 / 1413.2070752 | 24.9559519527 / 24.6073517436 | 3125669888 / 3623878656 | n/a | n/a | null | null | null |

## Metric scopes

- Compression latency: synchronized LLMLingua context-compression stage; zero for original-context conditions.
- Prefill/decode/generation latency and decode tok/s: synchronized production generation request.
- Stage-sum E2E: compression plus runtime warm-request latency with separate GPU residency; excludes warmup and model load/unload.
- Validation workload wall clock: 63965.712528 ms for compressor and engine lifecycles, including warmups and 40 measured requests.
- Workload lifecycle-amortized latency: 1599.1428132 ms per measured request; not a per-condition request latency.
- Context reduction uses the LLMLingua tokenizer; target-token reduction uses paired Qwen chat-template input counts and is null for original conditions.
