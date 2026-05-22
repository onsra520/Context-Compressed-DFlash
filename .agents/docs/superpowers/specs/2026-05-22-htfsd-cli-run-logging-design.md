# HTFSD CLI Run Logging Design

Date: 2026-05-22

## Goal

Add durable run logs for HTFSD CLI invocations so local vLLM/model failures can
be checked after a command exits. This is a CLI observability pass, not a
decoding behavior change.

The default artifact is one structured JSON run log per invocation:

```text
logs/runs/YYYYMMDD-HHMMSS-<command>-<short-id>.json
```

It records command metadata, runtime/config metadata when available, artifact
pointers, status, timing, and traceback/error information on failure. It does
not capture raw prompt text, generated model output, benchmark rows, debug trace
rows, or full terminal output by default.

## Scope

The feature applies to the existing flattened CLI layout:

```text
src/cli/run_logging.py
```

Do not reintroduce `src/htfsd` or mix old/new package layouts.

Included:

- structured JSON run logs around:
  - `htfsd-generate`
  - `htfsd-benchmark-low`
  - `htfsd-baseline-e4b`
- metadata and artifact pointers for successful runs
- error and traceback capture for failures after CLI logging starts
- prompt and sensitive argv sanitization
- generated `logs/` directory ignored by git
- short README notes for default run logging and its privacy boundary

Excluded:

- Low Tier loop changes
- D-Flash parser changes
- verifier, acceptance, fallback, or benchmark row-shape changes
- generated model output in run logs
- benchmark/debug-trace JSONL duplication in run logs
- default terminal transcript capture
- High Tier, EAGLE, or hidden-state promotion

Full terminal transcripts are optional debug work only. They may be added later
through an explicit opt-in such as `--terminal-log <path>` if a tested tee-style
implementation preserves stdout/stderr mirroring. They do not block the default
structured run logger.

## Chosen Approach

Use a shared CLI run logger around each console command `main`.

The logging boundary is:

```text
CLI responsibility:
argv, prompt sanitization, config path, artifact pointers, run status/error

Core responsibility:
LowTierEngine, D-Flash, verifier, benchmark logic, benchmark row output
```

Run logging must not move into:

- `LowTierEngine`
- D-Flash parser or verifier code
- benchmark row writers
- the Python API used by tests and research scripts

Benchmark JSONL and debug trace JSONL remain separate artifacts. A run log only
stores paths pointing to them.

## Data Flow

Each CLI command uses the same outer flow:

```text
main(argv)
-> create RunLogSession(command_name, argv)
-> parse args inside logging boundary
-> record parsed args and artifact pointers
-> load config
-> record config/runtime/model metadata best-effort
-> run existing command behavior
-> return the existing exit code
-> write ok/error JSON in __exit__/finally
```

The log directory is created automatically. The run JSON must still be written
when a command fails after logging starts, including config parse/load failures
where model metadata is unavailable.

`--help` is not an error. The implementation may avoid creating logs for help,
or it may log help invocations as:

```json
{"status": "ok", "exit_code": 0}
```

If argparse exits with a nonzero `SystemExit`, the run log records the error and
the original CLI exit behavior is preserved.

## RunLogSession API

`RunLogSession` is a small CLI-only context manager. CLI commands pass known
facts to it rather than hand-building JSON:

```python
with RunLogSession(
    command_name="htfsd-generate",
    argv=argv,
    log_dir=Path("logs/runs"),
) as run_log:
    args = parser.parse_args(argv)
    run_log.record_cli_args(args)
    config = load_config(args.config)
    run_log.record_config(config, config_path=args.config)
    run_log.record_artifact("debug_trace_path", args.debug_trace)
    return run_command(args, config)
```

Initial API shape:

```python
class RunLogSession:
    def __init__(
        self,
        command_name: str,
        argv: Sequence[str],
        log_dir: Path = Path("logs/runs"),
    ) -> None: ...

    @property
    def path(self) -> Path: ...

    def record_cli_args(self, args: argparse.Namespace) -> None: ...

    def record_config(self, config: AppConfig, config_path: str | Path) -> None: ...

    def record_artifact(self, name: str, path: str | Path | None) -> None: ...

    def record_metadata(self, **fields: JsonValue) -> None: ...

    def mark_error(
        self,
        message: str,
        exception_type: str = "CommandReturnedNonZero",
        exit_code: int = 1,
    ) -> None: ...
```

The context manager owns:

- start/end timestamp
- `duration_ms`
- `run_id`
- generated log path
- ok/error status
- exit code
- exception type/message/traceback
- JSON write in `__exit__`/`finally`

Normal exceptions are re-raised after logging. `SystemExit` is recorded then
re-raised with its original behavior. A command that returns a nonzero code
without raising must use `mark_error` or an equivalent wrapper path.

Logging metadata is best-effort:

- `record_config` must not crash the command because a config field is missing.
- `record_metadata` must not fail the command for non-JSON values; values may be
  stringified or skipped with an internal warning.
- Logging failure must not replace the original command exception. If possible,
  emit a concise stderr warning.

## JSON Schema

The first run log schema is versioned:

