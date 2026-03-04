# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for core/constants.py helpers."""

import pytest

from nac_test.core.constants import get_positive_numeric_env


class TestGetPositiveNumericEnv:
    """Tests for get_positive_numeric_env()."""

    @pytest.mark.parametrize(
        ("env_value", "value_type", "default", "expected"),
        [
            (None, int, 10, 10),  # not set → default
            ("5", int, 10, 5),  # valid int
            ("0", int, 10, 10),  # zero → default (non-positive)
            ("-1", int, 10, 10),  # negative → default
            ("abc", int, 10, 10),  # non-numeric → default
            ("", int, 10, 10),  # empty string → default
            (None, float, 1.5, 1.5),  # not set → default
            ("2.5", float, 1.5, 2.5),  # valid float
            ("0.0", float, 1.5, 1.5),  # zero → default (non-positive)
        ],
    )
    def test_returns_expected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_value: str | None,
        value_type: type,
        default: int | float,
        expected: int | float,
    ) -> None:
        if env_value is not None:
            monkeypatch.setenv("NAC_TEST_TEST_HELPER_VALUE", env_value)
        result = get_positive_numeric_env(
            "NAC_TEST_TEST_HELPER_VALUE", default, value_type
        )
        assert result == expected
