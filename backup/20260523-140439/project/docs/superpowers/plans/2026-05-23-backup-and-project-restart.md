# Backup and Project Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Back up the current source-focused project state into `backup/<timestamp>/`, then leave the repository root ready for a clean restart.

**Architecture:** This is a filesystem migration, not an application code change. The backup is timestamped, source-focused, and verified before any cleanup runs. Cleanup keeps only `.git/`, `backup/`, `README.md`, and `LICENSE` at the repository root.

**Tech Stack:** Bash, POSIX filesystem commands, Git status checks.

---

## File Structure

- Create: `backup/YYYYMMDD-HHMMSS/project/`
  - Contains copied source and project files from the approved scope.
- Create: `backup/YYYYMMDD-HHMMSS/MANIFEST.txt`
  - Records timestamp, source path, Git branch/commit, and included top-level items.
- Modify: `README.md`
  - Replaced with a short restart note after the original README is safely backed up.
- Preserve: `LICENSE`
  - Kept at root and copied into the backup.
- Remove from root after backup verification:
  - `src/`, `tests/`, `configs/`, `benchmarks/`, `docs/`
  - `pyproject.toml`, `pyrightconfig.json`
  - `.agents/`, `.gitignore`, `.pytest_cache/`, `.venv/`, `.worktrees/`, `logs/`, `models/`

## Task 1: Create Timestamped Backup

**Files:**
- Create: `backup/YYYYMMDD-HHMMSS/project/`
- Create: `backup/YYYYMMDD-HHMMSS/MANIFEST.txt`
- Read: `src/`, `tests/`, `configs/`, `benchmarks/`, `docs/`, `README.md`, `pyproject.toml`, `pyrightconfig.json`, `LICENSE`

- [ ] **Step 1: Record pre-flight state**

Run:

```bash
git status --short
find . -maxdepth 1 -mindepth 1 -printf '%f\n' | sort
```

Expected:

```text
README.md appears as modified.
The root contains src, tests, configs, benchmarks, docs, README.md, pyproject.toml, pyrightconfig.json, and LICENSE.
```

- [ ] **Step 2: Create the backup directory**

Run:

```bash
BACKUP_ID="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="backup/${BACKUP_ID}"
mkdir -p "${BACKUP_DIR}/project"
printf '%s\n' "${BACKUP_ID}" > backup/.current-backup-id
printf 'Created backup directory: %s\n' "${BACKUP_DIR}"
```

Expected:

```text
Created backup directory: backup/<current timestamp>
```

- [ ] **Step 3: Copy approved items into the backup**

Run:

```bash
BACKUP_ID="$(cat backup/.current-backup-id)"
BACKUP_DIR="backup/${BACKUP_ID}"
cp -a src tests configs benchmarks docs README.md pyproject.toml pyrightconfig.json LICENSE "${BACKUP_DIR}/project/"
```

Expected:

```text
No command output.
```

- [ ] **Step 4: Write the backup manifest**

Run:

```bash
BACKUP_ID="$(cat backup/.current-backup-id)"
BACKUP_DIR="backup/${BACKUP_ID}"
{
  printf 'Backup ID: %s\n' "${BACKUP_ID}"
  printf 'Source path: %s\n' "$(pwd)"
  printf 'Git branch: %s\n' "$(git branch --show-current)"
  printf 'Git HEAD: %s\n' "$(git rev-parse HEAD)"
  printf '\nIncluded top-level items:\n'
  printf -- '- %s\n' src tests configs benchmarks docs README.md pyproject.toml pyrightconfig.json LICENSE
  printf '\nExcluded top-level items:\n'
  printf -- '- %s\n' .git .venv .pytest_cache .worktrees logs models backup
} > "${BACKUP_DIR}/MANIFEST.txt"
```

Expected:

```text
No command output.
```

- [ ] **Step 5: Verify backup contents**

Run:

```bash
BACKUP_ID="$(cat backup/.current-backup-id)"
BACKUP_DIR="backup/${BACKUP_ID}"
test -d "${BACKUP_DIR}/project/src"
test -d "${BACKUP_DIR}/project/tests"
test -d "${BACKUP_DIR}/project/configs"
test -d "${BACKUP_DIR}/project/benchmarks"
test -d "${BACKUP_DIR}/project/docs"
test -f "${BACKUP_DIR}/project/README.md"
test -f "${BACKUP_DIR}/project/pyproject.toml"
test -f "${BACKUP_DIR}/project/pyrightconfig.json"
test -f "${BACKUP_DIR}/project/LICENSE"
test -f "${BACKUP_DIR}/MANIFEST.txt"
find "${BACKUP_DIR}/project" -maxdepth 1 -mindepth 1 -printf '%f\n' | sort
```

Expected:

```text
LICENSE
README.md
benchmarks
configs
docs
pyproject.toml
pyrightconfig.json
src
tests
```

## Task 2: Reset Root to Minimal Scaffold

**Files:**
- Modify: `README.md`
- Preserve: `LICENSE`
- Preserve: `backup/`
- Preserve: `.git/`
- Remove: all other root-level files and directories

- [ ] **Step 1: Replace root README with restart note**

Replace `README.md` with:

```markdown
# HTFS Decoding

This repository has been reset for a fresh project start.

The previous source-focused project state is preserved under `backup/`.
```

Expected:

```text
README.md contains only the restart note shown in this step.
```

- [ ] **Step 2: Remove non-scaffold root items**

Run:

```bash
find . -mindepth 1 -maxdepth 1 \
  ! -name '.git' \
  ! -name 'backup' \
  ! -name 'README.md' \
  ! -name 'LICENSE' \
  -exec rm -rf -- {} +
rm -f backup/.current-backup-id
```

Expected:

```text
No command output.
```

- [ ] **Step 3: Verify final root shape**

Run:

```bash
find . -maxdepth 1 -mindepth 1 -printf '%f\n' | sort
```

Expected:

```text
.git
LICENSE
README.md
backup
```

- [ ] **Step 4: Verify backup still contains the old project**

Run:

```bash
BACKUP_DIR="$(find backup -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | tail -1)"
test -n "${BACKUP_DIR}"
test -d "${BACKUP_DIR}/project/src"
test -d "${BACKUP_DIR}/project/tests"
test -d "${BACKUP_DIR}/project/docs"
test -f "${BACKUP_DIR}/project/README.md"
test -f "${BACKUP_DIR}/MANIFEST.txt"
printf 'Verified backup: %s\n' "${BACKUP_DIR}"
```

Expected:

```text
Verified backup: backup/<timestamp>
```

## Task 3: Final Git Status Check

**Files:**
- Read: Git working tree metadata

- [ ] **Step 1: Inspect resulting Git status**

Run:

```bash
git status --short
```

Expected:

```text
README.md appears modified.
Removed tracked project files appear deleted.
backup/ appears as untracked unless ignored by repository configuration.
No unexpected files remain at the repository root.
```

- [ ] **Step 2: Summarize completed state**

Report:

```text
Backup created at backup/<timestamp>.
Root reset to .git, backup, README.md, and LICENSE.
Original project files are available under backup/<timestamp>/project/.
```
