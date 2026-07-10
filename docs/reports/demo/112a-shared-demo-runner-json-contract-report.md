# T112A: Shared Demo Runner and JSON Contract

## 1. Purpose
The goal of Task 112A is to refactor the existing CC-DFlash benchmark execution paths into a single reusable demo execution layer. This layer must support arbitrary interactive prompts, dataset rows, and three demo conditions (`baseline_ar`, `dflash_r1`, `cc_dflash_r2`) while exposing a canonical JSON/JSONL/CSV result contract to be shared by future notebooks and web UIs.

## 2. Pre-existing benchmark architecture
The existing benchmark execution was deeply coupled to dataset iteration logic inside `scripts/run_mvp.py`. The models were loaded manually, and evaluation assumed dataset-specific structure (like GSM8K or QMSum expected formats). The existing metrics and token counting were hardcoded inside the generation loop.

## 3. Reused production modules
The shared demo runner reuses:
- `ccdf.dflash.loader`: `load_target`, `load_draft`, `load_tokenizer`
- `ccdf.dflash.generate`: `dflash_generate`
- `ccdf.compression.llmlingua`: `LLMLinguaCompressor`
- `scripts.eval_datasets`: Dataset specific prompt preparation rules (extracted into adapters)

## 4. New shared demo architecture
Created the `ccdf.demo` package containing:
- `contracts.py`: Defines the `RunRequest` schema.
- `condition_registry.py`: Centralizes definition and metadata for the three demo conditions.
- `prompt_profiles.py`: Manages raw, GSM8K, and QMSum-specific prompt suffix policies safely.
- `model_manager.py`: Encapsulates 4-bit loading, model caching, and condition-specific cleanup to ensure the runner stays within 8GB VRAM limits.
- `metrics.py`: Consolidates throughput, elapsed time, and VRAM measurement context managers.
- `runner.py`: Implements the `DemoRunner` which performs sequential execution and builds the canonical output JSON.
- `writers.py`: Implements JSON, append-safe JSONL, and flat CSV writers.
- `adapters/`: Contains mapping functions translating interactive prompts and dataset rows into `RunRequest`s.

## 5. Request contract
The canonical `RunRequest` mandates `schema_version="cc_dflash_demo_v1"`, and encapsulates `source_type`, `condition`, `prompt_profile`, `prompt`, `reference_answer`, `max_new_tokens`, `seed`, and nested options/metadata.

## 6. Result and CSV contracts
The JSON output guarantees a stable structure encompassing `source`, `request`, `response`, `tokens`, `timing_ms`, `throughput`, `resources`, `quality`, and `status`. Missing metrics default to `null` and not `0`. The flattened CSV representation provides deterministic header ordering, enabling direct ingestion by analytics scripts.

## 7. Condition semantics
Three locked identifiers are supported:
- `baseline_ar`: No compression, Auto-regressive.
- `dflash_r1`: No compression, Speculative decoding (DFlash).
- `cc_dflash_r2`: Light LLMLingua compression (keep rate 0.5), Speculative decoding.

## 8. Prompt-profile safety
Prompt suffix policies are isolated:
- `raw`: Leaves user prompts unmodified.
- `gsm8k_concise_final_answer_v1`: Appends numeric extraction prompt.
- `qmsum_demo_safe`: Appends the exact evidence-focused instruction.

## 9. Dataset adapter design
The `adapters` package bridges the gap between raw dataset rows and the `RunRequest` contract without polluting the runner itself. Adapters for `interactive`, `gsm8k`, and `qmsum` format prompts safely while preserving original context as metadata.

## 10. Model lifecycle
The `ModelManager` orchestrates initialization and teardown based on the selected condition. It loads only what is necessary, avoids loading the heavy validation judge, and cleans up the compressor/draft model during sequential execution to prevent VRAM accumulation on the 8GB GPU.

## 11. Tests
Unit tests were implemented in `tests/test_task112a_shared_demo_runner.py` leveraging a robust `dry_run` model stubbing capability. They cover request validation, identical logical prompting, dataset adapter translation, metric population rules, and schema consistency across formats without downloading real models.

## 12. Real smoke result
A real smoke execution over the three conditions was performed using the prompt: `Explain speculative decoding in two concise sentences.`
The execution successfully loaded Qwen3-4B models in 4-bit, generated outputs sequentially within the memory limit, and successfully serialized the canonical JSON outputs into `results/charts/task112a_shared_demo_runner/real_smoke/`.

## 13. Limitations and claim boundary
- The runner introduces a shared execution interface for demonstrations but does not constitute a global default switch for the overall architecture.
- CC-DFlash does not universally win; execution success over one prompt demonstrates operability, not semantic correctness.
- The pipeline limits execution to sequential condition evaluation.

## 14. Next task
T112B - Notebook Usage Demo
