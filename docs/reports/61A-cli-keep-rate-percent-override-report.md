# Task 61A: CLI Keep-Rate Percent Override

Date: 2026-06-12

Status: PASS

## Why This Flag Was Added

Task 60 showed that `max_new_tokens=256` reduces remaining compressed GSM8K truncation, but some rows still fail numeric extraction. The next calibration needs to test gentler compression, starting with `keep_rate=0.67`, without hard-coding new condition names or changing the default R2 behavior.

Task 61A adds a CLI override for compressed conditions so future runs can request the keep rate by percent.

## Flag Behavior

New flag:

- `--keep-rate-percent <float>`

Examples:

- `--keep-rate-percent 50` resolves to `keep_rate=0.50`
- `--keep-rate-percent 67` resolves to `keep_rate=0.67`
- `--keep-rate-percent 80` resolves to `keep_rate=0.80`

The flag only changes compressed-condition runs. It does not change default behavior when omitted.

## Validation Rules

Accepted:

- values greater than `0`
- values less than or equal to `100`

Rejected with a parser/config error:

- `0`
- negative values
- values above `100`
- non-numeric values

For real runs, `--keep-rate-percent` is valid only when the selected condition is compressed. Prompt dry-run still accepts the flag because no model, compressor, or output artifact is used.

There was no pre-existing `--keep-rate` float flag, so no conflict behavior was needed.

## Default Behavior

When `--keep-rate-percent` is omitted:

- Baseline-AR and DFlash-R1 remain uncompressed.
- R2 compressed conditions keep their existing default `keep_rate=0.5`.
- R3 compressed conditions keep their existing default `keep_rate=0.33`.
- `requested_keep_rate_percent` is `null` in compressed artifact metadata.
- `requested_keep_rate` is `null` in compressed artifact metadata.

## Artifact Metadata Changes

Future compressed rows now include:

- `requested_keep_rate_percent`
- `requested_keep_rate`
- `keep_rate`
- `actual_compression_ratio`
- `compression_ratio`
- `original_input_tokens`
- `compressed_input_tokens`

When an override is used, `requested_keep_rate_percent` stores the CLI percent and `requested_keep_rate` stores the divided float. The effective `keep_rate` records what the compressor used.

## Tests Added / Updated

Updated `tests/test_compression.py` to cover:

- `--keep-rate-percent 67` parses and resolves to `keep_rate=0.67`
- `--keep-rate-percent 50` parses and resolves to `keep_rate=0.5`
- invalid values `0`, negative, and above `100` are rejected
- default compressed behavior remains unchanged when omitted
- compressed metadata includes requested keep-rate fields when an override is supplied

## Runtime Scope

No real benchmark was run. No model, compressor, CUDA, QMSum, n=100, or result artifact overwrite was performed.

Allowed validation only:

- unit tests
- compile checks
- GSM8K prompt dry-run with `--keep-rate-percent 67`

## Validation

Full validation is recorded in the final response for this task.

## Next Recommendation

Task 61B should run the tiny compressed-only GSM8K keep-rate calibration using:

- `max_new_tokens=256`
- `--keep-rate-percent 67`
- unique Task 61B output paths
- `--resume`
- `--store-generated-text`
