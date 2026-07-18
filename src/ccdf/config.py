"""Root configuration loader with deterministic path expansion."""

from __future__ import annotations

import copy
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

import yaml

from .errors import ConfigurationError


def _expand(value: Any, project_root: Path) -> Any:
    if isinstance(value, str):
        expanded = value.replace("${PROJECT_ROOT}", str(project_root))
        return os.path.expandvars(os.path.expanduser(expanded))
    if isinstance(value, list):
        return [_expand(item, project_root) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, project_root) for key, item in value.items()}
    return value


def _require(mapping: Mapping[str, Any], dotted: str) -> Any:
    current: Any = mapping
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ConfigurationError(f"missing required config key: {dotted}")
        current = current[part]
    return current


def _merge_existing(base: dict[str, Any], overrides: Mapping[str, Any], prefix: str = "") -> None:
    """Apply profile overrides while rejecting misspelled or newly invented keys."""
    for key, value in overrides.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if key not in base:
            raise ConfigurationError(f"profile override targets unknown config key: {dotted}")
        if isinstance(value, Mapping):
            if not isinstance(base[key], dict):
                raise ConfigurationError(f"profile override type mismatch at: {dotted}")
            _merge_existing(base[key], value, dotted)
        else:
            base[key] = copy.deepcopy(value)


@dataclass(frozen=True)
class ResolvedProtocolProfile:
    """A named protocol profile and its fully resolved runtime configuration."""

    name: str
    settings: dict[str, Any]
    config: "Config"
    source_config_sha256: str

    def require(self, dotted: str) -> Any:
        return _require(self.settings, dotted)

    def path_for(self, dotted: str) -> Path:
        value = self.require(dotted)
        if not isinstance(value, str):
            raise ConfigurationError(f"profile key is not a path string: {dotted}")
        return Path(value).resolve()

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_profile": self.name,
            "source_config_path": str(self.config.path),
            "source_config_sha256": self.source_config_sha256,
            "profile_settings": copy.deepcopy(self.settings),
            "resolved_config": copy.deepcopy(self.config.data),
        }


