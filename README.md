# Context-Compressed Decoding Flash

```
cd ~/CCDF
source .venv/bin/activate

mkdir -p data/demo results/demo

shuf -n 1 data/eval/qmsum_meeting_qa_100.jsonl > data/demo/random_qmsum_one.jsonl

for CONDITION in baseline_ar dflash_r1 llmlingua_ar_r2 cc_dflash_r2; do
  PYTHONPATH=src .venv/bin/python scripts/run_mvp.py \
    --prompt-source fixture \
    --fixture data/demo/random_qmsum_one.jsonl \
    --condition "$CONDITION" \
    --max-prompts 1 \
    --max-new-tokens 384 \
    --store-generated-text \
    --overwrite \
    --output "results/demo/random_qmsum_one_${CONDITION}.jsonl"
done
```