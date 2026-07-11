# Rec-T02B2 - Canonical Configuration and Resolution Layer

Status: PASS

The reconstruction now resolves `configs/reconstruction.yml` before single-prompt and benchmark execution. The resolver validates local model locks, immutable identities, frozen n10 dataset manifests, prompt policy identities, evaluator identities, and canonical generation settings.

Canonical benchmark limits are GSM8K `256` and QMSum `384`; temperature is `0.0`; DFlash block size is `16`. A smaller `max_new_tokens` value is accepted only in explicit smoke mode, produces a noncanonical resolved configuration, and is rejected by canonical aggregation.

Resolved configurations are canonical JSON with a SHA-256 identity. Benchmark rows carry that exact hash. Compression receives the resolved model path, device, keep rate, minimum-context threshold, and chunk size.

Checks: `19 passed` across configuration, CLI, timing, compression, and condition-contract tests.
