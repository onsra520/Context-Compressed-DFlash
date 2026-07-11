# Rec-T05B - Unified Benchmark and Evaluation Workflow

Status: PASS

`ccdf benchmark` invokes `ccdf.benchmark.workflow.run_benchmark`, which uses `RuntimeEngine.execute` for every real row. `ccdf evaluate` reads those JSONL artifacts only and records summaries without loading or rerunning models.

The GSM8K n10 example completed with Baseline-AR and DFlash-R1. The QMSum n30 example completed `90/90` rows across Baseline-AR, DFlash-R1, and CC-DFlash-R2. All rows retain frozen fixture identity, manifest hash, prompt hashes, generated text, real timing/VRAM, and DFlash metrics. Evaluation is cap-aware; QMSum remains proxy-only and `NOT_CLAIMED` for semantic correctness.
