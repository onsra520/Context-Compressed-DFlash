# HTFSD Phase 0-2 MVP Design

Date: 2026-05-15

## 1. Scope And Runtime

This MVP covers Phase 0 through Phase 2 of HTFSD:

```text
prompt
  -> Qwen3-0.6B D-Flash draft
  -> strict D-Flash parse
  -> Gemma E2B retokenize + greedy exact-match verify
  -> accept prefix or fallback one Gemma E2B token
  -> repeat until max_new_tokens/EOS
  -> final output
```

Gemma E4B appears only in a separate Phase 0 autoregressive baseline benchmark:

```text
prompt_set -> Gemma E4B autoregressive -> baseline metrics
```

Gemma E4B is not part of the Low Tier interactive loop in Phase 0-2. The CLI and Python API should leave room for a future side-by-side E4B comparison option, but this MVP must not route Low Tier generation through Gemma E4B.

Interactive Low Tier greedy output is Gemma E2B greedy-equivalent, not Gemma E4B-equivalent. Phase 0-2 must not claim lossless generation or speedup against Gemma E4B. Gemma E4B baseline metrics are recorded separately.

Runtime decisions:

- vLLM is the primary backend for Qwen, Gemma E2B, and the Gemma E4B baseline.
- Model configuration uses `model_id_or_path`, supporting both Hugging Face IDs and local paths.
- The default execution mode loads Qwen and Gemma E2B concurrently.
- A sequential execution mode may exist for constrained VRAM or debugging, but its metrics are labeled debug/non-comparable.
- The default decoding mode is greedy.
- Sampling may exist only as experimental interactive mode and is not used for correctness metrics or speedup claims.

Includes:

- interactive generate mode
- batch Low Tier benchmark mode
- Gemma E4B autoregressive baseline benchmark
- strict D-Flash parser
- greedy exact-match verifier
- one-token Gemma E2B fallback
- metrics and logging

Excludes:

- High Tier
- EAGLE head
- hidden-state promotion
- Gemma E4B verification inside the HTFSD loop
- lossless equivalence claims against Gemma E4B
- sampling-based correctness or speedup claims

## 2. Core Components And Interfaces

Core logic lives in a Python package. CLI commands are thin wrappers over the Python API.

Package components:

```text
htfsd.config
  -> load YAML config, model_id_or_path, runtime mode, decoding params

htfsd.types
  -> result, token, verification, trace, and metrics dataclasses

htfsd.dflash
  -> D-Flash envelope parsing and Qwen prompt templates

htfsd.runtime.vllm
  -> vLLM model handles, generation adapter, verification adapter

htfsd.tokenization
  -> Gemma tokenizer boundary for encoding candidates and decoding output

htfsd.low_tier
  -> Qwen drafter, Gemma E2B verifier, acceptance policy, LowTierEngine

htfsd.metrics
  -> timers, counters, summaries

htfsd.benchmarks
  -> Gemma E4B baseline benchmark and Low Tier batch benchmark

htfsd.cli
  -> generate, benchmark-low, baseline-e4b command wrappers
```

Core result dataclasses must be defined up front and kept in one place, preferably `src/htfsd/types.py`:

- `GenerateResult`
- `DraftResult`
- `DFlashParseResult`
- `VerificationResult`
- `TokenResult`
- `StageMetrics`
- `GenerationMetrics`

Example Python API:

```python
from htfsd.config import load_config
from htfsd.low_tier import LowTierEngine

config = load_config("configs/local.yaml")
engine = LowTierEngine.from_config(config)

result = engine.generate(
    prompt="Liet ke cac tinh Viet Nam",
    max_new_tokens=128,
    decoding="greedy",
)
print(result.text)
print(result.metrics)
```

`LowTierEngine.generate(...)` returns a `GenerateResult` containing:

- `text`
- `token_ids`
- `metrics`
- optional `trace` when debug trace is enabled

The `LowTierEngine` owns the loop:

```text
for each cycle:
  1. ask QwenDFlashDrafter for one D-Flash envelope
  2. parse envelope strictly
  3. retokenize draft_text with the Gemma tokenizer
  4. verify candidate prefix with Gemma E2B greedy exact-match
  5. append accepted prefix if non-empty
  6. otherwise append one Gemma E2B greedy fallback token
  7. record metrics
```

The vLLM-specific risk is isolated in `VllmVerificationAdapter`. Its stable internal contract works primarily on Gemma token IDs:

```python
verify_greedy_prefix(
    context_token_ids: list[int],
    candidate_token_ids: list[int],
) -> VerificationResult
```

It also exposes a fallback method:

```python
greedy_next_token(context_token_ids: list[int]) -> TokenResult
```

Text is used at boundaries only:

- user prompt input
- Qwen D-Flash `draft_text`
- final detokenized output
- logs and debug display

CLI commands:

```text
htfsd-generate
htfsd-benchmark-low
htfsd-baseline-e4b
```

## 3. D-Flash And Acceptance Policy

D-Flash MVP uses a strict JSON object. The required field is:

```json
{
  "draft_text": "..."
}
```

Optional fields:

```json
{
  "confidence": 0.82,
  "max_tokens": 8
}
```

Parser policy:

- Accept only valid JSON objects.
- `draft_text` is required and must be a non-empty string after minimal normalization.
- `confidence` is optional. If present, it must be a number in `[0, 1]`. It is logged only and does not affect MVP acceptance.
- `max_tokens` is optional. If present, it is clamped by config and caps the number of Gemma candidate tokens verified.
- Parse failure, schema failure, empty draft, or retokenized-empty draft is counted and triggers one-token Gemma E2B greedy fallback.
- The parser must not repair malformed JSON or extract text with regex.

Minimal normalization means:

- strip leading/trailing whitespace
- normalize CRLF to LF if needed
- reject empty string
- do not modify semantic content
- do not repair malformed JSON

The Qwen prompt should request compact JSON only, with no Markdown fence and no prose outside JSON:

```json
{"draft_text":"...","confidence":0.7,"max_tokens":8}
```

Default acceptance policy:

```text
greedy exact-match:
accept candidate token at position i iff
candidate_token_id == argmax GemmaE2B(next-token distribution | context + accepted_prefix)
```

Verification stops at the first mismatch. The matching prefix before the mismatch is accepted. If the accepted prefix is empty, the engine falls back to one Gemma E2B greedy token.

Important guardrails:

- Acceptance happens in Gemma token space.
- Qwen token counts are not used in acceptance metrics.
- Interactive Low Tier greedy output is Gemma E2B greedy-equivalent, not Gemma E4B-equivalent.
- Sampling mode is experimental and not used for benchmark correctness.

## 4. Execution Modes, CLI, And Config

Configuration uses YAML. Example:

```yaml
models:
  qwen_drafter:
    model_id_or_path: "Qwen/Qwen3-0.6B"
    tensor_parallel_size: 1
    dtype: "auto"
    gpu_memory_utilization: 0.35

  gemma_e2b:
    model_id_or_path: "/models/gemma-e2b"
    tensor_parallel_size: 1
    dtype: "auto"
    gpu_memory_utilization: 0.55

  gemma_e4b_baseline:
    model_id_or_path: "/models/gemma-e4b"
    tensor_parallel_size: 1
    dtype: "auto"

runtime:
  backend: "vllm"
  execution_mode: "concurrent"   # concurrent | sequential
  max_context_tokens: 4096
  seed: 1234

generation:
  max_new_tokens: 128
  stop_on_eos: true

dflash:
  parser: "strict_json"
  required_fields: ["draft_text"]
  default_max_tokens: 8
  hard_max_tokens: 16
  experimental_repair: false

low_tier:
  acceptance_policy: "greedy_exact_match"
  fallback_policy: "single_token_greedy"
  fallback_tokens_per_cycle: 1

decoding:
  default: "greedy"
  sampling:
    enabled: true
    experimental: true
    temperature: 0.7
    top_p: 0.9

benchmark:
  fixture_path: "benchmarks/fixtures/prompts.jsonl"
  dataset:
    enabled: false
    name: null
    split: null
```

