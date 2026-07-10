import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def generate_charts_for_dataset(csv_path: str, dataset: str):
    # Retained for compatibility / secondary use
    df = pd.read_csv(csv_path)
    cond_order = ["baseline_ar", "dflash_r1", "cc_dflash_r2"]
    
    # We yield some simple figures if needed, but primary is the dashboard
    metrics = {
        "average_e2e_latency.png": ("t_e2e_ms", "E2E Latency (ms)"),
        "generation_throughput.png": ("generation_tok_s", "Generation Throughput (tokens/s)"),
        "e2e_throughput.png": ("e2e_tok_s", "E2E Throughput (tokens/s)"),
        "peak_vram.png": ("peak_vram_gib", "Peak VRAM (GiB)"),
    }
    sample_count = df.groupby("condition").size().max() if "condition" in df.columns else 1
    
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

def build_three_version_dashboard(df_or_csv, dataset: str, run_id: str):
    import numpy as np
    
    if isinstance(df_or_csv, (str, Path)):
        df = pd.read_csv(df_or_csv)
    else:
        df = df_or_csv
        
    conditions = ["baseline_ar", "dflash_r1", "cc_dflash_r2"]
    cond_labels = ["Baseline-AR", "DFlash-R1", "CC-DFlash-R2 Light GPU"]
    
    num_rows = 7
    num_cols = 3
    
    fig, axes = plt.subplots(num_rows, num_cols, figsize=(14, 18), dpi=180)
    fig.suptitle(f"Three-Version Comparison Dashboard - {dataset.upper()} (Run: {run_id})\n", fontsize=16, fontweight="bold", y=0.98)
    
    def draw_card(ax, value_text, label_text, color):
        ax.clear()
        ax.set_facecolor(color)
        rect = plt.Rectangle((0, 0), 1, 1, facecolor=color, transform=ax.transAxes, zorder=0)
        ax.add_patch(rect)
        ax.text(0.5, 0.6, value_text, ha='center', va='center', fontsize=18, fontweight='bold', color='#1a1a1a', transform=ax.transAxes)
        ax.text(0.5, 0.25, label_text, ha='center', va='center', fontsize=9, color='#444444', transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_edgecolor('#cccccc')
            spine.set_linewidth(1)

    for col_idx, cond in enumerate(conditions):
        row_match = df[df["condition"] == cond]
        has_data = not row_match.empty
        
        if has_data:
            r = row_match.iloc[0]
            input_tok = r.get("input_tokens", r.get("original_input_tokens"))
            comp_tok = r.get("compressed_tokens", r.get("compressed_input_tokens"))
            comp_ratio = r.get("compression_ratio")
            t_comp = r.get("t_compress_ms")
            t_prefill = r.get("t_prefill_ms")
            t_gen = r.get("t_generation_ms")
            t_e2e = r.get("t_e2e_ms")
            gen_toks = r.get("generation_tok_s")
            e2e_toks = r.get("e2e_tok_s")
            vram = r.get("peak_vram_gib")
            q_status = r.get("quality_status", r.get("evaluation_status", ""))
            run_stat = r.get("run_status", "OK" if r.get("ok", True) else "ERROR")
        else:
            input_tok = comp_tok = comp_ratio = t_comp = t_prefill = t_gen = t_e2e = gen_toks = e2e_toks = vram = q_status = run_stat = None
        
        # Row 0: Input / Compressed Tokens
        if cond in ["baseline_ar", "dflash_r1"]:
            val_text = f"{int(input_tok)}" if input_tok is not None and not pd.isna(input_tok) else "N/A"
            lbl_text = "Input Tokens (No Comp)"
        else:
            in_val = f"{int(input_tok)}" if input_tok is not None and not pd.isna(input_tok) else "N/A"
            c_val = f"{int(comp_tok)}" if comp_tok is not None and not pd.isna(comp_tok) and comp_tok != "" and comp_tok != "—" else "—"
            val_text = f"{in_val} / {c_val}"
            lbl_text = "Input / Compressed Tokens"
        draw_card(axes[0, col_idx], val_text, lbl_text, "#e6f2ff")
        axes[0, col_idx].set_title(cond_labels[col_idx], fontsize=12, fontweight="bold", pad=10)
        
        # Row 1: Compression Ratio & Latency
        if cond in ["baseline_ar", "dflash_r1"]:
            val_text = "—"
            lbl_text = "Compression: N/A"
        else:
            ratio_val = f"{float(comp_ratio):.2f}x" if comp_ratio is not None and not pd.isna(comp_ratio) and comp_ratio != "" and comp_ratio != "—" else "—"
            t_comp_val = f"{float(t_comp):.1f} ms" if t_comp is not None and not pd.isna(t_comp) and t_comp != "" and t_comp != "—" else "—"
            val_text = f"{ratio_val} ({t_comp_val})"
            lbl_text = "Ratio (Latency)"
        draw_card(axes[1, col_idx], val_text, lbl_text, "#fff2e6")
        
        # Row 2: Prefill / Generation Latency
        prefill_val = f"{float(t_prefill):.1f} ms" if t_prefill is not None and not pd.isna(t_prefill) else "N/A"
        gen_val = f"{float(t_gen):.1f} ms" if t_gen is not None and not pd.isna(t_gen) else "N/A"
        val_text = f"{prefill_val} / {gen_val}"
        lbl_text = "Prefill / Generation Latency"
        draw_card(axes[2, col_idx], val_text, lbl_text, "#e6ffe6")
        
        # Row 3: E2E Latency
        e2e_val = f"{float(t_e2e):.1f} ms" if t_e2e is not None and not pd.isna(t_e2e) else "N/A"
        val_text = e2e_val
        lbl_text = "End-to-End Latency"
        draw_card(axes[3, col_idx], val_text, lbl_text, "#ffe6e6")
        
        # Row 4: Throughput (Gen / E2E)
        gen_ts = f"{float(gen_toks):.1f} tok/s" if gen_toks is not None and not pd.isna(gen_toks) else "N/A"
        e2e_ts = f"{float(e2e_toks):.1f} tok/s" if e2e_toks is not None and not pd.isna(e2e_toks) else "N/A"
        val_text = f"{gen_ts} / {e2e_ts}"
        lbl_text = "Gen / E2E Throughput"
        draw_card(axes[4, col_idx], val_text, lbl_text, "#f9e6ff")
        
        # Row 5: Peak VRAM
        vram_val = f"{float(vram):.2f} GiB" if vram is not None and not pd.isna(vram) else "N/A"
        val_text = vram_val
        lbl_text = "Peak VRAM"
        draw_card(axes[5, col_idx], val_text, lbl_text, "#ffffcc")
        
        # Row 6: Quality / Run Status
        if run_stat == "ERROR":
            val_text = "ERROR"
            card_color = "#ffcccc"
        else:
            val_text = f"OK ({q_status})" if q_status else "OK"
            card_color = "#e6ffff"
        draw_card(axes[6, col_idx], val_text, "Quality & Execution Status", card_color)
        
    plt.tight_layout()
    return fig
