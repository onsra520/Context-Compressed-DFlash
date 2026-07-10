# T115 Canonical Source Audit

## Decision

`READY_AFTER_LOCALIZED_FIX`. T115 removed the detached target-prefill pass from the live benchmark path and added DFlash acceptance and timing counters. This is a measurement and unnecessary-work fix, not a production refactor.

## GSM8K

The T114H 100-row result remains valid: the exact T106B suffix reaches each real prompt, prompt hashes match across conditions, and the historical strict numeric evaluator remains in use. The true full-prompt reduction is reported in `summaries/gsm8k_recheck.json`; it uses only target-tokenizer pre/post counts. DFlash-R1 remains the preferred short-context condition because CC-DFlash's small reduction does not justify extra compressor VRAM and risk.

## QMSum

Historical T105B and T114 share frozen rows, rendered prompt hashes, model paths, block size, and maximum output tokens for their common rows. The controlled sample confirms DFlash is slower than Baseline because low acceptance produces many draft-proposal and target-verification cycles. T114's n=100 CC-DFlash advantage is consistent with its shorter prompt reducing target work; the corrected three-row sample has different output lengths and does not reproduce a lower CC end-to-end latency, so that exact delta remains variance-sensitive. This is not a semantic-quality claim. The original detached prefill was an instrumentation/lifecycle defect that inflated end-to-end time for all conditions; it did not create the DFlash-versus-Baseline ordering.

## Before Refactor

Implement acceptance/verification profiling and any proven block-size or cache improvement first. Do not rerun the full QMSum matrix, change models, or claim QMSum semantic correctness without a separately validated repair. The live split DFlash implementation is authoritative; `model_raw.py` is an unused duplicate that should be handled in a later deliberate refactor.
