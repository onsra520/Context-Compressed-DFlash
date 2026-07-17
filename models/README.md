# Model placement

Place local Hugging Face snapshots under the exact paths declared in `config.yml`:

- `baseline/Qwen3-4B-AWQ`
- `dflash/target/Qwen3-4B-AWQ`
- `dflash/target/Qwen3-4B-bnb-4bit` (optional fallback)
- `dflash/drafter/Qwen3-4B-DFlash-b16`
- `compressor/llmlingua-2-bert-base-multilingual-cased-meetingbank`

Baseline and D-Flash target paths are intentionally separate so each condition has explicit provenance. They may be deduplicated at the filesystem layer after validation, but the configured logical paths must remain stable.
