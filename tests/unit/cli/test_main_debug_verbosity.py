# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
from unittest.mock import Mock, patch

import pytest

from nac_test.core.types import CombinedResults, TestResults
from nac_test.utils.logging import VerbosityLevel

from .conftest import run_cli_with_temp_dirs


class TestDebugVerbosityInteraction:
    """Tests for --debug flag interaction with --verbosity."""

    @pytest.mark.parametrize(
        "cli_args,expected_level",
        [
            (["--debug"], VerbosityLevel.DEBUG),
            (["--debug", "--verbosity", "WARNING"], VerbosityLevel.WARNING),
            (["--debug", "-v", "WARNING"], VerbosityLevel.WARNING),
            (["--debug", "-v", "INFO"], VerbosityLevel.INFO),
            (["--debug", "-v", "ERROR"], VerbosityLevel.ERROR),
            (["--verbosity", "WARNING", "--debug"], VerbosityLevel.WARNING),
            (["-v", "INFO", "--debug"], VerbosityLevel.INFO),
            (["--debug", "-v", "DEBUG"], VerbosityLevel.DEBUG),
            ([], VerbosityLevel.WARNING),
            (["--verbosity", "DEBUG"], VerbosityLevel.DEBUG),
            (["-v", "INFO"], VerbosityLevel.INFO),
        ],
    )
    @patch("nac_test.cli.main.configure_logging")
    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_debug_verbosity_interaction(
        self,
        mock_orchestrator_cls: Mock,
        mock_configure_logging: Mock,
        cli_args: list[str],
        expected_level: VerbosityLevel,
    ) -> None:
        """Test that --debug implies DEBUG verbosity unless explicitly overridden."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_tests.return_value = CombinedResults(
            robot=TestResults(passed=1, failed=0, skipped=0)
        )
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = run_cli_with_temp_dirs(cli_args)

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_configure_logging.assert_called_once_with(expected_level)
