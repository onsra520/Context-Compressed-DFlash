# File-Backed CLI Invocation Fix Design

## Context

The first Low Tier CLI smoke test failed before generation. The test used a stdin heredoc fallback:

```bash
timeout 600 env PYTHONPATH=src python - <<'PY'
from cli.generate import main
raise SystemExit(main(["--config", "configs/local.yaml", "--prompt", "Hello"]))
PY
```

In WSL, vLLM forced multiprocessing `spawn`. The spawned worker attempted to re-run the main module from
`/home/quyseggs/HTFS-Decoding/<stdin>`, which is not a real file path. Engine initialization failed before the
Low Tier loop started.

The incident is recorded in:

```text
.agents/docs/logs/2026-05-23-low-tier-cli-test.md
```

## Scope

Fix the first recorded runtime error with a hybrid CLI workflow:

- primary path: install the package in editable mode and run the real console script;
- fallback path: run a real Python module with `PYTHONPATH=src python -m cli.generate`;
- never use stdin heredoc execution for a path that may initialize vLLM.

The intended primary smoke command is:

```bash
htfsd-generate --prompt "Hello"
```

The intended fallback command is:

```bash
PYTHONPATH=src python -m cli.generate --prompt "Hello"
```

## CLI Config Behavior

`--config` becomes optional for `htfsd-generate`.

Default behavior:

```text
--config default = configs/local.yaml
```

Users only need to pass `--config` when using a non-default file:

```bash
htfsd-generate --config configs/local.example.yaml --prompt "Hello"
```

If `configs/local.yaml` is missing and the user did not pass `--config`, the command must fail before model loading
with a clear message that explains:

- the CLI looked for `configs/local.yaml`;
- the user can create that file;
- or the user can pass `--config <path>`.

If the user explicitly passes `--config <path>`, the CLI must not silently fall back to `configs/local.yaml`.

## Packaging And Invocation

The implementation must verify that:

```bash
python -m pip install -e .
command -v htfsd-generate
htfsd-generate --help
```

works in the active environment.

If editable install does not create the script, fix packaging/import layout minimally. If packaging already works,
do not churn `pyproject.toml`.

The fallback invocation must remain file-backed:

```bash
PYTHONPATH=src python -m cli.generate --prompt "Hello"
```

Do not use:

```bash
python - <<'PY'
...
PY
```

for smoke tests or docs that initialize vLLM.

## Run Logging

Run logging remains at the CLI boundary.

The run log should record the effective config path:

- `configs/local.yaml` when the default is used;
- the explicit path when `--config` is provided.

Run logs must continue to avoid raw prompt text and generated model output by default.

If config loading fails, the run log should still record an error with the effective config path.

## Tests

Unit and CLI tests must not require GPU, vLLM model loading, or downloads.

Required tests:

- parser/default behavior uses `configs/local.yaml`;
- explicit `--config foo.yaml` overrides the default;
- missing default config fails before model loading with a clear error;
- run log records the effective config path;
- module invocation path is documented or covered without using heredoc.

Runtime verification after implementation:

```bash
python -m pip install -e .
command -v htfsd-generate
htfsd-generate --help
timeout 600 htfsd-generate --prompt "Hello"
timeout 600 env PYTHONPATH=src python -m cli.generate --prompt "Hello"
```

## Non-Goals

This fix must not change:

- `LowTierEngine` semantics;
- D-Flash parser behavior;
- verifier behavior;
- greedy acceptance/fallback behavior;
- benchmark JSONL row shape;
- generated stdout behavior, except that `--config` no longer has to be passed for the default local config.

This fix must not add High Tier, EAGLE, hidden-state promotion, or any Gemma E4B routing inside the Low Tier loop.

## Acceptance Criteria

- `htfsd-generate --prompt "Hello"` uses `configs/local.yaml`.
- `PYTHONPATH=src python -m cli.generate --prompt "Hello"` uses `configs/local.yaml`.
- `--config <path>` overrides the default.
- Missing default config fails clearly before model loading.
- vLLM smoke test no longer uses stdin heredoc invocation.
- Run logs show the effective config path and still redact raw prompt/model output.
- Existing Low Tier behavior and benchmark contracts are unchanged.
