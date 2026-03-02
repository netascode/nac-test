# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.utils.logging module."""

from nac_test.utils.logging import LogLevel


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


class TestLogLevelInt:
    """Tests for LogLevel __int__ conversion."""

    def test_int_debug(self) -> None:
        assert int(LogLevel.DEBUG) == 10

    def test_int_info(self) -> None:
        assert int(LogLevel.INFO) == 20

    def test_int_warning(self) -> None:
        assert int(LogLevel.WARNING) == 30

    def test_int_error(self) -> None:
        assert int(LogLevel.ERROR) == 40

    def test_int_critical(self) -> None:
        assert int(LogLevel.CRITICAL) == 50
