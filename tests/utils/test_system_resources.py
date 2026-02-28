# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for system_resources module environment variable handling."""

import pytest

from nac_test.utils.system_resources import SystemResourceCalculator


class TestWorkerCapacityEnvVar:
    """Tests for NAC_TEST_PYATS_PROCESSES environment variable override."""

    def test_env_var_override_worker_capacity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that NAC_TEST_PYATS_PROCESSES overrides calculated worker capacity."""
        monkeypatch.setenv("NAC_TEST_PYATS_PROCESSES", "42")

        result = SystemResourceCalculator.calculate_worker_capacity()

        assert result == 42

    def test_invalid_env_var_falls_back_to_calculated(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that invalid env var value logs warning and uses calculated value."""
        monkeypatch.setenv("NAC_TEST_PYATS_PROCESSES", "not_a_number")

        result = SystemResourceCalculator.calculate_worker_capacity()

        assert result >= 1
        assert "Invalid NAC_TEST_PYATS_PROCESSES value" in caplog.text


class TestConnectionCapacityEnvVar:
    """Tests for NAC_TEST_PYATS_MAX_CONNECTIONS environment variable override."""

    def test_env_var_override_connection_capacity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that NAC_TEST_PYATS_MAX_CONNECTIONS overrides calculated capacity."""
        monkeypatch.setenv("NAC_TEST_PYATS_MAX_CONNECTIONS", "500")

        result = SystemResourceCalculator.calculate_connection_capacity()

        assert result == 500

    def test_invalid_env_var_falls_back_to_calculated(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that invalid env var value logs warning and uses calculated value."""
        monkeypatch.setenv("NAC_TEST_PYATS_MAX_CONNECTIONS", "invalid")

        result = SystemResourceCalculator.calculate_connection_capacity()

        assert result >= 1
        assert "Invalid NAC_TEST_PYATS_MAX_CONNECTIONS value" in caplog.text
