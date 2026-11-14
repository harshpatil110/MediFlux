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
    if hasattr(response_model, "model_json_schema"):
        schema_dict = response_model.model_json_schema()
    else:
        from pydantic import TypeAdapter

        schema_dict = TypeAdapter(response_model).json_schema()
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

    if hasattr(response_model, "model_validate_json"):
        return response_model.model_validate_json(clean_json)

    from pydantic import TypeAdapter

    return TypeAdapter(response_model).validate_json(clean_json)


def repair_json_string(raw_text: str) -> str:
    """Repair malformed JSON string (strip fences, fix quotes, commas, balance brackets)."""
    text = raw_text.strip()
    if not text:
        return "{}"

    # 1. Strip markdown code fences (```json ... ``` or ``` ... ```)
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced_match:
        text = fenced_match.group(1).strip()
    elif text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 2. Locate starting bracket ({ or [)
    first_brace = text.find("{")
    first_bracket = text.find("[")

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_idx = first_brace
    elif first_bracket != -1:
        start_idx = first_bracket
    else:
        start_idx = 0

    text = text[start_idx:].strip()

    # 3. Replace single-quoted keys with double-quoted keys: {'key': -> {"key":
    text = re.sub(r"([{,]\s*)'([a-zA-Z0-9_\-\.]+)'\s*:", r'\1"\2":', text)

    # 4. Replace unquoted keys with double-quoted keys: {key: or {, key: -> {"key":
    text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_\-\.]*)\s*:", r'\1"\2":', text)

    # 5. Replace single-quoted values with double quotes where safe (e.g. : 'val' -> : "val")
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
    # Also in arrays: ['foo', 'bar'] -> ["foo", "bar"]
    text = re.sub(r"(\[\s*|\,\s*)'([^']*)'", r'\1"\2"', text)

    # 6. Remove trailing commas before closing braces/brackets
    text = re.sub(r",\s*([\]}])", r"\1", text)

    # 6b. Replace unquoted Python literals True, False, None with true, false, null
    def _sub_literal(m: re.Match[str]) -> str:
        if m.group(1):
            return m.group(1)
        val = m.group(2)
        if val == "True":
            return "true"
        elif val == "False":
            return "false"
        elif val == "None":
            return "null"
        return m.group(0)

    text = re.sub(
        r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|\b(True|False|None)\b',
        _sub_literal,
        text,
    )

    # 7. Balance brackets and unclosed string quotes
    in_string = False
    escape = False
    stack: list[str] = []
    rebuilt_chars: list[str] = []

    for char in text:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            rebuilt_chars.append(char)
        else:
            if char == '"':
                in_string = True
                rebuilt_chars.append(char)
            elif char in ("{", "["):
                stack.append(char)
                rebuilt_chars.append(char)
            elif char == "}":
                if stack and stack[-1] == "{":
                    stack.pop()
                    rebuilt_chars.append(char)
            elif char == "]":
                if stack and stack[-1] == "[":
                    stack.pop()
                    rebuilt_chars.append(char)
            else:
                rebuilt_chars.append(char)

    if in_string:
        rebuilt_chars.append('"')

    while stack:
        open_bracket = stack.pop()
        if open_bracket == "{":
            rebuilt_chars.append("}")
        elif open_bracket == "[":
            rebuilt_chars.append("]")

    result = "".join(rebuilt_chars).strip()
    result = re.sub(r",\s*([\]}])", r"\1", result)
    return result


def parse_and_repair_llm_json(
    raw_text: str,
    response_model: type[T],
    fallback_factory: Callable[[], T] | None = None,
) -> T:
    """Parse and repair malformed LLM JSON string, validating against response_model.

    Handles:
    - Markdown code fences (```json ... ```)
    - Unbalanced brackets and braces ({ ... } and [ ... ])
    - Trailing commas in objects and arrays
    - Unquoted or single-quoted keys
    - Graceful fallback using fallback_factory without raising unhandled json.JSONDecodeError.
    """
    # 1. Quick try with standard parse
    try:
        return parse_and_validate(raw_text, response_model)
    except Exception:
        pass

    # 2. Repair candidate string
    repaired_text = repair_json_string(raw_text)

    try:
        clean_json = extract_json_str(repaired_text) or repaired_text
        if hasattr(response_model, "model_validate_json"):
            return response_model.model_validate_json(clean_json)

        from pydantic import TypeAdapter

        return TypeAdapter(response_model).validate_json(clean_json)
    except Exception as exc:
        logger.warning(
            "parse_and_repair_llm_json failed validation: %s (repaired: %s)",
            exc,
            repaired_text,
        )
        if fallback_factory is not None:
            try:
                return fallback_factory()
            except Exception as fb_err:
                logger.error("fallback_factory invocation failed: %s", fb_err)

        raise LLMStructuredOutputError(
            message=f"Failed to parse and repair LLM output for {getattr(response_model, '__name__', str(response_model))}: {exc}",
            raw_output=raw_text,
            details={"error": str(exc), "repaired": repaired_text},
        ) from None


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
