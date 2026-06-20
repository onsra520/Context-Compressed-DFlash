# Task 91B — Linux GPU Readiness and DFlash Path Audit

## 1. Task framing

Task 91B belongs to Phase 2 system optimization. Its role is to prepare the Linux/Kubuntu runtime for Task92 lighter compressor integration and to confirm that the local one-GPU workflow is viable for the target model, the DFlash draft model, and the compressor path.

This task is a readiness and path-validation step, not a final benchmark. Linux/Kubuntu is used because it is expected to be a more reliable CUDA and model-loading runtime than the previous Windows setup for this repository's local execution path.

## 2. Environment

- OS: Kubuntu/Linux
- Python: 3.12.13
- torch: 2.5.1+cu121
- torch CUDA runtime: 12.1
- transformers: 4.57.3
- huggingface_hub: 0.36.2
- GPU: NVIDIA GeForce RTX 4070 Laptop GPU

The GPU validation shell used for Task91B reported both `nvidia-smi` success and `torch.cuda.is_available() == True`.

## 3. Dependency correction

The earlier setup audit draft overstated the PyTorch install recommendation. The suggested `torch==2.9.1+cu121` was not available from the CUDA 12.1 wheel index used in this environment, so it was not the validated setup for Task91B.

The actual validated PyTorch version is:

- `torch==2.5.1+cu121`

The Hugging Face dependency boundary also needed to remain conservative:

- `huggingface_hub==0.36.2`

This version is retained because newer `huggingface_hub` 1.x releases conflict with the validated `transformers==4.57.3` setup used by the project runner.

## 4. Local model paths

Task91B validated the presence and local use of these model folders:

- `models/Qwen3-4B`
- `models/Qwen3-4B-DFlash-b16`
- `models/llmlingua-2-xlm-roberta-large-meetingbank`
- `models/llmlingua-2-bert-base-multilingual-cased-meetingbank`

These `models/` folders are local-only runtime assets and must not be committed.

## 5. Validation summary

The Task91B readiness pass confirmed the following:

- Imports passed.
- `compileall` passed.
- `PYTHONPATH=src python scripts/run_mvp.py --help` passed.
- Large compressor CPU load passed.
- Light compressor CPU load passed.
- Target tokenizer load passed.
- Target Qwen3-4B 4-bit NF4 GPU load passed.
- DFlash-R1 `n=1` runner smoke passed.
- CC-DFlash-R2 `n=1` runner smoke with the large compressor passed.
- DFlash-R1 path audit against Task88 passed.

This work did not run any `n=30`, `n=100`, or full benchmark expansion.

## 6. DFlash path audit

The DFlash path audit was performed against the real project runner and the existing Task88 DFlash artifact path rather than by relying on direct draft-model probing alone.

Validated runner/path facts:

- `DFlash-R1` maps to `generation_mode="dflash"` and `uses_draft=true`.
- `scripts/run_mvp.py` loads the draft model and calls `dflash_generate(...)`.
- Fresh artifact rows expose real speculative-decoding evidence fields, including `draft_path`, numeric `tau_mean`, and non-empty `acceptance_lengths`.

Comparison against Task88 `gsm8k_short` DFlash-R1 `n=30`:

- Task88 `tokens_per_second` average: `54.74`
- New 3-run audit `tokens_per_second` average: `67.25`
- Task88 `tau_mean` average: `5.21`
- New 3-run audit `tau_mean` average: `6.04`
- Task88 VRAM allocated/reserved average: `3.51 / 3.84 GiB`
- New 3-run audit VRAM allocated/reserved average: `3.50 / 3.74 GiB`

Prefill caveat:

- New `t_prefill_ms` average: `250.32`
- Task88 `t_prefill_ms` average: `110.61`

This higher tiny-run prefill value is acceptable for a repeated-seed `n=1` path audit and does not invalidate the DFlash-path conclusion. The audit goal was to verify that the real DFlash execution path was active and producing the expected speculative fields, not to replace Task88 latency evidence.

## 7. Caveats

- The Chat/Codex shell may not see GPU even when the VS Code integrated terminal does.
- GPU runs should be launched from a shell where both `nvidia-smi` and `torch.cuda.is_available()` pass.
- `flash_attn` is not installed; the `torch.sdpa` fallback is acceptable for setup validation but may be slower.
- The `torch_dtype` deprecation warning observed during setup is non-blocking for this task.
- Direct draft `AutoModelForCausalLM` loading produced missing `lm_head` and embedding warnings, so direct draft generation is not treated as a correctness proof. The project runner remains the source of truth for DFlash path validation.

## 8. Task92 handoff

Task92 should integrate and compare the lighter compressor candidate:

- `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- Local path: `models/llmlingua-2-bert-base-multilingual-cased-meetingbank`

Task92 should compare that lighter compressor against the current large compressor path:

- `models/llmlingua-2-xlm-roberta-large-meetingbank`

Task92 goals:

- Reduce `T_compress`
- Preserve enough compression to remain useful
- Keep the quality proxy near Baseline-AR
- Improve end-to-end feasibility without making final benchmark claims yet

## 9. Artifact locations

- Report: `docs/reports/phase_2_system_optimization/91b-linux-gpu-readiness-and-dflash-path-audit-report.md`
- Results base: `results/phase_2_system_optimization/readiness_and_gate/task91b_linux_gpu_readiness/`
- Smoke artifacts: `results/phase_2_system_optimization/readiness_and_gate/task91b_linux_gpu_readiness/smoke/`
- DFlash path audit artifacts: `results/phase_2_system_optimization/readiness_and_gate/task91b_linux_gpu_readiness/dflash_path_audit/`

Local diagnostic logs may exist under `logs/`, but they are local-only support files and are not primary committed artifacts for Task91B.

## 10. Claim boundary

- No final benchmark claim
- No final speedup claim
- No deployment or confirmed 8GB claim
- No QMSum semantic correctness claim
- No `n=30`, `n=100`, or full benchmark was run in Task91B
