# Rec-T07 source repairs

Root cause: GPU kernels are asynchronous, so pre-existing compressor and warm-request wall-clock measurements could exclude queued GPU work. Peak CUDA statistics were also reset after optional compression, excluding compressor allocations from the advertised request peak. Finally, CUDA placement and resource reporting did not make constructor placement versus per-request transfer explicit.

Changed files: `src/ccdf/runtime/engine.py`, `src/ccdf/compression/llmlingua.py`, and `tests/test_rec_t07_gpu_hotfix.py` (commit `27db94f`).

Behavioral impact: GPU compression fences CUDA before and after compressor timing; warm E2E fences before start and after generation; CUDA peak statistics reset before prompt preparation/compression; GPU compressors fail if CUDA is unavailable or any discovered parameter/buffer is non-CUDA. Rows record full-request peaks, resident/staged mode, device set/counts, CPU RSS, and truthful constructor-placement/per-request transfer scope.

Comparability: CPU results are preserved and were not rerun. The new GPU timings are synchronized and therefore supersede the older unsynchronized GPU values for timing comparisons; prompt/output equivalence remains directly checked against preserved CPU raw rows.

Regression coverage: focused timing/resource tests cover fences, reset ordering, CUDA fallback rejection, tensor/buffer audit, and emitted metadata. The final n=3 and n=100 artifacts provide real-CUDA validation.
