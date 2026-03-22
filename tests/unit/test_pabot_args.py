# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for pabot argument validation.

This module tests argument validation error handling for the pabot runner.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from robot.errors import DataError

from nac_test.robot.pabot import parse_and_validate_extra_args, run_pabot


class TestParseAndValidateExtraArgs:
    """Test suite for parse_and_validate_extra_args function."""

    def test_datasource_raises_error(self) -> None:
        """Test that filenames/datasources in extra_args raise ValueError."""
        extra_args = ["--variable", "VAR:value", "/path/to/tests"]

        with pytest.raises(ValueError) as exc_info:
            parse_and_validate_extra_args(extra_args)

        assert (
            "datasource" in str(exc_info.value).lower()
            or "file" in str(exc_info.value).lower()
        )
        assert "/path/to/tests" in str(exc_info.value)

    def test_invalid_robot_args_raises_error(self) -> None:
        """Test that invalid Robot Framework arguments raise DataError."""
        extra_args = ["--invalid-option-xyz", "value"]

        with pytest.raises(DataError):
            parse_and_validate_extra_args(extra_args)

    def test_pabot_option_raises_error(self) -> None:
        """Test that pabot-specific options raise ValueError."""
        extra_args = ["--testlevelsplit"]

        with pytest.raises(ValueError) as exc_info:
            parse_and_validate_extra_args(extra_args)

        assert "pabot" in str(exc_info.value).lower()
        assert "testlevelsplit" in str(exc_info.value).lower()


class TestRunPabotErrorHandling:
    """Test error handling in run_pabot function."""

    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_invalid_extra_args_returns_error_code(
        self, mock_main_program: MagicMock
    ) -> None:
        """Test that invalid extra_args return error code 252."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--invalid-option", "value"]

        result = run_pabot(output_path, extra_args=extra_args)

        assert result == 252
        mock_main_program.assert_not_called()

    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_datasource_in_extra_args_returns_error_code(
        self, mock_main_program: MagicMock
    ) -> None:
        """Test that datasources in extra_args return error code 252."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--loglevel", "DEBUG", "/path/to/tests"]

        result = run_pabot(output_path, extra_args=extra_args)

        assert result == 252
        mock_main_program.assert_not_called()

    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_pabot_option_in_extra_args_returns_error_code(
        self, mock_main_program: MagicMock
    ) -> None:
        """Test that pabot options in extra_args return error code 252."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--testlevelsplit", "--loglevel", "DEBUG"]

        result = run_pabot(output_path, extra_args=extra_args)

        assert result == 252
        mock_main_program.assert_not_called()


class TestRunPabotRobotLoglevel:
    """Test robot_loglevel handling in run_pabot function.

    Tests that robot_loglevel parameter adds --loglevel to robot args.
    """

    @pytest.mark.parametrize(
        ("robot_loglevel", "expected_loglevel"),
        [
            # No robot_loglevel set - no --loglevel in final args
            (None, None),
            # robot_loglevel set to DEBUG
            ("DEBUG", "DEBUG"),
        ],
        ids=[
            "no_loglevel",
            "debug_loglevel",
        ],
    )
    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_robot_loglevel_adds_arg(
        self,
        mock_main_program: MagicMock,
        tmp_path: Path,
        robot_loglevel: str | None,
        expected_loglevel: str | None,
    ) -> None:
        """Test that robot_loglevel adds --loglevel to robot args."""
        mock_main_program.return_value = 0

        run_pabot(tmp_path, robot_loglevel=robot_loglevel)

        mock_main_program.assert_called_once()
        call_args = mock_main_program.call_args[0][0]

        if expected_loglevel is None:
            # --loglevel should not be in args
            assert "--loglevel" not in call_args
        else:
            # Find --loglevel and verify its value
            assert "--loglevel" in call_args
            loglevel_idx = call_args.index("--loglevel")
            actual_loglevel = call_args[loglevel_idx + 1]
            assert actual_loglevel == expected_loglevel
