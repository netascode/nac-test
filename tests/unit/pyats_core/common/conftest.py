# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for pyats_core common module tests."""

from typing import Any
from unittest.mock import MagicMock

import pytest


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
# PyATS Mocking Infrastructure
# =============================================================================

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
    from unittest.mock import patch

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
