"""Schema injection, JSON parsing, validation, and self-healing repair loop."""

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.schemas import LLMStructuredOutputError, RawCompletionResult

logger = logging.getLogger("mediflux.llm.parser")

T = TypeVar("T", bound=BaseModel)


def inject_schema(
    messages: list[dict[str, str]],
    response_model: type[BaseModel],
) -> list[dict[str, str]]:
    """Inject Pydantic model JSON schema and formatting constraints into conversation messages.

    Does not mutate the incoming messages list.
    """
    schema_dict = response_model.model_json_schema()
    schema_json = json.dumps(schema_dict, indent=2)

    instruction = (
        "\n\n[OUTPUT SCHEMA REQUIREMENT]\n"
        "You MUST respond ONLY with a valid JSON object strictly conforming to this schema:\n"
        f"{schema_json}\n\n"
        "RULES:\n"
        "1. Return raw valid JSON ONLY.\n"
        "2. Do NOT wrap output in markdown code blocks (e.g. do not use ```json ... ```).\n"
        "3. Do NOT include greetings, preamble, explanations, or trailing commentary.\n"
    )

    new_messages: list[dict[str, str]] = []
    has_system = False

    for msg in messages:
        if msg.get("role") == "system" and not has_system:
            new_messages.append({
                "role": "system",
                "content": f"{msg.get('content', '')}{instruction}",
            })
            has_system = True
        else:
            new_messages.append(dict(msg))

    if not has_system:
        # Prepend system instruction
        new_messages.insert(
            0,
            {
                "role": "system",
                "content": f"You are a structured data processing agent.{instruction}",
            },
        )

    return new_messages


def extract_json_str(raw_text: str) -> str:
    """Extract a candidate JSON string from LLM response text, stripping markdown and extraneous text."""
    text = raw_text.strip()
    if not text:
        return ""

    # 1. Check for markdown code fences (```json ... ``` or ``` ... ```)
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()

    # 2. Strip leading/trailing ``` fences if present on outer lines
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 3. Locate outer-most JSON object or array braces
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()

    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return text[first_bracket : last_bracket + 1].strip()

    return text


def parse_and_validate(raw_text: str, response_model: type[T]) -> T:
    """Extract JSON from raw completion text and validate against the Pydantic response model.

    Raises:
        ValueError, json.JSONDecodeError, or ValidationError if validation fails.
    """
    clean_json = extract_json_str(raw_text)
    if not clean_json:
        raise ValueError("LLM returned empty or whitespace-only response")

    # model_validate_json accepts JSON string directly
    return response_model.model_validate_json(clean_json)


async def execute_repair_loop(
    complete_fn: Callable[[list[dict[str, str]]], Awaitable[RawCompletionResult]],
    messages: list[dict[str, str]],
    response_model: type[T],
    max_repairs: int = 2,
) -> tuple[T, RawCompletionResult]:
    """Execute LLM call and validate output, automatically triggering self-healing repairs on failure.

    Up to `max_repairs` repair attempts are executed by sending back the broken output and
    validation error messages to the model.

    Raises:
        LLMStructuredOutputError: If output cannot be validated after max_repairs.
    """
    result = await complete_fn(messages)

    try:
        parsed = parse_and_validate(result.content, response_model)
        return parsed, result
    except (ValueError, ValidationError, json.JSONDecodeError) as initial_err:
        last_err: Exception = initial_err
        last_raw = result.content

    repair_messages = list(messages)
    accumulated_prompt = result.prompt_tokens
    accumulated_completion = result.completion_tokens
    accumulated_total = result.total_tokens
    accumulated_latency = result.latency_ms
    current_provider = result.provider
    current_model = result.model

    for attempt in range(1, max_repairs + 1):
        logger.warning(
            "Structured output validation failed (attempt %d/%d): %s. Executing repair loop...",
            attempt,
            max_repairs,
            last_err,
        )

        repair_messages.append({"role": "assistant", "content": last_raw})
        repair_messages.append({
            "role": "user",
            "content": (
                f"Your previous response failed schema validation with error:\n{last_err}\n\n"
                "Please fix the error and output ONLY the corrected valid JSON object conforming to the schema."
            ),
        })

        result = await complete_fn(repair_messages)
        last_raw = result.content
        accumulated_prompt += result.prompt_tokens
        accumulated_completion += result.completion_tokens
        accumulated_total += result.total_tokens
        accumulated_latency += result.latency_ms
        current_provider = result.provider
        current_model = result.model

        try:
            parsed = parse_and_validate(result.content, response_model)
            final_result = RawCompletionResult(
                content=result.content,
                provider=current_provider,
                model=current_model,
                prompt_tokens=accumulated_prompt,
                completion_tokens=accumulated_completion,
                total_tokens=accumulated_total,
                latency_ms=accumulated_latency,
            )
            return parsed, final_result
        except (ValueError, ValidationError, json.JSONDecodeError) as err:
            last_err = err

    raise LLMStructuredOutputError(
        message=f"Failed to produce valid structured output for {response_model.__name__} after {max_repairs} repair attempts: {last_err}",
        raw_output=last_raw,
        details={"attempts": max_repairs + 1, "last_error": str(last_err)},
    )
