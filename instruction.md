# CC-DFlash — Project Instruction & Roadmap
> **Context-Compressed DFlash** · v4.0 · 2026  
> Tài liệu hướng dẫn toàn bộ dự án — đọc trước khi làm bất kỳ thứ gì

---

## Mục tiêu dự án

Tích hợp **Input Context Compression** vào pipeline DFlash để giảm chi phí prefill
với long-context workload, **không thay đổi thuật toán speculative decoding bên trong**.

**Claim chính xác:**
```
lossy input compression  +  lossless speculative decoding trên C_nén
≠ lossless toàn pipeline
```

**Cách tiếp cận:**  
Lấy code gốc từ `z-lab/dflash` (`model/dflash.py`, `model/utils.py`, `benchmark.py`)
và **split thành các module nhỏ** phù hợp với hệ thống CCDF, sau đó phát triển thêm
Compression Layer phía trên mà không sửa logic DFlash lõi.

---

## Cấu trúc thư mục dự án

```
CCDF/
│
├── instruction.md              # File này — đọc trước tất cả
├── config.yml                  # Runtime config chính
├── requirements.txt            # Locked versions
├── setup.sh                    # Cài đặt môi trường
├── pyproject.toml              # Python package config
├── README.md
│
├── docs/
│   ├── researching/
│   │   ├── CC-DFlash-v3.html
│   │   └── CC-DFlash-v4.html   # Architecture reference
│   ├── plans/
│   │   └── task.md
│   └── paper/
│       └── CC-DFlash.docx
│
├── models/
│   └── .gitkeep                # Local model cache, không commit model
│
├── src/
│   └── ccdf/                   # Package chính
│       ├── __init__.py         # Public API
│       │
│       ├── dflash/             # ← SPLIT TỪ CODE GỐC z-lab/dflash
│       │   ├── __init__.py
│       │   ├── model.py        # DFlashDraftModel — từ model/dflash.py gốc
│       │   ├── attention.py    # Qwen3DFlashAttention — tách ra từ model/dflash.py
│       │   ├── generate.py     # spec_generate() loop — tách ra từ model/dflash.py
│       │   ├── loader.py       # load target, draft, tokenizer — từ benchmark.py gốc
│       │   └── utils.py        # extract_context_feature, sample — từ model/utils.py gốc
│       │
│       ├── compression/        # ← MODULE MỚI — không có trong code gốc
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract CompressorBase
│       │   ├── passthrough.py  # Baseline R=1, không nén
│       │   ├── llmlingua.py    # LLMLingua-2 wrapper (MVP)
│       │   ├── gemma.py        # Gemma4-E2B wrapper (Phase 2, skeleton)
│       │   └── segmentation.py # Tách question (protected) / context (compressible)
│       │
│       ├── pipeline/           # ← MODULE MỚI — nối compression + dflash
│       │   ├── __init__.py
│       │   ├── ccdf_pipeline.py # CCDFlashPipeline: compress → prefill → draft → verify
│       │   └── prompt_builder.py # Build chat template với enable_thinking=False
│       │
│       ├── benchmark/          # ← SPLIT + MỞ RỘNG TỪ benchmark.py gốc
│       │   ├── __init__.py
│       │   ├── runner.py       # BenchmarkRunner — logic chạy nhiều condition
│       │   ├── metrics.py      # SingleResult, MetricsCollector, compute_exact_match
│       │   ├── datasets.py     # load_and_process_dataset — từ model/utils.py gốc
│       │   └── conditions.py   # Định nghĩa 8 điều kiện thực nghiệm
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   └── loader.py       # Đọc config.yml
│       │
│       └── utils/
│           ├── __init__.py
│           ├── timing.py       # CUDA timing helpers
│           ├── vram.py         # VRAM monitoring
│           └── logging.py
│
├── scripts/
│   ├── synthetic_probe.py      # CHẠY ĐẦU TIÊN — Gate 0
│   ├── create_dataset.py       # Tạo GSM8K-augmented dataset
│   ├── run_mvp.py              # Entry point experiment
│   └── plot_results.py         # Sinh biểu đồ
│
├── tests/
│   ├── test_dflash_core.py     # Test spec_generate, extract_context_feature
│   ├── test_compression.py     # Test từng compressor
│   ├── test_pipeline.py        # Test end-to-end pipeline
│   └── test_metrics.py         # Test EM, IOR, τ calculation
│
├── data/
│   ├── raw/.gitkeep
│   └── processed/.gitkeep
│
├── results/
│   ├── .gitkeep
│   └── charts/.gitkeep
│
└── notebooks/
    └── explore.ipynb
```

---

## Mapping code gốc → module CCDF

Đây là phần quan trọng nhất. Mỗi dòng cho biết code từ đâu và đi về đâu.

```
CODE GỐC z-lab/dflash                  →  MODULE CCDF
─────────────────────────────────────────────────────────────────
model/dflash.py
  ├── DFlashDraftModel (class)          →  dflash/model.py
  ├── Qwen3DFlashDecoderLayer           →  dflash/model.py
  ├── Qwen3DFlashAttention              →  dflash/attention.py  (tách riêng)
  └── spec_generate() method            →  dflash/generate.py   (tách riêng)

model/utils.py
  ├── extract_context_feature()         →  dflash/utils.py
  ├── sample()                          →  dflash/utils.py
  ├── build_target_layer_ids()          →  dflash/utils.py
  └── load_and_process_dataset()        →  benchmark/datasets.py

benchmark.py
  ├── load target / load draft          →  dflash/loader.py
  ├── dflash_generate() loop            →  (tham khảo → dflash/generate.py)
  ├── acceptance_length tính toán       →  benchmark/metrics.py
  └── histogram / logging               →  benchmark/runner.py

model/__init__.py                       →  dflash/__init__.py  (giữ exports)
```

