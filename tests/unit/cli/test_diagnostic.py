# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for the diagnostic CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from nac_test.cli.diagnostic import (
    _find_diagnostic_script,
    _reconstruct_command,
    run_diagnostic,
)
from nac_test.core.constants import EXIT_INVALID_ARGS


class TestReconstructCommand:
    """Tests for _reconstruct_command function."""

    def test_removes_diagnostic_flag(self) -> None:
        """Test that --diagnostic is removed from command."""
        argv = ["nac-test", "-d", "./data", "--diagnostic", "-o", "./out"]
        result = _reconstruct_command(argv)
        assert "--diagnostic" not in result
        assert "nac-test" in result
        assert "-d" in result

    def test_preserves_other_args(self) -> None:
        """Test that other arguments are preserved."""
        argv = ["nac-test", "-d", "./data", "-t", "./tests", "--diagnostic"]
        result = _reconstruct_command(argv)
        # Verify key args are present (don't test exact shlex output)
        assert "-d" in result
        assert "-t" in result
        assert "./data" in result
        assert "./tests" in result

    def test_handles_no_diagnostic_flag(self) -> None:
        """Test command reconstruction when --diagnostic isn't present."""
        argv = ["nac-test", "-d", "./data"]
        result = _reconstruct_command(argv)
        assert "nac-test" in result
        assert "-d" in result


class TestFindDiagnosticScript:
    """Tests for _find_diagnostic_script function."""

    def test_returns_path_object(self) -> None:
        """Test that function returns a Path object."""
        result = _find_diagnostic_script()
        assert isinstance(result, Path)

    def test_script_file_exists(self) -> None:
        """Test that the returned path points to an existing file."""
        result = _find_diagnostic_script()
        assert result.exists()
        assert result.name == "nac-test-diagnostic.sh"


class TestRunDiagnostic:
    def test_windows_errors_without_running_script(self) -> None:
        with (
            patch("nac_test.cli.diagnostic.IS_WINDOWS", True),
            patch("nac_test.cli.diagnostic.subprocess.run") as mock_run,
            patch("nac_test.cli.diagnostic.typer.echo") as mock_echo,
        ):
            with pytest.raises(typer.Exit) as exc_info:
                run_diagnostic(Path("/tmp/out"), argv=["nac-test", "--diagnostic"])

            assert exc_info.value.exit_code == EXIT_INVALID_ARGS  # type: ignore[unreachable]
            mock_run.assert_not_called()
            mock_echo.assert_called_once()
            assert (
                "--diagnostic is supported only on Linux and macOS"
                in mock_echo.call_args.args[0]
            )
            assert mock_echo.call_args.kwargs["err"] is True

    @patch("nac_test.cli.diagnostic.subprocess.run")
    def test_propagates_script_exit_code(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=42)

        with (
            patch("nac_test.cli.diagnostic.IS_WINDOWS", False),
            patch("nac_test.cli.diagnostic.typer.echo"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                run_diagnostic(
                    Path("/tmp/out"),
                    argv=["nac-test", "-o", "/tmp/out", "--diagnostic"],
                )

            assert exc_info.value.exit_code == 42  # type: ignore[unreachable]
            mock_run.assert_called_once()
