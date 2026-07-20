# CCDF live streaming demo

This is an arbitrary-prompt demonstration of Baseline-AR, D-Flash, and
CC-DFlash. It is not a benchmark dataset run and does not report accuracy, EM,
ROUGE, or a quality verdict. The final n=20 benchmark and its artifacts are a
separate frozen evidence set.

## Run

```bash
conda activate CCDF
python -m ccdf.api
```

In another shell:

```bash
cd src/ccdf/frontend
pnpm dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. The backend queues runs in
memory and executes one GPU condition at a time in this order:

`Analyze Input → Baseline-AR → D-Flash → Compress → CC-DFlash → Compare`

## API and SSE

- `GET /api/demo/capabilities`
- `GET /api/demo/prompt-samples`
- `POST /api/demo/runs`
- `GET /api/demo/runs/{run_id}/events`
- `GET /api/demo/runs/{run_id}`
- `POST /api/demo/runs/{run_id}/cancel`

Create-run JSON contains `prompt`, `compression_device` (`cuda` or `cpu`), and
`max_new_tokens`. The event endpoint is `text/event-stream`; each event has a
strictly increasing sequence. Token deltas come directly from the generation
loops. Baseline emits target-committed tokens; D-Flash and CC-DFlash emit only
accepted draft tokens and target correction/bonus tokens after verification.
Unverified proposals are never sent.

CUDA compression is the default. The compressor model placement is validated
against the requested device. A CUDA error fails the run and is never silently
retried on CPU. A genuine bypass reports zero removed tokens and zero reduction.

## Metrics

- `decode tok/s = output tokens / generation latency`
- Baseline-AR and D-Flash pipeline E2E = generation latency
- CC-DFlash pipeline E2E = compression latency + generation latency
- acceptance rate = accepted draft tokens / proposed draft tokens
- keep rate = compressed input tokens / original input tokens
- reduction rate = removed input tokens / original input tokens

TTFT is measured from the real generation call to its first committed-token
callback. All displayed values belong only to the current live run. CC-DFlash
shows compression and generation as separate E2E components.
