# README command verification

Date: 2026-07-13. Commands were executed with the existing root-checkout `.venv` after local editable installation using `--no-deps --no-build-isolation`; no package or model download occurred.

| Command | Environment | Result |
|---|---|---|
| `.venv/bin/python -m ccdf --help` | clean `env -i` shell | PASS — exposes `run`, `benchmark`, `evaluate`, `paths` |
| `.venv/bin/python -m ccdf paths` | clean `env -i` shell from repository root | PASS — resolved root/model path metadata |
| `.venv/bin/python -m ccdf run --help` | clean `env -i` shell | PASS — condition and input arguments match README |
| `.venv/bin/python -m pytest -q tests/test_rec_t07_gpu_hotfix.py` | existing `.venv` | PASS — 9 tests |

Model-loading examples and benchmarks were intentionally not executed: the active `.venv` has no visible CUDA device and the task prohibits n=100 reruns. The README labels those commands as requiring pre-provisioned local models/data.