Execution modes:

- `concurrent` is the default and initializes Qwen and Gemma E2B handles together.
- `sequential` is for constrained VRAM/debug. Metrics must label this mode clearly because latency is not comparable to concurrent mode.

CLI examples:

```text
htfsd-generate --config configs/local.yaml
htfsd-generate --config configs/local.yaml --prompt "Liet ke cac tinh Viet Nam"
htfsd-generate --config configs/local.yaml --prompt "..." --debug-trace runs/trace.jsonl
htfsd-generate --config configs/local.yaml --decoding greedy --max-new-tokens 128
htfsd-generate --config configs/local.yaml --decoding sampling --temperature 0.7

htfsd-benchmark-low --config configs/local.yaml --fixtures benchmarks/fixtures/prompts.jsonl --output runs/low_tier.jsonl
htfsd-baseline-e4b --config configs/local.yaml --fixtures benchmarks/fixtures/prompts.jsonl --output runs/e4b_baseline.jsonl
```

Interactive behavior:

- If `--prompt` is absent, `htfsd-generate` opens a simple prompt loop.
- Each run prints final output and a compact metrics summary.
- `--debug-trace` writes per-cycle trace JSONL.
- CLI does not own the decoding loop.

Guardrails:

- `benchmark-low` runs greedy only in the MVP.
- Sampling is interactive experimental only.
- Sequential mode is not used for primary latency or speedup claims.
- `configs/local.example.yaml` should run after the user replaces `model_id_or_path` values for the local environment.
- The example config must clearly show concurrent as default, sequential as debug-only, greedy as default, and sampling as experimental.

## 5. Metrics, Outputs, And Testing

Metrics are split into three levels:

- per-cycle trace
- per-request summary
- batch benchmark JSONL

Per-cycle trace includes:

```json
{
  "cycle_index": 3,
  "context_tokens": 42,
  "dflash_parse_ok": true,
  "malformed_dflash": false,
  "draft_text_chars": 31,
  "draft_candidate_tokens": 8,
  "accepted_tokens": 5,
  "reject_position": 5,
  "candidate_exhausted": false,
  "fallback_used": false,
  "qwen_draft_ms": 18.2,
  "dflash_parse_ms": 0.1,
  "gemma_retokenize_ms": 0.2,
  "e2b_verify_ms": 21.5,
  "cycle_ms": 40.0
}
```

Reject metadata:

- `reject_position = null` and `candidate_exhausted = true` means the entire candidate matched.
- `reject_position = 0` means the first candidate token was rejected.
- `reject_position = n` means `n` tokens were accepted and the next token was rejected.

Malformed D-Flash breakdown:

- `malformed_dflash_count`
- `dflash_parse_fail_count`
- `dflash_schema_invalid_count`
- `dflash_empty_draft_count`
- `retokenized_empty_count`

Per-request `GenerateResult.metrics` includes:

- `generated_tokens`
- `cycles`
- `drafted_candidate_tokens`
- `accepted_tokens`
- `fallback_tokens`
- malformed D-Flash breakdown
- `low_acceptance_rate`
- `fallback_rate`
- `total_ms`
- `tokens_per_second`
- `latency_per_token_ms`
- `execution_mode`
- `decoding_mode`

Acceptance rate:

```text
low_acceptance_rate = accepted_tokens / drafted_candidate_tokens
```

`drafted_candidate_tokens` means Gemma candidate tokens after retokenization and after `max_tokens` cap. It is not the Qwen tokenizer count.

Batch benchmark output is JSONL:

- one row per prompt
- prompt id
- prompt length
- generated length
- metrics
- status/error
- run metadata
- optional `greedy_equivalence_pass`
- optional `greedy_equivalence_diff_at`

Greedy equivalence is checked only against Gemma E2B greedy autoregressive reference, not against Gemma E4B.

Gemma E4B baseline benchmark output includes:

