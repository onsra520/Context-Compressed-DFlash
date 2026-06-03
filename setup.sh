#!/usr/bin/env bash
# WARNING: skeleton-only helper. Do not run this script as part of the current review pass.
# It installs the Python environment and requirements for the project scaffold only.
set -euo pipefail

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt