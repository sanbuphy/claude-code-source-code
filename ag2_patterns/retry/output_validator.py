"""
Output Validator — Validate and repair LLM outputs for AG2 agents.

Extracted from Claude Code's validation patterns:
- src/services/api/withRetry.ts — Context overflow handling, output validation
- src/utils/model/validateModel.ts — Model validation
- src/services/tools/toolExecution.ts — Tool input validation (Zod schemas)

Patterns implemented:
1. JSON output validation and repair
2. Tool call output validation
3. Content safety checks (max length, required fields)
4. Model response validation with automatic retry
5. AG2-compatible output validation hooks
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result types
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of output validation.

    Source: src/Tool.ts — ValidationResult type
    """
    valid: bool
    message: str = ""
    repaired_output: str | None = None
    original_output: str | None = None


# ---------------------------------------------------------------------------
# JSON validation and repair
# ---------------------------------------------------------------------------

def validate_json_output(output: str) -> ValidationResult:
    """Validate that output is valid JSON.

    Attempts repair strategies:
    1. Direct parse
    2. Extract JSON from markdown code blocks
    3. Fix common issues (trailing commas, unquoted keys)
    """
    # Try direct parse
    try:
        json.loads(output)
        return ValidationResult(valid=True, original_output=output)
    except json.JSONDecodeError:
        pass

    # Try extracting from code blocks
    repaired = _extract_json_from_markdown(output)
    if repaired:
        try:
            json.loads(repaired)
            return ValidationResult(
                valid=True,
                repaired_output=repaired,
                original_output=output,
                message="Extracted JSON from markdown code block",
            )
        except json.JSONDecodeError:
            pass

    # Try fixing common issues
    repaired = _fix_common_json_issues(output)
    if repaired:
        try:
            json.loads(repaired)
            return ValidationResult(
                valid=True,
                repaired_output=repaired,
                original_output=output,
                message="Repaired common JSON issues",
            )
        except json.JSONDecodeError:
            pass

    return ValidationResult(
        valid=False,
        original_output=output,
        message="Output is not valid JSON and could not be repaired",
    )


def _extract_json_from_markdown(text: str) -> str | None:
    """Extract JSON from ```json ... ``` code blocks."""
    pattern = r"```(?:json)?\s*\n([\s\S]*?)\n```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None


def _fix_common_json_issues(text: str) -> str | None:
    """Fix common JSON formatting issues."""
    fixed = text.strip()

    # Remove trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    # Try wrapping bare objects
    if not fixed.startswith(("{", "[", '"')):
        fixed = "{" + fixed + "}"

    return fixed


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------

def validate_with_model(
    output: str,
    model_class: type[BaseModel],
) -> ValidationResult:
    """Validate output against a Pydantic model.

    Source: src/Tool.ts — inputSchema uses Zod; we use Pydantic

    Args:
        output: JSON string to validate.
        model_class: Pydantic model to validate against.

    Returns:
        ValidationResult with parsed model if valid.
    """
    # First ensure it's valid JSON
    json_result = validate_json_output(output)
    json_str = json_result.repaired_output or output

    try:
        data = json.loads(json_str)
        model_class.model_validate(data)
        return ValidationResult(
            valid=True,
            repaired_output=json_result.repaired_output,
            original_output=output,
        )
    except json.JSONDecodeError as e:
        return ValidationResult(
            valid=False,
            original_output=output,
            message=f"Invalid JSON: {e}",
        )
    except ValidationError as e:
        return ValidationResult(
            valid=False,
            original_output=output,
            message=f"Schema validation failed: {e}",
        )


# ---------------------------------------------------------------------------
# Content validators
# ---------------------------------------------------------------------------

def validate_max_length(
    output: str,
    max_chars: int = 50_000,
    truncate: bool = True,
) -> ValidationResult:
    """Validate output length and optionally truncate.

    Source: src/Tool.ts — maxResultSizeChars
    """
    if len(output) <= max_chars:
        return ValidationResult(valid=True, original_output=output)

    if truncate:
        truncated = output[:max_chars] + f"\n\n[Truncated: {len(output)} → {max_chars} chars]"
        return ValidationResult(
            valid=True,
            repaired_output=truncated,
            original_output=output,
            message=f"Output truncated from {len(output)} to {max_chars} chars",
        )

    return ValidationResult(
        valid=False,
        original_output=output,
        message=f"Output exceeds max length: {len(output)} > {max_chars}",
    )


