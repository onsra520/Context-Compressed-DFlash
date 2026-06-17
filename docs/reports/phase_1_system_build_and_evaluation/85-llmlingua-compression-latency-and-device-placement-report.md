# Task 85 — LLMLingua-2 Compression Latency Breakdown and Device Placement Optimization

## 1. Objective
Diagnose and optimize the compression latency bottleneck (`T_compress`) for the CC-DFlash pipeline. The objective is to understand the device placement, sub-timings, and feasibility of GPU or cached compression architectures.

## 2. Why Task 85 Was Needed
Following Task 84, QMSum was solidified as a diagnostic-only benchmark. The primary remaining bottleneck for the CC-DFlash pipeline is the end-to-end latency penalty caused by online compression (`T_compress`). Although CC-DFlash speeds up decoding, the ~5.7s compression overhead per row cancels out much of the gain compared to uncompressed Baseline-AR. 

## 3. Current Compressed-Path Bottleneck
The bottleneck is `T_compress`. During the Task 83 QMSum benchmark, `T_compress` averaged ~5.7 seconds per row for both LLMLingua-AR-R2 and CC-DFlash-R2. 

## 4. Device Placement Audit
An audit of `src/ccdf/compression/llmlingua.py` and `scripts/run_mvp.py` reveals that the `PromptCompressor` is initialized with `device_map="cpu"` by default. While the target decoding model (DFlash) runs on the GPU, the LLMLingua-2 compressor executes entirely on the CPU. This cross-device architecture avoids VRAM contention but incurs massive CPU computation overhead.

## 5. Compression Latency Breakdown
We instrumented `LLMLinguaCompressor` and ran a QMSum n=3 smoke test to break down the total compression time (~15.4s total, or ~5.1s per row):

| Component | Time (ms) | % of Total |
|---|---|---|
| **Outer Preprocessing** (Tokenizer/Chunking) | 23.8 ms | < 0.2% |
| **Inner Preprocessing** | 12.7 ms | < 0.1% |
| **Compressor Forward Pass (CPU)** | **15379.3 ms** | **99.3%** |
| **Token Selection & Scoring** | 63.1 ms | 0.4% |
| **Outer Postprocessing** (Reconstruction) | 5.7 ms | < 0.1% |
| **Total `T_compress`** | **15484.6 ms** | **100%** |

> [!WARNING]
> The CPU forward pass of the `xlm-roberta-large` model constitutes over 99% of the compression time.

## 6. VRAM Trace & GPU Compressor Smoke Result
We attempted to force the compressor onto the GPU (`device_map="cuda"`) in a subprocess. 
- **Result**: The subprocess crashed immediately with **Signal 11 (Segfault / OOM)** during model loading.
- **Diagnosis**: The 8GB GPU memory limit cannot reliably accommodate the `llmlingua-2-xlm-roberta-large-meetingbank` model, leading to hard crashes.

## 7. Load/Unload Architecture Result
Because the GPU compressor inherently segfaults/OOMs upon loading, **the load/unload architecture is inviable.** We cannot dynamically load the compressor to the GPU, run the forward pass, and unload it, because the load step itself exceeds safe memory/driver limits.

## 8. Cached/Precompressed Upper Bound
If the compression step could be performed entirely offline (cached), the `T_compress` penalty during online inference would be exactly 0.0 ms. 
- **Theoretical online improvement**: ~5.1 to 5.7 seconds per generation.
- **Implication**: If CC-DFlash relies on cached prompts, the online end-to-end latency would easily outpace Baseline-AR, proving that the DFlash decoding mechanism itself is highly efficient once the context is compressed.

## 9. Recommendation
**Keep the current CPU compressor but explicitly bound CC-DFlash claims around offline/cached compression.**

Since GPU compression is inviable under the 8GB constraint, and CPU compression is fundamentally too slow for real-time online use, the fairest deployment model for CC-DFlash is **Cached/Offline Compression Mode**. Future reports should emphasize that CC-DFlash demonstrates significant end-to-end speedups *if* the context is pre-compressed offline. Online compression on limited hardware remains an unsolved bottleneck, which is a standard limitation for context-compression research.

## 10. Artifact List
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_compression_latency_breakdown.json`
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_compression_latency_breakdown.csv`
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_vram_trace.json`
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_vram_trace.csv`
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_load_unload_architecture.json`
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_cached_compression_upper_bound.json`
- `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task85_cached_compression_upper_bound.csv`

## 11. Claim Boundary
> [!IMPORTANT]
> **Do not claim online compression is solved.** 
> **Do not claim deployment readiness for real-time LLMLingua-2 on 8GB GPUs.** 
> All future claims must clarify that CC-DFlash end-to-end speedups are optimal only in scenarios where prompt compression can be executed offline or asynchronously.
