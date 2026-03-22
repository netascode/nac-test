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

from nac_test.robot.pabot import parse_and_validate_extra_args, run_pabot


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


class TestParseAndValidateExtraArgsDataError:
    """Test DataError handling in parse_and_validate_extra_args."""

    def test_parse_and_validate_extra_args_data_error(self) -> None:
        """Test that DataError is raised for invalid Robot Framework arguments.

        When parse_args encounters invalid Robot Framework syntax,
        it raises DataError. This should propagate through parse_and_validate_extra_args
        to indicate that the robot arguments are malformed.
        """
        # Use invalid Robot Framework argument that will cause DataError
        extra_args = ["--invalid-robot-option-xyz123", "value"]

        # Should raise DataError from robot.errors
        with pytest.raises(DataError):
            parse_and_validate_extra_args(extra_args)
