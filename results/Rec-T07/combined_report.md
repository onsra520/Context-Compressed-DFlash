# Rec-T06D / Rec-T07 combined analysis

This analysis joins the preserved, identical-fixture n=100 summaries from Rec-T06D (CPU compression) and Rec-T07 (CUDA-compressor conditions). It does **not** rerun n=100 or rewrite raw evidence. Values and row-level provenance remain in the two run directories; [combined_summary.csv](combined_summary.csv) is the derived comparison table.

## CPU versus GPU compression

On QMSum, moving LLMLingua compression from CPU to GPU reduced mean compression time from 2858.357 ms to 154.037 ms: **18.56x** faster. CC-DFlash compression fell from 2810.884 ms to 164.710 ms: **17.07x** faster. Both retain the same 52.066% full-prompt reduction (1127.95 tokens on average) and the same stored reference proxy metrics as their CPU counterpart. The paired raw-output/evaluator evidence is therefore consistent with output equivalence for these CPU/GPU compressor variants; it is not a semantic-correctness claim.

GSM8K is different: all relevant short contexts bypass compression. The GPU compressor is not loaded, compression time is 0, and there is no GPU-compression speedup to claim. The new runtime composition makes that explicit.

## Warm E2E comparison

For QMSum LLMLingua-AR, GPU compression has a 1708.262 ms mean warm E2E time: 2757.732 ms faster than CPU compression, 162.599 ms faster than Baseline-AR, and 626.094 ms faster than DFlash. For QMSum CC-DFlash-GPU, the 2083.879 ms mean is 2696.175 ms faster than CPU CC-DFlash and 250.477 ms faster than DFlash, but 213.018 ms slower than Baseline-AR.

The GSM8K bypass rows do not demonstrate compressor performance. Their small timing differences are normal separate-process benchmark variation plus the unchanged target/drafter paths; no compression conclusion is drawn from them.

## Quality, output, and token boundaries

GSM8K strict correctness is preserved in the paired CPU/GPU rows (83/100 LLMLingua-AR and 84/100 CC-DFlash), where compression bypasses. QMSum GPU rows preserve the CPU rows’ reference recall/precision (0.2276/0.3364 for LLMLingua-AR and 0.2267/0.3381 for CC-DFlash) and show no invalid or empty outputs. **QMSum semantic correctness remains NOT_CLAIMED.** Exact cached-AR token equivalence is also not claimed.

## VRAM and RSS trade-offs

Historical process peaks show QMSum GPU compression at 3.43 GiB allocated / 3.54 GiB reserved for LLMLingua-AR and 4.63 GiB / 4.70 GiB for CC-DFlash. CPU compression peaks were 2.76 GiB / 2.83 GiB and 3.97 GiB / 4.07 GiB respectively, while CPU-side compressor RSS deltas were about 130–144 MiB. These are process measurements, not isolated component attribution. The hotfix now emits a true CUDA allocation/reservation delta around compressor construction when telemetry is available, and otherwise reports null with unsupported metadata.

## Conclusions

- For long QMSum contexts on the recorded hardware, GPU LLMLingua compression removes roughly 2.65–2.76 seconds of warm CPU-compression overhead and yields 17–19x faster compression.
- LLMLingua-AR-GPU is the fastest recorded QMSum condition; CC-DFlash-GPU beats DFlash but not Baseline-AR on warm E2E.
- GPU compression adds process VRAM relative to the CPU compressor path. Select it only when the large compression-time reduction is worth the VRAM budget.
- No GPU-compression performance claim applies to GSM8K short-context bypass.
