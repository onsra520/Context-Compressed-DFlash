from __future__ import annotations

import argparse
import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path

import torch

from ccdf.config import load_config
from ccdf.dflash.generate import dflash_generate
from ccdf.dflash.loader import load_draft, load_tokenizer


REQUIRED_DEFAULT_TARGET = "models/Qwen3-4B"
REQUIRED_DEFAULT_DRAFT = "models/Qwen3-4B-DFlash-b16"
REQUIRED_DEFAULT_TOKENIZER = "models/Qwen3-4B"


@dataclass(frozen=True)
class ProbeConfig:
    target_path: Path
    draft_path: Path
    tokenizer_path: Path
    device: str
    block_size: int
    max_new_tokens: int
    temperature: float


def _resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def _read_probe_config(path: str | Path) -> ProbeConfig:
    config = load_config(path)
    model_cfg = config.get("model", {})
    runtime_cfg = config.get("runtime", {})
    benchmark_cfg = config.get("benchmark", {})

    return ProbeConfig(
        target_path=_resolve_path(model_cfg.get("target_id", REQUIRED_DEFAULT_TARGET)),
        draft_path=_resolve_path(model_cfg.get("draft_id", REQUIRED_DEFAULT_DRAFT)),
        tokenizer_path=_resolve_path(model_cfg.get("tokenizer_id", REQUIRED_DEFAULT_TOKENIZER)),
        device=str(runtime_cfg.get("device", "cuda:0")),
        block_size=int(benchmark_cfg.get("block_size", 16)),
        max_new_tokens=min(int(benchmark_cfg.get("max_new_tokens", 16)), 16),
        temperature=float(benchmark_cfg.get("temperature", 0.0)),
    )


def _print_config(config: ProbeConfig) -> None:
    print(f"Target model path: {config.target_path}")
    print(f"Draft model path: {config.draft_path}")
    print(f"Tokenizer path: {config.tokenizer_path}")
    print(f"Runtime device: {config.device}")
    print(f"Block size: {config.block_size}")
    print(f"Max new tokens: {config.max_new_tokens}")
    print(f"Temperature: {config.temperature}")


def _check_file(path: Path, label: str, errors: list[str]) -> None:
    if path.exists():
        print(f"[OK] {label}: {path}")
    else:
        print(f"[MISSING] {label}: {path}")
        errors.append(f"{label}: {path}")


