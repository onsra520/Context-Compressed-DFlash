"""
fetch_wikipedia_source.py
=========================
Tạo data/raw/wikipedia_source.jsonl cho CC-DFlash từ SQuAD Wikipedia passages.

Nguồn: SQuAD v2.0 train split (rajpurkar/SQuAD-explorer trên GitHub)
  - 442 bài Wikipedia đa dạng chủ đề
  - Merge các đoạn văn liền kề để tạo passages 500–1500 token (~350–1100 words)
  - License: CC BY-SA 4.0 (Wikipedia content)

Output schema (mỗi dòng JSONL):
  {"id": "...", "title": "...", "text": "...", "word_count": N, "source": "squad_v2_wikipedia"}

Usage:
  python scripts/fetch_wikipedia_source.py --output data/raw/wikipedia_source.jsonl
  python scripts/fetch_wikipedia_source.py --output data/raw/wikipedia_source.jsonl --max-passages 500
"""

import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

SQUAD_TRAIN_URL = (
    "https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer" "/master/dataset/train-v2.0.json"
)
SQUAD_DEV_URL = (
    "https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer" "/master/dataset/dev-v2.0.json"
)

# Token targets: 1 word ≈ 1.35 tokens (empirical for Wikipedia text)
# 500 tokens ≈ 370 words, 1500 tokens ≈ 1110 words
MIN_WORDS = 370
MAX_WORDS = 1110


def fetch_squad(url: str) -> dict:
    print(f"  Fetching: {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "CC-DFlash-research/1.0 (academic)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def build_passages(squad_data: dict, min_words: int, max_words: int) -> list[dict]:
    """Merge consecutive SQuAD paragraphs into passages within target word range."""
    passages = []
    for article in squad_data["data"]:
        title = article["title"].replace("_", " ")
        para_texts = [p["context"].strip() for p in article["paragraphs"]]

        current_chunk: list[str] = []
        current_words = 0

        for para in para_texts:
            words = len(para.split())
            if current_words + words > max_words and current_chunk:
                merged = " ".join(current_chunk)
                mw = len(merged.split())
                if mw >= min_words:
                    pid = hashlib.md5(merged[:200].encode()).hexdigest()[:12]
                    passages.append(
                        {
                            "id": pid,
                            "title": title,
                            "text": merged,
                            "word_count": mw,
                            "source": "squad_v2_wikipedia",
                        }
                    )
                current_chunk = [para]
                current_words = words
            else:
                current_chunk.append(para)
                current_words += words

        # Flush remaining
        if current_chunk:
            merged = " ".join(current_chunk)
            mw = len(merged.split())
            if mw >= min_words:
                pid = hashlib.md5(merged[:200].encode()).hexdigest()[:12]
                passages.append(
                    {
                        "id": pid,
                        "title": title,
                        "text": merged,
                        "word_count": mw,
                        "source": "squad_v2_wikipedia",
                    }
                )

    return passages


def main():
    parser = argparse.ArgumentParser(description="Build wikipedia_source.jsonl for CC-DFlash")
    parser.add_argument(
        "--output",
        default="data/raw/wikipedia_source.jsonl",
        help="Output path (default: data/raw/wikipedia_source.jsonl)",
    )
    parser.add_argument(
        "--max-passages",
        type=int,
        default=0,
        help="Cap total passages (0 = no cap, default). Use 500 for a smaller file.",
    )
    parser.add_argument(
        "--include-dev",
        action="store_true",
        help="Also include SQuAD dev split (adds ~35 more articles)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=MIN_WORDS,
        help=f"Min words per passage (default: {MIN_WORDS} ≈ 500 tokens)",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=MAX_WORDS,
        help=f"Max words per passage (default: {MAX_WORDS} ≈ 1500 tokens)",
    )
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("CC-DFlash: Building wikipedia_source.jsonl from SQuAD Wikipedia passages")
    print(f"  Target word range: {args.min_words}–{args.max_words} words per passage")
    print(f"  Output: {output_path}")
    print()

    # Download SQuAD train
    print("[1/3] Downloading SQuAD v2.0 train split...")
    squad_train = fetch_squad(SQUAD_TRAIN_URL)
    passages = build_passages(squad_train, args.min_words, args.max_words)
    print(f"      → {len(passages)} passages from train ({len(squad_train['data'])} articles)")

    # Optionally download SQuAD dev
    if args.include_dev:
        print("[2/3] Downloading SQuAD v2.0 dev split...")
        squad_dev = fetch_squad(SQUAD_DEV_URL)
        dev_passages = build_passages(squad_dev, args.min_words, args.max_words)
        passages.extend(dev_passages)
        print(f"      → +{len(dev_passages)} passages from dev ({len(squad_dev['data'])} articles)")
    else:
        print("[2/3] Skipping dev split (use --include-dev to add)")

    # Deduplicate by id
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for p in passages:
        if p["id"] not in seen_ids:
            seen_ids.add(p["id"])
            unique.append(p)
    passages = unique
    print(f"      → {len(passages)} unique passages after dedup")

    # Cap if requested
    if args.max_passages and args.max_passages > 0:
        passages = passages[: args.max_passages]
        print(f"      → capped to {len(passages)} passages (--max-passages)")

    # Stats
    word_counts = [p["word_count"] for p in passages]
    word_counts.sort()
    n = len(word_counts)
    print()
    print("[3/3] Writing JSONL...")
    print(f"  Total passages : {n}")
    print(f"  Word count min : {word_counts[0]}")
    print(f"  Word count p25 : {word_counts[n // 4]}")
    print(f"  Word count med : {word_counts[n // 2]}")
    print(f"  Word count p75 : {word_counts[3 * n // 4]}")
    print(f"  Word count max : {word_counts[-1]}")

    with open(output_path, "w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    size_kb = output_path.stat().st_size / 1024
    print(f"  File size      : {size_kb:.1f} KB")
    print()
    print(f"✓ Done: {output_path}")
    print()
    print("Next step:")
    print("  Also run fetch_gsm8k_source.py (or wget) to get data/raw/gsm8k_source.jsonl")
    print("  Then run:")
    print("    PYTHONPATH=src .venv/bin/python scripts/create_dataset.py \\")
    print("      --output data/processed/gsm8k_wikipedia_augmented_full.jsonl \\")
    print("      --max-samples 100 --seed 41 --split test \\")
    print("      --source-mode hf \\")
    print("      --gsm8k-jsonl data/raw/gsm8k_source.jsonl \\")
    print("      --wikipedia-jsonl data/raw/wikipedia_source.jsonl")

    return 0


if __name__ == "__main__":
    sys.exit(main())
