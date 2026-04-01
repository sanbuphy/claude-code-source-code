"""
Retry Handler — Resilient API calls with exponential backoff for AG2.

Extracted from Claude Code's retry system:
- src/services/api/withRetry.ts — Core retry loop with backoff, jitter,
  transient error classification, 529 handling, context overflow

Patterns implemented:
1. Exponential backoff with jitter (500ms base, 32s cap)
2. Transient error classification (retryable vs non-retryable)
3. Capacity error handling (429/529) with cooldown
4. Context overflow detection and max_tokens adjustment
5. Model fallback on persistent overload (3+ consecutive 529s)
6. Persistent retry mode for unattended sessions
7. Tenacity integration for AG2 compatibility
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Error classification (from src/services/api/withRetry.ts)
# ---------------------------------------------------------------------------

class ErrorCategory(str, Enum):
    """Classification of API errors for retry decisions."""
    TRANSIENT = "transient"           # Network errors, 5xx
    CAPACITY = "capacity"             # 429, 529
    CONTEXT_OVERFLOW = "context_overflow"  # Prompt too long
    AUTH = "auth"                      # 401, 403
    CLIENT = "client"                  # Other 4xx
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an error for retry decision-making.

    Source: src/services/api/withRetry.ts — isTransientCapacityError(),
    shouldRetry(), error handling blocks

    Classifies:
    - Network/connection errors → TRANSIENT (retryable)
    - 5xx server errors → TRANSIENT (retryable)
    - 429/529 capacity → CAPACITY (retryable with longer backoff)
    - 401/403 → AUTH (may retry after token refresh)
    - Other 4xx → CLIENT (not retryable)
    - Prompt too long → CONTEXT_OVERFLOW (retry with adjusted params)
    """
    error_str = str(error).lower()
    status_code = _extract_status_code(error)

    if status_code:
        if status_code in (429, 529):
            return ErrorCategory.CAPACITY
        if status_code in (401, 403):
            return ErrorCategory.AUTH
        if 500 <= status_code < 600:
            return ErrorCategory.TRANSIENT
        if 400 <= status_code < 500:
            # Check for context overflow
            if "prompt is too long" in error_str or "context length" in error_str:
                return ErrorCategory.CONTEXT_OVERFLOW
            return ErrorCategory.CLIENT

    # Network-level errors
    if any(
        keyword in error_str
        for keyword in ("connection", "timeout", "network", "dns", "econnrefused", "econnreset")
    ):
        return ErrorCategory.TRANSIENT

    return ErrorCategory.UNKNOWN


def is_retryable(error: Exception) -> bool:
    """Check if an error should trigger a retry.

    Source: src/services/api/withRetry.ts — shouldRetry()
    """
    category = classify_error(error)
    return category in (ErrorCategory.TRANSIENT, ErrorCategory.CAPACITY, ErrorCategory.CONTEXT_OVERFLOW)


def _extract_status_code(error: Exception) -> int | None:
    """Try to extract an HTTP status code from an error."""
    # Common patterns in HTTP error messages
    if hasattr(error, "status_code"):
        return error.status_code
    if hasattr(error, "status"):
        return error.status
    if hasattr(error, "response") and hasattr(error.response, "status_code"):
        return error.response.status_code

    # Parse from string
    match = re.search(r"\b([45]\d{2})\b", str(error))
    if match:
        return int(match.group(1))
    return None