**Nguyên tắc khi split:**
- Không thay đổi logic bên trong — chỉ di chuyển và tổ chức lại
- Giữ nguyên tên function/class để dễ đối chiếu với paper
- Thêm docstring giải thích nguồn gốc: `# from z-lab/dflash model/dflash.py`
- Compression Layer là module **hoàn toàn mới**, không có trong code gốc

---

## Module Code — Chi tiết từng file

### `src/ccdf/dflash/utils.py`
*Nguồn: `model/utils.py` gốc — split ra, không sửa logic*

```python
# src/ccdf/dflash/utils.py
# Nguồn: z-lab/dflash model/utils.py
# Các utility function cốt lõi của DFlash

import torch
from typing import List


def extract_context_feature(hidden_states, target_layer_ids: List[int]) -> torch.Tensor:
    """
    Trích xuất hidden states từ các lớp cụ thể của Target Model.
    Đây là cơ chế KV Injection cốt lõi của DFlash.

    Nguồn: z-lab/dflash model/utils.py
    """
    return torch.cat(
        [hidden_states[layer_id] for layer_id in target_layer_ids],
        dim=-1,
    )


def sample(logits: torch.Tensor, temperature: float = 0.0) -> torch.Tensor:
    """
    Sample token từ logits.
    temperature=0.0 → greedy (argmax) — dùng cho benchmark
    temperature>0.0 → multinomial sampling

    Nguồn: z-lab/dflash model/utils.py
    """
    if temperature == 0.0:
        return logits.argmax(dim=-1)
    probs = torch.softmax(logits / temperature, dim=-1)
    return torch.multinomial(probs, num_samples=1).squeeze(-1)


def build_target_layer_ids(num_layers: int, num_draft_layers: int) -> List[int]:
    """
    Xác định các lớp của Target Model cần trích xuất hidden states.

    Nguồn: z-lab/dflash model/utils.py
    """
    step = num_layers // num_draft_layers
    return [i * step for i in range(num_draft_layers)]
```

---

### `src/ccdf/dflash/generate.py`
*Nguồn: `spec_generate()` từ `model/dflash.py` — tách thành file riêng*

```python
# src/ccdf/dflash/generate.py
# Nguồn: z-lab/dflash model/dflash.py — phần spec_generate() loop
#
# QUAN TRỌNG: File này chứa logic speculative decoding loop.
# acceptance_length được tính và trả về để đo τ (primary metric DFlash).
# KHÔNG sửa logic này — chỉ thêm return value nếu cần lấy τ.

import torch
from typing import Optional, List
from .utils import extract_context_feature, sample


def spec_generate(
    draft_model,
    target_model,
    input_ids: torch.Tensor,
    max_new_tokens: int = 512,
    block_size: int = 16,
    temperature: float = 0.0,
    mask_token_id: Optional[int] = None,
    stop_token_ids: Optional[List[int]] = None,
) -> dict:
    """
    Speculative generation loop của DFlash.

    Nguồn: z-lab/dflash model/dflash.py spec_generate()
    Thay đổi so với gốc: trả về dict thay vì chỉ output_ids,
    để BenchmarkRunner có thể lấy acceptance_lengths (τ).

    Returns:
        {
            "output_ids"        : torch.Tensor,
            "acceptance_lengths": List[int],   # τ per step — primary metric
            "n_steps"           : int,
        }
    """
    # Implementation: copy từ z-lab/dflash model/dflash.py spec_generate()
    # và thêm tracking acceptance_lengths
    acceptance_lengths = []

    # --- [Copy logic từ spec_generate() gốc] ---
    # Đây là nơi để paste code gốc vào, sau đó:
    # 1. Tìm dòng tính acceptance_length
    # 2. Thêm: acceptance_lengths.append(acceptance_length)
    # 3. Đổi return thành dict như trên
    # -------------------------------------------

    raise NotImplementedError(
        "Cần copy logic từ z-lab/dflash model/dflash.py spec_generate() vào đây. "
        "Xem instruction.md phần Gate 0 để biết chi tiết."
    )
```

---

### `src/ccdf/dflash/loader.py`
*Nguồn: phần load model trong `benchmark.py` gốc*

