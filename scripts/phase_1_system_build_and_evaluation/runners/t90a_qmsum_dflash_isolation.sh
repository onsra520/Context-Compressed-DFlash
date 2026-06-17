#!/bin/bash
set -e

export PYTHONPATH=src
PYTHON=".venv/bin/python"
SCRIPT="scripts/run_mvp.py"
OUT_DIR="results/phase_1_system_build_and_evaluation/repair_and_gate"

log_system_state() {
    date
    nvidia-smi || true
    free -h || true
    pgrep -af "run_mvp.py|python" || true
    echo "----------------------------------------"
}

run_experiment() {
    local ds=$1
    local cond_arg=$2
    local n_val=$3
    local out_slug=$4

    local out_file="${OUT_DIR}/${out_slug}.jsonl"
    local log_file="${OUT_DIR}/${out_slug}.log"

    echo "Running Experiment: ${out_slug}"
    log_system_state >> "$log_file" 2>&1

    # Run in background to easily capture exit code and allow timeout or direct segfault capture
    set +e
    $PYTHON $SCRIPT --dataset $ds --condition $cond_arg --n $n_val --output "$out_file" --resume --store-generated-text >> "$log_file" 2>&1
    local exit_code=$?
    set -e

    echo "Exit code: $exit_code" >> "$log_file"
    log_system_state >> "$log_file" 2>&1
    
    echo "Finished Experiment: ${out_slug} with exit code $exit_code"
    if [ $exit_code -ne 0 ]; then
        echo "Crash detected. Stopping further experiments."
        exit $exit_code
    fi
}

echo "=== Experiment A: QMSum DFlash-R1 isolated (n=1) ==="
run_experiment "qmsum_meeting_qa_long" "DFlash-R1" 1 "task90a_qmsum_dflash_r1_isolated_n1"

echo "=== Experiment B: QMSum DFlash-R1 isolated (n=3) ==="
run_experiment "qmsum_meeting_qa_long" "DFlash-R1" 3 "task90a_qmsum_dflash_r1_isolated_n3"

echo "=== Experiment C: Sequential stress check ==="
run_experiment "gsm8k_short" "Baseline-AR" 1 "task90a_sequence_1_gsm8k_baseline_n1"
run_experiment "gsm8k_short" "DFlash-R1" 1 "task90a_sequence_2_gsm8k_dflash_n1"
run_experiment "qmsum_meeting_qa_long" "Baseline-AR" 1 "task90a_sequence_3_qmsum_baseline_n1"
run_experiment "qmsum_meeting_qa_long" "DFlash-R1" 1 "task90a_sequence_4_qmsum_dflash_n1"

echo "All experiments completed successfully."
