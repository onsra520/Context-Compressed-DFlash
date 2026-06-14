import pytest
import sys
import os

# Ensure the scripts directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.analyze_task80b_rerun_issue_gate import (
    extract_vram_reserved,
    extract_vram_allocated,
    extract_prefill_ms,
    extract_tau_mean,
    classify_completeness,
    process_delta_row,
    generate_decision
)

def test_extract_vram_reserved():
    assert extract_vram_reserved({"vram_reserved_gib": 1.5}) == 1.5
    assert extract_vram_reserved({"prefill_vram_reserved_gib": "2.5"}) == 2.5
    assert extract_vram_reserved({"max_vram_reserved_gib": 3.0}) == 3.0
    assert extract_vram_reserved({"missing": 1.0}) is None
    assert extract_vram_reserved({"vram_reserved_gib": None}) is None

def test_extract_vram_allocated():
    assert extract_vram_allocated({"vram_allocated_gib": 1.1}) == 1.1
    assert extract_vram_allocated({"prefill_vram_allocated_gib": "2.2"}) == 2.2
    assert extract_vram_allocated({"max_vram_allocated_gib": 3.3}) == 3.3
    assert extract_vram_allocated({"missing": 1.0}) is None
    assert extract_vram_allocated({"vram_allocated_gib": None}) is None

def test_extract_prefill_ms():
    assert extract_prefill_ms({"t_prefill_ms": 100}) == 100.0
    assert extract_prefill_ms({"avg_t_prefill_ms": 200.5}) == 200.5
    assert extract_prefill_ms({"missing": 100}) is None
    assert extract_prefill_ms({"t_prefill_ms": None}) is None

def test_extract_tau_mean():
    assert extract_tau_mean({"tau_mean": 1.8}) == 1.8
    assert extract_tau_mean({"avg_tau_mean": 2.1}) == 2.1
    assert extract_tau_mean({"missing": 1.0}) is None
    assert extract_tau_mean({"tau_mean": None}) is None

def test_classify_completeness():
    assert classify_completeness(30, 30) == "completed"
    assert classify_completeness(0, 30) == "skipped"
    assert classify_completeness(2, 30) == "failed_partial"

def test_process_delta_row_skipped():
    row = {
        "condition": "CC-DFlash-R2",
        "dataset": "qmsum_meeting_qa_long",
        "metric": "avg_overlap_proxy",
        "task80a_value": "0.0",
        "delta": "-0.35",
        "relative_delta_percent": "-100",
        "severity": "ok"
    }
    c_row = process_delta_row(row, 0)
    assert c_row["task80a_value"] == "skipped"
    assert c_row["delta"] == "not_comparable"
    assert c_row["relative_delta_percent"] == "not_comparable"
    assert c_row["severity"] == "skipped"

def test_process_delta_row_partial():
    row = {
        "condition": "DFlash-R1",
        "dataset": "qmsum_meeting_qa_long",
        "metric": "e2e_tok_s",
        "task80a_value": "11.5",
        "delta": "-7.9",
        "relative_delta_percent": "-40.8",
        "severity": "watch"
    }
    c_row = process_delta_row(row, 2)
    assert c_row["task80a_value"] == "partial_run_not_comparable"
    assert c_row["delta"] == "partial_run_not_comparable"
    assert c_row["relative_delta_percent"] == "partial_run_not_comparable"
    assert c_row["severity"] == "partial_run"

def test_process_delta_row_count_major_shift():
    row = {
        "condition": "DFlash-R1",
        "dataset": "qmsum_meeting_qa_long",
        "metric": "row_count",
        "task80a_value": "2",
        "delta": "-28",
        "relative_delta_percent": "-93",
        "severity": "watch"
    }
    c_row = process_delta_row(row, 2)
    assert c_row["severity"] == "row_count_major_shift"
    # value is kept as 2
    assert c_row["task80a_value"] == "2"

def test_generate_decision():
    d = generate_decision()
    assert d["decision"] == "D"
    assert d["t80c_needed"] is False
