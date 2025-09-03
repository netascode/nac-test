# -*- coding: utf-8 -*-

"""Step interceptor for PyATS reporter message batching.

This module intercepts PyATS Step execution to buffer reporter messages
instead of sending them immediately. This prevents the reporter server
from being overwhelmed when tests create thousands of steps.

The interceptor:
    - Wraps Step.__enter__ and __exit__ methods
    - Buffers messages in BatchingReporter
    - Maintains step context hierarchy
    - Provides fallback to original behavior on errors
"""

import os
import logging
from typing import Any, Callable, Dict, Optional, Type
from functools import wraps
from types import TracebackType

from pyats.aetest.steps.implementation import Step
from nac_test.pyats_core.reporting.batching_reporter import BatchingReporter

logger = logging.getLogger(__name__)

# Module-level variables for global state
# These are set by NACTestBase during setup
batching_reporter: Optional[BatchingReporter] = None
interception_enabled: bool = False
interception_error_count: int = 0
MAX_INTERCEPTION_ERRORS: int = 10


class StepInterceptor:
    """Intercepts PyATS Step execution for message batching.

    This class provides methods to wrap PyATS Step.__enter__ and __exit__
    to intercept reporter messages and buffer them instead of sending
    immediately.
    """

    def __init__(self, batching_reporter: BatchingReporter):
        """Initialize the step interceptor.

        Args:
            batching_reporter: The BatchingReporter instance to buffer messages to
        """
        self.batching_reporter = batching_reporter
        self.enabled = True  # Can be disabled for fallback
        self.intercepted_count = 0
        self.error_count = 0

        # Store original methods (will be set when installing interceptors)
        self.original_enter: Optional[Callable[..., Any]] = None
        self.original_exit: Optional[Callable[..., Any]] = None

        logger.debug("StepInterceptor initialized")

    def is_batching_enabled(self) -> bool:
        """Check if batching is enabled via environment variable.

        Returns:
            True if batching should be used, False for original behavior
        """
        # Check environment variable
        env_enabled = (
            os.environ.get("NAC_TEST_BATCHING_REPORTER", "false").lower() == "true"
        )

        # Also check our internal enabled flag (for fallback scenarios)
        return env_enabled and self.enabled

    def wrap_step_enter(self, original_enter: Callable[..., Any]) -> Callable[..., Any]:
        """Create wrapper for Step.__enter__ method.

        This wrapper intercepts the step start and buffers the message
        instead of sending it immediately through the reporter.

        Args:
            original_enter: The original Step.__enter__ method

        Returns:
            Wrapped version of __enter__ that buffers messages
        """

        @wraps(original_enter)
        def wrapped_enter(step_self: Step) -> Any:
            """Wrapped __enter__ that intercepts step start."""

            # Check if we should intercept
            if not self.is_batching_enabled():
                # Batching disabled, use original behavior
                return original_enter(step_self)

            try:
                # Extract step information for buffering
                step_info = {
                    "name": str(step_self),  # Step name/description
                    "uid": getattr(step_self, "uid", None),
                    "source": getattr(step_self, "source", None),
                    "parent": getattr(step_self, "parent", None),
                }

                # Build context path for hierarchy preservation
                context_path = self._build_context_path(step_self)

                # Buffer the step start message
                self.batching_reporter.buffer_message(
                    message_type="step_start",
                    message_content=step_info,
                    context_path=context_path,
                )

                self.intercepted_count += 1

                # Temporarily disable the reporter to prevent duplicate messages
                # Store the original reporter so we can restore it in __exit__
                if hasattr(step_self, "reporter"):
                    step_self._original_reporter = step_self.reporter
                    # Create a dummy reporter that does nothing
                    step_self.reporter = DummyReporter()

                # Call the original __enter__ (with dummy reporter)
                result = original_enter(step_self)

                # Log interception (only in debug mode to avoid spam)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Intercepted step start: %s (context: %s)",
                        step_info["name"],
                        context_path,
                    )

                return result

            except Exception as e:
                # On any error, fall back to original behavior
                logger.error("Failed to intercept step start: %s", e)
                self.error_count += 1

                # CRITICAL FIX: Do NOT restore the original reporter on error!
                # Same issue as in wrapped_exit - restoring the reporter here would
                # allow direct communication with PyATS reporter server.
                # Better to keep DummyReporter active as a safety mechanism.
                # This ensures even error paths don't overwhelm the reporter server.
                #
                # if hasattr(step_self, '_original_reporter'):
                #     step_self.reporter = step_self._original_reporter
                #     delattr(step_self, '_original_reporter')

                # Use original behavior
                return original_enter(step_self)

        # Store reference to original for potential restoration
        self.original_enter = original_enter

        return wrapped_enter

    def wrap_step_exit(self, original_exit: Callable[..., Any]) -> Callable[..., Any]:
        """Create wrapper for Step.__exit__ method.

        This wrapper intercepts the step completion and buffers the result
        message instead of sending it immediately through the reporter.

        Args:
            original_exit: The original Step.__exit__ method

        Returns:
            Wrapped version of __exit__ that buffers messages
        """

        @wraps(original_exit)
        def wrapped_exit(
            step_self: Step,
            exc_type: Optional[Type[BaseException]],
            exc_value: Optional[BaseException],
            traceback: Optional[TracebackType],
        ) -> Any:
            """Wrapped __exit__ that intercepts step completion.

            Args:
                step_self: The Step instance
                exc_type: Exception type (if any)
                exc_value: Exception value (if any)
                traceback: Exception traceback (if any)

            Returns:
                Same as original __exit__ to preserve exception handling
            """

            # Check if we should intercept
            if not self.is_batching_enabled():
                # Batching disabled, use original behavior
                return original_exit(step_self, exc_type, exc_value, traceback)

            try:
                # Determine step result based on exception info
                if exc_type is None:
                    # No exception - step passed
                    result = "passed"
                elif issubclass(exc_type, AssertionError):
                    # Assertion failed - step failed
                    result = "failed"
                elif issubclass(exc_type, KeyboardInterrupt):
                    # User interrupted - step aborted
                    result = "aborted"
                else:
                    # Other exception - step errored
                    result = "errored"

                # Extract step information for buffering
                step_info = {
                    "name": str(step_self),
                    "uid": getattr(step_self, "uid", None),
                    "result": result,
                    "exc_type": exc_type.__name__ if exc_type else None,
                    "exc_value": str(exc_value) if exc_value else None,
                }

                # Build context path for hierarchy preservation
                context_path = self._build_context_path(step_self)

                # Buffer the step stop message
                self.batching_reporter.buffer_message(
                    message_type="step_stop",
                    message_content=step_info,
                    context_path=context_path,
                )

                # CRITICAL FIX: Do NOT restore the original reporter here!
                # This restoration was causing PyATS reporter server crashes because:
                # 1. We buffer the step_stop message (good)
                # 2. We restore the real reporter (bad - happens here)
                # 3. original_exit() then calls reporter.stop() with the REAL reporter
                # 4. Result: Both buffered AND direct messages sent, overwhelming the server
                #
                # By keeping the DummyReporter active, we ensure:
                # - PyATS calls DummyReporter.stop() (harmless no-op)
                # - Only our batched messages reach the reporter server
                # - No socket buffer overflow, no crashes
                #
                # if hasattr(step_self, '_original_reporter'):
                #     step_self.reporter = step_self._original_reporter
                #     delattr(step_self, '_original_reporter')

                # Block parent reporter access
                # PyATS Step.__exit__() has a fallback that checks self.parent.reporter
                # when self.reporter is None/falsy. This bypasses our DummyReporter!
                # We must temporarily replace parent.reporter to prevent this.
                saved_parent_reporter = None
                if hasattr(step_self, "parent") and hasattr(
                    step_self.parent, "reporter"
                ):
                    saved_parent_reporter = step_self.parent.reporter
                    step_self.parent.reporter = DummyReporter()
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "Blocked parent reporter access for step: %s",
                            str(step_self),
                        )

                try:
                    # Call the original __exit__ to preserve its behavior
                    # This is CRITICAL for exception propagation
                    # Now it cannot find ANY real reporter (both self.reporter and parent.reporter are dummy)
                    result = original_exit(step_self, exc_type, exc_value, traceback)
                finally:
                    # ALWAYS restore parent reporter, even if original_exit raises
                    if saved_parent_reporter is not None:
                        step_self.parent.reporter = saved_parent_reporter
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                "Restored parent reporter for step: %s", str(step_self)
                            )

                # Log interception (only in debug mode)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Intercepted step stop: %s (result: %s, context: %s)",
                        step_info["name"],
                        step_info["result"],
                        context_path,
                    )

                # Return the original result to preserve exception handling
                return result

            except Exception as e:
                # On any error in our interception, fall back to original
                logger.error("Failed to intercept step stop: %s", e)
                self.error_count += 1

                # Make sure to restore reporter if needed
                if hasattr(step_self, "_original_reporter"):
                    step_self.reporter = step_self._original_reporter
                    delattr(step_self, "_original_reporter")

                # CRITICAL: Also block parent reporter in error path
                # Same issue exists here - we must prevent parent.reporter access
                saved_parent_reporter_error = None
                if hasattr(step_self, "parent") and hasattr(
                    step_self.parent, "reporter"
                ):
                    saved_parent_reporter_error = step_self.parent.reporter
                    step_self.parent.reporter = DummyReporter()

                try:
                    # Use original behavior
                    return original_exit(step_self, exc_type, exc_value, traceback)
                finally:
                    # Restore parent reporter after error path execution
                    if saved_parent_reporter_error is not None:
                        step_self.parent.reporter = saved_parent_reporter_error

        # Store reference to original for potential restoration
        self.original_exit = original_exit

        return wrapped_exit

    def _build_context_path(self, step: Step) -> str:
        """Build hierarchical context path for a step.

        Traverses the parent chain to build a path like:
        "test.testcase.section.step"

        Args:
            step: The Step instance

        Returns:
            Dot-separated context path
        """
        path_parts = []
        current = step

        # Traverse up the parent chain
        while current:
            # Get the name/uid of current level
            if hasattr(current, "uid"):
                if current.uid:
                    # Use the full uid path if available
                    path_parts.append(str(current.uid))
                    break  # uid contains full path already
            elif hasattr(current, "name"):
                path_parts.append(str(current.name))
            else:
                path_parts.append(str(current))

            # Move to parent
            current = getattr(current, "parent", None)

        # Reverse to get top-down order
        path_parts.reverse()

        # Join with dots
        return ".".join(path_parts) if path_parts else "unknown"

    def install_interceptors(self) -> bool:
        """Install the interceptors on PyATS Step class.

        This modifies the Step class methods globally to use our wrappers.
        Should be called from test setup when batching is enabled.

        Returns:
            True if installation successful, False otherwise
        """
        try:
            # Store original methods if not already stored
            if not self.original_enter:
                self.original_enter = Step.__enter__
            if not self.original_exit:
                self.original_exit = Step.__exit__

            # Install our wrappers
            Step.__enter__ = self.wrap_step_enter(self.original_enter)
            Step.__exit__ = self.wrap_step_exit(self.original_exit)

            logger.info("Step interceptors installed successfully")
            return True

        except Exception as e:
            logger.error("Failed to install step interceptors: %s", e)
            return False

    def uninstall_interceptors(self) -> bool:
        """Uninstall the interceptors and restore original Step methods.

        Should be called from test teardown or when disabling batching.

        Returns:
            True if uninstallation successful, False otherwise
        """
        try:
            # Restore original methods if we have them
            if self.original_enter:
                Step.__enter__ = self.original_enter
            if self.original_exit:
                Step.__exit__ = self.original_exit

            logger.info("Step interceptors uninstalled successfully")
            return True

        except Exception as e:
            logger.error("Failed to uninstall step interceptors: %s", e)
            return False

    def disable(self) -> None:
        """Disable interception (fallback mode).

        Used when errors occur to prevent cascading failures.
        """
        self.enabled = False
        logger.warning("Step interception disabled due to errors")

        # Check if error rate is too high
        if (
            self.intercepted_count > 10
            and self.error_count / self.intercepted_count > 0.1
        ):
            # More than 10% error rate, uninstall interceptors completely
            logger.error(
                "High error rate detected (%.1f%%), uninstalling interceptors",
                (self.error_count / self.intercepted_count) * 100,
            )
            self.uninstall_interceptors()

    def get_stats(self) -> Dict[str, Any]:
        """Get interceptor statistics.

        Returns:
            Dictionary with interception metrics
        """
        return {
            "enabled": self.enabled,
            "batching_enabled": self.is_batching_enabled(),
            "intercepted_count": self.intercepted_count,
            "error_count": self.error_count,
            "error_rate": (
                self.error_count / self.intercepted_count
                if self.intercepted_count > 0
                else 0
            ),
        }


class DummyReporter:
    """Dummy reporter that discards all messages.

    Used to replace the real reporter during step execution when
    batching is enabled, preventing duplicate messages.
    """

    def __init__(self) -> None:
        """Initialize dummy reporter."""
        pass

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Return a no-op function for any method call.

        Args:
            name: Method name being called

        Returns:
            A function that does nothing
        """

        def noop(*args: Any, **kwargs: Any) -> None:
            """No-op function that accepts any arguments."""
            pass

        return noop

    def __bool__(self) -> bool:
        """Return True so 'if reporter:' checks still pass.

        Returns:
            True
        """
        return True

    def __repr__(self) -> str:
        """String representation.

        Returns:
            String identifying this as a dummy
        """
        return "DummyReporter(batching_enabled)"
