from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# We will implement custom metrics here instead of relying on task70 script 
# to keep this script self-contained with new deterministic heuristics.

QMSUM_FILES = {
    "Baseline-AR": Path("results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_baseline_ar_n30.jsonl"),
    "DFlash-R1": Path("results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_dflash_r1_n30.jsonl"),
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_llmlingua_ar_r2_n30.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_cc_dflash_r2_n30.jsonl"),
}

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've",
    "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's",
    "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
    "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            rows.append(row)
        except Exception:
            continue
    return rows

def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")

def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure stable ordering of fields
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0

def _tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.split()

def normalized_token_overlap(ref: str, gen: str) -> float:
    ref_toks = set(_tokenize(ref))
    gen_toks = set(_tokenize(gen))
    if not ref_toks or not gen_toks:
        return 0.0
    return len(ref_toks & gen_toks) / min(len(ref_toks), len(gen_toks))

def content_word_overlap(ref: str, gen: str) -> float:
    ref_toks = set(t for t in _tokenize(ref) if t not in STOPWORDS)
    gen_toks = set(t for t in _tokenize(gen) if t not in STOPWORDS)
    if not ref_toks or not gen_toks:
        return 0.0
    return len(ref_toks & gen_toks) / min(len(ref_toks), len(gen_toks))

def answer_containment_proxy(ref: str, gen: str) -> float:
    ref_toks = set(t for t in _tokenize(ref) if t not in STOPWORDS)
    gen_toks = set(t for t in _tokenize(gen) if t not in STOPWORDS)
    if not ref_toks:
        return 0.0
    # Recall of expected content words in the generated answer
    return len(ref_toks & gen_toks) / len(ref_toks)

def lcs_length(a: list[str], b: list[str]) -> int:
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]

def rouge_l_lcs(ref: str, gen: str) -> float:
    ref_toks = _tokenize(ref)
    gen_toks = _tokenize(gen)
    if not ref_toks or not gen_toks:
        return 0.0
    lcs = lcs_length(ref_toks, gen_toks)
    # Using recall as proxy (how much of the reference is produced in sequence)
    return lcs / len(ref_toks)

def is_generic_output(gen: str) -> bool:
    if not isinstance(gen, str):
        return False
    lower_gen = gen.lower()
    triggers = [
        "does not mention",
        "does not contain",
        "does not specifically address",
        "no specific decision",
        "information is missing",
        "not discussed in the provided context",
        "not discussed in the meeting",
        "not explicitly mentioned"
    ]
    return any(t in lower_gen for t in triggers)

def is_repetition(text: str) -> bool:
    if not isinstance(text, str) or not text:
        return False
    words = text.split()
    if len(words) < 20:
        return False
    unique_ratio = len(set(words)) / len(words)
    return unique_ratio < 0.2

def process_row(row: dict[str, Any], condition: str) -> dict[str, Any]:
    ref = row.get("expected_answer", "")
    gen = row.get("generated_text", "")
    output_tokens = row.get("output_tokens", 0)
    max_new_tokens = row.get("max_new_tokens", 384)
    
    overlap = normalized_token_overlap(ref, gen)
    content_overlap = content_word_overlap(ref, gen)
    containment = answer_containment_proxy(ref, gen)
    rouge_l = rouge_l_lcs(ref, gen)
    
    too_short = output_tokens < 15
    generic = is_generic_output(gen)
    repetition = is_repetition(gen)
    empty = not isinstance(gen, str) or not gen.strip()
    hit_cap = output_tokens >= max_new_tokens
    
    return {
        "prompt_id": row.get("prompt_id"),
        "condition": condition,
        "question": row.get("question", "N/A"), # It might not be in the row natively, usually expected_answer is what we look at
        "reference_answer": ref,
        "generated_answer": gen,
        "input_tokens": row.get("input_tokens"),
        "compressed_input_tokens": row.get("compressed_input_tokens", row.get("N_compressed")),
        "compression_ratio": row.get("actual_compression_ratio", row.get("R_actual")),
        "output_tokens": output_tokens,
        "overlap_proxy": round(overlap, 6),
        "content_word_overlap": round(content_overlap, 6),
        "containment_proxy": round(containment, 6),
        "rouge_l_lcs": round(rouge_l, 6),
        "hit_cap": hit_cap,
        "empty_output": empty,
        "repetition_flag": repetition,
        "too_short_output": too_short,
        "generic_output": generic
    }

