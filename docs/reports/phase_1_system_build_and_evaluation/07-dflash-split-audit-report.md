# DFlash Split Audit Report

Date: 2026-06-03

Scope: audit only. No feature implementation was performed.

Upstream reference used for comparison:

- Repository: `https://github.com/z-lab/dflash.git`
- Commit: `94e4abc5e0c31b67bc1a9d30f1cc34ece28a8756`
- Upstream files:
  - `dflash/model.py`
  - `dflash/benchmark.py`

Note: the project instruction refers to upstream `model/dflash.py`; the current upstream repository at the audited commit stores that code in `dflash/model.py`.

## Summary

Conclusion: **PARTIAL**

Raw files match upstream semantically, but the split modules do not yet preserve the raw DFlash implementation. Most split files are still skeleton placeholders, and `src/ccdf/dflash/generate.py` imports from `src/ccdf/model_raw.py`, which violates the import requirement.

## Raw File to Split File Mapping

| Raw / upstream source | Current split target | Status |
| --- | --- | --- |
| `dflash/model.py` / `src/ccdf/model_raw.py` utilities | `src/ccdf/dflash/utils.py` | Partial: `build_target_layer_ids` and `sample` match raw AST; `extract_context_feature` was changed. |
| `dflash/model.py` / `src/ccdf/model_raw.py` generation loop | `src/ccdf/dflash/generate.py` | Not split: wrapper calls `..model_raw.dflash_generate`. |
| `dflash/model.py` / `src/ccdf/model_raw.py` attention | `src/ccdf/dflash/attention.py` | Not split: skeleton placeholder only. |
| `dflash/model.py` / `src/ccdf/model_raw.py` draft model | `src/ccdf/dflash/model.py` | Not split: skeleton placeholder only. |
| `dflash/benchmark.py` / `src/ccdf/benchmark/benchmark_raw.py` model/tokenizer loading inside `_run_transformers` | `src/ccdf/dflash/loader.py` | Not split: loader functions raise `NotImplementedError`. |

## Raw Parity Check

`src/ccdf/model_raw.py` vs upstream `dflash/model.py`:

- AST equality: **true**
- Diff observed: formatting only.
- Conclusion: raw model file corresponds to upstream source logic.

`src/ccdf/benchmark/benchmark_raw.py` vs upstream `dflash/benchmark.py`:

- AST equality: **true**
- Diff observed: formatting only.
- Conclusion: raw benchmark file corresponds to upstream source logic.

## Functions and Classes Moved

Moved with matching raw AST:

- `build_target_layer_ids` -> `src/ccdf/dflash/utils.py`
- `sample` -> `src/ccdf/dflash/utils.py`

Moved but modified:

- `extract_context_feature` -> `src/ccdf/dflash/utils.py`
  - Raw behavior: iterates `layer_ids` directly.
  - Split behavior: uses `layer_ids or []`.
  - Impact: changes failure behavior for `None`; raw would error, split returns an empty selection and then fails at `torch.cat` differently.

Present but not moved from raw:

- `spec_generate` in `src/ccdf/dflash/generate.py`
  - This name does not exist in raw.
  - It wraps `dflash_generate` from `..model_raw`.

New loader stubs:

- `load_target`
- `load_draft`
- `load_tokenizer`
- `load_all`

These are not direct functions in upstream `dflash/benchmark.py`; they were intended to be extracted from the model/tokenizer loading logic inside `_run_transformers`, but currently raise `NotImplementedError`.

## Functions and Classes Still Missing From Split

From `src/ccdf/model_raw.py` / upstream `dflash/model.py`:

- `_cuda_time`
- `dflash_generate`
- `apply_rotary_pos_emb`
- `Qwen3DFlashDecoderLayer`

Present only as placeholders or wrappers, not real moved logic:

- `DFlashDraftModel`
- `Qwen3DFlashAttention`
- generation loop logic from `dflash_generate`

From `src/ccdf/benchmark/benchmark_raw.py` / upstream `dflash/benchmark.py`:

