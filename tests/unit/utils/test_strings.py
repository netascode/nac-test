# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for string utility functions."""

import pytest

from nac_test.utils.strings import parse_cli_option_name, sanitize_hostname


class TestSanitizeHostname:
    """Tests for sanitize_hostname utility function."""

    @pytest.mark.parametrize(
        ("hostname", "expected"),
        [
            ("sd-dc-c8kv-01", "sd_dc_c8kv_01"),
            ("Router.Corp", "router_corp"),
            ("device_name", "device_name"),
            ("192.168.1.1", "192_168_1_1"),
            ("UPPER-CASE", "upper_case"),
        ],
    )
    def test_sanitize_hostname(self, hostname: str, expected: str) -> None:
        assert sanitize_hostname(hostname) == expected


class TestParseCliOptionName:
    """Tests for parse_cli_option_name utility function."""

    @pytest.mark.parametrize(
        ("arg", "expected"),
        [
            ("--loglevel", "loglevel"),
            ("--loglevel=DEBUG", "loglevel"),
            ("-L", "L"),
            ("-i", "i"),
            ("--include", "include"),
            ("--include=sometag", "include"),
            ("--outputdir=/tmp/out", "outputdir"),
        ],
    )
    def test_parse_cli_option_name(self, arg: str, expected: str) -> None:
        assert parse_cli_option_name(arg) == expected
