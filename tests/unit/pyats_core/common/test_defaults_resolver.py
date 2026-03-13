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
    resolve_default_value,
)

# =============================================================================
# Fixtures (apic_data_model and sdwan_data_model are in conftest.py)
# =============================================================================


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
            missing_error="APIC defaults file required.",
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

    @pytest.mark.parametrize(
        "fixture_name,prefix",
        [
            pytest.param("apic_data_model", "defaults.apic", id="apic"),
            pytest.param("sdwan_data_model", "defaults.sdwan", id="sdwan"),
            pytest.param("catc_data_model", "defaults.catc", id="catc"),
        ],
    )
    def test_architecture_prefix_validates(
        self,
        fixture_name: str,
        prefix: str,
        apic_data_model: dict[str, Any],
        sdwan_data_model: dict[str, Any],
        catc_data_model: dict[str, Any],
    ) -> None:
        """Should work with each architecture's defaults prefix."""
        fixtures = {
            "apic_data_model": apic_data_model,
            "sdwan_data_model": sdwan_data_model,
            "catc_data_model": catc_data_model,
        }
        ensure_defaults_block_exists(
            data_model=fixtures[fixture_name],
            defaults_prefix=prefix,
            missing_error=f"{prefix.split('.')[1].upper()} defaults file required.",
        )

    def test_wrong_architecture_prefix_raises(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Should raise when architecture prefix does not match data model."""
        with pytest.raises(ValueError, match="SD-WAN defaults not found"):
            ensure_defaults_block_exists(
                data_model=apic_data_model,
                defaults_prefix="defaults.sdwan",
                missing_error="SD-WAN defaults not found",
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
        result = resolve_default_value(
            sdwan_data_model,
            "global.timeout",
            defaults_prefix="defaults.sdwan",
        )

        assert result == 30

    def test_single_path_nested_value(self, apic_data_model: dict[str, Any]) -> None:
        """Should work with deep nesting."""
        result = resolve_default_value(
            apic_data_model,
            "tenants.l3outs.nodes.pod",
            defaults_prefix="defaults.apic",
        )

        assert result == 1

    def test_single_path_deeply_nested_value(
        self, deeply_nested_data_model: dict[str, Any]
    ) -> None:
        """Should work with very deep nesting."""
        result = resolve_default_value(
            deeply_nested_data_model,
            "level1.level2.level3.level4.level5.value",
            defaults_prefix="defaults.apic",
        )

        assert result == "deep-value"

    def test_single_path_not_found_required_raises(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError when required value is missing."""
        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                sdwan_data_model,
                "nonexistent.path",
                defaults_prefix="defaults.sdwan",
                required=True,
            )

    def test_single_path_not_found_optional_returns_none(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return None when optional value is missing."""
        result = resolve_default_value(
            sdwan_data_model,
            "nonexistent.path",
            defaults_prefix="defaults.sdwan",
            required=False,
        )

        assert result is None

    @pytest.mark.parametrize(
        "path,expected_value",
        [
            pytest.param("settings.enabled", False, id="false"),
            pytest.param("settings.count", 0, id="zero"),
            pytest.param("settings.name", "", id="empty-string"),
            pytest.param("settings.items", [], id="empty-list"),
            pytest.param("settings.config", {}, id="empty-dict"),
        ],
    )
    def test_falsy_value_returned_correctly(
        self,
        data_model_with_falsy_values: dict[str, Any],
        path: str,
        expected_value: Any,
    ) -> None:
        """Should return falsy values correctly (not treated as None)."""
        result = resolve_default_value(
            data_model_with_falsy_values,
            path,
            defaults_prefix="defaults.apic",
        )

        assert result == expected_value

    def test_returns_dict_value(self, apic_data_model: dict[str, Any]) -> None:
        """Should return nested dict values."""
        result = resolve_default_value(
            apic_data_model,
            "tenants.l3outs.nodes",
            defaults_prefix="defaults.apic",
        )

        assert result == {"pod": 1}

    def test_returns_string_value(self, apic_data_model: dict[str, Any]) -> None:
        """Should return string values."""
        result = resolve_default_value(
            apic_data_model,
            "tenants.l3outs.bgp_peers.admin_state",
            defaults_prefix="defaults.apic",
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
        result = resolve_default_value(
            sdwan_data_model,
            "global.timeout",
            "device.connection_timeout",
            defaults_prefix="defaults.sdwan",
        )

        # First path exists, should return 30 (not 60)
        assert result == 30

    def test_cascade_skips_none_values(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should continue searching if first path returns None."""
        result = resolve_default_value(
            sdwan_data_model,
            "nonexistent.timeout",
            "global.timeout",
            defaults_prefix="defaults.sdwan",
        )

        # First path doesn't exist, should fall back to second path
        assert result == 30

    def test_cascade_returns_second_path(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return second path value when first is None."""
        result = resolve_default_value(
            sdwan_data_model,
            "missing.value",
            "device.os",
            defaults_prefix="defaults.sdwan",
        )

        assert result == "iosxe"

    def test_cascade_returns_third_path(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should return third path value when first two are None."""
        result = resolve_default_value(
            sdwan_data_model,
            "missing.first",
            "missing.second",
            "global.retry_count",
            defaults_prefix="defaults.sdwan",
        )

        assert result == 3

    def test_cascade_all_missing_required_raises(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError if all paths missing and required."""
        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                sdwan_data_model,
                "missing.path1",
                "missing.path2",
                "missing.path3",
                defaults_prefix="defaults.sdwan",
                required=True,
            )

    def test_cascade_all_missing_optional_returns_none(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Should return None if all paths missing and optional."""
        result = resolve_default_value(
            sdwan_data_model,
            "missing.path1",
            "missing.path2",
            "missing.path3",
            defaults_prefix="defaults.sdwan",
            required=False,
        )

        assert result is None

    def test_cascade_with_many_paths(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should handle many cascade paths correctly."""
        result = resolve_default_value(
            sdwan_data_model,
            "missing.a",
            "missing.b",
            "missing.c",
            "missing.d",
            "missing.e",
            "features.bgp.enabled",
            defaults_prefix="defaults.sdwan",
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
            resolve_default_value(
                sdwan_data_model,
                defaults_prefix="defaults.sdwan",
            )

    def test_missing_defaults_block_raises(
        self, empty_data_model: dict[str, Any]
    ) -> None:
        """Should raise ValueError if defaults block is missing (value not found).

        Note: CLI validators ensure defaults exist before tests run. This test
        validates the error message when a value lookup fails (which will happen
        if the entire defaults block is missing).
        """
        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.apic",
            )

    def test_error_message_includes_single_path(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Error message should show attempted path for single path lookup."""
        with pytest.raises(ValueError) as exc_info:
            resolve_default_value(
                sdwan_data_model,
                "nonexistent.setting",
                defaults_prefix="defaults.sdwan",
            )

        error_message = str(exc_info.value)
        assert "defaults.sdwan.nonexistent.setting" in error_message

    def test_error_message_includes_multiple_paths(
        self, sdwan_data_model: dict[str, Any]
    ) -> None:
        """Error message should show all attempted paths for cascade lookup."""
        with pytest.raises(ValueError) as exc_info:
            resolve_default_value(
                sdwan_data_model,
                "missing.path1",
                "missing.path2",
                "missing.path3",
                defaults_prefix="defaults.sdwan",
            )

        error_message = str(exc_info.value)
        assert "defaults.sdwan.missing.path1" in error_message
        assert "defaults.sdwan.missing.path2" in error_message
        assert "defaults.sdwan.missing.path3" in error_message
        assert "Tried paths in order" in error_message

    def test_custom_missing_error_used(self, empty_data_model: dict[str, Any]) -> None:
        """Error message should show path not found (CLI validators ensure defaults exist).

        Note: The missing_error parameter is no longer used for defaults block
        validation (CLI validators handle that). This test verifies the behavior
        when a value is not found in an empty data model.
        """
        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix="defaults.apic",
            )

    def test_none_data_model_raises(self) -> None:
        """Should raise ValueError for None data model (value not found).

        Note: CLI validators ensure defaults exist. This test verifies behavior
        when data_model is None (JMESPath will return None for any path search).
        """
        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                None,  # type: ignore[arg-type]
                "some.path",
                defaults_prefix="defaults.apic",
            )


# =============================================================================
# TestArchitectureAgnostic
# =============================================================================


class TestArchitectureAgnostic:
    """Tests verifying architecture-agnostic behavior.

    These tests ensure the functions work correctly with different
    architecture prefixes (APIC, SD-WAN, Catalyst Center).
    """

    @pytest.mark.parametrize(
        "fixture_name,prefix,path,expected_value",
        [
            pytest.param(
                "apic_data_model",
                "defaults.apic",
                "fabric.name",
                "test-fabric",
                id="apic",
            ),
            pytest.param(
                "sdwan_data_model", "defaults.sdwan", "device.os", "iosxe", id="sdwan"
            ),
            pytest.param(
                "catc_data_model", "defaults.catc", "sites.area", "Global", id="catc"
            ),
        ],
    )
    def test_architecture_prefix_resolves_value(
        self,
        fixture_name: str,
        prefix: str,
        path: str,
        expected_value: str,
        apic_data_model: dict[str, Any],
        sdwan_data_model: dict[str, Any],
        catc_data_model: dict[str, Any],
    ) -> None:
        """Should work with each architecture's defaults prefix."""
        fixtures = {
            "apic_data_model": apic_data_model,
            "sdwan_data_model": sdwan_data_model,
            "catc_data_model": catc_data_model,
        }
        result = resolve_default_value(
            fixtures[fixture_name],
            path,
            defaults_prefix=prefix,
        )

        assert result == expected_value

    def test_custom_architecture_prefix(self) -> None:
        """Should work with custom architecture prefix."""
        custom_data_model: dict[str, Any] = {
            "defaults": {"custom_arch": {"setting": {"value": "custom-value"}}}
        }

        result = resolve_default_value(
            custom_data_model,
            "setting.value",
            defaults_prefix="defaults.custom_arch",
        )

        assert result == "custom-value"

    @pytest.mark.parametrize(
        "prefix",
        [
            pytest.param("defaults.apic", id="apic"),
            pytest.param("defaults.sdwan", id="sdwan"),
            pytest.param("defaults.catc", id="catc"),
        ],
    )
    def test_error_message_includes_prefix(
        self, empty_data_model: dict[str, Any], prefix: str
    ) -> None:
        """Should raise value not found error with prefix in message.

        Note: CLI validators handle defaults block validation. This test verifies
        the error message when a value is not found.
        """
        with pytest.raises(ValueError) as exc_info:
            resolve_default_value(
                empty_data_model,
                "some.path",
                defaults_prefix=prefix,
            )

        assert "Required default value not found" in str(exc_info.value)
        assert f"{prefix}.some.path" in str(exc_info.value)


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

        result = resolve_default_value(
            data_model,
            "timeout",
            defaults_prefix="defaults.apic",
        )

        assert result == 30

    def test_path_with_special_characters_in_keys(self) -> None:
        """Should handle keys with underscores and numbers."""
        data_model: dict[str, Any] = {
            "defaults": {"apic": {"config_v2": {"setting_1": {"value_2": "test"}}}}
        }

        result = resolve_default_value(
            data_model,
            "config_v2.setting_1.value_2",
            defaults_prefix="defaults.apic",
        )

        assert result == "test"

    def test_data_model_with_none_value(self) -> None:
        """Should treat explicit None value as not found."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"setting": None}}}

        result = resolve_default_value(
            data_model,
            "setting",
            defaults_prefix="defaults.apic",
            required=False,
        )

        # Explicit None is treated as "not found"
        assert result is None

    def test_data_model_with_none_value_required(self) -> None:
        """Should raise for explicit None when required."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"setting": None}}}

        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                data_model,
                "setting",
                defaults_prefix="defaults.apic",
                required=True,
            )

    def test_list_value_returned(self) -> None:
        """Should return list values correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"ports": [80, 443, 8080]}}}

        result = resolve_default_value(
            data_model,
            "ports",
            defaults_prefix="defaults.apic",
        )

        assert result == [80, 443, 8080]

    def test_boolean_true_value(self) -> None:
        """Should return True correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"enabled": True}}}

        result = resolve_default_value(
            data_model,
            "enabled",
            defaults_prefix="defaults.apic",
        )

        assert result is True

    def test_float_value(self) -> None:
        """Should return float values correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"threshold": 0.95}}}

        result = resolve_default_value(
            data_model,
            "threshold",
            defaults_prefix="defaults.apic",
        )

        assert result == 0.95

    def test_negative_number(self) -> None:
        """Should return negative numbers correctly."""
        data_model: dict[str, Any] = {"defaults": {"apic": {"offset": -10}}}

        result = resolve_default_value(
            data_model,
            "offset",
            defaults_prefix="defaults.apic",
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

        result = resolve_default_value(
            data_model,
            "tenants.tenant_5.vrfs.vrf_7.id",
            defaults_prefix="defaults.apic",
        )

        assert result == 7

    def test_required_defaults_to_true(self, sdwan_data_model: dict[str, Any]) -> None:
        """Should default required parameter to True."""
        # Not passing required parameter should behave as required=True
        with pytest.raises(ValueError, match="Required default value not found"):
            resolve_default_value(
                sdwan_data_model,
                "nonexistent.path",
                defaults_prefix="defaults.sdwan",
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
            missing_error="APIC defaults file required.",
        )

        assert apic_data_model == original

    def test_malformed_jmespath_expression_propagates(self) -> None:
        """Malformed JMESPath expressions propagate as jmespath exceptions.

        The defaults_resolver intentionally does NOT catch JMESPath parse
        errors — they indicate a programming error in the caller (wrong
        path syntax), not a missing value. Letting the ParseError propagate
        gives developers an immediate, clear traceback pointing at the
        malformed expression rather than a misleading "value not found".
        """
        import jmespath.exceptions

        data_model: dict[str, Any] = {"defaults": {"apic": {"key": "value"}}}

        with pytest.raises(jmespath.exceptions.ParseError):
            resolve_default_value(
                data_model,
                "[invalid",
                defaults_prefix="defaults.apic",
            )

    def test_get_default_value_preserves_original_data(
        self, apic_data_model: dict[str, Any]
    ) -> None:
        """Ensure get_default_value does not modify data model."""
        import copy

        original = copy.deepcopy(apic_data_model)

        resolve_default_value(
            apic_data_model,
            "fabric.name",
            defaults_prefix="defaults.apic",
        )

        assert apic_data_model == original

    def test_empty_string_path_raises_jmespath_error(self) -> None:
        """Empty string path produces a malformed JMESPath and raises ParseError.

        When an empty string "" is passed as a default_path, the full
        JMESPath expression becomes "defaults.apic." (trailing dot),
        which is syntactically invalid. JMESPath raises a ParseError.

        This test documents the behavior so callers know that passing
        an empty path is not silently treated as "root lookup" — it is
        a hard error, which is the correct behavior since an empty path
        is almost certainly a bug at the call site.
        """
        import jmespath.exceptions

        data_model: dict[str, Any] = {"defaults": {"apic": {"key": "value"}}}

        # Empty path becomes "defaults.apic." which is invalid JMESPath
        with pytest.raises(jmespath.exceptions.ParseError):
            resolve_default_value(
                data_model,
                "",
                defaults_prefix="defaults.apic",
            )
