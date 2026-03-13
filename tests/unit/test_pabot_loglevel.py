# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for run_pabot loglevel handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nac_test.robot.pabot import _has_loglevel_arg, run_pabot


class TestRunPabotLoglevel:
    """Test default_robot_loglevel handling in run_pabot function."""

    @pytest.mark.parametrize(
        ("default_robot_loglevel", "expected_loglevel"),
        [
            (None, None),
            ("DEBUG", "DEBUG"),
        ],
        ids=[
            "no_loglevel",
            "debug_loglevel",
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
        "extra_args",
        [
            ["--loglevel", "TRACE"],  # space-separated form
            ["--loglevel=TRACE"],  # equals form
            ["-L", "TRACE"],  # short flag
        ],
        ids=["loglevel_space", "loglevel_equals", "loglevel_short"],
    )
    @patch("nac_test.robot.pabot.pabot.pabot.main_program")
    def test_extra_args_loglevel_overrides_default(
        self,
        mock_main_program: MagicMock,
        tmp_path: Path,
        extra_args: list[str],
    ) -> None:
        """Test that any loglevel form in extra_args overrides default_robot_loglevel."""
        mock_main_program.return_value = 0

        run_pabot(
            tmp_path,
            default_robot_loglevel="DEBUG",
            extra_args=extra_args,
        )

        mock_main_program.assert_called_once()
        call_args = mock_main_program.call_args[0][0]

        # The default "DEBUG" loglevel must not have been appended — only the user's
        # explicit loglevel (from extra_args) should be present.
        # _has_loglevel_arg is the authoritative detector; we use it here to confirm
        # the flag is present, then verify the value by extracting it directly.
        assert _has_loglevel_arg(call_args), (
            f"Expected a loglevel flag in call_args, but found none: {call_args}"
        )
        # Locate the flag and extract its value — handles both "=" and space forms.
        loglevel_flags = [
            i
            for i, arg in enumerate(call_args)
            if arg.startswith("-") and _has_loglevel_arg([arg])
        ]
        assert len(loglevel_flags) == 1, (
            f"Expected exactly one loglevel flag, got {len(loglevel_flags)} in {call_args}"
        )
        flag = call_args[loglevel_flags[0]]
        if "=" in flag:
            actual_value = flag.split("=", 1)[1]
        else:
            actual_value = call_args[loglevel_flags[0] + 1]
        assert actual_value == "TRACE", (
            f"Expected loglevel TRACE, got {actual_value} in {call_args}"
        )
