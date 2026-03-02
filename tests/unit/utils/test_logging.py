# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.utils.logging module."""

import logging

import pytest

from nac_test.utils.logging import LogLevel


class TestLogLevelIntValue:
    """Tests for LogLevel.int_value property."""

    @pytest.mark.parametrize(
        ("level", "expected_int"),
        [
            (LogLevel.DEBUG, logging.DEBUG),
            (LogLevel.INFO, logging.INFO),
            (LogLevel.WARNING, logging.WARNING),
            (LogLevel.ERROR, logging.ERROR),
            (LogLevel.CRITICAL, logging.CRITICAL),
        ],
    )
    def test_int_value_matches_logging_module(
        self, level: LogLevel, expected_int: int
    ) -> None:
        assert level.int_value == expected_int


class TestLogLevelComparison:
    """Tests for LogLevel comparison operators."""

    def test_debug_less_than_info(self) -> None:
        assert LogLevel.DEBUG < LogLevel.INFO

    def test_info_less_than_warning(self) -> None:
        assert LogLevel.INFO < LogLevel.WARNING

    def test_warning_less_than_error(self) -> None:
        assert LogLevel.WARNING < LogLevel.ERROR

    def test_error_less_than_critical(self) -> None:
        assert LogLevel.ERROR < LogLevel.CRITICAL

    def test_debug_less_than_or_equal_debug(self) -> None:
        assert LogLevel.DEBUG <= LogLevel.DEBUG

    def test_debug_less_than_or_equal_info(self) -> None:
        assert LogLevel.DEBUG <= LogLevel.INFO

    def test_critical_greater_than_error(self) -> None:
        assert LogLevel.CRITICAL > LogLevel.ERROR

    def test_warning_greater_than_or_equal_warning(self) -> None:
        assert LogLevel.WARNING >= LogLevel.WARNING

    def test_warning_greater_than_or_equal_info(self) -> None:
        assert LogLevel.WARNING >= LogLevel.INFO