- `prompt_id`
- `prompt_tokens`
- `generated_tokens`
- `total_ms`
- `tokens_per_second`
- `latency_per_token_ms`
- `peak_vram_mb` if available
- `output_text` or `output_path`

Testing requirements:

```text
tests/test_dflash_parser.py
  - valid minimal envelope
  - valid optional confidence/max_tokens
  - malformed JSON rejects
  - empty draft_text rejects
  - CRLF normalization
  - no regex repair behavior

tests/test_acceptance_policy.py
  - accepts full matching prefix
  - stops on first mismatch
  - empty prefix triggers fallback path
  - max_tokens cap is respected

tests/test_config.py
  - dflash max_tokens clamp works
  - benchmark-low rejects sampling mode in MVP
  - sequential mode is labeled debug/non-comparable

tests/test_metrics.py
  - counters aggregate correctly
  - malformed/fallback rates computed safely
  - execution_mode and decoding_mode labels preserved

tests/test_tokenization.py
  - retokenize non-empty draft_text into Gemma candidate token IDs
  - empty/whitespace draft is rejected before verification
  - accepted/fallback token IDs decode into stable final text

tests/test_low_tier_engine.py
  - fake drafter/verifier adapters drive the loop
  - loop terminates by max_new_tokens/EOS
  - engine behavior is CLI-independent
  - golden fake verifier covers full match, partial mismatch, immediate reject, malformed D-Flash, retokenized-empty draft, fallback, EOS, max token termination

tests/test_cli.py
  - CLI calls the core engine
  - CLI does not duplicate loop logic
  - --output writes JSONL
  - --debug-trace writes per-cycle JSONL
```

vLLM integration tests are optional/marked because they require GPU access and model downloads. Unit tests use fakes for fast local/CI runs.

## 6. MVP Deliverables And File Layout

File layout:

```text
configs/
  local.example.yaml

src/htfsd/
  __init__.py
  config.py
  types.py

  dflash/
    __init__.py
    parser.py
    prompts.py

  runtime/
    __init__.py
    vllm_adapter.py

  tokenization/
    __init__.py
    gemma.py

  low_tier/
    __init__.py
    drafter.py
    verifier.py
    engine.py
    acceptance.py

  metrics/
    __init__.py
    timers.py
    counters.py

  benchmarks/
    __init__.py
    baseline_e4b.py
    low_tier.py
    fixtures.py

  cli/
    __init__.py
    generate.py
    benchmark_low.py
    baseline_e4b.py

benchmarks/
  fixtures/
    prompts.jsonl

tests/
  test_dflash_parser.py
  test_acceptance_policy.py
  test_config.py
  test_metrics.py
  test_tokenization.py
  test_low_tier_engine.py
  test_cli.py
```

Phase deliverables and order:

Phase 0: config and Gemma E4B baseline

```text
configs/local.example.yaml
src/htfsd/benchmarks/baseline_e4b.py
src/htfsd/cli/baseline_e4b.py
```

Output:

```text
runs/e4b_baseline.jsonl
```

Phase 1: D-Flash parser, prompt, and drafter

```text
src/htfsd/dflash/parser.py
src/htfsd/dflash/prompts.py
src/htfsd/low_tier/drafter.py
tests/test_dflash_parser.py
```

Phase 2: Low Tier engine, verifier adapter, interactive CLI, batch CLI

```text
src/htfsd/low_tier/engine.py
src/htfsd/low_tier/verifier.py
src/htfsd/runtime/vllm_adapter.py
src/htfsd/tokenization/gemma.py
src/htfsd/cli/generate.py
src/htfsd/cli/benchmark_low.py
```

Outputs:

```text
runs/low_tier.jsonl
runs/trace.jsonl
```

Packaging:

- Use `pyproject.toml`.
- Expose console scripts:
  - `htfsd-generate`
  - `htfsd-benchmark-low`
  - `htfsd-baseline-e4b`
- Core dependencies include `vllm`, `pyyaml`, and either `pydantic` or local validation helpers.
- Dev dependencies include `pytest`.
- Optional benchmark dependencies for dataset support are separated in an optional extra.

Generated artifacts:

