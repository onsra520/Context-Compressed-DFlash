# Unified four-condition protocol

## Conditions and fairness

| ID | Name | Runtime | Input |
|---|---|---|---|
| C1 | Baseline-AR | autoregressive target | exact original prompt |
| C2 | DFlash-R1 | DFlash target/drafter | exact original prompt |
| C3 | LLMLingua-AR-R2 | autoregressive target | persisted compressed prompt |
| C4 | CC-DFlash-R2 | DFlash target/drafter | the same persisted compressed prompt as C3 |

Compression is staged before generation. One GPU-only LLMLingua-2 process compresses every sample once and writes a cache keyed by stable sample ID. The compressor is unloaded and the GPU is proven empty before generation. C1 through C4 then execute sequentially in distinct processes, and an empty-GPU boundary is captured between each condition. C3/C4 never load the compressor and can only consume the persisted cache.

All four conditions use the same sample order, Qwen tokenizer, target model, seed 42, temperature 0, stopping IDs, non-thinking chat template, SDPA-math policy, and maximum-new-token value. C1/C2 must have identical input prompt hashes and generated token IDs. C3/C4 must independently satisfy the same pairwise requirements. C1/C3 equality is neither required nor claimed.

## Compressor contract

The requested device must begin with `cuda`; unavailable CUDA, a bad device index, any parameter or buffer outside the resolved CUDA device, an empty prompt, or a 2.25 GiB reserved-memory budget breach raises a hard failure. The cache and audit persist requested/resolved device, device index/name, actual floating dtypes, model/config identity, per-sample compression latency, and per-sample allocated/reserved peak. Silent CPU fallback does not exist.

## Unified raw schema

Schema `ccdf.four-condition.raw.v1` is validated before every row is written. It includes run/process/sample/condition identity, phase and repetition, seed, original/compressed/input prompt hashes, one-time compression-run identity, target-token counts and reduction metrics, compressor identity/device/dtype/latency/memory, generated IDs/text/count, component and total timings, DFlash structure, generation and condition memory, mock quality, model/runtime identity, and status/error.

DFlash-only fields are `null` for AR. Compressor runtime fields are `null` for original-input conditions. Condition peak is `max(compressor peak, generation peak)` for staged compressed conditions; peaks are never summed and mislabeled as simultaneous E2E residency.

## Metric definitions

- Token reduction = original target-token count - compressed target-token count.
- Keep rate = compressed target-token count / original target-token count.
- Compression ratio = original target-token count / compressed target-token count.
- Compressor latency measures only compression inference after model load; model-load latency is separate.
- Decode throughput = decode tokens / decode time. End-to-end throughput = generated tokens / warm request time.
- Every scalar series reports count, mean, median, min, max, and sample standard deviation.
- Draft and verify time are sums of per-block CUDA-event spans. Events do not synchronize inside the decode loop.
- DFlash acceptance rate = accepted draft tokens / drafted tokens; tau is the existing mean advance per verification call.
- Pairwise parity is exact generated-token-list equality by `(sample_id, repetition)` with first mismatch index and token IDs.
- Mock quality only checks protocol/runtime behavior; it is not dataset-quality evidence.

## Mock10 decision

The initial run passed all orchestration, compressor, schema, metric, order, isolation, and C1/C2 parity gates. C3/C4 failed exact generated-token parity on mock-02 and mock-10, so Stage 2 is `FAIL` and later stages are closed.
