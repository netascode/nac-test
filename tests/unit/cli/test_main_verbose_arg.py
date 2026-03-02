# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
from unittest.mock import Mock, patch

import pytest

from nac_test.core.types import CombinedResults, TestResults
from nac_test.utils.logging import DEFAULT_VERBOSITY, VerbosityLevel

from .conftest import run_cli_with_temp_dirs


class TestVerboseVerbosityInteraction:
    """Tests for --verbose flag interaction with --verbosity."""

    @pytest.mark.parametrize(
        ("cli_args", "expected_verbosity", "expected_verbose"),
        [
            # --verbose alone implies DEBUG verbosity
            (["--verbose"], VerbosityLevel.DEBUG, True),
            # --verbose with explicit verbosity override
            (["--verbose", "--verbosity", "WARNING"], VerbosityLevel.WARNING, True),
            (["--verbose", "--verbosity", "INFO"], VerbosityLevel.INFO, True),
            (["--verbose", "--verbosity", "ERROR"], VerbosityLevel.ERROR, True),
            # --verbosity without --verbose
            ([], DEFAULT_VERBOSITY, False),
            (["--verbosity", "DEBUG"], VerbosityLevel.DEBUG, False),
            (["--verbosity", "INFO"], VerbosityLevel.INFO, False),
        ],
        ids=[
            "verbose_only",
            "verbose_with_warning",
            "verbose_with_info",
            "verbose_with_error",
            "default",
            "verbosity_debug",
            "verbosity_info",
        ],
    )
    @patch("nac_test.cli.main.configure_logging")
    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_verbose_verbosity_passed_to_orchestrator(
        self,
        mock_orchestrator_cls: Mock,
        mock_configure_logging: Mock,
        cli_args: list[str],
        expected_verbosity: VerbosityLevel,
        expected_verbose: bool,
    ) -> None:
        """Test that verbosity and verbose are correctly passed to CombinedOrchestrator."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_tests.return_value = CombinedResults(
            robot=TestResults(passed=1, failed=0, skipped=0)
        )
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = run_cli_with_temp_dirs(cli_args)

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        # Verify configure_logging called with correct verbosity
        mock_configure_logging.assert_called_once_with(expected_verbosity)

        # Verify CombinedOrchestrator instantiated with correct verbosity and verbose
        mock_orchestrator_cls.assert_called_once()
        call_kwargs = mock_orchestrator_cls.call_args[1]
        assert call_kwargs["verbosity"] == expected_verbosity
        assert call_kwargs["verbose"] == expected_verbose