- `runs/*.jsonl` files are generated outputs and should not be committed by default.
- `runs/` may be gitignored, or retained with `.gitkeep` if the implementation chooses to keep the directory visible.

Implementation guardrails:

- Do not implement High Tier in this MVP.
- Do not add EAGLE head implementation in this MVP.
- Do not add hidden-state promotion in this MVP.
- Do not claim Phase 0-2 achieves Gemma E4B speedup or lossless behavior.
- Keep `docs/htfsd.md` as the research overview.
- Keep this design spec under `docs/superpowers/specs/`.

## 7. Risks, Open Questions, And Caveats

The main implementation risk is `VllmVerificationAdapter`. The MVP requires greedy exact-match under Gemma E2B, but vLLM public APIs are optimized for generation rather than custom token-by-token verification. This adapter must have a narrow contract and dedicated tests.

Risks and caveats:

1. Greedy verification API shape

   `verify_greedy_prefix(context_token_ids, candidate_token_ids)` must determine the next-token argmax at each candidate position. Candidate verification may use prompt/prefill logprobs, generated logprobs, or a lower-level engine API depending on what the pinned vLLM version supports. The chosen implementation must be validated against Gemma E2B greedy autoregressive reference.

2. Verification equivalence is required before trusting metrics

   Acceptance rate is not trustworthy until `VllmVerificationAdapter` passes an equivalence test against Gemma E2B greedy autoregressive output. If the adapter does not match reference behavior, `benchmark-low` must fail or mark results invalid.

3. Tokenization boundary

   Qwen emits text in D-Flash. Candidate tokens are always Gemma token IDs after retokenization. Qwen token counts must not be used for acceptance metrics.

4. Determinism

   Greedy mode must fix:

   - `temperature=0`
   - seed if the backend uses one
   - stop/EOS behavior
   - `max_new_tokens`
   - tokenizer settings

5. vLLM version drift

   The run metadata must record `vllm_version`. If `prompt_logprobs` or `logprobs` output shape changes, only `runtime/vllm_adapter.py` and related tests should need changes.

6. Concurrent VRAM pressure

   Default concurrent mode may fail on smaller GPUs. Sequential mode exists for debugging, but output metrics must label `execution_mode=sequential` and must not be used for primary latency or speedup claims.

7. D-Flash structured output fragility

   Qwen may emit malformed JSON. MVP does not repair malformed output. Malformed rate is a real metric.

8. Interactive output positioning

   Interactive Phase 0-2 greedy output is Gemma E2B greedy-equivalent. It does not represent Gemma E4B target quality.

9. Sampling mode ambiguity

   Sampling interactive mode is experimental. It is excluded from:

   - `benchmark-low`
   - greedy equivalence checks
   - correctness metrics
   - speedup claims

10. EOS and stop handling

   EOS generated by Gemma E2B fallback should terminate generation if `stop_on_eos=true`. If Qwen draft text retokenizes to EOS-like tokens, the verifier must handle them consistently with Gemma E2B greedy baseline. Stop behavior must match between Low Tier greedy and Gemma E2B reference during equivalence checks.

11. Context growth and max context

   If context exceeds `max_context_tokens`, the MVP must fail clearly or use an explicit truncation policy. It must not silently truncate because that would break greedy equivalence.

Open questions:

- Which exact vLLM API route should candidate verification use: prompt logprobs, generated logprobs, or a lower-level engine API?
- Does the target vLLM version reliably support token-ID prompt inputs for the Gemma tokenizer and verification path?
- Should the adapter get the tokenizer from the vLLM model handle or load it separately from `model_id_or_path`?
- If the tokenizer is loaded separately, how do we ensure tokenizer config matches model runtime config?
- Which concrete Gemma E2B/E4B model IDs or local paths will be used?
- Does the target machine have enough VRAM for concurrent Qwen + Gemma E2B?
- Should optional dataset benchmarking be enabled during initial implementation or left config-only until fixtures pass?

Risk mitigation:

