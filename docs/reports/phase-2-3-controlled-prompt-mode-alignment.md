# Phase 2.3 Controlled Prompt Mode Alignment

## Summary

Phase 2.3 added explicit prompt-mode support to controlled trace commands and aligned trace metadata with the actual backend generation path.

Both low-tier and target-baseline traces now accept:

```bash
--prompt-mode raw
--prompt-mode chat
```

`raw` mode remains the default for compatibility and debugging. `chat` mode uses backend chat completion with the model chat template.

## Problem Observed In Phase 2.2

Phase 2.2 found that target-baseline raw output was empty for two of three prompts:

```text
baseline_empty_after_normalization count: 2
trace-001: low_tier=79, baseline=0
trace-002: low_tier=38, baseline=0
trace-003: low_tier=9, baseline=355
```

This suggested that raw prompting was not a reliable default for Gemma output-comparison preparation.

## Prompt Mode Policy

Prompt mode metadata now reflects the actual generation path:

```text
prompt_mode = raw
  backend.generate_text(...)

prompt_mode = chat
  backend.generate_chat([{"role": "user", "content": prompt}], ...)
```

For the low-tier path, both Qwen drafting and Gemma continuation/fallback use the configured prompt mode. If Qwen chat-mode draft normalization rejects the draft, Gemma fallback runs with the original prompt through the same configured prompt mode.

## Baseline Raw vs Chat Result

Verification traces:

```text
baseline raw:
logs/reports/20260525T025830Z-target-baseline-trace.json

baseline chat:
logs/reports/20260525T025839Z-target-baseline-trace.json
```

Observed target-baseline normalized output lengths:

```text
raw prompt_mode:
  baseline_empty_after_normalization: 2
  lengths: [0, 0, 355]

chat prompt_mode:
  baseline_empty_after_normalization: 0
  lengths: [144, 19, 372]
```

For output-comparison preparation, `chat` is the recommended prompt mode for Gemma baseline traces.

## Low-Tier Raw vs Chat Result

Verification traces:

```text
low-tier raw:
logs/reports/20260525T025859Z-low-tier-trace.json

low-tier chat:
logs/reports/20260525T025918Z-low-tier-trace.json
```

Observed low-tier normalized output lengths:

```text
raw prompt_mode:
  low_tier_empty_after_normalization: 0
  fallback_count: 0
  lengths: [79, 38, 9]

chat prompt_mode:
  low_tier_empty_after_normalization: 0
  fallback_count: 3
  lengths: [144, 19, 372]
```

In this run, Qwen chat-mode drafts were rejected by the bridge and Gemma fallback produced the low-tier outputs. This is expected trace behavior, but it means the chat-mode low-tier path was mostly validating fallback and formatting rather than useful Qwen draft contribution.

## Output Health Checks

The output normalization preview now records:

```text
low_tier_empty_after_normalization_count
baseline_empty_after_normalization_count
all_low_tier_outputs_present
all_baseline_outputs_present
prompt_mode_risk
warnings
```

If baseline normalized outputs are empty, preview reports:

```text
baseline outputs contain empty normalized text; output comparison diagnostics may be uninformative
```

For the chat-mode comparison preview:

```text
low_tier_empty_after_normalization_count: 0
baseline_empty_after_normalization_count: 0
all_low_tier_outputs_present: true
all_baseline_outputs_present: true
prompt_mode_risk: none
warnings: []
```

## Precheck/Preview Result

Chat-mode precheck and preview used:

```text
low-tier:
logs/reports/20260525T025918Z-low-tier-trace.json

target-baseline:
logs/reports/20260525T025839Z-target-baseline-trace.json
```

Generated:

```text
logs/reports/20260525T025925Z-output-comparison-precheck.md
logs/reports/20260525T025925Z-output-normalization-preview.md
```

Precheck result:

```text
output_comparison_ready: yes
blocking_reasons: []
```

Preview result:

```text
preview_ready: yes
preview_records: 3
blocking_reasons: []
normalized_outputs_exact_string_match count: 3
```

The exact-string field is a preview field only.

## Tests

Focused verification:

```text
.venv/bin/pytest tests/test_generation_settings.py tests/test_baseline_trace.py tests/test_low_tier_trace.py tests/test_output_preview.py -v
35 passed
```

Full verification is expected to include:

```text
.venv/bin/pytest -v
```

## Non-Claims

This phase does not compare output equality.
No output parity claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.

## Remaining Issues

`chat` mode fixes the empty Gemma baseline issue for the current prompt set, but low-tier chat mode caused all three Qwen drafts to be rejected in this verification run. Future diagnostic comparison should account for whether a low-tier trace is exercising valid draft continuation or fallback-only behavior.

## Conclusion

passed

Phase 2.3 aligns prompt-mode behavior and adds output health checks so raw-capture traces are more informative before later diagnostic comparison work.

## Next Step

Phase 2.4 should design fallback-aware output diagnostic comparison. It should distinguish fallback-only records from valid-draft records and remain diagnostic rather than a target-equivalence claim.
