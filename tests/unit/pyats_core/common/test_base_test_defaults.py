# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for NACTestBase.get_default_value() delegation to defaults_resolver.

This module verifies that the get_default_value() instance method on NACTestBase:
- Guards against missing DEFAULTS_PREFIX with NotImplementedError
- Delegates to defaults_resolver.get_default_value with correct arguments
- Threads through DEFAULTS_PREFIX and DEFAULTS_MISSING_ERROR class attributes

Note:
    Cascade behavior, falsy value handling, error messages, and edge cases
    are thoroughly tested in test_defaults_resolver.py. These tests focus
    exclusively on the delegation contract between NACTestBase and the
    defaults_resolver utility.
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
    """Tests for NACTestBase.get_default_value() delegation contract.

    These tests verify that the instance method correctly guards on
    DEFAULTS_PREFIX and delegates to defaults_resolver.get_default_value
    with the proper arguments from class attributes.
    """

    def test_prefix_none_raises_not_implemented(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """get_default_value raises NotImplementedError when DEFAULTS_PREFIX is None."""
        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.data_model = apic_data_model
        # DEFAULTS_PREFIX is None by default on NACTestBase

        with pytest.raises(NotImplementedError) as exc_info:
            instance.get_default_value("fabric.name")

        error_message = str(exc_info.value)
        assert "does not support defaults resolution" in error_message
        assert "Set DEFAULTS_PREFIX" in error_message

    def test_class_name_in_not_implemented_error(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """NotImplementedError includes the concrete subclass name."""

        class MyConcreteTest(nac_test_base_class):  # type: ignore[misc]
            pass  # DEFAULTS_PREFIX is still None

        instance = MyConcreteTest.__new__(MyConcreteTest)
        instance.data_model = apic_data_model

        with pytest.raises(NotImplementedError) as exc_info:
            instance.get_default_value("some.path")

        assert "MyConcreteTest" in str(exc_info.value)

    def test_delegates_to_resolver_with_correct_args(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """get_default_value delegates to _resolve with all arguments threaded through."""

        class APICTestBase(nac_test_base_class):  # type: ignore[misc]
            DEFAULTS_PREFIX = "defaults.apic"
            DEFAULTS_MISSING_ERROR = "APIC defaults required."

        instance = APICTestBase.__new__(APICTestBase)
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
            missing_error="APIC defaults required.",
            required=False,
        )
        assert result is sentinel.result

    def test_default_error_message_threaded_through(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """Default DEFAULTS_MISSING_ERROR value is passed when not overridden."""

        class TestBase(nac_test_base_class):  # type: ignore[misc]
            DEFAULTS_PREFIX = "defaults.apic"
            # Don't override DEFAULTS_MISSING_ERROR — use base class default

        instance = TestBase.__new__(TestBase)
        instance.data_model = apic_data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
        ) as mock_resolve:
            instance.get_default_value("some.path")

        _, kwargs = mock_resolve.call_args
        assert "Defaults block not found in data model" in kwargs["missing_error"]
        assert (
            "Ensure the defaults file is passed to nac-test" in kwargs["missing_error"]
        )

    def test_required_defaults_to_true(
        self,
        nac_test_base_class: Any,
        apic_data_model: dict[str, Any],
    ) -> None:
        """required parameter defaults to True when not explicitly passed."""

        class TestBase(nac_test_base_class):  # type: ignore[misc]
            DEFAULTS_PREFIX = "defaults.apic"

        instance = TestBase.__new__(TestBase)
        instance.data_model = apic_data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
        ) as mock_resolve:
            instance.get_default_value("some.path")

        _, kwargs = mock_resolve.call_args
        assert kwargs["required"] is True

    def test_subclass_prefix_overrides_base(
        self,
        nac_test_base_class: Any,
        sdwan_data_model: dict[str, Any],
    ) -> None:
        """Subclass DEFAULTS_PREFIX and DEFAULTS_MISSING_ERROR override base values."""

        class SDWANTestBase(nac_test_base_class):  # type: ignore[misc]
            DEFAULTS_PREFIX = "defaults.sdwan"
            DEFAULTS_MISSING_ERROR = "SD-WAN defaults required."

        instance = SDWANTestBase.__new__(SDWANTestBase)
        instance.data_model = sdwan_data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
        ) as mock_resolve:
            instance.get_default_value("global.timeout")

        _, kwargs = mock_resolve.call_args
        assert kwargs["defaults_prefix"] == "defaults.sdwan"
        assert kwargs["missing_error"] == "SD-WAN defaults required."

    def test_data_model_passed_to_resolver(
        self,
        nac_test_base_class: Any,
    ) -> None:
        """The instance's data_model is passed as the first positional argument."""
        data_model = {"defaults": {"apic": {"key": "value"}}}

        class TestBase(nac_test_base_class):  # type: ignore[misc]
            DEFAULTS_PREFIX = "defaults.apic"

        instance = TestBase.__new__(TestBase)
        instance.data_model = data_model

        with patch(
            "nac_test.pyats_core.common.base_test._resolve",
        ) as mock_resolve:
            instance.get_default_value("key")

        args, _ = mock_resolve.call_args
        assert args[0] is data_model
