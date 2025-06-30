# -*- coding: utf-8 -*-

"""Generic base test class for all architectures."""

from pyats import aetest
import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, TypeVar, Callable, Awaitable

from nac_test.pyats.common.connection_pool import ConnectionPool
from nac_test.pyats.common.retry_strategy import SmartRetry

T = TypeVar("T")


class NACTestBase(aetest.Testcase):
    """Generic base class with common functionality for all architectures"""

    @aetest.setup
    def setup(self) -> None:
        """Common setup for all tests"""
        # Configure test-specific logger
        self.logger = logging.getLogger(self.__class__.__module__)

        # Only show test logs in debug mode
        if not os.environ.get("PYATS_DEBUG"):
            self.logger.setLevel(logging.ERROR)

        # Load merged data model created by nac-test
        self.data_model = self.load_data_model()

        # Get controller details from environment
        self.controller_type = os.environ.get("CONTROLLER_TYPE", "ACI")
        self.controller_url = os.environ[f"{self.controller_type}_URL"]
        self.username = os.environ[f"{self.controller_type}_USERNAME"]
        self.password = os.environ[f"{self.controller_type}_PASSWORD"]

        # Connection pool is shared within process
        self.pool = ConnectionPool()

    def load_data_model(self) -> Dict[str, Any]:
        """Load the merged data model from the test environment.

        Returns:
            Merged data model dictionary
        """
        data_file = Path(os.environ.get("DATA_FILE", "merged_data_model.yaml"))
        with open(data_file, "r") as f:
            data = yaml.safe_load(f)
            # Ensure we always return a dict
            return data if isinstance(data, dict) else {}

    async def api_call_with_retry(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Standard API call with retry logic

        Args:
            func: Async function to execute with retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution
        """
        return await SmartRetry.execute(func, *args, **kwargs)

    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for the specific architecture.

        Must be implemented by subclasses to return architecture-specific
        connection details.
        """
        raise NotImplementedError(
            "Subclasses must implement get_connection_params() method"
        )