```python
# src/ccdf/dflash/loader.py
# Nguồn: z-lab/dflash benchmark.py — phần load target, draft, tokenizer

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    AutoModel,
    BitsAndBytesConfig,
)


def load_target(
    model_id: str = "Qwen/Qwen3-4B",
    device: str = "cuda:0",
    load_in_4bit: bool = True,
):
    """
    Load Target Model với 4-bit NF4.

    QUAN TRỌNG: 4-bit NF4 là bắt buộc cho 8GB VRAM.
    Qwen3-4B ở FP16 = 8GB — không fit.
    Qwen3-4B ở 4-bit NF4 = ~2.5GB — fit.

    Nguồn: z-lab/dflash benchmark.py
    """
    bnb_cfg = None
    if load_in_4bit:
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_cfg,
        torch_dtype=torch.bfloat16 if not load_in_4bit else None,
        device_map=device,
    ).eval()

    vram = torch.cuda.memory_allocated(device) / 1e9
    print(f"[loader] Target loaded. VRAM: {vram:.2f} GB")
    return model


def load_draft(
    model_id: str = "z-lab/Qwen3-4B-DFlash-b16",
    device: str = "cuda:0",
):
    """
    Load Draft Model (DFlashDraftModel).

    Draft Qwen3-4B-DFlash-b16 chỉ ~0.5B params → ~1GB BF16.
    Không cần quantize.
    trust_remote_code=True bắt buộc — custom architecture.

    Nguồn: z-lab/dflash benchmark.py
    """
    model = AutoModel.from_pretrained(
        model_id,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map=device,
    ).eval()

    vram = torch.cuda.memory_allocated(device) / 1e9
    print(f"[loader] Draft loaded. VRAM: {vram:.2f} GB")
    return model


def load_tokenizer(model_id: str = "Qwen/Qwen3-4B"):
    """
    Load tokenizer và thêm mask token cho DFlash.

    QUAN TRỌNG: DFlash yêu cầu mask token <|MASK|> cho block diffusion.
    Nếu thiếu dòng add_special_tokens, draft model sẽ lỗi.

    Nguồn: z-lab/dflash benchmark.py
    """
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.add_special_tokens({"mask_token": "<|MASK|>"})
    return tokenizer


def load_all(
    target_id: str = "Qwen/Qwen3-4B",
    draft_id: str = "z-lab/Qwen3-4B-DFlash-b16",
    device: str = "cuda:0",
    load_in_4bit: bool = True,
):
    """
    Load cả target, draft, tokenizer trong một lần gọi.
    Returns: (target, draft, tokenizer)
    """
    target = load_target(target_id, device, load_in_4bit)
    draft  = load_draft(draft_id, device)
    tok    = load_tokenizer(target_id)
    vram   = torch.cuda.memory_allocated(device) / 1e9
    print(f"[loader] All loaded. Total VRAM: {vram:.2f} GB")
    return target, draft, tok
```

---

### `src/ccdf/dflash/__init__.py`
*Export public API của dflash module*

```python
# src/ccdf/dflash/__init__.py
# Nguồn: z-lab/dflash model/__init__.py — giữ nguyên exports, thêm loader

from .loader import load_target, load_draft, load_tokenizer, load_all
from .utils import extract_context_feature, sample, build_target_layer_ids
from .generate import spec_generate

# DFlashDraftModel được import từ model.py khi đã copy code gốc vào
# from .model import DFlashDraftModel

__all__ = [
    "load_target", "load_draft", "load_tokenizer", "load_all",
    "extract_context_feature", "sample", "build_target_layer_ids",
    "spec_generate",
]
```

---

### `src/ccdf/compression/base.py`
*Module mới — không có trong code gốc*

```python
# src/ccdf/compression/base.py
# Module hoàn toàn mới — không có trong z-lab/dflash
# Abstract interface cho mọi compressor

import time
from abc import ABC, abstractmethod
from typing import Tuple


class CompressorBase(ABC):
    """
    Interface chuẩn cho mọi compression strategy.

    Để thêm compressor mới:
    1. Tạo file mới trong compression/
    2. Kế thừa CompressorBase
    3. Implement compress()
    4. Không cần sửa bất kỳ file nào khác trong pipeline

    info_dict chuẩn trả về:
        {
            "t_compress_ms": float,   # thời gian nén (ms)
            "R_actual"     : float,   # compression ratio thực tế
            "N_original"   : int,     # số token trước nén (word-split)
            "N_compressed" : int,     # số token sau nén
        }
    """

    @abstractmethod
    def compress(
        self,
        context: str,
        question: str,
        keep_rate: float,
    ) -> Tuple[str, dict]:
        """
        Nén context dựa trên question.

        Args:
            context   : đoạn văn dài cần nén (Wikipedia passage, v.v.)
            question  : câu hỏi — dùng để bias compression về phía tokens quan trọng
            keep_rate : tỷ lệ GIỮ LẠI — 0.33 = giữ 33%, R_actual ≈ 3

        Returns: (compressed_text, info_dict)
        """
        ...

    def _make_info(self, original: str, compressed: str, t_ms: float) -> dict:
        """Helper tính info_dict chuẩn từ text trước/sau nén."""
        n_orig = len(original.split())
        n_comp = len(compressed.split())
        return {
            "t_compress_ms": round(t_ms, 1),
            "R_actual"     : round(n_orig / max(n_comp, 1), 2),
            "N_original"   : n_orig,
            "N_compressed" : n_comp,
        }
```

---

### `src/ccdf/compression/passthrough.py`
*Baseline không nén — R=1*

```python
# src/ccdf/compression/passthrough.py
# Baseline: không nén gì cả — R = 1.0
# Dùng cho điều kiện DFlash-R1 và Baseline-AR

from .base import CompressorBase
from typing import Tuple


class PassthroughCompressor(CompressorBase):
    """
    Không nén — trả về context nguyên vẹn.
    Dùng làm baseline để so sánh.
    """

    def compress(self, context: str, question: str, keep_rate: float) -> Tuple[str, dict]:
        return context, self._make_info(context, context, 0.0)
```

---

### `src/ccdf/compression/segmentation.py`
*Module mới — logic tách question ra khỏi context trước khi nén*

