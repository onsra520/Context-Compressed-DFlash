from __future__ import annotations

# STATUS: skeleton-only placeholder. Do not treat this as the upstream DFlash implementation.

from typing import Any


def spec_generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from ..model_raw import dflash_generate as upstream_dflash_generate

    return_stats = kwargs.get("return_stats", False)
    result = upstream_dflash_generate(*args, **kwargs)

    if not return_stats:
        return {"output_ids": result, "acceptance_lengths": [], "n_steps": 0}

    return {
        "output_ids": result.output_ids,
        "acceptance_lengths": list(result.acceptance_lengths),
        "n_steps": len(result.acceptance_lengths),
        "num_input_tokens": result.num_input_tokens,
        "num_output_tokens": result.num_output_tokens,
        "time_to_first_token": result.time_to_first_token,
        "time_per_output_token": result.time_per_output_token,
    }