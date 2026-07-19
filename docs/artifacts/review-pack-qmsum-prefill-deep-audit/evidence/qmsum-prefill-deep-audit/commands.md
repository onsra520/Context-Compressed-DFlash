# Commands used

All commands were run from `D:\projects\CCDF-Rework`; every GPU probe was orchestrated as a fresh process with `-X faulthandler`, a 120-second timeout, and a 7,680 MiB physical-VRAM kill gate.

```powershell
.\.venv\Scripts\python.exe -X faulthandler tests\run_qmsum_prefill_deep_audit.py --output-root docs\artifacts\qmsum-prefill-deep-audit --profile --snapshot
```

Supplemental forced-backend and standard-generate cases used `--single-case` with these JSON cases:

```text
{"length":2048,"backend":"efficient","mask":"none","forward_path":"standard","use_cache":"true"}
{"length":2048,"backend":"flash","mask":"none","forward_path":"standard","use_cache":"true"}
{"length":2048,"backend":"auto","mask":"none","forward_path":"generate","use_cache":"true"}
{"length":2048,"backend":"auto","mask":"ones","forward_path":"generate","use_cache":"true"}
```

Post-patch safety gate:

```powershell
.\.venv\Scripts\python.exe -X faulthandler tests\run_qmsum_prefill_deep_audit.py --output-root docs\artifacts\qmsum-prefill-deep-audit-postpatch-no-profile --single-case '{"length":2048,"backend":"auto","mask":"ones","forward_path":"project","use_cache":"true"}'
```

Validation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_prefill_runner_overhead.py tests\test_dataset_smoke_watchdog.py tests\test_dataset_smoke_protocol.py tests\test_config.py
.\.venv\Scripts\python.exe -m ruff check src\ccdf\protocols\orchestrator.py src\ccdf\runtime\engine.py src\ccdf\inference\baseline.py src\ccdf\benchmark\dataset_smoke.py tests\test_prefill_runner_overhead.py tests\run_qmsum_prefill_probe.py tests\run_qmsum_prefill_deep_audit.py
git diff --check
```

The exact child command for every case is also stored in its `monitored-result.json` or `summary.json`.
