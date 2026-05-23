# Backup and Project Restart Design

## Goal

Back up the current project source into a root-level `backup/` directory, then prepare the repository for a clean restart while preserving the backup and Git history.

## Scope

Back up only the selected source and project files:

- `src/`
- `tests/`
- `configs/`
- `benchmarks/`
- `docs/`
- `README.md`
- `pyproject.toml`
- `pyrightconfig.json`
- `LICENSE`

Do not back up generated, heavy, or environment-specific directories:

- `.git/`
- `.venv/`
- `.pytest_cache/`
- `.worktrees/`
- `logs/`
- `models/`
- `backup/`

## Approach

Create a timestamped backup directory at:

```text
backup/YYYYMMDD-HHMMSS/project/
```

Copy the in-scope folders and files into that `project/` directory. Add a manifest file at:

```text
backup/YYYYMMDD-HHMMSS/MANIFEST.txt
```

The manifest records the backup timestamp, the source repository path, and the exact top-level items included.

## Restart State

After the backup is verified, clean the repository root so it keeps only the minimal restart scaffold:

- `.git/`
- `backup/`
- `README.md`
- `LICENSE`

The root `README.md` will be replaced with a short restart note. The original README remains available inside the timestamped backup.

## Verification

After the operation:

- Confirm the timestamped backup directory exists.
- Confirm all in-scope items exist under `backup/YYYYMMDD-HHMMSS/project/`.
- Confirm `MANIFEST.txt` exists and lists the included items.
- Confirm removed source/config/docs directories are no longer present at the repository root.
- Confirm `.git/`, `backup/`, `README.md`, and `LICENSE` remain at the repository root.

## Risks and Mitigations

- Existing uncommitted changes, including `README.md`, must be preserved in the backup before the root README is replaced.
- The backup path must be timestamped to avoid overwriting earlier backups.
- Heavy local artifacts are intentionally excluded to keep the backup small and source-focused.
