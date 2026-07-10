import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import os

def generate_charts_for_dataset(csv_path: str, dataset: str):
    df = pd.read_csv(csv_path)
    if "schema_version" not in df.columns or df["schema_version"].iloc[0] != "cc_dflash_demo_v1":
        raise ValueError(f"Invalid schema version in {csv_path}")
        
    
    # We expect condition to be baseline_ar, dflash_r1, cc_dflash_r2
    # Ensure they are ordered correctly
    cond_order = ["baseline_ar", "dflash_r1", "cc_dflash_r2"]
    
    df['condition'] = pd.Categorical(df['condition'], categories=cond_order, ordered=True)
    
    metrics = {
        "average_e2e_latency.png": ("t_e2e_ms", "E2E Latency (ms)"),
        "generation_throughput.png": ("generation_tok_s", "Generation Throughput (tokens/s)"),
        "e2e_throughput.png": ("e2e_tok_s", "E2E Throughput (tokens/s)"),
        "peak_vram.png": ("peak_vram_gib", "Peak VRAM (GiB)"),
    }
    
    sample_count = df.groupby("condition").size().max()
    
    for filename, (col, ylabel) in metrics.items():
        if col not in df.columns:
            continue
            
        fig, ax = plt.subplots(figsize=(8, 5))
        means = df.groupby("condition")[col].mean().reindex(cond_order)
        means.plot(kind="bar", ax=ax, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
        ax.set_title(f"{ylabel} - {dataset.upper()} (N={sample_count})")
        ax.set_ylabel(ylabel)
        ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
        plt.tight_layout()
        yield filename, fig
        
    # Input token comparison
    if "compressed_input_tokens" in df.columns and "original_input_tokens" in df.columns:
        fig, ax = plt.subplots(figsize=(8, 5))
        tokens_df = df.groupby("condition")[["original_input_tokens", "compressed_input_tokens"]].mean().reindex(cond_order)
        tokens_df.columns = ["Original Input Tokens", "Compressed Input Tokens"]
        tokens_df.plot(kind="bar", ax=ax)
        ax.set_title(f"Input Token Comparison - {dataset.upper()} (N={sample_count})")
        ax.set_ylabel("Tokens")
        ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
        plt.tight_layout()
        yield "input_token_comparison.png", fig
        
    # Latency breakdown
    timing_cols = ["t_compress_ms", "t_prefill_ms", "t_generation_ms"]
    if all(c in df.columns for c in timing_cols):
        fig, ax = plt.subplots(figsize=(8, 5))
        breakdown_df = df.groupby("condition")[timing_cols].mean().reindex(cond_order)
        breakdown_df.columns = ["Compression", "Prefill", "Generation"]
        breakdown_df.plot(kind="bar", stacked=True, ax=ax)
        ax.set_title(f"Latency Breakdown - {dataset.upper()} (N={sample_count})")
        ax.set_ylabel("Latency (ms)")
        ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
        plt.tight_layout()
        yield "latency_breakdown.png", fig
        
    # Dataset specific charts
    if dataset == "gsm8k":
        # Quality comparison (proxy)
        if "numeric_match" in df.columns:
            fig, ax = plt.subplots(figsize=(8, 5))
            # Treat numeric match as boolean/int
            df["numeric_match_int"] = df["numeric_match"].fillna(0).astype(int)
            acc = df.groupby("condition")["numeric_match_int"].mean().reindex(cond_order) * 100
            acc.plot(kind="bar", ax=ax, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
            ax.set_title(f"GSM8K Quality (Proxy Exact Match %) (N={sample_count})")
            ax.set_ylabel("Accuracy (%)")
            ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
            plt.tight_layout()
            yield "gsm8k_quality_comparison.png", fig
            
        fig, ax = plt.subplots(figsize=(8, 5))
        invalid = df.groupby("condition")["ok"].apply(lambda x: (~x.fillna(True)).sum()).reindex(cond_order)
        invalid.plot(kind="bar", ax=ax, color=["#d62728"] * 3)
        ax.set_title(f"GSM8K Failed/Invalid Rows (N={sample_count})")
        ax.set_ylabel("Count")
        ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
        plt.tight_layout()
        yield "gsm8k_cap_or_invalid_count.png", fig
        
    elif dataset == "qmsum":
        if "t_e2e_ms" in df.columns:
            fig, ax = plt.subplots(figsize=(8, 5))
            runtime = df.groupby("condition")["t_e2e_ms"].sum().reindex(cond_order) / 1000.0
            runtime.plot(kind="bar", ax=ax, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
            ax.set_title(f"QMSum Total Runtime (s) (N={sample_count})")
            ax.set_ylabel("Total Runtime (s)")
            ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
            plt.tight_layout()
            yield "qmsum_runtime_comparison.png", fig
            
        if "original_input_tokens" in df.columns and "compressed_input_tokens" in df.columns:
            fig, ax = plt.subplots(figsize=(8, 5))
            red = df.groupby("condition").apply(lambda x: (x["original_input_tokens"] - x["compressed_input_tokens"].fillna(x["original_input_tokens"])).sum()).reindex(cond_order)
            red.plot(kind="bar", ax=ax, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
            ax.set_title(f"QMSum Token Reduction (N={sample_count})")
            ax.set_ylabel("Tokens Reduced")
            ax.set_xticklabels(["Baseline-AR", "DFlash-R1", "CC-DFlash-R2"], rotation=0)
            plt.tight_layout()
            yield "qmsum_token_reduction.png", fig
