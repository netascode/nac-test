# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.utils.logging module."""

import io
import logging
import sys
from collections.abc import Generator
from typing import Any

import pytest

from nac_test.utils.logging import (
    DEFAULT_LOGLEVEL,
    CurrentStreamHandler,
    LogLevel,
    configure_logging,
)


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


class TestCurrentStreamHandler:
    """Tests for CurrentStreamHandler dynamic stream behavior."""

    def test_stream_follows_stdout_replacement(self) -> None:
        """Verify handler tracks stdout when replaced (core fix for #487)."""
        original_stdout = sys.stdout
        handler = CurrentStreamHandler("stdout")
        assert handler.stream is original_stdout

        fake_stdout = io.StringIO()
        sys.stdout = fake_stdout
        try:
            assert handler.stream is fake_stdout
        finally:
            sys.stdout = original_stdout

    def test_stream_setter_is_noop(self) -> None:
        """Verify stream setter ignores attempts to override."""
        handler = CurrentStreamHandler("stdout")
        handler.stream = io.StringIO()
        assert handler.stream is sys.stdout

    def test_no_io_error_on_closed_stdout(self) -> None:
        """Verify no I/O error when previous stdout is closed (regression test for #487)."""
        handler = CurrentStreamHandler("stdout")
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_closed_stdout")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)

        original_stdout = sys.stdout
        old_captured = io.StringIO()
        sys.stdout = old_captured
        old_captured.close()

        new_captured = io.StringIO()
        sys.stdout = new_captured

        try:
            logger.info("message after replacement")
            handler.flush()
            assert "message after replacement" in new_captured.getvalue()
        finally:
            sys.stdout = original_stdout


class TestConfigureLogging:
    """Tests for configure_logging() function."""

    @pytest.fixture(autouse=True)
    def cleanup_root_logger(self) -> Generator[None, Any, None]:
        """Clean up root logger after each test."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level
        yield
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)

    def test_uses_current_stream_handler(self) -> None:
        """Verify configure_logging() installs CurrentStreamHandler."""
        configure_logging("INFO")

        root_logger = logging.getLogger()
        current_stream_handlers = [
            h for h in root_logger.handlers if isinstance(h, CurrentStreamHandler)
        ]
        assert len(current_stream_handlers) >= 1

    def test_surgical_handler_removal_preserves_file_handlers(self) -> None:
        """Verify only stdout/stderr handlers are removed, not file handlers."""
        root_logger = logging.getLogger()

        file_stream = io.StringIO()
        file_handler = logging.StreamHandler(file_stream)
        stdout_handler = logging.StreamHandler(sys.stdout)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stdout_handler)

        configure_logging("INFO")

        assert file_handler in root_logger.handlers
        assert stdout_handler not in root_logger.handlers

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
