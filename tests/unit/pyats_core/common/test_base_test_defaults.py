# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for NACTestBase.get_default_value() method.

This module tests the defaults resolution wrapper method on NACTestBase,
which delegates to the defaults_resolver utility functions while providing
architecture-specific configuration through class attributes.

Test Structure:
    - TestNACTestBaseDefaults: Tests for the get_default_value() instance method
        - DEFAULTS_PREFIX handling (set vs None)
        - Custom error message usage
        - Subclass override behavior
        - Cascade behavior through the base class method
        - Optional (required=False) lookup behavior
"""

import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Mock PyATS before importing NACTestBase
# This is necessary because NACTestBase inherits from aetest.Testcase
_mock_aetest = MagicMock()
_mock_aetest.Testcase = object  # Make Testcase a simple object for inheritance
_mock_aetest.setup = lambda f: f  # Decorator that returns the function unchanged


@pytest.fixture(autouse=True)
def mock_pyats() -> Any:
    """Mock PyATS module to avoid import errors in test environment."""
    with patch.dict(
        "sys.modules", {"pyats": MagicMock(), "pyats.aetest": _mock_aetest}
    ):
        yield


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_data_model_file() -> Any:
    """Create a temporary data model file for tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"test": "data"}, f)
        temp_file = f.name
    yield temp_file
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def apic_data_model() -> dict[str, Any]:
    """Sample APIC data model with defaults block."""
    return {
        "defaults": {
            "apic": {
                "tenants": {
                    "l3outs": {
                        "nodes": {"pod": 1},
                        "bgp_peers": {"admin_state": "enabled"},
                    }
                },
                "fabric": {"name": "test-fabric"},
            }
        }
    }


@pytest.fixture
def sdwan_data_model() -> dict[str, Any]:
    """Sample SD-WAN data model with defaults block."""
    return {
        "defaults": {
            "sdwan": {
                "global": {"timeout": 30, "retry_count": 3},
                "device": {"os": "iosxe", "connection_timeout": 60},
                "features": {"bgp": {"enabled": True}, "ospf": {"area": 0}},
            }
        }
    }


# =============================================================================
# TestNACTestBaseDefaults
# =============================================================================