```python
# src/ccdf/compression/segmentation.py
# Module hoàn toàn mới — không có trong z-lab/dflash
#
# Giải quyết vấn đề: LLMLingua-2 có thể cắt mất số toán học
# trong câu hỏi GSM8K nếu toàn bộ prompt đi qua compressor.
#
# Giải pháp từ CC-DFlash-v4.html Section 4.1:
# - Tách prompt thành [context] + [question]
# - Chỉ nén [context]
# - [question] được bảo vệ, không qua compressor
# - Nối lại sau: compressed_context + "\n\n" + question

from dataclasses import dataclass
from typing import Optional


@dataclass
class SegmentedPrompt:
    """Prompt đã được tách thành 2 phần."""
    context : str   # phần dài — sẽ được nén
    question: str   # phần bảo vệ — KHÔNG nén


def segment_gsm8k(full_prompt: str) -> SegmentedPrompt:
    """
    Tách GSM8K-augmented prompt thành context (Wikipedia) + question.

    Giả định format: [wiki context]\n\n[question]
    Câu hỏi toán học thường ở cuối, sau dấu "\n\n".
    """
    parts = full_prompt.rsplit("\n\n", maxsplit=1)
    if len(parts) == 2:
        return SegmentedPrompt(context=parts[0], question=parts[1])
    # Fallback: không tách được → coi toàn bộ là question (bảo vệ)
    return SegmentedPrompt(context="", question=full_prompt)


def merge(compressed_context: str, question: str) -> str:
    """Nối lại context đã nén với question được bảo vệ."""
    if not compressed_context:
        return question
    return compressed_context.strip() + "\n\n" + question
```

---

### `src/ccdf/compression/llmlingua.py`
*LLMLingua-2 compressor — MVP*

```python
# src/ccdf/compression/llmlingua.py
# Module mới — không có trong z-lab/dflash
# LLMLingua-2: extractive compressor, chạy CPU, không chiếm GPU VRAM

import time
from .base import CompressorBase
from typing import Tuple


class LLMLinguaCompressor(CompressorBase):
    """
    LLMLingua-2 extractive compressor.

    Chạy CPU — không chiếm GPU VRAM.
    question= parameter bias token classification về phía tokens quan trọng
    cho đáp án (giữ số, đơn vị, tên riêng).

    Latency: ~10ms trên CPU (500-token context)
    """

    MODEL_ID = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"

    def __init__(self, device_map: str = "cpu"):
        from llmlingua import PromptCompressor
        self._comp = PromptCompressor(
            model_name=self.MODEL_ID,
            use_llmlingua2=True,
            device_map=device_map,
        )
        print(f"[LLMLingua] Loaded on {device_map}")

    def compress(self, context: str, question: str, keep_rate: float) -> Tuple[str, dict]:
        """
        Nén context với question-aware biasing.

        force_tokens: luôn giữ các token cấu trúc
        question=: bias về phía tokens liên quan đến đáp án
        """
        t0 = time.time()
        result = self._comp.compress_prompt(
            context=context,
            question=question,
            rate=keep_rate,
            force_tokens=["\n", "?", ".", ":"],
        )
        t_ms = (time.time() - t0) * 1000
        compressed = result["compressed_prompt"]
        return compressed, self._make_info(context, compressed, t_ms)
```

---

### `src/ccdf/pipeline/ccdf_pipeline.py`
*Module mới — nối compression + dflash*

```python
# src/ccdf/pipeline/ccdf_pipeline.py
# Module hoàn toàn mới — không có trong z-lab/dflash
# Nối Compression Layer với DFlash pipeline

import torch
import time
from ..compression.base import CompressorBase
from ..compression.segmentation import segment_gsm8k, merge
from ..dflash.generate import spec_generate


class CCDFlashPipeline:
    """
    Pipeline hoàn chỉnh: Compress → Prefill → Draft → Verify.

    Flow:
        1. segment(): tách context / question
        2. compress(): nén context (nếu keep_rate < 1.0)
        3. merge(): nối lại
        4. build_input_ids(): tokenize với enable_thinking=False
        5. spec_generate(): DFlash speculative decoding

    Không chứa logic đo metrics — đó là nhiệm vụ của BenchmarkRunner.
    """

    def __init__(self, target, draft, tokenizer, compressor: CompressorBase):
        self.target     = target
        self.draft      = draft
        self.tokenizer  = tokenizer
        self.compressor = compressor

    def build_input_ids(
        self,
        context: str,
        question: str,
        keep_rate: float = 1.0,
    ):
        """Compress + tokenize. Returns (input_ids, compression_info)."""
        if keep_rate < 1.0 and context.strip():
            compressed, info = self.compressor.compress(
                context=context,
                question=question,
                keep_rate=keep_rate,
            )
            prompt = merge(compressed, question)
        else:
            prompt = merge(context, question) if context else question
            info = {"t_compress_ms": 0.0, "R_actual": 1.0,
                    "N_original": len(prompt.split()),
                    "N_compressed": len(prompt.split())}

        messages = [{"role": "user", "content": prompt}]
        input_ids = self.tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
            add_generation_prompt=True,
            enable_thinking=False,  # ← KHÓA CỨNG — không bao giờ bỏ dòng này
        ).to(next(self.target.parameters()).device)

        return input_ids, info

    def run(
        self,
        context: str,
        question: str,
        keep_rate: float = 1.0,
        max_new_tokens: int = 512,
        block_size: int = 16,
        temperature: float = 0.0,
    ) -> dict:
        """
        Chạy pipeline end-to-end.
        Returns dict với output và timing cơ bản.
        BenchmarkRunner sẽ đo thêm prefill riêng và τ.
        """
        input_ids, comp_info = self.build_input_ids(context, question, keep_rate)

        torch.cuda.synchronize()
        t0 = time.time()
        result = spec_generate(
            draft_model=self.draft,
            target_model=self.target,
            input_ids=input_ids,
            max_new_tokens=max_new_tokens,
            block_size=block_size,
            temperature=temperature,
            mask_token_id=self.tokenizer.mask_token_id,
            stop_token_ids=[self.tokenizer.eos_token_id],
        )
        torch.cuda.synchronize()
        t_gen = time.time() - t0

        output_ids = result["output_ids"]
        n_new = output_ids.shape[1] - input_ids.shape[1]
        out_txt = self.tokenizer.decode(
            output_ids[0][input_ids.shape[1]:], skip_special_tokens=True
        )

        return {
            **comp_info,
            "t_gen_s"           : round(t_gen, 3),
            "tok_per_sec"       : round(n_new / max(t_gen, 1e-6), 1),
            "n_out_tok"         : n_new,
            "acceptance_lengths": result["acceptance_lengths"],  # τ per step
            "output"            : out_txt,
        }
```

