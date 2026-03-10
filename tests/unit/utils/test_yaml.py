# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for YAML utilities."""

from io import StringIO

from nac_test.utils.yaml import dump, dump_to_stream, safe_load


class TestSafeLoad:
    """Tests for safe_load function."""

    def test_load_from_string(self) -> None:
        """Load YAML from string input."""
        result = safe_load("key: value")
        assert result == {"key": "value"}

    def test_load_from_file_handle(self) -> None:
        """Load YAML from file-like object."""
        stream = StringIO("key: value")
        result = safe_load(stream)
        assert result == {"key": "value"}

    def test_load_empty_returns_none(self) -> None:
        """Empty YAML document returns None."""
        assert safe_load("") is None


class TestDump:
    """Tests for dump function."""

    def test_dump_returns_string(self) -> None:
        """Dump returns YAML string."""
        result = dump({"key": "value"})
        assert "key: value" in result


class TestDumpToStream:
    """Tests for dump_to_stream function."""

    def test_dump_to_stream_writes(self) -> None:
        """Dump to stream writes YAML content."""
        stream = StringIO()
        dump_to_stream({"key": "value"}, stream)
        assert "key: value" in stream.getvalue()
