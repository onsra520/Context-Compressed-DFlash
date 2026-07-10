#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
import json
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ccdf.demo import DemoRunner, RunRequest
from ccdf.demo.writers import write_json, write_jsonl_append, write_flat_csv_append
from ccdf.demo.condition_registry import CONDITIONS, validate_condition
from ccdf.demo.adapters.interactive import interactive_to_request
from ccdf.demo.adapters.gsm8k import gsm8k_row_to_request
from ccdf.demo.adapters.qmsum import qmsum_row_to_request

def parse_args():
    parser = argparse.ArgumentParser(description="CC-DFlash Demo Runner")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    parser.add_argument("--dry-run", action="store_true", help="Run without loading real models")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # run-prompt
    p_run = subparsers.add_parser("run-prompt")
    p_run.add_argument("--condition", required=True, choices=list(CONDITIONS.keys()))
    p_run.add_argument("--prompt", required=True)
    p_run.add_argument("--prompt-profile", default="raw")
    p_run.add_argument("--max-new-tokens", type=int, default=64)
    p_run.add_argument("--seed", type=int, default=42)
    p_run.add_argument("--output", type=str, required=True)
    p_run.add_argument("--overwrite", action="store_true")
    
    # compare-prompt
    p_comp = subparsers.add_parser("compare-prompt")
    p_comp.add_argument("--prompt", required=True)
    p_comp.add_argument("--conditions", required=True, help="comma-separated conditions")
    p_comp.add_argument("--prompt-profile", default="raw")
    p_comp.add_argument("--max-new-tokens", type=int, default=64)
    p_comp.add_argument("--seed", type=int, default=42)
    p_comp.add_argument("--output-dir", type=str, required=True)
    p_comp.add_argument("--overwrite", action="store_true")
    
    # run-dataset
    p_ds = subparsers.add_parser("run-dataset")
    p_ds.add_argument("--dataset", required=True, choices=["gsm8k", "qmsum"])
    p_ds.add_argument("--input", required=True)
    p_ds.add_argument("--conditions", required=True, help="comma-separated conditions")
    p_ds.add_argument("--limit", type=int, default=1)
    p_ds.add_argument("--seed", type=int, default=42)
    p_ds.add_argument("--output-dir", type=str, required=True)
    p_ds.add_argument("--resume", action="store_true")
    p_ds.add_argument("--overwrite", action="store_true")
    
    return parser.parse_args()

def load_rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def main():
    args = parse_args()
    
    from ccdf.config import load_config
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        config = {}
    
    # Wrap it in a subclass to add dry_run just in case it doesn't allow set
    if isinstance(config, dict):
        class ConfigDict(dict):
            pass
        config = ConfigDict(config)
    
    config.dry_run = args.dry_run
    
    runner = DemoRunner(config)
    
    if args.command == "run-prompt":
        req = interactive_to_request(
            prompt=args.prompt,
            condition=args.condition,
            prompt_profile=args.prompt_profile,
            max_new_tokens=args.max_new_tokens,
            seed=args.seed
        )
        res = runner.run(req)
        write_json(res, Path(args.output), overwrite=args.overwrite)
        
    elif args.command == "compare-prompt":
        conditions = [c.strip() for c in args.conditions.split(",")]
        for c in conditions:
            validate_condition(c)
        results = runner.compare_prompt(
            prompt=args.prompt,
            conditions=conditions,
            prompt_profile=args.prompt_profile,
            max_new_tokens=args.max_new_tokens,
            seed=args.seed
        )
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, res in enumerate(results):
            cond = conditions[i]
            write_json(res, out_dir / f"compare_{cond}.json", overwrite=args.overwrite)
            
    elif args.command == "run-dataset":
        conditions = [c.strip() for c in args.conditions.split(",")]
        for c in conditions:
            validate_condition(c)
            
        rows = load_rows(args.input)
        if args.limit > 0:
            rows = rows[:args.limit]
            
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        for cond in conditions:
            jsonl_path = out_dir / f"{args.dataset}_{cond}.jsonl"
            csv_path = out_dir / f"{args.dataset}_{cond}.csv"
            
            skip_count = 0
            if args.resume and jsonl_path.exists():
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    skip_count = sum(1 for line in f if line.strip())
            elif args.overwrite:
                if jsonl_path.exists():
                    jsonl_path.unlink()
                if csv_path.exists():
                    csv_path.unlink()
            elif jsonl_path.exists():
                raise FileExistsError(f"{jsonl_path} already exists")
                
            for i, row in enumerate(rows):
                if i < skip_count:
                    continue
                    
                if args.dataset == "gsm8k":
                    req = gsm8k_row_to_request(row, cond, seed=args.seed)
                else:
                    req = qmsum_row_to_request(row, cond, seed=args.seed)
                    
                res = runner.run(req)
                write_jsonl_append(res, jsonl_path)
                write_flat_csv_append(res, csv_path)

if __name__ == "__main__":
    main()
