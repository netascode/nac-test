# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for defaults_resolver module.

This module tests the pure utility functions for reading default values
from merged NAC data models. These functions use JMESPath for data model
traversal and are architecture-agnostic.

Test Structure:
    - TestEnsureDefaultsBlockExists: Tests for defaults block validation
    - TestGetDefaultValueSinglePath: Tests for single-path lookups
    - TestGetDefaultValueCascade: Tests for cascade/fallback behavior
    - TestGetDefaultValueErrorHandling: Tests for error conditions
    - TestArchitectureAgnostic: Tests for different architecture prefixes
"""

from typing import Any

import pytest

from nac_test.pyats_core.common.defaults_resolver import (
    ensure_defaults_block_exists,
    get_default_value,
)

# =============================================================================
# Fixtures
# =============================================================================


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


@pytest.fixture
def catc_data_model() -> dict[str, Any]:
    """Sample Catalyst Center data model with defaults block."""
    return {
        "defaults": {
            "catc": {
                "sites": {"area": "Global", "building": "Main"},
                "devices": {"role": "ACCESS", "family": "Switches and Hubs"},
            }
        }
    }


@pytest.fixture
def data_model_with_falsy_values() -> dict[str, Any]:
    """Data model containing falsy values that should be returned correctly."""
    return {
        "defaults": {
            "apic": {
                "settings": {
                    "enabled": False,
                    "count": 0,
                    "name": "",
                    "items": [],
                    "config": {},
                }
            }
        }
    }


@pytest.fixture
def deeply_nested_data_model() -> dict[str, Any]:
    """Data model with deeply nested structure."""
    return {
        "defaults": {
            "apic": {
                "level1": {
                    "level2": {
                        "level3": {"level4": {"level5": {"value": "deep-value"}}}
                    }
                }
            }
        }
    }


@pytest.fixture
def empty_data_model() -> dict[str, Any]:
    """Empty data model."""
    return {}


@pytest.fixture
def partial_data_model() -> dict[str, Any]:
    """Data model with defaults key but missing nested architecture key."""
    return {"defaults": {}}


# =============================================================================
# TestEnsureDefaultsBlockExists
# =============================================================================


class TestEnsureDefaultsBlockExists:
    """Tests for the ensure_defaults_block_exists function.

    This function validates that a defaults block exists in the data model
    before attempting to read any default values.
    """

    def test_valid_defaults_block_passes(self, apic_data_model: dict[str, Any]) -> None:
        """Should not raise with valid defaults block."""
        # Should not raise any exception
        ensure_defaults_block_exists(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults block missing.",
        )

    def test_missing_defaults_raises_value_error(
        self, empty_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError when no defaults key exists."""
        error_message = "APIC defaults block missing. Pass defaults.yaml to nac-test."

        with pytest.raises(ValueError, match="APIC defaults block missing"):
            ensure_defaults_block_exists(
                data_model=empty_data_model,
                defaults_prefix="defaults.apic",
                missing_error=error_message,
            )

    def test_missing_nested_block_raises_value_error(
        self, partial_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError when nested architecture key is missing."""
        error_message = "SD-WAN defaults block missing."

        with pytest.raises(ValueError, match="SD-WAN defaults block missing"):
            ensure_defaults_block_exists(
                data_model=partial_data_model,
                defaults_prefix="defaults.sdwan",
                missing_error=error_message,
            )

    def test_custom_prefix_apic(self, apic_data_model: dict[str, Any]) -> None:
        """Should work with defaults.apic prefix."""
        ensure_defaults_block_exists(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
            missing_error="Missing APIC defaults.",
        )

    def test_custom_prefix_sdwan(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should work with defaults.sdwan prefix."""
        ensure_defaults_block_exists(
            data_model=sdwan_data_model,
            defaults_prefix="defaults.sdwan",
            missing_error="Missing SD-WAN defaults.",
        )

    def test_custom_prefix_catc(self, catc_data_model: dict[str, Any]) -> None:
        """Should work with defaults.catc prefix."""
        ensure_defaults_block_exists(
            data_model=catc_data_model,
            defaults_prefix="defaults.catc",
            missing_error="Missing Catalyst Center defaults.",
        )

    def test_wrong_architecture_prefix_raises(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Should raise when architecture prefix does not match data model."""
        with pytest.raises(ValueError, match="SD-WAN defaults not found"):
            ensure_defaults_block_exists(
                data_model=apic_data_model,
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults not found.",
            )


# =============================================================================
# TestGetDefaultValueSinglePath
# =============================================================================


class TestGetDefaultValueSinglePath:
    """Tests for get_default_value with single path lookups.

    These tests verify that single-path lookups return the correct value
    or raise appropriate errors when values are not found.
    """

    def test_single_path_value_found(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should return correct value for single path lookup."""
        result = get_default_value(
            sdwan_data_model,
            "global.timeout",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        assert result == 30

    def test_single_path_nested_value(self, apic_data_model: dict[str, Any]) -> None:
        """Should work with deep nesting."""
        result = get_default_value(
            apic_data_model,
            "tenants.l3outs.nodes.pod",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == 1

    def test_single_path_deeply_nested_value(
        self, deeply_nested_data_model: dict[str, Any]
    ) -> None:
        """Should work with very deep nesting."""
        result = get_default_value(
            deeply_nested_data_model,
            "level1.level2.level3.level4.level5.value",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == "deep-value"

    def test_single_path_not_found_required_raises(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError when required value is missing."""
        with pytest.raises(ValueError, match="Required default value not found"):
            get_default_value(
                sdwan_data_model,
                "nonexistent.path",
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults missing.",
                required=True,
            )

    def test_single_path_not_found_optional_returns_none(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return None when optional value is missing."""
        result = get_default_value(
            sdwan_data_model,
            "nonexistent.path",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
            required=False,
        )

        assert result is None

    def test_falsy_value_false_returned(
        self, data_model_with_falsy_values: dict[str, Any]
    ) -> None:
        """Should return False correctly (not treated as None)."""
        result = get_default_value(
            data_model_with_falsy_values,
            "settings.enabled",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result is False

    def test_falsy_value_zero_returned(
        self, data_model_with_falsy_values: dict[str, Any]
    ) -> None:
        """Should return 0 correctly (not treated as None)."""
        result = get_default_value(
            data_model_with_falsy_values,
            "settings.count",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == 0

    def test_falsy_value_empty_string_returned(
        self, data_model_with_falsy_values: dict[str, Any]
    ) -> None:
        """Should return empty string correctly (not treated as None)."""
        result = get_default_value(
            data_model_with_falsy_values,
            "settings.name",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == ""

    def test_falsy_value_empty_list_returned(
        self, data_model_with_falsy_values: dict[str, Any]
    ) -> None:
        """Should return empty list correctly (not treated as None)."""
        result = get_default_value(
            data_model_with_falsy_values,
            "settings.items",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == []

    def test_falsy_value_empty_dict_returned(
        self, data_model_with_falsy_values: dict[str, Any]
    ) -> None:
        """Should return empty dict correctly (not treated as None)."""
        result = get_default_value(
            data_model_with_falsy_values,
            "settings.config",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == {}

    def test_returns_dict_value(self, apic_data_model: dict[str, Any]) -> None:
        """Should return nested dict values."""
        result = get_default_value(
            apic_data_model,
            "tenants.l3outs.nodes",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == {"pod": 1}

    def test_returns_string_value(self, apic_data_model: dict[str, Any]) -> None:
        """Should return string values."""
        result = get_default_value(
            apic_data_model,
            "tenants.l3outs.bgp_peers.admin_state",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == "enabled"


# =============================================================================
# TestGetDefaultValueCascade
# =============================================================================


class TestGetDefaultValueCascade:
    """Tests for get_default_value with cascade/fallback behavior.

    These tests verify that multiple paths are tried in order and the
    first non-None value is returned.
    """

    def test_cascade_returns_first_found(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return first non-None value in cascade."""
        result = get_default_value(
            sdwan_data_model,
            "global.timeout",
            "device.connection_timeout",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        # First path exists, should return 30 (not 60)
        assert result == 30

    def test_cascade_skips_none_values(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should continue searching if first path returns None."""
        result = get_default_value(
            sdwan_data_model,
            "nonexistent.timeout",
            "global.timeout",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        # First path doesn't exist, should fall back to second path
        assert result == 30

    def test_cascade_returns_second_path(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return second path value when first is None."""
        result = get_default_value(
            sdwan_data_model,
            "missing.value",
            "device.os",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        assert result == "iosxe"

    def test_cascade_returns_third_path(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should return third path value when first two are None."""
        result = get_default_value(
            sdwan_data_model,
            "missing.first",
            "missing.second",
            "global.retry_count",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        assert result == 3

    def test_cascade_all_missing_required_raises(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError if all paths missing and required."""
        with pytest.raises(ValueError, match="Required default value not found"):
            get_default_value(
                sdwan_data_model,
                "missing.path1",
                "missing.path2",
                "missing.path3",
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults missing.",
                required=True,
            )

    def test_cascade_all_missing_optional_returns_none(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return None if all paths missing and optional."""
        result = get_default_value(
            sdwan_data_model,
            "missing.path1",
            "missing.path2",
            "missing.path3",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
            required=False,
        )

        assert result is None

    def test_cascade_with_many_paths(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should handle many cascade paths correctly."""
        result = get_default_value(
            sdwan_data_model,
            "missing.a",
            "missing.b",
            "missing.c",
            "missing.d",
            "missing.e",
            "features.bgp.enabled",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        assert result is True


# =============================================================================
# TestGetDefaultValueErrorHandling
# =============================================================================


class TestGetDefaultValueErrorHandling:
    """Tests for error handling in get_default_value.

    These tests verify that appropriate errors are raised for invalid
    inputs and that error messages are helpful.
    """

    def test_no_paths_raises_type_error(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should raise TypeError if no paths are provided."""
        with pytest.raises(
            TypeError, match="requires at least one default_path argument"
        ):
            get_default_value(
                sdwan_data_model,
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults missing.",
            )

    def test_missing_defaults_block_raises(
        self, empty_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError if defaults block is missing."""
        with pytest.raises(ValueError, match="Defaults block not found"):
            get_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.apic",
                missing_error="Defaults block not found.",
            )

    def test_error_message_includes_single_path(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Error message should show attempted path for single path lookup."""
        with pytest.raises(ValueError) as exc_info:
            get_default_value(
                sdwan_data_model,
                "nonexistent.setting",
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults missing.",
            )

        error_message = str(exc_info.value)
        assert "defaults.sdwan.nonexistent.setting" in error_message

    def test_error_message_includes_multiple_paths(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Error message should show all attempted paths for cascade lookup."""
        with pytest.raises(ValueError) as exc_info:
            get_default_value(
                sdwan_data_model,
                "missing.path1",
                "missing.path2",
                "missing.path3",
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults missing.",
            )

        error_message = str(exc_info.value)
        assert "defaults.sdwan.missing.path1" in error_message
        assert "defaults.sdwan.missing.path2" in error_message
        assert "defaults.sdwan.missing.path3" in error_message
        assert "Tried paths in order" in error_message

    def test_custom_missing_error_used(self, empty_data_model: dict[str, Any]) -> None:
        """Custom error message should be used when defaults block is missing."""
        custom_error = "Custom error: Please provide defaults.yaml file."

        with pytest.raises(ValueError, match="Custom error"):
            get_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.apic",
                missing_error=custom_error,
            )

    def test_none_data_model_raises(self) -> None:
        """Should raise ValueError for None data model (treated as missing defaults)."""
        with pytest.raises(ValueError, match="Missing defaults"):
            get_default_value(
                None,  # type: ignore[arg-type]
                "some.path",
                defaults_prefix="defaults.apic",
                missing_error="Missing defaults.",
            )


# =============================================================================
# TestArchitectureAgnostic
# =============================================================================


class TestArchitectureAgnostic:
    """Tests verifying architecture-agnostic behavior.

    These tests ensure the functions work correctly with different
    architecture prefixes (APIC, SD-WAN, Catalyst Center).
    """

    def test_apic_prefix(self, apic_data_model: dict[str, Any]) -> None:
        """Should work with defaults.apic prefix."""
        result = get_default_value(
            apic_data_model,
            "fabric.name",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == "test-fabric"

    def test_sdwan_prefix(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should work with defaults.sdwan prefix."""
        result = get_default_value(
            sdwan_data_model,
            "device.os",
            defaults_prefix="defaults.sdwan",
            missing_error="SD-WAN defaults missing.",
        )

        assert result == "iosxe"

    def test_catc_prefix(self, catc_data_model: dict[str, Any]) -> None:
        """Should work with defaults.catc prefix."""
        result = get_default_value(
            catc_data_model,
            "sites.area",
            defaults_prefix="defaults.catc",
            missing_error="Catalyst Center defaults missing.",
        )

        assert result == "Global"

    def test_custom_architecture_prefix(self) -> None:
        """Should work with custom architecture prefix."""
        custom_data_model: dict[str, Any] = {
            "defaults": {"custom_arch": {"setting": {"value": "custom-value"}}}
        }

        result = get_default_value(
            custom_data_model,
            "setting.value",
            defaults_prefix="defaults.custom_arch",
            missing_error="Custom architecture defaults missing.",
        )

        assert result == "custom-value"

    def test_custom_error_message_apic(self, empty_data_model: dict[str, Any]) -> None:
        """Custom error messages should be used for APIC."""
        custom_error = "APIC defaults not found. Please pass defaults.yaml to nac-test."

        with pytest.raises(ValueError) as exc_info:
            get_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.apic",
                missing_error=custom_error,
            )

        assert custom_error in str(exc_info.value)

    def test_custom_error_message_sdwan(self, empty_data_model: dict[str, Any]) -> None:
        """Custom error messages should be used for SD-WAN."""
        custom_error = "SD-WAN defaults not configured. Check your data directory."

        with pytest.raises(ValueError) as exc_info:
            get_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.sdwan",
                missing_error=custom_error,
            )

        assert custom_error in str(exc_info.value)

    def test_custom_error_message_catc(self, empty_data_model: dict[str, Any]) -> None:
        """Custom error messages should be used for Catalyst Center."""
        custom_error = "Catalyst Center defaults file is required."

        with pytest.raises(ValueError) as exc_info:
            get_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.catc",
                missing_error=custom_error,
            )

        assert custom_error in str(exc_info.value)


# =============================================================================
# TestEdgeCases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions.

    These tests cover unusual but valid inputs and ensure robust behavior.
    """

    def test_single_level_path(self) -> None:
        """Should work with single-level path."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"timeout": 30}}}

        result = get_default_value(
            data_model,
            "timeout",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == 30

    def test_path_with_special_characters_in_keys(self) -> None:
        """Should handle keys with underscores and numbers."""
        data_model: dict[str, Any] = {
            "defaults": {"apic": {"config_v2": {"setting_1": {"value_2": "test"}}}}
        }

        result = get_default_value(
            data_model,
            "config_v2.setting_1.value_2",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == "test"

    def test_data_model_with_none_value(self) -> None:
        """Should treat explicit None value as not found."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"setting": None}}}

        result = get_default_value(
            data_model,
            "setting",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
            required=False,
        )

        # Explicit None is treated as "not found"
        assert result is None

    def test_data_model_with_none_value_required(self) -> None:
        """Should raise for explicit None when required."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"setting": None}}}

        with pytest.raises(ValueError, match="Required default value not found"):
            get_default_value(
                data_model,
                "setting",
                defaults_prefix="defaults.apic",
                missing_error="APIC defaults missing.",
                required=True,
            )

    def test_list_value_returned(self) -> None:
        """Should return list values correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"ports": [80, 443, 8080]}}}

        result = get_default_value(
            data_model,
            "ports",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == [80, 443, 8080]

    def test_boolean_true_value(self) -> None:
        """Should return True correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"enabled": True}}}

        result = get_default_value(
            data_model,
            "enabled",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result is True

    def test_float_value(self) -> None:
        """Should return float values correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"threshold": 0.95}}}

        result = get_default_value(
            data_model,
            "threshold",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == 0.95

    def test_negative_number(self) -> None:
        """Should return negative numbers correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"offset": -10}}}

        result = get_default_value(
            data_model,
            "offset",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == -10

    def test_large_nested_structure(self) -> None:
        """Should handle large nested structures."""
        data_model: dict[str, Any] = {
            "defaults": {
                "apic": {
                    "tenants": {
                        f"tenant_{i}": {
                            "vrfs": {f"vrf_{j}": {"id": j} for j in range(10)}
                        }
                        for i in range(10)
                    }
                }
            }
        }

        result = get_default_value(
            data_model,
            "tenants.tenant_5.vrfs.vrf_7.id",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert result == 7

    def test_required_defaults_to_true(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should default required parameter to True."""
        # Not passing required parameter should behave as required=True
        with pytest.raises(ValueError, match="Required default value not found"):
            get_default_value(
                sdwan_data_model,
                "nonexistent.path",
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults missing.",
            )

    def test_ensure_defaults_preserves_original_data(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Ensure defaults block check does not modify data model."""
        import copy

        original = copy.deepcopy(apic_data_model)

        ensure_defaults_block_exists(
            data_model=apic_data_model,
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert apic_data_model == original

    def test_get_default_value_preserves_original_data(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Ensure get_default_value does not modify data model."""
        import copy

        original = copy.deepcopy(apic_data_model)

        get_default_value(
            apic_data_model,
            "fabric.name",
            defaults_prefix="defaults.apic",
            missing_error="APIC defaults missing.",
        )

        assert apic_data_model == original
