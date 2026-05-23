# Low Tier CLI Test Design

## Goal

Run a focused Low Tier CLI smoke test using the existing local configuration in
`configs/local.yaml`, then capture any failure in a durable agent-readable
markdown report under `.agents/docs/logs/`.

This is a runtime validation pass, not a feature change.

## Scope

Included:

- Confirm the active Python environment can invoke the HTFSD CLI path.
- Run a lightweight preflight before model execution.
- Run `htfsd-generate` with two prompts:
  - `Hello`
  - `Liệt kê các tỉnh Việt Nam`
- Inspect structured run logs under `logs/runs/*.json` if a command fails.
- Write a markdown incident report to `.agents/docs/logs/` when a failure occurs.

Excluded:

- No Low Tier engine behavior changes.
- No D-Flash parser changes.
- No verifier or acceptance/fallback policy changes.
- No config edits unless a later approved fix explicitly requires them.
- No generated `logs/` or model outputs committed to git.

## Test Flow

1. Check repository and environment context:
   - current branch/status
   - `configs/local.yaml` exists
   - CLI modules import
   - console script availability, with a source-tree fallback if needed
2. Run the short smoke prompt:
   - `Hello`
3. Run the Vietnamese workflow prompt:
   - `Liệt kê các tỉnh Việt Nam`
4. If a command fails:
   - inspect the latest `logs/runs/*.json`
   - extract status, exit code, exception type, message, traceback summary, and
     relevant config/model metadata
   - write a markdown report in `.agents/docs/logs/`
5. If both commands pass:
   - report success in chat
   - do not create an incident report

## Error Report Format

Failure reports use:

```text
.agents/docs/logs/YYYY-MM-DD-low-tier-cli-test.md
```

Report template:

```markdown
# Low Tier CLI Test Log - YYYY-MM-DD

## Command
<command>

## Prompt
<test prompt>

## Status
failed

## Run Log
- path: logs/runs/...
- status:
- exit_code:
- exception_type:
- message:
- traceback summary:

## Observed Error
<main error output or summary>

## Root Cause Hypothesis
<most likely cause>

## Fix Attempt / Proposed Fix
<attempted fix or proposed fix>

## Next Step
<next command or investigation step>
```

The prompt text may be recorded for these approved smoke prompts. Future reports
should avoid storing sensitive user prompts.

## Guardrails

- Keep the run log privacy boundary intact: do not copy full model output into
  the incident report.
- Prefer structured `logs/runs/*.json` data over raw terminal output when
  diagnosing failures.
- If a failure appears to require code or config changes, stop after writing the
  report and propose the fix before changing behavior.
- Preserve the current uncommitted `README.md` worktree change.