- Real target model loading logic from `_run_transformers`
- Real draft model loading logic from `_run_transformers`
- Real tokenizer loading logic from `_run_transformers`
- Attention implementation selection via `_get_transformers_attn_impl`
- Transformers model support validation via `_check_transformers_model`

## Logic Modified Compared With Raw

Modified:

- `src/ccdf/dflash/utils.py::extract_context_feature`
  - Adds `layer_ids or []`, which is not in raw.

Not preserved:

- `src/ccdf/dflash/model.py::DFlashDraftModel`
  - Raw class inherits `Qwen3PreTrainedModel`, builds `Qwen3DFlashDecoderLayer` modules, projects target hidden states, owns `block_size` and `mask_token_id`, and delegates generation to `dflash_generate`.
  - Split class is a dataclass placeholder and `from_pretrained` raises `NotImplementedError`.

- `src/ccdf/dflash/attention.py::Qwen3DFlashAttention`
  - Raw class inherits `nn.Module`, creates Q/K/V/O projections, applies Qwen RMSNorm, rotary embeddings, cache update, and attention function dispatch.
  - Split class is a placeholder and raises `NotImplementedError`.

- `src/ccdf/dflash/generate.py::spec_generate`
  - Does not contain the DFlash generation loop.
  - Calls `..model_raw.dflash_generate`, then reshapes return data.

- `src/ccdf/dflash/loader.py`
  - Contains only `NotImplementedError` stubs.

## Import Graph Audit

Circular imports:

- None detected by static import graph over `src/ccdf/**/*.py`.

Imports from raw files:

- **Violation:** `src/ccdf/dflash/generate.py:9` imports `ccdf.model_raw`.

Relevant graph:

- `ccdf.dflash` -> `ccdf.dflash.attention`, `ccdf.dflash.generate`, `ccdf.dflash.loader`, `ccdf.dflash.model`, `ccdf.dflash.utils`
- `ccdf.dflash.generate` -> `ccdf.model_raw`

`src/ccdf/__init__.py`:

- Does not import from `*_raw.py`.
- Exports only package-level public APIs for config/compression:
  - `load_config`
  - `CompressorBase`
  - `PassthroughCompressor`
  - `segment_gsm8k`
  - `merge`
- It does not export DFlash raw internals.

`src/ccdf/dflash/__init__.py`:

- Exports split-module names through lazy `__getattr__`.
- However, some exported names resolve to placeholders or a wrapper that imports raw code.

## Verification Commands

Requested command:

```bash
python -m compileall src tests scripts
```

Result: **PASS**

Requested command:

```bash
python -c "import ccdf; import ccdf.dflash"
```

Result: **FAIL in the current shell**

Error:

```text
ModuleNotFoundError: No module named 'ccdf'
```

Follow-up environment check:

```bash
PYTHONPATH=src python3 -c "import ccdf; import ccdf.dflash"
```

Result: **PASS**

Requested command:

```bash
pytest tests/test_dflash_core.py -q
```

Result: **FAIL in the current shell**

Error:

```text
/bin/bash: line 1: pytest: command not found
```

Follow-up environment check:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q
```

Result: **PASS**

Output:

```text
3 passed in 1.55s
```

## Test Coverage Note

`tests/test_dflash_core.py` currently covers only:

- `build_target_layer_ids`
- `extract_context_feature`
- `sample`

It does not exercise real DFlash model construction, attention, speculative generation, loader behavior, or raw-free split-module execution.

## Next Action for `scripts/synthetic_probe.py`

Current probe status:

```bash
PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml
```

Result:

```text
Loaded config keys: benchmark, compression, model, runtime
Skeleton import/config check completed. Real Gate 0 has NOT been run.
```

Next action:

1. Replace split placeholders with raw-free DFlash logic copied from upstream/raw.
2. Remove the `src/ccdf/dflash/generate.py` import from `..model_raw`.
3. Implement `src/ccdf/dflash/loader.py` from the upstream `_run_transformers` loading path.
4. Add a synthetic probe mode that imports and exercises split modules only, without touching `model_raw.py`.
5. Run:

```bash
PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml
```

Until the split modules are real and raw-free, `scripts/synthetic_probe.py` remains an import/config skeleton check, not a DFlash execution check.
