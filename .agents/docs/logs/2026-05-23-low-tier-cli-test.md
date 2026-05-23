# Low Tier CLI Smoke Test Incident Report

- Timestamp: 2026-05-23T12:47:14+07:00
- Command:

```bash
timeout 600 env PYTHONPATH=src python - <<'PY'
from cli.generate import main
raise SystemExit(main(["--config", "configs/local.yaml", "--prompt", "Hello"]))
PY
```

- Status: failed
- Observed terminal error:
  - Command exited with code 1.
  - vLLM detected WSL and overrode `VLLM_WORKER_MULTIPROC_METHOD` to `spawn`.
  - Spawned worker failed with `FileNotFoundError: [Errno 2] No such file or directory: '/home/quyseggs/HTFS-Decoding/<stdin>'`.
  - Parent process raised `RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {'EngineCore': 1}`.
- Run log path: `logs/runs/20260523-124638-htfsd-generate-0514fb3a.json`
- Run log error/traceback summary:
  - `status`: `error`
  - `exit_code`: `1`
  - `exception_type`: `RuntimeError`
  - `message`: `Engine core initialization failed. See root cause above. Failed core proc(s): {'EngineCore': 1}`
  - Traceback shows failure during `_build_engine(config)` while loading the Gemma E2B vLLM handle via `src/runtime/vllm_adapter.py`.
- Diagnosis:
  - The fallback stdin-based Python invocation is incompatible with vLLM's forced `spawn` multiprocessing path in this WSL environment. The spawned child attempts to re-run the main module from `<stdin>`, which is not a real file path, causing engine startup to fail before generation.
- Fix method attempted/proposed:
  - No code, package, model, or config changes were attempted per task guardrails.
  - Proposed fix: run the CLI through a real script/module entry point instead of a stdin heredoc when vLLM requires `spawn`, for example by restoring the `htfsd-generate` console script or invoking a file-backed module entry point.
  - Concrete rerun option without installing the package:

```bash
timeout 600 env PYTHONPATH=src python -m cli.generate \
  --config configs/local.yaml \
  --prompt "Hello"
```

  - Concrete environment fix to restore console scripts:

```bash
python -m pip install -e .
```

- Recommendation:
  - Re-run this smoke test once a file-backed CLI invocation is available in the environment. Keep the prompt redaction check in place; this failed run's structured log redacted the prompt and did not include raw `Hello`.

## Planned Resolution

- Make `--config` optional for `htfsd-generate`, defaulting to `configs/local.yaml`.
- Use file-backed invocations for vLLM smoke tests:
  - `htfsd-generate --prompt "Hello"`
  - `PYTHONPATH=src python -m cli.generate --prompt "Hello"`
- Do not use stdin heredoc for commands that initialize vLLM under WSL.