---

### `src/ccdf/benchmark/metrics.py`
*Nguồn: tính acceptance_length từ `benchmark.py` gốc + thêm metrics mới*

```python
# src/ccdf/benchmark/metrics.py
# Nguồn: z-lab/dflash benchmark.py — phần tính acceptance_length
# Mở rộng thêm: EM, IOR, Semantic Score

import re
import json
import torch
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from pathlib import Path


@dataclass
class SingleResult:
    """Kết quả một lần chạy."""
    condition       : str   = ""
    keep_rate       : float = 1.0
    R_actual        : float = 1.0
    N_original      : int   = 0
    N_compressed    : int   = 0
    t_compress_ms   : float = 0.0
    t_prefill_ms    : float = 0.0       # đo riêng bằng CUDA sync
    t_gen_s         : float = 0.0
    tok_per_sec     : float = 0.0
    n_out_tok       : int   = 0
    # τ — primary DFlash metric (Nguồn: benchmark.py gốc)
    tau_mean        : float = 0.0       # acceptance length trung bình
    tau_histogram   : list  = field(default_factory=list)  # distribution
    alpha           : float = 0.0       # acceptance rate (%) — secondary
    # Quality metrics
    exact_match     : Optional[bool] = None
    invalid_output  : bool  = False
    output          : str   = ""
    ground_truth    : str   = ""


def compute_tau(acceptance_lengths: List[int], block_size: int = 16) -> dict:
    """
    Tính τ (acceptance length) từ list acceptance_lengths của spec_generate.

    Nguồn: z-lab/dflash benchmark.py
        acceptance_length = (block_output_ids[:, 1:] == posterior[:, :-1])
                            .cumprod(dim=1).sum(dim=1)[0].item()
        histogram = [acceptance_lengths.count(b) / len(acceptance_lengths)
                     for b in range(block_size + 1)]
    """
    if not acceptance_lengths:
        return {"tau_mean": 0.0, "tau_histogram": [], "alpha": 0.0}

    tau_mean  = sum(acceptance_lengths) / len(acceptance_lengths)
    histogram = [
        acceptance_lengths.count(b) / len(acceptance_lengths)
        for b in range(block_size + 1)
    ]
    alpha = tau_mean / block_size * 100  # % tokens accepted

    return {
        "tau_mean"     : round(tau_mean, 3),
        "tau_histogram": [round(x * 100, 1) for x in histogram],
        "alpha"        : round(alpha, 1),
    }


def compute_exact_match(output: str, ground_truth: str) -> bool:
    """Exact Match cho GSM8K — so sánh số cuối cùng trong output."""
    def last_number(text: str) -> Optional[float]:
        nums = re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
        return float(nums[-1]) if nums else None

    pred = last_number(output)
    gt   = last_number(ground_truth)
    if pred is None or gt is None:
        return False
    return abs(pred - gt) < 1e-6


class MetricsCollector:
    """Thu thập và tổng hợp kết quả từ nhiều lần chạy."""

    def __init__(self):
        self.results: List[SingleResult] = []

    def add(self, r: SingleResult):
        self.results.append(r)

    def measure_prefill_ms(self, target_model, input_ids: torch.Tensor) -> float:
        """Đo prefill latency riêng biệt bằng CUDA synchronize."""
        torch.cuda.synchronize()
        import time
        t0 = time.time()
        with torch.no_grad():
            _ = target_model(input_ids, use_cache=True)
        torch.cuda.synchronize()
        return (time.time() - t0) * 1000

    def summary(self) -> dict:
        """Tổng hợp theo condition."""
        by_cond = {}
        for r in self.results:
            by_cond.setdefault(r.condition, []).append(r)

        out = {}
        for cond, items in by_cond.items():
            ems = [r.exact_match for r in items if r.exact_match is not None]
            out[cond] = {
                "n"              : len(items),
                "tok_per_sec"    : round(sum(r.tok_per_sec for r in items)/len(items), 1),
                "t_prefill_ms"   : round(sum(r.t_prefill_ms for r in items)/len(items), 1),
                "t_compress_ms"  : round(sum(r.t_compress_ms for r in items)/len(items), 1),
                "R_actual"       : round(sum(r.R_actual for r in items)/len(items), 2),
                "tau_mean"       : round(sum(r.tau_mean for r in items)/len(items), 3),
                "alpha_pct"      : round(sum(r.alpha for r in items)/len(items), 1),
                "em_pct"         : round(sum(ems)/len(ems)*100, 1) if ems else None,
                "invalid_rate"   : round(sum(r.invalid_output for r in items)/len(items)*100, 1),
            }
        return out

    def save(self, path: str = "results/results_raw.json"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "results": [asdict(r) for r in self.results],
                "summary": self.summary(),
            }, f, ensure_ascii=False, indent=2)
        print(f"[metrics] Saved {len(self.results)} results → {path}")
```

