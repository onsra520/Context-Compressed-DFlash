# Phase 2.9 Controlled Diagnostic Record Selector

## Summary

Phase 2.9 passed.

This phase implements a controlled diagnostic record selector. The selector consumes the existing precheck, output preview, contribution classifier, and diagnostic comparison layers, then decides which records are eligible for future draft-contribution diagnostics.

The selector does not add a new output comparison claim. It only assigns selection categories and exclusion reasons.

## Selector Command

```bash
python scripts/select_diagnostic_records.py \
  --low-tier logs/reports/<low-tier-raw-capture-trace>.json \
  --baseline logs/reports/<target-baseline-raw-capture-trace>.json
```

The command writes markdown and JSON reports under `logs/reports/`.

## Selection Rules

Implemented selection categories:

```text
eligible_valid_draft_record
excluded_fallback_derived_record
excluded_unknown_contribution_record
excluded_empty_baseline_record
excluded_prompt_mode_risk_record
```

A record is eligible only when it is a `valid_draft_continuation` record with complete metadata, no fallback, non-empty low-tier output, non-empty baseline output, and a present diagnostic exact-string flag.

Exclusion reasons are preserved even when a higher-priority primary category is assigned.

Priority order:

```text
unknown contribution
fallback-derived
empty baseline
prompt-mode risk
eligible valid draft
```

## Raw Mode Result

Input traces:

```text
low-tier: logs/reports/20260525T085414Z-low-tier-trace.json
baseline: logs/reports/20260525T085426Z-target-baseline-trace.json
selector report: logs/reports/20260525T085530Z-diagnostic-record-selection-2.md
```

Selector output:

```text
selection_ready: yes
total_records: 3
eligible_valid_draft_record_count: 1
excluded_fallback_derived_record_count: 0
excluded_unknown_contribution_record_count: 0
excluded_empty_baseline_record_count: 2
excluded_prompt_mode_risk_record_count: 0
blocking_reasons: []
```

Interpretation: raw mode still exercises the valid-draft path, but two records are excluded because the baseline normalized output is empty. Those excluded records are uninformative for deeper draft-contribution diagnostics.

## Chat Mode Result

Input traces:

```text
low-tier: logs/reports/20260525T085448Z-low-tier-trace.json
baseline: logs/reports/20260525T085516Z-target-baseline-trace.json
selector report: logs/reports/20260525T085530Z-diagnostic-record-selection.md
```

Selector output:

```text
selection_ready: yes
total_records: 3
eligible_valid_draft_record_count: 0
excluded_fallback_derived_record_count: 3
excluded_unknown_contribution_record_count: 0
excluded_empty_baseline_record_count: 0
excluded_prompt_mode_risk_record_count: 0
blocking_reasons: []
```

Interpretation: chat mode produces non-empty baseline output, but all low-tier records are fallback-derived. The selector excludes them from draft-contribution diagnostics.

## Selection Counts

Raw mode:

```text
eligible_valid_draft_record_count: 1
excluded_empty_baseline_record_count: 2
```

Chat mode:

```text
excluded_fallback_derived_record_count: 3
```

## Exclusion Reasons

Raw mode exclusion reasons:

```text
empty_baseline
prompt_mode_risk
```

`empty_baseline` is the primary category for the affected records. `prompt_mode_risk` is preserved as an additional reason because raw prompt mode can produce empty Gemma baseline outputs for this prompt set.

Chat mode exclusion reasons:

```text
fallback_derived
prompt_mode_risk
```

`fallback_derived` is the primary category. `prompt_mode_risk` is preserved because chat mode produced fallback-derived low-tier records in this run.

## Warnings

Raw mode warnings:

```text
The baseline output is empty after normalization. This record is uninformative for target-baseline string diagnostics.
Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for output-comparison preparation.
```

Chat mode warnings:

```text
This record used Gemma fallback. It is excluded from draft-contribution diagnostics.
Chat prompt mode produced fallback-derived low-tier records in this run. Matches in this mode must not be read as Qwen draft contribution.
```

## Tests

Added selector coverage in:

```text
tests/test_diagnostic_record_selection.py
```

Focused selector test result:

```text
12 passed
```

Full suite verification is recorded in the final Phase 2.9 result.

## Non-Claims

This is not an output equality report.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Remaining Issues

Raw mode can still produce empty Gemma baseline outputs for this prompt set. Chat mode fixes baseline output presence, but the low-tier chat records observed here are fallback-derived and excluded from draft-contribution diagnostics.

## Conclusion

passed

Phase 2.9 implements the record selector needed before any deeper diagnostic inspection. The selector correctly separates eligible valid-draft records from fallback-derived, unknown, empty-baseline, and prompt-mode-risk records.

## Next Step

Phase 2.10 should design an eligible-record inspection report that consumes selector output and lists only eligible valid-draft records with compact diagnostic metadata. It should not add target-equivalence, correctness, or benchmark claims.
