# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for logging utilities."""

import io
import logging
import sys
from collections.abc import Generator
from typing import Any

import pytest

from nac_test.utils.logging import CurrentStreamHandler, configure_logging


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