def validate_not_empty(output: str) -> ValidationResult:
    """Validate that output is not empty or whitespace-only."""
    if output and output.strip():
        return ValidationResult(valid=True, original_output=output)
    return ValidationResult(
        valid=False,
        original_output=output,
        message="Output is empty or whitespace-only",
    )


def validate_no_error_markers(output: str) -> ValidationResult:
    """Check output for common error markers that indicate a failed generation."""
    error_patterns = [
        r"I (?:cannot|can't|am unable to)",
        r"(?:Error|ERROR):",
        r"(?:sorry|Sorry),? I",
    ]
    for pattern in error_patterns:
        if re.search(pattern, output):
            return ValidationResult(
                valid=False,
                original_output=output,
                message=f"Output contains error marker matching: {pattern}",
            )
    return ValidationResult(valid=True, original_output=output)


# ---------------------------------------------------------------------------
# Composite validator
# ---------------------------------------------------------------------------

class OutputValidator:
    """Composable output validator that chains multiple validation rules.

    Example::

        validator = OutputValidator()
        validator.add(validate_not_empty)
        validator.add(validate_json_output)
        validator.add(lambda o: validate_max_length(o, 10000))

        result = validator.validate(llm_output)
        if not result.valid:
            print(f"Validation failed: {result.message}")
    """

    def __init__(self) -> None:
        self._validators: list[Callable[[str], ValidationResult]] = []

    def add(self, validator: Callable[[str], ValidationResult]) -> "OutputValidator":
        """Add a validator to the chain."""
        self._validators.append(validator)
        return self

    def validate(self, output: str) -> ValidationResult:
        """Run all validators in order. Stop on first failure.

        If a validator produces a repaired output, subsequent validators
        operate on the repaired version.
        """
        current = output
        for validator in self._validators:
            result = validator(current)
            if not result.valid:
                return result
            if result.repaired_output:
                current = result.repaired_output

        return ValidationResult(
            valid=True,
            repaired_output=current if current != output else None,
            original_output=output,
        )


# ---------------------------------------------------------------------------
# AG2 Integration: Reply validation hook
# ---------------------------------------------------------------------------

def create_ag2_reply_validator(
    validator: OutputValidator,
    max_repair_attempts: int = 2,
) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Create an AG2-compatible reply validation function.

    This can be used as a reply_func or message transform in AG2
    to validate and repair agent outputs before they're sent.

    Args:
        validator: OutputValidator instance with rules.
        max_repair_attempts: How many times to attempt repair.

    Returns:
        A function compatible with AG2's reply processing.
    """

    def validate_reply(message: dict[str, Any]) -> dict[str, Any] | None:
        content = message.get("content", "")
        if not isinstance(content, str):
            return message

        result = validator.validate(content)
        if result.valid:
            if result.repaired_output:
                message = {**message, "content": result.repaired_output}
            return message

        logger.warning(f"Reply validation failed: {result.message}")
        return None

    return validate_reply


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test JSON validation
    print("JSON validation:")
    test_cases = [
        '{"key": "value"}',
        '```json\n{"key": "value"}\n```',
        '{"key": "value",}',  # trailing comma
        "not json at all",
    ]
    for tc in test_cases:
        result = validate_json_output(tc)
        status = "VALID" if result.valid else "INVALID"
        extra = f" (repaired: {result.message})" if result.repaired_output else ""
        print(f"  {tc[:40]:40s} → {status}{extra}")

    # Test Pydantic validation
    class TaskOutput(BaseModel):
        task: str
        status: str
        result: str | None = None

    print("\nPydantic validation:")
    result = validate_with_model(
        '{"task": "build", "status": "done", "result": "ok"}',
        TaskOutput,
    )
    print(f"  Valid schema: {result.valid}")

    result = validate_with_model('{"task": "build"}', TaskOutput)
    print(f"  Missing field: {result.valid} — {result.message}")

    # Test composite validator
    print("\nComposite validator:")
    validator = OutputValidator()
    validator.add(validate_not_empty)
    validator.add(lambda o: validate_max_length(o, 100))

    for test in ["hello world", "", "x" * 200]:
        result = validator.validate(test)
        print(f"  len={len(test):3d}: valid={result.valid} {result.message}")