---

### `src/ccdf/benchmark/runner.py`
*BenchmarkRunner — chạy nhiều condition*

```python
# src/ccdf/benchmark/runner.py
# Chạy experiment matrix: nhiều condition × nhiều samples

from .metrics import SingleResult, MetricsCollector, compute_tau, compute_exact_match
from typing import List


class BenchmarkRunner:
    """
    Chạy toàn bộ experiment matrix.
    Kết hợp CCDFlashPipeline + MetricsCollector.

    Mỗi condition = một cặp (compressor, keep_rate).
    8 conditions bắt buộc: xem benchmark/conditions.py
    """

    def __init__(self, pipeline, collector: MetricsCollector):
        self.pipeline  = pipeline
        self.collector = collector

    def warmup(self, n: int = 2):
        """Warm up GPU trước khi đo — tránh timing sai lần đầu."""
        print(f"[runner] Warming up ({n} runs)...")
        for _ in range(n):
            self.pipeline.run("", "What is 2 + 2?",
                              keep_rate=1.0, max_new_tokens=32)

    def run_condition(
        self,
        condition_name: str,
        samples: list,
        keep_rate: float = 1.0,
        max_new_tokens: int = 512,
        block_size: int = 16,
        verbose: bool = True,
    ) -> List[SingleResult]:
        """
        Chạy một điều kiện trên toàn bộ samples.

        samples: list of {"context": str, "question": str, "answer": str}
        """
        results = []
        for i, s in enumerate(samples):
            context  = s.get("context", "")
            question = s.get("question", "")
            answer   = s.get("answer", "")

            # Đo prefill riêng — quan trọng để vẽ breakeven curve
            input_ids, comp_info = self.pipeline.build_input_ids(
                context, question, keep_rate
            )
            t_pf = self.collector.measure_prefill_ms(self.pipeline.target, input_ids)

            # Run pipeline
            gen = self.pipeline.run(context, question, keep_rate, max_new_tokens, block_size)

            # Tính τ từ acceptance_lengths (Nguồn: benchmark.py gốc)
            tau_info = compute_tau(gen.get("acceptance_lengths", []), block_size)

            r = SingleResult(
                condition     = condition_name,
                keep_rate     = keep_rate,
                R_actual      = comp_info["R_actual"],
                N_original    = comp_info["N_original"],
                N_compressed  = comp_info["N_compressed"],
                t_compress_ms = comp_info["t_compress_ms"],
                t_prefill_ms  = round(t_pf, 1),
                t_gen_s       = gen["t_gen_s"],
                tok_per_sec   = gen["tok_per_sec"],
                n_out_tok     = gen["n_out_tok"],
                tau_mean      = tau_info["tau_mean"],
                tau_histogram = tau_info["tau_histogram"],
                alpha         = tau_info["alpha"],
                exact_match   = compute_exact_match(gen["output"], answer) if answer else None,
                invalid_output= len(gen["output"].strip()) < 5,
                output        = gen["output"][:300],
                ground_truth  = answer,
            )
            results.append(r)
            self.collector.add(r)

            if verbose and (i + 1) % 10 == 0:
                print(f"[{condition_name}] {i+1}/{len(samples)} | "
                      f"R={r.R_actual:.1f} | τ={r.tau_mean:.2f} | "
                      f"T_pf={r.t_prefill_ms:.0f}ms | "
                      f"speed={r.tok_per_sec:.1f}tok/s")

        return results
```

---

### `src/ccdf/benchmark/conditions.py`
*8 điều kiện thực nghiệm bắt buộc*

```python
# src/ccdf/benchmark/conditions.py
# 8 điều kiện thực nghiệm — xem CC-DFlash-v4.html Section 6.4

CONDITIONS = [
    # (name, compressor_type, keep_rate, note)
    ("Baseline-AR",     "none",      1.0,  "Autoregressive thuần — floor"),
    ("DFlash-R1",       "none",      1.0,  "DFlash gốc — baseline chính"),
    ("LLMLingua-AR",    "llmlingua", 0.5,  "Compression + AR, không DFlash — tách nguồn gốc speedup"),
    ("LLMLingua-AR-R3", "llmlingua", 0.33, "Compression + AR, R≈3"),
    ("CC-LLM-R2",       "llmlingua", 0.5,  "CC-DFlash nhẹ"),
    ("CC-LLM-R3",       "llmlingua", 0.33, "Điểm kỳ vọng tối ưu R*"),
    ("CC-LLM-R4",       "llmlingua", 0.25, "Nén mạnh — kiểm tra giới hạn"),
    # Phase 2 — thêm sau khi Gemma4-E2B fine-tune xong
    # ("CC-Gemma-R3",   "gemma",     0.33, "Phase 2 contribution"),
]

# LLMLingua-AR là điều kiện bắt buộc để tách nguồn gốc speedup:
# Nếu CC-DFlash-R3 nhanh hơn DFlash-R1, nhưng LLMLingua-AR cũng nhanh tương đương
# → speedup đến từ compression, KHÔNG phải DFlash
# Thiếu baseline này → kết luận sai
```

---

### `src/ccdf/__init__.py`
*Public API entry point*

