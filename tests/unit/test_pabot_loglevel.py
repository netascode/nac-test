# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for run_pabot loglevel handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nac_test.core.types import ValidatedRobotArgs
from nac_test.robot.pabot import run_pabot
from tests.unit.conftest import is_sublist


class TestRunPabotLoglevel:
    """Test default_robot_loglevel handling in run_pabot function."""

    @pytest.mark.parametrize(
        ("default_robot_loglevel", "expected_loglevel"),
        [
            (None, None),
            ("DEBUG", "DEBUG"),
        ],
    )
    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_default_robot_loglevel_adds_arg(
        self,
        mock_main_program: MagicMock,
        tmp_path: Path,
        default_robot_loglevel: str | None,
        expected_loglevel: str | None,
    ) -> None:
        """Test that default_robot_loglevel adds --loglevel to robot args."""
        mock_main_program.return_value = 0

        run_pabot(tmp_path, default_robot_loglevel=default_robot_loglevel)

        mock_main_program.assert_called_once()
        call_args = mock_main_program.call_args[0][0]

        if expected_loglevel is None:
            assert "--loglevel" not in call_args
        else:
            assert "--loglevel" in call_args
            loglevel_idx = call_args.index("--loglevel")
            actual_loglevel = call_args[loglevel_idx + 1]
            assert actual_loglevel == expected_loglevel

    @pytest.mark.parametrize(
        "extra_args_strings",
        [
            ["--loglevel", "TRACE"],
            ["--loglevel=TRACE"],
            ["-L", "TRACE"],
        ],
    )
    @pytest.mark.parametrize(
        "default_robot_loglevel",
        ["DEBUG", None],
    )
    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_extra_args_loglevel_overrides_default(
        self,
        mock_main_program: MagicMock,
        tmp_path: Path,
        default_robot_loglevel: str | None,
        extra_args_strings: list[str],
    ) -> None:
        """Test that an explicit loglevel in extra_args suppresses the default."""
        mock_main_program.return_value = 0

        # robot_opts reflects what pabot's parser would produce: loglevel is set
        extra_args = ValidatedRobotArgs(
            args=extra_args_strings,
            robot_opts={"loglevel": "TRACE"},
        )
        run_pabot(
            tmp_path,
            default_robot_loglevel=default_robot_loglevel,
            extra_args=extra_args,
        )

        mock_main_program.assert_called_once()
        call_args = mock_main_program.call_args[0][0]

        # extra_args.args passed through verbatim and in order
        assert is_sublist(extra_args_strings, call_args), (
            f"extra_args {extra_args_strings} not found as contiguous sequence in {call_args}"
        )

        # default loglevel must not be appended when extra_args already contains one
        if default_robot_loglevel:
            assert call_args[-2:] != ["--loglevel", default_robot_loglevel]