def main():
    all_row_diagnostics = []
    condition_summaries = []
    
    for condition, path in QMSUM_FILES.items():
        rows = load_jsonl(path)
        cond_diags = []
        
        for r in rows:
            diag = process_row(r, condition)
            cond_diags.append(diag)
            all_row_diagnostics.append(diag)
        
        # Summary for condition
        if cond_diags:
            condition_summaries.append({
                "condition": condition,
                "row_count": len(cond_diags),
                "avg_overlap_proxy": round(_mean([d["overlap_proxy"] for d in cond_diags]), 6),
                "avg_content_word_overlap": round(_mean([d["content_word_overlap"] for d in cond_diags]), 6),
                "avg_containment_proxy": round(_mean([d["containment_proxy"] for d in cond_diags]), 6),
                "avg_rouge_l_lcs": round(_mean([d["rouge_l_lcs"] for d in cond_diags]), 6),
                "count_too_short": sum(1 for d in cond_diags if d["too_short_output"]),
                "count_generic": sum(1 for d in cond_diags if d["generic_output"]),
                "count_repetition": sum(1 for d in cond_diags if d["repetition_flag"]),
                "count_empty": sum(1 for d in cond_diags if d["empty_output"]),
                "count_hit_cap": sum(1 for d in cond_diags if d["hit_cap"])
            })

    # Group by prompt_id for manual sampling
    prompts = {}
    for diag in all_row_diagnostics:
        pid = diag["prompt_id"]
        if pid not in prompts:
            prompts[pid] = []
        prompts[pid].append(diag)

    samples = []
    for pid, diags in prompts.items():
        # Only take it if it has all 4 conditions
        if len(diags) == 4:
            diags_dict = {d["condition"]: d for d in diags}
            baseline = diags_dict["Baseline-AR"]
            dflash = diags_dict["DFlash-R1"]
            llmlingua = diags_dict["LLMLingua-AR-R2"]
            cc_dflash = diags_dict["CC-DFlash-R2"]
            
            # Label heuristic
            label = "normal"
            if dflash["overlap_proxy"] < 0.1:
                label = "very_low_overlap"
            elif dflash["overlap_proxy"] > 0.4:
                label = "high_overlap"
            elif any(d["generic_output"] for d in diags):
                label = "contains_generic"
            elif cc_dflash["containment_proxy"] < llmlingua["containment_proxy"] - 0.1:
                label = "cc_dflash_worse"
            elif abs(dflash["overlap_proxy"] - baseline["overlap_proxy"]) > 0.15:
                label = "dflash_differs_strongly_from_baseline"
                
            samples.append({
                "prompt_id": pid,
                "label": label,
                "reference_answer": baseline["reference_answer"],
                "answers": {
                    "Baseline-AR": baseline["generated_answer"],
                    "DFlash-R1": dflash["generated_answer"],
                    "LLMLingua-AR-R2": llmlingua["generated_answer"],
                    "CC-DFlash-R2": cc_dflash["generated_answer"]
                },
                "containment_proxies": {
                    "Baseline-AR": baseline["containment_proxy"],
                    "DFlash-R1": dflash["containment_proxy"],
                    "LLMLingua-AR-R2": llmlingua["containment_proxy"],
                    "CC-DFlash-R2": cc_dflash["containment_proxy"]
                },
                "overlap_proxies": {
                    "Baseline-AR": baseline["overlap_proxy"],
                    "DFlash-R1": dflash["overlap_proxy"],
                    "LLMLingua-AR-R2": llmlingua["overlap_proxy"],
                    "CC-DFlash-R2": cc_dflash["overlap_proxy"]
                }
            })

    # Pick 15 samples based on interesting labels
    interesting_labels = ["contains_generic", "cc_dflash_worse", "dflash_differs_strongly_from_baseline", "very_low_overlap", "high_overlap"]
    chosen_samples = []
    
    # Try to grab 3 of each interesting label
    for label in interesting_labels:
        subset = [s for s in samples if s["label"] == label]
        chosen_samples.extend(subset[:3])
    
    # Fill remaining to 15 with normal or anything left
    if len(chosen_samples) < 15:
        remaining = [s for s in samples if s not in chosen_samples]
        chosen_samples.extend(remaining[:15 - len(chosen_samples)])

    failure_samples = [d for d in all_row_diagnostics if d["too_short_output"] or d["generic_output"] or d["empty_output"]]

    _write_json(Path("results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task84_qmsum_quality_proxy_summary.json"), condition_summaries)
    _write_csv(Path("results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task84_qmsum_quality_proxy_table.csv"), all_row_diagnostics)
    _write_jsonl(Path("results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task84_qmsum_manual_audit_samples.jsonl"), chosen_samples)
    _write_jsonl(Path("results/phase_1_system_build_and_evaluation/quality_and_latency_audits/task84_qmsum_quality_proxy_failure_samples.jsonl"), failure_samples)
    
    print(f"Generated metrics for {len(all_row_diagnostics)} rows.")
    print(f"Selected {len(chosen_samples)} manual audit samples.")
    print(f"Found {len(failure_samples)} failure instances across all conditions.")

if __name__ == "__main__":
    main()
