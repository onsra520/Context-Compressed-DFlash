import argparse
import gc
import json
import logging
import sys
import time
from pathlib import Path

import torch

from ccdf.compression.llmlingua import LLMLinguaCompressor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

QMSUM_DATA = Path("data/eval/qmsum_meeting_qa_100.jsonl")

class Profiler:
    def __init__(self):
        self.timings = {
            "outer_preprocessing": 0.0,
            "inner_preprocessing": 0.0,
            "forward_pass": 0.0,
            "token_scoring": 0.0,
            "compression_selection": 0.0,
            "outer_postprocessing": 0.0,
            "total_t_compress": 0.0
        }

profiler = Profiler()

def monkeypatch_llmlingua(compressor):
    # Monkeypatch the internal llmlingua methods
    pc = compressor._get_compressor()
    
    orig_chunk_context = pc._PromptCompressor__chunk_context
    orig_get_context_prob = pc._PromptCompressor__get_context_prob
    orig_compress = pc._PromptCompressor__compress
    
    def hooked_chunk_context(*args, **kwargs):
        t0 = time.perf_counter()
        res = orig_chunk_context(*args, **kwargs)
        profiler.timings["inner_preprocessing"] += (time.perf_counter() - t0) * 1000
        return res
        
    def hooked_get_context_prob(*args, **kwargs):
        t0 = time.perf_counter()
        res = orig_get_context_prob(*args, **kwargs)
        profiler.timings["forward_pass"] += (time.perf_counter() - t0) * 1000
        return res
        
    def hooked_compress(*args, **kwargs):
        t0 = time.perf_counter()
        res = orig_compress(*args, **kwargs)
        profiler.timings["compression_selection"] += (time.perf_counter() - t0) * 1000
        return res
        
    pc._PromptCompressor__chunk_context = hooked_chunk_context
    pc._PromptCompressor__get_context_prob = hooked_get_context_prob
    pc._PromptCompressor__compress = hooked_compress

    orig_model_forward = pc.model.forward

    def hooked_model_forward(*args, **kwargs):
        t0 = time.perf_counter()
        res = orig_model_forward(*args, **kwargs)
        profiler.timings["forward_pass"] += (time.perf_counter() - t0) * 1000
        return res
        
    pc.model.forward = hooked_model_forward

    # Also monkeypatch the outer LLMLinguaCompressor wrapper to catch preprocessing
    orig_chunk_plan = compressor._chunk_plan
    
    def hooked_chunk_plan(*args, **kwargs):
        t0 = time.perf_counter()
        res = orig_chunk_plan(*args, **kwargs)
        profiler.timings["outer_preprocessing"] += (time.perf_counter() - t0) * 1000
        return res
        
    compressor._chunk_plan = hooked_chunk_plan

