"""
Dedicated smoke test driver for the three required scenarios.
Connects to an already-running API server on 127.0.0.1:8001.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8001"
RESULTS_DIR = Path("results/Frontend-API-Integration")


def post_json(path: str, data: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def read_sse(path: str, timeout: float = 600) -> list[tuple[str, str]]:
    """Read SSE stream until connection closes. Returns [(event, data), ...]."""
    req = urllib.request.Request(BASE + path)
    events: list[tuple[str, str]] = []
    current_event: str | None = None
    current_data: str | None = None

    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw_line in r:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                current_data = line[5:].strip()
            elif line == "":
                if current_event and current_data is not None:
                    events.append((current_event, current_data))
                    print(f"  [SSE] {current_event}: {current_data[:100]}")
                current_event = None
                current_data = None
            # Skip keepalive comments (lines starting with :)
    return events


def run_scenario(
    name: str,
    prompt: str,
    compression_device: str,
    *,
    expect_cc_bypass: bool = False,
    expect_cc_applied: bool = False,
) -> dict:
    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"Device: {compression_device}")
    print(f"Prompt preview: {prompt[:80]!r}...")
    print("=" * 60)

    t0 = time.monotonic()
    resp = post_json("/api/compare", {"input": prompt, "compression_device": compression_device})
    job_id = resp["job_id"]
    print(f"Job ID: {job_id}")

    events = read_sse(f"/api/compare/{job_id}/events")
    elapsed = time.monotonic() - t0

    event_names = [e for e, _ in events]
    completed_events = [(e, json.loads(d)) for e, d in events if e == "condition.completed"]
    failed_events = [(e, json.loads(d)) for e, d in events if e in ("condition.failed", "job.failed")]

    # Assertions
    assert "job.started" in event_names, f"FAIL: job.started missing from {event_names}"
    assert "job.completed" in event_names or "job.failed" in event_names, "FAIL: no terminal event"
    assert "comparison.completed" in event_names or "job.failed" in event_names, "FAIL: no comparison.completed"

    result = {
        "scenario": name,
        "device": compression_device,
        "job_id": job_id,
        "elapsed_s": round(elapsed, 1),
        "event_names": event_names,
        "conditions": {},
        "failures": failed_events,
        "pass": True,
    }

    for _, cdata in completed_events:
        cid = cdata["condition_id"]
        result["conditions"][cid] = cdata
        print(f"\n  [{cid}]")
        print(f"    generated_text: {cdata.get('generated_text', '')[:60]!r}")
        print(f"    output_tokens: {cdata.get('output_tokens')}")
        print(f"    decode_total_ms: {cdata.get('decode_total_ms')}")
        print(f"    warm_request_e2e_ms: {cdata.get('warm_request_e2e_ms')}")
        print(f"    compression_applied: {cdata.get('compression_applied')}")
        print(f"    compression_bypassed: {cdata.get('compression_bypassed')}")
        print(f"    compression_bypass_reason: {cdata.get('compression_bypass_reason')}")
        print(f"    effective_tau: {cdata.get('effective_tau')}")

    cc_cid = "cc-dflash-r2-gpu" if compression_device == "cuda" else "cc-dflash-r2"
    cc = result["conditions"].get(cc_cid)

    if cc:
        if expect_cc_bypass:
            if not cc.get("compression_bypassed"):
                result["pass"] = False
                result["fail_reason"] = f"Expected bypass for {cc_cid} but got compression_bypassed=False"
                print(f"  FAIL: Expected bypass but compression_bypassed={cc.get('compression_bypassed')}")
        if expect_cc_applied:
            if not cc.get("compression_applied"):
                result["pass"] = False
                result["fail_reason"] = f"Expected compression applied for {cc_cid} but got compression_applied=False"
                print(f"  FAIL: Expected compression_applied but got {cc.get('compression_applied')}")

    if failed_events:
        result["pass"] = False
        result["fail_reason"] = str(failed_events)

    status = "PASS" if result["pass"] else "FAIL"
    print(f"\nScenario result: {status} ({elapsed:.1f} s)")
    return result


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Health check
    health = post_json("/api/health", {}) if False else json.loads(
        urllib.request.urlopen(BASE + "/api/health").read()
    )
    caps = json.loads(urllib.request.urlopen(BASE + "/api/capabilities").read())
    print(f"Server health: {health}")
    print(f"Capabilities: {caps}")

    results = {}

    # Scenario 1: Question-only, CPU
    results["scenario1"] = run_scenario(
        "Question-only, CPU",
        "What is the capital of France?",
        "cpu",
        expect_cc_bypass=True,
    )

    # Scenario 2: Context + question, CPU
    context_prompt = (
        "Alice: We need to finalize the offline sync approach for the mobile release. "
        "The current build retries every 10 seconds, causing duplicate uploads on unstable networks.\n"
        "Bob: The backend team can add idempotency keys, though not before the next release candidate.\n"
        "Carla: Product wants the release this Friday. We can accept limited offline mode if pending records are shown.\n"
        "Alice: Proposal: keep local changes, show pending badge, retry after stable connection.\n\n"
        "What decision was made about offline synchronization?"
    )
    results["scenario2"] = run_scenario(
        "Context + question, CPU",
        context_prompt,
        "cpu",
        expect_cc_applied=True,
    )

    # Scenario 3: Context + question, CUDA (if available)
    if caps.get("cuda_available"):
        results["scenario3"] = run_scenario(
            "Context + question, CUDA",
            context_prompt,
            "cuda",
            expect_cc_applied=True,
        )
    else:
        results["scenario3"] = {"scenario": "Context + question, CUDA", "pass": "SKIPPED", "reason": "CUDA not available"}

    # Write report
    report_path = RESULTS_DIR / "report.md"
    all_pass = all(
        r.get("pass") is True or r.get("pass") == "SKIPPED"
        for r in results.values()
    )

    with open(report_path, "w") as f:
        f.write("# CC-DFlash Frontend-API Integration Report\n\n")
        f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Overall:** {'PASS' if all_pass else 'FAIL'}\n\n")

        for key, r in results.items():
            f.write(f"## {r['scenario']}\n")
            f.write(f"- **Status:** {r.get('pass')}\n")
            f.write(f"- **Device:** {r.get('device', 'N/A')}\n")
            f.write(f"- **Elapsed:** {r.get('elapsed_s', 'N/A')} s\n")
            f.write(f"- **Events:** {r.get('event_names', 'N/A')}\n")
            if r.get("fail_reason"):
                f.write(f"- **Failure:** {r['fail_reason']}\n")
            f.write("\n")
            for cid, cdata in (r.get("conditions") or {}).items():
                f.write(f"### {cid}\n")
                for k, v in cdata.items():
                    if k != "generated_text":
                        f.write(f"- `{k}`: `{v}`\n")
                f.write(f"- `generated_text`: {cdata.get('generated_text', '')[:200]!r}\n\n")

    # Save raw results
    with open(RESULTS_DIR / "raw_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    print(f"Report: {report_path}")
    print(f"Raw:    {RESULTS_DIR / 'raw_results.json'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
