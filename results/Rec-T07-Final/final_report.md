# Rec-T07 final synchronized GPU report

The CPU comparison uses preserved Rec-T06D QMSum n=100 rows; only the two requested GPU conditions were rerun. QMSum semantic correctness is **NOT_CLAIMED**. Exact output/compressed-input matches below are observed hash evidence.

| GPU condition | CPU/GPU compression ms | speedup | CPU/GPU warm E2E ms | warm improvement | vs Baseline-AR | vs DFlash-R1 | prompt reduction | output/input hashes | peak alloc/reserved | CPU RSS current/peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| llmlingua-ar-r2-gpu | 2858.357 / 177.925 | 16.06x | 4465.995 / 1811.300 | 2654.694 ms | -59.561 ms | -523.056 ms | 52.066% | 100/100; 100/100 | 3.43/3.49 GiB | 1.42/3.27 GiB |
| cc-dflash-r2-gpu | 2810.884 / 177.467 | 15.84x | 4780.054 / 2205.786 | 2574.268 ms | 334.924 ms | -128.571 ms | 52.066% | 100/100; 100/100 | 4.63/4.71 GiB | 1.48/3.27 GiB |

## Synchronized-versus-older GPU values

| Condition | old compression ms | synchronized compression ms | old warm E2E ms | synchronized warm E2E ms |
|---|---:|---:|---:|---:|
| llmlingua-ar-r2-gpu | 154.037 | 177.925 | 1708.262 | 1811.300 |
| cc-dflash-r2-gpu | 164.710 | 177.467 | 2083.879 | 2205.786 |

All 200 final GPU rows passed output-health checks. Both compressors ran as CUDA-resident on `cuda:0` with 199 parameters and 2 buffers; per-request transfer/offload were 0 ms, while initial device placement is recorded separately in raw rows. Request-wide peaks include prompt preparation, compression, and generation.