def _check_any(paths: list[Path], label: str, errors: list[str]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        print(f"[OK] {label}: {', '.join(str(path) for path in existing)}")
    else:
        print(f"[MISSING] {label}: {', '.join(str(path) for path in paths)}")
        errors.append(f"{label}: {paths}")


def _check_local_files(config: ProbeConfig) -> list[str]:
    errors: list[str] = []
    for path, label in [
        (config.target_path, "target directory"),
        (config.draft_path, "draft directory"),
        (config.tokenizer_path, "tokenizer directory"),
    ]:
        if path.exists() and path.is_dir():
            print(f"[OK] {label}: {path}")
        else:
            print(f"[MISSING] {label}: {path}")
            errors.append(f"{label}: {path}")

    _check_file(config.target_path / "config.json", "target config.json", errors)
    _check_file(config.tokenizer_path / "tokenizer_config.json", "target tokenizer_config.json", errors)
    _check_file(config.tokenizer_path / "tokenizer.json", "target tokenizer.json", errors)
    _check_any(
        [
            config.target_path / "model.safetensors.index.json",
            config.target_path / "model.safetensors",
            *sorted(config.target_path.glob("*.safetensors")),
        ],
        "target safetensors/index files",
        errors,
    )
    _check_file(config.draft_path / "config.json", "draft config.json", errors)
    _check_any(
        [config.draft_path / "modeling_dflash.py", config.draft_path / "dflash.py"],
        "draft modeling_dflash.py or dflash.py",
        errors,
    )
    _check_file(config.draft_path / "model.safetensors", "draft model.safetensors", errors)
    return errors


def _raw_import_guard() -> list[tuple[str, str]]:
    bad: list[tuple[str, str]] = []
    for path in Path("src/ccdf/dflash").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ["model_raw", "benchmark_raw"]:
            if needle in text:
                bad.append((str(path), needle))
    print(f"Raw import guard: {bad}")
    return bad


def _cuda_available() -> bool:
    available = torch.cuda.is_available()
    print(f"CUDA available: {available}")
    if available:
        print(f"CUDA device count: {torch.cuda.device_count()}")
        print(f"CUDA current device: {torch.cuda.current_device()}")
        print(f"CUDA device name: {torch.cuda.get_device_name(torch.cuda.current_device())}")
    return available


def _vram(label: str) -> dict[str, float] | None:
    if not torch.cuda.is_available():
        print(f"VRAM {label}: unavailable")
        return None
    torch.cuda.synchronize()
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    free, total = torch.cuda.mem_get_info()
    info = {
        "allocated_gib": allocated,
        "reserved_gib": reserved,
        "free_gib": free / 1024**3,
        "total_gib": total / 1024**3,
    }
    print(
        f"VRAM {label}: allocated={info['allocated_gib']:.2f}GiB "
        f"reserved={info['reserved_gib']:.2f}GiB free={info['free_gib']:.2f}GiB "
        f"total={info['total_gib']:.2f}GiB"
    )
    return info


def _dry_run(config: ProbeConfig) -> int:
    _print_config(config)
    file_errors = _check_local_files(config)
    raw_errors = _raw_import_guard()
    _cuda_available()
    if file_errors or raw_errors:
        print("Final status: DRY-RUN-FAIL")
        return 1
    print("Final status: DRY-RUN-PASS")
    return 0


def _load_target_4bit(target_path: Path, device: str):
    if importlib.util.find_spec("bitsandbytes") is None:
        raise RuntimeError("bitsandbytes is required for 4-bit NF4 target loading")

    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    return AutoModelForCausalLM.from_pretrained(
        str(target_path),
        quantization_config=quantization_config,
        device_map={"": device},
        dtype=torch.bfloat16,
    ).eval()


def _build_prompt(tokenizer) -> torch.Tensor:
    messages = [{"role": "user", "content": "Answer with one word: ready."}]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    return tokenizer.encode(prompt, return_tensors="pt")


def _validate_hidden_state(hidden: torch.Tensor, device: str) -> str | None:
    print(f"H_target shape: {tuple(hidden.shape)}")
    print(f"H_target dtype: {hidden.dtype}")
    print(f"H_target device: {hidden.device}")
    norm = hidden.norm().item()
    print(f"H_target norm: {norm:.6f}")

    if hidden.ndim != 3:
        return f"expected 3 dims, got {hidden.ndim}"
    if hidden.shape[0] != 1 or hidden.shape[1] < 1 or hidden.shape[2] < 1:
        return f"invalid shape {tuple(hidden.shape)}"
    if hidden.dtype not in {torch.float16, torch.bfloat16}:
        return f"expected float16/bfloat16, got {hidden.dtype}"
    if device.startswith("cuda") and hidden.device.type != "cuda":
        return f"expected CUDA hidden state, got {hidden.device}"
    if torch.isnan(hidden).any().item():
        return "hidden state contains NaN"
    if not math.isfinite(norm) or norm <= 0:
        return f"invalid norm {norm}"
    return None


def _real_probe(config: ProbeConfig) -> int:
    _print_config(config)
    file_errors = _check_local_files(config)
    raw_errors = _raw_import_guard()
    if file_errors or raw_errors:
        print("Final status: FAIL-MODEL-UNAVAILABLE")
        return 1
    if not _cuda_available():
        print("Final status: FAIL-CUDA-UNAVAILABLE")
        return 1

    device = config.device
    try:
        _vram("before load")
        tokenizer = load_tokenizer(str(config.tokenizer_path), trust_remote_code=True)
        target = _load_target_4bit(config.target_path, device)
        _vram("after target load")
        draft = load_draft(
            str(config.draft_path),
            device=device,
            trust_remote_code=True,
            dtype=torch.bfloat16,
        )
        _vram("after draft load")
    except Exception as exc:
        print(f"Model load error: {type(exc).__name__}: {exc}")
        print("Final status: FAIL-MODEL-UNAVAILABLE")
        return 1

    input_ids = _build_prompt(tokenizer).to(device)
    try:
        with torch.inference_mode():
            output = target(
                input_ids,
                use_cache=True,
                logits_to_keep=1,
                output_hidden_states=True,
            )
        hidden_error = _validate_hidden_state(output.hidden_states[-1], device)
    except Exception as exc:
        print(f"H_target error: {type(exc).__name__}: {exc}")
        print("Final status: FAIL-H-TARGET")
        return 1

    if hidden_error is not None:
        print(f"H_target validation error: {hidden_error}")
        print("Final status: FAIL-H-TARGET")
        return 1

    try:
        stop_token_ids = [tokenizer.eos_token_id] if tokenizer.eos_token_id is not None else None
        result = dflash_generate(
            draft,
            target=target,
            input_ids=input_ids,
            max_new_tokens=config.max_new_tokens,
            stop_token_ids=stop_token_ids,
            temperature=config.temperature,
            block_size=config.block_size,
            return_stats=True,
        )
        generated = int(result.output_ids.shape[1] - result.num_input_tokens)
        print(f"Generation output shape: {tuple(result.output_ids.shape)}")
        print(f"Generation new tokens: {generated}")
        print(f"Generation acceptance lengths: {list(result.acceptance_lengths)}")
        if generated <= 0:
            raise RuntimeError("generation produced no new tokens")
    except Exception as exc:
        print(f"Generation error: {type(exc).__name__}: {exc}")
        print("Final status: FAIL-GENERATION")
        return 1

    _vram("after generation")
    print("Final status: PASS")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="CCDF DFlash Gate 0 synthetic probe")
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = _read_probe_config(args.config)
    if args.dry_run:
        raise SystemExit(_dry_run(config))
    raise SystemExit(_real_probe(config))


if __name__ == "__main__":
    main()
