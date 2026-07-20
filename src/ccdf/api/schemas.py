"""Request/response schemas for the live demo API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CreateRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    compression_device: Literal["cuda", "cpu"] = "cuda"
    max_new_tokens: int = Field(default=64, ge=1, le=256)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


class CreateRunResponse(BaseModel):
    run_id: str
    status: Literal["queued"]
