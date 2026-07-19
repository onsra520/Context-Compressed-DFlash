#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 WORKLOAD SAMPLES MAX_NEW_TOKENS OUTPUT_DIR" >&2
  exit 2
fi

workload=$1
samples=$2
max_new_tokens=$3
out=$4
mkdir -p "$out/compression" "$out/raw" "$out/boundaries" "$out/metrics"
log="$out/command.log"
: > "$log"

run() {
  printf '$' >> "$log"
  printf ' %q' "$@" >> "$log"
  printf '\n' >> "$log"
  "$@" 2>&1 | tee -a "$log"
}

run python scripts/run_four_condition.py --config config.yml build-manifest \
  --samples "$samples" --run-id "quality-repair-${workload}-n10" \
  --workload-name "$workload" --warmups 1 --repetitions 1 \
  --max-new-tokens "$max_new_tokens" --output "$out/run-manifest.json"
run python scripts/run_four_condition.py --config config.yml compress \
  --samples "$samples" --output "$out/compression/cache.jsonl" \
  --audit "$out/compression/audit.json"

states=()
for condition in C1 C2 C3 C4; do
  run python scripts/run_four_condition.py --config config.yml run \
    --condition "$condition" --samples "$samples" \
    --compression "$out/compression/cache.jsonl" \
    --manifest "$out/run-manifest.json" --output "$out/raw/$condition.jsonl"
  run python scripts/run_four_condition.py --config config.yml capture-gpu-state \
    --label "after-$condition" --output "$out/boundaries/$condition.json"
  states+=(--state "$out/boundaries/$condition.json")
done

run python scripts/run_four_condition.py --config config.yml build-isolation \
  "${states[@]}" --output "$out/isolation.json"
run python scripts/run_four_condition.py --config config.yml audit \
  --c1 "$out/raw/C1.jsonl" --c2 "$out/raw/C2.jsonl" \
  --c3 "$out/raw/C3.jsonl" --c4 "$out/raw/C4.jsonl" \
  --compression "$out/compression/cache.jsonl" \
  --compressor-audit "$out/compression/audit.json" \
  --isolation "$out/isolation.json" --manifest "$out/run-manifest.json" \
  --output "$out/metrics/audit.json" --report "$out/report.md"
