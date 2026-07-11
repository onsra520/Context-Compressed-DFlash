# Real CLI Output

`ccdf run --condition baseline-ar --prompt "What is 2+2? Answer:" --format text` reports the real model answer, input/output tokens, total/prefill/generation latency, GPU peak memory, stop reason, and cap-hit state.

`dflash-r1` adds real verification and draft counters. `cc-dflash-r2` adds compression state and bypass details.
