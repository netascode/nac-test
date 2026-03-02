# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
from unittest.mock import Mock, patch

import pytest

from nac_test.core.types import CombinedResults, TestResults
from nac_test.utils.logging import DEFAULT_LOGLEVEL, LogLevel

from .conftest import run_cli_with_temp_dirs


class TestVerboseVerbosityInteraction:
    """Tests for --verbose flag interaction with --loglevel (--verbosity deprecated)."""

    @pytest.mark.parametrize(
        ("cli_args", "expected_loglevel", "expected_verbose"),
        [
            # --verbose alone implies DEBUG loglevel
            (["--verbose"], LogLevel.DEBUG, True),
            # --verbose with explicit loglevel override
            (["--verbose", "--loglevel", "WARNING"], LogLevel.WARNING, True),
            (["--verbose", "--loglevel", "INFO"], LogLevel.INFO, True),
            (["--verbose", "--loglevel", "ERROR"], LogLevel.ERROR, True),
            # --loglevel without --verbose
            ([], DEFAULT_LOGLEVEL, False),
            (["--loglevel", "DEBUG"], LogLevel.DEBUG, False),
            (["--loglevel", "INFO"], LogLevel.INFO, False),
            # deprecated --verbosity still works
            (["--verbosity", "DEBUG"], LogLevel.DEBUG, False),
        ],
        ids=[
            "verbose_only",
            "verbose_with_warning",
            "verbose_with_info",
            "verbose_with_error",
            "default",
            "loglevel_debug",
            "loglevel_info",
            "deprecated_verbosity",
        ],
    )
    @patch("nac_test.cli.main.configure_logging")
    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_verbose_loglevel_passed_to_orchestrator(
        self,
        mock_orchestrator_cls: Mock,
        mock_configure_logging: Mock,
        cli_args: list[str],
        expected_loglevel: LogLevel,
        expected_verbose: bool,
    ) -> None:
        """Test that loglevel and verbose are correctly passed to CombinedOrchestrator."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_tests.return_value = CombinedResults(
            robot=TestResults(passed=1, failed=0, skipped=0)
        )
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = run_cli_with_temp_dirs(cli_args)

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        # Verify configure_logging called with correct loglevel
        mock_configure_logging.assert_called_once_with(expected_loglevel)

        # Verify CombinedOrchestrator instantiated with correct loglevel and verbose
        mock_orchestrator_cls.assert_called_once()
        call_kwargs = mock_orchestrator_cls.call_args[1]
        assert call_kwargs["loglevel"] == expected_loglevel
        assert call_kwargs["verbose"] == expected_verbose