def get_vram_stats():
    if not torch.cuda.is_available():
        return {"allocated_mb": 0.0, "reserved_mb": 0.0}
    return {
        "allocated_mb": torch.cuda.memory_allocated() / (1024 ** 2),
        "reserved_mb": torch.cuda.memory_reserved() / (1024 ** 2)
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Number of rows for smoke test")
    args = parser.parse_args()

    # 1. Load data
    rows = []
    with open(QMSUM_DATA, "r") as f:
        for i, line in enumerate(f):
            if i >= args.n:
                break
            rows.append(json.loads(line))
            
    vram_trace = {}
    vram_trace["before_load"] = get_vram_stats()

    # 2. CPU compressor test
    logging.info("Testing CPU Compressor (Default)")
    compressor_cpu = LLMLinguaCompressor(device_map="cpu", default_keep_rate=0.5)
    _ = compressor_cpu._get_compressor() # force load
    vram_trace["after_cpu_load"] = get_vram_stats()
    
    monkeypatch_llmlingua(compressor_cpu)
    
    total_cpu_time = 0.0
    for row in rows:
        context = row.get("context", row.get("source", ""))
        question = row.get("question", row.get("query", ""))
        t0 = time.perf_counter()
        _, _ = compressor_cpu.compress(context, question, keep_rate=0.5)
        total_cpu_time += (time.perf_counter() - t0) * 1000
        
    profiler.timings["total_t_compress"] = total_cpu_time
    
    # Calculate postprocessing overhead
    measured_subtimings = (
        profiler.timings["outer_preprocessing"] +
        profiler.timings["inner_preprocessing"] +
        profiler.timings["forward_pass"] +
        profiler.timings["compression_selection"]
    )
    profiler.timings["outer_postprocessing"] = total_cpu_time - measured_subtimings
    
    # Save latency breakdown
    lat_file = Path("results/task85_compression_latency_breakdown.json")
    lat_file.parent.mkdir(exist_ok=True, parents=True)
    with open(lat_file, "w") as f:
        json.dump(profiler.timings, f, indent=2)
        
    # Free CPU compressor
    del compressor_cpu
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # 3. GPU Compressor Mode
    logging.info("Testing GPU Compressor Mode in Subprocess")
    if torch.cuda.is_available():
        import subprocess
        
        gpu_script = f"""
import time, json, gc, sys
import torch
from ccdf.compression.llmlingua import LLMLinguaCompressor

def get_vram_stats():
    return {{
        "allocated_mb": torch.cuda.memory_allocated() / (1024 ** 2),
        "reserved_mb": torch.cuda.memory_reserved() / (1024 ** 2)
    }}

rows = []
import json
with open('{QMSUM_DATA}', 'r') as f:
    for i, line in enumerate(f):
        if i >= {args.n}: break
        rows.append(json.loads(line))

vram_trace = {{}}
try:
    t0 = time.perf_counter()
    compressor_gpu = LLMLinguaCompressor(device_map="cuda", default_keep_rate=0.5)
    _ = compressor_gpu._get_compressor()
    t_load = (time.perf_counter() - t0) * 1000
    vram_trace["after_gpu_load"] = get_vram_stats()
    
    gpu_time = 0.0
    for row in rows:
        context = row.get("context", row.get("source", ""))
        question = row.get("question", row.get("query", ""))
        t0 = time.perf_counter()
        _, _ = compressor_gpu.compress(context, question, keep_rate=0.5)
        gpu_time += (time.perf_counter() - t0) * 1000
    
    vram_trace["after_gpu_forward"] = get_vram_stats()
    
    t0 = time.perf_counter()
    del compressor_gpu
    gc.collect()
    torch.cuda.empty_cache()
    t_unload = (time.perf_counter() - t0) * 1000
    vram_trace["after_gpu_unload"] = get_vram_stats()
    
    with open("results/task85_load_unload_architecture.json", "w") as f:
        json.dump({{"t_load_compressor_ms": t_load, "t_compress_gpu_ms": gpu_time, "t_unload_compressor_ms": t_unload}}, f)
    with open("results/task85_vram_trace_gpu.json", "w") as f:
        json.dump(vram_trace, f)
except Exception as e:
    sys.exit(1)
"""
        with open("scripts/temp_gpu_test.py", "w") as f:
            f.write(gpu_script)
            
        result = subprocess.run([sys.executable, "scripts/temp_gpu_test.py"], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"GPU Compressor subprocess failed (likely OOM or Segfault). Return code: {result.returncode}")
            vram_trace["gpu_error"] = "Subprocess crashed (Segfault/OOM)."
        else:
            logging.info("GPU Compressor succeeded.")
            with open("results/task85_load_unload_architecture.json", "r") as f:
                arch_stats = json.load(f)
            arch_stats["t_total_compress_pass_ms"] = arch_stats["t_load_compressor_ms"] + arch_stats["t_compress_gpu_ms"] + arch_stats["t_unload_compressor_ms"]
            arch_stats["t_cpu_compress_ms"] = total_cpu_time
            arch_stats["load_unload_viable"] = arch_stats["t_total_compress_pass_ms"] < total_cpu_time
            with open("results/task85_load_unload_architecture.json", "w") as f:
                json.dump(arch_stats, f, indent=2)
                
            with open("results/task85_vram_trace_gpu.json", "r") as f:
                gpu_vram = json.load(f)
            vram_trace.update(gpu_vram)
            Path("scripts/temp_gpu_test.py").unlink(missing_ok=True)
            Path("results/task85_vram_trace_gpu.json").unlink(missing_ok=True)
    
    # Write VRAM trace
    with open("results/task85_vram_trace.json", "w") as f:
        json.dump(vram_trace, f, indent=2)
        
    # Write CSVs
    import csv
    with open("results/task85_compression_latency_breakdown.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value_ms"])
        for k, v in profiler.timings.items():
            writer.writerow([k, v])
            
    with open("results/task85_vram_trace.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["state", "allocated_mb", "reserved_mb"])
        for k, v in vram_trace.items():
            if isinstance(v, dict) and "allocated_mb" in v:
                writer.writerow([k, v["allocated_mb"], v["reserved_mb"]])

    # 5. Cached/Precompressed Upper Bound
    cached_upper_bound = {
        "online_t_compress_ms": total_cpu_time,
        "offline_t_compress_ms": 0.0,
        "theoretical_e2e_improvement_ms": total_cpu_time
    }
    with open("results/task85_cached_compression_upper_bound.json", "w") as f:
        json.dump(cached_upper_bound, f, indent=2)

    with open("results/task85_cached_compression_upper_bound.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in cached_upper_bound.items():
            writer.writerow([k, v])

if __name__ == "__main__":
    main()
