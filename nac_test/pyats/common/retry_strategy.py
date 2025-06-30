# -*- coding: utf-8 -*-

"""Generic smart retry strategy with exponential backoff."""

import asyncio
import random
import httpx
import logging
from typing import Any, Callable, TypeVar, Optional, Awaitable

from nac_test.pyats.constants import (
    RETRY_MAX_ATTEMPTS,
    RETRY_INITIAL_DELAY,
    RETRY_MAX_DELAY,
    RETRY_EXPONENTIAL_BASE,
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

    @classmethod
    async def execute(
        cls,
        func: Callable[..., Awaitable[T]],
        *args,
        max_attempts: Optional[int] = None,
        **kwargs,
    ) -> T:
        """Execute function with smart retry logic

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            max_attempts: Override default max attempts
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            Last exception encountered after all retries exhausted
        """
        if max_attempts is None:
            max_attempts = RETRY_MAX_ATTEMPTS

        last_exception: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)

            except httpx.HTTPStatusError as e:
                if e.response.status_code not in cls.HTTP_RETRY_CODES:
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
                    RETRY_INITIAL_DELAY * (RETRY_EXPONENTIAL_BASE**attempt),
                    RETRY_MAX_DELAY,
                )

                # Add jitter to prevent thundering herd
                delay *= 0.5 + random.random()

                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Unexpected error in retry logic")
