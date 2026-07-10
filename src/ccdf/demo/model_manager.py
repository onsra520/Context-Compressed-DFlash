from __future__ import annotations
import gc
import torch
import importlib.util

from ccdf.dflash.loader import load_draft, load_tokenizer

def _attention_backend() -> str:
    if importlib.util.find_spec("flash_attn") is None:
        return "sdpa"
    return "flash_attention_2"

def _load_target_4bit(target_path: str, device: str, attn_implementation: str):
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
        target_path,
        attn_implementation=attn_implementation,
        quantization_config=quantization_config,
        device_map={"": device},
        dtype=torch.bfloat16,
    ).eval()

class ModelManager:
    def __init__(self, config: dict):
        self.config = config
        self.device = config.get("runtime", {}).get("device", "cuda:0")
        
        model_cfg = config.get("model", {})
        self.target_path = model_cfg.get("target_id", "models/Qwen3-4B")
        self.draft_path = model_cfg.get("draft_id", "models/Qwen3-4B-DFlash-b16")
        self.tokenizer_path = model_cfg.get("tokenizer_id", "models/Qwen3-4B")
        
        self.target = None
        self.draft = None
        self.tokenizer = None
        self.compressor = None
        
        # Determine if we're in dry run mode
        self.dry_run = self.config.get('dry_run', False) if isinstance(self.config, dict) else getattr(self.config, 'dry_run', False)

    def get_tokenizer(self):
        if self.dry_run:
            class DummyTokenizer:
                eos_token_id = 0
                def apply_chat_template(self, messages, **kwargs):
                    return messages[0]["content"]
                def encode(self, text, **kwargs):
                    return torch.tensor([[1, 2, 3]])
                def decode(self, token_ids, **kwargs):
                    return "dummy decoded text"
            return DummyTokenizer()
            
        if self.tokenizer is None:
            self.tokenizer = load_tokenizer(self.tokenizer_path)
        return self.tokenizer

    def get_target(self):
        if self.dry_run:
            class DummyTarget:
                def __call__(self, *args, **kwargs):
                    pass
            return DummyTarget()
            
        if self.target is None:
            attn_impl = _attention_backend()
            self.target = _load_target_4bit(self.target_path, self.device, attn_impl)
        return self.target

    def get_draft(self):
        if self.dry_run:
            class DummyDraft:
                pass
            return DummyDraft()
            
        if self.draft is None:
            attn_impl = _attention_backend()
            self.draft = load_draft(self.draft_path, device=self.device, attn_implementation=attn_impl, dtype=torch.bfloat16)
        return self.draft

    def get_compressor(self):
        if self.dry_run:
            class DummyCompressor:
                def compress(self, context, question, keep_rate):
                    info = {
                        "t_compress_ms": 0.0,
                        "R_actual": keep_rate,
                        "N_original": 100,
                        "N_compressed": int(100 * keep_rate)
                    }
                    return f"{context} {question}", info
            return DummyCompressor()
            
        if self.compressor is None:
            from ccdf.compression.llmlingua import LLMLinguaCompressor
            self.compressor = LLMLinguaCompressor(device_map=self.device)
        return self.compressor

    def cleanup_for_condition(self, condition_id: str):
        if self.dry_run:
            return
            
        from ccdf.demo.condition_registry import get_condition
        cond = get_condition(condition_id)
        
        if not cond["uses_compression"] and self.compressor is not None:
            del self.compressor
            self.compressor = None
            
        if not cond["uses_dflash"] and self.draft is not None:
            del self.draft
            self.draft = None
            
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
    def cleanup_all(self):
        self.target = None
        self.draft = None
        self.tokenizer = None
        self.compressor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
