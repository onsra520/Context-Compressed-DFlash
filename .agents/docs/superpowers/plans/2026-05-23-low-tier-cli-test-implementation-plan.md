# Low Tier CLI Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the configured Low Tier CLI smoke test and document any runtime failure in `.agents/docs/logs/`.

**Architecture:** This is a runtime validation pass, not a feature change. Use a lightweight preflight before model execution, then run two `htfsd-generate` prompts in order. If a command fails, diagnose from structured `logs/runs/*.json` and write a markdown incident report without committing generated run logs or model output.

**Tech Stack:** Bash, Python 3, HTFSD CLI entrypoint `htfsd-generate`, `configs/local.yaml`, structured JSON run logs, markdown incident notes.

---

## Current Working Tree Notes

The repository currently has an unrelated uncommitted `README.md` change. Do not
stage, revert, or rewrite it during this test pass.

`.agents/` is ignored by default in `.gitignore`. If an incident report must be
committed later, it will need `git add -f`. This plan does not require committing
the incident report unless explicitly requested after the report is reviewed.

Generated runtime artifacts are ignored:

- `logs/runs/*.json`
- `runs/*.jsonl`

Do not force-add generated runtime artifacts.

## Files

- Read: `configs/local.yaml`
- Read: `src/cli/generate.py`
- Read: `src/cli/run_logging.py`
- Create if failure occurs: `.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md`

Do not modify:

- `src/low_tier/**`
- `src/dflash/**`
- `src/runtime/**`
- `src/tokenization/**`
- `src/benchmarks/**`
- `configs/local.yaml`
- `README.md`

## Task 1: Preflight Environment And Config

**Files:**

- Read: `configs/local.yaml`
- Read: `pyproject.toml`
- No file writes

- [ ] **Step 1: Confirm repository state**

Run:

```bash
git branch --show-current
git status --short --untracked-files=all
```

Expected:

- Branch is `main`.
- `README.md` may be modified.
- No generated `logs/` or model output files are staged.

- [ ] **Step 2: Confirm config exists**

Run:

```bash
test -f configs/local.yaml && printf 'configs/local.yaml exists\n'
```

Expected:

```text
configs/local.yaml exists
```

If this fails, stop and write an incident report with root cause hypothesis
`missing local config`.

- [ ] **Step 3: Inspect config model paths without changing config**

Run:

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from config import load_config

config = load_config("configs/local.yaml")
for name, model in (
    ("qwen_drafter", config.qwen_drafter),
    ("gemma_e2b", config.gemma_e2b),
    ("gemma_e4b_baseline", config.gemma_e4b_baseline),
):
    value = model.model_id_or_path
    path = Path(value)
    exists = path.exists() if path.is_absolute() or value.startswith(".") else "hub-id"
    print(f"{name}: {value} exists={exists}")
print(f"execution_mode: {config.runtime.execution_mode}")
print(f"decoding_default: {config.decoding.default}")
PY
```

Expected:

- Command exits `0`.
- Model IDs or local paths are printed.
- `execution_mode` and `decoding_default` are printed.

If this fails, stop and write an incident report with the Python traceback and
latest run log if one exists.

- [ ] **Step 4: Confirm CLI import path**

Run:

```bash
PYTHONPATH=src python - <<'PY'
from cli.generate import main
from cli.run_logging import RunLogSession

print(main.__name__)
print(RunLogSession.__name__)
PY
```

Expected:

```text
main
RunLogSession
```

If this fails, stop and write an incident report with root cause hypothesis
`source import path failure`.

- [ ] **Step 5: Confirm console script or fallback invocation**

Run:

```bash
if command -v htfsd-generate >/dev/null 2>&1; then
  printf 'console_script=htfsd-generate\n'
  htfsd-generate --help >/tmp/htfsd-generate-help.txt
else
  printf 'console_script=missing; fallback=PYTHONPATH=src python -c cli.generate.main\n'
  PYTHONPATH=src python - <<'PY' >/tmp/htfsd-generate-help.txt
from cli.generate import main
try:
    main(["--help"])
except SystemExit as exc:
    raise SystemExit(exc.code)
