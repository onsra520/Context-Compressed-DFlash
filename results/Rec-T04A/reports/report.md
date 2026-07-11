# Rec-T04A - Compression Architecture Reconstruction

Status: PASS

## Scope

Rec-T04A rebuilt the CC-DFlash compression architecture around structured prompt parts. The compressor only receives and returns `context`; question and instruction are preserved by the canonical renderer.

No compressor backend returns a full prompt. The final CC-DFlash prompt is reconstructed by replacing only the context field.

## Implementation

- Added `src/ccdf/prompts/` with `PromptParts` and canonical renderer.
- Added `src/ccdf/compression/` with schemas, base interface, passthrough control, deterministic chunking, LLMLingua wrapper, registry, and validation.
- Added tests in `tests/test_rec_t04a_compression_contract.py`.

## Compressor Contract

Compression interface:

```python
compress(context: str, question: str, config: CompressionConfig) -> CompressionResult
```

`CompressionResult` separates:

- `compressed_context`
- segment token counts and tokenizer ID
- compression factor and retained ratio
- chunk count
- compression timing
- backend metadata
- explicit bypass state

LLMLingua uses local model path:

`models/llmlingua-2-bert-base-multilingual-cased-meetingbank`

Question handling:

- `question` is passed as conditioning.
- `concate_question=False`
- question is not concatenated into compressed chunks.

## Prompt Invariants

Artifact: `results/Rec-T04A/prompt_invariant_audit.csv`

All audited prompts passed:

- question occurrence: `1`
- instruction occurrence: `1`
- meeting marker preserved
- question marker preserved
- only context changed

Fixtures:

- GSM8K fixture: passthrough short-context bypass
- QMSum short fixture: LLMLingua compression
- QMSum long fixture: LLMLingua compression

## Token Scope

Artifact: `results/Rec-T04A/token_scope_audit.csv`

Token scopes are separated:

- segment scope uses LLMLingua tokenizer for compression metrics;
- full prompt scope uses target tokenizer for prompt metrics.

Observed full-prompt reductions:

- GSM8K passthrough: `0.0%`
- QMSum short: `52.37%`
- QMSum long: `52.45%`

## Single-Prompt Smokes

Artifact: `results/Rec-T04A/single_prompt_smokes.jsonl`

Three smokes passed:

- GSM8K passthrough control
- QMSum short LLMLingua compression
- QMSum long LLMLingua compression

Each smoke rendered a final prompt and used the Rec-T03A DFlash runtime path with `max_new_tokens=1` to prove routing compatibility.

## Caveat

The LLMLingua tokenizer emitted a warning for long QMSum context token length above the model positional setting during token counting/compression. The chunking layer split context into deterministic 180-word chunks and the compression run completed. This warning is retained in `results/Rec-T04A/logs/single_prompt_smokes.err`.

## Checks

Commands:

```bash
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q tests/test_rec_t04a_compression_contract.py
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python <single_prompt_smokes_script>
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q
```

Results:

- Focused Rec-T04A tests: `5 passed`
- Full available test suite: `40 passed`
- Single-prompt smokes: `3/3 passed`

## Gate Decision

PASS.

Gate evidence:

- only context is compressed;
- question and instruction each occur exactly once;
- passthrough is equivalent;
- question is not repeated across chunks;
- markers are preserved;
- segment/full-prompt token scopes are separate;
- compression latency is measured;
- single-prompt smokes pass;
- CC-DFlash routing uses the Rec-T03A DFlash runtime path.
