# QMSum prefill deep audit

## Verdict

The production Baseline AWQ path is not spending 9–40 minutes in tokenization or model load. It enters CUDA attention, dispatches to SDPA math, grows quadratically with prompt length, and exhausts the RTX 4070 Laptop GPU before the 6,289-token request can be launched safely. The 4,096-token prefix crossed the 7.5 GiB safety gate at 7,799 MiB physical VRAM and its process tree was terminated. The required 6,289-token case was therefore not run.

The proven root-cause codes are:

- `SDPA_MATH_FALLBACK` — profiler traces contain `aten::_scaled_dot_product_attention_math`, `aten::bmm`, and `aten::_softmax`; auto and forced-math are effectively identical at 2,048 tokens.
- `EXPLICIT_MASK_BLOCKS_FUSED_SDPA` — in the controlled cache-disabled standard-forward comparison, `attention_mask=None` used efficient attention in 0.832 s while an all-ones mask used math in 1.932 s, with the same first token (7849).
- `PHYSICAL_VRAM_EXHAUSTION` — the isolated 4,096-token case reached 7,799/8,188 MiB according to `nvidia-smi`, above the 7,680 MiB gate. This is physical VRAM, not a Torch allocator estimate.
- `WINDOWS_MEMORY_THRASH` — the earlier guarded full 6,289-token warmup had GPU utilization 100%, 7,692/8,188 MiB VRAM, and an 11,892,240,384-byte child working set while taking 563.27 s. This is operational evidence of the full-GPU/high-host-memory slow path. The audit cannot attribute every host page specifically to WDDM shared GPU memory.
- `OTHER_PROVEN_CAUSE` — the production `use_cache=true`/`DynamicCache` route remains on math even with `attention_mask=None`. Forced efficient rejects the GQA shape (`Q=32` heads, `K/V=8` heads); Flash rejects because this Torch build has no Flash Attention kernel. Thus removing the explicit mask alone cannot repair the production path.

`CUSTOM_FORWARD_PATH_REGRESSION` is ruled out at 2,048 tokens: project forward, standard forward, and standard `generate` all produced token 7849 and approximately 1.92–1.96 s prefill with cache enabled. `AWQ_TRITON_WINDOWS_SLOW_PATH` is not established because the repository contains no comparable canonical-Linux artifact. AWQ is visible, but it does not explain the length-dependent inflection.

## Reproduction matrix

All cases ran in fresh `python -X faulthandler` processes under a 120 s timeout. The parent sampled physical GPU memory and the whole process-tree working set and terminated the tree above 7,680 MiB.

| Prefix | Status | Load (s) | Prefill (s) | First token (s) | Decode token (s) | Physical VRAM (MiB) | Torch max alloc / reserve (GiB) | Host tree RSS (GiB) | Actual backend |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 128 | PASS | 2.589 | 0.246 | 0.250 | 0.114 | 3,549 | 2.56 / 2.58 | 3.95 | math |
| 512 | PASS | — | 0.426 | 0.430 | 0.131 | 3,723 | 2.71 / 2.75 | 3.91 | math |
| 1,024 | PASS | — | 0.721 | 0.724 | 0.106 | 4,074 | 3.06 / 3.09 | 3.88 | math |
| 2,048 | PASS | — | 1.934 | 1.938 | 0.127 | 5,302 | 4.13 / 4.29 | 4.02 | math |
| 4,096 | PHYSICAL_VRAM_LIMIT | — | not completed | not completed | not run | 7,799 | unavailable after kill | 3.88 | not observed |
| 6,289 | SKIPPED_BY_GATE | — | — | — | — | — | — | — | — |

Raw per-case JSON contains the model-load value for every successful case. The longest successful CUDA allocator snapshot is `cases/L2048-auto-none-standard-cache-true/cuda-memory-snapshot.pickle`.

## Backend and mask/cache evidence

At 2,048 tokens with standard forward and cache enabled:

