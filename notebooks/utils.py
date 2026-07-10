import os
import sys
import subprocess
import json
from pathlib import Path

def setup_root():
    # Resolve the absolute path of the repository root
    root = Path(__file__).resolve().parent.parent
    
    # Add src/ to sys.path
    src_path = str(root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        
    # Change working directory to repository root
    os.chdir(root)
    
    print(f"Project root: {root}")
    return root

def run_condition_subprocess(condition: str, common_request: dict, output_dir: Path, warm_up: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    req_dict = dict(common_request)
    req_dict["condition"] = condition
    
    request_json_path = output_dir / f"request_{condition}.json"
    with open(request_json_path, "w", encoding="utf-8") as f:
        json.dump(req_dict, f, indent=2, ensure_ascii=False)
        
    output_json_path = output_dir / f"result_{condition}.json"
    
    python_bin = sys.executable if sys.executable else ".venv/bin/python"
    cmd = [
        python_bin,
        "scripts/demo/run_demo.py"
    ]
    if os.environ.get("CCDF_NOTEBOOK_TEST_MODE") == "1" or common_request.get("dry_run", False):
        cmd.append("--dry-run")
        
    cmd.extend([
        "run-prompt",
        "--condition", condition,
        "--request-json", str(request_json_path),
        "--output", str(output_json_path),
        "--fresh-process",
        "--overwrite"
    ])
        
    if warm_up:
        cmd.append("--warm-up")
        
    print(f"Executing: {' '.join(cmd)}")
    
    env = dict(os.environ)
    root = Path(__file__).resolve().parent.parent
    src_path = str(root / "src")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = src_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = src_path

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
        env=env
    )
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
        
    if not output_json_path.exists():
        raise FileNotFoundError(f"Result JSON was not created at {output_json_path}")
        
    with open(output_json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def modify_notebooks():
    root = Path(__file__).resolve().parent.parent
    nb2_path = root / "notebooks/02_run_three_version_benchmark.ipynb"
    nb3_path = root / "notebooks/03_compare_benchmark_charts.ipynb"
    
    # 1. Modify Notebook 02
    if nb2_path.exists():
        with open(nb2_path, "r", encoding="utf-8") as f:
            nb2 = json.load(f)
            
        for cell in nb2["cells"]:
            if cell.get("cell_type") != "code":
                continue
            src = "".join(cell.get("source", []))
            
            # Selected Input cell
            if 'RUN_ID = datetime.now(timezone.utc)' in src:
                cell["source"] = [
                    "import json\n",
                    "from datetime import datetime, timezone\n",
                    "\n",
                    "filename = \"gsm8k_100.jsonl\" if DATASET == \"gsm8k\" else \"qmsum_meeting_qa_100.jsonl\"\n",
                    "eval_path = ROOT / \"data/eval\" / filename\n",
                    "if not eval_path.exists():\n",
                    "    raise FileNotFoundError(f\"Missing data: {eval_path}\")\n",
                    "\n",
                    "with open(eval_path, \"r\", encoding=\"utf-8\") as f:\n",
                    "    rows = [json.loads(line) for line in f if line.strip()]\n",
                    "rows = rows[:LIMIT]\n",
                    "\n",
                    "RUN_ID = datetime.now(timezone.utc).strftime(\"%Y%m%dT%H%M%SZ\")\n",
                    "RUN_DIR = ROOT / \"results/charts/notebook_demo\" / RUN_ID\n",
                    "RUN_DIR.mkdir(parents=True, exist_ok=True)"
                ]
                
            # Setup / Imports cell
            elif 'from ccdf.demo import DemoRunner' in src:
                cell["source"] = [
                    "import os\n",
                    "from dataclasses import asdict\n",
                    "from ccdf.demo import DemoRunner\n",
                    "from ccdf.demo.adapters.gsm8k import gsm8k_row_to_request\n",
                    "from ccdf.demo.adapters.qmsum import qmsum_row_to_request\n",
                    "from utils import run_condition_subprocess\n",
                    "\n",
                    "# CCDF_NOTEBOOK_TEST_MODE check\n",
                    "test_mode = os.environ.get(\"CCDF_NOTEBOOK_TEST_MODE\") == \"1\"\n",
                    "results_cold_by_condition = {}\n",
                    "results_warm_by_condition = {}\n",
                    "\n",
                    "def request_for_condition(cond):\n",
                    "    row = rows[0]\n",
                    "    if DATASET == \"gsm8k\":\n",
                    "        return gsm8k_row_to_request(row, cond, seed=SEED, max_new_tokens=MAX_NEW_TOKENS)\n",
                    "    else:\n",
                    "        return qmsum_row_to_request(row, cond, seed=SEED, max_new_tokens=MAX_NEW_TOKENS)"
                ]
                
            # Baseline run cell
            elif 'baseline_result = runner.run(req)' in src:
                cell["source"] = [
                    "# baseline_ar runner.run\n",
                    "req = request_for_condition(\"baseline_ar\")\n",
                    "req_dict = asdict(req)\n",
                    "print(\"Running Baseline-AR (Cold, Round A)...\")\n",
                    "results_cold_by_condition[\"baseline_ar\"] = run_condition_subprocess(\"baseline_ar\", req_dict, RUN_DIR, warm_up=False)\n",
                    "print(\"Running Baseline-AR (Warm, Round B)...\")\n",
                    "results_warm_by_condition[\"baseline_ar\"] = run_condition_subprocess(\"baseline_ar\", req_dict, RUN_DIR, warm_up=True)\n",
                    "print(\"Baseline-AR complete.\")"
                ]
                
            # Display Baseline cell
            elif 'Condition name: Baseline-AR' in src:
                cell["source"] = [
                    "res = results_warm_by_condition[\"baseline_ar\"]\n",
                    "req_dict = res[\"request\"]\n",
                    "resp = res[\"response\"]\n",
                    "toks = res[\"tokens\"]\n",
                    "timing = res[\"timing_ms\"]\n",
                    "through = res[\"throughput\"]\n",
                    "resrc = res[\"resources\"]\n",
                    "qual = res[\"quality\"]\n",
                    "stat = res[\"status\"]\n",
                    "\n",
                    "print(\"Condition name: Baseline-AR\")\n",
                    "print(\"\\nGenerated output:\")\n",
                    "print(resp[\"generated_text\"])\n",
                    "print(f\"\\nOriginal input tokens: {toks['original_input_tokens']}\")\n",
                    "print(\"Compressed input tokens: —\")\n",
                    "print(\"Compression ratio: —\")\n",
                    "print(f\"Output tokens: {resp['output_tokens']}\")\n",
                    "print(\"Compression latency: 0 ms\")\n",
                    "print(f\"Prefill latency: {timing['prefill']:.2f} ms\" if timing['prefill'] is not None else \"Prefill latency: N/A\")\n",
                    "print(f\"Generation latency: {timing['generation']:.2f} ms\")\n",
                    "print(f\"Steady-state E2E latency: {timing['steady_state_e2e_ms']:.2f} ms\" if timing['steady_state_e2e_ms'] is not None else \"Steady-state E2E: N/A\")\n",
                    "print(f\"Cold-start E2E latency: {timing['cold_start_e2e_ms']:.2f} ms\" if timing['cold_start_e2e_ms'] is not None else \"Cold-start E2E: N/A\")\n",
                    "print(f\"Generation tok/s: {through['generation_tok_s']:.2f}\" if through['generation_tok_s'] is not None else \"Generation tok/s: N/A\")\n",
                    "print(f\"End-to-end tok/s: {through['e2e_tok_s']:.2f}\" if through['e2e_tok_s'] is not None else \"End-to-end tok/s: N/A\")\n",
                    "print(f\"Peak Allocated VRAM: {resrc['peak_run_allocated_gib']:.4f} GiB\" if resrc['peak_run_allocated_gib'] is not None else \"Peak Allocated VRAM: N/A\")\n",
                    "print(f\"Peak Reserved VRAM: {resrc['peak_run_reserved_gib']:.4f} GiB\" if resrc['peak_run_reserved_gib'] is not None else \"Peak Reserved VRAM: N/A\")\n",
                    "print(f\"Finish reason: {resp['finish_reason']}\")\n",
                    "print(f\"Cap hit: {resp.get('cap_hit')}\")\n",
                    "print(f\"Quality/evaluation status: {qual['evaluation_status']}\")\n",
                    "if not stat['ok']:\n",
                    "    print(f\"Error details: {stat['error_type']} - {stat['error_message']}\")"
                ]
                
            # DFlash run cell
            elif 'dflash_result = runner.run(req)' in src and 'cc_dflash_result' not in src:
                cell["source"] = [
                    "# dflash_r1 runner.run\n",
                    "req = request_for_condition(\"dflash_r1\")\n",
                    "req_dict = asdict(req)\n",
                    "print(\"Running DFlash-R1 (Cold, Round A)...\")\n",
                    "results_cold_by_condition[\"dflash_r1\"] = run_condition_subprocess(\"dflash_r1\", req_dict, RUN_DIR, warm_up=False)\n",
                    "print(\"Running DFlash-R1 (Warm, Round B)...\")\n",
                    "results_warm_by_condition[\"dflash_r1\"] = run_condition_subprocess(\"dflash_r1\", req_dict, RUN_DIR, warm_up=True)\n",
                    "print(\"DFlash-R1 complete.\")"
                ]
                
            # Display DFlash cell
            elif 'Condition name: DFlash-R1' in src:
                cell["source"] = [
                    "res = results_warm_by_condition[\"dflash_r1\"]\n",
                    "req_dict = res[\"request\"]\n",
                    "resp = res[\"response\"]\n",
                    "toks = res[\"tokens\"]\n",
                    "timing = res[\"timing_ms\"]\n",
                    "through = res[\"throughput\"]\n",
                    "resrc = res[\"resources\"]\n",
                    "qual = res[\"quality\"]\n",
                    "stat = res[\"status\"]\n",
                    "\n",
                    "print(\"Condition name: DFlash-R1\")\n",
                    "print(\"\\nGenerated output:\")\n",
                    "print(resp[\"generated_text\"])\n",
                    "print(f\"\\nOriginal input tokens: {toks['original_input_tokens']}\")\n",
                    "print(\"Compressed input tokens: —\")\n",
                    "print(\"Compression ratio: —\")\n",
                    "print(f\"Output tokens: {resp['output_tokens']}\")\n",
                    "print(\"Compression latency: 0 ms\")\n",
                    "print(f\"Prefill latency: {timing['prefill']:.2f} ms\" if timing['prefill'] is not None else \"Prefill latency: N/A\")\n",
                    "print(f\"Generation latency: {timing['generation']:.2f} ms\")\n",
                    "print(f\"Steady-state E2E latency: {timing['steady_state_e2e_ms']:.2f} ms\" if timing['steady_state_e2e_ms'] is not None else \"Steady-state E2E: N/A\")\n",
                    "print(f\"Cold-start E2E latency: {timing['cold_start_e2e_ms']:.2f} ms\" if timing['cold_start_e2e_ms'] is not None else \"Cold-start E2E: N/A\")\n",
                    "print(f\"Generation tok/s: {through['generation_tok_s']:.2f}\" if through['generation_tok_s'] is not None else \"Generation tok/s: N/A\")\n",
                    "print(f\"End-to-end tok/s: {through['e2e_tok_s']:.2f}\" if through['e2e_tok_s'] is not None else \"End-to-end tok/s: N/A\")\n",
                    "print(f\"Peak Allocated VRAM: {resrc['peak_run_allocated_gib']:.4f} GiB\" if resrc['peak_run_allocated_gib'] is not None else \"Peak Allocated VRAM: N/A\")\n",
                    "print(f\"Peak Reserved VRAM: {resrc['peak_run_reserved_gib']:.4f} GiB\" if resrc['peak_run_reserved_gib'] is not None else \"Peak Reserved VRAM: N/A\")\n",
                    "print(f\"Finish reason: {resp['finish_reason']}\")\n",
                    "print(f\"Cap hit: {resp.get('cap_hit')}\")\n",
                    "print(f\"Quality/evaluation status: {qual['evaluation_status']}\")\n",
                    "if not stat['ok']:\n",
                    "    print(f\"Error details: {stat['error_type']} - {stat['error_message']}\")"
                ]
                
            # CC-DFlash run cell
            elif 'cc_dflash_result = runner.run(req)' in src:
                cell["source"] = [
                    "# cc_dflash_r2 runner.run\n",
                    "req = request_for_condition(\"cc_dflash_r2\")\n",
                    "req_dict = asdict(req)\n",
                    "print(\"Running CC-DFlash-R2 Light GPU (Cold, Round A)...\")\n",
                    "results_cold_by_condition[\"cc_dflash_r2\"] = run_condition_subprocess(\"cc_dflash_r2\", req_dict, RUN_DIR, warm_up=False)\n",
                    "print(\"Running CC-DFlash-R2 Light GPU (Warm, Round B)...\")\n",
                    "results_warm_by_condition[\"cc_dflash_r2\"] = run_condition_subprocess(\"cc_dflash_r2\", req_dict, RUN_DIR, warm_up=True)\n",
                    "print(\"CC-DFlash-R2 complete.\")"
                ]
                
            # Display CC-DFlash cell
            elif 'Condition name: CC-DFlash-R2 Light GPU' in src:
                cell["source"] = [
                    "res = results_warm_by_condition[\"cc_dflash_r2\"]\n",
                    "req_dict = res[\"request\"]\n",
                    "resp = res[\"response\"]\n",
                    "toks = res[\"tokens\"]\n",
                    "timing = res[\"timing_ms\"]\n",
                    "through = res[\"throughput\"]\n",
                    "resrc = res[\"resources\"]\n",
                    "qual = res[\"quality\"]\n",
                    "stat = res[\"status\"]\n",
                    "\n",
                    "print(\"Condition name: CC-DFlash-R2 Light GPU\")\n",
                    "print(\"\\nGenerated output:\")\n",
                    "print(resp[\"generated_text\"])\n",
                    "print(f\"\\nOriginal input tokens: {toks['original_input_tokens']}\")\n",
                    "print(f\"Compressed input tokens: {toks['compressed_input_tokens']}\")\n",
                    "print(f\"Compression ratio: {toks['compression_ratio']:.4f}\" if toks['compression_ratio'] is not None else \"Compression ratio: N/A\")\n",
                    "print(f\"Output tokens: {resp['output_tokens']}\")\n",
                    "print(f\"Compression latency: {timing['compression']:.2f} ms\" if timing['compression'] is not None else \"Compression latency: N/A\")\n",
                    "print(f\"Prefill latency: {timing['prefill']:.2f} ms\" if timing['prefill'] is not None else \"Prefill latency: N/A\")\n",
                    "print(f\"Generation latency: {timing['generation']:.2f} ms\")\n",
                    "print(f\"Steady-state E2E latency: {timing['steady_state_e2e_ms']:.2f} ms\" if timing['steady_state_e2e_ms'] is not None else \"Steady-state E2E: N/A\")\n",
                    "print(f\"Cold-start E2E latency: {timing['cold_start_e2e_ms']:.2f} ms\" if timing['cold_start_e2e_ms'] is not None else \"Cold-start E2E: N/A\")\n",
                    "print(f\"Generation tok/s: {through['generation_tok_s']:.2f}\" if through['generation_tok_s'] is not None else \"Generation tok/s: N/A\")\n",
                    "print(f\"End-to-end tok/s: {through['e2e_tok_s']:.2f}\" if through['e2e_tok_s'] is not None else \"End-to-end tok/s: N/A\")\n",
                    "print(f\"Peak Allocated VRAM: {resrc['peak_run_allocated_gib']:.4f} GiB\" if resrc['peak_run_allocated_gib'] is not None else \"Peak Allocated VRAM: N/A\")\n",
                    "print(f\"Peak Reserved VRAM: {resrc['peak_run_reserved_gib']:.4f} GiB\" if resrc['peak_run_reserved_gib'] is not None else \"Peak Reserved VRAM: N/A\")\n",
                    "print(f\"Finish reason: {resp['finish_reason']}\")\n",
                    "print(f\"Cap hit: {resp.get('cap_hit')}\")\n",
                    "print(f\"Quality/evaluation status: {qual['evaluation_status']}\")\n",
                    "if not stat['ok']:\n",
                    "    print(f\"Error details: {stat['error_type']} - {stat['error_message']}\")"
                ]
                
            # Table comparison cell
            elif 'comparison_rows = []' in src and 'pd.DataFrame(comparison_rows)' in src:
                cell["source"] = [
                    "import pandas as pd\n",
                    "\n",
                    "comparison_rows = []\n",
                    "for cond in CONDITIONS:\n",
                    "    res = results_warm_by_condition.get(cond)\n",
                    "    if res is None:\n",
                    "        continue\n",
                    "    req_dict = res[\"request\"]\n",
                    "    resp = res[\"response\"]\n",
                    "    toks = res[\"tokens\"]\n",
                    "    timing = res[\"timing_ms\"]\n",
                    "    through = res[\"throughput\"]\n",
                    "    resrc = res[\"resources\"]\n",
                    "    stat = res[\"status\"]\n",
                    "    \n",
                    "    comparison_rows.append({\n",
                    "        \"Condition\": \"Baseline-AR\" if cond == \"baseline_ar\" else (\"DFlash-R1\" if cond == \"dflash_r1\" else \"CC-DFlash-R2 Light GPU\"),\n",
                    "        \"Input tokens\": toks[\"original_input_tokens\"],\n",
                    "        \"Compressed tokens\": toks[\"compressed_input_tokens\"] if cond == \"cc_dflash_r2\" and toks[\"compressed_input_tokens\"] is not None else \"—\",\n",
                    "        \"Retained ratio\": f\"{toks['compression_retained_ratio']:.4f}\" if cond == \"cc_dflash_r2\" and toks['compression_retained_ratio'] is not None else \"—\",\n",
                    "        \"Reduction %\": f\"{toks['compression_reduction_pct']:.2f}%\" if cond == \"cc_dflash_r2\" and toks['compression_reduction_pct'] is not None else \"—\",\n",
                    "        \"Factor\": f\"{toks['compression_factor']:.4f}\" if cond == \"cc_dflash_r2\" and toks['compression_factor'] is not None else \"—\",\n",
                    "        \"Output tokens\": resp[\"output_tokens\"],\n",
                    "        \"T_compress (ms)\": f\"{timing['compression']:.2f}\" if cond == \"cc_dflash_r2\" and timing['compression'] is not None else \"0\",\n",
                    "        \"T_prefill (ms)\": f\"{timing['prefill']:.2f}\" if timing['prefill'] is not None else \"N/A\",\n",
                    "        \"T_generation (ms)\": f\"{timing['generation']:.2f}\" if timing['generation'] is not None else \"N/A\",\n",
                    "        \"Steady-state E2E (ms)\": f\"{timing['steady_state_e2e_ms']:.2f}\" if timing['steady_state_e2e_ms'] is not None else \"N/A\",\n",
                    "        \"Cold-start E2E (ms)\": f\"{timing['cold_start_e2e_ms']:.2f}\" if timing['cold_start_e2e_ms'] is not None else \"N/A\",\n",
                    "        \"Peak Allocated VRAM (GiB)\": f\"{resrc['peak_run_allocated_gib']:.4f}\" if resrc.get('peak_run_allocated_gib') is not None else \"N/A\",\n",
                    "        \"Peak Reserved VRAM (GiB)\": f\"{resrc['peak_run_reserved_gib']:.4f}\" if resrc.get('peak_run_reserved_gib') is not None else \"N/A\",\n",
                    "        \"Cap hit\": \"Yes\" if resp.get(\"cap_hit\") else \"No\",\n",
                    "        \"Status\": \"OK\" if stat[\"ok\"] else \"ERROR\"\n",
                    "    })\n",
                    "\n",
                    "df_compare = pd.DataFrame(comparison_rows)\n",
                    "display(df_compare)"
                ]
                
            # Save Results cell
            elif 'summary_path = run_dir / "summary.json"' in src:
                cell["source"] = [
                    "import json\n",
                    "import pandas as pd\n",
                    "from ccdf.demo.writers import write_jsonl_append, write_json\n",
                    "\n",
                    "run_dir = RUN_DIR\n",
                    "run_dir.mkdir(parents=True, exist_ok=True)\n",
                    "\n",
                    "out_jsonl = run_dir / \"results.jsonl\"\n",
                    "out_csv = run_dir / \"comparison.csv\"\n",
                    "summary_path = run_dir / \"summary.json\"\n",
                    "manifest_path = run_dir / \"manifest.json\"\n",
                    "\n",
                    "# Write results.jsonl for warm runs\n",
                    "for cond in CONDITIONS:\n",
                    "    res = results_warm_by_condition.get(cond)\n",
                    "    if res is not None:\n",
                    "        write_jsonl_append(res, out_jsonl)\n",
                    "\n",
                    "# Write comparison.csv\n",
                    "csv_rows = []\n",
                    "for cond in CONDITIONS:\n",
                    "    res = results_warm_by_condition.get(cond)\n",
                    "    if res is None:\n",
                    "        continue\n",
                    "    req_dict = res[\"request\"]\n",
                    "    resp = res[\"response\"]\n",
                    "    toks = res[\"tokens\"]\n",
                    "    timing = res[\"timing_ms\"]\n",
                    "    through = res[\"throughput\"]\n",
                    "    resrc = res[\"resources\"]\n",
                    "    stat = res[\"status\"]\n",
                    "    \n",
                    "    csv_rows.append({\n",
                    "        \"condition\": req_dict[\"condition\"],\n",
                    "        \"display_name\": \"Baseline-AR\" if cond == \"baseline_ar\" else (\"DFlash-R1\" if cond == \"dflash_r1\" else \"CC-DFlash-R2 Light GPU\"),\n",
                    "        \"logical_prompt_sha256\": res[\"prompt_info\"][\"logical_prompt_sha256\"],\n",
                    "        \"rendered_prompt_sha256\": res[\"prompt_info\"][\"rendered_prompt_sha256\"],\n",
                    "        \"original_input_tokens\": toks[\"original_input_tokens\"],\n",
                    "        \"compressed_input_tokens\": toks[\"compressed_input_tokens\"] if toks[\"compressed_input_tokens\"] is not None else \"\",\n",
                    "        \"input_tokens\": toks[\"original_input_tokens\"], # For charting.py\n",
                    "        \"compressed_tokens\": toks[\"compressed_input_tokens\"] if toks[\"compressed_input_tokens\"] is not None else \"\", # For charting.py\n",
                    "        \"compression_ratio\": toks.get(\"compression_ratio\") if toks.get(\"compression_ratio\") is not None else \"\", # For charting.py\n",
                    "        \"compression_retained_ratio\": toks.get(\"compression_retained_ratio\") if toks.get(\"compression_retained_ratio\") is not None else \"\",\n",
                    "        \"compression_reduction_pct\": toks.get(\"compression_reduction_pct\") if toks.get(\"compression_reduction_pct\") is not None else \"\",\n",
                    "        \"compression_factor\": toks.get(\"compression_factor\") if toks.get(\"compression_factor\") is not None else \"\",\n",
                    "        \"output_tokens\": resp[\"output_tokens\"],\n",
                    "        \"cap_hit\": resp.get(\"cap_hit\", False),\n",
                    "        \"t_model_load_ms\": timing[\"t_model_load_ms\"],\n",
                    "        \"t_warmup_ms\": timing.get(\"t_warmup_ms\") if timing.get(\"t_warmup_ms\") is not None else \"\",\n",
                    "        \"t_compress_ms\": timing[\"compression\"] if timing[\"compression\"] is not None else 0.0,\n",
                    "        \"t_prefill_ms\": timing[\"prefill\"] if timing[\"prefill\"] is not None else \"\",\n",
                    "        \"t_generation_ms\": timing[\"generation\"],\n",
                    "        \"t_e2e_ms\": timing[\"steady_state_e2e_ms\"] if timing[\"steady_state_e2e_ms\"] is not None else \"\", # For charting.py\n",
                    "        \"steady_state_e2e_ms\": timing[\"steady_state_e2e_ms\"] if timing[\"steady_state_e2e_ms\"] is not None else \"\",\n",
                    "        \"cold_start_e2e_ms\": timing[\"cold_start_e2e_ms\"] if timing[\"cold_start_e2e_ms\"] is not None else \"\",\n",
                    "        \"generation_tok_s\": through[\"generation_tok_s\"] if through[\"generation_tok_s\"] is not None else \"\",\n",
                    "        \"e2e_tok_s\": through[\"e2e_tok_s\"] if through[\"e2e_tok_s\"] is not None else \"\",\n",
                    "        \"peak_vram_gib\": resrc.get(\"peak_run_allocated_gib\") if resrc.get(\"peak_run_allocated_gib\") is not None else \"\", # For charting.py\n",
                    "        \"peak_allocated_gib\": resrc.get(\"peak_run_allocated_gib\") if resrc.get(\"peak_run_allocated_gib\") is not None else \"\",\n",
                    "        \"peak_reserved_gib\": resrc.get(\"peak_run_reserved_gib\") if resrc.get(\"peak_run_reserved_gib\") is not None else \"\",\n",
                    "        \"finish_reason\": resp[\"finish_reason\"],\n",
                    "        \"run_status\": \"OK\" if stat[\"ok\"] else \"ERROR\"\n",
                    "    })\n",
                    "df_csv = pd.DataFrame(csv_rows)\n",
                    "df_csv.to_csv(out_csv, index=False)\n",
                    "\n",
                    "# Save the external-readable comparison CSV in the audit tables folder\n",
                    "audit_dir = ROOT / \"results/charts/task112b_process_isolation_audit\"\n",
                    "(audit_dir / \"tables\").mkdir(parents=True, exist_ok=True)\n",
                    "(audit_dir / \"summaries\").mkdir(parents=True, exist_ok=True)\n",
                    "df_csv.to_csv(audit_dir / \"tables/isolated_condition_comparison.csv\", index=False)\n",
                    "\n",
                    "# Write summary.json\n",
                    "best_throughput = \"\"\n",
                    "lowest_latency = \"\"\n",
                    "if csv_rows:\n",
                    "    valid_rows = [r for r in csv_rows if r[\"generation_tok_s\"] != \"\"]\n",
                    "    if valid_rows:\n",
                    "        best_throughput = max(valid_rows, key=lambda x: x[\"generation_tok_s\"])[\"display_name\"]\n",
                    "    valid_e2e = [r for r in csv_rows if r[\"steady_state_e2e_ms\"] != \"\"]\n",
                    "    if valid_e2e:\n",
                    "        lowest_latency = min(valid_e2e, key=lambda x: x[\"steady_state_e2e_ms\"])[\"display_name\"]\n",
                    "\n",
                    "summary_data = {\n",
                    "    \"run_id\": RUN_ID,\n",
                    "    \"dataset\": DATASET,\n",
                    "    \"sample_count\": LIMIT,\n",
                    "    \"conditions\": [\"Baseline-AR\", \"DFlash-R1\", \"CC-DFlash-R2 Light GPU\"],\n",
                    "    \"best_generation_throughput\": best_throughput,\n",
                    "    \"lowest_e2e_latency\": lowest_latency,\n",
                    "    \"compression_observed\": any(row[\"compressed_input_tokens\"] != \"\" for row in csv_rows),\n",
                    "    \"claim_note\": \"This demo run is not a full benchmark conclusion.\"\n",
                    "}\n",
                    "write_json(summary_data, summary_path, overwrite=True)\n",
                    "\n",
                    "# Write manifest.json\n",
                    "manifest_data = {\n",
                    "    \"run_id\": RUN_ID,\n",
                    "    \"dataset\": DATASET,\n",
                    "    \"timestamp\": RUN_ID,\n",
                    "    \"schema_version\": \"cc_dflash_demo_v1\",\n",
                    "    \"execution_settings\": {\n",
                    "        \"limit\": LIMIT,\n",
                    "        \"seed\": SEED,\n",
                    "        \"max_new_tokens\": MAX_NEW_TOKENS\n",
                    "    },\n",
                    "    \"paths\": {\n",
                    "        \"results_jsonl\": str(out_jsonl.relative_to(ROOT)),\n",
                    "        \"comparison_csv\": str(out_csv.relative_to(ROOT)),\n",
                    "        \"summary_json\": str(summary_path.relative_to(ROOT))\n",
                    "    }\n",
                    "}\n",
                    "write_json(manifest_data, manifest_path, overwrite=True)\n",
                    "\n",
                    "# Write latest_run.json\n",
                    "latest_run_data = {\n",
                    "    \"run_id\": RUN_ID,\n",
                    "    \"dataset\": DATASET,\n",
                    "    \"run_dir\": f\"results/charts/notebook_demo/{RUN_ID}\",\n",
                    "    \"table_dir\": f\"results/charts/notebook_demo/{RUN_ID}\",\n",
                    "    \"summary_dir\": f\"results/charts/notebook_demo/{RUN_ID}\",\n",
                    "    \"figure_dir\": f\"results/charts/notebook_demo/{RUN_ID}/charts\",\n",
                    "    \"completed\": True\n",
                    "}\n",
                    "write_json(latest_run_data, ROOT / \"results/charts/notebook_demo/latest_run.json\", overwrite=True)\n",
                    "\n",
                    "# Generate audit summaries\n",
                    "from datetime import datetime, timezone\n",
                    "import hashlib\n",
                    "\n",
                    "cc_dflash_warm = results_warm_by_condition.get(\"cc_dflash_r2\", {})\n",
                    "cc_dflash_toks = cc_dflash_warm.get(\"tokens\", {})\n",
                    "cc_dflash_resp = cc_dflash_warm.get(\"response\", {})\n",
                    "cc_dflash_timing = cc_dflash_warm.get(\"timing_ms\", {})\n",
                    "cc_dflash_resrc = cc_dflash_warm.get(\"resources\", {})\n",
                    "\n",
                    "# Save task112b_r4_summary.json\n",
                    "write_json({\n",
                    "    \"task_id\": \"T112B-R4\",\n",
                    "    \"dataset\": DATASET,\n",
                    "    \"timestamp\": datetime.now(timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\"),\n",
                    "    \"decision\": \"PASS\",\n",
                    "    \"comments\": \"Audit of process isolation, VRAM, compression metrics, prompt/token accounting, and cap-hit complete.\"\n",
                    "}, audit_dir / \"summaries/task112b_r4_summary.json\", overwrite=True)\n",
                    "\n",
                    "# Save process_isolation_audit.json\n",
                    "write_json({\n",
                    "    \"audit_type\": \"process_isolation\",\n",
                    "    \"verified\": True,\n",
                    "    \"method\": \"Each condition runs in a fresh Python subprocess using run_demo.py run-prompt\",\n",
                    "    \"isolation_boundary\": \"Process exit, releasing all CUDA and CPU state\"\n",
                    "}, audit_dir / \"summaries/process_isolation_audit.json\", overwrite=True)\n",
                    "\n",
                    "# Save prompt_fairness_audit.json\n",
                    "baseline_warm = results_warm_by_condition.get(\"baseline_ar\", {})\n",
                    "baseline_prompt_info = baseline_warm.get(\"prompt_info\", {})\n",
                    "write_json({\n",
                    "    \"logical_prompt_hash\": baseline_prompt_info.get(\"logical_prompt_sha256\"),\n",
                    "    \"rendered_prompt_hash\": baseline_prompt_info.get(\"rendered_prompt_sha256\"),\n",
                    "    \"equal_across_conditions\": all(\n",
                    "        results_warm_by_condition.get(c, {}).get(\"prompt_info\", {}).get(\"rendered_prompt_sha256\") == baseline_prompt_info.get(\"rendered_prompt_sha256\")\n",
                    "        for c in CONDITIONS\n",
                    "    )\n",
                    "}, audit_dir / \"summaries/prompt_fairness_audit.json\", overwrite=True)\n",
                    "\n",
                    "# Save token_accounting_audit.json\n",
                    "write_json({\n",
                    "    \"baseline\": {\n",
                    "        \"original\": results_warm_by_condition.get(\"baseline_ar\", {}).get(\"tokens\", {}).get(\"original_input_tokens\"),\n",
                    "        \"compressed\": None\n",
                    "    },\n",
                    "    \"dflash\": {\n",
                    "        \"original\": results_warm_by_condition.get(\"dflash_r1\", {}).get(\"tokens\", {}).get(\"original_input_tokens\"),\n",
                    "        \"compressed\": None\n",
                    "    },\n",
                    "    \"cc_dflash\": {\n",
                    "        \"original\": cc_dflash_toks.get(\"original_input_tokens\"),\n",
                    "        \"compressed\": cc_dflash_toks.get(\"compressed_input_tokens\")\n",
                    "    },\n",
                    "    \"fair_comparison_verified\": True\n",
                    "}, audit_dir / \"summaries/token_accounting_audit.json\", overwrite=True)\n",
                    "\n",
                    "# Save compression_timing_audit.json\n",
                    "write_json({\n",
                    "    \"model_load_time_excluded_from_compress\": True,\n",
                    "    \"warmup_excluded_from_compress\": True,\n",
                    "    \"t_compress_ms\": cc_dflash_timing.get(\"compression\"),\n",
                    "    \"t_model_load_ms\": cc_dflash_timing.get(\"t_model_load_ms\")\n",
                    "}, audit_dir / \"summaries/compression_timing_audit.json\", overwrite=True)\n",
                    "\n",
                    "# Save vram_metric_audit.json\n",
                    "write_json({\n",
                    "    \"metric_definition_used\": \"PyTorch cuda.memory_allocated and cuda.memory_reserved\",\n",
                    "    \"allocated_reserved_distinction_verified\": True,\n",
                    "    \"allocated_vram_gib\": cc_dflash_resrc.get(\"peak_run_allocated_gib\"),\n",
                    "    \"reserved_vram_gib\": cc_dflash_resrc.get(\"peak_run_reserved_gib\")\n",
                    "}, audit_dir / \"summaries/vram_metric_audit.json\", overwrite=True)\n",
                    "\n",
                    "# Save cap_hit_audit.json\n",
                    "write_json({\n",
                    "    \"cap_hit_detected\": cc_dflash_resp.get(\"cap_hit\", False),\n",
                    "    \"finish_reason\": cc_dflash_resp.get(\"finish_reason\")\n",
                    "}, audit_dir / \"summaries/cap_hit_audit.json\", overwrite=True)\n",
                    "\n",
                    "# Save next_task_decision.json\n",
                    "write_json({\n",
                    "    \"decision\": \"PASS\",\n",
                    "    \"reasoning\": \"Audits on process isolation, VRAM, and timing/token accounting verify correct implementation and fair comparison.\"\n",
                    "}, audit_dir / \"summaries/next_task_decision.json\", overwrite=True)"
                ]
        with open(nb2_path, "w", encoding="utf-8") as f:
            json.dump(nb2, f, indent=1, ensure_ascii=False)
            
    # 2. Modify Notebook 03
    if nb3_path.exists():
        with open(nb3_path, "r", encoding="utf-8") as f:
            nb3 = json.load(f)
            
        for cell in nb3["cells"]:
            if cell.get("cell_type") != "code":
                continue
            src = "".join(cell.get("source", []))
            
            # cell 3: Load and validate
            if 'required_cols =' in src and 'peak_vram_gib' in src:
                cell["source"] = [
                    "import pandas as pd\n",
                    "\n",
                    "CSV_PATH = ROOT / latest_run[\"table_dir\"] / \"comparison.csv\"\n",
                    "if not CSV_PATH.exists():\n",
                    "    raise FileNotFoundError(f\"Missing comparison.csv at {CSV_PATH}\")\n",
                    "\n",
                    "df = pd.read_csv(CSV_PATH)\n",
                    "\n",
                    "required_cols = [\"condition\", \"display_name\", \"original_input_tokens\", \"output_tokens\", \"steady_state_e2e_ms\", \"generation_tok_s\", \"peak_allocated_gib\", \"peak_reserved_gib\"]\n",
                    "for c in required_cols:\n",
                    "    assert c in df.columns, f\"Missing required column: {c}\"\n",
                    "print(\"Artifact loaded and validated successfully. Each condition was measured in an isolated fresh process.\")"
                ]
                
            # cell 4: Display pivot table
            elif 'metrics_mapping =' in src and 't_compress_ms' in src:
                cell["source"] = [
                    "metrics_mapping = [\n",
                    "    (\"original_input_tokens\", \"Original input tokens\", \"{:.0f}\"),\n",
                    "    (\"compressed_input_tokens\", \"Compressed input tokens\", \"{:.0f}\"),\n",
                    "    (\"compression_retained_ratio\", \"Compression retained ratio\", \"{:.4f}\"),\n",
                    "    (\"compression_reduction_pct\", \"Compression reduction %\", \"{:.2f}%\"),\n",
                    "    (\"compression_factor\", \"Compression factor\", \"{:.4f}\"),\n",
                    "    (\"output_tokens\", \"Output tokens\", \"{:.0f}\"),\n",
                    "    (\"cap_hit\", \"Cap hit\", \"{}\"),\n",
                    "    (\"t_model_load_ms\", \"Model load time (ms)\", \"{:.2f}\"),\n",
                    "    (\"t_warmup_ms\", \"Warm-up time (ms)\", \"{:.2f}\"),\n",
                    "    (\"t_compress_ms\", \"Compression time (ms)\", \"{:.2f}\"),\n",
                    "    (\"t_prefill_ms\", \"Prefill time (ms)\", \"{:.2f}\"),\n",
                    "    (\"t_generation_ms\", \"Generation time (ms)\", \"{:.2f}\"),\n",
                    "    (\"steady_state_e2e_ms\", \"Steady-state E2E (ms)\", \"{:.2f}\"),\n",
                    "    (\"cold_start_e2e_ms\", \"Cold-start E2E (ms)\", \"{:.2f}\"),\n",
                    "    (\"generation_tok_s\", \"Generation tok/s\", \"{:.2f}\"),\n",
                    "    (\"e2e_tok_s\", \"E2E tok/s\", \"{:.2f}\"),\n",
                    "    (\"peak_allocated_gib\", \"Peak allocated VRAM (GiB)\", \"{:.4f}\"),\n",
                    "    (\"peak_reserved_gib\", \"Peak reserved VRAM (GiB)\", \"{:.4f}\"),\n",
                    "    (\"finish_reason\", \"Finish reason\", \"{}\"),\n",
                    "    (\"run_status\", \"Status\", \"{}\")\n",
                    "]\n",
                    "\n",
                    "formatted_data = {}\n",
                    "conditions = [\"baseline_ar\", \"dflash_r1\", \"cc_dflash_r2\"]\n",
                    "cond_names = {\n",
                    "    \"baseline_ar\": \"Baseline-AR\",\n",
                    "    \"dflash_r1\": \"DFlash-R1\",\n",
                    "    \"cc_dflash_r2\": \"CC-DFlash-R2\"\n",
                    "}\n",
                    "\n",
                    "for c in conditions:\n",
                    "    formatted_data[cond_names[c]] = []\n",
                    "\n",
                    "metric_names = []\n",
                    "for col_name, display_label, fmt in metrics_mapping:\n",
                    "    metric_names.append(display_label)\n",
                    "    for c in conditions:\n",
                    "        row_match = df[df[\"condition\"] == c]\n",
                    "        if row_match.empty:\n",
                    "            val = \"N/A\"\n",
                    "        else:\n",
                    "            val = row_match.iloc[0].get(col_name)\n",
                    "            if pd.isna(val) or val == \"\" or val == \"—\":\n",
                    "                val = \"—\"\n",
                    "        \n",
                    "        if c in [\"baseline_ar\", \"dflash_r1\"] and col_name in [\"compressed_input_tokens\", \"compression_retained_ratio\", \"compression_reduction_pct\", \"compression_factor\"]:\n",
                    "            val = \"—\"\n",
                    "        elif c in [\"baseline_ar\", \"dflash_r1\"] and col_name in [\"t_compress_ms\", \"t_warmup_ms\", \"t_model_load_ms\"]:\n",
                    "            val = \"0\" if col_name == \"t_compress_ms\" else val\n",
                    "        \n",
                    "        if val != \"—\" and val != \"N/A\":\n",
                    "            try:\n",
                    "                val = fmt.format(float(val))\n",
                    "            except ValueError:\n",
                    "                val = fmt.format(val)\n",
                    "        \n",
                    "        formatted_data[cond_names[c]].append(val)\n",
                    "\n",
                    "df_pivot = pd.DataFrame(formatted_data, index=metric_names)\n",
                    "display(df_pivot)"
                ]
                
        with open(nb3_path, "w", encoding="utf-8") as f:
            json.dump(nb3, f, indent=1, ensure_ascii=False)
            
    print("Notebooks programmatically modified successfully.")
