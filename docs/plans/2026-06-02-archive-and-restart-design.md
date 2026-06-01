# Design Document: Project Archiving and Restart (2026-06-02)

## Overview
This document outlines the design for archiving the current project's codebase into the `.archives/` directory and subsequently cleaning up the workspace to allow restarting the project fresh.

## Details
1. **Archive Target**:
   - Location: `.archives/<TIMESTAMP>/project/` where `<TIMESTAMP>` is `YYYYMMDD-HHMMSS` (local time).
   - MANIFEST file: `.archives/<TIMESTAMP>/MANIFEST.txt`.

2. **Scope**:
   - **Included Top-Level Items**: `src`, `tests`, `configs`, `docs`, `scripts`, `ui`, `README.md`, `pyproject.toml`, `pyrightconfig.json`, `LICENSE`.
   - **Excluded Top-Level Items**: `.git`, `.venv`, `.pytest_cache`, `.worktrees`, `logs`, `models`, `.archives`, `.agent`.

3. **Automation Script (`scripts/archive_project.py`)**:
   - The script will:
     - Detect current Git branch and HEAD hash.
     - Copy all included directories and files to the backup location.
     - Validate integrity by matching file count and sizes.
     - Write the `MANIFEST.txt` matching the repository's standard format.
     - Clean up (delete) the original source directories and files from the workspace root.
