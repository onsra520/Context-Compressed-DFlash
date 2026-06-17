#!/bin/bash
set -e

# Task 88 n=30 Rerun Execution Script

export PYTHONPATH=src
BASE_CMD=".venv/bin/python scripts/run_mvp.py --n 30 --prompt-source dataset --seed 42 --max-new-tokens 512 --store-generated-text --resume"

# Function to run benchmark
run_bench() {
    dataset=$1
    condition=$2
    cond_slug=$3
    extra_flags=$4

    output_file="results/phase_1_system_build_and_evaluation/final_reruns/task88_${dataset}_${cond_slug}_n30.jsonl"
    echo "Running ${dataset} - ${condition}"
    
    $BASE_CMD --dataset "$dataset" --condition "$condition" --output "$output_file" $extra_flags
}

# 1. GSM8K Short
run_bench "gsm8k_short" "Baseline-AR" "baseline_ar" ""
run_bench "gsm8k_short" "DFlash-R1" "dflash_r1" ""
run_bench "gsm8k_short" "LLMLingua-AR-R2" "llmlingua_ar_r2" "--keep-rate-percent 50"
run_bench "gsm8k_short" "CC-DFlash-R2" "cc_dflash_r2" "--keep-rate-percent 50"

# 2. QMSum Long
run_bench "qmsum_meeting_qa_long" "Baseline-AR" "baseline_ar" ""
run_bench "qmsum_meeting_qa_long" "DFlash-R1" "dflash_r1" ""
run_bench "qmsum_meeting_qa_long" "LLMLingua-AR-R2" "llmlingua_ar_r2" "--keep-rate-percent 50"
run_bench "qmsum_meeting_qa_long" "CC-DFlash-R2" "cc_dflash_r2" "--keep-rate-percent 50"

echo "Task 88 benchmark run complete."
