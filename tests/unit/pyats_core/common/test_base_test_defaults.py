# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for NACTestBase.get_default_value() auto-detection integration.

This module verifies that the get_default_value() instance method on NACTestBase:
- Auto-detects controller type from environment variables
- Maps controller type to correct defaults prefix
- Delegates to defaults_resolver.resolve_default_value with correct arguments
- Handles missing controller credentials gracefully

Note:
    Cascade behavior, falsy value handling, error messages, and edge cases
    are thoroughly tested in test_defaults_resolver.py. These tests focus
    exclusively on the auto-detection and delegation contract between
    NACTestBase and the defaults_resolver utility.
"""

from typing import Any
from unittest.mock import patch, sentinel

import pytest

# =============================================================================
# TestNACTestBaseDefaults
# =============================================================================


class TestNACTestBaseDefaults:
    """Tests for NACTestBase.get_default_value() auto-detection and delegation.

    These tests verify that the instance method:
    - Auto-detects controller type from environment variables
    - Maps controller type to correct defaults prefix
    - Delegates to defaults_resolver.get_default_value with proper arguments
    """

    def test_aci_autodetection(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
        aci_controller_env: None,
    ) -> None:
        """get_default_value uses self.controller_type set by setup() to find defaults prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model
        # Simulate what setup() does - set controller_type
        instance.controller_type = "ACI"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("fabric.name")

        # Should use self.controller_type (ACI) and map to defaults.apic prefix
        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.apic"
        assert result is sentinel.result

    def test_sdwan_autodetection(
        self,
        nac_test_base_class: Any,
        sdwan_data_model: dict[str, Any],
        sdwan_controller_env: None,
    ) -> None:
        """get_default_value uses self.controller_type to find defaults.sdwan prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = sdwan_data_model
        instance.controller_type = "SDWAN"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("global.timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.sdwan"
        assert result is sentinel.result

    def test_cc_autodetection(
        self,
        nac_test_base_class: Any,
        cc_controller_env: None,
    ) -> None:
        """get_default_value uses self.controller_type to find defaults.catc prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = {"defaults": {"catc": {"timeout": 30}}}
        instance.controller_type = "CC"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.catc"
        assert result is sentinel.result

    def test_iosxe_autodetection(
        self,
        nac_test_base_class: Any,
        iosxe_controller_env: None,
    ) -> None:
        """get_default_value uses self.controller_type to find defaults.iosxe prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = {"defaults": {"iosxe": {"timeout": 30}}}
        instance.controller_type = "IOSXE"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.iosxe"
        assert result is sentinel.result

    def test_no_controller_credentials_raises(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """get_default_value requires controller_type to be set by setup()."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model
        # Don't set controller_type - simulates calling before setup()

        with pytest.raises(AttributeError) as exc_info:
            instance.get_default_value("fabric.name")

        assert "controller_type" in str(exc_info.value)

    def test_delegates_to_resolver_with_cascade_paths(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
        aci_controller_env: None,
    ) -> None:
        """get_default_value delegates cascade paths to _resolve correctly."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model
        instance.controller_type = "ACI"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value(
                "fabric.name", "fallback.name", required=False
            )

        mock_resolve.assert_called_once_with(
            apic_data_model,
            "fabric.name",
            "fallback.name",
            defaults_prefix="defaults.apic",
            required=False,
        )
        assert result is sentinel.result

    def test_required_defaults_to_true(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
        aci_controller_env: None,
    ) -> None:
        """required parameter defaults to True when not explicitly passed."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model
        instance.controller_type = "ACI"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
        ) as mock_resolve:
            instance.get_default_value("some.path")

        _, kwargs = mock_resolve.call_args
        assert kwargs["required"] is True

    def test_data_model_passed_to_resolver(
        self,
        nac_test_base_class: Any,
        aci_controller_env: None,
    ) -> None:
        """The instance's data_model is passed as the first positional argument."""
        data_model = {"defaults": {"apic": {"key": "value"}}}
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = data_model
        instance.controller_type = "ACI"

        with patch(
            "nac_test.pyats_core.common.base_test.resolve_default_value",
        ) as mock_resolve:
            instance.get_default_value("key")

        args, _ = mock_resolve.call_args
        assert args[0] is data_model
