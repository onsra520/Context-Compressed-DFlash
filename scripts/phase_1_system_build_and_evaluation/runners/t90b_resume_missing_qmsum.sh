#!/bin/bash
set -e

export PYTHONPATH=src
PYTHON=".venv/bin/python"
SCRIPT="scripts/run_mvp.py"
OUT_DIR="results/phase_1_system_build_and_evaluation/final_reruns"
LOG_DIR="results/phase_1_system_build_and_evaluation/repair_and_gate"

log_before() {
    local log_file=$1
    date >> "$log_file"
    nvidia-smi >> "$log_file" 2>&1 || true
    free -h >> "$log_file" 2>&1 || true
    pgrep -af "run_mvp.py|python" >> "$log_file" 2>&1 || true
    echo "----------------------------------------" >> "$log_file"
}

log_after() {
    local log_file=$1
    local exit_code=$2
    echo "exit_code=$exit_code" >> "$log_file"
    date >> "$log_file"
    nvidia-smi >> "$log_file" 2>&1 || true
    echo "========================================" >> "$log_file"
}

run_isolated() {
    local ds="qmsum_meeting_qa_long"
    local cond_arg=$1
    local out_slug=$2
    local log_slug=$3

    local out_file="${OUT_DIR}/task90_${ds}_${out_slug}_n3.jsonl"
    local log_file="${LOG_DIR}/${log_slug}.log"

    echo "Running Isolated Resume: condition=${cond_arg}"
    log_before "$log_file"

    set +e
    $PYTHON $SCRIPT --dataset $ds --condition $cond_arg --n 3 --output "$out_file" --resume --store-generated-text >> "$log_file" 2>&1
    local exit_code=$?
    set -e

    log_after "$log_file" $exit_code

    echo "Finished Isolated Resume: condition=${cond_arg} with exit code $exit_code"
    if [ $exit_code -ne 0 ]; then
        echo "Crash detected on condition=${cond_arg}. Stopping."
        exit $exit_code
    fi
}

echo "=== Resuming Task 90 Missing QMSum Conditions ==="
run_isolated "DFlash-R1" "dflash_r1" "task90b_qmsum_dflash_r1_resume"
run_isolated "LLMLingua-AR-R2" "llmlingua_ar_r2" "task90b_qmsum_llmlingua_ar_r2_resume"
run_isolated "CC-DFlash-R2" "cc_dflash_r2" "task90b_qmsum_cc_dflash_r2_resume"

echo "All isolated resume runs completed successfully."
