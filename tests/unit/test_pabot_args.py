# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from robot.errors import DataError

from nac_test.pabot import parse_and_validate_extra_args, run_pabot


class TestParseAndValidateExtraArgs:
    """Test suite for parse_and_validate_extra_args function - edge cases only."""

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


class TestRunPabotWithArgs:
    """Test suite for run_pabot function."""

    @patch("nac_test.pabot.pabot.pabot.main")
    def test_run_pabot_without_extra_args(self, mock_main: MagicMock) -> None:
        """Test run_pabot without extra_args."""
        output_path = Path("/tmp/test_output")

        run_pabot(output_path)

        mock_main.assert_called_once()
        args = mock_main.call_args[0][0]

        # Pabot args should be present
        assert "--pabotlib" in args
        assert "--pabotlibport" in args
        assert "0" in args
        # Robot args should be present
        assert "--outputdir" in args
        assert str(output_path) in args
        assert "--skiponfailure" in args
        assert "non-critical" in args
        assert "--xunit" in args
        assert "xunit.xml" in args
        # Path should be last
        assert args[-1] == str(output_path)

    @patch("nac_test.pabot.pabot.pabot.main")
    def test_run_pabot_with_extra_args(self, mock_main: MagicMock) -> None:
        """Test run_pabot with extra_args appended to robot_args."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--loglevel", "INFO", "--variable", "ENV:test"]

        run_pabot(output_path, extra_args=extra_args)

        mock_main.assert_called_once()
        args = mock_main.call_args[0][0]

        # Extra args should be in the robot args section (after pabot args, before path)
        assert "--loglevel" in args
        assert "INFO" in args
        assert "--variable" in args
        assert "ENV:test" in args

        # Verify ordering: pabot_args come first, then robot_args (including extra), then path
        pabotlib_idx = args.index("--pabotlib")
        outputdir_idx = args.index("--outputdir")
        loglevel_idx = args.index("--loglevel")
        path_idx = len(args) - 1

        assert pabotlib_idx < outputdir_idx < loglevel_idx < path_idx

    @patch("nac_test.pabot.pabot.pabot.main")
    def test_run_pabot_extra_args_appended(self, mock_main: MagicMock) -> None:
        """Test that extra_args are appended to robot_args, not replacing anything."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--listener", "MyListener", "--variable", "KEY:value"]

        run_pabot(output_path, include=["smoke"], extra_args=extra_args)

        mock_main.assert_called_once()
        args = mock_main.call_args[0][0]

        # Original include should still be there
        assert "--include" in args
        assert "smoke" in args
        # Extra args should also be there
        assert "--listener" in args
        assert "MyListener" in args
        assert "--variable" in args
        assert "KEY:value" in args

    @patch("nac_test.pabot.pabot.pabot.main")
    def test_run_pabot_invalid_extra_args_raises_exception(
        self, mock_main: MagicMock
    ) -> None:
        """Test that invalid extra_args raise DataError."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--invalid-option", "value"]

        with pytest.raises(DataError):
            run_pabot(output_path, extra_args=extra_args)

        mock_main.assert_not_called()

    @patch("nac_test.pabot.pabot.pabot.main")
    def test_run_pabot_datasource_in_extra_args_raises_exception(
        self, mock_main: MagicMock
    ) -> None:
        """Test that datasources in extra_args raise ValueError."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--loglevel", "DEBUG", "/path/to/tests"]

        with pytest.raises(ValueError):
            run_pabot(output_path, extra_args=extra_args)

        mock_main.assert_not_called()

    @patch("nac_test.pabot.pabot.pabot.main")
    def test_run_pabot_pabot_option_in_extra_args_raises_exception(
        self, mock_main: MagicMock
    ) -> None:
        """Test that pabot options in extra_args raise ValueError."""
        output_path = Path("/tmp/test_output")
        extra_args = ["--testlevelsplit", "--loglevel", "DEBUG"]

        with pytest.raises(ValueError):
            run_pabot(output_path, extra_args=extra_args)

        mock_main.assert_not_called()
