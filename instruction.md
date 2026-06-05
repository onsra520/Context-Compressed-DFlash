# CC-DFlash — Agent Instruction

> **Agent Operating Manual** · v5.2  
> Read this file first. Do not duplicate live task status from canonical docs.

---

## Canonical Sources

| Document                    | Path                           | Role                                                                                    |
| --------------------------- | ------------------------------ | --------------------------------------------------------------------------------------- |
| Live roadmap / task tracker | `docs/Roadmap.html`            | Source of truth for live task ledger, next task, reports, artifacts, phase gates        |
| Stable research context     | `docs/CC-DFlash-Overview.html` | Source of truth for research context, claims, architecture, risks, benchmark philosophy |
| Agent manual                | `instruction.md`               | Source of truth for agent behavior, rules, validation expectations                      |

---

## Mandatory Reading Order

Before starting any meaningful task, read these files in order:

1. `instruction.md`
2. `docs/Roadmap.html`
3. `docs/CC-DFlash-Overview.html`

Use `docs/Roadmap.html` to determine the current task, next task, task status, required report path, and expected artifacts.

Use `docs/CC-DFlash-Overview.html` to understand the project context, research claim, architecture, benchmark philosophy, and risks.

Use `instruction.md` to determine what is allowed, forbidden, and required during execution.

---

## Source of Truth Rules

- `instruction.md` controls agent behavior, forbidden actions, update rules, and validation expectations.
- `docs/Roadmap.html` controls task progress, live task status, next task, report index, artifact index, and phase gates.
- `docs/CC-DFlash-Overview.html` controls stable research context, claims, architecture, benchmark philosophy, and risks.
- Do not copy live task status into `instruction.md`.
- Do not duplicate the roadmap or research overview inside `instruction.md`.
- If task status is needed, read `docs/Roadmap.html`.
- If project context or claim policy is needed, read `docs/CC-DFlash-Overview.html`.

---

## Update Rules

- Update `docs/Roadmap.html` after every meaningful task.
- Create or update a numbered Markdown report under `docs/reports/` for every meaningful task.
- Update `docs/CC-DFlash-Overview.html` only when research interpretation, claims, architecture, benchmark policy, risks, or phase interpretation change.
- Update `instruction.md` only when agent rules, source-of-truth policy, validation expectations, or forbidden actions change.
- Do not update `instruction.md` merely because a task was completed.

---

## Agent Sync Protocol

### Purpose

This protocol keeps human-facing task tracking and automated codebase understanding aligned. It prevents agents from drifting away from the live roadmap, the stable research context, or the latest analyzed codespace state.

### Roadmap vs Understand-Anything Roles

- `docs/Roadmap.html` is the source of truth for live task progress, task ledger, next task, reports, artifacts, and phase gates.
- `docs/CC-DFlash-Overview.html` is the source of truth for stable research context, claims, architecture, benchmark philosophy, and risks.
- `instruction.md` is the source of truth for agent behavior, forbidden actions, update rules, and validation expectations.
- `Understand-Anything` under `.understand-anything/` is the source of truth for codebase understanding, analyzed nodes, file relationships, and navigation context.

### Bootstrap Commands

Before starting any meaningful task work, run:

```bash
# 1. Read current task status and next task from Roadmap
grep -E "Current: Task|Current next:" docs/Roadmap.html | head -n 10

# 2. Identify the latest reports in chronological order
find docs/reports -maxdepth 1 -type f | sort | tail -5

# 3. Verify actual repository status and history
git status --short
git log --oneline -5

# 4. Check current Understand-Anything build metadata if available
cat .understand-anything/meta.json 2>/dev/null || true
```

### Reconciliation Rules

- If `docs/Roadmap.html` and the reports in `docs/reports/` disagree, inspect the actual repository state with `git diff` and `git log` before updating any docs.
- Update only with verified, objective facts.
- Do not overwrite or modify completed task logs or report index entries unless explicitly instructed.
- Do not invent or consume the next major task number for sync/protocol work.
- Use the task prefix assigned by `docs/Roadmap.html` or by the user.
- For auxiliary sync tasks, use a subtask prefix such as `45-5` or `45-sync`.

### What To Update After Each Task

1. `docs/Roadmap.html`: update the task status, add the report filename under the reports index, update the hero badges at the top to list the next task, and add a short entry to the update log.
2. `docs/reports/`: write a new report file named `<prefix>-<description>-report.md` using the next unused chronological prefix.
3. `Understand-Anything`: if codebase analysis runs or the graph's analyzed nodes advance, note the latest node ID in the completed report.

### Understand-Anything Metadata Rule

- If `.understand-anything/meta.json` is available, read the latest known Understand-Anything node or progress from that file.
- Do not hard-code a stale node number in `instruction.md`.
- If no metadata file is available, state that explicitly rather than guessing.

### Final Response Checklist

- Include a summary of files created or modified.
- Confirm whether benchmarks, model loading, or result artifacts were touched.
- Include a validation summary.
- Print `git status --short`.
- Print `git diff --stat`.
- List the changed files.

---

## Project Rules

### Forbidden Folders

- Archive, deprecated, and backup folders are forbidden unless the user explicitly names a file in one of them.
- Do not scan, grep, read, or index: `.archives/`, `archive/`, `archives/`, `backup/`, `backups/`, `old/`, `deprecated/`.

### Code Constraints

- Markdown code fences must remain balanced.
- Raw DFlash files are reference-only; production split modules must not import `*_raw.py`.
- Do not modify old artifacts in `results/` or `tests/fixtures/` unless the task explicitly requests regeneration or replacement.
- Do not use vLLM, SGLang, Docker, or scale-up infrastructure unless the user explicitly requests it.
- Keep the current project on the Transformers backend only.
- Do not introduce Gemma4-E2B compressor into MVP.

### Claims Policy

- Do not claim final speedup.
- Do not claim final correctness.
- Do not claim deploy readiness.
- Do not claim confirmed 8 GB deployment.
- Do not claim compression has been proven useful end-to-end.
- Keep all benchmark and evidence claims preliminary unless an explicit numbered report proves otherwise.

### Validation Expectations

- Every meaningful agent task must produce a verification summary.
- If code was changed, run compile checks before completion.
- If tests exist for the changed area, run the relevant tests before completion.
- If Markdown changed, check fence balance before completion.
- If HTML docs changed, sanity-check the HTML structure before completion.
- Always report `git diff --stat` and `git status --short` in the final response.

---

## Final Response Format

Final agent response must include:

1. Summary of files created or modified
2. Whether benchmarks, model loading, or result artifacts were touched
3. Validation summary
4. `git status --short` output
5. `git diff --stat` output
6. List of changed files
