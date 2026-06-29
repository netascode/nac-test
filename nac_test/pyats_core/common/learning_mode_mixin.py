# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Learning mode mixin for operational test classes.

Provides the contract for tests that support a two-phase workflow:
1. Learn mode (--learn): capture live state and save as baseline
2. Verify mode (default): compare live state against captured baseline

Tests opt in by inheriting LearningModeMixin and implementing
capture_learned_state(). The base class orchestration checks for
SUPPORTS_LEARNING and the NAC_TEST_LEARN env var to route execution.

Usage:
    class VerifyBGPRoutes(LearningModeMixin, IOSXETestBase):
        SUPPORTS_LEARNING = True

        async def capture_learned_state(self, semaphore, client, items):
            # Query live state and return structured data
            return {"sdwan": {"sites": [...]}}

        def get_items_to_verify(self):
            # Same as normal — extract what to check
            ...

        async def verify_item(self, semaphore, client, context):
            # Normal verification against data model (which now includes learned state)
            ...
"""

import os
from pathlib import Path
from typing import Any

from pyats import aetest


class LearningModeMixin(aetest.Testcase):  # type: ignore[misc]
    """Mixin adding learning mode support to operational test classes.

    Inherits from aetest.Testcase so that PyATS's TestableMeta metaclass
    processes this class correctly (methods get the required .source attribute).
    Python's MRO ensures aetest.Testcase appears only once when combined with
    other base classes that also inherit from it.

    Tests that support learning inherit this mixin and override
    capture_learned_state(). The framework detects learn mode via
    the NAC_TEST_LEARN environment variable and calls the capture
    method instead of the normal verify loop.

    Usage:
        class MyTest(LearningModeMixin, SDWANManagerTestBase):
            async def capture_learned_state(self, semaphore, client, items):
                ...

    Attributes:
        SUPPORTS_LEARNING: Class-level flag indicating this test supports
            the --learn mode. Set to True in subclasses that implement
            capture_learned_state().
    """

    SUPPORTS_LEARNING: bool = True

    @property
    def is_learn_mode(self) -> bool:
        """Check if running in learning mode.

        Returns:
            True if NAC_TEST_LEARN environment variable is set and truthy.
        """
        return bool(os.environ.get("NAC_TEST_LEARN"))

    @property
    def learned_state_dir(self) -> Path:
        """Get the output directory for learned state files.

        Returns:
            Path from NAC_TEST_LEARNED_STATE_DIR env var, or 'learned_state'
            as fallback.
        """
        return Path(os.environ.get("NAC_TEST_LEARNED_STATE_DIR", "learned_state"))

    async def capture_learned_state(
        self,
        semaphore: Any,
        client: Any,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Capture live state for all items. Override in subclass.

        Called in learning mode instead of the normal verify_item() loop.
        The implementation should make the same queries as verify_item() but
        return the raw captured state rather than a pass/fail verdict.

        The returned dict should be structured so it merges cleanly into the
        data model when loaded via -d (using nac_yaml's merge_dict logic).

        Args:
            semaphore: Asyncio semaphore for concurrency control.
            client: HTTP client or SSH connection (same as verify_item receives).
            items: List of context dicts from get_items_to_verify().

        Returns:
            Dictionary containing captured state, structured for data model merge.

        Raises:
            NotImplementedError: If subclass doesn't override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} has SUPPORTS_LEARNING=True but does not "
            f"implement capture_learned_state(). Override this method to define "
            f"what state to capture in learning mode."
        )
