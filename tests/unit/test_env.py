# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test._env module."""

import logging

import pytest

from nac_test._env import get_bool_env, get_positive_numeric_env


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

    def test_warns_on_invalid_value(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("NAC_TEST_TEST_VAR", "not_a_number")
        with caplog.at_level(logging.WARNING):
            result = get_positive_numeric_env("NAC_TEST_TEST_VAR", 42, int)
        assert result == 42
        assert "NAC_TEST_TEST_VAR=not_a_number" in caplog.text
        assert "not a valid int" in caplog.text

    def test_warns_on_non_positive_value(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("NAC_TEST_TEST_VAR", "-5")
        with caplog.at_level(logging.WARNING):
            result = get_positive_numeric_env("NAC_TEST_TEST_VAR", 42, int)
        assert result == 42
        assert "NAC_TEST_TEST_VAR=-5" in caplog.text
        assert "not positive" in caplog.text

    def test_no_warning_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("NAC_TEST_TEST_VAR", "invalid")
        with caplog.at_level(logging.WARNING):
            result = get_positive_numeric_env(
                "NAC_TEST_TEST_VAR", 42, int, warn_on_invalid=False
            )
        assert result == 42
        assert caplog.text == ""

    def test_no_warning_when_env_not_set(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            result = get_positive_numeric_env("NAC_TEST_UNSET_VAR", 99, int)
        assert result == 99
        assert caplog.text == ""


class TestGetBoolEnv:
    """Tests for get_bool_env()."""

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("yes", True),
            ("Yes", True),
            ("YES", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("no", False),
            ("0", False),
            ("", False),
            ("random", False),
        ],
    )
    def test_returns_expected(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
    ) -> None:
        monkeypatch.setenv("NAC_TEST_TEST_BOOL", env_value)
        assert get_bool_env("NAC_TEST_TEST_BOOL") == expected

    def test_returns_default_when_not_set(self) -> None:
        assert get_bool_env("NAC_TEST_UNSET_BOOL_VAR") is False
        assert get_bool_env("NAC_TEST_UNSET_BOOL_VAR", default=True) is True
