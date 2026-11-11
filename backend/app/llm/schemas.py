"""Pydantic schemas for LLM requests, responses, and token telemetry."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single message within an LLM conversation context."""

    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    """Standardized request schema for LLM generation."""

    model: str = "meta-llama/llama-3.1-70b-instruct"
    messages: list[ChatMessage]
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=16384)
    response_format: dict[str, Any] | None = None
    stream: bool = False


class TokenUsage(BaseModel):
    """Token consumption metrics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """Standardized response schema across all free LLM providers."""

    id: str
    provider: str
    model: str
    content: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cached: bool = False