@dataclass(frozen=True)
class Config:
    path: Path
    root: Path
    data: dict[str, Any]

    def get(self, dotted: str, default: Any = None) -> Any:
        current: Any = self.data
        for part in dotted.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return default
            current = current[part]
        return current

    def require(self, dotted: str) -> Any:
        return _require(self.data, dotted)

    def path_for(self, dotted: str) -> Path:
        value = self.require(dotted)
        if not isinstance(value, str):
            raise ConfigurationError(f"config key is not a path string: {dotted}")
        return Path(value).resolve()

    def model_profile(self, condition: str, target_profile: str = "primary") -> dict[str, Any]:
        if condition == "baseline":
            return dict(self.require("models.baseline"))
        if condition != "dflash":
            raise ConfigurationError(f"unknown condition: {condition}")
        target = dict(self.require("models.dflash.target"))
        if target_profile == "fallback":
            target = {
                **target,
                "model_id": target["fallback_model_id"],
                "local_path": target["fallback_local_path"],
                "quantization": target["fallback_quantization"],
                "tokenizer_path": target["fallback_local_path"],
            }
        elif target_profile != "primary":
            raise ConfigurationError(f"unknown target profile: {target_profile}")
        return target

    def resolve_active_protocol_profile(self) -> ResolvedProtocolProfile:
        active = self.require("protocol_profiles.active")
        if not isinstance(active, str) or not active:
            raise ConfigurationError("protocol_profiles.active must be a non-empty string")
        profiles = self.require("protocol_profiles.profiles")
        if not isinstance(profiles, Mapping) or active not in profiles:
            raise ConfigurationError(f"active protocol profile is not defined: {active}")
        settings = profiles[active]
        if not isinstance(settings, Mapping):
            raise ConfigurationError(f"protocol profile must be a mapping: {active}")
        overrides = _require(settings, "config_overrides")
        if not isinstance(overrides, Mapping):
            raise ConfigurationError("protocol profile config_overrides must be a mapping")
        resolved_data = copy.deepcopy(self.data)
        _merge_existing(resolved_data, overrides)
        resolved = Config(path=self.path, root=self.root, data=resolved_data)
        resolved.validate(require_model_files=False, require_canonical_block=False)
        return ResolvedProtocolProfile(
            name=active,
            settings=copy.deepcopy(dict(settings)),
            config=resolved,
            source_config_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
        )

    def resolve_dataset_smoke_profile(self) -> ResolvedProtocolProfile:
        settings = self.require("dataset_smoke")
        if not isinstance(settings, Mapping):
            raise ConfigurationError("dataset_smoke must be a mapping")
        overrides = _require(settings, "config_overrides")
        if not isinstance(overrides, Mapping):
            raise ConfigurationError("dataset_smoke.config_overrides must be a mapping")
        resolved_data = copy.deepcopy(self.data)
        _merge_existing(resolved_data, overrides)
        resolved = Config(path=self.path, root=self.root, data=resolved_data)
        resolved.validate(require_model_files=False)
        return ResolvedProtocolProfile(
            name="dataset_smoke",
            settings=copy.deepcopy(dict(settings)),
            config=resolved,
            source_config_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
        )

    def validate(
        self,
        require_model_files: bool = False,
        *,
        require_canonical_block: bool = True,
    ) -> list[str]:
        required = [
            "paths.project_root",
            "paths.baseline_model",
            "paths.dflash_target_model",
            "paths.dflash_drafter_model",
            "paths.compressor_model",
            "models.baseline.model_id",
            "models.baseline.local_path",
            "models.baseline.tokenizer_path",
            "models.baseline.device_map",
            "models.baseline.trust_remote_code",
            "models.dflash.target.model_id",
            "models.dflash.target.local_path",
            "models.dflash.target.tokenizer_path",
            "models.dflash.target.device_map",
            "models.dflash.target.trust_remote_code",
            "models.dflash.drafter.model_id",
            "models.dflash.drafter.local_path",
            "models.dflash.drafter.device_map",
            "models.dflash.drafter.trust_remote_code",
            "models.compressor.local_path",
            "models.compressor.device",
            "models.compressor.reserved_budget_gib",
            "memory.dflash_peak_reserved_limit_gib",
            "memory.device_capacity_gib",
            "memory.compressor_residency_mode",
            "memory.generation_residency_mode",
            "memory.request_cache_policy",
            "memory.enforce_after_model_load",
            "memory.enforce_after_generation",
            "runtime.attention_backend",
            "runtime.sdpa_kernel",
            "runtime.awq_split_k_iters",
            "runtime.device",
            "runtime.local_files_only",
            "runtime.temperature",
            "runtime.max_new_tokens",
            "runtime.stop_token_ids",
            "runtime.enable_thinking",
            "runtime.deterministic",
            "runtime.seed",
            "runtime.allow_tf32",
            "runtime.matmul_precision",
            "runtime.cuda_allocator_conf",
            "optimization.gpu_resident_acceptance",
            "optimization.output_contract_mode",
            "optimization.full_structural_audit",
            "optimization.compact_structural_audit",
            "optimization.profile_components",
            "optimization.block_policy.mode",
            "optimization.block_policy.fixed_block_size",
            "optimization.block_policy.allow_subblock_shapes",
            "validation.require_cuda",
            "validation.require_single_gpu",
            "validation.require_full_gpu_placement",
            "benchmark.repetitions",
            "benchmark.warmup_requests",
            "prompts.system",
            "datasets.seed",
            "datasets.sample_size",
            "datasets.qmsum_context_policy",
            "datasets.qmsum_query_policy",
            "dataset_smoke.version",
            "dataset_smoke.artifact_directory",
            "dataset_smoke.review_archive",
            "protocol_profiles.active",
            "protocol_profiles.profiles",
        ]
        for key in required:
            self.require(key)
        warnings: list[str] = []
        limit = float(self.require("memory.dflash_peak_reserved_limit_gib"))
        reserve = float(self.require("models.compressor.reserved_budget_gib"))
        capacity = float(self.require("memory.device_capacity_gib"))
        if limit <= 0 or reserve < 0 or capacity <= 0:
            raise ConfigurationError("memory limits must be positive")
        compressor_residency = str(self.require("memory.compressor_residency_mode"))
        generation_residency = str(self.require("memory.generation_residency_mode"))
        allowed_residency = {"staged", "simultaneous"}
        if compressor_residency not in allowed_residency:
            raise ConfigurationError(
                f"unsupported compressor residency mode: {compressor_residency}"
            )
        if generation_residency not in allowed_residency:
            raise ConfigurationError(
                f"unsupported generation residency mode: {generation_residency}"
            )
        if compressor_residency != generation_residency:
            raise ConfigurationError(
                "compressor and generation residency modes must describe the same lifecycle"
            )
        request_cache_policy = str(self.require("memory.request_cache_policy"))
        if request_cache_policy not in {"preserve", "release_unused"}:
            raise ConfigurationError(f"unsupported memory.request_cache_policy: {request_cache_policy}")
        if compressor_residency == "simultaneous" and limit + reserve > capacity:
            warnings.append(
                "simultaneous compressor plus D-Flash residency exceeds configured device capacity"
            )
        if self.require("runtime.attention_backend") != "sdpa":
            raise ConfigurationError("runtime requires attention_backend=sdpa")
        sdpa_kernel = str(self.require("runtime.sdpa_kernel"))
        if sdpa_kernel not in {"math", "auto"}:
            raise ConfigurationError(f"unsupported runtime.sdpa_kernel: {sdpa_kernel}")
        allocator_conf = self.require("runtime.cuda_allocator_conf")
        if allocator_conf is not None and (not isinstance(allocator_conf, str) or not allocator_conf):
            raise ConfigurationError("runtime.cuda_allocator_conf must be null or a non-empty string")
        if int(self.require("runtime.awq_split_k_iters")) != 1:
            raise ConfigurationError("canonical runtime requires awq_split_k_iters=1")
        allowed = list(self.require("optimization.block_policy.allowed_block_sizes"))
        checkpoint = int(self.require("models.dflash.drafter.checkpoint_block_size"))
        if sorted(set(allowed)) != sorted(allowed):
            raise ConfigurationError("allowed block sizes must be unique and sorted")
        if any(int(size) < 2 or int(size) > checkpoint for size in allowed):
            raise ConfigurationError("allowed block sizes must be in [2, checkpoint_block_size]")
        fixed_block = int(self.require("optimization.block_policy.fixed_block_size"))
        if fixed_block not in allowed:
            raise ConfigurationError("fixed block size must be listed in allowed block sizes")
        if require_canonical_block and fixed_block != checkpoint:
            raise ConfigurationError(
                "canonical fixed block size must match the D-Flash checkpoint block size"
            )
        configured_devices = {
            str(self.require("runtime.device")),
            str(self.require("models.baseline.device_map")),
            str(self.require("models.dflash.target.device_map")),
            str(self.require("models.dflash.drafter.device_map")),
            str(self.require("models.compressor.device")),
        }
        if any(not value.startswith("cuda") for value in configured_devices):
            raise ConfigurationError(f"all configured runtime devices must be CUDA: {configured_devices}")
        self._validate_protocol_profiles(allowed)
        self._validate_dataset_smoke()
        if require_model_files:
            for key in (
                "models.baseline.local_path",
                "models.dflash.target.local_path",
                "models.dflash.drafter.local_path",
            ):
                path = Path(self.require(key))
                if not path.exists():
                    raise ConfigurationError(f"model path does not exist: {path}")
        return warnings

    def _validate_protocol_profiles(self, allowed_blocks: list[Any]) -> None:
        profiles = self.require("protocol_profiles.profiles")
        active = self.require("protocol_profiles.active")
        if not isinstance(profiles, Mapping) or not profiles:
            raise ConfigurationError("protocol_profiles.profiles must be a non-empty mapping")
        if not isinstance(active, str) or active not in profiles:
            raise ConfigurationError(f"active protocol profile is not defined: {active}")
        profile = profiles[active]
        if not isinstance(profile, Mapping):
            raise ConfigurationError("active protocol profile must be a mapping")
        required = (
            "artifact_directory", "review_archive", "dataset", "config_overrides",
            "compression.keep_rate", "compression.min_context_tokens",
            "compression.chunk_size_tokens", "compression.chunk_overlap_tokens",
            "compression.tokenizer", "compression.merge_policy", "prompt_contract.question",
            "prompt_contract.output_instruction", "prompt_contract.strict_output_pattern",
            "prompt_contract.tolerant_field_pattern", "prompt_contract.distractor_template",
            "prompt_contract.evidence_template", "conditions", "parity_pairs",
            "hard_gates.condition_success_rate",
            "hard_gates.pair_generated_token_parity_rate",
            "hard_gates.exact_field_quality_rate", "hard_gates.protected_input_rate",
            "hard_gates.metric_validity_rate", "hard_gates.max_oom_events",
            "hard_gates.dflash_peak_reserved_vram_gib", "fixtures",
        )
        for key in required:
            _require(profile, key)
        for pattern_key in ("strict_output_pattern", "tolerant_field_pattern"):
            try:
                re.compile(str(_require(profile, f"prompt_contract.{pattern_key}")))
            except re.error as exc:
                raise ConfigurationError(f"invalid {pattern_key}: {exc}") from exc
        conditions = _require(profile, "conditions")
        if not isinstance(conditions, list) or not conditions:
            raise ConfigurationError("protocol profile conditions must be a non-empty list")
        condition_names: list[str] = []
        for condition in conditions:
            if not isinstance(condition, Mapping):
                raise ConfigurationError("each protocol condition must be a mapping")
            name = str(_require(condition, "name"))
            runtime_condition = str(_require(condition, "runtime_condition"))
            prompt_kind = str(_require(condition, "prompt_kind"))
            if runtime_condition not in {"baseline", "dflash"}:
                raise ConfigurationError(f"invalid runtime condition for {name}: {runtime_condition}")
            if prompt_kind not in {"original", "compressed"}:
                raise ConfigurationError(f"invalid prompt kind for {name}: {prompt_kind}")
            if prompt_kind == "compressed":
                _require(condition, "reduction_reference_condition")
            condition_names.append(name)
        if len(condition_names) != len(set(condition_names)):
            raise ConfigurationError("protocol condition names must be unique")
        pairs = _require(profile, "parity_pairs")
        if not isinstance(pairs, list) or not pairs:
            raise ConfigurationError("protocol parity_pairs must be a non-empty list")
        for pair in pairs:
            for side in ("left", "right"):
                if str(_require(pair, side)) not in condition_names:
                    raise ConfigurationError(f"parity pair references unknown condition: {pair}")
        fixtures = _require(profile, "fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            raise ConfigurationError("protocol fixtures must be a non-empty list")
        for fixture in fixtures:
            for key in (
                "turns", "evidence_position_fraction", "owner", "approval_code", "quantity"
            ):
                _require(fixture, key)
        for rate_key in (
            "condition_success_rate", "pair_generated_token_parity_rate",
            "exact_field_quality_rate", "protected_input_rate", "metric_validity_rate",
        ):
            rate = float(_require(profile, f"hard_gates.{rate_key}"))
            if not 0 < rate <= 1:
                raise ConfigurationError(f"protocol hard-gate rate must be in (0, 1]: {rate_key}")
        if int(_require(profile, "hard_gates.max_oom_events")) < 0:
            raise ConfigurationError("max_oom_events must be non-negative")
        memory_limit = float(_require(profile, "hard_gates.dflash_peak_reserved_vram_gib"))
        if memory_limit <= 0:
            raise ConfigurationError("D-Flash profile memory gate must be positive")
        overrides = _require(profile, "config_overrides")
        if not isinstance(overrides, Mapping):
            raise ConfigurationError("config_overrides must be a mapping")
        resolved = copy.deepcopy(self.data)
        _merge_existing(resolved, overrides)
        profile_block = int(_require(resolved, "optimization.block_policy.fixed_block_size"))
        if profile_block not in [int(value) for value in allowed_blocks]:
            raise ConfigurationError("protocol profile block size must be allowed by canonical config")
        if float(_require(resolved, "memory.dflash_peak_reserved_limit_gib")) > memory_limit:
            raise ConfigurationError(
                "resolved runtime memory limit cannot exceed the protocol hard gate"
            )

    def _validate_dataset_smoke(self) -> None:
        required = (
            "config_overrides",
            "cohorts.gsm8k", "cohorts.qmsum", "cohorts.manifest",
            "cohorts.selection_manifest",
            "cohorts.expected_rows_per_dataset", "compression.keep_rate",
            "compression.min_context_tokens", "compression.chunk_size_tokens",
            "compression.chunk_overlap_tokens", "compression.tokenizer",
            "compression.merge_policy", "prompts.gsm8k_context_header",
            "prompts.gsm8k_question_header", "prompts.qmsum_context_header",
            "prompts.qmsum_question_header", "generation.gsm8k_max_new_tokens",
            "generation.qmsum_max_new_tokens", "generation.warmup_requests",
            "generation.repetitions", "generation.qmsum_context_chunk_size_tokens",
            "generation.qmsum_context_chunk_overlap_tokens",
            "generation.qmsum_context_chunk_tokenizer",
            "generation.qmsum_context_merge_policy", "generation.condition_worker_max_attempts",
            "conditions", "parity_pairs",
            "evaluators.gsm8k.version", "evaluators.gsm8k.final_answer_prefix",
            "evaluators.gsm8k.fixture_cases", "evaluators.qmsum.version",
            "evaluators.qmsum.word_pattern", "evaluators.qmsum.semantic_correctness",
            "evaluators.qmsum.fixture_cases", "hard_gates.successful_condition_runs",
            "hard_gates.pair_input_token_parity_rate",
            "hard_gates.pair_generated_token_parity_rate",
            "hard_gates.protected_fields_rate", "hard_gates.gsm8k_evaluator_valid_count",
            "hard_gates.qmsum_evaluator_valid_count",
            "hard_gates.qmsum_precompression_coverage_rate",
            "hard_gates.hidden_truncated_tokens",
            "hard_gates.dflash_peak_reserved_vram_gib",
            "hard_gates.metric_validity_rate", "hard_gates.max_oom_events",
            "hard_gates.max_error_events", "validation_commands.compileall",
            "validation_commands.pytest", "validation_commands.pip_check",
            "validation_commands.diff_check", "validation_commands.artifact_verify",
        )
        settings = self.require("dataset_smoke")
        if not isinstance(settings, Mapping):
            raise ConfigurationError("dataset_smoke must be a mapping")
        for key in required:
            _require(settings, key)
        compression = _require(settings, "compression")
        keep_rate = float(_require(compression, "keep_rate"))
        chunk_size = int(_require(compression, "chunk_size_tokens"))
        overlap = int(_require(compression, "chunk_overlap_tokens"))
        if not 0 < keep_rate <= 1:
            raise ConfigurationError("dataset_smoke compression keep_rate must be in (0, 1]")
        if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
            raise ConfigurationError("invalid dataset_smoke token chunk size/overlap")
        if _require(compression, "tokenizer") != "compressor":
            raise ConfigurationError("dataset_smoke compression tokenizer must be compressor")
        if _require(compression, "merge_policy") != "newline_preserve_order":
            raise ConfigurationError("unsupported dataset_smoke compression merge policy")
        generation = _require(settings, "generation")
        generation_chunk_size = int(_require(generation, "qmsum_context_chunk_size_tokens"))
        generation_overlap = int(_require(generation, "qmsum_context_chunk_overlap_tokens"))
        if generation_chunk_size < 1 or generation_overlap < 0 or generation_overlap >= generation_chunk_size:
            raise ConfigurationError("invalid QMSum generation token chunk size/overlap")
        if _require(generation, "qmsum_context_chunk_tokenizer") != "generation_target":
            raise ConfigurationError("QMSum generation chunk tokenizer must be generation_target")
        if _require(generation, "qmsum_context_merge_policy") != "newline_preserve_order":
            raise ConfigurationError("unsupported QMSum generation context merge policy")
        if int(_require(generation, "condition_worker_max_attempts")) < 1:
            raise ConfigurationError("condition worker max attempts must be positive")
        if self.require("datasets.qmsum_context_policy") != "full_transcript":
            raise ConfigurationError("QMSum dataset context policy must be full_transcript")
        conditions = list(_require(settings, "conditions"))
        names = [str(_require(item, "name")) for item in conditions]
        if len(names) != 4 or len(set(names)) != 4:
            raise ConfigurationError("dataset_smoke requires four unique conditions")
        for condition in conditions:
            if _require(condition, "runtime_condition") not in {"baseline", "dflash"}:
                raise ConfigurationError("invalid dataset_smoke runtime condition")
            if _require(condition, "prompt_kind") not in {"original", "compressed"}:
                raise ConfigurationError("invalid dataset_smoke prompt kind")
        for pair in _require(settings, "parity_pairs"):
            if _require(pair, "left") not in names or _require(pair, "right") not in names:
                raise ConfigurationError("dataset_smoke parity pair references unknown condition")
        try:
            re.compile(str(_require(settings, "evaluators.qmsum.word_pattern")))
        except re.error as exc:
            raise ConfigurationError(f"invalid QMSum evaluator word pattern: {exc}") from exc
        if _require(settings, "evaluators.qmsum.semantic_correctness") != "NOT_CLAIMED":
            raise ConfigurationError("QMSum evaluator cannot claim semantic correctness")


def load_config(path: str | Path = "config.yml") -> Config:
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigurationError(f"config file not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigurationError("root config must be a mapping")
    project_root = Path(os.environ.get("PROJECT_ROOT", config_path.parent)).expanduser().resolve()
    expanded = _expand(raw, project_root)
    config = Config(path=config_path, root=project_root, data=expanded)
    config.validate(require_model_files=False)
    return config
