# QMSum n10 emergency runtime diagnostic

## Verdict

The interrupted run was not waiting in preparation, model load, or a deadlocked parent. It reached `baseline-ar` generation, completed all 10 GSM8K rows, then produced five QMSum rows before exiting. Four successful full-transcript QMSum requests ran at only 0.123–0.176 decode tok/s and took 1,928–2,479 seconds each; one additional QMSum request failed with CUDA OOM while attempting a 5.15 GiB allocation. The primary classification is **QMSum original-context generation pathologically slow**, with a separate OOM event. Buffered `capture_output=True` hid live worker progress from the parent, but did not cause the compute stall.

## Preserved state

- Prepared inputs: 20/20 (10 GSM8K + 10 QMSum).
- Completed rows: 15/80 overall; only `baseline-ar` started.
- `baseline-ar`: 10/10 GSM8K, 5/10 QMSum; 14 successes and 1 OOM.
- Other conditions: 0 rows; no retry or resume evidence and no orphan benchmark Python process at the emergency snapshot.
- Prepared file timestamp: 2026-07-19 04:41:30 +07:00.
- Last raw-row progress: 2026-07-19 07:20:32 +07:00.
- Generation-stage observation window after prepared output: 9,541.7 seconds.
- Sum of successful measured request wall time: 8,883.4 seconds; QMSum alone: 8,706.4 seconds.
- Sum of recorded compression latency: 18.2 seconds. Compression is not the runtime driver.

## QMSum row evidence

| Fixture | Input tokens | Output tokens | Request seconds | Decode tok/s | Cap hit | Result |
|---|---:|---:|---:|---:|---|---|
| meeting0029 / query 04 | 10,956 | 49 | 2,150.7 | 0.159 | no | EOS |
| meeting0018 / query 00 | unavailable in legacy error row | — | — | — | — | CUDA OOM, 5.15 GiB allocation attempted |
| meeting0033 / query 02 | 11,631 | 37 | 2,479.4 | 0.151 | no | EOS |
| meeting0001 / query 02 | 10,342 | 44 | 1,928.4 | 0.123 | no | EOS |
| meeting0013 / query 01 | 11,782 | 60 | 2,147.9 | 0.176 | no | EOS |

The slowest completed sample is `qmsum_test_meeting0033_specific_02_20d48688` at 2,479.4 seconds. None of the completed QMSum outputs hit the configured 512-token cap; the delay is therefore not caused by generating all 512 tokens. The request contract remained one final generation request per logical sample.

## Evidence limits

The requested benchmark process had already exited when the emergency snapshot was taken, so no pre-kill PID tree was available and no kill was issued. The legacy error row also discarded rendered-input token evidence on exception. The watchdog change closes both observability gaps for subsequent runs by streaming worker logs, flushing request-start/request-complete progress records, and capturing the process tree plus GPU state before tree termination.

## Guarded n=2 result

The required n=2 × four-condition gate stopped in the first condition and is `TIMEOUT_FAIL`; the slow-sample phase and n10 rerun are therefore prohibited.

- Selection: the two shortest full-transcript QMSum samples (3,862 and 6,030 original words).
- Profile: SDPA auto, fixed block size 8, QMSum `max_new_tokens=512`, one attempt, no retry/resume.
- `baseline-ar` model load: 5.49 seconds.
- First-sample warmup: 6,289 input tokens, 43 output tokens, 563.27 seconds, 0.276 decode tok/s, EOS, no cap-hit.
- Measured sample 1 then started, but the condition reached its config-owned 900-second limit before a row completed.
- Watchdog action: captured PID 10540 and child 30336, GPU 100%, 7,692/8,188 MiB VRAM, child working set 11,892,240,384 bytes and command lines; `taskkill /PID 10540 /T /F` succeeded.
- Post-kill GPU: 1%, 844 MiB; subsequent audit found only the unrelated Black formatter Python pair and no benchmark orphan.
- Attempt count 1; retry 0; resume false; native crash code absent. Timeout is the only failed runtime-safety gate.
