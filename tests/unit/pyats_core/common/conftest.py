# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for pyats_core common module tests."""

from typing import Any

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