```json
{
  "schema_version": 1,
  "run_id": "a1b2c3d4",
  "command": "htfsd-generate",
  "status": "error",
  "exit_code": 1,
  "start_time": "2026-05-22T15:01:02.123456+07:00",
  "end_time": "2026-05-22T15:01:10.654321+07:00",
  "duration_ms": 8530.865,
  "argv": {
    "sanitized": [
      "--config",
      "configs/local.yaml",
      "--prompt",
      "<redacted>"
    ],
    "prompt_present": true,
    "prompt_chars": 27,
    "prompt_sha256": null
  },
  "paths": {
    "config_path": "configs/local.yaml",
    "benchmark_output_path": null,
    "baseline_output_path": null,
    "debug_trace_path": "runs/trace.jsonl",
    "terminal_log_path": null
  },
  "runtime": {
    "git_commit": "abc123...",
    "vllm_version": "0.21.0",
    "execution_mode": "concurrent",
    "decoding_mode": "greedy"
  },
  "models": {
    "qwen_drafter": "./models/qwen3-0.6b",
    "gemma_e2b": "./models/gemma-4-e2b-it",
    "gemma_e4b_baseline": "./models/gemma-4-e4b-it"
  },
  "error": {
    "exception_type": "RuntimeError",
    "message": "...",
    "traceback": "..."
  }
}
```

Successful runs use:

```json
{
  "status": "ok",
  "exit_code": 0,
  "error": null
}
```

If config loading fails, runtime/model metadata may be absent or null, but the
log must still have command, sanitized argv, times, status, exit code, exception
type, and traceback.

## Sanitization And Path Rules

Do not store raw prompt text by default.

Prompt sanitization covers both forms:

```text
--prompt value
--prompt=value
```

The log records:

- `prompt_present`
- `prompt_chars`
- optional `prompt_sha256`

If prompt hashing is enabled, document that it can still identify repeated
prompt input. Raw prompt text remains redacted.

Sensitive argv handling must be extendable and should cover likely token-like
flags from the start:

- `--hf-token`
- `--token`
- `--api-key`
- `--password`

Do not copy token-bearing environment variables such as `HF_TOKEN` into run
logs.

Config/model paths are allowed because they support runtime reproduction. Path
fields should be repo-relative when that is safe; paths outside the repo may
remain absolute.

`record_artifact` accepts known artifact keys only:

- `benchmark_output_path`
- `baseline_output_path`
- `debug_trace_path`
- `terminal_log_path`

It must not allow arbitrary keys to overwrite top-level JSON groups.

## CLI Integration

### Generate

`htfsd-generate` records:

- config path
- sanitized prompt facts
- debug trace path when `--debug-trace` is present
- decoding mode from CLI override or loaded config
- runtime and model metadata after config load

Interactive prompt behavior and normal generated stdout stay unchanged. Generated
text and metrics printed to stdout are not copied into the JSON run log.

### Low Tier Benchmark

`htfsd-benchmark-low` records:

- config path
- benchmark output path from `--output`
- fixture path as metadata if useful
- decoding mode
- runtime/model metadata after config load

The benchmark JSONL output contract remains unchanged.

### Gemma E4B Baseline

`htfsd-baseline-e4b` records:

- config path
- baseline output path from `--output`
- fixture path as metadata if useful
- Gemma E4B baseline metadata after config load

Gemma E4B remains a separate baseline and is not routed into Low Tier generation.

## Testing

All run logging tests must run without GPU, vLLM model loading, or downloads.

Add focused logger tests:

- successful session writes schema version, ok status, exit code, command,
  timestamps, and duration
- raised exception writes error status, exit code, exception type, message, and
  traceback, then re-raises
- `SystemExit(0)` follows the approved help policy
- `SystemExit(nonzero)` logs error exit code and re-raises
- sanitizes `--prompt value`
- sanitizes `--prompt=value`
- redacts token-like sensitive flags
- normalizes repo-relative artifact paths
- creates `logs/runs/`
- config metadata recording is best-effort
- non-JSON metadata does not break the command

Extend CLI tests with fakes/monkeypatches:

- generate integration records run log and does not copy generated output
- benchmark integration records benchmark output pointer without changing JSONL
  row shape
- baseline integration records baseline output pointer
- parse/config-load failure still leaves an error run log when logging has
  started

Monkeypatch:

- `load_config`
- `_build_engine`
- benchmark runner
- baseline runner

These tests verify CLI run logging integration, not model runtime.

Manual smoke checks may include:

- `htfsd-generate --help` under the chosen help policy
- failing local config/model path produces a run log with traceback
- optional real vLLM command when GPU/model loading is available

## Repository Hygiene And Docs

Add generated log artifacts to `.gitignore`:

```gitignore
logs/
```

Keep existing `Log/`, `Logs/`, and `*.log` ignores intact.

README should state briefly:

- structured logs live under `logs/runs/*.json`
- raw prompts and generated model output are not logged by default
- benchmark and debug trace artifacts remain separate files
- terminal transcript capture is opt-in only if implemented

## Acceptance Criteria

The pass is complete when:

- each HTFSD console command writes a structured run log for ordinary command
  execution
- failures after logging starts produce an error JSON with traceback
- raw prompt text and generated model text are absent from default run logs
- benchmark JSONL and debug trace JSONL contracts stay unchanged
- `logs/` is ignored by git
- CPU/local tests cover run logging without loading vLLM models
- existing Low Tier, D-Flash, verifier, acceptance/fallback, and benchmark
  behavior remains unchanged