PY
fi
head -n 5 /tmp/htfsd-generate-help.txt
```

Expected:

- Either the console script is found, or the source-tree fallback works.
- Help output starts with argparse usage.

If the console script is missing but fallback works, continue and use the
fallback command for the smoke runs. Also mention this in the final summary.

## Task 2: Run Short Prompt Smoke Test

**Files:**

- Read: `configs/local.yaml`
- Generated and ignored: `logs/runs/*.json`
- Create if failure occurs: `.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md`

- [ ] **Step 1: Capture latest run-log state before running**

Run:

```bash
find logs/runs -maxdepth 1 -type f -name '*.json' 2>/dev/null | sort | tail -n 1
```

Expected:

- Prints the previous latest run log path, or prints nothing if there are no
  run logs yet.

- [ ] **Step 2: Run `Hello` through Low Tier CLI**

If `htfsd-generate` exists, run:

```bash
timeout 600 htfsd-generate \
  --config configs/local.yaml \
  --prompt "Hello"
```

If the console script was unavailable during preflight, run:

```bash
timeout 600 env PYTHONPATH=src python - <<'PY'
from cli.generate import main

raise SystemExit(main(["--config", "configs/local.yaml", "--prompt", "Hello"]))
PY
```

Expected:

- Command exits `0`.
- Generated text and metrics print to stdout.
- A structured run log is written under `logs/runs/*.json`.

- [ ] **Step 3: On success, inspect the latest run log summary**

Run:

```bash
export LATEST_LOG=$(find logs/runs -maxdepth 1 -type f -name '*.json' | sort | tail -n 1)
python - <<'PY'
import json
import os

path = os.environ["LATEST_LOG"]
row = json.load(open(path, encoding="utf-8"))
print(f"path={path}")
print(f"status={row.get('status')}")
print(f"exit_code={row.get('exit_code')}")
print(f"command={row.get('command')}")
print(f"execution_mode={row.get('runtime', {}).get('execution_mode')}")
print(f"decoding_mode={row.get('runtime', {}).get('decoding_mode')}")
PY
```

Expected:

```text
status=ok
exit_code=0
command=htfsd-generate
```

- [ ] **Step 4: On failure, write incident report and stop**

Create `.agents/docs/logs/` if needed:

```bash
mkdir -p .agents/docs/logs
```

Write `.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md` using the template in
Task 4. Include:

- command that failed
- prompt `Hello`
- terminal error summary
- latest structured run log path
- run log status, exit code, exception type, message, traceback summary
- root cause hypothesis
- proposed next step

Stop after writing the report. Do not run the Vietnamese prompt until the
failure is reviewed.

## Task 3: Run Vietnamese Prompt Smoke Test

**Files:**

- Read: `configs/local.yaml`
- Generated and ignored: `logs/runs/*.json`
- Create if failure occurs: `.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md`

- [ ] **Step 1: Run Vietnamese prompt through Low Tier CLI**

If `htfsd-generate` exists, run:

```bash
timeout 600 htfsd-generate \
  --config configs/local.yaml \
  --prompt "Liệt kê các tỉnh Việt Nam"
```

If the console script was unavailable during preflight, run:

```bash
timeout 600 env PYTHONPATH=src python - <<'PY'
from cli.generate import main

raise SystemExit(main(["--config", "configs/local.yaml", "--prompt", "Liệt kê các tỉnh Việt Nam"]))
PY
```

Expected:

- Command exits `0`.
- Generated text and metrics print to stdout.
- A structured run log is written under `logs/runs/*.json`.

- [ ] **Step 2: On success, inspect latest run log summary**

Run:

```bash
export LATEST_LOG=$(find logs/runs -maxdepth 1 -type f -name '*.json' | sort | tail -n 1)
python - <<'PY'
import json
import os

path = os.environ["LATEST_LOG"]
row = json.load(open(path, encoding="utf-8"))
print(f"path={path}")
print(f"status={row.get('status')}")
print(f"exit_code={row.get('exit_code')}")
print(f"command={row.get('command')}")
print(f"prompt_present={row.get('argv', {}).get('prompt_present')}")
print(f"prompt_chars={row.get('argv', {}).get('prompt_chars')}")
print(f"execution_mode={row.get('runtime', {}).get('execution_mode')}")
print(f"decoding_mode={row.get('runtime', {}).get('decoding_mode')}")
PY
```

Expected:

```text
status=ok
exit_code=0
command=htfsd-generate
prompt_present=True
```

- [ ] **Step 3: On failure, write incident report and stop**

Create `.agents/docs/logs/` if needed:

```bash
mkdir -p .agents/docs/logs
```

Write `.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md` using the template in
Task 4. Include:

- command that failed
- prompt `Liệt kê các tỉnh Việt Nam`
- terminal error summary
- latest structured run log path
- run log status, exit code, exception type, message, traceback summary
- root cause hypothesis
- proposed next step

Stop after writing the report. Do not edit config or source code without a new
approved fix plan.

## Task 4: Incident Report Template

**Files:**

- Create if failure occurs: `.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md`

- [ ] **Step 1: Use this markdown body for failures**

Use this exact structure and replace each instruction line with observed data.
Do not leave any instruction text in the final report.

```markdown
# Low Tier CLI Test Log - 2026-05-23

## Command
Write the exact command that failed in a fenced `bash` block.

## Prompt
Write `Hello` or `Liệt kê các tỉnh Việt Nam`.

## Status
failed

## Run Log
- path: write the latest structured run log path, for example `logs/runs/20260523-120000-htfsd-generate-abcd1234.json`
- status: write the JSON `status` value
- exit_code: write the JSON `exit_code` value
- exception_type: write the JSON `error.exception_type` value, or `null`
- message: write the JSON `error.message` value, or `null`
- traceback summary: summarize the first relevant project frame and final exception line

## Observed Error
Summarize the terminal error in one short paragraph.

## Root Cause Hypothesis
Write the most likely cause based on terminal output and structured run log.

## Fix Attempt / Proposed Fix
Write what was tried, or the smallest proposed fix to try next.

## Next Step
Write the next command or investigation step in a fenced `bash` block.
```

- [ ] **Step 2: Keep report focused and privacy-aware**

Rules:

- Do not paste full model output.
- Do not paste full tracebacks if they are very long; summarize the key frames.
- Do not include tokens or secrets.
- For these approved smoke prompts, prompt text may be recorded.
- Do not commit ignored `logs/runs/*.json`.

## Task 5: Final Summary

**Files:**

- No required file writes if both prompts pass
- Read: latest structured run logs

- [ ] **Step 1: Check final git status**

Run:

```bash
git status --short --untracked-files=all
```

Expected:

- The pre-existing `README.md` change may still be present.
- No generated `logs/` files are staged.
- If a failure report was written under ignored `.agents/`, it may not appear
  unless checked with `git status --ignored`.

- [ ] **Step 2: Report outcome in chat**

If both prompts passed, report:

- preflight status
- command form used: console script or source-tree fallback
- prompt `Hello`: pass
- prompt `Liệt kê các tỉnh Việt Nam`: pass
- latest run log paths
- reminder that generated `logs/` are ignored

If a prompt failed, report:

- which prompt failed
- incident report path
- latest run log path
- root cause hypothesis
- proposed next step