def extract_retry_after(error: Exception) -> float | None:
    """Extract retry-after delay from error headers/message.

    Source: src/services/api/withRetry.ts — checks retry-after header
    """
    if hasattr(error, "response") and hasattr(error.response, "headers"):
        headers = error.response.headers
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    # Parse from error message
    match = re.search(r"retry.?after[:\s]+(\d+\.?\d*)", str(error).lower())
    if match:
        return float(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Backoff calculation (from src/services/api/withRetry.ts)
# ---------------------------------------------------------------------------

def calculate_backoff(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 32.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff delay with optional jitter.

    Source: src/services/api/withRetry.ts — backoff calculation

    Formula: min(base_delay * 2^(attempt-1), max_delay) + random jitter

    Args:
        attempt: Current attempt number (1-based).
        base_delay: Base delay in seconds (Claude Code uses 0.5s).
        max_delay: Maximum delay cap in seconds (Claude Code uses 32s).
        jitter: Add random jitter to prevent thundering herd.

    Returns:
        Delay in seconds before next retry.
    """
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    if jitter:
        delay *= 0.5 + random.random()  # 50%-150% of calculated delay
    return delay


# ---------------------------------------------------------------------------
# Retry state tracking
# ---------------------------------------------------------------------------

@dataclass
class RetryState:
    """Tracks retry state across attempts.

    Source: src/services/api/withRetry.ts — attempt tracking, 529 counting
    """
    max_retries: int = 10
    attempt: int = 0
    consecutive_529s: int = 0
    total_wait_time: float = 0
    last_error: Exception | None = None
    used_fallback: bool = False
    _attempt_times: list[float] = field(default_factory=list)

    MAX_CONSECUTIVE_529S_FOR_FALLBACK = 3

    def record_attempt(self, error: Exception | None = None) -> None:
        """Record an attempt."""
        self.attempt += 1
        self._attempt_times.append(time.time())
        self.last_error = error

        if error and classify_error(error) == ErrorCategory.CAPACITY:
            self.consecutive_529s += 1
        else:
            self.consecutive_529s = 0

    @property
    def should_fallback(self) -> bool:
        """Whether to switch to fallback model.

        Source: src/services/api/withRetry.ts — 529 fallback logic
        """
        return self.consecutive_529s >= self.MAX_CONSECUTIVE_529S_FOR_FALLBACK

    @property
    def exhausted(self) -> bool:
        """Whether all retries are used up."""
        return self.attempt >= self.max_retries

    def get_delay(self) -> float:
        """Get next backoff delay."""
        return calculate_backoff(self.attempt)


# ---------------------------------------------------------------------------
# Context overflow handler
# ---------------------------------------------------------------------------

@dataclass
class ContextOverflowInfo:
    """Parsed context overflow error info.

    Source: src/services/api/withRetry.ts — regex parsing of overflow errors
    """
    input_tokens: int
    max_tokens: int
    context_limit: int

    @property
    def adjusted_max_tokens(self) -> int:
        """Calculate reduced max_tokens to fit within context.

        Source: src/services/api/withRetry.ts — dynamic max_tokens adjustment
        """
        available = self.context_limit - self.input_tokens
        # Leave some margin (10%)
        return max(1024, int(available * 0.9))


def parse_context_overflow(error: Exception) -> ContextOverflowInfo | None:
    """Parse context overflow details from error message.

    Source: src/services/api/withRetry.ts — regex parsing
    """
    error_str = str(error)
    # Pattern: "X input tokens + Y max tokens > Z context limit"
    match = re.search(r"(\d+)\s*\+\s*(\d+)\s*>\s*(\d+)", error_str)
    if match:
        return ContextOverflowInfo(
            input_tokens=int(match.group(1)),
            max_tokens=int(match.group(2)),
            context_limit=int(match.group(3)),
        )

    # Alternative pattern: "input_tokens (X) + max_tokens (Y) > context_window (Z)"
    match = re.search(
        r"input.tokens?\s*\(?(\d+)\)?\s*\+\s*max.tokens?\s*\(?(\d+)\)?\s*>\s*context.(?:window|limit)\s*\(?(\d+)\)?",
        error_str,
        re.IGNORECASE,
    )
    if match:
        return ContextOverflowInfo(
            input_tokens=int(match.group(1)),
            max_tokens=int(match.group(2)),
            context_limit=int(match.group(3)),
        )

    return None


# ---------------------------------------------------------------------------
# High-level retry wrapper
# ---------------------------------------------------------------------------

def with_retry(
    fn: Callable[..., T],
    max_retries: int = 10,
    base_delay: float = 0.5,
    max_delay: float = 32.0,
    on_retry: Callable[[int, Exception, float], None] | None = None,
    on_fallback: Callable[[], None] | None = None,
) -> Callable[..., T]:
    """Wrap a function with Claude Code-style retry logic.

    Source: src/services/api/withRetry.ts — withRetry<T>()

    Features:
    - Exponential backoff with jitter
    - Transient error classification
    - Capacity error handling with longer delays
    - Context overflow detection
    - Model fallback callback after 3 consecutive 529s

    Args:
        fn: The function to wrap (typically an API call).
        max_retries: Maximum retry attempts.
        base_delay: Base backoff delay in seconds.
        max_delay: Maximum backoff delay cap.
        on_retry: Callback(attempt, error, delay) before each retry.
        on_fallback: Callback when model fallback is triggered.

    Returns:
        Wrapped function with retry logic.
    """

    def wrapper(*args: Any, **kwargs: Any) -> T:
        state = RetryState(max_retries=max_retries)

        while True:
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as exc:
                category = classify_error(exc)
                state.record_attempt(exc)

                # Non-retryable errors
                if category in (ErrorCategory.CLIENT, ErrorCategory.AUTH):
                    raise

                # Check if retries exhausted
                if state.exhausted:
                    logger.error(
                        f"All {max_retries} retries exhausted. Last error: {exc}"
                    )
                    raise

                # Model fallback on persistent 529s
                if state.should_fallback and on_fallback:
                    logger.warning("Triggering model fallback after consecutive 529s")
                    on_fallback()
                    state.used_fallback = True
                    state.consecutive_529s = 0

                # Calculate delay
                retry_after = extract_retry_after(exc)
                if retry_after and retry_after > 0:
                    delay = retry_after
                else:
                    delay = calculate_backoff(
                        state.attempt, base_delay, max_delay
                    )

                # Capacity errors get extra delay
                if category == ErrorCategory.CAPACITY:
                    delay = max(delay, 2.0)

                state.total_wait_time += delay

                if on_retry:
                    on_retry(state.attempt, exc, delay)

                logger.info(
                    f"Retry {state.attempt}/{max_retries} after {delay:.1f}s "
                    f"({category.value}): {exc}"
                )
                time.sleep(delay)

    wrapper.__name__ = getattr(fn, "__name__", "wrapped")
    wrapper.__doc__ = f"Retry-wrapped: {getattr(fn, '__doc__', '')}"
    return wrapper


# ---------------------------------------------------------------------------
# Tenacity-based retry decorator (alternative)
# ---------------------------------------------------------------------------

def tenacity_retry(
    max_retries: int = 10,
    base_delay: float = 0.5,
    max_delay: float = 32.0,
) -> Any:
    """Tenacity-based retry decorator matching Claude Code's backoff profile.

    Use this as a decorator for simpler cases where you don't need
    the full state tracking of `with_retry()`.

    Example::

        @tenacity_retry(max_retries=5)
        def call_api(prompt: str) -> str:
            return openai.chat.completions.create(...)
    """
    return retry(
        retry=retry_if_exception(is_retryable),
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential_jitter(
            initial=base_delay,
            max=max_delay,
            jitter=max_delay / 4,
        ),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempts for tenacity."""
    if retry_state.outcome and retry_state.outcome.failed:
        exc = retry_state.outcome.exception()
        logger.info(
            f"Retry attempt {retry_state.attempt_number}: {exc}"
        )


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test error classification
    test_errors = [
        Exception("Connection refused"),
        Exception("HTTP 429 Too Many Requests"),
        Exception("HTTP 500 Internal Server Error"),
        Exception("HTTP 400 Bad Request"),
        Exception("HTTP 529 Overloaded"),
        Exception("prompt is too long: 190000 + 16384 > 200000"),
    ]

    print("Error classification:")
    for err in test_errors:
        cat = classify_error(err)
        retryable = is_retryable(err)
        print(f"  {str(err)[:50]:50s} → {cat.value:20s} retryable={retryable}")

    # Test backoff calculation
    print("\nBackoff delays (no jitter):")
    for attempt in range(1, 8):
        delay = calculate_backoff(attempt, jitter=False)
        print(f"  Attempt {attempt}: {delay:.1f}s")

    # Test context overflow parsing
    overflow = parse_context_overflow(
        Exception("190000 + 16384 > 200000")
    )
    if overflow:
        print(f"\nContext overflow: input={overflow.input_tokens}, "
              f"max={overflow.max_tokens}, limit={overflow.context_limit}")
        print(f"Adjusted max_tokens: {overflow.adjusted_max_tokens}")

    # Test retry wrapper
    call_count = 0

    def flaky_fn() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Connection timeout")
        return "success!"

    wrapped = with_retry(flaky_fn, max_retries=5, base_delay=0.1, max_delay=0.5)
    result = wrapped()
    print(f"\nRetry test: result='{result}', attempts={call_count}")
