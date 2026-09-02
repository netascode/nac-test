# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Centralized terminal formatting utilities for nac-test."""

import os
import re

from colorama import Fore, Style, init

from nac_test.core.types import CombinedResults

# autoreset=True means colors reset after each print
init(autoreset=True)


class TerminalColors:
    """Centralized color scheme for consistent terminal output.

    This class provides semantic color mappings and formatting methods
    to ensure consistent terminal output across the nac-test codebase.
    """

    # Semantic color mapping for different message types
    ERROR = Fore.RED
    WARNING = Fore.YELLOW
    SUCCESS = Fore.GREEN
    INFO = Fore.CYAN
    HIGHLIGHT = Fore.MAGENTA
    RESET = Style.RESET_ALL

    # Semantic styles
    BOLD = Style.BRIGHT
    DIM = Style.DIM

    # Check if colors should be disabled (for CI/CD environments)
    NO_COLOR = os.environ.get("NO_COLOR") is not None

    # Regex pattern to match ANSI escape sequences
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

    @classmethod
    def strip_ansi(cls, text: str) -> str:
        """Remove all ANSI escape sequences from text.

        Args:
            text: Text potentially containing ANSI color codes

        Returns:
            Clean text without any ANSI escape sequences
        """
        return cls.ANSI_ESCAPE_PATTERN.sub("", text)

    @classmethod
    def error(cls, text: str) -> str:
        """Format error text in red."""
        if cls.NO_COLOR:
            return text
        return f"{cls.ERROR}{text}{cls.RESET}"

    @classmethod
    def warning(cls, text: str) -> str:
        """Format warning text in yellow."""
        if cls.NO_COLOR:
            return text
        return f"{cls.WARNING}{text}{cls.RESET}"

    @classmethod
    def success(cls, text: str) -> str:
        """Format success text in green."""
        if cls.NO_COLOR:
            return text
        return f"{cls.SUCCESS}{text}{cls.RESET}"

    @classmethod
    def info(cls, text: str) -> str:
        """Format info text in cyan."""
        if cls.NO_COLOR:
            return text
        return f"{cls.INFO}{text}{cls.RESET}"

    @classmethod
    def highlight(cls, text: str) -> str:
        """Format highlighted text in magenta."""
        if cls.NO_COLOR:
            return text
        return f"{cls.HIGHLIGHT}{text}{cls.RESET}"

    @classmethod
    def bold(cls, text: str) -> str:
        """Format text in bold."""
        if cls.NO_COLOR:
            return text
        return f"{cls.BOLD}{text}{cls.RESET}"

    @classmethod
    def header(cls, text: str, width: int = 70, char: str = "=") -> str:
        """Format a header with separators.

        Args:
            text: Header text to display
            width: Width of separator line
            char: Character to use for separator

        Returns:
            Formatted header string with separators
        """
        if cls.NO_COLOR:
            separator = char * width
            return f"{separator}\n{text}\n{separator}"

        separator = char * width
        return f"{cls.ERROR}{separator}{cls.RESET}\n{cls.ERROR}{text}{cls.RESET}\n{cls.ERROR}{separator}{cls.RESET}"

    @classmethod
    def format_test_summary(cls, results: CombinedResults) -> str:
        """Format test results in Robot-style with colored numbers.

        Numbers are colored only when > 0:
        - passed: green
        - failed: red
        - skipped: yellow
        - other: magenta (only shown when > 0)
        """
        passed_str = (
            cls.success(str(results.passed))
            if results.passed > 0
            else str(results.passed)
        )
        failed_str = (
            cls.error(str(results.failed))
            if results.failed > 0
            else str(results.failed)
        )
        skipped_str = (
            cls.warning(str(results.skipped))
            if results.skipped > 0
            else str(results.skipped)
        )
        summary = (
            f"{results.total} tests, {passed_str} passed, "
            f"{failed_str} failed, {skipped_str} skipped."
        )
        if results.other > 0:
            other_str = cls.highlight(str(results.other))
            summary = summary[:-1] + f", {other_str} other."
        return summary


# Single instance for use across the codebase
terminal = TerminalColors()
