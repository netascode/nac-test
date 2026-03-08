# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for string utility functions."""

import pytest

from nac_test.utils.strings import markdown_to_html


class TestMarkdownToHtml:
    """Tests for markdown_to_html function."""

    @pytest.mark.parametrize("empty_input", ["", None])
    def test_empty_input_returns_empty_string(self, empty_input: str | None) -> None:
        assert markdown_to_html(empty_input) == ""

    def test_returns_string(self) -> None:
        """Verify basic contract only - not testing markdown library internals."""
        result = markdown_to_html("some text")
        assert isinstance(result, str)
        assert "some text" in result