```python
# src/ccdf/__init__.py
from .dflash.loader import load_all
from .pipeline.ccdf_pipeline import CCDFlashPipeline
from .benchmark.runner import BenchmarkRunner
from .benchmark.metrics import MetricsCollector
from .compression.base import CompressorBase
from .compression.llmlingua import LLMLinguaCompressor
from .compression.passthrough import PassthroughCompressor

__version__ = "1.0.0"
__all__ = [
    "load_all", "CCDFlashPipeline",
    "BenchmarkRunner", "MetricsCollector",
    "CompressorBase", "LLMLinguaCompressor", "PassthroughCompressor",
    "build_pipeline",
]


def build_pipeline(
    target_id:    str  = "Qwen/Qwen3-4B",
    draft_id:     str  = "z-lab/Qwen3-4B-DFlash-b16",
    compressor:   str  = "llmlingua",
    device:       str  = "cuda:0",
    load_in_4bit: bool = True,
) -> CCDFlashPipeline:
    """
    Quick start: tạo pipeline hoàn chỉnh với một lệnh.

    Ví dụ:
        from ccdf import build_pipeline
        pipeline = build_pipeline()
        result = pipeline.run(context="...", question="...", keep_rate=0.33)
    """
    target, draft, tok = load_all(target_id, draft_id, device, load_in_4bit)

    comp = (LLMLinguaCompressor(device_map="cpu")
            if compressor == "llmlingua"
            else PassthroughCompressor())

    return CCDFlashPipeline(target=target, draft=draft,
                            tokenizer=tok, compressor=comp)
```

---

## Roadmap phát triển — Stage-Gate

### Gate 0 — Synthetic Probe (BLOCKER)

**Làm ngay, không bỏ qua.** Mọi thứ khác vô nghĩa nếu Gate này fail.

**Rủi ro cần kiểm tra:**  
Khi Target load 4-bit NF4, `nn.Linear` → `Linear4bit`. Code DFlash dùng
`trust_remote_code` có thể check `isinstance(module, nn.Linear)` để tìm lớp cần inject.
Sau quantization check này trả `False` → silent failure → τ = 0 → DFlash vô dụng.

```bash
python scripts/synthetic_probe.py
```

**Pass criteria (đủ 4):**
- [ ] H_target dtype = `bfloat16`
- [ ] H_target không có NaN
- [ ] H_target norm > 0
- [ ] τ (acceptance_length) > 0 khi chạy spec_generate

**Nếu fail:** Tìm `isinstance(module, nn.Linear)` trong DFlash custom code,
patch thành `hasattr(module, 'weight')`.

---

### Phase 1 — MVP (Tuần 1–4)

#### Tuần 1 — Split code và chạy baseline

```bash
# Bước 1: Copy code gốc từ z-lab/dflash vào đúng module
# model/dflash.py      → src/ccdf/dflash/model.py, attention.py, generate.py
# model/utils.py       → src/ccdf/dflash/utils.py + benchmark/datasets.py
# benchmark.py         → src/ccdf/dflash/loader.py + benchmark/runner.py

# Bước 2: Cài môi trường
bash setup.sh

# Bước 3: Chạy Synthetic Probe
python scripts/synthetic_probe.py

# Bước 4: Chạy baseline — xác nhận pipeline hoạt động
python scripts/run_mvp.py --condition DFlash-R1 --group short --n 20
```

**Ghi lại:**
- VRAM thực tế sau load (kỳ vọng < 5 GB)
- τ baseline (kỳ vọng ~5–7 tokens)
- tok/s baseline (kỳ vọng ~70–90)

#### Tuần 2 — LLMLingua-2 Integration

```bash
# Chạy đủ 8 conditions
python scripts/run_mvp.py --conditions all --group short  --n 100
python scripts/run_mvp.py --conditions all --group long   --n 100
```

#### Tuần 3 — Dataset Long-Context

```bash
python scripts/create_dataset.py \
    --source gsm8k \
    --augment wikipedia \
    --target_tokens 800 \
    --output data/processed/gsm8k_long.json
```

**Pipeline tạo dataset:**
1. GSM8K test set (1.319 samples)
2. Tìm Wikipedia passage theo keyword từ question
3. Concatenate: `[Wikipedia passage]\n\n[question]`
4. Filter: 500–1500 tokens
5. Document: nguồn Wikipedia, ngày, chiến lược augment

#### Tuần 4 — Phân tích và Pareto Curve

```bash
python scripts/plot_results.py --input results/results_raw.json
```

**4 biểu đồ:**
1. T_prefill vs N (log-log) → slope O(N²/R²)
2. Speedup & τ vs R → tách short/long
3. EM vs R → short-context quality
4. Pareto frontier → Speedup vs EM

**Quyết định sau Tuần 4:**
- Speedup > 1.5× với EM giảm < 3% trên long-context → **Go Phase 2**
- Không đạt → **Báo cáo trung thực, Phase 2 là future work**

---

### Phase 2 — Gemma4-E2B Compressor (Sau Gate 1)

**Điều kiện:** LLMLingua-2 baseline chạy ổn, kết quả tích cực.

**Lý do tách riêng:** Gemma4-E2B là abstractive compressor — rủi ro mất số
toán học là structural, không patch được. Phải có LLMLingua-2 baseline trước
để biết threshold chất lượng.

