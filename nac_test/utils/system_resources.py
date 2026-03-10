# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""System resource calculation utilities for nac-test."""

import logging
import multiprocessing as mp
import os
import resource

import psutil

logger = logging.getLogger(__name__)


class SystemResourceCalculator:
    """Shared system resource calculation utilities."""

    @staticmethod
    def get_memory_info() -> dict[str, int]:
        """Get current memory information.

        Returns:
            Dictionary containing memory info in bytes:
            - available: Available memory
            - total: Total memory
            - used: Used memory
        """
        try:
            memory = psutil.virtual_memory()
            return {
                "available": memory.available,
                "total": memory.total,
                "used": memory.used,
            }
        except Exception as e:
            logger.warning(f"Could not get memory info: {e}")
            # Return conservative fallback values (8GB available)
            return {
                "available": 8 * 1024 * 1024 * 1024,  # 8GB
                "total": 16 * 1024 * 1024 * 1024,  # 16GB
                "used": 8 * 1024 * 1024 * 1024,  # 8GB
            }

    @staticmethod
    def get_file_descriptor_limits() -> dict[str, int]:
        """Get current file descriptor limits.

        Returns:
            Dictionary containing FD limits:
            - soft: Soft limit
            - hard: Hard limit
            - safe: Safe limit (70% of soft)
        """
        try:
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            safe_limit = int(soft_limit * 0.7)
            return {"soft": soft_limit, "hard": hard_limit, "safe": safe_limit}
        except (OSError, ValueError) as e:
            logger.warning(f"Could not get file descriptor limits: {e}")
            # Return conservative fallback
            return {
                "soft": 1024,
                "hard": 4096,
                "safe": 716,  # 70% of 1024
            }

    @staticmethod
    def calculate_worker_capacity(
        memory_per_worker_gb: float = 2.0,
        cpu_multiplier: float = 2.0,
        max_workers: int = 50,
        env_var: str = "NAC_TEST_PYATS_PROCESSES",
    ) -> int:
        """Calculate optimal worker count based on system resources.

        Args:
            memory_per_worker_gb: Memory per worker in GB
            cpu_multiplier: CPU multiplier factor
            max_workers: Maximum allowed workers
            env_var: Environment variable for override

        Returns:
            Optimal number of workers
        """
        # CPU-based calculation
        cpu_count = mp.cpu_count() or 4
        cpu_workers = int(cpu_count * cpu_multiplier)

        # Memory-based calculation
        memory_info = SystemResourceCalculator.get_memory_info()
        memory_per_worker_bytes = memory_per_worker_gb * 1024 * 1024 * 1024
        memory_workers = int(memory_info["available"] / memory_per_worker_bytes)

        # Consider system load
        try:
            load_avg = os.getloadavg()[0]  # 1-minute load average
            if load_avg > cpu_count:
                cpu_workers = max(1, int(cpu_workers * 0.5))
        except (OSError, AttributeError):
            # getloadavg not available on all systems
            pass

        # Use the more conservative limit
        calculated = max(1, min(cpu_workers, memory_workers, max_workers))

        # Allow environment variable override
        if env_var and os.environ.get(env_var):
            try:
                override = int(os.environ[env_var])
                logger.info(f"Using {env_var} environment override: {override}")
                return override
            except ValueError:
                logger.warning(f"Invalid {env_var} value: {os.environ[env_var]}")

        return calculated

    @staticmethod
    def calculate_connection_capacity(
        memory_per_connection_mb: float = 10.0,
        fds_per_connection: int = 5,
        max_connections: int = 1000,
        env_var: str = "NAC_TEST_PYATS_MAX_CONNECTIONS",
    ) -> int:
        """Calculate optimal connection count based on system resources.

        Args:
            memory_per_connection_mb: Memory per connection in MB
            fds_per_connection: File descriptors per connection
            max_connections: Maximum allowed connections
            env_var: Environment variable for override

        Returns:
            Optimal number of connections
        """
        # File descriptor-based calculation
        fd_limits = SystemResourceCalculator.get_file_descriptor_limits()
        max_connections_from_fds = fd_limits["safe"] // fds_per_connection

        # Memory-based calculation
        memory_info = SystemResourceCalculator.get_memory_info()
        memory_per_connection_bytes = int(memory_per_connection_mb * 1024 * 1024)
        max_connections_from_memory = (
            memory_info["available"] // memory_per_connection_bytes
        )

        # Use the more conservative limit
        calculated = max(
            1,
            min(max_connections_from_fds, max_connections_from_memory, max_connections),
        )

        # Allow environment variable override
        if env_var and os.environ.get(env_var):
            try:
                override = int(os.environ[env_var])
                logger.info(f"Using {env_var} environment override: {override}")
                return override
            except ValueError:
                logger.warning(f"Invalid {env_var} value: {os.environ[env_var]}")

        return calculated