class TestNACTestBaseDefaults:
    """Integration tests for NACTestBase.get_default_value() method.

    These tests verify that the instance method on NACTestBase correctly
    delegates to the defaults_resolver utility while providing proper
    architecture-specific configuration.
    """

    def _create_test_instance(
        self,
        data_model: dict[str, Any],
        defaults_prefix: str | None = None,
        missing_error: str | None = None,
    ) -> Any:
        """Create a NACTestBase-like instance for testing.

        Since NACTestBase requires PyATS infrastructure, we create a minimal
        class that has the same get_default_value method implementation.

        Args:
            data_model: The data model to attach to the instance.
            defaults_prefix: DEFAULTS_PREFIX class attribute value.
            missing_error: DEFAULTS_MISSING_ERROR class attribute value.

        Returns:
            A test instance with the get_default_value method.
        """
        from nac_test.pyats_core.common.defaults_resolver import (
            get_default_value as _resolve,
        )

        class TestableNACTestBase:
            """Minimal testable version of NACTestBase defaults functionality."""

            DEFAULTS_PREFIX: str | None = defaults_prefix
            DEFAULTS_MISSING_ERROR: str = missing_error or (
                "Defaults block not found in data model. "
                "Ensure the defaults file is passed to nac-test."
            )

            def __init__(self, data: dict[str, Any]) -> None:
                self.data_model = data

            def get_default_value(
                self,
                *default_paths: str,
                required: bool = True,
            ) -> Any | None:
                """Read default value(s) from defaults block with cascade support."""
                if self.DEFAULTS_PREFIX is None:
                    raise NotImplementedError(
                        f"{self.__class__.__name__} does not support defaults resolution. "
                        f"Set DEFAULTS_PREFIX class attribute to enable this feature."
                    )

                return _resolve(
                    self.data_model,
                    *default_paths,
                    defaults_prefix=self.DEFAULTS_PREFIX,
                    missing_error=self.DEFAULTS_MISSING_ERROR,
                    required=required,
                )

        return TestableNACTestBase(data_model)

    def test_get_default_value_without_prefix_raises(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Test that get_default_value raises NotImplementedError when DEFAULTS_PREFIX is None."""
        instance = self._create_test_instance(
            data_model=apic_data_model,
            defaults_prefix=None,  # Explicitly no prefix
        )

        with pytest.raises(NotImplementedError) as exc_info:
            instance.get_default_value("fabric.name")

        error_message = str(exc_info.value)
        assert "does not support defaults resolution" in error_message
        assert "Set DEFAULTS_PREFIX" in error_message

    def test_get_default_value_with_prefix_set(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Test that get_default_value works when DEFAULTS_PREFIX is set."""
        instance = self._create_test_instance(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
        )

        result = instance.get_default_value("fabric.name")
        assert result == "test-fabric"

    def test_custom_error_message_used(self) -> None:
        """Test that class DEFAULTS_MISSING_ERROR is used when defaults block missing."""
        empty_data_model: dict[str, Any] = {}
        custom_error = "Custom APIC error: Please provide defaults.yaml file."

        instance = self._create_test_instance(
            data_model=empty_data_model,
            defaults_prefix="defaults.apic",
            missing_error=custom_error,
        )

        with pytest.raises(ValueError) as exc_info:
            instance.get_default_value("some.path")

        assert custom_error in str(exc_info.value)

    def test_subclass_overrides_prefix(
        self,
        apic_data_model: dict[str, Any],
        sdwan_data_model: dict[str, Any],
    ) -> None:
        """Test that subclass can set different prefix and error message."""
        # APIC subclass
        apic_instance = self._create_test_instance(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults required.",
        )

        # SD-WAN subclass
        sdwan_instance = self._create_test_instance(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults required.",
        )

        # Each should work with their respective data models
        apic_result = apic_instance.get_default_value("fabric.name")
        assert apic_result == "test-fabric"

        sdwan_result = sdwan_instance.get_default_value("global.timeout")
        assert sdwan_result == 30

    def test_cascade_behavior_through_base(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Test that cascade/fallback works through NACTestBase method."""
        instance = self._create_test_instance(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
        )

        # First path doesn't exist, should fall back to second
        result = instance.get_default_value(
            "nonexistent.timeout",
            "global.timeout",
        )
        assert result == 30

        # First path exists, should return that value
        result = instance.get_default_value(
            "global.timeout",
            "device.connection_timeout",
        )
        assert result == 30  # First path wins, not 60

    def test_required_false_returns_none(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Test that optional lookup returns None through base class."""
        instance = self._create_test_instance(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
        )

        result = instance.get_default_value(
            "nonexistent.path",
            required=False,
        )
        assert result is None

    def test_nested_path_lookup(self, apic_data_model: dict[str, Any]) -> None:
        """Test deeply nested path lookups work correctly."""
        instance = self._create_test_instance(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
        )

        result = instance.get_default_value("tenants.l3outs.nodes.pod")
        assert result == 1

        result = instance.get_default_value("tenants.l3outs.bgp_peers.admin_state")
        assert result == "enabled"

    def test_required_true_raises_for_missing(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Test that required=True (default) raises ValueError for missing values."""
        instance = self._create_test_instance(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
        )

        with pytest.raises(ValueError) as exc_info:
            instance.get_default_value("nonexistent.path")

        assert "Required default value not found" in str(exc_info.value)

    def test_cascade_all_missing_optional(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Test cascade with all paths missing and required=False returns None."""
        instance = self._create_test_instance(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
        )

        result = instance.get_default_value(
            "missing.path1",
            "missing.path2",
            "missing.path3",
            required=False,
        )
        assert result is None

    def test_falsy_values_returned_correctly(self) -> None:
        """Test that falsy values (False, 0, empty string) are returned correctly."""
        data_model: dict[str, Any] = {
            "defaults": {
                "apic": {
                    "settings": {
                        "enabled": False,
                        "count": 0,
                        "name": "",
                    }
                }
            }
        }

        instance = self._create_test_instance(
            data_model=data_model,
            defaults_prefix="defaults.apic",
        )

        # False should be returned, not treated as missing
        result = instance.get_default_value("settings.enabled")
        assert result is False

        # 0 should be returned, not treated as missing
        result = instance.get_default_value("settings.count")
        assert result == 0

        # Empty string should be returned, not treated as missing
        result = instance.get_default_value("settings.name")
        assert result == ""

    def test_dict_value_returned(self, apic_data_model: dict[str, Any]) -> None:
        """Test that dict values are returned correctly."""
        instance = self._create_test_instance(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
        )

        result = instance.get_default_value("tenants.l3outs.nodes")
        assert result == {"pod": 1}

    def test_no_paths_raises_type_error(self, sdwan_data_model: dict[str, Any]) -> None:
        """Test that calling with no paths raises TypeError."""
        instance = self._create_test_instance(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
        )

        with pytest.raises(TypeError, match="requires at least one default_path"):
            instance.get_default_value()