**Bước 1 — Dataset với Gemma4-E4B Teacher:**
```python
# Teacher prompt
SYSTEM: Bạn là chuyên gia nén văn bản giữ nghĩa.
Nhiệm vụ: nén đoạn văn sau xuống còn {target_tokens} tokens.
Yêu cầu: giữ nguyên mọi thông tin cần để giải toán.
Chỉ trả về đoạn văn đã nén, không giải thích.
USER: {context_gốc}
```

**Filter 6 tiêu chí bắt buộc:**
1. R_actual trong ±10% target R
2. Answer EM ≥ 85% so với context gốc
3. Semantic similarity ≥ 0.85
4. Không chứa lời giải thích phụ
5. Không hallucinate thông tin mới
6. Không mất số liệu quan trọng (số, đơn vị)

**Bước 2 — Fine-tune với Unsloth:**
```python
model_name     = "google/gemma-4-E2B-it"
load_in_4bit   = True      # 4-bit QLoRA, ~6-7GB VRAM
lora_r         = 16
lora_alpha     = 32
batch_size     = 2
grad_accum     = 4
epochs         = 3
lr             = 2e-4
```

**Bước 3 — Implement GemmaCompressor:**
```python
# src/ccdf/compression/gemma.py — skeleton
# Kế thừa CompressorBase, implement compress()
# Chỉ làm sau khi có fine-tuned checkpoint
```

**Ngưỡng giữ lại:** Pareto tốt hơn LLMLingua-2:
- EM cao hơn ≥ 1% với cùng speedup, HOẶC
- Speedup cao hơn ≥ 0.5× với cùng EM

---

## Requirements.txt (locked)

```
transformers==4.57.3
torch==2.9.1+cu121
accelerate>=0.30.0
bitsandbytes>=0.43.0
llmlingua>=0.2.0
datasets>=2.14.0
matplotlib>=3.7.0
numpy>=1.24.0
# DFlash từ source — PIN commit hash
# git+https://github.com/z-lab/dflash.git@{COMMIT_HASH}
```

---

## Bộ chỉ số đánh giá (10 chỉ số)

| #   | Nhóm        | Chỉ số                | Ký hiệu     | Cách tính                               | Nhóm          |
| --- | ----------- | --------------------- | ----------- | --------------------------------------- | ------------- |
| 1   | Hiệu năng   | Throughput            | tok/s       | n_tokens / elapsed                      | Cả hai        |
| 2   | Hiệu năng   | Tổng Speedup          | S_total     | tok/s / tok/s_AR                        | Cả hai        |
| 3   | Hiệu năng   | Prefill Latency       | T_pf (ms)   | CUDA synchronize                        | Cả hai        |
| 4   | Hiệu năng   | Compress Overhead     | T_comp (ms) | Đo riêng compressor                     | Cả hai        |
| 5   | DFlash      | **Acceptance Length** | **τ**       | **compute_tau() — từ benchmark.py gốc** | Cả hai        |
| 6   | DFlash      | Acceptance Rate       | α (%)       | τ / block_size × 100                    | Cả hai        |
| 7   | Chất lượng  | Exact Match           | EM (%)      | compute_exact_match()                   | Short-context |
| 8   | Chất lượng  | Invalid Output Rate   | IOR (%)     | output < 5 chars                        | Cả hai        |
| 9   | Compression | Actual Ratio          | R_act       | N_gốc / N_nén                           | Cả hai        |
| 10  | Compression | Semantic Score        | Sem         | Cosine sim. embeddings                  | Cả hai        |

---

## Ký hiệu thống nhất

| Ký hiệu    | Định nghĩa                                                      |
| ---------- | --------------------------------------------------------------- |
| C_gốc      | Context đầu vào gốc (N tokens)                                  |
| C_nén      | Context đã nén (N/R tokens, text tự nhiên)                      |
| R          | Compression ratio = N_original / N_compressed                   |
| R*         | Compression ratio Pareto-optimal (kỳ vọng R*≈3, cần xác nhận)   |
| N          | Số token của C_gốc                                              |
| K          | Block size DFlash (K=16, từ z-lab/Qwen3-4B-DFlash-b16)          |
| τ          | Acceptance length — primary DFlash metric — từ benchmark.py gốc |
| α          | Acceptance rate (%) = τ/K × 100                                 |
| H_target   | Hidden states của Target từ C_nén — extract_context_feature()   |
| T_compress | Thời gian nén — đo thực tế, không giả định                      |
| T_prefill  | Thời gian prefill C_nén qua Target                              |
| ε(R)       | \|\|H_target(C_gốc) - H_target(C_nén)\|\| — tăng theo R         |

---

## Câu hỏi mở — trả lời trước khi submit

| Câu hỏi                                | Tại sao quan trọng                       | Cách trả lời                               |
| -------------------------------------- | ---------------------------------------- | ------------------------------------------ |
| GSM8K augmented tạo như thế nào?       | Không document → không tái lập được      | create_dataset.py + ghi nguồn Wikipedia    |
| T_compress thực tế bao nhiêu ms?       | Breakeven phụ thuộc số này               | Đo trong synthetic_probe.py                |
| VRAM peak thực tế bao nhiêu GB?        | Chưa có số thực                          | torch.cuda.memory_allocated() sau load all |
| τ với C_nén là bao nhiêu?              | Primary metric — phải đo, không giả định | compute_tau() sau Gate 0 pass              |
| Speedup đến từ compression hay DFlash? | Kết luận về contribution                 | So sánh LLMLingua-AR vs CC-DFlash          |

---

*CC-DFlash Instruction v2.0 · 2026 · arXiv:2602.06036 + arXiv:2403.12968*
