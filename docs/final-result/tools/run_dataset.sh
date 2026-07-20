#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 DATASET MAX_NEW_TOKENS" >&2
  exit 2
fi

dataset=$1
max_new_tokens=$2
case "$dataset" in
  gsm8k|qmsum) ;;
  *) echo "unsupported dataset: $dataset" >&2; exit 2 ;;
esac

python=/home/quyseggs/miniforge3/envs/CCDF/bin/python
root=docs/final-benchmark-n20
out="$root/$dataset"
samples="data/eval/$dataset/${dataset}_n20.jsonl"
mkdir -p "$out/checkpoints" "$out/boundaries" "$out/generic-audit"
log="$out/execution.log"

run() {
  printf '$' >> "$log"
  printf ' %q' "$@" >> "$log"
  printf '\n' >> "$log"
  "$@" 2>&1 | tee -a "$log"
}

if [[ ! -f "$out/run-manifest.json" ]]; then
  run "$python" scripts/run_four_condition.py --config config.yml build-manifest \
    --samples "$samples" --run-id "final-benchmark-${dataset}-n20" \
    --workload-name "${dataset}_n20" --warmups 1 --repetitions 1 \
    --max-new-tokens "$max_new_tokens" --output "$out/run-manifest.json"
fi

run "$python" scripts/run_four_condition.py --config config.yml compress \
  --samples "$samples" --output "$out/compression-cache.jsonl" \
  --audit "$out/compressor-audit.json" --resume
jq -e '.status == "success" and .sample_count == 20 and .usable_samples == 20' \
  "$out/compressor-audit.json" >/dev/null

states=()
for condition in C1 C2 C3 C4; do
  run "$python" scripts/run_four_condition.py --config config.yml capture-gpu-state \
    --label "before-${dataset}-${condition}" --output "$out/boundaries/before-${condition}.json"
  states+=(--state "$out/boundaries/before-${condition}.json")
  run "$python" scripts/run_four_condition.py --config config.yml run \
    --condition "$condition" --samples "$samples" \
    --compression "$out/compression-cache.jsonl" \
    --manifest "$out/run-manifest.json" \
    --output "$out/checkpoints/${condition}.jsonl" --resume
  run "$python" scripts/run_four_condition.py --config config.yml capture-gpu-state \
    --label "after-${dataset}-${condition}" --output "$out/boundaries/after-${condition}.json"
  states+=(--state "$out/boundaries/after-${condition}.json")
done

run "$python" scripts/run_four_condition.py --config config.yml build-isolation \
  "${states[@]}" --output "$out/isolation.json"
set +e
run "$python" scripts/run_four_condition.py --config config.yml audit \
  --c1 "$out/checkpoints/C1.jsonl" --c2 "$out/checkpoints/C2.jsonl" \
  --c3 "$out/checkpoints/C3.jsonl" --c4 "$out/checkpoints/C4.jsonl" \
  --compression "$out/compression-cache.jsonl" \
  --compressor-audit "$out/compressor-audit.json" \
  --isolation "$out/isolation.json" --manifest "$out/run-manifest.json" \
  --output "$out/generic-audit/audit.json" --report "$out/generic-audit/report.md"
audit_status=$?
set -e
printf '%s\n' "$audit_status" > "$out/generic-audit/exit-code.txt"

