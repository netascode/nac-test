# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for environment validation utilities."""

import pytest
from _pytest.monkeypatch import MonkeyPatch

from nac_test.utils.environment import EnvironmentValidator


class TestGetMissingControllerVars:
    """Tests for EnvironmentValidator.get_missing_controller_vars()."""

    def test_unknown_controller_type_raises_error(self) -> None:
        """Verify ValueError is raised for unknown controller types."""
        with pytest.raises(ValueError, match="Unknown controller type: UNKNOWN"):
            EnvironmentValidator.get_missing_controller_vars("UNKNOWN")

    def test_returns_all_vars_when_none_set(
        self, clean_controller_env: None, monkeypatch: MonkeyPatch
    ) -> None:
        """Verify all vars returned as missing when none are set."""
        missing = EnvironmentValidator.get_missing_controller_vars("ACI")
        assert missing == ["ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"]

    def test_returns_empty_when_all_vars_set(
        self, clean_controller_env: None, monkeypatch: MonkeyPatch
    ) -> None:
        """Verify empty list returned when all vars are set."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")
        missing = EnvironmentValidator.get_missing_controller_vars("ACI")
        assert missing == []

    def test_returns_partial_missing_vars(
        self, clean_controller_env: None, monkeypatch: MonkeyPatch
    ) -> None:
        """Verify only missing vars returned when some are set."""
        monkeypatch.setenv("SDWAN_URL", "https://sdwan.test.com")
        missing = EnvironmentValidator.get_missing_controller_vars("SDWAN")
        assert missing == ["SDWAN_USERNAME", "SDWAN_PASSWORD"]
