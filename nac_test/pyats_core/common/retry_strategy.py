"""Generic smart retry strategy with exponential backoff."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

from nac_test.pyats_core.constants import (
    RETRY_EXPONENTIAL_BASE,
    RETRY_INITIAL_DELAY,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
)

logger = logging.getLogger(__name__)

# Define transient exceptions
TRANSIENT_EXCEPTIONS = (
    httpx.HTTPError,
    asyncio.TimeoutError,
    ConnectionError,
)

# Type variable for generic return type
T = TypeVar("T")


class SmartRetry:
    """Context-aware retry strategy with exponential backoff"""

    HTTP_RETRY_CODES = {429, 502, 503, 504}

    @staticmethod
    async def execute(
        func: Callable[..., Awaitable[T]],
        *args: Any,
        max_attempts: int = RETRY_MAX_ATTEMPTS,
        initial_delay: float = RETRY_INITIAL_DELAY,
        max_delay: float = RETRY_MAX_DELAY,
        backoff_factor: float = RETRY_EXPONENTIAL_BASE,
        **kwargs: Any,
    ) -> T:
        """Execute function with smart retry logic

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            max_attempts: Override default max attempts
            initial_delay: Override default initial delay
            max_delay: Override default max delay
            backoff_factor: Override default backoff factor
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            Last exception encountered after all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)

            except httpx.HTTPStatusError as e:
                if e.response.status_code not in SmartRetry.HTTP_RETRY_CODES:
                    raise  # Don't retry client errors (4xx except 429)
                last_exception = e

                # Handle rate limiting specially
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 2**attempt))
                    await asyncio.sleep(retry_after)
                    continue

            except TRANSIENT_EXCEPTIONS as e:
                last_exception = e
                logger.warning(f"Transient failure on attempt {attempt + 1}: {e}")

            if attempt < max_attempts - 1:
                # Exponential backoff with jitter
                delay = min(
                    initial_delay * (backoff_factor**attempt),
                    max_delay,
                )

                # Add jitter to prevent thundering herd
                delay *= 0.5 + random.random()

                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Unexpected error in retry logic")
