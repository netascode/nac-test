# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Asyncio utilities for cross-version compatibility.

This module provides utilities to handle differences in asyncio behavior
across Python versions, particularly for Python 3.10-3.12+ compatibility.
"""

import asyncio


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create an event loop in a Python 3.10+ compatible way.

    In Python 3.12+, get_event_loop() raises RuntimeError if there's no
    current event loop in the main thread. In older versions (3.10-3.11),
    it automatically creates one. This helper function works across all
    supported versions by handling both behaviors.

    The function will:
    1. Try to get the existing event loop
    2. If the loop is closed, create a new one and set it
    3. If RuntimeError is raised (Python 3.12+), create a new loop and set it

    Returns:
        An asyncio event loop that is ready to use

    Example:
        >>> loop = get_or_create_event_loop()
        >>> result = loop.run_until_complete(my_async_function())
    """
    try:
        loop = asyncio.get_event_loop()
        # Check if the loop is closed (can happen in some scenarios)
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # Python 3.12+: no current event loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop
