# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for NACTestBase.get_default_value() auto-detection integration.

This module verifies that the get_default_value() instance method on NACTestBase:
- Auto-detects controller type from environment variables
- Maps controller type to correct defaults prefix
- Delegates to defaults_resolver.get_default_value with correct arguments
- Handles missing controller credentials gracefully

Note:
    Cascade behavior, falsy value handling, error messages, and edge cases
    are thoroughly tested in test_defaults_resolver.py. These tests focus
    exclusively on the auto-detection and delegation contract between
    NACTestBase and the defaults_resolver utility.
"""

from typing import Any
from unittest.mock import MagicMock, patch, sentinel

import pytest

# Mock PyATS before importing NACTestBase
# This is necessary because NACTestBase inherits from aetest.Testcase
# and step_interceptor imports from pyats.aetest.steps.implementation.
# The mock hierarchy must be wired so `from pyats import aetest` resolves
# the same mock that `import pyats.aetest` would.
_mock_aetest = MagicMock()
_mock_aetest.Testcase = object  # Make Testcase a simple object for inheritance
_mock_aetest.setup = lambda f: f  # Decorator that returns the function unchanged
_mock_aetest_steps = MagicMock()
_mock_aetest_steps_impl = MagicMock()

# Wire the hierarchy: pyats.aetest -> _mock_aetest
_mock_pyats_pkg = MagicMock()
_mock_pyats_pkg.aetest = _mock_aetest


@pytest.fixture(autouse=True)
def mock_pyats() -> Any:
    """Mock PyATS module to avoid import errors in test environment."""
    with patch.dict(
        "sys.modules",
        {
            "pyats": _mock_pyats_pkg,
            "pyats.aetest": _mock_aetest,
            "pyats.aetest.steps": _mock_aetest_steps,
            "pyats.aetest.steps.implementation": _mock_aetest_steps_impl,
        },
    ):
        yield


@pytest.fixture
def nac_test_base_class() -> Any:
    """Import and return the real NACTestBase class (with PyATS mocked)."""
    import sys

    # Clear cached module to force reimport with mocked pyats
    for mod_name in list(sys.modules):
        if "base_test" in mod_name or "step_interceptor" in mod_name:
            del sys.modules[mod_name]

    from nac_test.pyats_core.common.base_test import NACTestBase

    return NACTestBase


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
        """get_default_value auto-detects ACI controller and uses defaults.apic prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("fabric.name")

        # Should auto-detect ACI and use defaults.apic prefix
        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.apic"
        assert "ACI defaults file required" in kwargs["missing_error"]
        assert result is sentinel.result

    def test_sdwan_autodetection(
        self,
        nac_test_base_class: Any,
        sdwan_data_model: dict[str, Any],
        sdwan_controller_env: None,
    ) -> None:
        """get_default_value auto-detects SD-WAN controller and uses defaults.sdwan prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = sdwan_data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("global.timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.sdwan"
        assert "SDWAN defaults file required" in kwargs["missing_error"]
        assert result is sentinel.result

    def test_cc_autodetection(
        self,
        nac_test_base_class: Any,
        cc_controller_env: None,
    ) -> None:
        """get_default_value auto-detects Catalyst Center and uses defaults.catc prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = {"defaults": {"catc": {"timeout": 30}}}

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.catc"
        assert "CC defaults file required" in kwargs["missing_error"]
        assert result is sentinel.result

    def test_iosxe_autodetection(
        self,
        nac_test_base_class: Any,
        iosxe_controller_env: None,
    ) -> None:
        """get_default_value auto-detects IOS-XE and uses defaults.iosxe prefix."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = {"defaults": {"iosxe": {"timeout": 30}}}

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
            return_value=sentinel.result,
        ) as mock_resolve:
            result = instance.get_default_value("timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.iosxe"
        assert "IOSXE defaults file required" in kwargs["missing_error"]
        assert result is sentinel.result

    def test_no_controller_credentials_raises(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """get_default_value raises ValueError when no controller credentials found."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model

        with pytest.raises(ValueError) as exc_info:
            instance.get_default_value("fabric.name")

        error_message = str(exc_info.value)
        assert "Cannot resolve defaults - controller detection failed" in error_message
        assert "No controller credentials found" in error_message

    def test_delegates_to_resolver_with_cascade_paths(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
        aci_controller_env: None,
    ) -> None:
        """get_default_value delegates cascade paths to _resolve correctly."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
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
            missing_error="ACI defaults file required. Pass -d ./defaults/ to include defaults.apic configuration.",
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

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
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

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
        ) as mock_resolve:
            instance.get_default_value("key")

        args, _ = mock_resolve.call_args
        assert args[0] is data_model
