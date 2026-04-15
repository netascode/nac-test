# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyatsDiscoveryResult computed properties."""

from pathlib import Path

from nac_test.pyats_core.common.types import (
    PyatsDiscoveryResult,
    TestFileMetadata,
    TestType,
)


def _meta(path: str, test_type: TestType) -> TestFileMetadata:
    return TestFileMetadata(path=Path(path), test_type=test_type)


class TestPyatsDiscoveryResultProperties:
    """Tests for PyatsDiscoveryResult computed properties.

    Plain dataclass field assignment is not tested here — mypy enforces that.
    """

    def test_total_count_sums_both_lists(self) -> None:
        result = PyatsDiscoveryResult(
            api_tests=[_meta("/t/api1.py", "api"), _meta("/t/api2.py", "api")],
            d2d_tests=[_meta("/t/d2d1.py", "d2d")],
            filtered_by_tags=0,
        )
        assert result.total_count == 3

    def test_total_count_empty(self) -> None:
        result = PyatsDiscoveryResult(api_tests=[], d2d_tests=[], filtered_by_tags=0)
        assert result.total_count == 0

    def test_all_tests_is_api_then_d2d(self) -> None:
        api = _meta("/t/api.py", "api")
        d2d = _meta("/t/d2d.py", "d2d")
        result = PyatsDiscoveryResult(
            api_tests=[api], d2d_tests=[d2d], filtered_by_tags=0
        )
        assert result.all_tests == [api, d2d]

    def test_api_paths_extracts_paths(self) -> None:
        result = PyatsDiscoveryResult(
            api_tests=[_meta("/t/api1.py", "api"), _meta("/t/api2.py", "api")],
            d2d_tests=[],
            filtered_by_tags=0,
        )
        assert result.api_paths == [Path("/t/api1.py"), Path("/t/api2.py")]

    def test_d2d_paths_extracts_paths(self) -> None:
        result = PyatsDiscoveryResult(
            api_tests=[],
            d2d_tests=[_meta("/t/d2d1.py", "d2d"), _meta("/t/d2d2.py", "d2d")],
            filtered_by_tags=0,
        )
        assert result.d2d_paths == [Path("/t/d2d1.py"), Path("/t/d2d2.py")]
