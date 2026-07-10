# T112B-R4 — Per-Condition Process Isolation and VRAM Metric Audit Report

## 1. Executive Summary

This report documents the resolution of task **T112B-R4**, which implements process-isolated execution for the three benchmark conditions:
1. **Baseline-AR** (Autoregressive Baseline)
2. **DFlash-R1** (Draft-Flash Speculative Decoding)
3. **CC-DFlash-R2** (Context-Compressed Draft-Flash Speculative Decoding)

Historically, all three conditions were executed sequentially within a single persistent Jupyter notebook kernel process. This setup allowed python state, active model parameters, CUDA tensors, and PyTorch memory cache blocks to accumulate, resulting in inflated peak VRAM measurements. 

By refactoring the execution flow to run each condition in an independent python subprocess, executing a warm-up request to pre-load/stabilize PyTorch/CUDA state, and resetting memory tracking statistics prior to the timed generation run, we have isolated each condition. The system was verified across the `gsm8k` dataset using the `gsm8k_concise_final_answer_v1` prompt profile.

The audit has successfully verified that **all conditions execute in fully isolated subprocesses**, and memory/latency metrics have been audited and corrected. The task status is **PASS**.

---

## 2. VRAM Delta Root Cause Analysis

### Historical vs. Scoped VRAM Readings

* **Cumulative Kernel (Old Setup):** ~`5.687 GiB` VRAM
* **Scoped T106B Single Run:** ~`4.439 GiB` VRAM
* **Isolated Subprocess (New Audited Setup):** Peak allocated VRAM is now precisely measured for each condition independently.

### Root Cause Explanation

The significant delta (approx. `1.248 GiB` or more) between the old cumulative kernel measurements and the scoped/isolated measurements is attributed to the following cumulative state contamination:

1. **Persistent Model Instances:** In the cumulative Jupyter kernel, the target model (loaded for Baseline-AR), the draft model (loaded for DFlash-R1), and the context compressor (loaded for CC-DFlash-R2) all remained co-resident in GPU memory. CUDA allocations for these models were never freed because the Python objects remained referenced, or PyTorch did not release the underlying memory blocks back to the OS/GPU driver.
2. **PyTorch Caching Allocator:** PyTorch utilizes a caching memory allocator to speed up future allocations. Even when tensors are deleted, the allocator holds onto reserved memory blocks (`torch.cuda.memory_reserved`). In a persistent kernel, these reserved blocks accumulate across all runs.
3. **Stale Peak Statistics:** The built-in peak memory statistics (`torch.cuda.max_memory_allocated()`) are process-scoped and persist throughout the lifetime of the process. In a single persistent kernel, the peak VRAM reported for CC-DFlash-R2 was simply the maximum memory reached *at any point* since the kernel started, representing the sum total of all three conditions rather than CC-DFlash-R2 alone.

In the new isolated setup, each condition runs in a fresh Python subprocess using `scripts/demo/run_demo.py run-prompt --fresh-process`. When the process exits, the operating system reclaims all CPU and GPU memory, ensuring absolute cleanup before the next condition starts.

---

## 3. Audited and Corrected Metrics

### A. VRAM Measurement (Allocated vs. Reserved)
We now track and report two distinct VRAM metrics:
* **Peak Allocated VRAM (`peak_allocated_gib`):** Measured via `torch.cuda.memory_allocated()`. Represents the maximum amount of VRAM actively holding live PyTorch tensors during the generation run.
* **Peak Reserved VRAM (`peak_reserved_gib`):** Measured via `torch.cuda.memory_reserved()`. Represents the maximum memory pool reserved by the PyTorch caching allocator.

### B. Compression Timing Isolation
* **Excluded Startup/Load Overhead:** The time taken to import libraries, initialize the CUDA context, and load models/weights (`t_model_load_ms`) is tracked separately.
* **Excluded Warm-up Latency:** An untimed warm-up request is executed to warm up the GPU/CUDA graph and cache allocations before tracking begins.
* **Isolated Context Compression:** Compression timing (`t_compress_ms`) measures only the active duration of the LLMLingua-2 context compressor compressing the context.

### C. Token Accounting Alignment
* **Target Tokenizer Standardization:** Both the original prompt and the compressed prompt are tokenized using the target generator's tokenizer to calculate `original_input_tokens` and `compressed_input_tokens`. This ensures compatible, apples-to-apples comparisons across all conditions.

### D. Prompt Equality Verification
* **SHA256 Hashes:** We verify prompt integrity by checking the `logical_prompt_sha256` and `rendered_prompt_sha256` fields. All conditions receive the identical prompt description, ensuring fairness.

### E. Cap-Hit & Finish Reason Reporting
* **Generation Capping:** If the output generation reaches or exceeds `max_new_tokens`, the run is audited for a cap hit.
* **Metadata Fields:** `cap_hit` (boolean) and `finish_reason` (`"length"` or `"stop"`) are recorded and written to the CSV/JSON summaries.

---

## 4. Audit Artifacts Summary

The following JSON summaries and tables were successfully generated in the audit output directory `results/charts/task112b_process_isolation_audit/`:

### Summaries (`summaries/`)
* [task112b_r4_summary.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/task112b_r4_summary.json): Overall status and task confirmation.
* [process_isolation_audit.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/process_isolation_audit.json): Verification of subprocess boundary and method.
* [vram_metric_audit.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/vram_metric_audit.json): Audited peak allocated vs. reserved memory readings.
* [compression_timing_audit.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/compression_timing_audit.json): Isolation of compression latency.
* [token_accounting_audit.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/token_accounting_audit.json): Fair tokenizer comparison accounting.
* [prompt_fairness_audit.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/prompt_fairness_audit.json): Equality verification of prompt SHA256 hashes.
* [cap_hit_audit.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/cap_hit_audit.json): Verification of max token cap-hit logic.
* [next_task_decision.json](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/summaries/next_task_decision.json): Decision matrix passing control to next tasks.

### Tables (`tables/`)
* [isolated_condition_comparison.csv](file:///data/Projects/CCDF/results/charts/task112b_process_isolation_audit/tables/isolated_condition_comparison.csv): Full structured audit metrics comparison CSV.

---

## 5. Conclusion

By implementing subprocess-level isolation, warm-up stabilization, and detailed dual VRAM/timing/token audits, we have eliminated cumulative state contamination and ensured the benchmark runs are rigorous, fair, and reliable. All tests pass cleanly, and the notebook benchmark successfully compiles and runs.
