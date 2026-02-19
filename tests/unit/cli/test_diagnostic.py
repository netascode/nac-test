# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for the diagnostic CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from nac_test.cli.diagnostic import (
    _extract_output_dir,
    _find_diagnostic_script,
    _reconstruct_command,
    diagnostic_callback,
)
from nac_test.core.constants import EXIT_ERROR


class TestExtractOutputDir:
    """Tests for _extract_output_dir function."""

    def test_short_flag_with_space(self) -> None:
        """Test extraction with -o value syntax."""
        args = ["-d", "./data", "-o", "./output", "-t", "./tests"]
        result = _extract_output_dir(args)
        assert result == "./output"

    def test_long_flag_with_space(self) -> None:
        """Test extraction with --output value syntax."""
        args = ["-d", "./data", "--output", "./my-output", "-t", "./tests"]
        result = _extract_output_dir(args)
        assert result == "./my-output"

    def test_long_flag_with_equals(self) -> None:
        """Test extraction with --output=value syntax."""
        args = ["-d", "./data", "--output=./results", "-t", "./tests"]
        result = _extract_output_dir(args)
        assert result == "./results"

    def test_short_flag_with_equals(self) -> None:
        """Test extraction with -o=value syntax."""
        args = ["-d", "./data", "-o=./results", "-t", "./tests"]
        result = _extract_output_dir(args)
        assert result == "./results"

    def test_missing_output_returns_none(self) -> None:
        """Test that missing -o/--output returns None."""
        args = ["-d", "./data", "-t", "./tests"]
        result = _extract_output_dir(args)
        assert result is None

    def test_output_at_end_of_args(self) -> None:
        """Test that -o at end without value returns None."""
        args = ["-d", "./data", "-o"]
        result = _extract_output_dir(args)
        assert result is None

    def test_returns_first_occurrence(self) -> None:
        """Test that first -o occurrence is returned when multiple present."""
        args = ["-o", "first", "-o", "second"]
        result = _extract_output_dir(args)
        assert result == "first"


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


class TestDiagnosticCallback:
    """Tests for diagnostic_callback function."""

    def test_false_returns_immediately(self) -> None:
        """Test that False value returns without action."""
        # This should not raise or call subprocess - just returns None
        diagnostic_callback(False)  # Should complete without raising

    def test_true_without_output_dir_raises_exit(self) -> None:
        """Test that True without -o/--output raises Exit with code 1."""
        with patch("nac_test.cli.diagnostic.sys.argv", ["nac-test", "-d", "./data"]):
            with pytest.raises(typer.Exit) as exc_info:
                diagnostic_callback(True)
            assert exc_info.value.exit_code == EXIT_ERROR

    @patch("nac_test.cli.diagnostic.subprocess.run")
    def test_true_with_output_dir_runs_script(self, mock_run: MagicMock) -> None:
        """Test that True with valid args runs subprocess and exits."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch(
            "nac_test.cli.diagnostic.sys.argv",
            ["nac-test", "-d", "./data", "-o", "./output", "--diagnostic"],
        ):
            with pytest.raises(typer.Exit) as exc_info:
                diagnostic_callback(True)

            assert exc_info.value.exit_code == 0
            mock_run.assert_called_once()
            # Verify bash is called with script path
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "bash"
            assert "nac-test-diagnostic.sh" in call_args[1]

    @patch("nac_test.cli.diagnostic.subprocess.run")
    def test_propagates_script_exit_code(self, mock_run: MagicMock) -> None:
        """Test that subprocess exit code is propagated."""
        mock_run.return_value = MagicMock(returncode=42)

        with patch(
            "nac_test.cli.diagnostic.sys.argv",
            ["nac-test", "-d", "./data", "-o", "./output", "--diagnostic"],
        ):
            with pytest.raises(typer.Exit) as exc_info:
                diagnostic_callback(True)

            assert exc_info.value.exit_code == 42