- Start with fake adapters for unit tests.
- Add golden fake verifier tests for full match, partial mismatch, immediate reject, malformed D-Flash, retokenized-empty draft, fallback, EOS, and max token termination.
- Add optional GPU integration tests comparing Gemma E2B greedy autoregressive output and Low Tier output.
- Record run metadata:
  - `verification_adapter_version`
  - `vllm_version`
  - `tokenizer_name_or_path`
  - `model_id_or_path` for each model
  - `prompt_set_version`
  - `git_commit`
  - dtype
  - tensor parallel size
  - execution mode
  - max context tokens
  - max new tokens
  - decoding mode

## 8. Final MVP Acceptance Criteria

Functional acceptance:

- `htfsd-generate` runs an interactive prompt loop.
- `htfsd-generate --prompt "..."` runs one prompt and returns final output.
- Greedy interactive path uses Qwen D-Flash draft, strict parser, Gemma retokenization, Gemma E2B greedy exact-match verifier, and one-token Gemma E2B fallback.
- Malformed D-Flash or rejected candidates do not fail generation. The system falls back to one Gemma E2B greedy token and continues the next cycle unless it reaches EOS or `max_new_tokens`.
- Greedy Low Tier output is Gemma E2B greedy-equivalent, not Gemma E4B-equivalent.
- `htfsd-benchmark-low` runs fixture JSONL and writes JSONL metrics.
- `htfsd-baseline-e4b` runs the separate Gemma E4B autoregressive baseline and writes JSONL metrics.

Correctness acceptance:

- Unit tests pass with fake adapters.
- D-Flash malformed/schema/empty cases are rejected without repair.
- Acceptance stops at first mismatch and reports `reject_position`.
- `low_acceptance_rate = accepted_tokens / drafted_candidate_tokens`, where drafted candidate tokens are Gemma token IDs after retokenization and max-token cap.
- Greedy equivalence check compares Low Tier greedy output against Gemma E2B greedy autoregressive reference.
- Low Tier benchmark is marked valid only if verification adapter equivalence passes.

Metrics acceptance:

- Per-cycle trace includes parse status, draft/accept/reject metadata, fallback flag, and stage latencies.
- Per-request metrics include generated tokens, drafted candidate tokens, accepted tokens, fallback tokens, malformed breakdown, acceptance rate, fallback rate, total latency, tokens/sec, execution mode, and decoding mode.
- Batch JSONL includes prompt id, status/error, metrics, run metadata, and optional greedy equivalence fields.
- Benchmark commands create valid output JSONL even if some prompts error. Prompt-level errors are stored in `status/error` fields and should not discard the whole file unless there is a severe runtime failure.
- Run metadata records model paths, tokenizer path, vLLM version, adapter version, prompt set version, git commit, dtype, TP size, and execution mode.
- `runs/*.jsonl` files are generated artifacts and are not committed by default.

Scope acceptance:

- No High Tier implementation.
- No EAGLE head.
- No hidden-state promotion.
- No Gemma E4B verification inside the HTFSD loop.
- No Phase 0-2 claim of lossless generation or speedup against Gemma E4B.
- Sampling is interactive experimental only and is rejected for `benchmark-low` in MVP.
- Sequential execution mode is labeled debug/non-comparable and is not used for primary latency/speedup claims.

Config acceptance:

- `configs/local.example.yaml` runs after the user replaces `model_id_or_path` values for the local environment.
- The example config clearly shows:
  - `concurrent` as the default execution mode
  - `sequential` as debug/non-comparable
  - greedy as the default decoding mode
  - sampling as experimental

Testing acceptance:

- Required test files:
  - `tests/test_dflash_parser.py`
  - `tests/test_acceptance_policy.py`
  - `tests/test_config.py`
  - `tests/test_metrics.py`
  - `tests/test_tokenization.py`
  - `tests/test_low_tier_engine.py`
  - `tests/test_cli.py`
- Optional GPU/vLLM integration tests are marked and not required for fast unit CI.
- Golden fake verifier tests cover full match, partial mismatch, immediate reject, malformed D-Flash, retokenized-empty draft, fallback, EOS, and max token termination.
