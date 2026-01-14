"""Command cache implementation for SSH device testing.

This module provides per-device command output caching to eliminate redundant
command execution when multiple tests need the same show command outputs.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class CommandCache:
    """Per-device command output cache with TTL support.

    This class provides caching functionality for command outputs on a per-device
    basis. It helps eliminate redundant command execution when multiple tests
    need the same show command outputs from a device.

    The cache uses a time-to-live (TTL) mechanism to ensure data freshness,
    automatically expiring entries after a configured time period.
    """

    def __init__(self, hostname: str, ttl: int = 3600):
        """Initialize command cache for a specific device.

        Args:
            hostname: Unique identifier for the device
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        self.hostname = hostname
        self.ttl = ttl
        self.cache: dict[str, dict[str, Any]] = {}  # command -> {output, timestamp}

        logger.debug(f"Initialized command cache for device {hostname} with TTL {ttl}s")

    def get(self, command: str) -> str | None:
        """Get cached command output if valid.

        Args:
            command: The command to retrieve from cache

        Returns:
            Cached command output if valid, None if not cached or expired
        """
        if command in self.cache:
            entry = self.cache[command]
            if time.time() - entry["timestamp"] < self.ttl:
                logger.debug(f"Cache hit for '{command}' on {self.hostname}")
                return str(entry["output"])
            else:
                # Entry has expired, remove it
                del self.cache[command]
                logger.debug(f"Cache expired for '{command}' on {self.hostname}")

        return None

    def set(self, command: str, output: str) -> None:
        """Cache command output with current timestamp.

        Args:
            command: The command that was executed
            output: The command output to cache
        """
        self.cache[command] = {"output": output, "timestamp": time.time()}
        logger.debug(
            f"Cached '{command}' output for {self.hostname} ({len(output)} chars)"
        )

    def clear(self) -> None:
        """Clear all cached entries for this device."""
        entry_count = len(self.cache)
        self.cache.clear()
        logger.debug(f"Cleared {entry_count} cached entries for {self.hostname}")

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary containing cache statistics:
                - total_entries: Total number of cached entries
                - expired_entries: Number of expired entries
                - valid_entries: Number of valid entries
        """
        current_time = time.time()
        expired_count = 0
        valid_count = 0

        for entry in self.cache.values():
            if current_time - entry["timestamp"] >= self.ttl:
                expired_count += 1
            else:
                valid_count += 1

        return {
            "total_entries": len(self.cache),
            "expired_entries": expired_count,
            "valid_entries": valid_count,
        }
