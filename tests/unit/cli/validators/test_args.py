# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for extra Robot Framework argument validation.

This module tests validation of extra Robot Framework arguments passed via
the -- separator, including controlled options, pabot options, and datasources.

ValueError from validate_extra_args maps to EXIT_INVALID_ARGS in the CLI
(CLI misuse: controlled option, pabot option, or datasource in extra args).
DataError maps to EXIT_DATA_ERROR (invalid Robot Framework argument).
"""

import pytest
from robot.errors import DataError

from nac_test.cli.validators import validate_extra_args


class TestValidateExtraArgs:
    """Test suite for validate_extra_args function."""

    # -- controlled long options --------------------------------------------------

    @pytest.mark.parametrize(
        "option",
        [
            "--include",
            "--exclude",
            "--outputdir",
            "--output",
            "--log",
            "--report",
            "--xunit",
        ],
    )
    @pytest.mark.parametrize("form", ["space", "equals"])
    def test_controlled_long_option_raises_error(self, option: str, form: str) -> None:
        """Test that controlled long options raise ValueError in both --opt value and --opt=value forms."""
        args = [f"{option}=value"] if form == "equals" else [option, "value"]
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(args)

        assert option in str(exc_info.value)
        assert "nac-test" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "short_opt",
        ["-i", "-e", "-d", "-o", "-l", "-r", "-x"],
    )
    def test_controlled_short_option_raises_error(self, short_opt: str) -> None:
        """Test that controlled short options raise ValueError with guidance."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args([short_opt, "value"])

        assert short_opt in str(exc_info.value)
        assert "nac-test" in str(exc_info.value).lower()

    def test_dryrun_option_raises_error(self) -> None:
        """Test that --dryrun raises ValueError (no short form)."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(["--dryrun"])

        assert "--dryrun" in str(exc_info.value)
        assert "nac-test --dry-run" in str(exc_info.value)

    def test_multiple_controlled_options_lists_all(self) -> None:
        """Test that multiple controlled options are all listed in the error."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(
                ["--include", "tag1", "-e", "tag2", "--outputdir", "/tmp"]
            )

        error_msg = str(exc_info.value)
        assert "--include" in error_msg
        assert "-e" in error_msg
        assert "--outputdir" in error_msg

    # -- pabot options ------------------------------------------------------------

    @pytest.mark.parametrize(
        "extra_args",
        [
            ["--testlevelsplit"],
            ["--pabotlib"],
            ["--pabotlibhost", "localhost"],
            ["--pabotlibport", "8270"],
            ["--processes", "4"],
            ["--verbose"],
            ["--artifacts", "png"],
        ],
    )
    def test_pabot_option_raises_error(self, extra_args: list[str]) -> None:
        """Test that pabot-specific options raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(extra_args)

        assert "pabot" in str(exc_info.value).lower()
        assert extra_args[0] in str(exc_info.value)

    def test_pabot_option_equals_form_raises_error(self) -> None:
        """Test that pabot options in --opt=value form raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(["--testlevelsplit=true"])

        assert "pabot" in str(exc_info.value).lower()

    def test_pabot_option_with_valid_robot_args_raises_error(self) -> None:
        """Test pabot option mixed with valid Robot args still raises, reporting only offenders."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(
                ["--variable", "FOO:bar", "--pabotlib", "--loglevel", "DEBUG"]
            )

        assert "pabot" in str(exc_info.value).lower()
        assert "--pabotlib" in str(exc_info.value)
        assert "--variable" not in str(exc_info.value)

    # -- datasources --------------------------------------------------------------

    def test_datasource_raises_error(self) -> None:
        """Test that filenames/datasources in extra_args raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_extra_args(["--variable", "VAR:value", "/path/to/tests"])

        assert (
            "datasource" in str(exc_info.value).lower()
            or "file" in str(exc_info.value).lower()
        )
        assert "/path/to/tests" in str(exc_info.value)

    # -- invalid RF args ----------------------------------------------------------

    def test_invalid_robot_args_raises_data_error(self) -> None:
        """Test that invalid Robot Framework arguments raise DataError (→ EXIT_DATA_ERROR)."""
        with pytest.raises(DataError):
            validate_extra_args(["--invalid-option-xyz", "value"])

    # -- valid args ---------------------------------------------------------------

    def test_empty_args_succeeds(self) -> None:
        """Test that empty extra_args validates without error."""
        validate_extra_args([])

    def test_valid_robot_args_succeeds(self) -> None:
        """Test that valid Robot args validate without error."""
        validate_extra_args(["--variable", "VAR:value", "--loglevel", "DEBUG"])


class TestPabotApiShape:
    """Guard against pabot API changes that would silently disable validation."""

    def test_pabot_parse_args_returns_expected_shape(self) -> None:
        """Verify parse_args returns expected tuple structure with known types and keys.

        nac_test.cli.validators.args relies on:
          result[1] being a list  (datasources — iterated in _raise_if_datasources)
          result[2] being a dict  (pabot args — .keys() used to build _PABOT_OPTION_NAMES)
        Type assertions here catch API changes where the return shape is preserved but
        element types change (e.g. result[2] becomes a list), which would silently
        break validation without failing a keys-only check.
        """
        from nac_test.cli.validators.args import _pabot_parse_args

        assert _pabot_parse_args is not None
        result = _pabot_parse_args(["__dummy__.robot"])
        assert len(result) == 4, f"Expected 4-tuple from parse_args, got {len(result)}"

        datasources = result[1]
        assert isinstance(datasources, list), (
            f"Expected result[1] (datasources) to be a list, got {type(datasources).__name__}"
        )

        pabot_args = result[2]
        assert isinstance(pabot_args, dict), (
            f"Expected result[2] (pabot_args) to be a dict, got {type(pabot_args).__name__}"
        )
        assert "pabotlib" in pabot_args, (
            f"Expected 'pabotlib' key in pabot_args, got {list(pabot_args)}"
        )
        assert "testlevelsplit" in pabot_args
