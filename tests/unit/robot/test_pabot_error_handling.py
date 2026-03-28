# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for pabot error handling edge cases.

This module tests error scenarios in pabot execution, including unexpected
exceptions from pabot.main_program and DataError handling.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from robot.errors import DataError

from nac_test.cli.validators import validate_extra_args
from nac_test.robot.pabot import run_pabot


class TestRunPabotUnexpectedException:
    """Test pabot error handling for unexpected exceptions."""

    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_run_pabot_unexpected_exception(self, mock_main_program: MagicMock) -> None:
        """Test that unexpected exceptions from pabot.main_program are propagated.

        When pabot.main_program raises an exception (not ValueError/DataError),
        the exception should propagate to the caller rather than being caught.
        This tests the error path where pabot encounters an unexpected failure.
        """
        output_path = Path("/tmp/test_output")

        # Mock pabot.main_program to raise an unexpected exception
        mock_main_program.side_effect = RuntimeError("Unexpected pabot failure")

        # Exception should propagate
        with pytest.raises(RuntimeError, match="Unexpected pabot failure"):
            run_pabot(output_path)


# --- Robot executable resolution tests ---


class TestRunPabotRobotExecutableResolution:
    """Test that run_pabot resolves the robot binary via sysconfig."""

    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_run_pabot_resolves_robot_using_sysconfig(
        self, mock_main_program: MagicMock, tmp_path: Path
    ) -> None:
        """Test that robot executable is resolved using sysconfig.get_path('scripts')."""
        fake_scripts_dir = tmp_path / "scripts"
        fake_scripts_dir.mkdir()
        fake_robot_executable = fake_scripts_dir / "robot"
        fake_robot_executable.touch()
        mock_main_program.return_value = 0

        with patch(
            "nac_test.robot.pabot.sysconfig.get_path",
            return_value=str(fake_scripts_dir),
        ):
            run_pabot(tmp_path)

        call_args = mock_main_program.call_args[0][0]
        assert "--command" in call_args
        command_idx = call_args.index("--command")
        assert call_args[command_idx + 1] == str(fake_robot_executable)

    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_run_pabot_raises_runtime_error_when_robot_not_found(
        self, mock_main_program: MagicMock, tmp_path: Path
    ) -> None:
        """Test that RuntimeError is raised when robot executable does not exist."""
        fake_scripts_dir = tmp_path / "scripts"
        fake_scripts_dir.mkdir()

        with patch(
            "nac_test.robot.pabot.sysconfig.get_path",
            return_value=str(fake_scripts_dir),
        ):
            with pytest.raises(RuntimeError, match="robot executable not found"):
                run_pabot(tmp_path)

        mock_main_program.assert_not_called()


class TestValidateExtraArgsDataError:
    """Test DataError handling in validate_extra_args."""

    def test_validate_extra_args_data_error(self) -> None:
        """Test that DataError is raised for invalid Robot Framework arguments.

        When parse_args encounters invalid Robot Framework syntax,
        it raises DataError. This should propagate through validate_extra_args
        to indicate that the robot arguments are malformed.
        """
        # Use invalid Robot Framework argument that will cause DataError
        extra_args = ["--invalid-robot-option-xyz123", "value"]

        # Should raise DataError from robot.errors
        with pytest.raises(DataError):
            validate_extra_args(extra_args)
