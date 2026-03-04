# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.utils.logging module."""

import logging
from collections.abc import Generator
from typing import Any

import pytest

from nac_test.utils.logging import DEFAULT_LOGLEVEL, LogLevel, configure_logging


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


class TestConfigureLogging:
    """Tests for configure_logging() function.

    Note: PR fix/487-pytest-io-error adds further tests for CurrentStreamHandler
    and handler configuration. After merging, consolidate overlapping tests.
    """

    @pytest.fixture(autouse=True)
    def cleanup_root_logger(self) -> Generator[None, Any, None]:
        """Clean up root logger after each test."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level
        yield
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)

    def test_uses_stream_handler(self) -> None:
        """Verify configure_logging() installs a StreamHandler."""
        configure_logging("INFO")

        root_logger = logging.getLogger()
        stream_handlers = [
            h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) >= 1

    @pytest.mark.parametrize(
        ("level_input", "expected_level"),
        [
            (LogLevel.DEBUG, logging.DEBUG),
            (LogLevel.INFO, logging.INFO),
            (LogLevel.WARNING, logging.WARNING),
            (LogLevel.ERROR, logging.ERROR),
            (LogLevel.CRITICAL, logging.CRITICAL),
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("debug", logging.DEBUG),
            ("info", logging.INFO),
            ("warning", logging.WARNING),
        ],
    )
    def test_valid_input_configures_logging_correctly(
        self, level_input: LogLevel | str, expected_level: int
    ) -> None:
        configure_logging(level_input)
        assert logging.getLogger().level == expected_level

    @pytest.mark.parametrize(
        "invalid_input",
        ["invalid", "", "NOTREAL", "trace"],
    )
    def test_invalid_input_falls_back_to_default(self, invalid_input: str) -> None:
        configure_logging(invalid_input)
        assert logging.getLogger().level == int(DEFAULT_LOGLEVEL)
