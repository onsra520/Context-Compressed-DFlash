# Task 91 — Lighter Compressor Feasibility Setup Report

## 1. Objective

The objective of Task 91 is to prepare the CC-DFlash repository for Phase 2 system optimization by adding config and loader compatibility for a lighter compressor candidate. This enables safely comparing compressor profiles in downstream tasks without breaking any existing Phase 1 runners or benchmarks.

## 2. Why T91 Starts with Config Compatibility

To guarantee clean, reproducible experiments, we must avoid hardcoding experimental settings. By defining distinct configuration profiles (`large_llmlingua` vs `light_llmlingua`) and upgrading the loader to support profile-based resolution, we ensure:

- The system can target different compressors cleanly via CLI/config changes.
- All pre-existing test suites and runners continue to function automatically without breakage.

## 3. Old vs New Compression Config

### Old Config Shape (Legacy)

```yaml
compression:
  strategy: passthrough
  keep_rate: 1.0
  llmlingua:
    model_name: microsoft/llmlingua-2-xlm-roberta-large-meetingbank
    device_map: cpu
    use_llmlingua2: true
    default_keep_rate: 0.5
```

### New Config Shape (Task 91)

```yaml
compression:
  strategy: passthrough
  keep_rate: 1.0
  large_llmlingua:
    model_name: microsoft/llmlingua-2-xlm-roberta-large-meetingbank
    device_map: cpu
    use_llmlingua2: true
    default_keep_rate: 0.5
  light_llmlingua:
    model_name: microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank
    device_map: cuda:0
    use_llmlingua2: true
    default_keep_rate: 0.5
```

## 4. Backward Compatibility Behavior

We implemented a robust config resolver `resolve_llmlingua_config(config, profile)` supporting the following:

- **Default Profile:** If no profile is explicitly selected, the loader defaults to `large`, keeping Phase 1 runner behavior unchanged.
- **Legacy Fallback:** If the new configuration block `large_llmlingua` is missing but the legacy `llmlingua` block is present, the resolver seamlessly falls back to using the legacy config block when `large` is requested.
- **Explicit CLI Flag:** Added `--compressor-profile` choice argument (`large`, `large_llmlingua`, `light`, `light_llmlingua`) to `scripts/run_mvp.py` to allow clean runtime selection of compressor configs.
- **Strict Error Handling:** If `light` is requested but `light_llmlingua` is not configured (e.g. when parsing an old config file), a clear error is raised:
  `Requested compressor profile 'light' but compression.light_llmlingua is not configured.`

## 5. Lighter Compressor Candidate

- **Current Large Compressor:** `microsoft/llmlingua-2-xlm-roberta-large-meetingbank`
- **Candidate Lighter Compressor:** `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank`

The BERT-base-multilingual-cased model has significantly fewer parameters, offering the potential to reduce online prompt compression latency $T_{\text{compress}}$.

## 6. Device/Runtime Notes

- The new configuration specifies `device_map: cuda:0` for the lighter compressor candidate.
- Config loading and parsing do not require CUDA to be present (permitting safe CPU-only dry-runs and unit tests).
- Actual Hugging Face model loading is deferred to runtime initialization and is bypassed during testing.

## 7. Tests Added

We added the following test cases to `tests/test_compression.py`:

1. Old config shape works (resolving `large` to legacy `llmlingua` model settings).
2. New config shape works for both `large` and `light` profiles.
3. Default profile correctly resolves to `large`.
4. Requesting `light` with only the old config shape raises the expected error.
5. Profile aliases (`large_llmlingua` == `large`, `light_llmlingua` == `light`) resolve correctly.
6. `LLMLinguaCompressor.from_config()` supports the new `profile` keyword parameter.

## 8. What T91 Does Not Claim Yet

- **T91 does not prove that the lighter compressor is faster.**
- **T91 does not prove that the lighter compressor preserves quality.**
- **T91 only prepares the config and runner path so T92/T93 can measure those questions safely.**

## 9. Next Task

- **Task 92 — Lighter Compressor Integration:** Integrate and test model loading for the lighter compressor candidate, validating that it runs correctly on the target device.
