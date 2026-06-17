# DFlash Raw-Free Split Audit Report

Date: 2026-06-03

## Conclusion

**PASS**

The raw-free DFlash split implementation satisfies the audit goals for the production split modules:

- `src/ccdf/dflash/*.py` does not depend on `model_raw.py` or `benchmark_raw.py`.
- No `NotImplementedError` placeholder remains in production DFlash split modules.
- The requested core symbols are present in split modules and AST-identical to the raw reference symbols.
- `ccdf.dflash` uses lazy exports and does not load `torch` or `transformers` on plain `import ccdf.dflash`.
- Focused tests pass without requiring model weights.

## Files Inspected

- `src/ccdf/model_raw.py`
- `src/ccdf/benchmark/benchmark_raw.py`
- `src/ccdf/dflash/__init__.py`
- `src/ccdf/dflash/attention.py`
- `src/ccdf/dflash/generate.py`
- `src/ccdf/dflash/loader.py`
- `src/ccdf/dflash/model.py`
- `src/ccdf/dflash/utils.py`
- `tests/test_dflash_core.py`
- `docs/reports/09-dflash-raw-free-split-implementation-report.md`

No archive, backup, old, deprecated, or similarly forbidden folder was read, scanned, grepped, indexed, or used.

## Raw Dependency Scan Result

Requested scan result:

```text
scan: []
```

Additional targeted source scan found no production DFlash references to:

- `ccdf.model_raw`
- `ccdf.benchmark.benchmark_raw`
- `model_raw`
- `benchmark_raw`

The only remaining raw-name strings found in the audited scope are inside the test guard itself and report text, not production `src/ccdf/dflash/*.py` modules.

## Remaining `NotImplementedError` Result

Requested scan included `NotImplementedError` and returned:

```text
scan: []
```

No placeholder `NotImplementedError` remains in production DFlash split modules.

## Symbol Mapping Status

All requested symbols were found and compared against `src/ccdf/model_raw.py` with AST attributes excluded. Each comparison returned `ast_equal=True`.

- `DFlashDraftModel` -> `src/ccdf/dflash/model.py`
- `Qwen3DFlashDecoderLayer` -> `src/ccdf/dflash/model.py`
- `Qwen3DFlashAttention` -> `src/ccdf/dflash/attention.py`
- `apply_rotary_pos_emb` -> `src/ccdf/dflash/attention.py`
- `dflash_generate` -> `src/ccdf/dflash/generate.py`
- `_cuda_time` -> `src/ccdf/dflash/generate.py`
- `build_target_layer_ids` -> `src/ccdf/dflash/utils.py`
- `extract_context_feature` -> `src/ccdf/dflash/utils.py`
- `sample` -> `src/ccdf/dflash/utils.py`

## Mechanical Split Assessment

The split appears mechanical for the DFlash core symbols:

- `attention.py` contains raw-equivalent `apply_rotary_pos_emb` and `Qwen3DFlashAttention`.
- `generate.py` contains raw-equivalent `_cuda_time` and `dflash_generate`, with helper imports adapted to `.utils`.
- `model.py` contains raw-equivalent `Qwen3DFlashDecoderLayer` and `DFlashDraftModel`, with imports adapted to `.attention`, `.generate`, and `.utils`.
- `utils.py` contains raw-equivalent utility functions.
- `loader.py` implements a minimal loader path derived from `benchmark_raw.py` rather than benchmark execution features.

No missing class/function dependency was found during compile, import, or focused test verification.

## Test Meaningfulness

`tests/test_dflash_core.py` is meaningful for split-contract coverage:

- It checks no raw references exist in `src/ccdf/dflash/*.py`.
- It checks key split symbols and lazy exports.
- It checks basic utility behavior for layer spacing, hidden-state extraction, raw-compatible error behavior, and greedy sampling.
- It avoids model weights and does not require real target/draft model loading.

Remaining gap:

- It does not execute a real DFlash generation pass with model weights.
- It does not instantiate `DFlashDraftModel` with a full Qwen config.
- It does not validate numerical parity of attention/generation at runtime.

## Export Surface

`ccdf.dflash.__all__` exports the expected public API:

- `DFlashDraftModel`
- `Qwen3DFlashAttention`
- `Qwen3DFlashDecoderLayer`
- `apply_rotary_pos_emb`
- `build_target_layer_ids`
- `dflash_generate`
- `extract_context_feature`
- `load_all`
- `load_draft`
- `load_target`
- `load_tokenizer`
- `sample`
- `spec_generate`

Plain package import behavior:

```text
torch_loaded_after_import_ccdf_dflash: False
transformers_loaded_after_import_ccdf_dflash: False
```

This confirms that `import ccdf.dflash` itself does not trigger heavyweight model-loading imports.

## Tests Run

```bash
python3 -m compileall src tests scripts
```

Result: **PASS**

```bash
PYTHONPATH=src python3 -c "import ccdf; import ccdf.dflash"
```

Result: **PASS**

```bash
PYTHONPATH=src python3 - <<'PY'
import pathlib
bad = []
for p in pathlib.Path("src/ccdf/dflash").glob("*.py"):
    text = p.read_text(encoding="utf-8")
    for needle in ["model_raw", "benchmark_raw", "NotImplementedError"]:
        if needle in text:
            bad.append((str(p), needle))
print("scan:", bad)
raise SystemExit(1 if bad else 0)
PY
```

Result: **PASS**

```text
scan: []
```

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q
```

Result: **PASS**

```text
6 passed, 2 warnings in 3.31s
```

## Safe to Commit

Yes, the DFlash raw-free split audit result is safe to commit from a code-audit standpoint.

Commit caveat:

- `README.md` is modified in the worktree but was unrelated to this audit. Do not include it in a DFlash split commit unless that change is intentional.

## Next Action for Real `synthetic_probe.py`

The next action is to add a real, model-aware synthetic probe path that uses `src/ccdf/dflash/loader.py` and split DFlash modules only.

Before that probe can be considered real execution coverage, it needs:

- accessible target and draft model IDs or local model paths;
- tokenizer availability;
- CUDA-capable runtime for the DFlash timing/generation path;
- a tiny prompt and `max_new_tokens` setting suitable for a smoke test;
- an assertion that the probe does not import or call `*_raw.py`.
