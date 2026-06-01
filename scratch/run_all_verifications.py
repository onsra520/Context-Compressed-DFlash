import subprocess
import sys

def run_cmd(cmd_list):
    print(f"\n========================================\nRunning: {' '.join(cmd_list)}\n========================================")
    res = subprocess.run(cmd_list, capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr)
    print(f"Exit code: {res.returncode}")
    return res.returncode

# 1. git status
run_cmd(["git", "status", "--short"])

# 2. git diff --stat
run_cmd(["git", "diff", "--stat"])

# 3. pytest phase 3.16
run_cmd([".venv/bin/pytest", "tests/test_phase_3_16_low_tier_speedup_blocker_audit.py", "-v"])

# 4. pytest phase 3.15
run_cmd([".venv/bin/pytest", "tests/test_phase_3_15_low_tier_benchmark_dry_run.py", "-v"])

# 5. prior regression tests
run_cmd([
    ".venv/bin/pytest",
    "tests/test_phase_3_14_low_tier_benchmark_protocol.py",
    "tests/test_phase_3_13_equivalence_harness.py",
    "tests/test_phase_3_13_fake_validation.py",
    "tests/test_phase_3_12_strict_accept_reject.py",
    "tests/test_phase_3_12_token_bridge.py",
    "tests/test_phase_3_12_backend_capabilities.py",
    "tests/test_phase_3_11_token_level_verifier_design.py",
    "tests/test_phase_3_10_dflash_correctness_spec.py",
    "-q"
])

# 6. git diff --check
run_cmd(["git", "diff", "--check"])
