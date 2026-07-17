# CCDF Rec-2 — D-Flash Optimization Runtime

Rec-2 is a standalone backend-only workspace for selecting and optimizing the target model used by D-Flash on a single 8 GB consumer GPU. It is intentionally separated from the existing project and does not include or modify the frontend.

## Locked model layout

```text
models/
├── compressor/
│   └── llmlingua-2-bert-base-multilingual-cased-meetingbank/
├── dflash/
│   ├── target/
│   │   ├── Qwen3-4B-AWQ/
│   │   └── Qwen3-4B-bnb-4bit/          # optional fallback
│   └── drafter/
│       └── Qwen3-4B-DFlash-b16/
└── baseline/
    └── Qwen3-4B-AWQ/
```

Default model roles:

- Baseline: `Qwen/Qwen3-4B-AWQ`.
- D-Flash target: `Qwen/Qwen3-4B-AWQ`.
- Optional target fallback: `unsloth/Qwen3-4B-bnb-4bit`.
- Drafter: local `Qwen3-4B-DFlash-b16` checkpoint, BF16, checkpoint block size 16.
- Compressor is not loaded by Rec-2; 2 GiB is reserved for later integration.

The D-Flash stack has a hard peak-reserved-memory gate of 6 GiB. Baseline execution is not subject to that gate.

## Setup

```bash
cd ccdf-rec2
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e '.[awq,profile,dev]'
```

Set the project root explicitly when running outside the repository root:

```bash
export PROJECT_ROOT="$PWD"
```

All paths are declared in the root `config.yml`. `${PROJECT_ROOT}` is expanded by the config loader.

## Validation-first workflow

```bash
ccdf-rec2 validate-config --config config.yml
ccdf-rec2 validate-env --config config.yml
ccdf-rec2 validate-models --config config.yml
```

Run the full cycle before and after changing an optimization flag:

```bash
ccdf-rec2 validation-cycle --config config.yml
```

## Run one prompt

Baseline:

```bash
ccdf-rec2 run --config config.yml --condition baseline --prompt "What is 17 multiplied by 6?"
```

D-Flash:

```bash
ccdf-rec2 run --config config.yml --condition dflash --prompt "What is 17 multiplied by 6?"
```

Use the fallback target only for a controlled comparison:

```bash
ccdf-rec2 run --config config.yml --condition dflash --target-profile fallback --prompt "What is 17 multiplied by 6?"
```

## Benchmark JSONL

For the locked deterministic five-prompt audit, run:

```bash
.venv/bin/python scripts/run_short_prompt_smoke.py \
  --config config.yml \
  --artifact docs/artifacts/benchmark/deterministic_benchmark.json
```

This protocol runs one warm-up and five measured repetitions per prompt,
condition, and order. It executes both Baseline→D-Flash and D-Flash→Baseline,
keeps attention probes and component profiling outside measured timing, and
fails unless repetition consistency, cross-condition token parity, structural
validation, and the 6 GiB D-Flash reserved-memory gate all pass.

The general JSONL benchmark accepts user-provided datasets. Each input line
must contain at least `id` and `prompt`:

```json
{"id":"gsm8k-1","prompt":"A shop sold 12 boxes with 8 items each. How many items were sold?"}
```

```bash
ccdf-rec2 benchmark   --config config.yml   --input data/benchmark/prompts.jsonl   --conditions baseline,dflash
```

The output records distinct scopes:

- target prefill latency;
- complete decode latency;
- full generation latency;
- upstream-equivalent steady-state decode latency;
- warm request latency;
- effective tau;
- draft acceptance rate;
- target forwards per output token;
- peak allocated and peak reserved VRAM;
- D-Flash memory-gate result.

## Optimization flags

The root config contains independently auditable flags for:

- GPU-resident acceptance-prefix calculation;
- GPU-resident acceptance with a host-side ablation path;
- one compact GPU-to-CPU transfer per verification block and no duplicate argmax work as implementation invariants;
- finalize-only output contracts by default, with optional block-boundary checks;
- compact versus full structural audit;
- fixed or adaptive block sizes;
- drafter compilation;
- target verification compilation;
- attention backend selection;
- hard D-Flash VRAM enforcement.

The default is deliberately conservative: fixed block size 16, SDPA, no compilation, compact structural audit, and finalize-only text contracts so AR and D-Flash hot-path timing remain comparable. Enable one optimization at a time and run `validation-cycle` after each change.

## Integration boundary

The main integration surface is:

```python
from ccdf.runtime.engine import RuntimeEngine

engine = RuntimeEngine.from_config("config.yml", condition="dflash")
result = engine.generate("Your prompt")
print(result.to_dict())
engine.close()
```

No web server or frontend dependency is included.

## Important claim boundary

- AWQ is a quantized target and is not equivalent to the original BF16 model.
- D-Flash speedup is measured against the same AWQ target running autoregressively.
- Full-system comparison against another model condition must be labeled separately.
- A target candidate is accepted only after model-contract, deterministic-reference, quality, and 6 GiB D-Flash memory gates pass on the actual GPU.
