#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: missing project Python: $PYTHON" >&2
    exit 1
fi

# Pinned model identities.
TARGET_REPO="unsloth/Qwen3-4B-bnb-4bit"
TARGET_REV="cad0bedfdd862093a12af478cb974ab2addd0e0a"
TARGET_DIR="models/target/unsloth--Qwen3-4B-bnb-4bit"

DRAFT_REPO="z-lab/Qwen3-4B-DFlash-b16"
DRAFT_REV="b74e3a329c4d963783143b1e970d95b002be72bd"
DRAFT_DIR="models/drafter/z-lab--Qwen3-4B-DFlash-b16"

export HF_HUB_DOWNLOAD_TIMEOUT=300
export HF_HUB_ETAG_TIMEOUT=60

mkdir -p \
    models/target \
    models/drafter \
    models/validation \
    results/Rec-T01B/logs \
    results/Rec-T01B/reports

echo "Python:"
"$PYTHON" - <<'PY'
import sys
import huggingface_hub

print(sys.executable)
print("huggingface_hub:", huggingface_hub.__version__)
PY

cat > results/Rec-T01B/resolved_revisions.env <<EOF
TARGET_REPO=$TARGET_REPO
TARGET_REV=$TARGET_REV
TARGET_DIR=$TARGET_DIR
DRAFT_REPO=$DRAFT_REPO
DRAFT_REV=$DRAFT_REV
DRAFT_DIR=$DRAFT_DIR
EOF

download_model() {
    local role="$1"
    local repo="$2"
    local revision="$3"
    local destination="$4"
    local log_path="$5"

    echo
    echo "=== Download $role ==="
    echo "Repository:  $repo"
    echo "Revision:    $revision"
    echo "Destination: $destination"

    "$PYTHON" - "$repo" "$revision" "$destination" <<'PY' \
        2>&1 | tee "$log_path"
from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

repo_id, revision, local_dir = sys.argv[1:4]
destination = Path(local_dir)

destination.mkdir(parents=True, exist_ok=True)

resolved_path = snapshot_download(
    repo_id=repo_id,
    revision=revision,
    local_dir=str(destination),
    repo_type="model",
    max_workers=4,
)

print(f"Downloaded snapshot: {resolved_path}")

config_path = destination / "config.json"
if not config_path.is_file():
    raise SystemExit(f"ERROR: missing config.json in {destination}")

print(f"Validated config: {config_path}")
PY
}

download_model \
    "target" \
    "$TARGET_REPO" \
    "$TARGET_REV" \
    "$TARGET_DIR" \
    "results/Rec-T01B/logs/target-download.log"

download_model \
    "drafter" \
    "$DRAFT_REPO" \
    "$DRAFT_REV" \
    "$DRAFT_DIR" \
    "results/Rec-T01B/logs/drafter-download.log"

echo
echo "=== Download inventory ==="

find "$TARGET_DIR" -type f -printf 'target\t%P\t%s\n' \
    | LC_ALL=C sort \
    > results/Rec-T01B/model_file_inventory.tsv

find "$DRAFT_DIR" -type f -printf 'drafter\t%P\t%s\n' \
    | LC_ALL=C sort \
    >> results/Rec-T01B/model_file_inventory.tsv

echo "Target files:"
find "$TARGET_DIR" -type f | wc -l

echo "Drafter files:"
find "$DRAFT_DIR" -type f | wc -l

echo
echo "Downloads completed successfully."
