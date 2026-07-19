# Four-condition mock10 final report

- Sealed summary SHA-256: `36573f03a66129cbb450b061b1daf071671511682d129a3fee6982d668b3f77d`
- Source `config.yml` SHA-256: `904c408e5d492ec03ec0b21a710303b06589479012e804725a575bb14ba4c086`
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
| baseline-ar | 991.2 | null | null | 0 / 0 | 740.26225 / 675.32835 | 1365.02995 / 1358.53472 | 2059.0035 / 2033.92803 | 2061.38885 / 2036.28132 | 14.276849628 / 14.2856058058 | 3518361600 / 4645191680 | n/a | n/a | null | null | null |
| cc-dflash-r2 | 665.4 | 0.446620732455 | 0.327658798289 | 117.031100001 / 128.11561 | 465.6669 / 450.98899 | 358.23785 / 388.499649999 | 856.6396 / 839.55854 | 954.519550001 / 970.59497 | 53.0507825725 / 51.63243186 | 4397017600 / 4861198336 | PASS | 8 | 4.52272727273 | 0.538961038961 | 0.258373205742 |
| dflash-r1 | 991.2 | null | null | 0 / 0 | 710.3368 / 666.34171 | 341.017700001 / 323.04975 | 997.568950001 / 989.46229 | 1000.943 / 992.88733 | 58.2176398836 / 60.8508492606 | 4814022656 / 5807013888 | PASS | 8 | 5.10526315789 | 0.616541353383 | 0.235294117647 |
| llmlingua-ar-r2 | 665.4 | 0.446620732455 | 0.327658798289 | 117.031100001 / 128.11561 | 466.5649 / 450.72952 | 1410.6 / 1420.739 | 1822.5164 / 1871.51377 | 1956.3729 / 2001.85725 | 14.0233009981 / 13.9396582491 | 3166330880 / 3680501760 | n/a | n/a | null | null | null |

## Metric scopes

- Compression latency: synchronized LLMLingua context-compression stage; zero for original-context conditions.
- Prefill/decode/generation latency and decode tok/s: synchronized production generation request.
- Stage-sum E2E: compression plus runtime warm-request latency with separate GPU residency; excludes warmup and model load/unload.
- Validation workload wall clock: 95775.2158 ms for compressor and engine lifecycles, including warmups and 40 measured requests.
- Workload lifecycle-amortized latency: 2394.380395 ms per measured request; not a per-condition request latency.
- Context reduction uses the LLMLingua tokenizer; target-token reduction uses paired Qwen chat-template input counts and is null for original conditions.