- auto: PASS, actual math, 1.924 s;
- forced math: PASS, actual math, 1.907 s;
- forced Flash: REJECTED, `RuntimeError: No available kernel`; stderr says Torch was not compiled with Flash Attention;
- forced efficient: REJECTED, `RuntimeError: No available kernel`; stderr reports the dense GQA head mismatch and also records the unavailable Flash/cudnn alternatives.

No forced backend silently fell back. The profiler, rather than enabled flags, determined the actual operator. The standard `generate` checks with mask `None` and all-ones both used math and matched token 7849, so the custom loop is not the regression.

Transformers 4.57.6 integration evidence (`transformers/integrations/sdpa_attention.py`, installed environment) states that CUDA GQA is eligible only when its internal attention mask is `None`; otherwise it repeats K/V, and it calls PyTorch SDPA at line 96. The recorded rejection warnings and profiler traces are retained in the pack, so this source note is not the sole evidence.

## AWQ and operator attribution

Environment: AutoAWQ 0.2.9, Triton metadata 3.7.1, Triton-Windows 3.7.1.post27, Torch 2.13.0+cu130, Transformers 4.57.6, CUDA runtime 13.0, driver 610.62, Python 3.12.10.

At 128 tokens, `WQLinearMMFunction`/`awq_gemm_kernel` used 53.7 ms self CUDA time, while `aten::bmm` used 1.0 ms and `_softmax` 0.24 ms. At 2,048 tokens, AWQ dequantization used 34.2 ms, while math-attention components grew to 194.3 ms (`bmm`), 175.9 ms (`softmax`), and 171.2 ms (`where`); dense `mm` used 361.3 ms. This shift, plus rising VRAM, identifies attention/mask scaling as the long-context driver. Without a same-model canonical-Linux trace, no Windows-specific AWQ conclusion is claimed.

## Memory classification

- Fragmentation: not proven. The 2,048 snapshot is retained, but the 4,096 case was killed by the physical limit before a CUDA OOM could expose allocator free-block evidence.
- Physical exhaustion: proven at 4,096 tokens by `nvidia-smi` (7,799 MiB used).
- Virtual allocation: the earlier 5.15 GiB allocation request is an attempted allocation, not physical usage and not a claim of 36–46 GiB VRAM.
- Host/shared-memory thrash: strongly supported operationally by the 6,289-token guarded run (full GPU, 11.89 GB child working set, 100% GPU, 563 s). Direct page-level WDDM attribution was not available.
- Metric bug: ruled out for the physical limit because the parent used `nvidia-smi` independently of Torch.

## Patch and post-patch gate

No dependency was changed and no D-Flash core file was modified by this audit. The only safe source patch removes runner overhead and improves observability:

- reuse the one chat-template tensor captured for the token audit instead of encoding the same request again in `RuntimeEngine.generate`;
- remove the dataset worker's pre-count encoding, reducing three encodes per measured request to one;
- report encode and token-audit time separately;
- emit `model_loaded`, `tokenize_complete`, `prefill_start`, `prefill_complete`, `decode_start`, and `decode_complete`.

The post-patch 2,048-token safety probe passed: one chat-template call, 1.889 s prefill, 1.895 s first token, 5,039 MiB maximum physical VRAM, and the same token 7849. A profiled repeat completed prefill/decode but the Windows Kineto process then raised a native access violation while computing `key_averages`; its stderr is retained separately. The unprofiled post-patch gate is the authoritative PASS.

The full n1 workload is `BLOCKED_BY_PHYSICAL_VRAM_GATE`: the prerequisite length matrix already failed at 4,096, so launching the longer 6,289-token request would violate the explicit stop rule. Consequently n2 was not launched after the patch, and n10 remains prohibited. The earlier guarded n2 already failed at its first condition after a 563.27 s warmup and a 900 s timeout.

Using the preserved partial run's 9,541.7 s wall time for 15 of 80 completed measured requests gives a naive projected 80-request wall time of 50,889 s (14.14 h), excluding the cost of the OOM row. This is far above the 50-minute admission threshold and includes no safety basis for n10.

